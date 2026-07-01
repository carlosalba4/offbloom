"""Tests para los repositorios de persistencia: UserRepo, ProfileRepo, PlanRepo.

Estructura AAA (Arrange – Act – Assert). Comentarios en español.
Nombres de funciones y variables en inglés.
Ningún test toca offbloom.db; usan la fixture db_session en memoria.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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

# ===========================================================================
# UserRepo
# ===========================================================================


class TestUserRepoCreate:
    def test_create_assigns_non_empty_id(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        user = repo.create("test@example.com")
        db_session.commit()

        # Assert
        assert user.id is not None
        assert len(user.id) > 0

    def test_create_persists_user_to_db(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        user = repo.create("persist@example.com")
        db_session.commit()
        fetched = repo.get_by_id(user.id)

        # Assert
        assert fetched is not None
        assert fetched.id == user.id

    def test_create_normalizes_email_to_lowercase(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        user = repo.create("Foo@Bar.COM")
        db_session.commit()

        # Assert — el email almacenado debe estar en minúsculas
        assert user.email == "foo@bar.com"

    def test_create_stores_password_hash_when_provided(self, db_session):
        # Arrange
        repo = UserRepo(db_session)
        pw_hash = "hashed_password_xyz"

        # Act
        user = repo.create("pw@example.com", password_hash=pw_hash)
        db_session.commit()

        # Assert
        assert user.password_hash == pw_hash

    def test_create_allows_null_password_hash(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        user = repo.create("nopw@example.com", password_hash=None)
        db_session.commit()

        # Assert
        assert user.password_hash is None


class TestUserRepoGetById:
    def test_get_by_id_returns_user(self, db_session):
        # Arrange
        repo = UserRepo(db_session)
        user = repo.create("lookup@example.com")
        db_session.commit()

        # Act
        found = repo.get_by_id(user.id)

        # Assert
        assert found is not None
        assert found.id == user.id

    def test_get_by_id_returns_none_for_unknown_id(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        found = repo.get_by_id("00000000-0000-0000-0000-000000000000")

        # Assert
        assert found is None


class TestUserRepoGetByEmail:
    def test_get_by_email_finds_existing_user(self, db_session):
        # Arrange
        repo = UserRepo(db_session)
        repo.create("alice@example.com")
        db_session.commit()

        # Act
        found = repo.get_by_email("alice@example.com")

        # Assert
        assert found is not None
        assert found.email == "alice@example.com"

    def test_get_by_email_is_case_insensitive(self, db_session):
        # Arrange — guardado con email normalizado pero buscado en mayúsculas
        repo = UserRepo(db_session)
        repo.create("Foo@Bar.COM")
        db_session.commit()

        # Act
        found = repo.get_by_email("FOO@BAR.COM")

        # Assert
        assert found is not None
        assert found.email == "foo@bar.com"

    def test_get_by_email_returns_none_for_unknown_email(self, db_session):
        # Arrange
        repo = UserRepo(db_session)

        # Act
        found = repo.get_by_email("nobody@example.com")

        # Assert
        assert found is None


# ===========================================================================
# ProfileRepo
# ===========================================================================


class TestProfileRepoGetByUserId:
    def test_get_by_user_id_returns_none_when_no_profile_exists(self, db_session):
        # Arrange — usuario sin perfil
        user_repo = UserRepo(db_session)
        user = user_repo.create("noprofile@example.com")
        db_session.commit()
        profile_repo = ProfileRepo(db_session)

        # Act
        result = profile_repo.get_by_user_id(user.id)

        # Assert
        assert result is None


class TestProfileRepoUpsert:
    def _profile_data(self) -> dict:
        """Datos mínimos válidos para upsert."""
        return {
            "goals": ["meditar"],
            "interests": ["yoga"],
            "constraints": {
                "available_minutes": 30,
                "energy": "LOW",
                "place": "HOME",
                "social": "SOLO",
            },
            "lang": "ES",
        }

    def test_upsert_creates_profile_when_not_exists(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("new_profile@example.com")
        db_session.commit()
        repo = ProfileRepo(db_session)
        data = self._profile_data()

        # Act
        profile = repo.upsert(user.id, data)
        db_session.commit()

        # Assert
        assert profile is not None
        assert profile.user_id == user.id
        assert profile.goals == ["meditar"]

    def test_upsert_is_idempotent_does_not_duplicate(self, db_session):
        # Arrange — mismo usuario, dos llamadas a upsert
        user = UserRepo(db_session).create("idempotent@example.com")
        db_session.commit()
        repo = ProfileRepo(db_session)

        # Act
        repo.upsert(user.id, self._profile_data())
        db_session.commit()
        repo.upsert(user.id, {**self._profile_data(), "goals": ["correr"]})
        db_session.commit()

        # Assert — solo debe existir 1 perfil para ese usuario
        from coach.db.models.profile import Profile
        count = db_session.query(Profile).filter(Profile.user_id == user.id).count()
        assert count == 1

    def test_upsert_updates_existing_profile_field(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("update_profile@example.com")
        db_session.commit()
        repo = ProfileRepo(db_session)
        repo.upsert(user.id, self._profile_data())
        db_session.commit()

        # Act — actualizar goals
        repo.upsert(user.id, {**self._profile_data(), "goals": ["correr", "leer"]})
        db_session.commit()
        updated = repo.get_by_user_id(user.id)

        # Assert — el campo debe haber cambiado
        assert updated is not None
        assert updated.goals == ["correr", "leer"]

    def test_upsert_respects_schema_version(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("schemaversion@example.com")
        db_session.commit()
        repo = ProfileRepo(db_session)

        # Act
        profile = repo.upsert(user.id, self._profile_data(), schema_version=3)
        db_session.commit()

        # Assert
        assert profile.schema_version == 3


# ===========================================================================
# PlanRepo
# ===========================================================================


def _make_plan_for_user(user_id: str, created_at: datetime | None = None):
    """Construye un Plan ORM usando el mapper oficial, listo para persistir."""
    profile = make_profile()
    usage = make_usage()
    weekly_plan = WeeklyPlan(
        weekly_focus="Foco semanal de prueba",
        intentions=["Reducir scroll nocturno"],
        swaps=[Swap(habit="Instagram", alternative="Leer 15 min")],
        citations=[Citation(source="Referencia Test", chunk_id=None)],
    )
    state: CoachState = {
        "plan": weekly_plan,
        "activities": [
            CuratedActivity(
                title="Paseo al aire libre",
                reason="Mejora el ánimo",
                why_it_fits="Bajo coste energético",
                duration_min=30,
                energy=EnergyLevel.LOW,
                place=Place.OUTDOORS,
                social=SocialPreference.SOLO,
            )
        ],
    }
    plan = coach_result_to_plan_row(
        result=state,
        user_id=user_id,
        input_profile=profile,
        input_usage=usage,
    )
    if created_at is not None:
        plan.created_at = created_at
    return plan


class TestPlanRepoCreate:
    def test_create_persists_plan(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("planowner@example.com")
        db_session.commit()
        plan = _make_plan_for_user(user.id)
        repo = PlanRepo(db_session)

        # Act
        saved = repo.create(plan)
        db_session.commit()

        # Assert
        assert saved.id is not None
        assert saved.user_id == user.id


class TestPlanRepoGetById:
    def test_get_by_id_returns_plan_for_correct_user(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("getplan@example.com")
        db_session.commit()
        plan = _make_plan_for_user(user.id)
        repo = PlanRepo(db_session)
        saved = repo.create(plan)
        db_session.commit()

        # Act
        found = repo.get_by_id(saved.id, user.id)

        # Assert
        assert found is not None
        assert found.id == saved.id

    def test_get_by_id_returns_none_for_unknown_plan(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("noplans@example.com")
        db_session.commit()
        repo = PlanRepo(db_session)

        # Act
        found = repo.get_by_id("nonexistent-id", user.id)

        # Assert
        assert found is None


class TestPlanRepoListByUser:
    def test_list_by_user_returns_plans_in_desc_order(self, db_session):
        # Arrange — tres planes con fechas distintas creados manualmente
        user = UserRepo(db_session).create("list_order@example.com")
        db_session.commit()
        repo = PlanRepo(db_session)

        now = datetime.now(UTC)
        oldest = _make_plan_for_user(user.id, created_at=now - timedelta(days=2))
        middle = _make_plan_for_user(user.id, created_at=now - timedelta(days=1))
        newest = _make_plan_for_user(user.id, created_at=now)

        # Guardamos en orden no cronológico para probar que el repo ordena correctamente
        for p in [middle, oldest, newest]:
            repo.create(p)
        db_session.commit()

        # Act
        plans = repo.list_by_user(user.id)

        # Assert — el más reciente primero
        assert len(plans) == 3
        assert plans[0].created_at >= plans[1].created_at >= plans[2].created_at

    def test_list_by_user_respects_limit(self, db_session):
        # Arrange — creamos 3 planes
        user = UserRepo(db_session).create("limit_user@example.com")
        db_session.commit()
        repo = PlanRepo(db_session)

        now = datetime.now(UTC)
        for i in range(3):
            repo.create(_make_plan_for_user(user.id, created_at=now - timedelta(days=i)))
        db_session.commit()

        # Act
        plans = repo.list_by_user(user.id, limit=2)

        # Assert
        assert len(plans) == 2

    def test_list_by_user_respects_offset(self, db_session):
        # Arrange — creamos 3 planes
        user = UserRepo(db_session).create("offset_user@example.com")
        db_session.commit()
        repo = PlanRepo(db_session)

        now = datetime.now(UTC)
        ids = []
        for i in range(3):
            p = repo.create(_make_plan_for_user(user.id, created_at=now - timedelta(days=i)))
            ids.append(p.id)
        db_session.commit()

        # Act — saltar el primero (el más reciente)
        all_plans = repo.list_by_user(user.id, limit=20, offset=0)
        paginated = repo.list_by_user(user.id, limit=20, offset=1)

        # Assert — offset=1 omite el primer resultado
        assert len(paginated) == len(all_plans) - 1
        assert paginated[0].id == all_plans[1].id
