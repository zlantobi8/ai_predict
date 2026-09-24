from flask import Blueprint, request, jsonify
from database import run_query
from utils.auth_utils import token_required

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@alerts_bp.get("")
@token_required
def list_alerts():
    status = request.args.get("status")
    query = """
        SELECT a.*, e.name AS equipment_name, e.location AS equipment_location
        FROM alerts a
        JOIN equipment e ON e.id = a.equipment_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND a.status = %s"
        params.append(status)
    query += " ORDER BY a.created_at DESC, a.id DESC"
    return jsonify(run_query(query, tuple(params), fetch=True))


@alerts_bp.put("/<int:alert_id>")
@token_required
def update_alert(alert_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("open", "acknowledged", "resolved"):
        return jsonify({"error": "status must be one of open, acknowledged, resolved"}), 400
    if not run_query("SELECT id FROM alerts WHERE id = %s", (alert_id,), fetch_one=True):
        return jsonify({"error": "Alert not found"}), 404

    if status == "resolved":
        run_query("UPDATE alerts SET status = %s, resolved_at = NOW() WHERE id = %s",
                  (status, alert_id), commit=True)
    else:
        run_query("UPDATE alerts SET status = %s, resolved_at = NULL WHERE id = %s",
                  (status, alert_id), commit=True)
    return jsonify({"message": "Updated"})
