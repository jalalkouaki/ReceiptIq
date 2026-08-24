import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from config import load_settings
from logger import log_event


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return check_password_hash(hashed_password, plain_password)


def create_jwt_token(user_id: int, username: str, role: str) -> str:
    cfg = load_settings()
    secret = cfg.get("SECRET_KEY", "receiptiq-jwt-secret-local-only-key")
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    cfg = load_settings()
    secret = cfg.get("SECRET_KEY", "receiptiq-jwt-secret-local-only-key")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        log_event("auth", "JWT token expired", level="WARNING")
        return None
    except jwt.InvalidTokenError as e:
        log_event("auth", f"Invalid JWT token: {e}", level="WARNING")
        return None
