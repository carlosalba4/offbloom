"""Tests para los mappers ORM <-> dominio Pydantic.

Los mappers son funciones puras sin efectos secundarios, salvo el round-trip de
perfil que necesita ProfileRepo.upsert y una sesión de DB.

Estructura AAA. Comentarios en español, nombres en inglés.
"""

from __future__ import annotations

import json

from coach.db.enums import PlanStatus
from coach.db.mappers import (
    coach_result_to_plan_row,
    domain_to_profile_dict,
    plan_row_to_activities,
    plan_row_to_derivation,
    plan_row_to_weekly_plan,
    profile_to_domain,
)
from coach.db.repositories import ProfileRepo, UserRepo
from coach.graph.state import (
    Citation,
    CoachState,
    Constraints,
    CuratedActivity,
    DerivationMessage,
    EnergyLevel,
    Lang,
    Place,
    ResourceType,
    RiskSignal,
    Severity,
    SocialPreference,
    Swap,
    UserProfile,
    WeeklyPlan,
)
from tests.conftest import make_profile, make_usage

# ---------------------------------------------------------------------------
# Helpers locales
# ---------------------------------------------------------------------------


def _constraints() -> Constraints:
    return Constraints(
        available_minutes=60,
        energy=EnergyLevel.HIGH,
        place=Place.OUTDOORS,
        social=SocialPreference.WITH_OTHERS,
    )


def _full_profile() -> UserProfile:
    return UserProfile(
        goals=["meditar", "correr"],
        interests=["naturaleza", "música"],
        constraints=_constraints(),
        lang=Lang.EN,
    )


def _weekly_plan() -> WeeklyPlan:
    return WeeklyPlan(
        weekly_focus="Desconexión digital",
        intentions=["No usar el móvil al despertar", "Leer 20 min antes de dormir"],
        swaps=[Swap(habit="Instagram", alternative="Diario")],
        citations=[Citation(source="Digital Minimalism", chunk_id="c1")],
    )


def _activities() -> list[CuratedActivity]:
    return [
        CuratedActivity(
            title="Yoga matutino",
            reason="Reduce ansiedad",
            why_it_fits="Encaja con el nivel de energía alto",
            duration_min=30,
            energy=EnergyLevel.MEDIUM,
            place=Place.HOME,
            social=SocialPreference.SOLO,
        ),
        CuratedActivity(
            title="Paseo en bici",
            reason="Ejercicio al aire libre",
            why_it_fits="Preferencia por exterior",
            duration_min=45,
            energy=EnergyLevel.HIGH,
            place=Place.OUTDOORS,
            social=SocialPreference.ANY,
        ),
    ]


# ===========================================================================
# Round-trip Profile <-> UserProfile
# ===========================================================================


class TestProfileRoundTrip:
    def test_domain_to_profile_dict_returns_four_expected_keys(self):
        # Arrange
        profile = _full_profile()

        # Act
        result = domain_to_profile_dict(profile)

        # Assert — exactamente las 4 claves que ProfileRepo.upsert espera
        assert set(result.keys()) == {"goals", "interests", "constraints", "lang"}

    def test_round_trip_profile_to_domain_equals_original(self, db_session):
        # Arrange — crear usuario y persistir perfil vía repo
        user = UserRepo(db_session).create("roundtrip@example.com")
        db_session.commit()
        original = _full_profile()
        data = domain_to_profile_dict(original)
        profile_orm = ProfileRepo(db_session).upsert(user.id, data)
        db_session.commit()

        # Act
        reconstructed = profile_to_domain(profile_orm)

        # Assert — igualdad completa incluyendo constraints anidado
        assert reconstructed == original

    def test_round_trip_preserves_nested_constraints(self, db_session):
        # Arrange
        user = UserRepo(db_session).create("constraints_rt@example.com")
        db_session.commit()
        original = _full_profile()
        data = domain_to_profile_dict(original)
        profile_orm = ProfileRepo(db_session).upsert(user.id, data)
        db_session.commit()

        # Act
        reconstructed = profile_to_domain(profile_orm)

        # Assert — los campos de constraints sobreviven al viaje de ida y vuelta
        assert reconstructed.constraints.available_minutes == original.constraints.available_minutes
        assert reconstructed.constraints.energy == original.constraints.energy
        assert reconstructed.constraints.place == original.constraints.place
        assert reconstructed.constraints.social == original.constraints.social


# ===========================================================================
# GENERATED: CoachState → Plan → reconstrucción
# ===========================================================================


