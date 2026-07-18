"use client"

/**
 * Dashboard: check-in ligero de uso (solo `UsageData` — energía y tiempo
 * disponible ya viven en el perfil) que dispara `POST /plans` y renderiza el
 * `PlanResult` correspondiente.
 */

import * as React from "react"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

import { RouteGuard } from "@/components/route-guard"
import { ChipGroup, FieldError } from "@/components/onboarding-fields"
import { PlanResult } from "@/components/plan-result"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createPlan, type PlanResponse } from "@/lib/api/plans"
import { ApiError } from "@/lib/api/client"
import { useAuth } from "@/lib/auth/auth-context"
import {
  buildUsage,
  createEmptyForm,
  TIME_OPTIONS,
  TRIGGER_OPTIONS,
  USAGE_CATEGORIES,
  type OnboardingForm,
  type TimeOfDay,
} from "@/lib/coach"

// ---------------------------------------------------------------------------
// Validación — solo el check-in de uso
// ---------------------------------------------------------------------------

interface FormErrors {
  usage?: string
}

function validate(form: OnboardingForm): FormErrors {
  const errors: FormErrors = {}
  const hasUsage = USAGE_CATEGORIES.some((c) => {
    const m = form.categoryMinutes[c]
    return m && m > 0
  })
  if (!hasUsage) {
    errors.usage = "Rellena los minutos de al menos una categoría."
  }
  return errors
}

type RequestStatus = "idle" | "loading" | "success" | "error"

// El coach tarda decenas de segundos; rotamos estos mensajes durante la espera.
const LOADING_MESSAGES = [
  "Analizando tus hábitos…",
  "Buscando alternativas para ti…",
  "Preparando tu plan…",
] as const

function CheckInForm() {
  const [form, setForm] = React.useState<OnboardingForm>(createEmptyForm)
  const [errors, setErrors] = React.useState<FormErrors>({})
  const [status, setStatus] = React.useState<RequestStatus>("idle")
  const [plan, setPlan] = React.useState<PlanResponse | null>(null)
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [loadingMsg, setLoadingMsg] = React.useState<string>(LOADING_MESSAGES[0])

  // Rota el mensaje de carga mientras esperamos al coach.
  React.useEffect(() => {
    if (status !== "loading") return
    let index = 0
    const id = window.setInterval(() => {
      index = (index + 1) % LOADING_MESSAGES.length
      setLoadingMsg(LOADING_MESSAGES[index])
    }, 3500)
    return () => window.clearInterval(id)
  }, [status])

  function toggleTrigger(value: string) {
    setForm((prev) => {
      const list = prev.triggers
      const next = list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value]
      return { ...prev, triggers: next }
    })
  }

  function addTrigger(value: string) {
    setForm((prev) =>
      prev.triggers.includes(value)
        ? prev
        : { ...prev, triggers: [...prev.triggers, value] }
    )
  }

  function removeTrigger(value: string) {
    setForm((prev) => ({
      ...prev,
      triggers: prev.triggers.filter((v) => v !== value),
    }))
  }

  function togglePeakWindow(value: TimeOfDay) {
    setForm((prev) => ({
      ...prev,
      peakWindows: prev.peakWindows.includes(value)
        ? prev.peakWindows.filter((v) => v !== value)
        : [...prev.peakWindows, value],
    }))
  }

  function setCategoryMinutes(category: string, raw: string) {
    const parsed = raw === "" ? null : Number.parseInt(raw, 10)
    setForm((prev) => ({
      ...prev,
      categoryMinutes: {
        ...prev.categoryMinutes,
        [category]: Number.isNaN(parsed as number) ? null : parsed,
      },
    }))
  }

  async function sendCheckIn() {
    setLoadingMsg(LOADING_MESSAGES[0])
    setStatus("loading")
    setErrorMsg(null)
    setPlan(null)
    try {
      const result = await createPlan(buildUsage(form))
      setPlan(result)
      setStatus("success")
    } catch (err) {
      setErrorMsg(
        err instanceof ApiError
          ? err.message
          : "No hemos podido contactar con el coach. Inténtalo de nuevo."
      )
      setStatus("error")
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      return
    }
    await sendCheckIn()
  }

  /** Limpia el resultado para permitir otro check-in, con el formulario en blanco. */
  function resetFlow() {
    setForm(createEmptyForm())
    setErrors({})
    setStatus("idle")
    setPlan(null)
    setErrorMsg(null)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  if (status === "success" && plan) {
    return <PlanResult response={plan} onReset={resetFlow} />
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
        <Card>
          <CardHeader>
            <CardTitle>Tu uso del móvil</CardTitle>
            <CardDescription>
              Una estimación basta. Deja en blanco lo que no apliques.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3">
              <Label>Minutos al día por categoría</Label>
              <div className="flex flex-col gap-3">
                {USAGE_CATEGORIES.map((category) => (
                  <div
                    key={category}
                    className="flex items-center justify-between gap-4"
                  >
                    <span className="text-sm text-foreground">{category}</span>
                    <Input
                      type="number"
                      min={0}
                      inputMode="numeric"
                      placeholder="min/día"
                      aria-label={`Minutos al día en ${category}`}
                      className="max-w-[8rem]"
                      value={form.categoryMinutes[category] ?? ""}
                      onChange={(e) =>
                        setCategoryMinutes(category, e.target.value)
                      }
                    />
                  </div>
                ))}
              </div>
              <FieldError message={errors.usage} />
            </div>

            <div className="flex flex-col gap-3">
              <Label>Cuándo lo usas más</Label>
              <div className="flex flex-wrap gap-4">
                {TIME_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className="flex cursor-pointer items-center gap-2 text-sm text-foreground"
                  >
                    <Checkbox
                      checked={form.peakWindows.includes(option.value)}
                      onCheckedChange={() => togglePeakWindow(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <Label>Qué te empuja a cogerlo</Label>
              <ChipGroup
                options={TRIGGER_OPTIONS}
                selected={form.triggers}
                onToggle={toggleTrigger}
                onAdd={addTrigger}
                onRemove={removeTrigger}
                addPlaceholder="Añadir otro disparador…"
              />
            </div>
          </CardContent>
        </Card>

        <Button
          type="submit"
          size="lg"
          className="self-center px-8 text-base"
          disabled={status === "loading"}
        >
          Generar mi plan
        </Button>
      </form>

      {/* Estado de carga: el coach tarda decenas de segundos. */}
      {status === "loading" && (
        <Card>
          <CardContent className="flex items-center gap-3 py-6">
            <Loader2 className="size-5 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {loadingMsg}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Estado de error: amable y con opción de reintentar. */}
      {status === "error" && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle>No hemos podido generar tu plan</CardTitle>
            <CardDescription>
              {errorMsg ?? "Algo ha fallado al contactar con el coach."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => void sendCheckIn()}
            >
              Reintentar
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

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
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
              Tu check-in
            </h1>
            <p className="text-sm text-muted-foreground">
              Sesión iniciada como{" "}
              <span className="font-medium text-foreground">{user?.email}</span>.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
          >
            {loggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
          </Button>
        </header>

        <CheckInForm />
      </div>
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
