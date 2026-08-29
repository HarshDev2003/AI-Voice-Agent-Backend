from datetime import UTC, datetime
from typing import Any


def new_user_document(name: str, email: str, password_hash: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "email": email,
        "password_hash": password_hash,
        "name": name,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }


def serialize_user(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a MongoDB user document into a safe dict (never exposes password hash)."""
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "email": document["email"],
        "is_active": document.get("is_active", True),
    }
