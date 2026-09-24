"""
Trains a scikit-learn DecisionTreeClassifier that predicts equipment
condition from sensor readings.

IMPORTANT (read this before you defend the project):
There is no real historical sensor log for your campus equipment, so this
script generates a synthetic training dataset using realistic engineering
thresholds (temperature, vibration, voltage deviation, operating hours,
maintenance history) plus random noise, then trains an actual Decision
Tree on that data. The model at inference time only ever sees the trained
tree's learned splits — it is not an if/else rule engine. If you later get
real logged sensor + outcome data, drop it into `build_dataset()` in place
of the synthetic generator and retrain; nothing else in the API needs to
change.

Run this once (and again any time you change the dataset):
    python ml/train_model.py
It writes ml/model.joblib (the trained tree + encoders + feature order).
"""
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

RANDOM_SEED = 42
N_SAMPLES = 6000

try:                                   # `python ml/train_model.py` (script) or imported as a package
    from constants import EQUIPMENT_TYPES, MAINTENANCE_HISTORY, CONDITIONS
except ImportError:
    from ml.constants import EQUIPMENT_TYPES, MAINTENANCE_HISTORY, CONDITIONS


def _label_row(temp, vib, volt_dev, hours, history):
    """Domain-informed scoring function used ONLY to generate synthetic
    ground-truth labels for training. The deployed model does not call
    this function — it uses the tree learned from this labeled data."""
    score = 0
    score += 2 if temp > 85 else (1 if temp > 70 else 0)
    score += 2 if vib > 4.0 else (1 if vib > 2.0 else 0)
    score += 2 if volt_dev > 15 else (1 if volt_dev > 7 else 0)
    score += 2 if hours > 8000 else (1 if hours > 4000 else 0)
    score += {"recent": 0, "moderate": 1, "overdue": 3}[history]

    if score <= 2:
        return "Healthy"
    elif score <= 4:
        return "Needs Monitoring"
    elif score <= 7:
        return "Needs Maintenance"
    return "Critical"


def build_dataset(n=N_SAMPLES, seed=RANDOM_SEED):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        equipment_type = rng.choice(EQUIPMENT_TYPES)
        history = rng.choice(MAINTENANCE_HISTORY, p=[0.4, 0.4, 0.2])

        temp = rng.normal(65, 18)
        temp = float(np.clip(temp, 15, 130))

        vib = abs(rng.normal(2.0, 1.6))
        vib = float(np.clip(vib, 0, 12))

        nominal_voltage = 220.0
        voltage = rng.normal(nominal_voltage, 12)
        volt_dev = abs(voltage - nominal_voltage) / nominal_voltage * 100

        hours = float(np.clip(rng.exponential(3500), 0, 15000))

        label = _label_row(temp, vib, volt_dev, hours, history)

        rows.append({
            "equipment_type": equipment_type,
            "temperature": round(temp, 2),
            "vibration": round(vib, 2),
            "voltage": round(float(voltage), 2),
            "operating_hours": round(hours, 1),
            "maintenance_history": history,
            "condition": label,
        })
    return pd.DataFrame(rows)


def train():
    df = build_dataset()

    equip_encoder = LabelEncoder().fit(EQUIPMENT_TYPES)
    history_encoder = LabelEncoder().fit(MAINTENANCE_HISTORY)
    condition_encoder = LabelEncoder().fit(CONDITIONS)

    df["equipment_type_enc"] = equip_encoder.transform(df["equipment_type"])
    df["maintenance_history_enc"] = history_encoder.transform(df["maintenance_history"])
    df["condition_enc"] = condition_encoder.transform(df["condition"])

    feature_cols = [
        "equipment_type_enc", "temperature", "vibration",
        "voltage", "operating_hours", "maintenance_history_enc",
    ]
    X = df[feature_cols]
    y = df["condition_enc"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = DecisionTreeClassifier(
        max_depth=8,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"Test accuracy: {acc:.3f}")
    print(classification_report(
        y_test, preds, target_names=condition_encoder.classes_
    ))

    bundle = {
        "model": model,
        "equip_encoder": equip_encoder,
        "history_encoder": history_encoder,
        "condition_encoder": condition_encoder,
        "feature_cols": feature_cols,
    }
    out_path = os.path.join(os.path.dirname(__file__), "model.joblib")
    joblib.dump(bundle, out_path)
    print(f"Saved trained model to {out_path}")


if __name__ == "__main__":
    train()
