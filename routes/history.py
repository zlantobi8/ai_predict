from flask import Blueprint, jsonify
from database import run_query
from utils.auth_utils import token_required
from utils.health import MAINTENANCE_DISPLAY_STATUS

history_bp = Blueprint("history", __name__, url_prefix="/api/history")


@history_bp.get("")
@token_required
def list_history():
    """One chronological feed of predictions, maintenance jobs and user accounts."""
    records = run_query(
        f"""
        (SELECT 'prediction' AS activity, p.id AS record_id, p.created_at AS occurred_at,
                e.name AS equipment_name, e.location AS equipment_location,
                p.created_by AS actor, p.predicted_condition AS result,
                p.risk_level AS risk_level, p.confidence AS confidence,
                NULL AS maintenance_type, NULL AS scheduled_date, NULL AS role
         FROM predictions p JOIN equipment e ON e.id = p.equipment_id)
        UNION ALL
        (SELECT 'maintenance', m.id, m.created_at,
                e.name, e.location,
                COALESCE(m.created_by, m.technician), {MAINTENANCE_DISPLAY_STATUS},
                NULL, NULL,
                m.maintenance_type, m.scheduled_date, NULL
         FROM maintenance_logs m JOIN equipment e ON e.id = m.equipment_id)
        UNION ALL
        (SELECT 'user', u.id, u.created_at,
                NULL, NULL,
                u.full_name, IF(u.status = 'active', 'Active', 'Inactive'),
                NULL, NULL,
                NULL, NULL, u.role
         FROM users u)
        ORDER BY occurred_at DESC
        LIMIT 500
        """,
        fetch=True,
    )
    counts = run_query(
        """SELECT (SELECT COUNT(*) FROM predictions) AS predictions,
                  (SELECT COUNT(*) FROM maintenance_logs) AS maintenance,
                  (SELECT COUNT(*) FROM users) AS users""",
        fetch_one=True,
    )
    counts["total"] = counts["predictions"] + counts["maintenance"] + counts["users"]
    return jsonify({"counts": counts, "records": records})
