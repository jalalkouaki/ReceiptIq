from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import PriceHistory
from routes.middleware import jwt_required

price_history_bp = Blueprint("price_history_bp", __name__)


@price_history_bp.route("/api/price-history", methods=["GET"])
@jwt_required
def get_price_history():
    item_query = request.args.get("item", "").strip()

    db = next(get_db_session())
    query = db.query(PriceHistory).filter_by(user_id=g.user.id)

    if item_query:
        query = query.filter(
            (PriceHistory.item_name.ilike(f"%{item_query}%")) |
            (PriceHistory.vendor.ilike(f"%{item_query}%"))
        )

    records = query.order_by(PriceHistory.date.asc()).all()
    return jsonify({"price_history": [r.to_dict() for r in records]}), 200
