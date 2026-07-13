/**
 * Cliente HTTP central para hablar con el backend (FastAPI).
 *
 * Contrato de sesión: el access token (JWT corto) vive en memoria del
 * cliente y viaja por header `Authorization: Bearer`; el refresh token vive
 * en una cookie httpOnly (`Path=/auth`) que el navegador gestiona solo. Por
 * eso TODAS las peticiones van con `credentials: 'include'` y ninguna
 * función de este módulo escribe el access token en localStorage/sessionStorage/
 * cookies — solo lo mantiene el `AuthProvider` en un `useRef`.
 *
 * Para evitar un import circular con React, `AuthProvider` se registra aquí
 * mediante un pequeño registry de módulo (`setAccessTokenGetter`,
 * `setAccessTokenSetter`, `setOnAuthFailure`) en vez de que este módulo
 * importe el contexto de React.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// ---------------------------------------------------------------------------
// Registry de módulo — puente sin import circular con el AuthProvider
// ---------------------------------------------------------------------------

let accessTokenGetter: (() => string | null) | null = null
let accessTokenSetter: ((token: string | null) => void) | null = null
let onAuthFailure: (() => void) | null = null

/** Registrado por `AuthProvider`: permite leer el access token vigente en memoria. */
export function setAccessTokenGetter(fn: () => string | null): void {
  accessTokenGetter = fn
}

/** Registrado por `AuthProvider`: permite que el interceptor actualice el access token tras un refresh. */
export function setAccessTokenSetter(fn: (token: string | null) => void): void {
  accessTokenSetter = fn
}

/** Registrado por `AuthProvider`: se invoca cuando el refresh falla (sesión perdida). */
export function setOnAuthFailure(fn: () => void): void {
  onAuthFailure = fn
}

// ---------------------------------------------------------------------------
// Error tipado
// ---------------------------------------------------------------------------

/** Error lanzado por `apiRequest` cuando la respuesta HTTP no es 2xx. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

// ---------------------------------------------------------------------------
// Fetch de bajo nivel
// ---------------------------------------------------------------------------

function buildUrl(path: string): string {
  return `${API_BASE}${path}`
}

function buildHeaders(options: RequestInit, token: string | null): Headers {
  const headers = new Headers(options.headers)
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }
  return headers
}

/** Dispara el fetch real; `tokenOverride` fuerza un token concreto (usado en el reintento tras refresh). */
function doFetch(
  path: string,
  options: RequestInit,
  tokenOverride?: string | null
): Promise<Response> {
  const token =
    tokenOverride !== undefined ? tokenOverride : (accessTokenGetter?.() ?? null)

  return fetch(buildUrl(path), {
    ...options,
    credentials: "include",
    headers: buildHeaders(options, token),
  })
}

/** Endpoints de auth que NUNCA deben disparar el interceptor de refresh (evita bucles). */
function isAuthBootstrapEndpoint(path: string): boolean {
  return path === "/auth/refresh" || path === "/auth/login"
}

// ---------------------------------------------------------------------------
// Interceptor 401 con cola single-flight
// ---------------------------------------------------------------------------

// Único refresh en vuelo compartido por todas las peticiones concurrentes que
// vean un 401: la primera lo dispara, las demás esperan la MISMA promesa en
// vez de disparar N refresh (que rotarían el token en cascada e invalidarían
// entre sí las respuestas de las otras).
let refreshPromise: Promise<string | null> | null = null

async function performRefresh(): Promise<string | null> {
  try {
    const res = await fetch(buildUrl("/auth/refresh"), {
      method: "POST",
      credentials: "include",
    })
    if (!res.ok) return null

    const data = (await res.json()) as { access_token: string; token_type: string }
    accessTokenSetter?.(data.access_token)
    return data.access_token
  } catch {
    return null
  }
}

function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

/**
 * `fetch` con sesión: adjunta el Bearer vigente, manda cookies, y si la
 * respuesta es 401 (y la petición no es a `/auth/login` ni `/auth/refresh`)
 * intenta refrescar UNA vez de forma compartida y reintenta la petición
 * original con el nuevo access token. Si el refresh falla, notifica
 * `onAuthFailure` y devuelve la respuesta 401 original.
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const res = await doFetch(path, options)

  if (res.status !== 401 || isAuthBootstrapEndpoint(path)) {
    return res
  }

  const newToken = await refreshAccessToken()
  if (!newToken) {
    onAuthFailure?.()
    return res
  }

  return doFetch(path, options, newToken)
}

// ---------------------------------------------------------------------------
// Wrapper de alto nivel: parsea JSON y lanza `ApiError` en fallos
// ---------------------------------------------------------------------------

/** Envía la petición y devuelve el body ya parseado como `T`; lanza `ApiError` si la respuesta no es 2xx. */
export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await apiFetch(path, options)

  if (!res.ok) {
    let detail = res.statusText
    try {
      const json = (await res.json()) as { detail?: string }
      if (typeof json.detail === "string") detail = json.detail
    } catch {
      // La respuesta no es JSON — usa statusText como mensaje.
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) {
    return undefined as T
  }

  try {
    return (await res.json()) as T
  } catch {
    return undefined as T
  }
}
