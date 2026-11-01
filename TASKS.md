# InvoiceIQ implementation checklist

Status reflects verified implementation in this working tree, not planned work.

- [x] Phase 0: inspect the repository, runtime, and supplied receipt location.
- [x] Phase 0: document architecture, local assumptions, data handling, and operating limits.
- [x] Phase 1: add domain schema, SQLite persistence, seeded vendor and PO ledger, synthetic fixture PDFs, and deterministic decision tests. Evidence: `tests/test_decision.py`, `scripts/generate_demo_data.py`.
- [x] Phase 2: add safe image/PDF ingestion, text extraction, OCR fallback, provenance, and file-signature tests. Tesseract-dependent receipt verification remains blocked until the system binary is installed.
- [x] Phase 3: add bounded Ollama JSON-schema extraction plus explicit `AI_UNAVAILABLE` and `RULE_ONLY` behavior. No model extraction has been claimed because Ollama is stopped locally.
- [x] Phase 4: complete persisted runs, reconciliation, review audit actions, and direct backend workflow verification. Evidence: a generated PDF recorded 14 persisted events and a completed technical run in `RULE_ONLY` mode.
- [x] Phase 5: build and connect the React UI. Evidence: `frontend/` production build succeeds and routes use real API paths.
- [ ] Phase 6: browser and HTTP verification plus receipt evaluation remain blocked by this environment's loopback restriction and missing system Tesseract/Ollama services.

## Latest verification

- [x] New JPG upload bytes persist in SQLite and the inline preview response exactly matches the original source bytes.
- [x] The document workspace renders image MIME types in an image element and PDFs in an embedded PDF preview.
- [x] Generated synthetic vendor-matched PNG previews are available under `data/generated/vendor-matched/` after running the fixture generator.
- [x] Receipt vendor-match copier evaluated all 20 supplied JPGs with exact seeded-vendor aliases. It found zero matches and copied zero files, preserving the conservative policy.

## Runtime findings

- `uv 0.13.6` is available. Its cache must be directed to a writable local path in this sandbox.
- Python 3.13 virtual environment exists but initially has no application dependencies.
- The 20 JPG samples exist in `data/raw-Inovoice-20/`; this location is gitignored pending licence confirmation.
- Tesseract is not installed. Ollama client is installed but no local server was running at inspection time.
