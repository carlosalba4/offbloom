"use client"

import type { ReactNode } from "react"
import { Loader2 } from "lucide-react"

import {
  useRedirectIfAuthenticated,
  useRequireAuth,
} from "@/lib/auth/use-require-auth"

/** Placeholder mientras se resuelve el cold-start de sesión o se está redirigiendo. */
function AuthPlaceholder() {
  return (
    <main className="flex flex-1 items-center justify-center py-24">
      <Loader2 className="size-6 animate-spin text-primary" aria-label="Cargando" />
    </main>
  )
}

/**
 * Envuelve rutas protegidas (p.ej. /dashboard). Mientras se resuelve el
 * estado de sesión muestra un placeholder (no redirige); si no hay sesión,
 * `useRequireAuth` ya dispara la navegación a /login y aquí no se renderiza
 * nada; si hay sesión, renderiza los children.
 */
export function RouteGuard({ children }: { children: ReactNode }) {
  const { status } = useRequireAuth()

  if (status === "loading") return <AuthPlaceholder />
  if (status === "unauthenticated") return null

  return <>{children}</>
}

/**
 * Envuelve páginas públicas de auth (/login, /register). Si ya hay sesión,
 * `useRedirectIfAuthenticated` navega a `destination` (o a /onboarding si el
 * usuario aún no tiene perfil) y aquí no se renderiza nada; en cualquier otro
 * caso, renderiza los children (el formulario).
 */
export function GuestGuard({
  children,
  destination,
}: {
  children: ReactNode
  destination?: string
}) {
  const { status } = useRedirectIfAuthenticated(destination)

  if (status === "loading") return <AuthPlaceholder />
  if (status === "authenticated") return null

  return <>{children}</>
}
