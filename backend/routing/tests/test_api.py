import pytest
from rest_framework.test import APIClient

from routing import views
from routing.errors import PlanningError

GOOD = {"origin": "Chicago, IL", "destination": "Denver, CO", "departure": "2026-10-20T14:00:00Z",
        "load_weight_lb": 42000, "checkpoint_spacing": "25"}


@pytest.fixture
def client():
    return APIClient()


def test_health(client):
    assert client.get("/api/health/").json() == {"status": "ok"}


def test_validation_errors(client):
    r = client.post("/api/plan/", {**GOOD, "load_weight_lb": -5}, format="json")
    assert r.status_code == 400 and "load_weight_lb" in r.json()["details"]
    r = client.post("/api/plan/", {**GOOD, "checkpoint_spacing": "7"}, format="json")
    assert r.status_code == 400
    r = client.post("/api/plan/", {"origin": "x"}, format="json")
    assert r.status_code == 400


def test_success_passes_parsed_values(client, monkeypatch):
    seen = {}

    def fake(o, d, dep, load, spacing):
        seen.update(o=o, d=d, dep=dep, load=load, spacing=spacing)
        return {"ok": True}

    monkeypatch.setattr(views, "plan_trip", fake)
    r = client.post("/api/plan/", GOOD, format="json")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert seen["load"] == 42000 and seen["spacing"] == "25" and seen["dep"].tzinfo is not None


def test_planning_error_maps_to_status(client, monkeypatch):
    def boom(*a, **k):
        raise PlanningError("nope", 422)

    monkeypatch.setattr(views, "plan_trip", boom)
    r = client.post("/api/plan/", GOOD, format="json")
    assert r.status_code == 422 and r.json()["error"] == "nope"
