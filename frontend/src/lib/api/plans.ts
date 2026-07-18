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
