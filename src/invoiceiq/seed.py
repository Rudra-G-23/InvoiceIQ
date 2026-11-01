from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoiceiq.models import PurchaseOrderRecord, VendorRecord

VENDORS = [
    (
        "V-ACME",
        "Acme Industrial Supplies Sdn. Bhd.",
        ["Acme Industrial", "ACME Supplies"],
        "MYR-ACME-01",
        "APPROVED",
    ),
    (
        "V-NOVA",
        "Nova Office Systems Sdn. Bhd.",
        ["Nova Office", "NOVA"],
        "MYR-NOVA-02",
        "APPROVED",
    ),
    (
        "V-VERDE",
        "Verde Facilities Services Sdn. Bhd.",
        ["Verde Facilities", "VERDE"],
        "MYR-VERDE-03",
        "APPROVED",
    ),
    (
        "V-INACTIVE",
        "Dormant Vendor Sdn. Bhd.",
        ["Dormant Vendor"],
        "MYR-DORMANT-99",
        "INACTIVE",
    ),
]
POS = [
    ("PO-ACME-1001", "V-ACME", "5000.00", "1250.00"),
    ("PO-NOVA-2001", "V-NOVA", "3200.00", "0.00"),
    ("PO-VERDE-3001", "V-VERDE", "1800.00", "0.00"),
]


def seed_reference_data(session: Session) -> None:
    if session.scalar(select(VendorRecord.id).limit(1)):
        return
    for vendor_id, name, aliases, tax_id, status in VENDORS:
        session.add(
            VendorRecord(
                id=vendor_id,
                legal_name=name,
                aliases=aliases,
                tax_id=tax_id,
                status=status,
                currency="MYR",
            )
        )
    session.commit()
    for po_id, vendor_id, total, consumed in POS:
        session.add(
            PurchaseOrderRecord(
                id=po_id,
                vendor_id=vendor_id,
                currency="MYR",
                authorized_total=Decimal(total),
                approved_consumed=Decimal(consumed),
                status="OPEN",
            )
        )
    session.commit()
