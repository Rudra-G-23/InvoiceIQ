import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoiceiq.db import Base
from invoiceiq.extractor import BaselineExtractor
from invoiceiq.models import DocumentRecord
from invoiceiq.processor import DocumentProcessingError, DocumentProcessor, TextResult
from invoiceiq.schemas import DocumentType


def test_rejects_extension_spoofed_content() -> None:
    with pytest.raises(DocumentProcessingError):
        DocumentProcessor().detect_mime(b"not an invoice")


def test_detects_pdf_signature() -> None:
    assert DocumentProcessor().detect_mime(b"%PDF-1.7 fake") == "application/pdf"


def test_total_parser_does_not_use_subtotal_as_grand_total() -> None:
    result = TextResult(
        text="Subtotal: MYR 1000.00\nTax: MYR 60.00\nGrand Total: MYR 1060.00",
        method="pdf_text",
        document_type=DocumentType.B2B_INVOICE,
    )
    assert BaselineExtractor().extract(result, "rule_only").grand_total == 1060


def test_document_content_is_persisted_in_database() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            DocumentRecord(
                id="document-blob",
                original_filename="receipt.jpg",
                mime_type="image/jpeg",
                sha256="a" * 64,
                storage_path="/unused/receipt.jpg",
                content=b"receipt-bytes",
            )
        )
        session.commit()
        assert session.get(DocumentRecord, "document-blob").content == b"receipt-bytes"
