import datetime
import math


class ValidationError(ValueError):
    """Raised by route code; app.py turns it into a 400 JSON response."""


def number(data, key, label=None, minimum=None, maximum=None, required=True, default=None):
    label = label or key
    raw = data.get(key)
    if raw in (None, ""):
        if required:
            raise ValidationError(f"{label} is required")
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number")
    if math.isnan(value) or math.isinf(value):
        raise ValidationError(f"{label} must be a number")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{label} must be at least {minimum:g}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{label} must be at most {maximum:g}")
    return value


def iso_date(value, label="date"):
    """Accepts 'YYYY-MM-DD' and returns a datetime.date."""
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format")


def text(data, key, label=None, max_len=255, required=True):
    label = label or key
    value = data.get(key)
    value = value.strip() if isinstance(value, str) else value
    if not value:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    if len(value) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters")
    return value
