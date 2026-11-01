from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invoiceiq.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentRecord(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    document_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    storage_path: Mapped[str] = mapped_column(Text)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped["DecisionRecord | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    runs: Mapped[list["ProcessingRunRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class VendorRecord(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), unique=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="APPROVED")
    currency: Mapped[str] = mapped_column(String(3), default="MYR")


class PurchaseOrderRecord(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    authorized_total: Mapped[float] = mapped_column(Numeric(14, 2))
    approved_consumed: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")


class ProcessingRunRecord(Base):
    __tablename__ = "processing_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    stage: Mapped[str] = mapped_column(String(50), default="RECEIVED")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    document: Mapped[DocumentRecord] = relationship(back_populates="runs")
    events: Mapped[list["StageEventRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StageEventRecord.sequence",
    )


class StageEventRecord(Base):
    __tablename__ = "stage_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("processing_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    run: Mapped[ProcessingRunRecord] = relationship(back_populates="events")


class DecisionRecord(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(20))
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    suggested_po: Mapped[str | None] = mapped_column(String(50), nullable=True)
    checks: Mapped[list] = mapped_column(JSON, default=list)
    reviewer_actions: Mapped[list] = mapped_column(JSON, default=list)
    document: Mapped[DocumentRecord] = relationship(back_populates="decision")
