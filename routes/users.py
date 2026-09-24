import bcrypt
from flask import Blueprint, request, jsonify, g
from database import run_query
from utils.auth_utils import admin_required, ROLES
from utils.validation import ValidationError, text

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

COLUMNS = "id, staff_id, full_name, email, role, status, created_at"
STATUSES = ("active", "inactive")


def _hash_password(password):
    if not isinstance(password, str) or not 6 <= len(password) <= 72:
        raise ValidationError("Password must be between 6 and 72 characters")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_choice(value, allowed, label):
    if value not in allowed:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")


def _other_active_admins(user_id):
    return run_query(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND status = 'active' AND id <> %s",
        (user_id,), fetch_one=True,
    )["c"]


@users_bp.get("")
@admin_required
def list_users():
    return jsonify(run_query(f"SELECT {COLUMNS} FROM users ORDER BY id", fetch=True))


@users_bp.post("")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    staff_id = text(data, "staff_id", "Staff ID", 50)
    full_name = text(data, "full_name", "Full name", 100)
    email = text(data, "email", "Email", 120, required=False)
    role = data.get("role") or "maintenance_staff"
    status = data.get("status") or "active"
    _check_choice(role, ROLES, "role")
    _check_choice(status, STATUSES, "status")
    if email and "@" not in email:
        raise ValidationError("Email is not valid")
    password_hash = _hash_password(data.get("password"))

    if run_query("SELECT id FROM users WHERE staff_id = %s", (staff_id,), fetch_one=True):
        return jsonify({"error": "That Staff ID is already in use"}), 409

    new_id = run_query(
        """INSERT INTO users (staff_id, full_name, email, password_hash, role, status)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (staff_id, full_name, email, password_hash, role, status), commit=True,
    )
    return jsonify(run_query(f"SELECT {COLUMNS} FROM users WHERE id = %s", (new_id,), fetch_one=True)), 201


@users_bp.put("/<int:user_id>")
@admin_required
def update_user(user_id):
    target = run_query("SELECT * FROM users WHERE id = %s", (user_id,), fetch_one=True)
    if not target:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    fields, params = [], []

    if "full_name" in data:
        fields.append("full_name = %s"); params.append(text(data, "full_name", "Full name", 100))
    if "email" in data:
        email = text(data, "email", "Email", 120, required=False)
        if email and "@" not in email:
            raise ValidationError("Email is not valid")
        fields.append("email = %s"); params.append(email)

    new_role = data.get("role", target["role"])
    new_status = data.get("status", target["status"])
    _check_choice(new_role, ROLES, "role")
    _check_choice(new_status, STATUSES, "status")
    if "role" in data:
        fields.append("role = %s"); params.append(new_role)
    if "status" in data:
        fields.append("status = %s"); params.append(new_status)

    # Never let the system end up with nobody who can administer it.
    was_active_admin = target["role"] == "admin" and target["status"] == "active"
    still_active_admin = new_role == "admin" and new_status == "active"
    if was_active_admin and not still_active_admin:
        if target["id"] == g.user["id"]:
            raise ValidationError("You cannot demote or deactivate your own account")
        if _other_active_admins(user_id) == 0:
            raise ValidationError("At least one active administrator must remain")

    if data.get("password"):
        fields.append("password_hash = %s"); params.append(_hash_password(data["password"]))

    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    params.append(user_id)
    run_query(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(params), commit=True)
    return jsonify(run_query(f"SELECT {COLUMNS} FROM users WHERE id = %s", (user_id,), fetch_one=True))


@users_bp.delete("/<int:user_id>")
@admin_required
def delete_user(user_id):
    target = run_query("SELECT * FROM users WHERE id = %s", (user_id,), fetch_one=True)
    if not target:
        return jsonify({"error": "User not found"}), 404
    if target["id"] == g.user["id"]:
        raise ValidationError("You cannot delete your own account")
    if target["role"] == "admin" and target["status"] == "active" and _other_active_admins(user_id) == 0:
        raise ValidationError("At least one active administrator must remain")

    run_query("DELETE FROM users WHERE id = %s", (user_id,), commit=True)
    return jsonify({"message": "Deleted"})
