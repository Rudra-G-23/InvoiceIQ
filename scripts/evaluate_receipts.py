"""Evaluate local receipt OCR and extraction without asserting fabricated labels."""

import json
import sys
import time
from pathlib import Path

from invoiceiq.extractor import OllamaExtractor
from invoiceiq.processor import DocumentProcessor


def main() -> None:
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/receipts/raw")
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")
    processor, extractor = DocumentProcessor(), OllamaExtractor()
    results = []
    for path in sorted(input_dir.glob("*")):
        if not path.is_file():
            continue
        started = time.perf_counter()
        mime = processor.detect_mime(path.read_bytes()[:16])
        text_result = processor.process(path, mime)
        ocr_finished = time.perf_counter()
        extraction = extractor.extract(text_result)
        results.append(
            {
                "file": path.name,
                "method": text_result.method,
                "ocr_seconds": round(ocr_finished - started, 3),
                "total_seconds": round(time.perf_counter() - started, 3),
                "raw_text_preview": text_result.text[:500],
                "warnings": extraction.warnings,
                "extraction": extraction.model_dump(mode="json"),
                "critical_fields_present": all(
                    [extraction.vendor_raw_name, extraction.grand_total]
                ),
            }
        )
    output = input_dir / "evaluation_results.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} honest evaluation records to {output}")


if __name__ == "__main__":
    main()
