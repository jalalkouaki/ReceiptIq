from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import InventoryItem
from routes.middleware import jwt_required

inventory_bp = Blueprint("inventory_bp", __name__)


@inventory_bp.route("/api/inventory", methods=["GET"])
@jwt_required
def get_inventory():
    db = next(get_db_session())
    items = db.query(InventoryItem).filter_by(user_id=g.user.id).all()
    results = []
    for item in items:
        d = item.to_dict()
        d["reorder_alert"] = item.quantity <= item.reorder_point
        results.append(d)

    return jsonify({"inventory": results}), 200


@inventory_bp.route("/api/inventory", methods=["POST"])
@jwt_required
def create_inventory_item():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    quantity = int(data.get("quantity", 1))
    unit_cost = float(data.get("unit_cost", 0.0))
    reorder_point = int(data.get("reorder_point", 1))
    receipt_id = data.get("receipt_id")

    if not name:
        return jsonify({"error": "Item name is required"}), 400

    db = next(get_db_session())
    item = InventoryItem(
        user_id=g.user.id,
        receipt_id=receipt_id,
        name=name,
        quantity=quantity,
        unit_cost=unit_cost,
        reorder_point=reorder_point
    )
    db.add(item)
    db.commit()
    return jsonify({"message": "Inventory item created", "item": item.to_dict()}), 201
