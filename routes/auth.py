import bcrypt
from flask import Blueprint, request, jsonify, g
from database import run_query
from utils.auth_utils import generate_token, token_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def public_user(user):
    return {
        "id": user["id"],
        "staff_id": user["staff_id"],
        "full_name": user["full_name"],
        "email": user.get("email"),
        "role": user["role"],
        "status": user["status"],
    }


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    # The login form calls the field "username"; it is the account's staff_id.
    staff_id = (data.get("staff_id") or data.get("username") or "").strip()
    password = data.get("password") or ""

    if not staff_id or not password:
        return jsonify({"error": "Staff ID and password are required"}), 400

    user = run_query("SELECT * FROM users WHERE staff_id = %s", (staff_id,), fetch_one=True)
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Invalid staff ID or password"}), 401
    if user["status"] != "active":
        return jsonify({"error": "This account is inactive. Please contact an administrator."}), 403

    return jsonify({"token": generate_token(user), "user": public_user(user)})


@auth_bp.get("/me")
@token_required
def me():
    return jsonify(public_user(g.user))

# Accounts are created by administrators through POST /api/users (see routes/users.py).
# The old open POST /api/auth/register was removed: anyone could call it with role=admin.
