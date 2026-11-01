# InvoiceIQ architecture

InvoiceIQ is a local, single-user demonstration application. A FastAPI API owns SQLite persistence, stores the original upload bytes in the `documents.content` BLOB, keeps a generated filesystem copy only as a legacy fallback, and submits each document to a single-worker in-process executor. The browser polls persisted run events. This is deliberately not a distributed job queue and is not a multi-tenant production deployment.

## Decision boundary

Document text is untrusted input. `DocumentProcessor` obtains embedded PDF text or Tesseract OCR with provenance. `OllamaExtractor` may map text to the canonical schema, but its output is Pydantic-validated and never decides approval. `DecisionEngine` is pure deterministic Python using `Decimal`; it records each fact and check before yielding `APPROVED`, `NEEDS_REVIEW`, or `BLOCKED`.

The conservative policy is: confirmed duplicates are `BLOCKED`; retail receipts, adjustment notes, missing evidence, unavailable AI, and reconciliation uncertainty are `NEEDS_REVIEW`; only a verified B2B invoice with an explicit open PO, approved vendor, matching MYR currency, valid arithmetic, and available approved balance is `APPROVED`.

## Local limits and data

Uploads are content-signature checked, stored using UUID filenames, limited to 10 MB and eight PDF pages by default, and never interpreted as paths or executable instructions. Raw user uploads and third-party receipts are gitignored. The included fixture generator creates clearly labeled synthetic demonstration PDFs and a ledger. It does not represent real invoices.

The default setup uses `uv`, Python 3.13+, SQLite, PyMuPDF, Pillow, optional system Tesseract, and optional local Ollama (`qwen2.5:1.5b-instruct`). When either optional service is absent, the run records the missing dependency rather than reporting fabricated success. `RULE_ONLY=true` is a diagnostic mode and is displayed as such in run results.
