"""Mappers ORM <-> dominio Pydantic.

ÚNICO archivo de db/ que importa coach.graph.state. Nunca al revés (frontera
bloqueante, ADR-006). Funciones puras: no tocan la sesión ni la DB.

Contrato de persistencia (ADR-008):
- Al guardar: model_dump(mode="json") para serializar a dict/JSON.
- Al leer:    Model.model_validate(...) para reconstruir desde dict/JSON.
- RiskSignal NUNCA se persiste (contiene internos de riesgo sensibles).
- Cuando status=DERIVED se guarda solo el DerivationMessage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from coach.db.enums import PlanStatus
from coach.db.models.plan import Plan
from coach.db.models.profile import Profile
from coach.graph.state import (
    CoachState,
    CuratedActivity,
    DerivationMessage,
    UsageData,
    UserProfile,
    WeeklyPlan,
)


def profile_to_domain(profile: Profile) -> UserProfile:
    """Reconstruye un UserProfile del dominio desde un Profile ORM.

    Usa model_validate para que Pydantic valide los datos al leer de la DB.
    """
    return UserProfile.model_validate(
        {
            "goals": profile.goals or [],
            "interests": profile.interests or [],
            "constraints": profile.constraints,
            "lang": profile.lang,
        }
    )


def domain_to_profile_dict(user_profile: UserProfile) -> dict:
    """Serializa un UserProfile del dominio a dict para pasarlo a ProfileRepo.upsert.

    El dict resultante contiene exactamente los campos que el repo espera:
    goals, interests, constraints, lang.
    """
    data = user_profile.model_dump(mode="json")
    return {
        "goals": data["goals"],
        "interests": data["interests"],
        "constraints": data["constraints"],
        "lang": data["lang"],
    }


def coach_result_to_plan_row(
    result: CoachState,
    user_id: str,
    input_profile: UserProfile,
    input_usage: UsageData,
    langfuse_trace_id: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> Plan:
    """Mapea el resultado del grafo del coach a un Plan ORM listo para persistir.

    Reglas (ADR-008):
    - result["derivation"] presente → status=DERIVED; guarda solo el
      DerivationMessage serializado. plan/activities quedan a None.
      El RiskSignal NUNCA se guarda (datos internos de riesgo sensibles).
    - Sin derivación → status=GENERATED; guarda WeeklyPlan + list[CuratedActivity].

    El mapper no importa settings; recibe llm_provider/model como argumentos.
    """
    derivation = result.get("derivation")

    if derivation is not None:
        status = PlanStatus.DERIVED
        plan_json: dict | None = None
        activities_json: list | None = None
        derivation_json: dict | None = derivation.model_dump(mode="json")
    else:
        status = PlanStatus.GENERATED
        weekly_plan: WeeklyPlan | None = result.get("plan")
        plan_json = weekly_plan.model_dump(mode="json") if weekly_plan is not None else None
        raw_activities: list[CuratedActivity] = result.get("activities") or []
        activities_json = [a.model_dump(mode="json") for a in raw_activities]
        derivation_json = None

    return Plan(
        id=str(uuid.uuid4()),
        user_id=user_id,
        status=status,
        input_profile_snapshot=input_profile.model_dump(mode="json"),
        input_usage_snapshot=input_usage.model_dump(mode="json"),
        plan=plan_json,
        activities=activities_json,
        derivation=derivation_json,
        errors=result.get("errors") or [],
        langfuse_trace_id=langfuse_trace_id,
        llm_provider=llm_provider,
        llm_model=llm_model,
        created_at=datetime.now(UTC),
    )


def plan_row_to_weekly_plan(plan: Plan) -> WeeklyPlan | None:
    """Reconstruye un WeeklyPlan desde el snapshot JSON almacenado en el Plan ORM.

    Devuelve None si el campo no está presente (p. ej. cuando status=DERIVED).
    """
    if plan.plan is None:
        return None
    return WeeklyPlan.model_validate(plan.plan)


def plan_row_to_activities(plan: Plan) -> list[CuratedActivity]:
    """Reconstruye la lista de CuratedActivity desde el snapshot JSON del Plan ORM.

    Devuelve lista vacía si el campo es None (p. ej. cuando status=DERIVED).
    """
    if not plan.activities:
        return []
    return [CuratedActivity.model_validate(a) for a in plan.activities]


def plan_row_to_derivation(plan: Plan) -> DerivationMessage | None:
    """Reconstruye un DerivationMessage desde el snapshot JSON del Plan ORM.

    Devuelve None si el campo es None (p. ej. cuando status=GENERATED).
    """
    if plan.derivation is None:
        return None
    return DerivationMessage.model_validate(plan.derivation)
