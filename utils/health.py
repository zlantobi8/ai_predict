"""One place that defines what 'healthy / at risk / faulty' and 'due soon / overdue' mean,
so the Dashboard, Equipment, Reports and Maintenance pages always agree."""

# A maintenance job that is not completed counts as "Due Soon" when it is scheduled within this many days.
DUE_SOON_DAYS = 7

# equipment.status (stored) -> label shown in the UI
HEALTH_LABEL = {"operational": "Healthy", "at_risk": "At Risk", "faulty": "Faulty"}
EQUIPMENT_STATUSES = tuple(HEALTH_LABEL)

# Latest prediction for each piece of equipment, joined as alias `lp` (needs the equipment table aliased `e`)
LATEST_PREDICTION_JOIN = """
    LEFT JOIN predictions lp
      ON lp.id = (SELECT MAX(p2.id) FROM predictions p2 WHERE p2.equipment_id = e.id)
"""

# SQL expression giving the status label shown for a maintenance log (table aliased `m`)
MAINTENANCE_DISPLAY_STATUS = f"""
    CASE
        WHEN m.status = 'completed' THEN 'Completed'
        WHEN m.scheduled_date < CURDATE() THEN 'Overdue'
        WHEN m.scheduled_date <= DATE_ADD(CURDATE(), INTERVAL {DUE_SOON_DAYS} DAY) THEN 'Due Soon'
        ELSE 'Scheduled'
    END
"""


def health_label(status):
    return HEALTH_LABEL.get(status, "Healthy")
