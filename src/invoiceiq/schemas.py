from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    RETAIL_RECEIPT = "RETAIL_RECEIPT"
    B2B_INVOICE = "B2B_INVOICE"
    ADJUSTMENT_NOTE = "ADJUSTMENT_NOTE"
    UNKNOWN = "UNKNOWN"


class TaxInclusion(StrEnum):
    INCLUSIVE = "INCLUSIVE"
    EXCLUSIVE = "EXCLUSIVE"
    UNKNOWN = "UNKNOWN"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DecisionOutcome(StrEnum):
    APPROVED = "APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class LineItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    tax: Decimal | None = None


class Evidence(BaseModel):
    page: int = 1
    text: str
    box: list[float] | None = None


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    vendor_raw_name: str | None = None
    vendor_display_name: str | None = None
    normalized_vendor_id: str | None = None
    vendor_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_reference: str | None = None
    currency: str | None = None
    currency_source_label: str | None = None
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    tax: Decimal | None = None
    rounding: Decimal | None = None
    grand_total: Decimal | None = None
    cash_tendered: Decimal | None = None
    change: Decimal | None = None
    tax_inclusion: TaxInclusion = TaxInclusion.UNKNOWN
    line_items: list[LineItem] = Field(default_factory=list)
    extraction_method: str
    confidence: float | None = None
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RuleCheck(BaseModel):
    code: str
    status: CheckStatus
    explanation: str
    facts: dict[str, Any] = Field(default_factory=dict)


class DecisionResult(BaseModel):
    outcome: DecisionOutcome
    reason_codes: list[str]
    explanation: str
    suggested_po: str | None = None
    checks: list[RuleCheck]


class DocumentSummary(BaseModel):
    id: str
    original_filename: str
    mime_type: str
    sha256: str
    document_type: DocumentType
    uploaded_at: datetime
    decision_outcome: DecisionOutcome | None = None
    run_id: str | None = None
    run_status: RunStatus | None = None
    run_stage: str | None = None
    stage_event_count: int = 0


class StageEventView(BaseModel):
    stage: str
    status: str
    occurred_at: datetime
    detail: str | None = None


class RunView(BaseModel):
    id: str
    document_id: str
    status: RunStatus
    stage: str
    started_at: datetime | None
    ended_at: datetime | None
    error: str | None
    model_version: str | None
    events: list[StageEventView]


class ReviewRequest(BaseModel):
    action: DecisionOutcome
    reviewer: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)
