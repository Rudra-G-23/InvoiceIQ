from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from invoiceiq.config import settings
from invoiceiq.db import SessionLocal
from invoiceiq.decision import DecisionEngine
from invoiceiq.extractor import OllamaExtractor
from invoiceiq.models import (
    DecisionRecord,
    DocumentRecord,
    ProcessingRunRecord,
    PurchaseOrderRecord,
    StageEventRecord,
)
from invoiceiq.processor import DocumentProcessingError, DocumentProcessor
from invoiceiq.schemas import DecisionOutcome, RunStatus

STAGES = [
    "RECEIVED",
    "CLASSIFY_DOCUMENT",
    "TEXT_EXTRACTION",
    "AI_FIELD_EXTRACTION",
    "SCHEMA_VALIDATION",
    "VENDOR_MATCH",
    "PO_RECONCILIATION",
    "RULE_VALIDATION",
    "DECISION",
    "COMPLETED",
]


def now() -> datetime:
    return datetime.now(UTC)


class WorkflowService:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="invoiceiq-worker"
        )
        self.processor = DocumentProcessor()
        self.extractor = OllamaExtractor()

    def submit(self, run_id: str) -> None:
        self.executor.submit(self.run, run_id)

    def _event(
        self,
        session: Session,
        run: ProcessingRunRecord,
        stage: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        run.stage = stage
        session.add(
            StageEventRecord(
                run_id=run.id,
                sequence=len(run.events) + 1,
                stage=stage,
                status=status,
                detail=detail,
            )
        )
        session.commit()

    def run(self, run_id: str) -> None:
        with SessionLocal() as session:
            run = session.get(ProcessingRunRecord, run_id)
            if run is None or run.status != RunStatus.QUEUED.value:
                return
            document = session.get(DocumentRecord, run.document_id)
            if document is None:
                return
            run.status = RunStatus.RUNNING.value
            run.started_at = now()
            run.model_version = (
                settings.ollama_model if not settings.rule_only else "RULE_ONLY"
            )
            session.commit()
            try:
                self._event(session, run, "CLASSIFY_DOCUMENT", "STARTED")
                text_result = self.processor.process(
                    document.storage_path, document.mime_type
                )
                document.document_type = text_result.document_type.value
                self._event(
                    session,
                    run,
                    "CLASSIFY_DOCUMENT",
                    "COMPLETED",
                    document.document_type,
                )

                self._event(session, run, "TEXT_EXTRACTION", "STARTED")
                document.raw_text = text_result.text
                self._event(
                    session, run, "TEXT_EXTRACTION", "COMPLETED", text_result.method
                )

                self._event(session, run, "AI_FIELD_EXTRACTION", "STARTED")
                extraction = self.extractor.extract(text_result)
                document.extraction_json = extraction.model_dump(mode="json")
                self._event(
                    session,
                    run,
                    "AI_FIELD_EXTRACTION",
                    "COMPLETED",
                    extraction.extraction_method,
                )

                self._event(
                    session,
                    run,
                    "SCHEMA_VALIDATION",
                    "COMPLETED",
                    "Pydantic canonical schema validated",
                )
                self._event(session, run, "VENDOR_MATCH", "STARTED")
                decision = DecisionEngine(session).decide(document, extraction)
                self._event(session, run, "VENDOR_MATCH", "COMPLETED")
                self._event(session, run, "PO_RECONCILIATION", "COMPLETED")
                self._event(session, run, "RULE_VALIDATION", "COMPLETED")
                self._event(session, run, "DECISION", "STARTED")
                session.add(
                    DecisionRecord(
                        document_id=document.id,
                        outcome=decision.outcome.value,
                        reason_codes=decision.reason_codes,
                        explanation=decision.explanation,
                        suggested_po=decision.suggested_po,
                        checks=[
                            check.model_dump(mode="json") for check in decision.checks
                        ],
                        reviewer_actions=[],
                    )
                )
                if (
                    decision.outcome == DecisionOutcome.APPROVED
                    and decision.suggested_po
                    and extraction.grand_total is not None
                ):
                    po = session.get(PurchaseOrderRecord, decision.suggested_po)
                    if (
                        po is None
                        or Decimal(str(po.authorized_total))
                        - Decimal(str(po.approved_consumed))
                        < extraction.grand_total
                    ):
                        raise DocumentProcessingError(
                            "PO balance changed before the approval commitment could be saved."
                        )
                    po.approved_consumed = (
                        Decimal(str(po.approved_consumed)) + extraction.grand_total
                    )
                session.commit()
                self._event(
                    session, run, "DECISION", "COMPLETED", decision.outcome.value
                )
                run.status = RunStatus.COMPLETED.value
                run.ended_at = now()
                self._event(session, run, "COMPLETED", "COMPLETED")
            except Exception as error:  # noqa: BLE001
                session.rollback()
                run = session.get(ProcessingRunRecord, run_id)
                if run:
                    run.status = RunStatus.FAILED.value
                    run.stage = "FAILED"
                    run.error = str(error)[:500]
                    run.ended_at = now()
                    session.add(
                        StageEventRecord(
                            run_id=run.id,
                            sequence=len(run.events) + 1,
                            stage="FAILED",
                            status="FAILED",
                            detail=run.error,
                        )
                    )
                    session.commit()

    async def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)


workflow = WorkflowService()
