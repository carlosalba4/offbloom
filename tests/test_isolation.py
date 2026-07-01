"""Tests de aislamiento entre usuarios — SEGURIDAD BLOQUEANTE.

Garantizan que un usuario no puede ver ni acceder a los recursos de otro.
ADR-007: toda query autenticada filtra por user_id; un recurso ajeno → None.

Estructura AAA. Comentarios en español, nombres en inglés.
"""

from __future__ import annotations

from coach.db.mappers import coach_result_to_plan_row
from coach.db.repositories import PlanRepo, ProfileRepo, UserRepo
from coach.graph.state import (
    Citation,
    CoachState,
    CuratedActivity,
    EnergyLevel,
    Place,
    SocialPreference,
    Swap,
    WeeklyPlan,
)
from tests.conftest import make_profile, make_usage

# ---------------------------------------------------------------------------
# Helpers locales
# ---------------------------------------------------------------------------


def _create_user(db_session, email: str):
    """Crea y persiste un usuario; devuelve la entidad ORM."""
    user = UserRepo(db_session).create(email)
    db_session.commit()
    return user


def _create_plan_for_user(db_session, user_id: str):
    """Crea un Plan GENERATED para el usuario dado y lo persiste."""
    state: CoachState = {
        "plan": WeeklyPlan(
            weekly_focus="Foco de prueba",
            intentions=["Intención de prueba"],
            swaps=[Swap(habit="TikTok", alternative="Caminar")],
            citations=[Citation(source="Fuente test", chunk_id=None)],
        ),
        "activities": [
            CuratedActivity(
                title="Actividad aislamiento",
                reason="Prueba de aislamiento",
                why_it_fits="Encaja con el perfil de prueba",
                energy=EnergyLevel.LOW,
                place=Place.HOME,
                social=SocialPreference.SOLO,
            )
        ],
    }
    plan_orm = coach_result_to_plan_row(
        result=state,
        user_id=user_id,
        input_profile=make_profile(),
        input_usage=make_usage(),
    )
    repo = PlanRepo(db_session)
    saved = repo.create(plan_orm)
    db_session.commit()
    return saved


def _create_profile_for_user(db_session, user_id: str):
    """Crea un perfil mínimo para el usuario dado."""
    data = {
        "goals": ["objetivo aislamiento"],
        "interests": ["interés aislamiento"],
        "constraints": {
            "available_minutes": 20,
            "energy": "LOW",
            "place": "HOME",
            "social": "SOLO",
        },
        "lang": "ES",
    }
    profile = ProfileRepo(db_session).upsert(user_id, data)
    db_session.commit()
    return profile


# ===========================================================================
# Tests de aislamiento de planes
# ===========================================================================


class TestPlanIsolation:
    def test_get_plan_of_user_a_with_user_b_id_returns_none(self, db_session):
        # Arrange — dos usuarios y un plan solo para A
        user_a = _create_user(db_session, "user_a@example.com")
        user_b = _create_user(db_session, "user_b@example.com")
        plan_a = _create_plan_for_user(db_session, user_a.id)
        repo = PlanRepo(db_session)

        # Act — B intenta acceder al plan de A
        result = repo.get_by_id(plan_a.id, user_id=user_b.id)

        # Assert — debe recibir None (nunca 403, sino 404 transparente)
        assert result is None

    def test_get_plan_of_user_a_with_user_a_id_returns_plan(self, db_session):
        # Arrange — control positivo: A accede a su propio plan
        user_a = _create_user(db_session, "user_a_pos@example.com")
        plan_a = _create_plan_for_user(db_session, user_a.id)
        repo = PlanRepo(db_session)

        # Act
        result = repo.get_by_id(plan_a.id, user_id=user_a.id)

        # Assert
        assert result is not None
        assert result.id == plan_a.id

    def test_list_plans_of_user_b_does_not_include_plans_of_user_a(self, db_session):
        # Arrange — A y B tienen planes propios
        user_a = _create_user(db_session, "user_a_list@example.com")
        user_b = _create_user(db_session, "user_b_list@example.com")
        plan_a = _create_plan_for_user(db_session, user_a.id)
        _create_plan_for_user(db_session, user_b.id)
        repo = PlanRepo(db_session)

        # Act — listar planes de B
        plans_of_b = repo.list_by_user(user_b.id)
        ids_of_b = {p.id for p in plans_of_b}

        # Assert — el plan de A no aparece en la lista de B
        assert plan_a.id not in ids_of_b

    def test_each_user_sees_exactly_their_own_plans(self, db_session):
        # Arrange — A tiene 2 planes, B tiene 1
        user_a = _create_user(db_session, "a_exact@example.com")
        user_b = _create_user(db_session, "b_exact@example.com")
        plan_a1 = _create_plan_for_user(db_session, user_a.id)
        plan_a2 = _create_plan_for_user(db_session, user_a.id)
        plan_b1 = _create_plan_for_user(db_session, user_b.id)
        repo = PlanRepo(db_session)

        # Act
        plans_a = repo.list_by_user(user_a.id)
        plans_b = repo.list_by_user(user_b.id)

        # Assert
        assert {p.id for p in plans_a} == {plan_a1.id, plan_a2.id}
        assert {p.id for p in plans_b} == {plan_b1.id}


# ===========================================================================
# Tests de aislamiento de perfiles
# ===========================================================================


class TestProfileIsolation:
    def test_get_profile_of_user_a_with_user_b_id_returns_none(self, db_session):
        # Arrange — A tiene perfil, B no
        user_a = _create_user(db_session, "profile_a@example.com")
        user_b = _create_user(db_session, "profile_b@example.com")
        _create_profile_for_user(db_session, user_a.id)
        repo = ProfileRepo(db_session)

        # Act — B intenta obtener su propio perfil (no el de A)
        profile_b = repo.get_by_user_id(user_b.id)

        # Assert — B no debe ver el perfil de A
        assert profile_b is None

    def test_get_profile_returns_correct_owner(self, db_session):
        # Arrange — ambos usuarios con perfil propio
        user_a = _create_user(db_session, "profile_a_own@example.com")
        user_b = _create_user(db_session, "profile_b_own@example.com")
        _create_profile_for_user(db_session, user_a.id)
        _create_profile_for_user(db_session, user_b.id)
        repo = ProfileRepo(db_session)

        # Act
        profile_a = repo.get_by_user_id(user_a.id)
        profile_b = repo.get_by_user_id(user_b.id)

        # Assert — cada usuario obtiene su propio perfil
        assert profile_a is not None
        assert profile_a.user_id == user_a.id
        assert profile_b is not None
        assert profile_b.user_id == user_b.id
        assert profile_a.id != profile_b.id
