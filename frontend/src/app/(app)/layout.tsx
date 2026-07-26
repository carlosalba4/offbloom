"use client"

import type { ReactNode } from "react"

import { RouteGuard } from "@/components/route-guard"
import { AppSidebar } from "@/components/app-sidebar"

/**
 * Chrome autenticado: sidebar de navegación + `RouteGuard` aplicado una sola
 * vez para todas las rutas del grupo (dashboard, historial de planes, perfil).
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RouteGuard>
      <div className="flex flex-1 flex-col md:flex-row">
        <AppSidebar />
        <div className="flex flex-1 flex-col">{children}</div>
      </div>
    </RouteGuard>
  )
}
