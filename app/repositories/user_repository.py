from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.models.user import new_user_document


class UserRepository:
    """MongoDB persistence for users."""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db
        self._collection: Any | None = None

    @property
    def collection(self) -> Any:
        if self._collection is None:
            db = self._db if self._db is not None else get_database()
            self._collection = db.users
        return self._collection

    async def create_user(self, name: str, email: str, password_hash: str) -> dict[str, Any]:
        document = new_user_document(name, email, password_hash)
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise EmailAlreadyRegisteredError from exc
        document["_id"] = result.inserted_id
        return document

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email})

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        from bson import ObjectId

        try:
            _id = ObjectId(user_id)
        except Exception:
            return None
        return await self.collection.find_one({"_id": _id})

    async def email_exists(self, email: str) -> bool:
        return await self.collection.find_one({"email": email}, {"_id": 1}) is not None


class EmailAlreadyRegisteredError(Exception):
    """Raised when a user tries to register with an email that already exists."""


def _hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RefreshTokenRepository:
    """MongoDB persistence for refresh tokens (stored hashed, with rotation)."""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db
        self._collection: Any | None = None

    @property
    def collection(self) -> Any:
        if self._collection is None:
            db = self._db if self._db is not None else get_database()
            self._collection = db.refresh_tokens
        return self._collection

    async def issue(
        self, user_id: str, token: str, expires_at: datetime
    ) -> dict[str, Any]:
        document = {
            "user_id": user_id,
            "token_hash": _hash_token(token),
            "revoked": False,
            "expires_at": expires_at,
            "created_at": datetime.now(UTC),
        }
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def find_active_by_token(self, token: str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"token_hash": _hash_token(token)})
        if document is None or document.get("revoked", False):
            return None
        expires_at = document.get("expires_at")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                return None
        return document

    async def revoke(self, token: str) -> bool:
        document = await self.collection.find_one({"token_hash": _hash_token(token)})
        if document is None:
            return False
        return await self._set_revoked(document)

    async def revoke_all_for_user(self, user_id: str) -> int:
        revoked = 0
        # Async pymongo does not support update_many on all drivers yet; iterate.
        async for document in self.collection.find({"user_id": user_id, "revoked": False}):
            if await self._set_revoked(document):
                revoked += 1
        return revoked

    async def _set_revoked(self, document: dict[str, Any]) -> bool:
        if document.get("revoked", False):
            return False
        document["revoked"] = True
        await self.collection.replace_one({"_id": document["_id"]}, document)
        return True
