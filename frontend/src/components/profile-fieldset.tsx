"use client"

/**
 * Campos de perfil (objetivos, intereses y contexto) compartidos por
 * `/onboarding` y `/profile`: mismas dos `<Card>`, mismas primitivas
 * (`ChipGroup`/`EnumSelect`/`FieldError`) y mismos catálogos. Componente
 * controlado: no valida ni envía, solo edita `form` vía `setForm`.
 */

import * as React from "react"

import { ChipGroup, EnumSelect, FieldError } from "@/components/onboarding-fields"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
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

export interface ProfileFieldErrors {
  goals?: string
  availableMinutes?: string
  energy?: string
  place?: string
  social?: string
}

interface ProfileFieldsetProps {
  form: OnboardingForm
  errors: ProfileFieldErrors
  setForm: React.Dispatch<React.SetStateAction<OnboardingForm>>
}

export function ProfileFieldset({ form, errors, setForm }: ProfileFieldsetProps) {
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

  return (
    <>
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
    </>
  )
}
