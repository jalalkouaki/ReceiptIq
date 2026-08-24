from flask import Blueprint, request, jsonify, g
from database import get_db_session
from models import User, Receipt
from auth import hash_password
from logger import log_event
from routes.middleware import admin_required

admin_bp = Blueprint("admin_bp", __name__)


@admin_bp.route("/api/admin/users", methods=["GET"])
@admin_required
def get_users():
    db = next(get_db_session())
    users = db.query(User).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@admin_bp.route("/api/admin/users", methods=["POST"])
@admin_required
def create_user():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if role not in ["admin", "user"]:
        return jsonify({"error": "Role must be 'admin' or 'user'"}), 400

    db = next(get_db_session())
    existing = db.query(User).filter_by(username=username).first()
    if existing:
        return jsonify({"error": f"Username '{username}' already exists"}), 400

    new_user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        must_change_password=False
    )
    db.add(new_user)
    db.commit()

    log_event("admin", f"Admin '{g.user.username}' created user '{username}' (role={role})", level="INFO", user=g.user.username)
    return jsonify({"message": "User created successfully", "user": new_user.to_dict()}), 201


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    if user_id == g.user.id:
        return jsonify({"error": "You cannot delete your own admin account"}), 400

    db = next(get_db_session())
    target_user = db.query(User).filter_by(id=user_id).first()
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    target_name = target_user.username
    db.delete(target_user)
    db.commit()

    log_event("admin", f"Admin '{g.user.username}' deleted user '{target_name}'", level="INFO", user=g.user.username)
    return jsonify({"message": f"User '{target_name}' deleted successfully"}), 200


@admin_bp.route("/api/admin/stats", methods=["GET"])
@admin_required
def get_admin_stats():
    db = next(get_db_session())
    total_users = db.query(User).count()
    total_receipts = db.query(Receipt).count()
    total_expenses = sum(r.total_amount for r in db.query(Receipt).all())

    return jsonify({
        "total_users": total_users,
        "total_receipts": total_receipts,
        "total_expenses": round(total_expenses, 2)
    }), 200
