from datetime import datetime
from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import User
from auth import verify_password, create_jwt_token
from logger import log_event
from routes.middleware import jwt_required

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db = next(get_db_session())
    user = db.query(User).filter_by(username=username).first()

    if not user or not verify_password(password, user.password_hash):
        log_event("auth", f"Failed login attempt for username '{username}'", level="WARNING", user=username)
        return jsonify({"error": "Invalid username or password"}), 401

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_jwt_token(user.id, user.username, user.role)
    log_event("auth", f"User '{username}' logged in successfully", level="INFO", user=username)

    redirect_url = "/admin" if user.role == "admin" else "/dashboard"

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict(),
        "redirect_url": redirect_url
    }), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    log_event("auth", "User logged out", level="INFO")
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.route("/api/me", methods=["GET"])
@jwt_required
def get_me():
    return jsonify({"user": g.user.to_dict()}), 200