class TestCoachResultToPlanGenerated:
    def test_generated_plan_has_status_generated(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.status == PlanStatus.GENERATED

    def test_generated_plan_has_null_derivation_column(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.derivation is None

    def test_plan_row_to_weekly_plan_reconstructs_faithfully(self):
        # Arrange
        original_weekly_plan = _weekly_plan()
        state: CoachState = {"plan": original_weekly_plan, "activities": _activities()}
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Act
        reconstructed = plan_row_to_weekly_plan(plan)

        # Assert
        assert reconstructed is not None
        assert reconstructed == original_weekly_plan

    def test_plan_row_to_activities_reconstructs_faithfully(self):
        # Arrange
        original_activities = _activities()
        state: CoachState = {"plan": _weekly_plan(), "activities": original_activities}
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Act
        reconstructed = plan_row_to_activities(plan)

        # Assert
        assert reconstructed == original_activities

    def test_generated_plan_has_input_profile_snapshot(self):
        # Arrange
        profile = make_profile()
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=profile,
            input_usage=make_usage(),
        )

        # Assert — el snapshot de entrada debe estar presente
        assert plan.input_profile_snapshot is not None
        assert isinstance(plan.input_profile_snapshot, dict)

    def test_generated_plan_has_input_usage_snapshot(self):
        # Arrange
        usage = make_usage()
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-001",
            input_profile=make_profile(),
            input_usage=usage,
        )

        # Assert
        assert plan.input_usage_snapshot is not None
        assert isinstance(plan.input_usage_snapshot, dict)


# ===========================================================================
# DERIVED: CoachState con derivation → Plan → reconstrucción
# ===========================================================================


class TestCoachResultToPlanDerived:
    def _derivation(self) -> DerivationMessage:
        return DerivationMessage(
            message="Por favor consulta a un profesional de salud mental.",
            resource_type=ResourceType.MENTAL_HEALTH,
        )

    def _risk(self) -> RiskSignal:
        return RiskSignal(
            flag=True,
            reason="RAZON_UNICA_RIESGO_XYZ_2025",
            severity=Severity.HIGH,
        )

    def test_derived_plan_has_status_derived(self):
        # Arrange
        state: CoachState = {
            "derivation": self._derivation(),
            "risk": self._risk(),
        }

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-002",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.status == PlanStatus.DERIVED

    def test_derived_plan_has_null_plan_column(self):
        # Arrange
        state: CoachState = {
            "derivation": self._derivation(),
            "risk": self._risk(),
        }

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-002",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.plan is None

    def test_derived_plan_has_null_activities_column(self):
        # Arrange
        state: CoachState = {
            "derivation": self._derivation(),
            "risk": self._risk(),
        }

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-002",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.activities is None

    def test_plan_row_to_derivation_reconstructs_derivation_message(self):
        # Arrange
        original_derivation = self._derivation()
        state: CoachState = {
            "derivation": original_derivation,
            "risk": self._risk(),
        }
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-002",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Act
        reconstructed = plan_row_to_derivation(plan)

        # Assert
        assert reconstructed is not None
        assert reconstructed == original_derivation

    def test_risk_signal_reason_not_persisted_in_any_column(self):
        # Arrange — razón de riesgo con texto único que NO debe aparecer en BD
        sensitive_reason = "RAZON_UNICA_RIESGO_XYZ_2025"
        state: CoachState = {
            "derivation": self._derivation(),
            "risk": RiskSignal(
                flag=True,
                reason=sensitive_reason,
                severity=Severity.HIGH,
            ),
        }

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-002",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert — INVARIANTE DE SEGURIDAD: el RiskSignal nunca se persiste
        # Serializar todas las columnas relevantes a string y verificar ausencia
        serialized = json.dumps(
            {
                "plan": plan.plan,
                "activities": plan.activities,
                "derivation": plan.derivation,
                "errors": plan.errors,
                "input_profile_snapshot": plan.input_profile_snapshot,
                "input_usage_snapshot": plan.input_usage_snapshot,
            },
            default=str,
        )
        assert sensitive_reason not in serialized, (
            f"El RiskSignal.reason '{sensitive_reason}' fue encontrado en las "
            f"columnas persistidas del Plan — violación de ADR-008."
        )


# ===========================================================================
# Campos de auditoría
# ===========================================================================


class TestAuditFields:
    def test_langfuse_trace_id_propagated_to_plan(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}
        trace_id = "lf-trace-abc123"

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-audit",
            input_profile=make_profile(),
            input_usage=make_usage(),
            langfuse_trace_id=trace_id,
        )

        # Assert
        assert plan.langfuse_trace_id == trace_id

    def test_llm_provider_propagated_to_plan(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-audit",
            input_profile=make_profile(),
            input_usage=make_usage(),
            llm_provider="ollama",
        )

        # Assert
        assert plan.llm_provider == "ollama"

    def test_llm_model_propagated_to_plan(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-audit",
            input_profile=make_profile(),
            input_usage=make_usage(),
            llm_model="llama3.2:3b",
        )

        # Assert
        assert plan.llm_model == "llama3.2:3b"

    def test_audit_fields_all_none_when_not_provided(self):
        # Arrange
        state: CoachState = {"plan": _weekly_plan(), "activities": _activities()}

        # Act
        plan = coach_result_to_plan_row(
            result=state,
            user_id="user-audit",
            input_profile=make_profile(),
            input_usage=make_usage(),
        )

        # Assert
        assert plan.langfuse_trace_id is None
        assert plan.llm_provider is None
        assert plan.llm_model is None
