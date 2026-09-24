import jwt
import datetime
from functools import wraps
from flask import request, jsonify, g
from config import Config
from database import run_query

ROLES = ("admin", "maintenance_staff", "technical_staff")


def generate_token(user):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user["id"]),          # JWT spec: subject is a string (newer PyJWT enforces this)
        "staff_id": user["staff_id"],
        "role": user["role"],
        "exp": now + datetime.timedelta(hours=Config.JWT_EXPIRES_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])


def token_required(fn):
    """Requires a valid Bearer token AND a still-existing, active account.

    g.user is loaded fresh from the database, so deactivating or deleting a user
    (or changing their role) takes effect immediately instead of when their token expires.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        user = run_query(
            "SELECT id, staff_id, full_name, email, role, status FROM users WHERE id = %s",
            (payload.get("sub"),), fetch_one=True,
        )
        if not user or user["status"] != "active":
            return jsonify({"error": "This account is no longer active"}), 401
        g.user = user
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """token_required + the caller must be an administrator."""
    @wraps(fn)
    @token_required
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            return jsonify({"error": "Administrator access required"}), 403
        return fn(*args, **kwargs)
    return wrapper
