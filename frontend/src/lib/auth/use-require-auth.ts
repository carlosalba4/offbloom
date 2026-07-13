"use client"

/**
 * Hooks de guarda de ruta, solo-cliente. La defensa real de los datos la hace
 * el backend con el 401; esto es únicamente para UX (evitar mostrar
 * pantallas protegidas/públicas a quien no toca, y navegar a donde
 * corresponda).
 */

import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"

import { useAuth, type AuthStatus } from "@/lib/auth/auth-context"

/** Para rutas protegidas: redirige a /login (con `next`) en cuanto se confirma que no hay sesión. */
export function useRequireAuth(): { status: AuthStatus } {
  const { status } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (status === "unauthenticated") {
      const next = encodeURIComponent(pathname)
      router.replace(`/login?next=${next}`)
    }
  }, [status, pathname, router])

  return { status }
}

/** Para páginas públicas de auth (/login, /register): aparta a quien ya tiene sesión. */
export function useRedirectIfAuthenticated(destination = "/dashboard"): {
  status: AuthStatus
} {
  const { status } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (status === "authenticated") {
      router.replace(destination)
    }
  }, [status, router, destination])

  return { status }
}
