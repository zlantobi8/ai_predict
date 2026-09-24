import datetime
from flask import Blueprint, request, jsonify, g
from database import run_query
from utils.auth_utils import token_required
from utils.health import MAINTENANCE_DISPLAY_STATUS
from utils.validation import ValidationError, iso_date, text

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/api/maintenance")

STATUSES = ("scheduled", "in_progress", "completed")

SELECT_LOGS = f"""
    SELECT m.*, e.name AS equipment_name, e.category, e.location AS equipment_location,
           {MAINTENANCE_DISPLAY_STATUS} AS display_status
    FROM maintenance_logs m
    JOIN equipment e ON e.id = m.equipment_id
"""


def _require_equipment(equipment_id):
    if not run_query("SELECT id FROM equipment WHERE id = %s", (equipment_id,), fetch_one=True):
        raise ValidationError("Selected equipment does not exist")


def _record_completion(equipment_id, completed_date):
    """A completed job becomes the equipment's last maintenance date."""
    run_query(
        """UPDATE equipment SET last_maintenance_date = %s
           WHERE id = %s AND (last_maintenance_date IS NULL OR last_maintenance_date < %s)""",
        (completed_date, equipment_id, completed_date), commit=True,
    )


@maintenance_bp.get("")
@token_required
def list_logs():
    status = request.args.get("status")
    query = SELECT_LOGS + " WHERE 1=1"
    params = []
    if status:
        query += " AND m.status = %s"
        params.append(status)
    query += " ORDER BY m.scheduled_date DESC, m.id DESC"
    return jsonify(run_query(query, tuple(params), fetch=True))


@maintenance_bp.post("")
@token_required
def create_log():
    data = request.get_json(silent=True) or {}
    if not data.get("equipment_id"):
        raise ValidationError("Equipment is required")
    maintenance_type = text(data, "maintenance_type", "Maintenance type", 50)
    scheduled = iso_date(data.get("scheduled_date"), "Scheduled date")
    status = data.get("status", "scheduled")
    if status not in STATUSES:
        raise ValidationError(f"status must be one of: {', '.join(STATUSES)}")
    _require_equipment(data["equipment_id"])

    completed = datetime.date.today() if status == "completed" else None
    new_id = run_query(
        """INSERT INTO maintenance_logs
           (equipment_id, maintenance_type, description, technician, status,
            scheduled_date, completed_date, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            data["equipment_id"], maintenance_type,
            text(data, "description", "Description", 2000, required=False),
            text(data, "technician", "Assigned staff", 120, required=False),
            status, scheduled, completed, g.user["full_name"],
        ),
        commit=True,
    )
    if completed:
        _record_completion(data["equipment_id"], completed)
    return jsonify({"id": new_id}), 201


@maintenance_bp.put("/<int:log_id>")
@token_required
def update_log(log_id):
    current = run_query("SELECT * FROM maintenance_logs WHERE id = %s", (log_id,), fetch_one=True)
    if not current:
        return jsonify({"error": "Maintenance record not found"}), 404

    data = request.get_json(silent=True) or {}
    fields, params = [], []

    if "equipment_id" in data:
        _require_equipment(data["equipment_id"])
        fields.append("equipment_id = %s"); params.append(data["equipment_id"])
    if "maintenance_type" in data:
        fields.append("maintenance_type = %s"); params.append(text(data, "maintenance_type", "Maintenance type", 50))
    if "description" in data:
        fields.append("description = %s"); params.append(text(data, "description", "Description", 2000, required=False))
    if "technician" in data:
        fields.append("technician = %s"); params.append(text(data, "technician", "Assigned staff", 120, required=False))
    if "scheduled_date" in data:
        fields.append("scheduled_date = %s"); params.append(iso_date(data["scheduled_date"], "Scheduled date"))

    completed_now = None
    if "status" in data:
        if data["status"] not in STATUSES:
            raise ValidationError(f"status must be one of: {', '.join(STATUSES)}")
        fields.append("status = %s"); params.append(data["status"])
        if data["status"] == "completed":
            completed_now = (
                iso_date(data["completed_date"], "Completed date") if data.get("completed_date")
                else (current["completed_date"] or datetime.date.today())
            )
            fields.append("completed_date = %s"); params.append(completed_now)
        else:
            fields.append("completed_date = NULL")   # re-opened

    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    params.append(log_id)
    run_query(f"UPDATE maintenance_logs SET {', '.join(fields)} WHERE id = %s", tuple(params), commit=True)
    if completed_now:
        _record_completion(data.get("equipment_id", current["equipment_id"]), completed_now)
    return jsonify({"message": "Updated"})


@maintenance_bp.delete("/<int:log_id>")
@token_required
def delete_log(log_id):
    if not run_query("SELECT id FROM maintenance_logs WHERE id = %s", (log_id,), fetch_one=True):
        return jsonify({"error": "Maintenance record not found"}), 404
    run_query("DELETE FROM maintenance_logs WHERE id = %s", (log_id,), commit=True)
    return jsonify({"message": "Deleted"})
