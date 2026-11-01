"""Copy supplied receipts only when OCR proves an exact seeded-vendor match."""

import json
import shutil
from pathlib import Path

from invoiceiq.decision import normalized
from invoiceiq.processor import DocumentProcessor
from invoiceiq.seed import VENDORS

SOURCE_DIR = Path("data/raw-Inovoice-20")
TARGET_DIR = Path("data/receipts/vendor-matched")


def vendor_matches(text: str) -> list[dict[str, str]]:
    normalized_text = normalized(text)
    matches = []
    for vendor_id, legal_name, aliases, _tax_id, _status in VENDORS:
        names = [legal_name, *aliases]
        if any(normalized(name) in normalized_text for name in names):
            matches.append({"vendor_id": vendor_id, "vendor_name": legal_name})
    return matches


def write_manifest(copied: list[dict], skipped: list[dict]) -> None:
    (TARGET_DIR / "matches.json").write_text(
        json.dumps({"copied": copied, "skipped": skipped}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"Source directory not found: {SOURCE_DIR}")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = TARGET_DIR / "matches.json"
    existing = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    copied = existing.get("copied", [])
    skipped = existing.get("skipped", [])
    processed_files = {item["file"] for item in [*copied, *skipped]}
    processor = DocumentProcessor()
    for path in sorted(SOURCE_DIR.glob("*")):
        if not path.is_file() or path.name in processed_files:
            continue
        mime_type = processor.detect_mime(path.read_bytes()[:16])
        result = processor.process(path, mime_type)
        matches = vendor_matches(result.text)
        if len(matches) == 1:
            target = TARGET_DIR / path.name
            shutil.copy2(path, target)
            copied.append({"file": path.name, "target": str(target), **matches[0]})
        else:
            skipped.append(
                {"file": path.name, "matches": matches, "warnings": result.warnings}
            )
        write_manifest(copied, skipped)
    evaluated_files = {item["file"] for item in [*copied, *skipped]}
    print(
        f"Copied {len(copied)} exact vendor-matched receipts to {TARGET_DIR}; evaluated {len(evaluated_files)} of {len(list(SOURCE_DIR.glob('*')))} source files"
    )


if __name__ == "__main__":
    main()
