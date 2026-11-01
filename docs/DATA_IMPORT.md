# Receipt data handling

The currently available 20 JPGs are in `data/raw-Inovoice-20/`. They are not committed and remain gitignored because redistribution rights have not been independently verified. To evaluate another licensed copy, place files in `data/receipts/raw/` and run `uv run python scripts/evaluate_receipts.py data/receipts/raw` after installing Tesseract.

The evaluator reports observed OCR text, timing, and extracted values. It does not use hard-coded expected values or infer PO references. Retail receipts without a reliable PO must remain `NEEDS_REVIEW`.

`uv run python scripts/copy_vendor_matched_receipts.py` performs a separate exact-match OCR pass. It copies a receipt into `data/receipts/vendor-matched/` only when text contains an exact seeded vendor alias. Unknown and ambiguous receipts are not copied or approved.
