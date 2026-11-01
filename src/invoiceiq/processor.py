import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import fitz
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from invoiceiq.config import settings
from invoiceiq.schemas import DocumentType


class DocumentProcessingError(ValueError):
    pass


@dataclass
class TextResult:
    text: str
    method: str
    document_type: DocumentType
    evidence: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DocumentProcessor:
    signatures: ClassVar[dict[bytes, str]] = {
        b"%PDF-": "application/pdf",
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG\r\n\x1a\n": "image/png",
    }

    def detect_mime(self, payload: bytes) -> str:
        for signature, mime_type in self.signatures.items():
            if payload.startswith(signature):
                return mime_type
        raise DocumentProcessingError(
            "Unsupported or invalid file signature. Upload a PDF, JPG, or PNG."
        )

    def process(self, path: Path, mime_type: str) -> TextResult:
        if mime_type == "application/pdf":
            return self._process_pdf(path)
        return self._process_image(path)

    def _process_pdf(self, path: Path) -> TextResult:
        try:
            pdf = fitz.open(path)
        except fitz.FileDataError as error:
            raise DocumentProcessingError(
                "The PDF is corrupt or cannot be opened."
            ) from error
        with pdf:
            if pdf.needs_pass:
                raise DocumentProcessingError(
                    "Password-protected PDFs are not supported."
                )
            if pdf.page_count == 0:
                raise DocumentProcessingError("The PDF has no pages.")
            if pdf.page_count > settings.max_pdf_pages:
                raise DocumentProcessingError(
                    f"The PDF has {pdf.page_count} pages, above the configured limit of {settings.max_pdf_pages}."
                )
            chunks: list[str] = []
            evidence: dict[str, dict] = {}
            warnings: list[str] = []
            used_ocr = False
            for page_index, page in enumerate(pdf):
                page_text = page.get_text("text").strip()
                if len(page_text) >= 30:
                    chunks.append(page_text)
                    evidence[f"page_{page_index + 1}"] = {
                        "page": page_index + 1,
                        "text": page_text[:500],
                    }
                    continue
                used_ocr = True
                pixmap = page.get_pixmap(dpi=160, alpha=False)
                result = self._ocr(
                    Image.open(io.BytesIO(pixmap.tobytes("png"))), page_index + 1
                )
                chunks.append(result.text)
                evidence.update(result.evidence)
                warnings.extend(result.warnings)
            text = "\n".join(chunk for chunk in chunks if chunk).strip()
            if not text:
                warnings.append("EMPTY_TEXT_EXTRACTION")
            return TextResult(
                text=text,
                method="pdf_text_and_ocr" if used_ocr else "pdf_text",
                document_type=self._classify(text),
                evidence=evidence,
                warnings=warnings,
            )

    def _process_image(self, path: Path) -> TextResult:
        try:
            with Image.open(path) as original:
                original.verify()
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise DocumentProcessingError(
                "The image is corrupt or unsupported."
            ) from error
        width, height = image.size
        if width * height > 80_000_000:
            raise DocumentProcessingError(
                "The image dimensions exceed the safe processing limit."
            )
        result = self._ocr(image, 1)
        return TextResult(
            text=result.text,
            method="ocr",
            document_type=self._classify(result.text),
            evidence=result.evidence,
            warnings=result.warnings,
        )

    def _ocr(self, image: Image.Image, page: int) -> TextResult:
        if shutil.which("tesseract") is None:
            return TextResult(
                text="",
                method="ocr_unavailable",
                document_type=DocumentType.UNKNOWN,
                warnings=["TESSERACT_UNAVAILABLE"],
            )
        import pytesseract

        prepared = ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(1.5)
        try:
            rows = pytesseract.image_to_data(
                prepared,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",
                timeout=30,
            )
        except (RuntimeError, pytesseract.TesseractError) as error:
            return TextResult(
                text="",
                method="ocr",
                document_type=DocumentType.UNKNOWN,
                warnings=[f"OCR_FAILED: {str(error)[:120]}"],
            )
        words: list[str] = []
        evidence: dict[str, dict] = {}
        confidences: list[float] = []
        for index, text in enumerate(rows["text"]):
            word = text.strip()
            confidence = float(rows["conf"][index])
            if not word:
                continue
            words.append(word)
            if confidence >= 0:
                confidences.append(confidence)
            evidence[f"word_{index}"] = {
                "page": page,
                "text": word,
                "box": [
                    rows["left"][index],
                    rows["top"][index],
                    rows["width"][index],
                    rows["height"][index],
                ],
            }
        warnings = []
        if confidences and sum(confidences) / len(confidences) < 55:
            warnings.append("LOW_OCR_CONFIDENCE")
        return TextResult(
            text=" ".join(words),
            method="ocr",
            document_type=self._classify(" ".join(words)),
            evidence=evidence,
            warnings=warnings,
        )

    @staticmethod
    def _classify(text: str) -> DocumentType:
        upper = text.upper()
        if "ADJUSTMENT" in upper or "CREDIT NOTE" in upper:
            return DocumentType.ADJUSTMENT_NOTE
        if "PURCHASE ORDER" in upper or "PO-" in upper or "BILL TO" in upper:
            return DocumentType.B2B_INVOICE
        if "RECEIPT" in upper or "CASH" in upper or "CHANGE" in upper:
            return DocumentType.RETAIL_RECEIPT
        return DocumentType.UNKNOWN
