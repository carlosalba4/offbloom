"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { RouteGuard } from "@/components/route-guard"
import { ChipGroup, EnumSelect, FieldError } from "@/components/onboarding-fields"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { putProfile } from "@/lib/api/profile"
import { ApiError } from "@/lib/api/client"
import { useAuth } from "@/lib/auth/auth-context"
import {
  buildProfile,
  createEmptyForm,
  ENERGY_OPTIONS,
  GOAL_OPTIONS,
  INTEREST_OPTIONS,
  PLACE_OPTIONS,
  SOCIAL_OPTIONS,
  type EnergyLevel,
  type OnboardingForm,
  type Place,
  type SocialPreference,
} from "@/lib/coach"

// ---------------------------------------------------------------------------
// Validación — solo los campos de perfil (goals, minutos, energy, place, social)
// ---------------------------------------------------------------------------

interface FormErrors {
  goals?: string
  availableMinutes?: string
  energy?: string
  place?: string
  social?: string
}

function validate(form: OnboardingForm): FormErrors {
  const errors: FormErrors = {}
  if (form.goals.length === 0) {
    errors.goals = "Elige al menos un objetivo."
  }
  if (!form.availableMinutes || form.availableMinutes <= 0) {
    errors.availableMinutes = "Indica cuántos minutos tienes disponibles."
  }
  if (!form.energy) errors.energy = "Selecciona tu nivel de energía."
  if (!form.place) errors.place = "Selecciona dónde sueles estar."
  if (!form.social) errors.social = "Selecciona tu preferencia social."
  return errors
}

type SubmitStatus = "idle" | "loading" | "error"

function OnboardingContent() {
  const { user, refreshUser } = useAuth()
  const router = useRouter()

  const [form, setForm] = React.useState<OnboardingForm>(createEmptyForm)
  const [errors, setErrors] = React.useState<FormErrors>({})
  const [status, setStatus] = React.useState<SubmitStatus>("idle")
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)

  // Ya tiene perfil (p.ej. entró aquí directamente por URL): fuera, al dashboard.
  React.useEffect(() => {
    if (user?.has_profile === true) {
      router.replace("/dashboard")
    }
  }, [user, router])

  function toggleInList(key: "goals" | "interests", value: string) {
    setForm((prev) => {
      const list = prev[key]
      const next = list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value]
      return { ...prev, [key]: next }
    })
  }

  function addToList(key: "goals" | "interests", value: string) {
    setForm((prev) =>
      prev[key].includes(value)
        ? prev
        : { ...prev, [key]: [...prev[key], value] }
    )
  }

  function removeFromList(key: "goals" | "interests", value: string) {
    setForm((prev) => ({
      ...prev,
      [key]: prev[key].filter((v) => v !== value),
    }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setStatus("loading")
    setErrorMsg(null)
    try {
      await putProfile(buildProfile(form))
      await refreshUser()
      router.replace("/dashboard")
    } catch (err) {
      setErrorMsg(
        err instanceof ApiError
          ? err.message
          : "No hemos podido guardar tu perfil. Inténtalo de nuevo."
      )
      setStatus("error")
    }
  }

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <header className="flex flex-col gap-2 text-center">
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-foreground">
            Cuéntanos sobre ti
          </h1>
          <p className="text-lg leading-relaxed text-muted-foreground">
            Con esto el coach prepara un plan a tu medida. Sin prisa: responde
            lo que te encaje.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
          {/* Sección 1 — Objetivos e intereses */}
          <Card>
            <CardHeader>
              <CardTitle>Objetivos e intereses</CardTitle>
              <CardDescription>
                Qué quieres conseguir y qué te apetece hacer en su lugar.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3">
                <Label>Objetivos</Label>
                <ChipGroup
                  options={GOAL_OPTIONS}
                  selected={form.goals}
                  onToggle={(v) => toggleInList("goals", v)}
                  onAdd={(v) => addToList("goals", v)}
                  onRemove={(v) => removeFromList("goals", v)}
                  addPlaceholder="Añadir otro objetivo…"
                  invalid={!!errors.goals}
                />
                <FieldError message={errors.goals} />
              </div>
              <div className="flex flex-col gap-3">
                <Label>Intereses</Label>
                <ChipGroup
                  options={INTEREST_OPTIONS}
                  selected={form.interests}
                  onToggle={(v) => toggleInList("interests", v)}
                  onAdd={(v) => addToList("interests", v)}
                  onRemove={(v) => removeFromList("interests", v)}
                  addPlaceholder="Añadir otro interés…"
                />
              </div>
            </CardContent>
          </Card>

          {/* Sección 2 — Restricciones de contexto */}
          <Card>
            <CardHeader>
              <CardTitle>Tu contexto</CardTitle>
              <CardDescription>
                Esto ayuda al coach a proponerte cosas realistas para tu día a día.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-2">
                <Label htmlFor="available-minutes">
                  Minutos disponibles al día
                </Label>
                <Input
                  id="available-minutes"
                  type="number"
                  min={1}
                  inputMode="numeric"
                  placeholder="p. ej. 30"
                  className="max-w-[10rem]"
                  value={form.availableMinutes ?? ""}
                  onChange={(e) => {
                    const v =
                      e.target.value === ""
                        ? null
                        : Number.parseInt(e.target.value, 10)
                    setForm((prev) => ({
                      ...prev,
                      availableMinutes: Number.isNaN(v as number) ? null : v,
                    }))
                  }}
                  aria-invalid={!!errors.availableMinutes}
                />
                <FieldError message={errors.availableMinutes} />
              </div>

              <div className="grid gap-5 sm:grid-cols-3">
                <div className="flex flex-col gap-2">
                  <Label>Energía</Label>
                  <EnumSelect
                    value={form.energy}
                    onChange={(v: EnergyLevel) =>
                      setForm((p) => ({ ...p, energy: v }))
                    }
                    options={ENERGY_OPTIONS}
                    placeholder="Elige…"
                    invalid={!!errors.energy}
                  />
                  <FieldError message={errors.energy} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Dónde sueles estar</Label>
                  <EnumSelect
                    value={form.place}
                    onChange={(v: Place) =>
                      setForm((p) => ({ ...p, place: v }))
                    }
                    options={PLACE_OPTIONS}
                    placeholder="Elige…"
                    invalid={!!errors.place}
                  />
                  <FieldError message={errors.place} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Preferencia social</Label>
                  <EnumSelect
                    value={form.social}
                    onChange={(v: SocialPreference) =>
                      setForm((p) => ({ ...p, social: v }))
                    }
                    options={SOCIAL_OPTIONS}
                    placeholder="Elige…"
                    invalid={!!errors.social}
                  />
                  <FieldError message={errors.social} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Button
            type="submit"
            size="lg"
            className="self-center px-8 text-base"
            disabled={status === "loading"}
          >
            {status === "loading" ? "Guardando…" : "Guardar y continuar"}
          </Button>
        </form>

        {/* Estado de error: amable y con opción de reintentar. */}
        {status === "error" && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle>No hemos podido guardar tu perfil</CardTitle>
              <CardDescription>
                {errorMsg ?? "Algo ha fallado al guardar tu perfil."}
              </CardDescription>
            </CardHeader>
          </Card>
        )}
      </div>
    </main>
  )
}

export default function OnboardingPage() {
  return (
    <RouteGuard>
      <OnboardingContent />
    </RouteGuard>
  )
}
