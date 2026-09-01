from fastapi.testclient import TestClient

from api.main import app
from api.sessions import get_session

client = TestClient(app)


def test_health():
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_routes_to_hr():
    resp = client.post(
        "/chat",
        json={
            "platform": "test",
            "user_id": "u1",
            "message": "How many employees are on the roster?",
        },
    )

    assert resp.status_code == 200
    assert "hr" in resp.json()["metadata"]["invoked_specialists"]


def test_chat_session_persists_across_calls():
    user_id = "u2"
    client.post(
        "/chat",
        json={
            "platform": "test",
            "user_id": user_id,
            "message": "How many employees are on the roster?",
        },
    )
    client.post(
        "/chat",
        json={
            "platform": "test",
            "user_id": user_id,
            "message": "What's our budget for this expense?",
        },
    )

    session = get_session("test", user_id)
    assert len(session["conversation_history"]) == 2


def test_chat_missing_field_returns_422():
    resp = client.post("/chat", json={"platform": "test", "user_id": "u3"})

    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_chat_error_returns_clean_envelope(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("api.main.run_orchestrator", boom)

    resp = client.post(
        "/chat", json={"platform": "test", "user_id": "u4", "message": "hi"}
    )

    assert resp.status_code == 500
    assert resp.json() == {
        "response": "Something went wrong processing your request.",
        "metadata": {},
    }