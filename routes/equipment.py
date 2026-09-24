from flask import Blueprint, request, jsonify
from database import run_query
from utils.auth_utils import token_required
from utils.health import LATEST_PREDICTION_JOIN, EQUIPMENT_STATUSES, health_label
from utils.validation import ValidationError, number, text
from ml.constants import EQUIPMENT_TYPES

equipment_bp = Blueprint("equipment", __name__, url_prefix="/api/equipment")

SELECT_WITH_LATEST_PREDICTION = f"""
    SELECT e.*,
           lp.predicted_condition AS last_condition,
           lp.risk_level          AS last_risk,
           lp.confidence          AS last_confidence,
           lp.created_at          AS last_prediction_at
    FROM equipment e
    {LATEST_PREDICTION_JOIN}
"""


def _annotate(row):
    """Adds the labels the UI shows: health (Healthy/At Risk/Faulty) and condition (last ML result)."""
    row["health"] = health_label(row["status"])
    row["condition"] = row["last_condition"] or "Not assessed"
    return row


def _check_type_and_status(data):
    if "equipment_type" in data and data["equipment_type"] not in EQUIPMENT_TYPES:
        raise ValidationError(f"equipment_type must be one of: {', '.join(EQUIPMENT_TYPES)}")
    if "status" in data and data["status"] not in EQUIPMENT_STATUSES:
        raise ValidationError(f"status must be one of: {', '.join(EQUIPMENT_STATUSES)}")


@equipment_bp.get("")
@token_required
def list_equipment():
    category = request.args.get("category")
    search = request.args.get("search")

    query = SELECT_WITH_LATEST_PREDICTION + " WHERE 1=1"
    params = []
    if category:
        query += " AND e.category = %s"
        params.append(category)
    if search:
        query += " AND e.name LIKE %s"
        params.append(f"%{search}%")
    query += " ORDER BY e.id"

    return jsonify([_annotate(r) for r in run_query(query, tuple(params), fetch=True)])


@equipment_bp.get("/<int:equipment_id>")
@token_required
def get_equipment(equipment_id):
    row = run_query(SELECT_WITH_LATEST_PREDICTION + " WHERE e.id = %s", (equipment_id,), fetch_one=True)
    if not row:
        return jsonify({"error": "Equipment not found"}), 404
    return jsonify(_annotate(row))


@equipment_bp.post("")
@token_required
def create_equipment():
    data = request.get_json(silent=True) or {}
    name = text(data, "name", "Equipment name", 120)
    category = text(data, "category", "Category", 50)
    if not data.get("equipment_type"):
        raise ValidationError("equipment_type is required")
    _check_type_and_status(data)
    hours = number(data, "operating_hours", "Operating hours", 0, 1_000_000, required=False, default=0)

    new_id = run_query(
        """INSERT INTO equipment
           (name, equipment_type, category, location, status, operating_hours,
            installed_date, last_maintenance_date)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            name, data["equipment_type"], category,
            text(data, "location", "Location", 120, required=False),
            data.get("status", "operational"), hours,
            data.get("installed_date") or None, data.get("last_maintenance_date") or None,
        ),
        commit=True,
    )

    # Optional first sensor reading (the Add Equipment form has temperature/vibration/voltage boxes).
    if all(data.get(k) not in (None, "") for k in ("temperature", "vibration", "voltage")):
        run_query(
            """INSERT INTO sensor_readings (equipment_id, temperature, vibration, voltage, operating_hours)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                new_id,
                number(data, "temperature", "Temperature", -50, 300),
                number(data, "vibration", "Vibration", 0, 100),
                number(data, "voltage", "Voltage", 0, 2000),
                hours,
            ),
            commit=True,
        )
    return jsonify({"id": new_id}), 201


@equipment_bp.put("/<int:equipment_id>")
@token_required
def update_equipment(equipment_id):
    if not run_query("SELECT id FROM equipment WHERE id = %s", (equipment_id,), fetch_one=True):
        return jsonify({"error": "Equipment not found"}), 404

    data = request.get_json(silent=True) or {}
    _check_type_and_status(data)
    if "operating_hours" in data:
        data["operating_hours"] = number(data, "operating_hours", "Operating hours", 0, 1_000_000)

    fields, params = [], []
    for col in ["name", "equipment_type", "category", "location", "status", "operating_hours",
                "installed_date", "last_maintenance_date"]:
        if col in data:
            value = data[col]
            if col in ("name", "category") and not (isinstance(value, str) and value.strip()):
                raise ValidationError(f"{col} cannot be empty")
            fields.append(f"{col} = %s")
            params.append(value if value != "" else None)
    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    params.append(equipment_id)
    run_query(f"UPDATE equipment SET {', '.join(fields)} WHERE id = %s", tuple(params), commit=True)
    return jsonify({"message": "Updated"})


@equipment_bp.delete("/<int:equipment_id>")
@token_required
def delete_equipment(equipment_id):
    if not run_query("SELECT id FROM equipment WHERE id = %s", (equipment_id,), fetch_one=True):
        return jsonify({"error": "Equipment not found"}), 404
    run_query("DELETE FROM equipment WHERE id = %s", (equipment_id,), commit=True)
    return jsonify({"message": "Deleted"})
