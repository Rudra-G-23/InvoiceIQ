"""Generate non-sensitive synthetic B2B invoice fixtures for local demos."""

import json
from pathlib import Path

import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

FIXTURES = [
    {
        "file": "01_clean_acme.pdf",
        "vendor": "Acme Industrial Supplies Sdn. Bhd.",
        "number": "ACME-2026-001",
        "date": "2026-10-01",
        "po": "PO-ACME-1001",
        "subtotal": "1000.00",
        "tax": "60.00",
        "total": "1060.00",
        "expected": "APPROVED",
        "layout": 0,
    },
    {
        "file": "02_nova_alternative.pdf",
        "vendor": "Nova Office Systems Sdn. Bhd.",
        "number": "NOVA-2026-114",
        "date": "2026-10-03",
        "po": "PO-NOVA-2001",
        "subtotal": "800.00",
        "tax": "48.00",
        "total": "848.00",
        "expected": "APPROVED",
        "layout": 1,
    },
    {
        "file": "03_acme_duplicate_name.pdf",
        "vendor": "Acme Industrial Supplies Sdn. Bhd.",
        "number": "ACME-2026-001",
        "date": "2026-10-01",
        "po": "PO-ACME-1001",
        "subtotal": "1000.00",
        "tax": "60.00",
        "total": "1060.00",
        "expected": "BLOCKED",
        "layout": 2,
    },
    {
        "file": "04_acme_over_balance.pdf",
        "vendor": "Acme Industrial Supplies Sdn. Bhd.",
        "number": "ACME-2026-099",
        "date": "2026-10-04",
        "po": "PO-ACME-1001",
        "subtotal": "4000.00",
        "tax": "240.00",
        "total": "4240.00",
        "expected": "NEEDS_REVIEW",
        "layout": 0,
    },
    {
        "file": "05_acme_partial.pdf",
        "vendor": "Acme Industrial Supplies Sdn. Bhd.",
        "number": "ACME-2026-002",
        "date": "2026-10-05",
        "po": "PO-ACME-1001",
        "subtotal": "1000.00",
        "tax": "60.00",
        "total": "1060.00",
        "expected": "APPROVED",
        "layout": 1,
    },
    {
        "file": "06_missing_po.pdf",
        "vendor": "Verde Facilities Services Sdn. Bhd.",
        "number": "VERDE-2026-007",
        "date": "2026-10-06",
        "po": None,
        "subtotal": "500.00",
        "tax": "30.00",
        "total": "530.00",
        "expected": "NEEDS_REVIEW",
        "layout": 2,
    },
    {
        "file": "07_unknown_vendor.pdf",
        "vendor": "Beacon Unlisted Trading",
        "number": "BEACON-55",
        "date": "2026-10-07",
        "po": "PO-VERDE-3001",
        "subtotal": "300.00",
        "tax": "18.00",
        "total": "318.00",
        "expected": "NEEDS_REVIEW",
        "layout": 0,
    },
    {
        "file": "08_inclusive_discount_rounding.pdf",
        "vendor": "Verde Facilities Services Sdn. Bhd.",
        "number": "VERDE-2026-008",
        "date": "2026-10-08",
        "po": "PO-VERDE-3001",
        "subtotal": "1200.00",
        "tax": "67.92",
        "total": "1187.92",
        "expected": "APPROVED",
        "layout": 1,
        "inclusive": True,
        "discount": "80.00",
    },
]


