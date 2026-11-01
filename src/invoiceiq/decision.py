from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoiceiq.models import DocumentRecord, PurchaseOrderRecord, VendorRecord
from invoiceiq.schemas import (
    CheckStatus,
    DecisionOutcome,
    DecisionResult,
    DocumentType,
    ExtractedInvoice,
    RuleCheck,
    TaxInclusion,
)


def money(value: Decimal | None) -> str | None:
    return (
        str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if value is not None
        else None
    )


def normalized(value: str | None) -> str:
    return "".join(char for char in (value or "").casefold() if char.isalnum())


class DecisionEngine:
    def __init__(self, session: Session):
        self.session = session

    def _check(
        self, code: str, status: CheckStatus, explanation: str, **facts: object
    ) -> RuleCheck:
        return RuleCheck(code=code, status=status, explanation=explanation, facts=facts)

    def _find_vendor(self, extraction: ExtractedInvoice) -> VendorRecord | None:
        needle = normalized(
            extraction.vendor_raw_name or extraction.vendor_display_name
        )
        if not needle:
            return None
        for vendor in self.session.scalars(select(VendorRecord)).all():
            names = [vendor.legal_name, *vendor.aliases]
            if needle in {normalized(name) for name in names}:
                return vendor
        return None

    def decide(
        self, document: DocumentRecord, extraction: ExtractedInvoice
    ) -> DecisionResult:
        checks: list[RuleCheck] = []
        reasons: list[str] = []

        if document.document_type == DocumentType.B2B_INVOICE.value:
            checks.append(
                self._check(
                    "DOCUMENT_TYPE_COMPATIBLE",
                    CheckStatus.PASS,
                    "The document is a B2B invoice.",
                )
            )
        elif document.document_type == DocumentType.RETAIL_RECEIPT.value:
            checks.append(
                self._check(
                    "UNMATCHABLE_RETAIL_RECEIPT",
                    CheckStatus.FAIL,
                    "Retail receipts are not automatically matched to purchase orders.",
                )
            )
            reasons.append("UNMATCHABLE_RETAIL_RECEIPT")
        else:
            checks.append(
                self._check(
                    "DOCUMENT_TYPE_COMPATIBLE",
                    CheckStatus.UNKNOWN,
                    "The document type is not suitable for automatic PO approval.",
                    document_type=document.document_type,
                )
            )
            reasons.append("DOCUMENT_TYPE_UNCERTAIN")

        vendor = self._find_vendor(extraction)
        if vendor is None:
            checks.append(
                self._check(
                    "VENDOR_MATCH",
                    CheckStatus.FAIL,
                    "No approved vendor identity could be confirmed.",
                    vendor=extraction.vendor_raw_name,
                )
            )
            reasons.append("VENDOR_NOT_APPROVED")
        elif vendor.status != "APPROVED":
            checks.append(
                self._check(
                    "VENDOR_NOT_APPROVED",
                    CheckStatus.FAIL,
                    "The matched vendor is inactive.",
                    vendor_id=vendor.id,
                )
            )
            reasons.append("VENDOR_NOT_APPROVED")
        else:
            checks.append(
                self._check(
                    "VENDOR_MATCH",
                    CheckStatus.PASS,
                    "The vendor exactly matches an approved ledger vendor.",
                    vendor_id=vendor.id,
                )
            )
            extraction.normalized_vendor_id = vendor.id

        missing = [
            name
            for name, value in (
                ("invoice_number", extraction.invoice_number),
                ("invoice_date", extraction.invoice_date),
                ("grand_total", extraction.grand_total),
                ("currency", extraction.currency),
            )
            if value is None
        ]
        if missing:
            checks.append(
                self._check(
                    "CRITICAL_FIELD_MISSING",
                    CheckStatus.FAIL,
                    "Critical approval fields are missing.",
                    missing=missing,
                )
            )
            reasons.append("CRITICAL_FIELD_MISSING")
        else:
            checks.append(
                self._check(
                    "CRITICAL_FIELDS",
                    CheckStatus.PASS,
                    "Invoice number, date, amount, and currency are available.",
                )
            )

        duplicate = self.session.scalar(
            select(DocumentRecord).where(
                DocumentRecord.id != document.id,
                DocumentRecord.sha256 == document.sha256,
            )
        )
        if duplicate is None and vendor and extraction.invoice_number:
            candidates = self.session.scalars(
                select(DocumentRecord).where(DocumentRecord.id != document.id)
            ).all()
            duplicate = next(
                (
                    item
                    for item in candidates
                    if item.extraction_json
                    and item.extraction_json.get("normalized_vendor_id") == vendor.id
                    and item.extraction_json.get("invoice_number")
                    == extraction.invoice_number
                ),
                None,
            )
        if duplicate:
            checks.append(
                self._check(
                    "DUPLICATE_INVOICE",
                    CheckStatus.FAIL,
                    "This file or vendor invoice number was processed previously.",
                    existing_document_id=duplicate.id,
                )
            )
            reasons.append("DUPLICATE_INVOICE")
        else:
            checks.append(
                self._check(
                    "DUPLICATE_INVOICE",
                    CheckStatus.PASS,
                    "No matching file hash or vendor invoice number was found.",
                )
            )

        po = None
        if not extraction.po_reference:
            checks.append(
                self._check(
                    "PO_REFERENCE_MISSING",
                    CheckStatus.FAIL,
                    "No explicit purchase order reference was extracted.",
                )
            )
            reasons.append("PO_REFERENCE_MISSING")
        else:
            po = self.session.get(PurchaseOrderRecord, extraction.po_reference)
            if po is None:
                checks.append(
                    self._check(
                        "PO_NOT_FOUND",
                        CheckStatus.FAIL,
                        "The referenced purchase order is not in the ledger.",
                        po_reference=extraction.po_reference,
                    )
                )
                reasons.append("PO_NOT_FOUND")
            elif po.status != "OPEN":
                checks.append(
                    self._check(
                        "PO_NOT_OPEN",
                        CheckStatus.FAIL,
                        "The referenced purchase order is not open.",
                        po_reference=po.id,
                    )
                )
                reasons.append("PO_NOT_OPEN")
            elif vendor and po.vendor_id != vendor.id:
                checks.append(
                    self._check(
                        "VENDOR_PO_MISMATCH",
                        CheckStatus.FAIL,
                        "The purchase order belongs to a different vendor.",
                        po_vendor_id=po.vendor_id,
                        vendor_id=vendor.id,
                    )
                )
                reasons.append("VENDOR_PO_MISMATCH")
            elif extraction.currency and po.currency != extraction.currency:
                checks.append(
                    self._check(
                        "CURRENCY_MISMATCH",
                        CheckStatus.FAIL,
                        "The invoice currency differs from the purchase order.",
                        invoice_currency=extraction.currency,
                        po_currency=po.currency,
                    )
                )
                reasons.append("CURRENCY_MISMATCH")
            else:
                checks.append(
                    self._check(
                        "PO_MATCH",
                        CheckStatus.PASS,
                        "The explicit PO is open and matches the vendor and currency.",
                        po_reference=po.id,
                    )
                )

        if (
            po
            and extraction.grand_total is not None
            and not any(
                reason in reasons
                for reason in ("VENDOR_PO_MISMATCH", "CURRENCY_MISMATCH", "PO_NOT_OPEN")
            )
        ):
            available = Decimal(str(po.authorized_total)) - Decimal(
                str(po.approved_consumed)
            )
            if extraction.grand_total > available:
                checks.append(
                    self._check(
                        "AMOUNT_EXCEEDS_PO_BALANCE",
                        CheckStatus.FAIL,
                        "The invoice exceeds the PO's remaining approved balance.",
                        available_balance=money(available),
                        invoice_total=money(extraction.grand_total),
                    )
                )
                reasons.append("AMOUNT_EXCEEDS_PO_BALANCE")
            else:
                checks.append(
                    self._check(
                        "PO_BALANCE",
                        CheckStatus.PASS,
                        "The invoice is within the remaining approved balance.",
                        available_balance=money(available),
                        invoice_total=money(extraction.grand_total),
                    )
                )

        if extraction.grand_total is None:
            checks.append(
                self._check(
                    "TOTAL_ARITHMETIC",
                    CheckStatus.UNKNOWN,
                    "No total is available to validate.",
                )
            )
        elif extraction.tax_inclusion == TaxInclusion.INCLUSIVE:
            checks.append(
                self._check(
                    "TOTAL_ARITHMETIC",
                    CheckStatus.PASS,
                    "The document declares tax-inclusive pricing; tax is not added a second time.",
                )
            )
        elif extraction.subtotal is not None and extraction.tax is not None:
            expected = (
                extraction.subtotal
                - (extraction.discount or Decimal(0))
                + extraction.tax
                + (extraction.rounding or Decimal(0))
            )
            if abs(expected - extraction.grand_total) > Decimal("0.01"):
                checks.append(
                    self._check(
                        "TOTAL_ARITHMETIC_MISMATCH",
                        CheckStatus.FAIL,
                        "Subtotal, tax, discount, and rounding do not reconcile to the total.",
                        expected=money(expected),
                        actual=money(extraction.grand_total),
                    )
                )
                reasons.append("TOTAL_ARITHMETIC_MISMATCH")
            else:
                checks.append(
                    self._check(
                        "TOTAL_ARITHMETIC",
                        CheckStatus.PASS,
                        "Available financial fields reconcile to the total.",
                        expected=money(expected),
                    )
                )
        else:
            checks.append(
                self._check(
                    "TOTAL_ARITHMETIC",
                    CheckStatus.UNKNOWN,
                    "Not enough tax-basis detail is available to prove arithmetic.",
                )
            )
            reasons.append("LOW_EXTRACTION_CONFIDENCE")

        if extraction.extraction_method in {
            "ai_unavailable",
            "ocr_unavailable",
            "rule_only",
        }:
            checks.append(
                self._check(
                    "AI_UNAVAILABLE",
                    CheckStatus.UNKNOWN,
                    "The optional extraction dependency was unavailable; this run cannot auto-approve.",
                    method=extraction.extraction_method,
                )
            )
            reasons.append("AI_UNAVAILABLE")

        if "DUPLICATE_INVOICE" in reasons:
            outcome = DecisionOutcome.BLOCKED
            explanation = "Blocked because a confirmed duplicate was detected. No payment action was initiated."
        elif reasons:
            outcome = DecisionOutcome.NEEDS_REVIEW
            explanation = "Needs human review because one or more approval checks are missing, uncertain, or failed."
        else:
            outcome = DecisionOutcome.APPROVED
            explanation = "Approved by the local demo AP policy after deterministic vendor, PO, balance, and arithmetic checks. No payment was initiated."
        return DecisionResult(
            outcome=outcome,
            reason_codes=list(dict.fromkeys(reasons)),
            explanation=explanation,
            suggested_po=po.id if po else None,
            checks=checks,
        )
