"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { RouteGuard } from "@/components/route-guard"
import { ProfileFieldset, type ProfileFieldErrors } from "@/components/profile-fieldset"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { putProfile } from "@/lib/api/profile"
import { ApiError } from "@/lib/api/client"
import { useAuth } from "@/lib/auth/auth-context"
import { buildProfile, createEmptyForm, type OnboardingForm } from "@/lib/coach"

// ---------------------------------------------------------------------------
// Validación — solo los campos de perfil (goals, minutos, energy, place, social)
// ---------------------------------------------------------------------------

function validate(form: OnboardingForm): ProfileFieldErrors {
  const errors: ProfileFieldErrors = {}
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
  const [errors, setErrors] = React.useState<ProfileFieldErrors>({})
  const [status, setStatus] = React.useState<SubmitStatus>("idle")
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)

  // Ya tiene perfil (p.ej. entró aquí directamente por URL): fuera, al dashboard.
  React.useEffect(() => {
    if (user?.has_profile === true) {
      router.replace("/dashboard")
    }
  }, [user, router])

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
          <ProfileFieldset form={form} errors={errors} setForm={setForm} />

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
