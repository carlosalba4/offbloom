"""Tests for POST /coach endpoint.

Covers: normal flow, derivation path, graph error (502), and invalid input (422).
No LLM or Ollama is ever called — all graph invocations are intercepted by
_FakeGraph. The FastAPI lifespan (build_coach_graph) is deliberately NOT
triggered by using TestClient without a context manager.

Structure: Arrange – Act – Assert (AAA) throughout.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from coach.graph.state import (
    Analysis,
    Citation,
    CuratedActivity,
    DerivationMessage,
    EnergyLevel,
    NeedMapping,
    Place,
    ResourceType,
    RetrievedChunk,
    RiskSignal,
    Severity,
    SocialPreference,
    Swap,
    WeeklyPlan,
)
from coach.main import app

# ---------------------------------------------------------------------------
# Sentinel — detect whether app.state.graph existed before the test
# ---------------------------------------------------------------------------

_SENTINEL = object()


# ---------------------------------------------------------------------------
# FakeGraph double
# ---------------------------------------------------------------------------


class _FakeGraph:
    """Minimal graph double: records invocation args and returns/raises on demand."""

    def __init__(
        self,
        *,
        returns: Any = None,
        raises: BaseException | None = None,
    ) -> None:
        self._returns = returns
        self._raises = raises
        self.invoked_with: Any = None

    def invoke(self, state: Any, config: Any = None) -> Any:
        self.invoked_with = state
        if self._raises is not None:
            raise self._raises
        return self._returns


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def graph_client():
    """Factory fixture that injects a _FakeGraph into app.state and yields.

    Usage inside a test::

        def test_something(graph_client):
            client, fake = graph_client(returns={...})
            resp = client.post("/coach", json=payload)

    The previous value of app.state.graph (if any) is restored on teardown.
    TestClient is created WITHOUT entering the async context manager, so the
    lifespan hook (which calls build_coach_graph) is never executed.
    """
    prev = getattr(app.state, "graph", _SENTINEL)

    def _factory(
        *,
        returns: Any = None,
        raises: BaseException | None = None,
    ) -> tuple[TestClient, _FakeGraph]:
        fake = _FakeGraph(returns=returns, raises=raises)
        app.state.graph = fake
        client = TestClient(app)
        return client, fake

    yield _factory

    if prev is _SENTINEL:
        try:
            del app.state.graph
        except AttributeError:
            pass
    else:
        app.state.graph = prev


# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------


def _valid_payload() -> dict[str, Any]:
    """Return a valid CoachRequest JSON dict with all required fields."""
    return {
        "profile": {
            "goals": ["reduce screen time", "sleep better"],
            "interests": ["reading", "hiking"],
            "constraints": {
                "available_minutes": 45,
                "energy": "MEDIUM",
                "place": "HOME",
                "social": "SOLO",
            },
            "lang": "ES",
        },
        "usage": {
            "categories": [
                {"category": "social_media", "minutes_per_day": 120},
                {"category": "streaming", "minutes_per_day": 90},
            ],
            "peak_windows": ["EVENING"],
            "self_reported_triggers": ["boredom", "stress"],
        },
    }


def _normal_graph_state() -> dict[str, Any]:
    """Return a realistic CoachState dict as if the full graph completed successfully.

    Intentionally includes internal channels (analysis, risk, retrieved) to verify
    that the endpoint strips them from the public response.
    """
    plan = WeeklyPlan(
        weekly_focus="Reducir el uso de redes sociales",
        intentions=["No abrir Instagram antes del mediodía"],
        swaps=[Swap(habit="scroll nocturno", alternative="lectura 20 minutos")],
        citations=[Citation(source="Estudio bienestar digital 2023", chunk_id="chunk-001")],
    )
    activities = [
        CuratedActivity(
            title="Lectura antes de dormir",
            reason="Sustituye el scroll nocturno por una actividad relajante",
            why_it_fits="Encaja con tu tiempo disponible y preferencia en casa",
            replaces="scroll nocturno",
            source="Recomendación RAG",
            duration_min=20,
            energy=EnergyLevel.LOW,
            place=Place.HOME,
            social=SocialPreference.SOLO,
        )
    ]
    # Internal channels — must NOT appear in CoachResponse
    analysis = Analysis(
        patterns=["uso intensivo tarde-noche"],
        triggers=["aburrimiento"],
        needs_covered=[NeedMapping(use="Instagram", need="conexión social")],
    )
    risk = RiskSignal(flag=False, severity=Severity.NONE)
    retrieved = [
        RetrievedChunk(
            id="chunk-001",
            text="El uso excesivo de redes sociales se asocia con peor calidad del sueño.",
            category="digital_wellbeing",
            source="Estudio bienestar digital 2023",
        )
    ]
    return {
        "plan": plan,
        "activities": activities,
        "analysis": analysis,
        "risk": risk,
        "retrieved": retrieved,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# 1. Normal flow — plan and activities returned, internal channels hidden
# ---------------------------------------------------------------------------


def test_normal_flow_returns_200_with_plan_and_activities(graph_client) -> None:
    # Arrange
    client, _ = graph_client(returns=_normal_graph_state())
    payload = _valid_payload()

    # Act
    resp = client.post("/coach", json=payload)

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] is not None
    assert body["plan"]["weekly_focus"] != ""
    assert len(body["activities"]) > 0


def test_normal_flow_does_not_expose_internal_graph_channels(graph_client) -> None:
    # Arrange — graph returns state that includes internal-only channels
    client, _ = graph_client(returns=_normal_graph_state())
    payload = _valid_payload()

    # Act
    resp = client.post("/coach", json=payload)

    # Assert — internal channels must be absent from the public JSON body
    body = resp.json()
    assert "analysis" not in body
    assert "risk" not in body
    assert "retrieved" not in body


# ---------------------------------------------------------------------------
# 2. Derivation path — safety gate triggered; plan is None, derivation populated
# ---------------------------------------------------------------------------


def test_derivation_path_returns_200_with_derivation_populated_and_plan_none(
    graph_client,
) -> None:
    # Arrange
    derivation_msg = DerivationMessage(
        message="Gracias por compartir esto. Te recomendamos hablar con un profesional.",
        resource_type=ResourceType.MENTAL_HEALTH,
    )
    client, _ = graph_client(
        returns={"derivation": derivation_msg, "activities": [], "errors": []}
    )
    payload = _valid_payload()

    # Act
    resp = client.post("/coach", json=payload)

    # Assert — derivation is a valid HTTP 200; the client distinguishes via derivation != null
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] is None
    assert body["derivation"] is not None
    assert body["derivation"]["resource_type"] == "MENTAL_HEALTH"
    assert body["derivation"]["message"] != ""


# ---------------------------------------------------------------------------
# 3. Graph error → 502 with a safe public message; no internal leakage
# ---------------------------------------------------------------------------


def test_graph_error_returns_502_with_safe_detail_no_internal_leakage(
    graph_client,
) -> None:
    # Arrange — simulate an internal graph failure with sensitive info in the message
    client, _ = graph_client(
        raises=RuntimeError("ollama timeout en _internal_node:secreto")
    )
    payload = _valid_payload()

    # Act
    resp = client.post("/coach", json=payload)

    # Assert
    assert resp.status_code == 502
    detail: str = resp.json()["detail"]
    assert detail == "El coach no pudo procesar la petición. Inténtalo de nuevo."
    # Sensitive internal details must never reach the caller
    assert "ollama" not in detail
    assert "_internal_node" not in detail
    assert "secreto" not in detail


# ---------------------------------------------------------------------------
# 4. Invalid input → 422 (Pydantic / FastAPI validation before handler runs)
# ---------------------------------------------------------------------------


def test_invalid_enum_value_in_constraints_returns_422(graph_client) -> None:
    # Arrange — "SUPER" is not a valid EnergyLevel value
    payload = _valid_payload()
    payload["profile"]["constraints"]["energy"] = "SUPER"
    # Graph is configured but will never be reached; validation fires first
    client, _ = graph_client(returns=None)

    # Act
    resp = client.post("/coach", json=payload)

    # Assert
    assert resp.status_code == 422


def test_extra_field_forbidden_in_profile_returns_422(graph_client) -> None:
    # Arrange — UserProfile has extra="forbid"; injecting an unknown field triggers 422
    payload = _valid_payload()
    payload["profile"]["unknown_field"] = "should_be_rejected"
    client, _ = graph_client(returns=None)

    # Act
    resp = client.post("/coach", json=payload)

    # Assert
    assert resp.status_code == 422
