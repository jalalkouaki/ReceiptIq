from datetime import datetime
from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import Subscription
from routes.middleware import jwt_required

subscription_bp = Blueprint("subscription_bp", __name__)


@subscription_bp.route("/api/subscriptions", methods=["GET"])
@jwt_required
def get_subscriptions():
    db = next(get_db_session())
    subs = db.query(Subscription).filter_by(user_id=g.user.id).all()
    return jsonify({"subscriptions": [s.to_dict() for s in subs]}), 200


@subscription_bp.route("/api/subscriptions", methods=["POST"])
@jwt_required
def create_subscription():
    data = request.get_json() or {}
    vendor = data.get("vendor", "").strip()
    amount = float(data.get("amount", 0.0))
    currency = data.get("currency", "USD").strip()
    frequency = data.get("frequency", "monthly").strip()
    next_renewal = data.get("next_renewal", "").strip() or datetime.utcnow().strftime("%Y-%m-%d")

    if not vendor or amount <= 0:
        return jsonify({"error": "Vendor and valid positive amount are required"}), 400

    db = next(get_db_session())
    sub = Subscription(
        user_id=g.user.id,
        vendor=vendor,
        amount=amount,
        currency=currency,
        frequency=frequency,
        next_renewal=next_renewal,
        active=True
    )
    db.add(sub)
    db.commit()
    return jsonify({"message": "Subscription created", "subscription": sub.to_dict()}), 201


@subscription_bp.route("/api/subscriptions/<int:sub_id>", methods=["PATCH"])
@jwt_required
def update_subscription(sub_id):
    db = next(get_db_session())
    sub = db.query(Subscription).filter_by(id=sub_id, user_id=g.user.id).first()
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404

    data = request.get_json() or {}
    if "vendor" in data:
        sub.vendor = data["vendor"]
    if "amount" in data:
        sub.amount = float(data["amount"])
    if "frequency" in data:
        sub.frequency = data["frequency"]
    if "next_renewal" in data:
        sub.next_renewal = data["next_renewal"]
    if "active" in data:
        sub.active = bool(data["active"])

    db.commit()
    return jsonify({"message": "Subscription updated", "subscription": sub.to_dict()}), 200


@subscription_bp.route("/api/subscriptions/<int:sub_id>", methods=["DELETE"])
@jwt_required
def delete_subscription(sub_id):
    db = next(get_db_session())
    sub = db.query(Subscription).filter_by(id=sub_id, user_id=g.user.id).first()
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404

    db.delete(sub)
    db.commit()
    return jsonify({"message": "Subscription deleted"}), 200
