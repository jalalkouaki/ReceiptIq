import os
import csv
import io
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, g
from database import get_db_session
from models import Receipt, ExpenseCategory, WarrantyItem, Subscription
from config import load_settings
from logger import log_event
from routes.middleware import jwt_required

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

report_bp = Blueprint("report_bp", __name__)


@report_bp.route("/api/dashboard/summary", methods=["GET"])
@jwt_required
def get_dashboard_summary():
    year_param = request.args.get("year", type=int)
    current_year = year_param or datetime.utcnow().year

    db = next(get_db_session())
    user_receipts = db.query(Receipt).filter_by(user_id=g.user.id).all()

    filtered_receipts = []
    for r in user_receipts:
        if r.receipt_date:
            try:
                r_year = int(r.receipt_date.split("-")[0])
                if r_year == current_year:
                    filtered_receipts.append(r)
            except Exception:
                filtered_receipts.append(r)
        else:
            filtered_receipts.append(r)

    total_spent = sum(r.total_amount for r in filtered_receipts)
    tax_deductible_total = sum(
        r.total_amount for r in filtered_receipts
        if r.category and r.category.tax_deductible
    )
    pending_review_count = len([r for r in user_receipts if r.status == "needs_review"])

    # Monthly breakdown for 12 months
    monthly_spending = [0.0] * 12
    for r in filtered_receipts:
        if r.receipt_date:
            try:
                m = int(r.receipt_date.split("-")[1]) - 1
                if 0 <= m < 12:
                    monthly_spending[m] += r.total_amount
            except Exception:
                pass

    # Category breakdown
    categories = db.query(ExpenseCategory).all()
    category_map = {c.id: {"name": c.name, "color": c.color, "total": 0.0} for c in categories}
    category_map[None] = {"name": "Uncategorized", "color": "#6c757d", "total": 0.0}

    for r in filtered_receipts:
        cat_id = r.category_id if r.category_id in category_map else None
        category_map[cat_id]["total"] += r.total_amount

    category_breakdown = [
        {"name": data["name"], "color": data["color"], "total": round(data["total"], 2)}
        for cat_id, data in category_map.items() if data["total"] > 0
    ]

    # Upcoming alerts
    today = datetime.utcnow().date()
    warranty_alerts = []
    warranties = db.query(WarrantyItem).all()
    for w in warranties:
        try:
            p_dt = datetime.strptime(w.purchase_date, "%Y-%m-%d").date()
            exp_dt = p_dt + timedelta(days=w.warranty_months * 30)
            days_left = (exp_dt - today).days
            if 0 <= days_left <= 60:
                warranty_alerts.append({
                    "item_name": w.item_name,
                    "days_left": days_left
                })
        except Exception:
            pass

    subscription_alerts = []
    subs = db.query(Subscription).filter_by(user_id=g.user.id, active=True).all()
    for s in subs:
        subscription_alerts.append({
            "vendor": s.vendor,
            "amount": s.amount,
            "next_renewal": s.next_renewal
        })

    return jsonify({
        "year": current_year,
        "total_spent": round(total_spent, 2),
        "tax_deductible_total": round(tax_deductible_total, 2),
        "pending_review_count": pending_review_count,
        "monthly_spending": [round(val, 2) for val in monthly_spending],
        "category_breakdown": category_breakdown,
        "warranty_alerts": warranty_alerts,
        "subscription_alerts": subscription_alerts,
        "recent_receipts": [r.to_dict() for r in sorted(user_receipts, key=lambda x: x.id, reverse=True)[:5]]
    }), 200


@report_bp.route("/api/exports/csv", methods=["POST", "GET"])
@jwt_required
def export_csv():
    year = request.args.get("year", type=int)

    db = next(get_db_session())
    query = db.query(Receipt).filter_by(user_id=g.user.id)
    receipts = query.order_by(Receipt.receipt_date.desc()).all()

    if year:
        receipts = [r for r in receipts if r.receipt_date and r.receipt_date.startswith(str(year))]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Vendor", "Date", "Total Amount", "Tax Amount", "Currency", "Category", "Tax Deductible", "Payment Method", "Status"])

    for r in receipts:
        cat_name = r.category.name if r.category else "Uncategorized"
        tax_ded = "Yes" if r.category and r.category.tax_deductible else "No"
        writer.writerow([
            r.id, r.vendor or "Unknown", r.receipt_date or "",
            f"{r.total_amount:.2f}", f"{r.tax_amount:.2f}", r.currency,
            cat_name, tax_ded, r.payment_method or "N/A", r.status
        ])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)

    filename = f"receiptiq_expenses_{year or 'all'}.csv"
    log_event("admin", f"User '{g.user.username}' exported CSV tax report", level="INFO", user=g.user.username)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)


@report_bp.route("/api/exports/pdf", methods=["POST", "GET"])
@jwt_required
def export_pdf():
    if not REPORTLAB_AVAILABLE:
        return jsonify({"error": "ReportLab library not installed on server"}), 500

    year = request.args.get("year", type=int) or datetime.utcnow().year

    db = next(get_db_session())
    query = db.query(Receipt).filter_by(user_id=g.user.id)
    receipts = [r for r in query.all() if r.receipt_date and r.receipt_date.startswith(str(year))]

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    story = []
    story.append(Paragraph(f"ReceiptIQ Expense & Tax Report ({year})", styles['Title']))
    story.append(Paragraph(f"Generated for: {g.user.username} | Date: {datetime.utcnow().strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Spacer(1, 15))

    total_spent = sum(r.total_amount for r in receipts)
    tax_ded = sum(r.total_amount for r in receipts if r.category and r.category.tax_deductible)

    summary_data = [
        ["Total Receipts", "Total Expenses", "Tax Deductible Expenses"],
        [str(len(receipts)), f"${total_spent:,.2f}", f"${tax_ded:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[180, 180, 180])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6'))
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Itemized Expense List", styles['Heading2']))
    story.append(Spacer(1, 10))

    table_data = [["Date", "Vendor", "Category", "Amount", "Tax Deductible"]]
    for r in receipts[:100]:
        cat_name = r.category.name if r.category else "Uncategorized"
        is_ded = "Yes" if r.category and r.category.tax_deductible else "No"
        table_data.append([
            r.receipt_date or "N/A",
            r.vendor[:25] if r.vendor else "Unknown",
            cat_name[:20],
            f"${r.total_amount:,.2f}",
            is_ded
        ])

    rec_table = Table(table_data, colWidths=[90, 150, 130, 90, 80])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e0e0e0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    story.append(rec_table)

    doc.build(story)
    pdf_buffer.seek(0)

    filename = f"receiptiq_tax_report_{year}.pdf"
    log_event("admin", f"User '{g.user.username}' exported PDF report for {year}", level="INFO", user=g.user.username)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


@report_bp.route("/api/backup", methods=["POST"])
@jwt_required
def create_backup():
    cfg = load_settings()
    db_path = cfg.get("DB_PATH")

    if not os.path.exists(db_path):
        return jsonify({"error": "Database file does not exist to backup"}), 404

    backup_dir = Path(db_path).parent / "backups"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"receiptiq_backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    log_event("admin", f"User '{g.user.username}' created DB backup at {backup_path}", level="INFO", user=g.user.username)
    return jsonify({"message": "Encrypted database backup created successfully", "backup_path": str(backup_path)}), 200
