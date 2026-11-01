# Demo runbook

## Start the application

1. Copy `.env.example` to `.env` and run the backend and Vite commands in the README.
2. Run `uv run python scripts/generate_demo_data.py` to create eight synthetic PDFs.
3. Open the dashboard. The vendor and PO ledgers are seeded, but document counts are honest zeroes until a document is uploaded.

## Happy path with Ollama

1. Start `ollama serve` and install `qwen2.5:1.5b-instruct`.
2. Upload `data/generated/invoices/01_clean_acme.pdf`.
3. Open its workspace. Verify the original document preview, persisted stage timeline, extracted vendor, PO, MYR 1060.00 total, rule checks, and final decision.
4. A successful approval requires a real Ollama extraction with all critical fields. It commits the amount against the PO only after all checks pass.

## Edge cases

- Upload `03_acme_duplicate_name.pdf` after the clean Acme sample. Its vendor plus invoice number identifies a duplicate and results in `BLOCKED`.
- Upload `04_acme_over_balance.pdf`. Its amount exceeds the partially consumed PO balance and results in `NEEDS_REVIEW`.
- Upload `06_missing_po.pdf`. It remains `NEEDS_REVIEW` with `PO_REFERENCE_MISSING`.
- Upload a supplied JPG after installing Tesseract. It receives OCR and remains `NEEDS_REVIEW` unless explicit verified B2B PO evidence exists.

## Review and reset

Use `POST /api/v1/documents/{id}/review` with `reviewer`, `note`, and `action` (`APPROVED` or `NEEDS_REVIEW`) to append an audit record. A human approval still requires a reconciled open PO with available balance. `POST /api/v1/demo/reseed` is available only when `DEMO_MODE=true` and clears local demo data.

## Current local verification

- The synthetic PDF workflow was run with `RULE_ONLY=true`: technical run `COMPLETED`, 14 persisted events, extracted total `1060.00`, and a conservative `NEEDS_REVIEW` with `AI_UNAVAILABLE`.
- Tesseract was not installed and the Ollama client found no running server in this environment. No receipt accuracy or model-extraction claim is made.
- The test environment blocks loopback sockets, so HTTP and browser interaction must be verified on a normal local machine using the commands above.
