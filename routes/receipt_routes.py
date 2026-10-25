import os
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import Receipt, ExpenseCategory, WarrantyItem, Subscription, PriceHistory
from config import load_settings
from ocr_engine import process_receipt_file
from logger import log_event
from notifier import send_notification
from routes.middleware import jwt_required

receipt_bp = Blueprint("receipt_bp", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@receipt_bp.route("/api/receipts/upload", methods=["POST"])
@jwt_required
def upload_receipt():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Supported formats: PNG, JPG, JPEG, WEBP, PDF"}), 400

    cfg = load_settings()
    storage_dir = Path(cfg.get("STORAGE_PATH"))
    os.makedirs(storage_dir, exist_ok=True)

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"{timestamp}_{filename}"
    saved_path = storage_dir / saved_filename
    file.save(saved_path)

    log_event("upload", f"User '{g.user.username}' uploaded {saved_filename}", level="INFO", user=g.user.username)

    # Run OCR processing
    ocr_result = process_receipt_file(str(saved_path), ocr_lang=cfg.get("OCR_LANGUAGE", "eng"))

    db = next(get_db_session())
    category = db.query(ExpenseCategory).filter_by(slug=ocr_result["category_slug"]).first()
    if not category:
        category = db.query(ExpenseCategory).filter_by(slug="other").first()

    receipt = Receipt(
        user_id=g.user.id,
        file_path=str(saved_path),
        vendor=ocr_result["vendor"],
        receipt_date=ocr_result["receipt_date"],
        total_amount=ocr_result["total_amount"],
        tax_amount=ocr_result["tax_amount"],
        currency=ocr_result["currency"],
        payment_method=ocr_result["payment_method"],
        category_id=category.id if category else None,
        raw_ocr_text=ocr_result["raw_ocr_text"],
        confidence=ocr_result["confidence"],
        status=ocr_result["status"]
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Record price history
    if receipt.vendor and receipt.total_amount > 0:
        price_rec = PriceHistory(
            user_id=g.user.id,
            vendor=receipt.vendor,
            item_name=f"Receipt #{receipt.id} ({category.name if category else 'Expense'})",
            price=receipt.total_amount,
            currency=receipt.currency,
            date=receipt.receipt_date or datetime.utcnow().strftime("%Y-%m-%d")
        )
        db.add(price_rec)

    # Suggest warranty item for electronics
    warranty_suggested = False
    if ocr_result["is_electronics"]:
        warranty_item = WarrantyItem(
            receipt_id=receipt.id,
            item_name=f"{receipt.vendor} Equipment",
            purchase_date=receipt.receipt_date or datetime.utcnow().strftime("%Y-%m-%d"),
            warranty_months=12,
            notes="Auto-suggested for electronics purchase"
        )
        db.add(warranty_item)
        warranty_suggested = True

    # Detect recurring subscriptions
    subscription_detected = False
    if receipt.vendor and receipt.total_amount > 0:
        existing_receipts = db.query(Receipt).filter(
            Receipt.user_id == g.user.id,
            Receipt.vendor.ilike(f"%{receipt.vendor}%"),
            Receipt.id != receipt.id
        ).all()

        if len(existing_receipts) >= 1:
            existing_sub = db.query(Subscription).filter(
                Subscription.user_id == g.user.id,
                Subscription.vendor.ilike(f"%{receipt.vendor}%")
            ).first()
            if not existing_sub:
                new_sub = Subscription(
                    user_id=g.user.id,
                    vendor=receipt.vendor,
                    amount=receipt.total_amount,
                    currency=receipt.currency,
                    frequency="monthly",
                    next_renewal=datetime.utcnow().strftime("%Y-%m-%d"),
                    active=True
                )
                db.add(new_sub)
                subscription_detected = True

    db.commit()

    send_notification("Receipt Uploaded", f"Processed {receipt.vendor} (${receipt.total_amount:.2f})")

    return jsonify({
        "message": "Receipt processed successfully",
        "receipt": receipt.to_dict(),
        "warranty_suggested": warranty_suggested,
        "subscription_detected": subscription_detected
    }), 201


@receipt_bp.route("/api/receipts", methods=["GET"])
@jwt_required
def get_receipts():
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", type=int)
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)

    db = next(get_db_session())
    query = db.query(Receipt).filter_by(user_id=g.user.id)

    if search:
        query = query.filter((Receipt.vendor.ilike(f"%{search}%")) | (Receipt.raw_ocr_text.ilike(f"%{search}%")))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if start_date:
        query = query.filter(Receipt.receipt_date >= start_date)
    if end_date:
        query = query.filter(Receipt.receipt_date <= end_date)

    total_count = query.count()
    receipts = query.order_by(Receipt.id.desc()).offset((page - 1) * limit).limit(limit).all()

    return jsonify({
        "receipts": [r.to_dict() for r in receipts],
        "total": total_count,
        "page": page,
        "limit": limit
    }), 200


@receipt_bp.route("/api/receipts/<int:receipt_id>", methods=["GET"])
@jwt_required
def get_receipt(receipt_id):
    db = next(get_db_session())
    receipt = db.query(Receipt).filter_by(id=receipt_id, user_id=g.user.id).first()
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404
    return jsonify({"receipt": receipt.to_dict()}), 200


@receipt_bp.route("/api/receipts/<int:receipt_id>", methods=["PATCH"])
@jwt_required
def update_receipt(receipt_id):
    db = next(get_db_session())
    receipt = db.query(Receipt).filter_by(id=receipt_id, user_id=g.user.id).first()
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404

    data = request.get_json() or {}
    if "vendor" in data:
        receipt.vendor = data["vendor"]
    if "receipt_date" in data:
        receipt.receipt_date = data["receipt_date"]
    if "total_amount" in data:
        receipt.total_amount = float(data["total_amount"])
    if "tax_amount" in data:
        receipt.tax_amount = float(data["tax_amount"])
    if "category_id" in data:
        receipt.category_id = int(data["category_id"])
    if "status" in data:
        receipt.status = data["status"]

    db.commit()
    log_event("upload", f"User '{g.user.username}' updated receipt #{receipt.id}", level="INFO", user=g.user.username)
    return jsonify({"message": "Receipt updated", "receipt": receipt.to_dict()}), 200


@receipt_bp.route("/api/receipts/<int:receipt_id>", methods=["DELETE"])
@jwt_required
def delete_receipt(receipt_id):
    db = next(get_db_session())
    receipt = db.query(Receipt).filter_by(id=receipt_id, user_id=g.user.id).first()
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404

    # Remove physical file if exists
    if receipt.file_path and os.path.exists(receipt.file_path):
        try:
            os.remove(receipt.file_path)
        except Exception:
            pass

    db.delete(receipt)
    db.commit()
    log_event("upload", f"User '{g.user.username}' deleted receipt #{receipt_id}", level="INFO", user=g.user.username)
    return jsonify({"message": "Receipt deleted"}), 200


@receipt_bp.route("/api/receipts/<int:receipt_id>/categorize", methods=["POST"])
@jwt_required
def categorize_receipt(receipt_id):
    data = request.get_json() or {}
    category_id = data.get("category_id")
    if not category_id:
        return jsonify({"error": "category_id is required"}), 400

    db = next(get_db_session())
    receipt = db.query(Receipt).filter_by(id=receipt_id, user_id=g.user.id).first()
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404

    receipt.category_id = int(category_id)
    receipt.status = "completed"
    db.commit()
    return jsonify({"message": "Category updated", "receipt": receipt.to_dict()}), 200
