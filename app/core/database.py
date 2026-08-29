from typing import Any

from pymongo import AsyncMongoClient

from app.core.config import get_settings

_client: AsyncMongoClient | None = None


def get_mongo_client() -> AsyncMongoClient:
    """Return the shared MongoDB client, creating it on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncMongoClient(settings.mongodb_url)
    return _client


def get_database() -> Any:
    """Return the application database from the shared client."""
    return get_mongo_client()[get_settings().MONGODB_DATABASE]


async def close_mongo_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ensure_indexes() -> None:
    """Create/verify required indexes."""
    db = get_database()
    await db.users.create_index("email", unique=True)
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("user_id")
    # TTL index: expired refresh tokens are cleaned up automatically.
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
