import os
import joblib
import numpy as np
import pandas as pd

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
_bundle = None


class ModelNotTrainedError(RuntimeError):
    pass


def _load_bundle():
    global _bundle
    if _bundle is None:
        if not os.path.exists(_MODEL_PATH):
            raise ModelNotTrainedError(
                "No trained model found. Run `python ml/train_model.py` first."
            )
        _bundle = joblib.load(_MODEL_PATH)
    return _bundle


# Risk level shown to the frontend is derived from the tree's own class
# probabilities, not a separate rule set.
_RISK_BY_CONDITION = {
    "Healthy": "low",
    "Needs Monitoring": "moderate",
    "Needs Maintenance": "high",
    "Critical": "critical",
}

# What the equipment's stored status becomes after a prediction (see routes/prediction.py).
STATUS_BY_CONDITION = {
    "Healthy": "operational",
    "Needs Monitoring": "at_risk",
    "Needs Maintenance": "at_risk",
    "Critical": "faulty",
}

RECOMMENDATION_BY_CONDITION = {
    "Healthy": "Equipment condition appears normal. Continue routine monitoring.",
    "Needs Monitoring": "Keep monitoring this equipment and re-check the readings soon.",
    "Needs Maintenance": "Schedule maintenance and continue monitoring equipment condition.",
    "Critical": "Immediate maintenance inspection is recommended.",
}


def predict(equipment_type: str, temperature: float, vibration: float,
            voltage: float, operating_hours: float, maintenance_history: str):
    bundle = _load_bundle()
    model = bundle["model"]
    equip_encoder = bundle["equip_encoder"]
    history_encoder = bundle["history_encoder"]
    condition_encoder = bundle["condition_encoder"]

    if equipment_type not in equip_encoder.classes_:
        raise ValueError(
            f"Unknown equipment_type '{equipment_type}'. "
            f"Expected one of {list(equip_encoder.classes_)}"
        )
    if maintenance_history not in history_encoder.classes_:
        raise ValueError(
            f"Unknown maintenance_history '{maintenance_history}'. "
            f"Expected one of {list(history_encoder.classes_)}"
        )

    features = pd.DataFrame([{
        "equipment_type_enc": equip_encoder.transform([equipment_type])[0],
        "temperature": float(temperature),
        "vibration": float(vibration),
        "voltage": float(voltage),
        "operating_hours": float(operating_hours),
        "maintenance_history_enc": history_encoder.transform([maintenance_history])[0],
    }])[bundle["feature_cols"]]

    pred_class_idx = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    condition = str(condition_encoder.inverse_transform([pred_class_idx])[0])
    confidence = float(np.max(probabilities))

    return {
        "predicted_condition": condition,
        "risk_level": _RISK_BY_CONDITION.get(condition, "moderate"),
        "recommendation": RECOMMENDATION_BY_CONDITION.get(condition, ""),
        "confidence": round(confidence, 4),
        "class_probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(condition_encoder.classes_, probabilities)
        },
    }
RISK_BY_CONDITION = _RISK_BY_CONDITION  # public alias (used by reports)
