"""Tests para POST /plans (check-in autenticado, persiste un Plan).

Cubre: flujo normal (201, persiste GENERATED), sin perfil (404), sin token
(401), derivación (persiste DERIVED, sin filtrar el RiskSignal interno) y
aislamiento entre usuarios. El grafo siempre se mockea con _FakeGraph — nunca
se llama a Ollama ni a un LLM real.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from typing import Any

from coach.db.enums import PlanStatus
from coach.db.models.plan import Plan
from coach.db.models.user import User
from coach.db.repositories import PlanRepo
from coach.graph.state import (
    Citation,
    CuratedActivity,
    DerivationMessage,
    EnergyLevel,
    Place,
    ResourceType,
    RiskSignal,
    Severity,
    SocialPreference,
    Swap,
    WeeklyPlan,
)
from tests.conftest import auth_headers, make_profile, make_usage


def _usage_payload() -> dict[str, Any]:
    return make_usage().model_dump(mode="json")


def _save_profile(client, headers: dict[str, str]) -> None:
    """Guarda un perfil válido para el usuario autenticado (precondición de /plans)."""
    payload = make_profile().model_dump(mode="json")
    resp = client.put("/me/profile", json=payload, headers=headers)
    assert resp.status_code == 200


def _normal_graph_state() -> dict[str, Any]:
    """CoachState realista de un check-in exitoso, con canales internos incluidos.

    analysis/risk/retrieved deben persistirse solo indirectamente (risk nunca)
    y no deben filtrarse en la respuesta pública.
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
    return {
        "plan": plan,
        "activities": activities,
        "risk": RiskSignal(flag=False, severity=Severity.NONE),
        "errors": [],
    }


class TestCreatePlanNormalFlow:
    def test_post_plans_with_profile_returns_201_and_persists_generated_plan(
        self, client, graph_client, db_session
    ):
        # Arrange
        headers = auth_headers(client, email="checkin@example.com")
        _save_profile(client, headers)
        graph_client(returns=_normal_graph_state())

        # Act
        resp = client.post("/plans", json={"usage": _usage_payload()}, headers=headers)

        # Assert — respuesta pública
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "GENERATED"
        assert body["plan"] is not None
        assert body["plan"]["weekly_focus"] != ""
        assert len(body["activities"]) > 0
        assert body["derivation"] is None
        assert "id" in body and "created_at" in body

        # Assert — se ha persistido una fila Plan asociada al usuario
        rows = db_session.query(Plan).all()
        assert len(rows) == 1
        assert rows[0].status == PlanStatus.GENERATED
        assert rows[0].id == body["id"]

    def test_post_plans_without_profile_returns_404(self, client, graph_client):
        # Arrange
        headers = auth_headers(client, email="no-profile@example.com")
        graph_client(returns=_normal_graph_state())

        # Act
        resp = client.post("/plans", json={"usage": _usage_payload()}, headers=headers)

        # Assert
        assert resp.status_code == 404

    def test_post_plans_without_token_returns_401(self, client, graph_client):
        # Arrange
        graph_client(returns=_normal_graph_state())

        # Act
        resp = client.post("/plans", json={"usage": _usage_payload()})

        # Assert
        assert resp.status_code == 401


class TestCreatePlanDerivation:
    def test_post_plans_derivation_persists_derived_and_hides_risk_internals(
        self, client, graph_client, db_session
    ):
        # Arrange — el grafo devuelve derivation poblado Y risk interno presente
        headers = auth_headers(client, email="derivation@example.com")
        _save_profile(client, headers)
        derivation_msg = DerivationMessage(
            message="Gracias por compartir esto. Te recomendamos hablar con un profesional.",
            resource_type=ResourceType.MENTAL_HEALTH,
        )
        internal_risk = RiskSignal(
            flag=True, reason="motivo sensible interno", severity=Severity.HIGH
        )
        graph_client(
            returns={
                "derivation": derivation_msg,
                "activities": [],
                "risk": internal_risk,
                "errors": [],
            }
        )

        # Act
        resp = client.post("/plans", json={"usage": _usage_payload()}, headers=headers)

        # Assert — respuesta pública
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "DERIVED"
        assert body["plan"] is None
        assert body["activities"] == []
        assert body["derivation"] is not None
        assert body["derivation"]["resource_type"] == "MENTAL_HEALTH"
        assert "risk" not in body

        # Assert — en DB: status DERIVED, plan/activities None, derivation solo el mensaje
        rows = db_session.query(Plan).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == PlanStatus.DERIVED
        assert row.plan is None
        assert row.activities is None
        assert row.derivation == {
            "message": derivation_msg.message,
            "resource_type": "MENTAL_HEALTH",
        }


class TestCreatePlanIsolation:
    def test_plan_created_by_user_a_is_not_visible_under_user_b(
        self, client, graph_client, db_session
    ):
        # Arrange — dos usuarios, cada uno con su propio perfil
        headers_a = auth_headers(client, email="user-a@example.com")
        headers_b = auth_headers(client, email="user-b@example.com")
        _save_profile(client, headers_a)
        _save_profile(client, headers_b)
        graph_client(returns=_normal_graph_state())

        # Act — solo A crea un plan
        resp = client.post("/plans", json={"usage": _usage_payload()}, headers=headers_a)
        assert resp.status_code == 201
        plan_id = resp.json()["id"]

        # Assert — el plan de A no es accesible bajo el user_id de B
        user_b = db_session.query(User).filter(User.email == "user-b@example.com").first()
        assert user_b is not None

        cross_lookup = PlanRepo(db_session).get_by_id(plan_id, user_b.id)
        assert cross_lookup is None
