from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId


class FakeCollection:
    """Minimal in-memory stand-in for a MongoDB collection (find_one/insert_one)."""

    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}

    async def create_index(self, *args, **kwargs) -> None:
        return None

    async def insert_one(self, document: dict[str, Any]):
        if "email" in document and any(
            d["email"] == document["email"] for d in self.documents.values()
        ):
            from pymongo.errors import DuplicateKeyError

            raise DuplicateKeyError(11000, "E11000 duplicate key error collection: tests.users index: email_unique")
        _id = ObjectId()
        stored = dict(document)
        stored["_id"] = _id
        self.documents[_id] = stored

        class Result:
            inserted_id = _id

        return Result()

    async def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None):
        doc = self._match(filter)
        if doc is None:
            return None
        if projection and projection.get("_id") == 1 and len(projection) == 1:
            return {"_id": doc["_id"]}
        return dict(doc)

    def _match(self, filter: dict[str, Any]):
        if "_id" in filter:
            return self.documents.get(filter["_id"])
        for key, value in filter.items():
            if key == "_id":
                continue
            return next(
                (d for d in self.documents.values() if d.get(key) == value), None
            )
        return None

    def find(self, filter: dict[str, Any]):
        """Return an async iterable over matching documents."""
        matches = [
            dict(d)
            for d in self.documents.values()
            if all(d.get(k) == v for k, v in filter.items())
        ]

        async def _iterator():
            for doc in matches:
                yield doc

        return _iterator()

    async def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any]):
        self.documents[replacement["_id"]] = dict(replacement)

        class Result:
            modified_count = 1

        return Result()


class FakeDatabase:
    def __init__(self) -> None:
        self.users = FakeCollection()
        self.refresh_tokens = FakeCollection()

    async def create_index(self, *args, **kwargs) -> None:  # pragma: no cover
        return None


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDatabase()
    import app.core.database as database_module
    import app.dependencies.auth as deps_auth
    import app.repositories.user_repository as repo_module

    monkeypatch.setattr(database_module, "get_database", lambda: db)
    monkeypatch.setattr(deps_auth, "get_database", lambda: db)
    monkeypatch.setattr(repo_module, "get_database", lambda: db)
    return db


@pytest.fixture()
def client(fake_db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    try:
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


def register(client, name="John Doe", email="john@example.com", password="Password@123"):
    return client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )


def login(client, email="john@example.com", password="Password@123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def refresh(client, refresh_token):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


def logout(client, refresh_token):
    return client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
