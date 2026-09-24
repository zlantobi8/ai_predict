from flask import Blueprint, request, jsonify, g
from database import run_query
from utils.auth_utils import token_required
from utils.validation import ValidationError, number
from ml.predictor import (
    predict as run_prediction, ModelNotTrainedError, STATUS_BY_CONDITION,
)

prediction_bp = Blueprint("prediction", __name__, url_prefix="/api/predictions")


@prediction_bp.post("")
@token_required
def create_prediction():
    data = request.get_json(silent=True) or {}
    if not data.get("equipment_id"):
        raise ValidationError("equipment_id is required")
    if not data.get("maintenance_history"):
        raise ValidationError("maintenance_history is required")

    equipment = run_query(
        "SELECT id, name, equipment_type FROM equipment WHERE id = %s",
        (data["equipment_id"],), fetch_one=True,
    )
    if not equipment:
        return jsonify({"error": "Equipment not found"}), 404

    # equipment_type is optional: the equipment record already knows what it is.
    equipment_type = data.get("equipment_type") or equipment["equipment_type"]
    if equipment_type != equipment["equipment_type"]:
        raise ValidationError(
            f"equipment_type '{equipment_type}' does not match this equipment "
            f"(it is registered as '{equipment['equipment_type']}')"
        )

    temperature = number(data, "temperature", "Temperature", -50, 300)
    vibration = number(data, "vibration", "Vibration", 0, 100)
    voltage = number(data, "voltage", "Voltage", 0, 2000)
    hours = number(data, "operating_hours", "Operating hours", 0, 1_000_000)

    try:
        result = run_prediction(
            equipment_type=equipment_type, temperature=temperature, vibration=vibration,
            voltage=voltage, operating_hours=hours,
            maintenance_history=data["maintenance_history"],
        )
    except ModelNotTrainedError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        raise ValidationError(str(e))

    equipment_id = equipment["id"]
    new_id = run_query(
        """INSERT INTO predictions
           (equipment_id, temperature, vibration, voltage, operating_hours,
            maintenance_history, predicted_condition, risk_level, confidence, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            equipment_id, temperature, vibration, voltage, hours,
            data["maintenance_history"], result["predicted_condition"],
            result["risk_level"], result["confidence"], g.user["full_name"],
        ),
        commit=True,
    )

    # Keep the rest of the system in step with the prediction:
    # the readings are stored, and the equipment's hours and health status are updated.
    run_query(
        """INSERT INTO sensor_readings (equipment_id, temperature, vibration, voltage, operating_hours)
           VALUES (%s, %s, %s, %s, %s)""",
        (equipment_id, temperature, vibration, voltage, hours), commit=True,
    )
    run_query(
        "UPDATE equipment SET operating_hours = %s, status = %s WHERE id = %s",
        (hours, STATUS_BY_CONDITION.get(result["predicted_condition"], "at_risk"), equipment_id),
        commit=True,
    )

    # A high-risk prediction automatically raises an alert for the Alerts page.
    alert_created = result["risk_level"] in ("high", "critical")
    if alert_created:
        run_query(
            "INSERT INTO alerts (equipment_id, message, severity) VALUES (%s, %s, %s)",
            (
                equipment_id,
                f"Prediction flagged {result['predicted_condition']} "
                f"(confidence {result['confidence']:.0%})",
                result["risk_level"],
            ),
            commit=True,
        )

    return jsonify({"id": new_id, "equipment_name": equipment["name"],
                    "alert_created": alert_created, **result}), 201


@prediction_bp.get("")
@token_required
def list_predictions():
    equipment_id = request.args.get("equipment_id")
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
    except ValueError:
        limit = 100

    query = """
        SELECT p.*, e.name AS equipment_name, e.location AS equipment_location,
               e.equipment_type
        FROM predictions p
        JOIN equipment e ON e.id = p.equipment_id
        WHERE 1=1
    """
    params = []
    if equipment_id:
        query += " AND p.equipment_id = %s"
        params.append(equipment_id)
    query += " ORDER BY p.id DESC LIMIT %s"
    params.append(limit)
    return jsonify(run_query(query, tuple(params), fetch=True))
