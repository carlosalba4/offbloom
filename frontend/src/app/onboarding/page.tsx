"use client"

import * as React from "react"
import { Plus, X } from "lucide-react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  buildCoachRequest,
  createEmptyForm,
  ENERGY_OPTIONS,
  GOAL_OPTIONS,
  INTEREST_OPTIONS,
  PLACE_OPTIONS,
  SOCIAL_OPTIONS,
  TIME_OPTIONS,
  TRIGGER_OPTIONS,
  USAGE_CATEGORIES,
  type CoachRequest,
  type EnergyLevel,
  type EnumOption,
  type OnboardingForm,
  type Place,
  type SocialPreference,
  type TimeOfDay,
} from "@/lib/coach"

// ---------------------------------------------------------------------------
// Subcomponentes locales (chips de selección múltiple con opción de añadir)
// ---------------------------------------------------------------------------

interface ChipGroupProps {
  options: readonly string[]
  selected: string[]
  onToggle: (value: string) => void
  onRemove: (value: string) => void
  onAdd: (value: string) => void
  addPlaceholder: string
  invalid?: boolean
}

/** Grupo de chips predefinidos + chips propios añadidos + campo "Añadir otro". */
function ChipGroup({
  options,
  selected,
  onToggle,
  onRemove,
  onAdd,
  addPlaceholder,
  invalid,
}: ChipGroupProps) {
  const [draft, setDraft] = React.useState("")
  const custom = selected.filter((s) => !options.includes(s))

  function commitDraft() {
    const value = draft.trim()
    if (value) {
      onAdd(value)
      setDraft("")
    }
  }

  return (
    <div className="flex flex-col gap-3" aria-invalid={invalid}>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = selected.includes(option)
          return (
            <button
              key={option}
              type="button"
              aria-pressed={active}
              onClick={() => onToggle(option)}
              className={
                active
                  ? "rounded-full border border-primary bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors"
                  : "rounded-full border border-border bg-background px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted"
              }
            >
              {option}
            </button>
          )
        })}
        {custom.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 rounded-full border border-accent bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground"
          >
            {value}
            <button
              type="button"
              aria-label={`Quitar ${value}`}
              onClick={() => onRemove(value)}
              className="rounded-full transition-opacity hover:opacity-70"
            >
              <X className="size-3.5" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              commitDraft()
            }
          }}
          placeholder={addPlaceholder}
          className="max-w-xs"
        />
        <Button
          type="button"
          variant="outline"
          size="lg"
          onClick={commitDraft}
          disabled={!draft.trim()}
        >
          <Plus className="size-4" />
          Añadir
        </Button>
      </div>
    </div>
  )
}

interface EnumSelectProps<T extends string> {
  value: T | null
  onChange: (value: T) => void
  options: ReadonlyArray<EnumOption<T>>
  placeholder: string
  invalid?: boolean
}

/** `Select` genérico para un enum, mostrando la etiqueta español y guardando el valor de API. */
function EnumSelect<T extends string>({
  value,
  onChange,
  options,
  placeholder,
  invalid,
}: EnumSelectProps<T>) {
  return (
    <Select value={value ?? undefined} onValueChange={(v) => onChange(v as T)}>
      <SelectTrigger aria-invalid={invalid}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="text-sm text-destructive">{message}</p>
}

// ---------------------------------------------------------------------------
// Validación
// ---------------------------------------------------------------------------

interface FormErrors {
  goals?: string
  availableMinutes?: string
  energy?: string
  place?: string
  social?: string
  usage?: string
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
  const hasUsage = USAGE_CATEGORIES.some((c) => {
    const m = form.categoryMinutes[c]
    return m && m > 0
  })
  if (!hasUsage) {
    errors.usage = "Rellena los minutos de al menos una categoría."
  }
  return errors
}

// ---------------------------------------------------------------------------
// Pantalla
// ---------------------------------------------------------------------------

export default function OnboardingPage() {
  const [form, setForm] = React.useState<OnboardingForm>(createEmptyForm)
  const [errors, setErrors] = React.useState<FormErrors>({})
  const [request, setRequest] = React.useState<CoachRequest | null>(null)

  function toggleInList(key: "goals" | "interests" | "triggers", value: string) {
    setForm((prev) => {
      const list = prev[key]
      const next = list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value]
      return { ...prev, [key]: next }
    })
  }

  function addToList(key: "goals" | "interests" | "triggers", value: string) {
    setForm((prev) =>
      prev[key].includes(value)
        ? prev
        : { ...prev, [key]: [...prev[key], value] }
    )
  }

  function removeFromList(
    key: "goals" | "interests" | "triggers",
    value: string
  ) {
    setForm((prev) => ({
      ...prev,
      [key]: prev[key].filter((v) => v !== value),
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      setRequest(null)
      return
    }
    const built = buildCoachRequest(form)
    // Paso intermedio: aún no llamamos a la API; verificamos el objeto.
    console.log("CoachRequest:", built)
    setRequest(built)
  }

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
        <header className="flex flex-col gap-2 text-center">
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-foreground">
            Cuéntanos sobre ti
          </h1>
          <p className="text-lg leading-relaxed text-muted-foreground">
            Con esto el coach prepara un plan y actividades a tu medida. Sin
            prisa: responde lo que te encaje.
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

          {/* Sección 3 — Datos de uso */}
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
                  onToggle={(v) => toggleInList("triggers", v)}
                  onAdd={(v) => addToList("triggers", v)}
                  onRemove={(v) => removeFromList("triggers", v)}
                  addPlaceholder="Añadir otro disparador…"
                />
              </div>
            </CardContent>
          </Card>

          <Button type="submit" size="lg" className="self-center px-8 text-base">
            Generar mi plan
          </Button>
        </form>

        {/* Previsualización del request (paso intermedio: aún no se llama a la API). */}
        {request && (
          <Card>
            <CardHeader>
              <CardTitle>Vista previa del CoachRequest</CardTitle>
              <CardDescription>
                Esto es lo que se enviará a la API en el siguiente paso. También
                aparece en la consola del navegador.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs leading-relaxed text-foreground">
                {JSON.stringify(request, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  )
}
