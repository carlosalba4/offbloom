"use client"

/**
 * Perfil editable: precarga el perfil persistido en el mismo formulario que
 * el onboarding (`ProfileFieldset`) y permite guardarlo de nuevo sin
 * redirigir — feedback de éxito/error inline.
 */

import * as React from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"

import { ProfileFieldset, type ProfileFieldErrors } from "@/components/profile-fieldset"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getProfile, putProfile } from "@/lib/api/profile"
import { ApiError } from "@/lib/api/client"
import { createEmptyForm, buildProfile, formFromProfile, type OnboardingForm } from "@/lib/coach"

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

type LoadStatus = "loading" | "success" | "needs-onboarding" | "error"
type SaveStatus = "idle" | "saving" | "saved" | "error"

export default function ProfilePage() {
  const [loadStatus, setLoadStatus] = React.useState<LoadStatus>("loading")
  const [loadErrorMsg, setLoadErrorMsg] = React.useState<string | null>(null)

  const [form, setForm] = React.useState<OnboardingForm>(createEmptyForm)
  const [errors, setErrors] = React.useState<ProfileFieldErrors>({})
  const [saveStatus, setSaveStatus] = React.useState<SaveStatus>("idle")
  const [saveErrorMsg, setSaveErrorMsg] = React.useState<string | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        const profile = await getProfile()
        if (cancelled) return
        setForm(formFromProfile(profile))
        setLoadStatus("success")
      } catch (err) {
        if (cancelled) return
        // 404 = el usuario aún no completó el onboarding: no es un error, lo
        // encaminamos a crearlo en vez de ofrecer un "Reintentar" inútil.
        if (err instanceof ApiError && err.status === 404) {
          setLoadStatus("needs-onboarding")
          return
        }
        setLoadErrorMsg(
          err instanceof ApiError
            ? err.message
            : "No hemos podido cargar tu perfil."
        )
        setLoadStatus("error")
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [reloadToken])

  function retryLoad() {
    setLoadStatus("loading")
    setLoadErrorMsg(null)
    setReloadToken((t) => t + 1)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setSaveStatus("saving")
    setSaveErrorMsg(null)
    try {
      await putProfile(buildProfile(form))
      setSaveStatus("saved")
    } catch (err) {
      setSaveErrorMsg(
        err instanceof ApiError
          ? err.message
          : "No hemos podido guardar tu perfil. Inténtalo de nuevo."
      )
      setSaveStatus("error")
    }
  }

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <header className="flex flex-col gap-2">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
            Tu perfil
          </h1>
          <p className="text-sm text-muted-foreground">
            Objetivos, intereses y contexto que usa el coach para tus planes.
          </p>
        </header>

        {loadStatus === "loading" && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-primary" aria-label="Cargando" />
          </div>
        )}

        {loadStatus === "needs-onboarding" && (
          <Card>
            <CardHeader>
              <CardTitle>Aún no tienes un perfil</CardTitle>
              <CardDescription>
                Completa el onboarding para que el coach pueda conocerte y
                prepararte planes a tu medida.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="lg">
                <Link href="/onboarding">Completar onboarding</Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {loadStatus === "error" && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle>No hemos podido cargar tu perfil</CardTitle>
              <CardDescription>
                {loadErrorMsg ?? "Algo ha fallado al cargar tu perfil."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" variant="outline" size="lg" onClick={retryLoad}>
                Reintentar
              </Button>
            </CardContent>
          </Card>
        )}

        {loadStatus === "success" && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
            <ProfileFieldset
              form={form}
              errors={errors}
              setForm={(next) => {
                // Al editar, cualquier feedback de guardado anterior queda obsoleto.
                setSaveStatus("idle")
                setForm(next)
              }}
            />

            <Button
              type="submit"
              size="lg"
              className="self-center px-8 text-base"
              disabled={saveStatus === "saving"}
            >
              {saveStatus === "saving" ? "Guardando…" : "Guardar cambios"}
            </Button>

            {saveStatus === "saved" && (
              <p className="text-center text-sm font-medium text-primary" role="status">
                Perfil actualizado.
              </p>
            )}
            {saveStatus === "error" && (
              <p className="text-center text-sm text-destructive" role="alert">
                {saveErrorMsg ?? "Algo ha fallado al guardar tu perfil."}
              </p>
            )}
          </form>
        )}
      </div>
    </main>
  )
}
