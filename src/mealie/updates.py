from typing import Any


def merge_replacement_record(
    existing: Any,
    changes: dict[str, Any],
    *,
    required_fields: tuple[str, ...] = ("id", "name"),
) -> dict[str, Any]:
    """Merge a partial update only after validating the fetched record."""
    if not isinstance(existing, dict) or any(
        not isinstance(existing.get(field), str) or not existing[field].strip()
        for field in required_fields
    ):
        raise ValueError("Cannot update an invalid or incomplete existing record")
    return {**existing, **changes}
