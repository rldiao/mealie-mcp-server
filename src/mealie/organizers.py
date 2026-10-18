import logging
from typing import Any, Dict, Literal

logger = logging.getLogger("mealie-mcp")

OrganizerKind = Literal["tag", "category", "tool", "label", "food", "unit"]

# kind -> (method, endpoint, source key, target key). Tags, categories, tools,
# and labels share the newer {fromId, toId} merge; foods and units keep their
# original PUT payloads.
_MERGE_ENDPOINTS = {
    "tag": ("POST", "/api/organizers/tags/merge", "fromId", "toId"),
    "category": ("POST", "/api/organizers/categories/merge", "fromId", "toId"),
    "tool": ("POST", "/api/organizers/tools/merge", "fromId", "toId"),
    "label": ("POST", "/api/groups/labels/merge", "fromId", "toId"),
    "food": ("PUT", "/api/foods/merge", "fromFood", "toFood"),
    "unit": ("PUT", "/api/units/merge", "fromUnit", "toUnit"),
}


class OrganizersMixin:
    """Mixin for operations shared by every kind of organizer."""

    def merge_organizers(
        self, kind: OrganizerKind, from_id: str, to_id: str
    ) -> Dict[str, Any]:
        """Move every use of one organizer onto another, then delete the first.

        Args:
            kind: Which organizer type both IDs belong to
            from_id: ID of the organizer to merge away (deleted afterwards)
            to_id: ID of the organizer to keep

        Returns:
            The surviving organizer, or Mealie's success message for foods/units
        """
        if kind not in _MERGE_ENDPOINTS:
            raise ValueError(f"Unknown organizer kind: {kind}")
        if not from_id or not from_id.strip() or not to_id or not to_id.strip():
            raise ValueError("Both from_id and to_id are required")
        if from_id == to_id:
            raise ValueError("from_id and to_id must be different")
        method, url, from_key, to_key = _MERGE_ENDPOINTS[kind]

        logger.info({"message": "Merging organizers", "kind": kind})
        return self._handle_request(
            method, url, json={from_key: from_id, to_key: to_id}
        )
