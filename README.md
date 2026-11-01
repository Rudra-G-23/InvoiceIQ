# InvoiceIQ

InvoiceIQ is a local, explainable invoice-to-purchase-order validation demo. It accepts PDF and image documents, extracts text, optionally calls a local Ollama model for structured fields, and applies deterministic `Decimal`-based vendor, PO, duplicate, balance, and arithmetic rules. `APPROVED` means the document passed the configurable demo AP policy. It never initiates a payment.

## Quick start

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/), Node 20+, and optionally system Tesseract plus Ollama.

```bash
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv sync --all-groups
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run python scripts/generate_demo_data.py
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run uvicorn invoiceiq.main:app --host 127.0.0.1 --port 8000 --reload
```

An ignored local `.env` is included with safe development defaults. For a clean clone, copy `.env.example` to `.env`. Keep `RULE_ONLY=false` when Ollama is running. Set `RULE_ONLY=true` for a fast reproducible diagnostic flow that does not auto-approve documents.

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API is available at `http://127.0.0.1:8000/docs` and health is at `GET /api/v1/health`.

## Backend only

From the repository root, run:

```bash
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run uvicorn invoiceiq.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify it in another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/dependencies
```

To exercise a real upload without Ollama, temporarily set `RULE_ONLY=true` in `.env`, restart the backend, then upload a generated fixture:

```bash
curl -F "file=@data/generated/invoices/01_clean_acme.pdf;type=application/pdf" http://127.0.0.1:8000/api/v1/documents
```

Poll the returned `run_id` at `GET /api/v1/runs/{run_id}`. The run should complete with a persisted timeline and `NEEDS_REVIEW` plus `AI_UNAVAILABLE`, which is the deliberate conservative result for rule-only mode.

For a deterministic diagnostic pass without Ollama, set `RULE_ONLY=true` before starting the backend. This mode retains labeled field candidates but deliberately produces `AI_UNAVAILABLE` and does not auto-approve documents.

## Optional local dependencies

```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr
ollama serve
ollama pull qwen2.5:1.5b-instruct
```

Tesseract handles JPG, PNG, and scanned PDF pages. Ollama receives text only, with a bounded JSON-schema request, then Pydantic validates the result. If either dependency is unavailable, the processing record reports the problem instead of claiming successful AI extraction.

## Demo data and policy

Generate the eight intentionally fictional fixture PDFs with `uv run python scripts/generate_demo_data.py`. They are stored under ignored `data/generated/` and are visibly labeled synthetic. The seed ledger contains three approved MYR vendors, one inactive vendor, and three POs including a partially consumed balance.

The generator also renders the approved vendor-and-PO fixtures as PNG previews in `data/generated/vendor-matched/`. These are synthetic copies for fast visual testing only. The real supplied receipt images are never presented as vendor matches.

The 20 supplied receipt images currently reside at `data/raw-Inovoice-20/` and are ignored pending independent licence confirmation. See [docs/DATA_IMPORT.md](docs/DATA_IMPORT.md). Retail receipts and adjustment notes without an authorized PO always need review. Invoice text is untrusted data, never instructions.

To copy only receipts that OCR can exactly identify as a seeded system vendor, run:

```bash
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run python scripts/copy_vendor_matched_receipts.py
```

Copies are written to `data/receipts/vendor-matched/` and remain ignored. The current supplied set has no exact matches to the fictional InvoiceIQ vendor ledger, so the copier correctly creates no receipt copies.

## Checks

```bash
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/invoiceiq-uv-cache uv run pytest -q
cd frontend && npm run build
```

The local architecture and limits are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). A presenter-oriented scenario guide is in [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md).
