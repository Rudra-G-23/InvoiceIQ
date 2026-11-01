# Vendor-matched receipt copies

Run `uv run python scripts/copy_vendor_matched_receipts.py` to copy only supplied receipt images whose OCR text contains an exact alias for a seeded InvoiceIQ vendor. Copied files and the generated manifest are ignored because the supplied images may be third-party material.

No file is copied when the vendor identity is unknown or ambiguous. This directory never treats a retail receipt as an approved invoice.
