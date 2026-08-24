from flask import Blueprint, request, jsonify, g
from config import load_settings, save_settings
from database import check_db_encryption
from logger import log_event
from routes.middleware import jwt_required

setting_bp = Blueprint("setting_bp", __name__)


@setting_bp.route("/api/settings", methods=["GET"])
@jwt_required
def get_settings():
    cfg = load_settings()
    # Mask ENCRYPTION_KEY
    sanitized = {k: v for k, v in cfg.items() if k != "ENCRYPTION_KEY"}
    return jsonify({"settings": sanitized}), 200


@setting_bp.route("/api/settings", methods=["PATCH"])
@jwt_required
def update_settings():
    data = request.get_json() or {}
    updated = save_settings(data)
    log_event("admin", f"User '{g.user.username}' updated application settings", level="INFO", user=g.user.username)
    sanitized = {k: v for k, v in updated.items() if k != "ENCRYPTION_KEY"}
    return jsonify({"message": "Settings updated", "settings": sanitized}), 200
