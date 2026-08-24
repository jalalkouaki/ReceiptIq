from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import WarrantyItem, Receipt
from routes.middleware import jwt_required

warranty_bp = Blueprint("warranty_bp", __name__)


@warranty_bp.route("/api/warranties", methods=["GET"])
@jwt_required
def get_warranties():
    days_until_expiry = request.args.get("days_until_expiry", type=int)

    db = next(get_db_session())
    # Find warranties where associated receipt belongs to user or explicit warranty record
    query = db.query(WarrantyItem).join(Receipt, WarrantyItem.receipt_id == Receipt.id, isouter=True).filter(
        (Receipt.user_id == g.user.id) | (WarrantyItem.receipt_id == None)
    )

    items = query.all()
    results = []
    today = datetime.utcnow().date()

    for item in items:
        try:
            purchase_dt = datetime.strptime(item.purchase_date, "%Y-%m-%d").date()
            expiry_dt = purchase_dt + timedelta(days=item.warranty_months * 30)
            days_left = (expiry_dt - today).days
        except Exception:
            days_left = 365

        item_dict = item.to_dict()
        item_dict["days_remaining"] = max(0, days_left)
        item_dict["is_expired"] = days_left <= 0

        if days_until_expiry is None or days_left <= days_until_expiry:
            results.append(item_dict)

    return jsonify({"warranties": results}), 200


@warranty_bp.route("/api/warranties", methods=["POST"])
@jwt_required
def create_warranty():
    data = request.get_json() or {}
    item_name = data.get("item_name", "").strip()
    purchase_date = data.get("purchase_date", "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
    warranty_months = int(data.get("warranty_months", 12))
    notes = data.get("notes", "").strip()
    receipt_id = data.get("receipt_id")

    if not item_name:
        return jsonify({"error": "item_name is required"}), 400

    db = next(get_db_session())
    item = WarrantyItem(
        receipt_id=receipt_id,
        item_name=item_name,
        purchase_date=purchase_date,
        warranty_months=warranty_months,
        notes=notes
    )
    db.add(item)
    db.commit()
    return jsonify({"message": "Warranty created", "warranty": item.to_dict()}), 201


@warranty_bp.route("/api/warranties/<int:warranty_id>", methods=["DELETE"])
@jwt_required
def delete_warranty(warranty_id):
    db = next(get_db_session())
    item = db.query(WarrantyItem).filter_by(id=warranty_id).first()
    if not item:
        return jsonify({"error": "Warranty item not found"}), 404

    db.delete(item)
    db.commit()
    return jsonify({"message": "Warranty deleted"}), 200
