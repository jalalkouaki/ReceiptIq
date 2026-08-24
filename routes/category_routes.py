from flask import Blueprint, jsonify
from database import get_db_session
from models import ExpenseCategory
from routes.middleware import jwt_required

category_bp = Blueprint("category_bp", __name__)


@category_bp.route("/api/categories", methods=["GET"])
@jwt_required
def get_categories():
    db = next(get_db_session())
    categories = db.query(ExpenseCategory).all()
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200
