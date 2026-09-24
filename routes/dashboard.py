from flask import Blueprint, request, jsonify
from database import run_query
from utils.auth_utils import token_required
from utils.health import DUE_SOON_DAYS, MAINTENANCE_DISPLAY_STATUS
from utils.validation import ValidationError, iso_date
from ml.constants import CONDITIONS
from ml.predictor import RISK_BY_CONDITION

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _equipment_status_counts():
    rows = run_query("SELECT status, COUNT(*) AS c FROM equipment GROUP BY status", fetch=True)
    counts = {r["status"]: r["c"] for r in rows}
    return {
        "healthy": counts.get("operational", 0),
        "at_risk": counts.get("at_risk", 0),
        "faulty": counts.get("faulty", 0),
    }


def _maintenance_status_counts(where="", params=()):
    rows = run_query(
        f"""SELECT {MAINTENANCE_DISPLAY_STATUS} AS display_status, COUNT(*) AS c
            FROM maintenance_logs m {where}
            GROUP BY display_status""",
        tuple(params), fetch=True,
    )
    counts = {r["display_status"]: r["c"] for r in rows}
    return {
        "scheduled": counts.get("Scheduled", 0),
        "due_soon": counts.get("Due Soon", 0),
        "overdue": counts.get("Overdue", 0),
        "completed": counts.get("Completed", 0),
    }


@dashboard_bp.get("/summary")
@token_required
def summary():
    total_equipment = run_query("SELECT COUNT(*) AS c FROM equipment", fetch_one=True)["c"]
    open_alerts = run_query(
        "SELECT COUNT(*) AS c FROM alerts WHERE status = 'open'", fetch_one=True
    )["c"]
    pending_maintenance = run_query(
        "SELECT COUNT(*) AS c FROM maintenance_logs WHERE status IN ('scheduled','in_progress')",
        fetch_one=True,
    )["c"]
    predictions_today = run_query(
        "SELECT COUNT(*) AS c FROM predictions WHERE DATE(created_at) = CURDATE()",
        fetch_one=True,
    )["c"]
    by_category = run_query(
        "SELECT category, COUNT(*) AS count FROM equipment GROUP BY category", fetch=True
    )
    risk_breakdown = run_query(
        """SELECT risk_level, COUNT(*) AS count FROM predictions
           WHERE created_at >= NOW() - INTERVAL 30 DAY
           GROUP BY risk_level""",
        fetch=True,
    )
    health = _equipment_status_counts()
    maintenance = _maintenance_status_counts()
    recent_maintenance = run_query(
        f"""SELECT m.id, m.maintenance_type, m.scheduled_date, m.completed_date,
                   e.name AS equipment_name, {MAINTENANCE_DISPLAY_STATUS} AS display_status
            FROM maintenance_logs m JOIN equipment e ON e.id = m.equipment_id
            ORDER BY COALESCE(m.completed_date, m.scheduled_date) DESC, m.id DESC
            LIMIT 5""",
        fetch=True,
    )

    return jsonify({
        "total_equipment": total_equipment,
        "open_alerts": open_alerts,
        "pending_maintenance": pending_maintenance,
        "predictions_today": predictions_today,
        "equipment_by_category": by_category,
        "risk_breakdown_30d": risk_breakdown,
        # used by the Dashboard page
        "healthy_equipment": health["healthy"],
        "at_risk_equipment": health["at_risk"],
        "faulty_equipment": health["faulty"],
        "maintenance_due": maintenance["due_soon"] + maintenance["overdue"],
        "due_soon_days": DUE_SOON_DAYS,
        "recent_maintenance": recent_maintenance,
    })


@reports_bp.get("/condition-trend")
@token_required
def condition_trend():
    """Predicted condition counts per day, for the last 30 days — feeds a line/bar chart."""
    rows = run_query(
        """SELECT DATE(created_at) AS date, predicted_condition, COUNT(*) AS count
           FROM predictions
           WHERE created_at >= NOW() - INTERVAL 30 DAY
           GROUP BY DATE(created_at), predicted_condition
           ORDER BY date""",
        fetch=True,
    )
    return jsonify(rows)


@reports_bp.get("/maintenance-summary")
@token_required
def maintenance_summary():
    rows = run_query(
        """SELECT e.category, m.status, COUNT(*) AS count
           FROM maintenance_logs m
           JOIN equipment e ON e.id = m.equipment_id
           GROUP BY e.category, m.status""",
        fetch=True,
    )
    return jsonify(rows)


def _range_clause(column, date_from, date_to):
    clauses, params = [], []
    if date_from:
        clauses.append(f"DATE({column}) >= %s"); params.append(date_from)
    if date_to:
        clauses.append(f"DATE({column}) <= %s"); params.append(date_to)
    return clauses, params


@reports_bp.get("/overview")
@token_required
def overview():
    """Everything the Reports page shows. Optional ?from=YYYY-MM-DD&to=YYYY-MM-DD.

    The date range applies to maintenance (by scheduled date) and predictions (by when they ran).
    Equipment counts are always the current state.
    """
    date_from = iso_date(request.args["from"], "From date") if request.args.get("from") else None
    date_to = iso_date(request.args["to"], "To date") if request.args.get("to") else None
    if date_from and date_to and date_from > date_to:
        raise ValidationError("The From date cannot be later than the To date")

    total_equipment = run_query("SELECT COUNT(*) AS c FROM equipment", fetch_one=True)["c"]
    health = _equipment_status_counts()

    m_clauses, m_params = _range_clause("m.scheduled_date", date_from, date_to)
    m_where = ("WHERE " + " AND ".join(m_clauses)) if m_clauses else ""
    maintenance = _maintenance_status_counts(m_where, m_params)

    p_clauses, p_params = _range_clause("created_at", date_from, date_to)
    p_where = ("WHERE " + " AND ".join(p_clauses)) if p_clauses else ""
    predictions_made = run_query(
        f"SELECT COUNT(*) AS c FROM predictions {p_where}", tuple(p_params), fetch_one=True
    )["c"]

    # Latest prediction per equipment inside the range -> "how many pieces of equipment are in each condition"
    rows = run_query(
        f"""SELECT predicted_condition, COUNT(*) AS c FROM predictions
            WHERE id IN (SELECT MAX(id) FROM predictions {p_where} GROUP BY equipment_id)
            GROUP BY predicted_condition""",
        tuple(p_params), fetch=True,
    )
    by_condition = {r["predicted_condition"]: r["c"] for r in rows}
    prediction_summary = [
        {"predicted_condition": c, "risk_level": RISK_BY_CONDITION[c],
         "equipment_count": by_condition.get(c, 0)}
        for c in CONDITIONS
    ]

    return jsonify({
        "range": {"from": date_from, "to": date_to},
        "summary": {
            "total_equipment": total_equipment,
            "maintenance_records": sum(maintenance.values()),
            "predictions_made": predictions_made,
            "at_risk_faulty": health["at_risk"] + health["faulty"],
        },
        "equipment_status": health,
        "maintenance_activity": maintenance,
        "prediction_summary": prediction_summary,
    })
