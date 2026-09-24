"""Values shared by the trainer, the predictor and the API validation, so they can't drift apart."""

EQUIPMENT_TYPES = ["lathe", "drilling", "ac", "water-pump"]
MAINTENANCE_HISTORY = ["recent", "moderate", "overdue"]
CONDITIONS = ["Healthy", "Needs Monitoring", "Needs Maintenance", "Critical"]
