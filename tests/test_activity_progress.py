"""Tests del progreso de actividades: PUT .../progress y su reflejo en GET /plans/{id}.

Cubre: persistencia del marcado, alternancia true->false, idempotencia (una sola
fila por (plan_id, activity_index)), aislamiento entre usuarios (404, nunca 403),
activity_index fuera de rango y acceso sin token. No se invoca el grafo del
coach: las filas Plan se insertan directamente en la sesión de test.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from coach.db.enums import ActivityProgressStatus, PlanStatus
from coach.db.models.activity_progress import ActivityProgress
from coach.db.models.plan import Plan
from coach.db.models.user import User
from tests.conftest import auth_headers, make_profile, make_usage


def _get_user_id(db_session: Session, email: str) -> str:
    """Recupera el id del usuario ya autenticado a partir de su email."""
    user = db_session.query(User).filter(User.email == email.lower()).first()
    assert user is not None
    return user.id


def _make_plan_with_activities(user_id: str, count: int = 3) -> Plan:
    """Construye una fila Plan GENERATED con `count` actividades conocidas.

    Las actividades tienen la forma de CuratedActivity serializada, que es lo
    que el mapper espera al reconstruirlas desde el snapshot JSON.
    """
    return Plan(
        user_id=user_id,
        status=PlanStatus.GENERATED,
        input_profile_snapshot=make_profile().model_dump(mode="json"),
        input_usage_snapshot=make_usage().model_dump(mode="json"),
        plan={
            "weekly_focus": "Reducir el uso de redes sociales",
            "intentions": ["No abrir Instagram antes del mediodía"],
            "swaps": [],
            "citations": [],
        },
        activities=[
            {
                "title": f"Actividad {i}",
                "reason": "Sustituye un rato de scroll",
                "why_it_fits": "Encaja con el tiempo disponible",
            }
            for i in range(count)
        ],
        derivation=None,
        errors=[],
        created_at=datetime.now(UTC),
    )


def _seed_plan(db_session: Session, user_id: str, count: int = 3) -> Plan:
    """Inserta y refresca un Plan con actividades para el usuario indicado."""
    plan_row = _make_plan_with_activities(user_id, count)
    db_session.add(plan_row)
    db_session.commit()
    db_session.refresh(plan_row)
    return plan_row


class TestSetActivityProgress:
    def test_mark_activity_done_persists_and_is_reflected_in_plan_detail(self, client, db_session):
        # Arrange
        headers = auth_headers(client, email="progress-done@example.com")
        user_id = _get_user_id(db_session, "progress-done@example.com")
        plan_row = _seed_plan(db_session, user_id)

        # Act
        put_resp = client.put(
            f"/plans/{plan_row.id}/activities/1/progress",
            json={"done": True},
            headers=headers,
        )

        # Assert — la respuesta del PUT trae el estado resultante
        assert put_resp.status_code == 200
        assert put_resp.json() == {"activity_index": 1, "done": True}

        # Assert — el detalle del plan refleja done solo en la actividad marcada
        get_resp = client.get(f"/plans/{plan_row.id}", headers=headers)
        assert get_resp.status_code == 200
        activities = get_resp.json()["activities"]
        assert [activity["done"] for activity in activities] == [False, True, False]
        # El contrato previo de la actividad se mantiene intacto
        assert activities[1]["title"] == "Actividad 1"

    def test_toggling_done_back_to_false_is_reflected_in_plan_detail(self, client, db_session):
        # Arrange — la actividad 0 ya está marcada como hecha
        headers = auth_headers(client, email="progress-toggle@example.com")
        user_id = _get_user_id(db_session, "progress-toggle@example.com")
        plan_row = _seed_plan(db_session, user_id)
        client.put(
            f"/plans/{plan_row.id}/activities/0/progress",
            json={"done": True},
            headers=headers,
        )

        # Act — se desmarca
        put_resp = client.put(
            f"/plans/{plan_row.id}/activities/0/progress",
            json={"done": False},
            headers=headers,
        )

        # Assert
        assert put_resp.status_code == 200
        assert put_resp.json() == {"activity_index": 0, "done": False}

        get_resp = client.get(f"/plans/{plan_row.id}", headers=headers)
        assert [activity["done"] for activity in get_resp.json()["activities"]] == [
            False,
            False,
            False,
        ]

        # Assert — la fila sigue existiendo, ahora en PENDING (no se borra)
        rows = db_session.query(ActivityProgress).filter_by(plan_id=plan_row.id).all()
        assert len(rows) == 1
        assert rows[0].status is ActivityProgressStatus.PENDING

    def test_marking_the_same_activity_twice_is_idempotent(self, client, db_session):
        # Arrange
        headers = auth_headers(client, email="progress-idempotent@example.com")
        user_id = _get_user_id(db_session, "progress-idempotent@example.com")
        plan_row = _seed_plan(db_session, user_id)

        # Act — mismo body dos veces
        first = client.put(
            f"/plans/{plan_row.id}/activities/2/progress",
            json={"done": True},
            headers=headers,
        )
        second = client.put(
            f"/plans/{plan_row.id}/activities/2/progress",
            json={"done": True},
            headers=headers,
        )

        # Assert — mismo resultado y una sola fila persistida
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == {"activity_index": 2, "done": True}

        rows = db_session.query(ActivityProgress).filter_by(plan_id=plan_row.id).all()
        assert len(rows) == 1
        assert rows[0].activity_index == 2
        assert rows[0].status is ActivityProgressStatus.DONE

        get_resp = client.get(f"/plans/{plan_row.id}", headers=headers)
        assert get_resp.json()["activities"][2]["done"] is True


class TestSetActivityProgressErrors:
    def test_progress_on_another_users_plan_returns_404(self, client, db_session):
        # Arrange — el plan pertenece a B; A intenta marcar una actividad
        headers_a = auth_headers(client, email="progress-isolation-a@example.com")
        auth_headers(client, email="progress-isolation-b@example.com")
        user_b_id = _get_user_id(db_session, "progress-isolation-b@example.com")
        plan_row = _seed_plan(db_session, user_b_id)

        # Act
        resp = client.put(
            f"/plans/{plan_row.id}/activities/0/progress",
            json={"done": True},
            headers=headers_a,
        )

        # Assert — 404, nunca 403, y sin efectos secundarios en la DB
        assert resp.status_code == 404
        assert db_session.query(ActivityProgress).count() == 0

    def test_progress_with_nonexistent_plan_returns_404(self, client):
        # Arrange
        headers = auth_headers(client, email="progress-missing-plan@example.com")

        # Act
        resp = client.put(
            "/plans/id-que-no-existe/activities/0/progress",
            json={"done": True},
            headers=headers,
        )

        # Assert
        assert resp.status_code == 404

    def test_progress_with_out_of_range_activity_index_returns_404(self, client, db_session):
        # Arrange — el plan solo tiene 3 actividades (índices 0..2)
        headers = auth_headers(client, email="progress-range@example.com")
        user_id = _get_user_id(db_session, "progress-range@example.com")
        plan_row = _seed_plan(db_session, user_id, count=3)

        # Act
        resp = client.put(
            f"/plans/{plan_row.id}/activities/3/progress",
            json={"done": True},
            headers=headers,
        )

        # Assert
        assert resp.status_code == 404
        assert resp.json()["detail"] == "activity_index fuera de rango"
        assert db_session.query(ActivityProgress).count() == 0


class TestActivityProgressAuthRequired:
    def test_progress_without_token_returns_401(self, client):
        # Act
        resp = client.put("/plans/some-id/activities/0/progress", json={"done": True})

        # Assert
        assert resp.status_code == 401
