import hashlib
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invoiceiq.config import settings
from invoiceiq.db import Base, SessionLocal, create_schema, get_session
from invoiceiq.models import DecisionRecord, DocumentRecord, ProcessingRunRecord
from invoiceiq.processor import DocumentProcessor
from invoiceiq.schemas import (
    DecisionOutcome,
    DocumentSummary,
    ReviewRequest,
    RunView,
    StageEventView,
)
from invoiceiq.seed import seed_reference_data
from invoiceiq.workflow import workflow


def utcnow() -> datetime:
    return datetime.now(UTC)


def run_view(run: ProcessingRunRecord) -> RunView:
    return RunView(
        id=run.id,
        document_id=run.document_id,
        status=run.status,
        stage=run.stage,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error=run.error,
        model_version=run.model_version,
        events=[
            StageEventView(
                stage=item.stage,
                status=item.status,
                occurred_at=item.occurred_at,
                detail=item.detail,
            )
            for item in run.events
        ],
    )


def document_view(document: DocumentRecord) -> dict:
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "sha256": document.sha256,
        "document_type": document.document_type,
        "uploaded_at": document.uploaded_at,
        "extraction": document.extraction_json,
        "raw_text": document.raw_text,
        "decision": None
        if document.decision is None
        else {
            "outcome": document.decision.outcome,
            "reason_codes": document.decision.reason_codes,
            "explanation": document.decision.explanation,
            "suggested_po": document.decision.suggested_po,
            "checks": document.decision.checks,
            "reviewer_actions": document.decision.reviewer_actions,
        },
        "runs": [run_view(run).model_dump(mode="json") for run in document.runs],
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_schema()
    with SessionLocal() as session:
        seed_reference_data(session)
        interrupted = session.scalars(
            select(ProcessingRunRecord).where(ProcessingRunRecord.status == "RUNNING")
        ).all()
        for run in interrupted:
            run.status, run.stage, run.error, run.ended_at = (
                "FAILED",
                "FAILED",
                "INTERRUPTED_BY_RESTART",
                utcnow(),
            )
        session.commit()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield
    await workflow.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="InvoiceIQ API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok", "service": "invoiceiq"}

    @app.get("/api/v1/health/dependencies")
    def dependency_health() -> dict:
        import shutil as dependency_shutil

        import httpx

        ollama = False
        try:
            ollama = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5
            ).is_success
        except httpx.HTTPError:
            pass
        return {
            "database": "ok",
            "tesseract": dependency_shutil.which("tesseract") is not None,
            "ollama": ollama,
            "ollama_model": settings.ollama_model,
            "rule_only": settings.rule_only,
        }

    @app.post("/api/v1/documents", status_code=202)
    async def upload_document(
        file: UploadFile = File(...), session: Session = Depends(get_session)
    ) -> dict:
        filename = Path(file.filename or "document").name
        payload = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if not payload:
            raise HTTPException(status_code=422, detail="The uploaded file is empty.")
        if len(payload) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"Files may not exceed {settings.max_upload_mb} MB.",
            )
        try:
            mime_type = DocumentProcessor().detect_mime(payload)
        except ValueError as error:
            raise HTTPException(status_code=415, detail=str(error)) from error
        document_id, run_id = str(uuid.uuid4()), str(uuid.uuid4())
        storage_path = (
            settings.upload_dir / f"{document_id}{Path(filename).suffix.lower()}"
        )
        storage_path.write_bytes(payload)
        document = DocumentRecord(
            id=document_id,
            original_filename=filename[:255],
            mime_type=mime_type,
            sha256=hashlib.sha256(payload).hexdigest(),
            storage_path=str(storage_path),
            content=payload,
        )
        run = ProcessingRunRecord(
            id=run_id, document_id=document_id, status="QUEUED", stage="RECEIVED"
        )
        session.add_all([document, run])
        session.commit()
        workflow.submit(run_id)
        return {"document_id": document_id, "run_id": run_id, "status": "QUEUED"}

    @app.get("/api/v1/documents", response_model=list[DocumentSummary])
    def list_documents(
        status: str | None = Query(default=None),
        search: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> list[DocumentSummary]:
        query = select(DocumentRecord).order_by(DocumentRecord.uploaded_at.desc())
        if search:
            query = query.where(
                DocumentRecord.original_filename.ilike(f"%{search[:100]}%")
            )
        documents = session.scalars(query).all()
        summaries = []
        for item in documents:
            if status and (not item.decision or item.decision.outcome != status):
                continue
            latest_run = item.runs[-1] if item.runs else None
            summaries.append(
                DocumentSummary(
                    id=item.id,
                    original_filename=item.original_filename,
                    mime_type=item.mime_type,
                    sha256=item.sha256,
                    document_type=item.document_type,
                    uploaded_at=item.uploaded_at,
                    decision_outcome=item.decision.outcome if item.decision else None,
                    run_id=latest_run.id if latest_run else None,
                    run_status=latest_run.status if latest_run else None,
                    run_stage=latest_run.stage if latest_run else None,
                    stage_event_count=len(latest_run.events) if latest_run else 0,
                )
            )
        return summaries

    @app.get("/api/v1/documents/{document_id}")
    def get_document(document_id: str, session: Session = Depends(get_session)) -> dict:
        document = session.get(DocumentRecord, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
        return document_view(document)

    @app.get("/api/v1/documents/{document_id}/file")
    def get_document_file(
        document_id: str, session: Session = Depends(get_session)
    ) -> Response:
        document = session.get(DocumentRecord, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Stored document not found.")
        if document.content is not None:
            return Response(content=document.content, media_type=document.mime_type)
        if not Path(document.storage_path).is_file():
            raise HTTPException(status_code=404, detail="Stored document not found.")
        return FileResponse(
            document.storage_path,
            media_type=document.mime_type,
        )

    @app.get("/api/v1/runs/{run_id}", response_model=RunView)
    def get_run(run_id: str, session: Session = Depends(get_session)) -> RunView:
        run = session.get(ProcessingRunRecord, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found.")
        return run_view(run)

    @app.get("/api/v1/dashboard/summary")
    def dashboard_summary(session: Session = Depends(get_session)) -> dict:
        documents = (
            session.scalar(select(func.count()).select_from(DocumentRecord)) or 0
        )
        grouped = dict(
            session.execute(
                select(DecisionRecord.outcome, func.count()).group_by(
                    DecisionRecord.outcome
                )
            ).all()
        )
        failed = (
            session.scalar(
                select(func.count())
                .select_from(ProcessingRunRecord)
                .where(ProcessingRunRecord.status == "FAILED")
            )
            or 0
        )
        recent = session.scalars(
            select(DocumentRecord).order_by(DocumentRecord.uploaded_at.desc()).limit(8)
        ).all()
        return {
            "counts": {
                "processed": documents,
                "approved": grouped.get("APPROVED", 0),
                "needs_review": grouped.get("NEEDS_REVIEW", 0),
                "blocked": grouped.get("BLOCKED", 0),
                "failed": failed,
            },
            "recent": [document_view(item) for item in recent],
        }

    @app.get("/api/v1/vendors")
    def vendors(session: Session = Depends(get_session)) -> list[dict]:
        from invoiceiq.models import VendorRecord

        return [
            {
                "id": item.id,
                "legal_name": item.legal_name,
                "aliases": item.aliases,
                "tax_id": item.tax_id,
                "status": item.status,
                "currency": item.currency,
            }
            for item in session.scalars(
                select(VendorRecord).order_by(VendorRecord.legal_name)
            ).all()
        ]

    @app.get("/api/v1/purchase-orders")
    def purchase_orders(session: Session = Depends(get_session)) -> list[dict]:
        from invoiceiq.models import PurchaseOrderRecord

        return [
            {
                "id": item.id,
                "vendor_id": item.vendor_id,
                "currency": item.currency,
                "authorized_total": str(item.authorized_total),
                "approved_consumed": str(item.approved_consumed),
                "remaining_balance": str(
                    item.authorized_total - item.approved_consumed
                ),
                "status": item.status,
            }
            for item in session.scalars(
                select(PurchaseOrderRecord).order_by(PurchaseOrderRecord.id)
            ).all()
        ]

    @app.get("/api/v1/reviews")
    def reviews(session: Session = Depends(get_session)) -> list[dict]:
        items = session.scalars(
            select(DocumentRecord)
            .join(DecisionRecord)
            .where(DecisionRecord.outcome == DecisionOutcome.NEEDS_REVIEW.value)
            .order_by(DocumentRecord.uploaded_at.desc())
        ).all()
        return [document_view(item) for item in items]

    @app.post("/api/v1/documents/{document_id}/review")
    def review_document(
        document_id: str,
        request: ReviewRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        document = session.get(DocumentRecord, document_id)
        if not document or not document.decision:
            raise HTTPException(status_code=404, detail="Document decision not found.")
        if document.decision.outcome != DecisionOutcome.NEEDS_REVIEW.value:
            raise HTTPException(
                status_code=409,
                detail="Only needs-review records may receive a reviewer decision.",
            )
        if request.action == DecisionOutcome.BLOCKED:
            raise HTTPException(
                status_code=422,
                detail="Use APPROVED or NEEDS_REVIEW as a human resolution action.",
            )
        document.decision.reviewer_actions = [
            *document.decision.reviewer_actions,
            {
                "action": request.action.value,
                "reviewer": request.reviewer,
                "note": request.note,
                "at": utcnow().isoformat(),
            },
        ]
        if request.action == DecisionOutcome.APPROVED:
            extraction = document.extraction_json or {}
            po_id, total = document.decision.suggested_po, extraction.get("grand_total")
            if not po_id or total is None:
                raise HTTPException(
                    status_code=422,
                    detail="A reviewer cannot approve without a reconciled PO and total.",
                )
            from decimal import Decimal

            from invoiceiq.models import PurchaseOrderRecord

            po = session.get(PurchaseOrderRecord, po_id)
            amount = Decimal(total)
            if (
                not po
                or po.status != "OPEN"
                or Decimal(str(po.authorized_total))
                - Decimal(str(po.approved_consumed))
                < amount
            ):
                raise HTTPException(
                    status_code=409,
                    detail="The PO is no longer available for this approval.",
                )
            po.approved_consumed = Decimal(str(po.approved_consumed)) + amount
            document.decision.outcome = DecisionOutcome.APPROVED.value
        session.commit()
        return document_view(document)

    @app.post("/api/v1/demo/reseed")
    def reseed_demo(session: Session = Depends(get_session)) -> dict:
        if not settings.demo_mode:
            raise HTTPException(status_code=404, detail="Demo reset is disabled.")
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        shutil.rmtree(settings.upload_dir, ignore_errors=True)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        seed_reference_data(session)
        return {"status": "reseeded", "warning": "Local demo data was cleared."}

    return app
