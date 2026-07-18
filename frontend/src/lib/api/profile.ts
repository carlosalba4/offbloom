/**
 * Funciones tipadas sobre `apiRequest` para el endpoint `/me/profile`.
 *
 * Espejo del contrato del backend (`src/coach/api/schemas.py` +
 * `src/coach/graph/state.py`): `UserProfile` es el mismo modelo tanto en el
 * GET como en el PUT (upsert idempotente).
 */

import { apiRequest } from "./client"
import type { UserProfile } from "@/lib/coach"

/** GET /me/profile — 404 "Perfil sin onboarding" si el usuario aún no tiene perfil. */
export function getProfile(): Promise<UserProfile> {
  return apiRequest<UserProfile>("/me/profile")
}

/** PUT /me/profile — upsert idempotente; body y respuesta son ambos `UserProfile`. */
export function putProfile(profile: UserProfile): Promise<UserProfile> {
  return apiRequest<UserProfile>("/me/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  })
}
