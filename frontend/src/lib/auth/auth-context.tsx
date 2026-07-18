"use client"

/**
 * `AuthProvider`: dueño del estado de sesión en el cliente.
 *
 * El access token vive en un `useRef` (para que `apiFetch` siempre lea el
 * valor vigente sin closures obsoletas) y se registra en el cliente HTTP
 * mediante el registry de módulo de `lib/api/client.ts` — así se evita un
 * import circular entre este contexto de React y el cliente HTTP.
 *
 * Al montar, hace un "cold start": intenta `refresh()` contra la cookie
 * httpOnly. Si hay sesión (cookie válida), recupera el usuario; si no, cae a
 * `unauthenticated` sin romper (primera visita sin cookie).
 */

import * as React from "react"

import * as authApi from "@/lib/api/auth"
import type { AuthUser } from "@/lib/api/auth"
import {
  setAccessTokenGetter,
  setAccessTokenSetter,
  setOnAuthFailure,
} from "@/lib/api/client"

export type AuthStatus = "loading" | "authenticated" | "unauthenticated"

interface AuthContextValue {
  user: AuthUser | null
  status: AuthStatus
  login: (email: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  refreshSession: () => Promise<boolean>
  /** Vuelve a pedir /auth/me y actualiza `user` (p.ej. tras completar el onboarding). */
  refreshUser: () => Promise<void>
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null)
  const [status, setStatus] = React.useState<AuthStatus>("loading")
  const accessTokenRef = React.useRef<string | null>(null)

  const setAccessToken = React.useCallback((token: string | null) => {
    accessTokenRef.current = token
  }, [])

  const clearSession = React.useCallback(() => {
    setAccessToken(null)
    setUser(null)
    setStatus("unauthenticated")
  }, [setAccessToken])

  // Registro en el cliente HTTP + cold start. Se ejecuta una única vez al montar.
  React.useEffect(() => {
    setAccessTokenGetter(() => accessTokenRef.current)
    setAccessTokenSetter(setAccessToken)
    setOnAuthFailure(clearSession)

    let cancelled = false

    async function coldStart() {
      try {
        const tokens = await authApi.refresh()
        if (cancelled) return
        setAccessToken(tokens.access_token)

        const me = await authApi.getMe()
        if (cancelled) return
        setUser(me)
        setStatus("authenticated")
      } catch {
        if (cancelled) return
        clearSession()
      }
    }

    void coldStart()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo debe correr una vez al montar
  }, [])

  const login = React.useCallback(
    async (email: string, password: string): Promise<AuthUser> => {
      const tokens = await authApi.login(email, password)
      setAccessToken(tokens.access_token)

      const me = await authApi.getMe()
      setUser(me)
      setStatus("authenticated")
      return me
    },
    [setAccessToken]
  )

  const logout = React.useCallback(async (): Promise<void> => {
    try {
      await authApi.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const refreshSession = React.useCallback(async (): Promise<boolean> => {
    try {
      const tokens = await authApi.refresh()
      setAccessToken(tokens.access_token)
      return true
    } catch {
      clearSession()
      return false
    }
  }, [setAccessToken, clearSession])

  const refreshUser = React.useCallback(async (): Promise<void> => {
    const me = await authApi.getMe()
    setUser(me)
  }, [])

  const value = React.useMemo<AuthContextValue>(
    () => ({ user, status, login, logout, refreshSession, refreshUser }),
    [user, status, login, logout, refreshSession, refreshUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth debe usarse dentro de <AuthProvider>")
  }
  return ctx
}
