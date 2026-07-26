"use client"

/**
 * Historial de planes: lista los planes/derivaciones persistidos del usuario
 * (orden fecha desc, ya dado por el backend) y enlaza a su detalle.
 */

import * as React from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { listPlans, type PlanSummary } from "@/lib/api/plans"
import { ApiError } from "@/lib/api/client"

type LoadStatus = "loading" | "success" | "error"

const dateFormatter = new Intl.DateTimeFormat("es-ES", { dateStyle: "long" })

/** Etiqueta legible del estado de un plan. */
function statusLabel(status: string): string {
  return status === "GENERATED" ? "Plan" : "Derivación"
}

/** Foco a mostrar; las derivaciones no tienen `focus`, así que damos un texto de respaldo. */
function focusLabel(plan: PlanSummary): string {
  if (plan.focus) return plan.focus
  return plan.status === "DERIVED"
    ? "Derivación a ayuda profesional"
    : "Sin foco disponible"
}

function PlanCard({ plan }: { plan: PlanSummary }) {
  return (
    <Link href={`/plans/${plan.id}`}>
      <Card className="transition-colors hover:border-primary/50">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-lg">{focusLabel(plan)}</CardTitle>
            <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
              {statusLabel(plan.status)}
            </span>
          </div>
          <CardDescription>
            {dateFormatter.format(new Date(plan.created_at))}
          </CardDescription>
        </CardHeader>
      </Card>
    </Link>
  )
}

export default function PlansPage() {
  const [status, setStatus] = React.useState<LoadStatus>("loading")
  const [plans, setPlans] = React.useState<PlanSummary[]>([])
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        const result = await listPlans()
        if (cancelled) return
        setPlans(result)
        setStatus("success")
      } catch (err) {
        if (cancelled) return
        setErrorMsg(
          err instanceof ApiError
            ? err.message
            : "No hemos podido cargar tu historial de planes."
        )
        setStatus("error")
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [reloadToken])

  function retry() {
    setStatus("loading")
    setErrorMsg(null)
    setReloadToken((t) => t + 1)
  }

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <header className="flex flex-col gap-2">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
            Mis planes
          </h1>
          <p className="text-sm text-muted-foreground">
            El historial de tus planes semanales y derivaciones.
          </p>
        </header>

        {status === "loading" && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-primary" aria-label="Cargando" />
          </div>
        )}

        {status === "error" && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle>No hemos podido cargar tus planes</CardTitle>
              <CardDescription>
                {errorMsg ?? "Algo ha fallado al cargar tu historial."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" variant="outline" size="lg" onClick={retry}>
                Reintentar
              </Button>
            </CardContent>
          </Card>
        )}

        {status === "success" && plans.length === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Aún no tienes planes</CardTitle>
              <CardDescription>
                Haz tu primer check-in para que el coach prepare uno a tu medida.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="lg">
                <Link href="/dashboard">Ir al check-in</Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {status === "success" && plans.length > 0 && (
          <div className="flex flex-col gap-4">
            {plans.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
