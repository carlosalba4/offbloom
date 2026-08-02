/**
 * Funciones tipadas sobre `apiRequest` para el endpoint `/plans`.
 *
 * Espejo del contrato del backend (`src/coach/api/schemas.py`): `PlanResponse`
 * es un superset de `CoachResponse` — añade metadatos de persistencia
 * (`id`, `status`, `created_at`) y conserva `plan | null`, `activities[]`,
 * `derivation | null`, `errors[]` sin cambios, así que el `PlanResult` que
 * consume `CoachResponse` lo renderiza sin mapeo adicional.
 */

import { apiRequest } from "./client"
import type { CoachResponse, UsageData } from "@/lib/coach"

export interface PlanResponse extends CoachResponse {
  id: string
  status: string
  created_at: string
}

/** POST /plans — genera y persiste un plan a partir del check-in de uso actual. */
export function createPlan(usage: UsageData): Promise<PlanResponse> {
  return apiRequest<PlanResponse>("/plans", {
    method: "POST",
    body: JSON.stringify({ usage }),
  })
}

/** Resumen de un plan persistido, tal y como lo devuelve `GET /plans` (orden fecha desc). */
export interface PlanSummary {
  id: string
  status: string
  created_at: string
  focus: string | null
}

/** GET /plans — historial de planes del usuario autenticado. */
export function listPlans(): Promise<PlanSummary[]> {
  return apiRequest<PlanSummary[]>("/plans")
}

/** GET /plans/{id} — detalle completo de un plan; `ApiError.status === 404` si no existe o es ajeno. */
export function getPlan(id: string): Promise<PlanResponse> {
  return apiRequest<PlanResponse>(`/plans/${id}`)
}

/** Estado resultante tras marcar o desmarcar una actividad (espejo de `ActivityProgressResponse`). */
export interface ActivityProgressResponse {
  activity_index: number
  done: boolean
}

/**
 * PUT /plans/{planId}/activities/{activityIndex}/progress — marca o desmarca
 * una actividad (idempotente). La identidad de la actividad es su posición en
 * el array inmutable del plan (ADR-008). `ApiError.status === 404` si el plan
 * no existe o es ajeno, y también si el índice cae fuera de rango.
 */
export function setActivityProgress(
  planId: string,
  activityIndex: number,
  done: boolean
): Promise<ActivityProgressResponse> {
  return apiRequest<ActivityProgressResponse>(
    `/plans/${planId}/activities/${activityIndex}/progress`,
    {
      method: "PUT",
      body: JSON.stringify({ done }),
    }
  )
}
