"use client"

/**
 * Punto único de providers de cliente. Se importa desde el `layout.tsx` raíz
 * (Server Component) para que el árbol pueda usar `useAuth()` sin convertir
 * el layout entero en Client Component.
 */

import type { ReactNode } from "react"

import { AuthProvider } from "@/lib/auth/auth-context"

export function Providers({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}
