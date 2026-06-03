"""Validation rules for extracted accounting fields."""


def validate_required_fields(fields: dict, required_fields: list[str]) -> dict:
    """Validate required fields and return missing list."""
    missing = [name for name in required_fields if not str(fields.get(name, "")).strip()]
    return {"missing_fields": missing, "is_valid": len(missing) == 0}
