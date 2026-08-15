"""Backend API tests — health + auth flow (SQLite, no heavy ala services needed).

Run from the backend/ directory:  pytest -q
The retrieval/chat/knowledge endpoints require the built ala corpus (Qdrant/graph/
BM25) + optionally Ollama; they are exercised by the smoke test below only when
those artifacts are present.
"""

from __future__ import annotations

import os

os.environ.setdefault("DIGILER_DATABASE_URL", "sqlite+aiosqlite:///./test_digiler.db")
os.environ.setdefault("DIGILER_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    # The context manager runs the app lifespan, which creates the DB tables
    # (init_models) — without it every DB-backed request fails with "no such table".
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_root(client):
    assert client.get("/").json()["service"] == "Digiler AI"


def test_auth_flow(client):
    email = "student@example.com"
    reg = client.post("/api/auth/register", json={"email": email, "password": "secret123",
                                                  "name": "Test Student"})
    assert reg.status_code in (201, 409)
    login = client.post("/api/auth/login", data={"username": email, "password": "secret123"})
    assert login.status_code == 200
    tok = login.json()
    assert tok["access_token"] and tok["refresh_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == email
    assert me.json()["role"] == "student" and me.json()["student_id"].startswith("student-")

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]


def test_protected_requires_auth(client):
    # both routes gate on the JWT before any heavy service is built
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/chats").status_code == 401


def test_role_gate_on_mutating_function(client):
    # a mutating function call requires auth (401 without a token)
    assert client.post("/api/functions/call", json={"name": "knowledge_update",
                                                     "arguments": {"source": "x"}}).status_code == 401


def _student_headers(client, email: str) -> dict:
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    tok = client.post("/api/auth/login", data={"username": email, "password": "secret123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_admin_panel_role_gate(client):
    # /admin/users needs no ala services (session + role only) — the gate is testable here.
    assert client.get("/api/admin/users").status_code == 401            # anonymous
    h = _student_headers(client, "gate_admin@example.com")
    assert client.get("/api/admin/users", headers=h).status_code == 403  # student forbidden


def test_instructor_panel_role_gate(client):
    # the role dependency runs before the heavy services dependency, so this short-circuits.
    assert client.get("/api/instructor/students").status_code == 401     # anonymous
    h = _student_headers(client, "gate_inst@example.com")
    assert client.get("/api/instructor/students", headers=h).status_code == 403  # student forbidden


@pytest.mark.skipif(not os.path.exists(os.path.join("..", "data", "graph", "concept_graph.db")),
                    reason="ala corpus not built")
def test_ready_smoke(client):
    r = client.get("/api/ready")
    assert r.status_code == 200 and "retrieval" in r.json()
