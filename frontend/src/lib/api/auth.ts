/**
 * Funciones tipadas sobre `apiRequest` para los endpoints de `/auth`.
 *
 * Espejo del contrato del backend (`src/coach/api/schemas.py`): el refresh
 * token vive solo en la cookie httpOnly, nunca en el body de estas
 * respuestas ni de estas peticiones.
 */

import { apiRequest } from "./client"

export interface AuthUser {
  id: string
  email: string
  has_profile: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

/** POST /auth/login — body {email, password}; el refresh viaja en Set-Cookie, no en el body. */
export function login(email: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

/** POST /auth/register — 201 sin tokens; hay que hacer login aparte. */
export function register(email: string, password: string): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

/** POST /auth/refresh — sin body; la cookie del refresh viaja sola y se rota. */
export function refresh(): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/refresh", { method: "POST" })
}

/** POST /auth/logout — sin body; borra la cookie del refresh en el backend. */
export async function logout(): Promise<void> {
  await apiRequest<{ detail: string }>("/auth/logout", { method: "POST" })
}

/** GET /auth/me — requiere Bearer válido (lo adjunta apiFetch automáticamente). */
export function getMe(): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me", { method: "GET" })
}
