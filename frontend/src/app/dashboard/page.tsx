"use client"

/**
 * Placeholder mínimo, protegido, para verificar el flujo de guardas/logout
 * end-to-end. La pantalla real del dashboard/plan es la Parte 2.
 */

import * as React from "react"
import { useRouter } from "next/navigation"

import { RouteGuard } from "@/components/route-guard"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth/auth-context"

function DashboardContent() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [loggingOut, setLoggingOut] = React.useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      router.replace("/login")
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Dashboard</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Sesión iniciada como <span className="font-medium text-foreground">{user?.email}</span>.
          </p>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
          >
            {loggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}

export default function DashboardPage() {
  return (
    <RouteGuard>
      <DashboardContent />
    </RouteGuard>
  )
}