def draw_invoice(path: Path, data: dict) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    if data["layout"] == 0:
        pdf.setFillColor(colors.HexColor("#17324d"))
        pdf.rect(0, height - 42 * mm, width, 42 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawString(18 * mm, height - 22 * mm, "ACCOUNTS PAYABLE INVOICE")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            18 * mm,
            height - 31 * mm,
            "Synthetic demonstration data - not a real invoice",
        )
        y = height - 58 * mm
    elif data["layout"] == 1:
        pdf.setStrokeColor(colors.HexColor("#18794e"))
        pdf.setLineWidth(3)
        pdf.line(18 * mm, height - 20 * mm, width - 18 * mm, height - 20 * mm)
        pdf.setFillColor(colors.HexColor("#18794e"))
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawRightString(width - 18 * mm, height - 35 * mm, "INVOICE")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(18 * mm, height - 34 * mm, "Synthetic demonstration data")
        y = height - 53 * mm
    else:
        pdf.setFillColor(colors.HexColor("#f5f1e8"))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#6b3d24"))
        pdf.setFont("Courier-Bold", 17)
        pdf.drawString(18 * mm, height - 22 * mm, "TAX INVOICE")
        pdf.setFont("Courier", 8)
        pdf.drawString(18 * mm, height - 30 * mm, "SYNTHETIC DEMONSTRATION DATA")
        y = height - 48 * mm
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(18 * mm, y, f"Vendor: {data['vendor']}")
    pdf.setFont("Helvetica", 10)
    y -= 9 * mm
    for label, value in (
        ("Invoice No", data["number"]),
        ("Invoice Date", data["date"]),
        ("Purchase Order", data["po"] or "Not supplied"),
        ("Currency", "MYR"),
    ):
        pdf.drawString(18 * mm, y, f"{label}: {value}")
        y -= 7 * mm
    y -= 4 * mm
    pdf.setFillColor(colors.HexColor("#e6edf3"))
    pdf.rect(18 * mm, y - 7 * mm, width - 36 * mm, 9 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(21 * mm, y - 1 * mm, "Description")
    pdf.drawRightString(width - 21 * mm, y - 1 * mm, "Amount (MYR)")
    y -= 16 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(21 * mm, y, "Professional goods and services")
    pdf.drawRightString(width - 21 * mm, y, data["subtotal"])
    y -= 14 * mm
    pdf.drawRightString(width - 21 * mm, y, f"Subtotal: MYR {data['subtotal']}")
    if data.get("discount"):
        y -= 7 * mm
        pdf.drawRightString(width - 21 * mm, y, f"Discount: MYR {data['discount']}")
    y -= 7 * mm
    tax_label = "Tax included in total" if data.get("inclusive") else "Tax"
    pdf.drawRightString(width - 21 * mm, y, f"{tax_label}: MYR {data['tax']}")
    y -= 11 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(width - 21 * mm, y, f"Grand Total: MYR {data['total']}")
    if data.get("inclusive"):
        y -= 8 * mm
        pdf.setFont("Helvetica-Oblique", 8)
        pdf.drawRightString(
            width - 21 * mm, y, "Tax is included in the stated grand total."
        )
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawString(
        18 * mm,
        16 * mm,
        "Synthetic demonstration data for InvoiceIQ local workflow testing.",
    )
    pdf.save()


def render_vendor_matched_preview(pdf_path: Path, image_path: Path) -> None:
    with fitz.open(pdf_path) as document:
        pixmap = document[0].get_pixmap(dpi=140, alpha=False)
        pixmap.save(image_path)


def main() -> None:
    output_dir = Path("data/generated/invoices")
    preview_dir = output_dir.parent / "vendor-matched"
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    for fixture in FIXTURES:
        pdf_path = output_dir / fixture["file"]
        draw_invoice(pdf_path, fixture)
        if fixture["expected"] == "APPROVED":
            render_vendor_matched_preview(
                pdf_path, preview_dir / f"{pdf_path.stem}.png"
            )
    expected = [
        {
            key: item.get(key)
            for key in ("file", "vendor", "number", "date", "po", "total", "expected")
        }
        for item in FIXTURES
    ]
    (output_dir.parent / "expected_results.json").write_text(
        json.dumps(expected, indent=2) + "\n", encoding="utf-8"
    )
    (preview_dir / "README.txt").write_text(
        "Synthetic PNG renderings of fixture invoices with explicit approved vendor and PO matches.\n",
        encoding="utf-8",
    )
    print(
        f"Generated {len(FIXTURES)} synthetic invoices in {output_dir} and vendor-matched previews in {preview_dir}"
    )


if __name__ == "__main__":
    main()
