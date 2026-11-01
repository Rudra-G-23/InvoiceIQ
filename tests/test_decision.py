from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoiceiq.db import Base
from invoiceiq.decision import DecisionEngine
from invoiceiq.models import DocumentRecord, PurchaseOrderRecord, VendorRecord
from invoiceiq.schemas import DocumentType, ExtractedInvoice, TaxInclusion


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        VendorRecord(
            id="V-ACME",
            legal_name="Acme Industrial Supplies Sdn. Bhd.",
            aliases=["ACME"],
            status="APPROVED",
            currency="MYR",
        )
    )
    session.add(
        PurchaseOrderRecord(
            id="PO-ACME-1001",
            vendor_id="V-ACME",
            currency="MYR",
            authorized_total=Decimal(5000),
            approved_consumed=Decimal(1250),
            status="OPEN",
        )
    )
    session.commit()
    return session


def document(session: Session, identifier: str = "document-1") -> DocumentRecord:
    item = DocumentRecord(
        id=identifier,
        original_filename="invoice.pdf",
        mime_type="application/pdf",
        sha256=identifier * 5,
        storage_path="/tmp/invoice.pdf",
        document_type=DocumentType.B2B_INVOICE.value,
    )
    session.add(item)
    session.commit()
    return item


def extraction(**overrides) -> ExtractedInvoice:
    values = {
        "vendor_raw_name": "Acme Industrial Supplies Sdn. Bhd.",
        "invoice_number": "ACME-001",
        "invoice_date": date(2026, 10, 1),
        "po_reference": "PO-ACME-1001",
        "currency": "MYR",
        "subtotal": Decimal(1000),
        "tax": Decimal(60),
        "grand_total": Decimal(1060),
        "tax_inclusion": TaxInclusion.EXCLUSIVE,
        "extraction_method": "ollama",
    }
    values.update(overrides)
    return ExtractedInvoice(**values)


def test_verified_b2b_invoice_is_approved() -> None:
    session = build_session()
    outcome = DecisionEngine(session).decide(document(session), extraction())
    assert outcome.outcome.value == "APPROVED"
    assert not outcome.reason_codes


def test_duplicate_vendor_invoice_is_blocked() -> None:
    session = build_session()
    prior = document(session, "prior")
    prior.extraction_json = {
        "normalized_vendor_id": "V-ACME",
        "invoice_number": "ACME-001",
    }
    session.commit()
    outcome = DecisionEngine(session).decide(document(session, "current"), extraction())
    assert outcome.outcome.value == "BLOCKED"
    assert "DUPLICATE_INVOICE" in outcome.reason_codes


def test_amount_over_remaining_po_balance_needs_review() -> None:
    session = build_session()
    outcome = DecisionEngine(session).decide(
        document(session),
        extraction(
            grand_total=Decimal("3750.01"),
            subtotal=Decimal("3500.01"),
            tax=Decimal(250),
        ),
    )
    assert outcome.outcome.value == "NEEDS_REVIEW"
    assert "AMOUNT_EXCEEDS_PO_BALANCE" in outcome.reason_codes


def test_inclusive_tax_is_not_double_counted() -> None:
    session = build_session()
    outcome = DecisionEngine(session).decide(
        document(session),
        extraction(
            tax_inclusion=TaxInclusion.INCLUSIVE,
            subtotal=Decimal(1200),
            tax=Decimal("67.92"),
            grand_total=Decimal(1200),
        ),
    )
    assert outcome.outcome.value == "APPROVED"
    assert "TOTAL_ARITHMETIC_MISMATCH" not in outcome.reason_codes


def test_retail_receipt_cannot_auto_approve() -> None:
    session = build_session()
    item = document(session)
    item.document_type = DocumentType.RETAIL_RECEIPT.value
    session.commit()
    outcome = DecisionEngine(session).decide(item, extraction())
    assert outcome.outcome.value == "NEEDS_REVIEW"
    assert "UNMATCHABLE_RETAIL_RECEIPT" in outcome.reason_codes
