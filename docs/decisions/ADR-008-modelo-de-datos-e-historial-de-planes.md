# ADR-008: Modelo de datos e historial de planes

- **Estado**: aceptado
- **Fecha**: 2026-06-30

## Contexto
Cada ejecución del coach produce un plan que el usuario consulta a lo largo del tiempo y
sobre el que marca progreso. Necesitamos decidir qué se guarda inmutable y qué se hace
consultable, cómo identificar una actividad concreta para el progreso, cómo persistir
las derivaciones del gate de seguridad sin almacenar internos de riesgo, y cómo se borra
una cuenta. El plan es un **artefacto generado**: re-derivarlo cambiaría el histórico.

## Decisión
- **Snapshot JSON para lo inmutable**: `Plan` guarda `input_profile_snapshot`,
  `input_usage_snapshot`, `plan` (WeeklyPlan), `activities` (lista de CuratedActivity) y
  `derivation` como **JSON**. **Normalización solo de lo mutable**: `ActivityProgress`
  (status PENDING/DONE/SKIPPED).
- **Identidad de actividad por `activity_index`**: el progreso referencia
  `(plan_id, activity_index)` —posición en el array snapshotado—; **no** se añade `id` a
  `CuratedActivity`. Restricción **única (plan_id, activity_index)**.
- **Derivaciones con `status=DERIVED`**: cuando salta el gate de seguridad se persiste un
  `Plan` con `status=DERIVED` que guarda **solo** el `DerivationMessage`. **Nunca** se
  almacenan internos de riesgo: sin teléfonos, sin diagnóstico, sin el `RiskSignal` del
  Analista. (`status` GENERATED|DERIVED; campos `plan`/`activities` quedan vacíos.)
- **Borrado en cascada**: **ON DELETE CASCADE** diseñado desde Fase 1 (User →
  Profile/Plan/ActivityProgress/RefreshToken). El endpoint `DELETE /me` se expone en
  **Fase 2**; las cascadas existen desde ya para no migrar el esquema después.
- **`schema_version` en `Profile`** (int): permite evolucionar la forma del perfil
  (goals/interests/constraints) y migrar perfiles antiguos de forma controlada.
- **Auditoría en `Plan`** (nullable): `langfuse_trace_id`, `llm_provider`, `llm_model`
  para correlacionar cada plan con su traza y el modelo que lo generó.

## Consecuencias
- **Positivas**: el histórico es fiel e inmutable (un plan se lee tal como se generó); el
  progreso vive desacoplado y consultable; identificar actividades por índice evita
  ensuciar el dominio con IDs de persistencia; las derivaciones quedan registradas para
  el usuario sin filtrar datos sensibles de riesgo; el borrado de cuenta es íntegro
  desde el inicio; `schema_version` evita migraciones traumáticas del perfil.
- **Negativas**: el `activity_index` acopla el progreso al orden del array; el snapshot
  no permite reordenar ni editar actividades de un plan ya generado (deseable: es
  inmutable); el contenido JSON no es filtrable por sus campos internos.

## Alternativas descartadas
- **Normalizar plan y actividades en tablas** — el plan es inmutable y no se filtra por
  su contenido; normalizar añade esquema y joins sin beneficio, y dificulta conservar el
  histórico exacto.
- **Añadir `id` a `CuratedActivity`** — contamina el modelo de dominio con una
  preocupación de persistencia; `activity_index` basta para un array inmutable.
- **No persistir las derivaciones** — el usuario perdería el rastro de su interacción; se
  persiste el mensaje empático, nunca los internos de riesgo.
- **Guardar el `RiskSignal`/diagnóstico** — viola la seguridad del dominio (CLAUDE.md
  §8); prohibido.
- **Borrado lógico (soft delete) en Fase 1** — innecesario ahora; la cascada física es
  más simple y el endpoint llega en Fase 2.
- **Perfil sin `schema_version`** — obligaría a migraciones ad-hoc en cuanto cambie la
  forma del perfil.
