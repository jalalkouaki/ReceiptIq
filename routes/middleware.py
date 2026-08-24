from functools import wraps
from flask import request, jsonify, g
from auth import decode_jwt_token
from database import get_db_session
from models import User


def get_current_user():
    """Extract and return authenticated user from Authorization header or query parameter."""
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.args.get("token"):
        token = request.args.get("token")

    if not token:
        return None

    payload = decode_jwt_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    db = next(get_db_session())
    user = db.query(User).filter_by(id=user_id).first()
    return user


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized or expired token"}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        g.user = user
        return f(*args, **kwargs)
    return decorated
