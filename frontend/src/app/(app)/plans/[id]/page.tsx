"use client"

/**
 * Detalle de un plan persistido: recargable por URL desde su creación.
 * Siempre re-consulta el backend en el montaje (sin caché de cliente).
 */

import * as React from "react"
import { use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

import { PlanResult } from "@/components/plan-result"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getPlan, type PlanResponse } from "@/lib/api/plans"
import { ApiError } from "@/lib/api/client"

type LoadStatus = "loading" | "success" | "not-found" | "error"

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()

  const [status, setStatus] = React.useState<LoadStatus>("loading")
  const [plan, setPlan] = React.useState<PlanResponse | null>(null)
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        const result = await getPlan(id)
        if (cancelled) return
        setPlan(result)
        setStatus("success")
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setStatus("not-found")
          return
        }
        setErrorMsg(
          err instanceof ApiError ? err.message : "No hemos podido cargar este plan."
        )
        setStatus("error")
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [id, reloadToken])

  function retry() {
    setStatus("loading")
    setErrorMsg(null)
    setPlan(null)
    setReloadToken((t) => t + 1)
  }

  // Al navegar de /plans/A a /plans/B, Next reutiliza este componente y el
  // efecto re-consulta por el nuevo id; hasta que resuelve, `plan` sigue siendo
  // el anterior. Como cada `PlanResponse` trae su propio id, detectamos ese
  // desfase y mostramos el spinner (sin resetear estado dentro del efecto).
  const stale = status === "success" && plan?.id !== id

  if (status === "loading" || stale) {
    return (
      <main className="flex flex-1 items-center justify-center py-24">
        <Loader2 className="size-6 animate-spin text-primary" aria-label="Cargando" />
      </main>
    )
  }

  if (status === "not-found") {
    return (
      <main className="flex flex-1 justify-center px-6 py-12">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
          <Card>
            <CardHeader>
              <CardTitle>No encontramos este plan</CardTitle>
              <CardDescription>
                Puede que ya no exista o que no tengas acceso a él.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="lg">
                <Link href="/plans">Volver a mis planes</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  if (status === "error") {
    return (
      <main className="flex flex-1 justify-center px-6 py-12">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle>No hemos podido cargar tu plan</CardTitle>
              <CardDescription>
                {errorMsg ?? "Algo ha fallado al cargar este plan."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" variant="outline" size="lg" onClick={retry}>
                Reintentar
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  if (!plan) return null

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <PlanResult response={plan} onReset={() => router.push("/dashboard")} />
      </div>
    </main>
  )
}
