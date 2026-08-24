import io
from datetime import datetime
from flask import Blueprint, request, jsonify, g, send_file
from config import load_settings, save_settings
from logger import log_event
from routes.middleware import jwt_required, admin_required

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

generator_bp = Blueprint("generator_bp", __name__)


@generator_bp.route("/api/generator/config", methods=["GET"])
@jwt_required
def get_generator_config():
    """Retrieve generator store configuration and user edit permissions."""
    cfg = load_settings()
    store_name = cfg.get("STORE_NAME", "ReceiptIQ Store")
    is_admin = (g.user.role == "admin")
    return jsonify({
        "store_name": store_name,
        "role": g.user.role,
        "is_admin": is_admin
    }), 200


@generator_bp.route("/api/generator/store-name", methods=["POST"])
@jwt_required
@admin_required
def update_store_name():
    """Admin-only endpoint to update default store name."""
    data = request.get_json() or {}
    new_store_name = data.get("store_name", "").strip()
    if not new_store_name:
        return jsonify({"error": "Store name cannot be empty"}), 400

    updated = save_settings({"STORE_NAME": new_store_name})
    log_event("admin", f"Admin '{g.user.username}' updated store name to '{new_store_name}'", level="INFO", user=g.user.username)
    return jsonify({
        "message": "Store name updated successfully",
        "store_name": updated.get("STORE_NAME", new_store_name)
    }), 200


@generator_bp.route("/api/generator/pdf", methods=["POST"])
@jwt_required
def generate_receipt_pdf():
    """Generate and download a PDF receipt from itemized list."""
    if not REPORTLAB_AVAILABLE:
        return jsonify({"error": "ReportLab library not installed on server"}), 500

    data = request.get_json() or {}
    cfg = load_settings()
    
    # Store name from admin config or request (if admin overrides)
    default_store = cfg.get("STORE_NAME", "ReceiptIQ Store")
    store_name = data.get("store_name", "").strip() or default_store
    
    # If user is not admin, enforce global store name from settings
    if g.user.role != "admin":
        store_name = default_store

    receipt_number = data.get("receipt_number", "").strip() or f"REC-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    date_str = data.get("date", "").strip() or datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    payment_method = data.get("payment_method", "Cash").strip()
    notes = data.get("notes", "Thank you for your business!").strip()
    
    try:
        tax_rate = float(data.get("tax_rate", 0.0))
        if tax_rate < 0:
            tax_rate = 0.0
    except (ValueError, TypeError):
        tax_rate = 0.0

    raw_items = data.get("items", [])
    if not raw_items or not isinstance(raw_items, list):
        return jsonify({"error": "At least one receipt item is required"}), 400

    cleaned_items = []
    subtotal = 0.0
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip() or f"Item #{idx + 1}"
        try:
            price = float(item.get("price", 0.0))
            quantity = int(item.get("quantity", 1))
        except (ValueError, TypeError):
            continue

        if price < 0 or quantity <= 0:
            continue

        line_total = round(price * quantity, 2)
        subtotal += line_total
        cleaned_items.append({
            "name": name,
            "quantity": quantity,
            "price": price,
            "total": line_total
        })

    if not cleaned_items:
        return jsonify({"error": "No valid items provided with positive quantity and price"}), 400

    tax_amount = round(subtotal * (tax_rate / 100.0), 2)
    total_amount = round(subtotal + tax_amount, 2)

    # Build PDF using ReportLab
    pdf_buffer = io.BytesIO()
    # Thermal receipt dimension: 3.125 inches (225 pt) width, variable height
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=(240, 500 + len(cleaned_items) * 25),
        rightMargin=12,
        leftMargin=12,
        topMargin=15,
        bottomMargin=15
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=1, # Center
        textColor=colors.HexColor('#111827')
    )
    center_sub = ParagraphStyle(
        'CenterSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#4b5563')
    )
    left_bold = ParagraphStyle(
        'LeftBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#111827')
    )
    right_bold = ParagraphStyle(
        'RightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=2, # Right
        textColor=colors.HexColor('#111827')
    )
    item_name_style = ParagraphStyle(
        'ItemName',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1f2937')
    )

    story = []

    # Store Header
    story.append(Paragraph(store_name.upper(), title_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("OFFICIAL SALES RECEIPT", center_sub))
    story.append(Spacer(1, 6))

    # Metadata Table
    meta_data = [
        [Paragraph(f"<b>Receipt #:</b> {receipt_number}", item_name_style)],
        [Paragraph(f"<b>Date:</b> {date_str}", item_name_style)],
        [Paragraph(f"<b>Payment:</b> {payment_method}", item_name_style)],
    ]
    meta_table = Table(meta_data, colWidths=[216])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Divider
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#9ca3af'), spaceBefore=2, spaceAfter=6, dash=[2, 2]))

    # Items Table
    item_rows = [[
        Paragraph("<b>ITEM</b>", left_bold),
        Paragraph("<b>QTY</b>", center_sub),
        Paragraph("<b>PRICE</b>", center_sub),
        Paragraph("<b>TOTAL</b>", right_bold)
    ]]

    for it in cleaned_items:
        item_rows.append([
            Paragraph(it["name"][:18], item_name_style),
            Paragraph(str(it["quantity"]), center_sub),
            Paragraph(f"${it['price']:.2f}", center_sub),
            Paragraph(f"${it['total']:.2f}", right_bold)
        ])

    items_table = Table(item_rows, colWidths=[96, 25, 45, 50])
    items_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6))

    # Divider
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#9ca3af'), spaceBefore=2, spaceAfter=6, dash=[2, 2]))

    # Summary Totals Table
    totals_data = [
        [Paragraph("Subtotal:", item_name_style), Paragraph(f"${subtotal:.2f}", right_bold)],
        [Paragraph(f"Tax ({tax_rate:.1f}%):", item_name_style), Paragraph(f"${tax_amount:.2f}", right_bold)],
        [Paragraph("<b>TOTAL:</b>", title_style), Paragraph(f"<b>${total_amount:.2f}</b>", title_style)],
    ]
    totals_table = Table(totals_data, colWidths=[116, 100])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,1), (1,1), 1, colors.HexColor('#111827')),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 10))

    # Notes / Barcode simulation footer
    if notes:
        story.append(Paragraph(notes, center_sub))
        story.append(Spacer(1, 6))

    story.append(Paragraph("||||| ||||||| |||| |||||||| ||||||", ParagraphStyle('Barcode', parent=center_sub, fontName='Courier-Bold', fontSize=10, leading=11)))
    story.append(Paragraph(f"*{receipt_number}*", center_sub))

    doc.build(story)
    pdf_buffer.seek(0)

    log_event("generator", f"User '{g.user.username}' generated receipt PDF #{receipt_number} for ${total_amount:.2f}", level="INFO", user=g.user.username)
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"receipt_{receipt_number}.pdf"
    )
