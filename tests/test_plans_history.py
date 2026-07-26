"""Tests para el historial de planes: GET /plans y GET /plans/{id}.

Cubre: listado propio ordenado por fecha descendente, aislamiento entre
usuarios, forma de PlanSummary (sin plan/activities completos), cálculo de
`focus` según status, obtención de detalle completo, aislamiento en el
detalle (404, nunca 403), 404 con id inexistente, 401 sin token y paginación
(limit/offset). No se invoca el grafo del coach: las filas Plan se insertan
directamente en la sesión de test.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from coach.db.enums import PlanStatus
from coach.db.models.plan import Plan
from coach.db.models.user import User
from tests.conftest import auth_headers, make_profile, make_usage


def _get_user_id(db_session: Session, email: str) -> str:
    """Recupera el id del usuario ya autenticado a partir de su email."""
    user = db_session.query(User).filter(User.email == email.lower()).first()
    assert user is not None
    return user.id


def _make_generated_plan(
    user_id: str,
    created_at: datetime,
    weekly_focus: str = "Reducir el uso de redes sociales",
) -> Plan:
    """Construye una fila Plan GENERATED lista para insertar directamente en la sesión."""
    return Plan(
        user_id=user_id,
        status=PlanStatus.GENERATED,
        input_profile_snapshot=make_profile().model_dump(mode="json"),
        input_usage_snapshot=make_usage().model_dump(mode="json"),
        plan={
            "weekly_focus": weekly_focus,
            "intentions": ["No abrir Instagram antes del mediodía"],
            "swaps": [],
            "citations": [],
        },
        activities=[],
        derivation=None,
        errors=[],
        created_at=created_at,
    )


def _make_derived_plan(user_id: str, created_at: datetime) -> Plan:
    """Construye una fila Plan DERIVED (sin plan/activities) lista para insertar."""
    return Plan(
        user_id=user_id,
        status=PlanStatus.DERIVED,
        input_profile_snapshot=make_profile().model_dump(mode="json"),
        input_usage_snapshot=make_usage().model_dump(mode="json"),
        plan=None,
        activities=None,
        derivation={
            "message": "Gracias por compartir esto. Te recomendamos hablar con un profesional.",
            "resource_type": "MENTAL_HEALTH",
        },
        errors=[],
        created_at=created_at,
    )


class TestListPlansOwnershipAndOrder:
    def test_list_plans_returns_only_own_plans_ordered_by_created_at_desc(self, client, db_session):
        # Arrange — dos usuarios; A tiene tres planes con timestamps distintos, B tiene uno
        headers_a = auth_headers(client, email="history-a@example.com")
        headers_b = auth_headers(client, email="history-b@example.com")
        user_a_id = _get_user_id(db_session, "history-a@example.com")
        user_b_id = _get_user_id(db_session, "history-b@example.com")

        now = datetime.now(UTC)
        oldest = _make_generated_plan(user_a_id, now - timedelta(days=2), weekly_focus="foco-1")
        middle = _make_generated_plan(user_a_id, now - timedelta(days=1), weekly_focus="foco-2")
        newest = _make_generated_plan(user_a_id, now, weekly_focus="foco-3")
        other_user_plan = _make_generated_plan(user_b_id, now, weekly_focus="foco-ajeno")
        db_session.add_all([oldest, middle, newest, other_user_plan])
        db_session.commit()

        # Act
        resp = client.get("/plans", headers=headers_a)

        # Assert — solo los 3 planes de A, en orden descendente por fecha
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3
        assert [item["focus"] for item in body] == ["foco-3", "foco-2", "foco-1"]
        for item in body:
            assert set(item.keys()) == {"id", "status", "created_at", "focus"}
            assert "plan" not in item
            assert "activities" not in item

        # Assert — el plan del otro usuario nunca aparece
        assert not any(item["focus"] == "foco-ajeno" for item in body)

        # Sanity check adicional del header b (no interfiere en el listado de A)
        resp_b = client.get("/plans", headers=headers_b)
        assert resp_b.status_code == 200
        assert len(resp_b.json()) == 1

    def test_list_plans_focus_is_none_for_derived_and_present_for_generated(
        self, client, db_session
    ):
        # Arrange
        headers = auth_headers(client, email="history-focus@example.com")
        user_id = _get_user_id(db_session, "history-focus@example.com")
        now = datetime.now(UTC)
        generated = _make_generated_plan(user_id, now - timedelta(hours=1), weekly_focus="mi-foco")
        derived = _make_derived_plan(user_id, now)
        db_session.add_all([generated, derived])
        db_session.commit()

        # Act
        resp = client.get("/plans", headers=headers)

        # Assert
        assert resp.status_code == 200
        body = resp.json()
        by_status = {item["status"]: item for item in body}
        assert by_status["GENERATED"]["focus"] == "mi-foco"
        assert by_status["DERIVED"]["focus"] is None


class TestGetPlanDetail:
    def test_get_plan_detail_returns_full_plan_response_shape(self, client, db_session):
        # Arrange
        headers = auth_headers(client, email="history-detail@example.com")
        user_id = _get_user_id(db_session, "history-detail@example.com")
        plan_row = _make_generated_plan(user_id, datetime.now(UTC), weekly_focus="foco-detalle")
        db_session.add(plan_row)
        db_session.commit()
        db_session.refresh(plan_row)

        # Act
        resp = client.get(f"/plans/{plan_row.id}", headers=headers)

        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == plan_row.id
        assert body["status"] == "GENERATED"
        assert body["plan"]["weekly_focus"] == "foco-detalle"
        assert body["activities"] == []
        assert body["derivation"] is None
        assert set(body.keys()) == {
            "id",
            "status",
            "created_at",
            "plan",
            "activities",
            "derivation",
            "errors",
        }

    def test_get_plan_detail_of_another_user_returns_404(self, client, db_session):
        # Arrange — el plan pertenece a B; A intenta acceder a él
        headers_a = auth_headers(client, email="isolation-a@example.com")
        auth_headers(client, email="isolation-b@example.com")
        user_b_id = _get_user_id(db_session, "isolation-b@example.com")
        plan_row = _make_derived_plan(user_b_id, datetime.now(UTC))
        db_session.add(plan_row)
        db_session.commit()
        db_session.refresh(plan_row)

        # Act
        resp = client.get(f"/plans/{plan_row.id}", headers=headers_a)

        # Assert — 404, nunca 403, para no revelar la existencia del recurso ajeno
        assert resp.status_code == 404

    def test_get_plan_detail_with_nonexistent_id_returns_404(self, client):
        # Arrange
        headers = auth_headers(client, email="history-missing@example.com")

        # Act
        resp = client.get("/plans/id-que-no-existe", headers=headers)

        # Assert
        assert resp.status_code == 404


class TestPlansHistoryAuthRequired:
    def test_list_plans_without_token_returns_401(self, client):
        # Act
        resp = client.get("/plans")

        # Assert
        assert resp.status_code == 401

    def test_get_plan_detail_without_token_returns_401(self, client):
        # Act
        resp = client.get("/plans/some-id")

        # Assert
        assert resp.status_code == 401


class TestListPlansPagination:
    def test_list_plans_limit_and_offset_slice_the_results(self, client, db_session):
        # Arrange — cinco planes con timestamps crecientes
        headers = auth_headers(client, email="history-pagination@example.com")
        user_id = _get_user_id(db_session, "history-pagination@example.com")
        now = datetime.now(UTC)
        plans = [
            _make_generated_plan(user_id, now - timedelta(minutes=i), weekly_focus=f"foco-{i}")
            for i in range(5, 0, -1)
        ]
        db_session.add_all(plans)
        db_session.commit()

        # Act — página de 2 elementos saltando el primero
        resp = client.get("/plans?limit=2&offset=1", headers=headers)

        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        # Orden descendente completo: foco-1, foco-2, foco-3, foco-4, foco-5
        # offset=1 salta foco-1, limit=2 se queda con foco-2 y foco-3
        assert [item["focus"] for item in body] == ["foco-2", "foco-3"]
