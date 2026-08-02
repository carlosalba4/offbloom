"use client"

/**
 * Sección de actividades del plan con progreso binario: un checkbox por
 * actividad, contador "X de N completadas" y guardado optimista contra
 * `PUT /plans/{id}/activities/{i}/progress`.
 *
 * La identidad de una actividad es su posición en el array del plan (ADR-008),
 * así que el estado local es un array de flags paralelo a `activities` y el
 * índice del map es el `activity_index` que viaja al backend.
 */

import * as React from "react"

import { Checkbox } from "@/components/ui/checkbox"
import { setActivityProgress } from "@/lib/api/plans"
import {
  ENERGY_OPTIONS,
  PLACE_OPTIONS,
  TIME_OPTIONS,
  type ActivityWithProgress,
  type EnergyLevel,
  type Place,
  type TimeOfDay,
} from "@/lib/coach"
import { cn } from "@/lib/utils"

// ---------------------------------------------------------------------------
// Lookups de etiquetas
// ---------------------------------------------------------------------------

// Lookups valor de API → etiqueta español para la metainfo de actividades.
// Reutilizan los catálogos del dominio como única fuente de verdad.
const ENERGY_LABELS = Object.fromEntries(
  ENERGY_OPTIONS.map((o) => [o.value, o.label])
) as Record<EnergyLevel, string>

const PLACE_LABELS = Object.fromEntries(
  PLACE_OPTIONS.map((o) => [o.value, o.label])
) as Record<Place, string>

const TIME_LABELS = Object.fromEntries(
  TIME_OPTIONS.map((o) => [o.value, o.label])
) as Record<TimeOfDay, string>

// ---------------------------------------------------------------------------
// Estado de progreso
// ---------------------------------------------------------------------------

/** Copia el array de flags cambiando solo la posición `index`. */
function withAt(flags: boolean[], index: number, value: boolean): boolean[] {
  return flags.map((flag, i) => (i === index ? value : flag))
}

// ---------------------------------------------------------------------------
// Subcomponentes de presentación
// ---------------------------------------------------------------------------

/** Badge discreto para la metainfo de una actividad. */
function MetaBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
      {children}
    </span>
  )
}

/** Aviso discreto cuando el guardado del progreso falla. */
function SaveErrorNotice() {
  return (
    <div
      role="alert"
      className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
    >
      No hemos podido guardar el cambio. Inténtalo de nuevo.
    </div>
  )
}

/** Tarjeta de una actividad curada, con su checkbox de progreso y su metainfo. */
function ActivityCard({
  activity,
  done,
  onToggle,
}: {
  activity: ActivityWithProgress
  done: boolean
  onToggle: (next: boolean) => void
}) {
  // El título se mantiene como <h3> por semántica; el checkbox se etiqueta con
  // él por id en vez de envolverlo en un <label>.
  const titleId = React.useId()

  const badges: string[] = []
  if (activity.duration_min != null) badges.push(`${activity.duration_min} min`)
  if (activity.energy) badges.push(`Energía: ${ENERGY_LABELS[activity.energy]}`)
  if (activity.place) badges.push(PLACE_LABELS[activity.place])
  if (activity.moment) badges.push(TIME_LABELS[activity.moment])

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 transition-colors",
        done && "bg-muted/40"
      )}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          className="mt-1"
          checked={done}
          onCheckedChange={(checked) => onToggle(checked === true)}
          aria-labelledby={titleId}
        />
        <h3
          id={titleId}
          className={cn(
            "font-serif text-lg font-semibold leading-snug text-foreground transition-colors",
            done && "text-muted-foreground line-through"
          )}
        >
          {activity.title}
        </h3>
      </div>
      <div
        className={cn(
          "flex flex-col gap-3 transition-opacity",
          done && "opacity-60"
        )}
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          {activity.why_it_fits}
        </p>
        {activity.replaces && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Sustituye a:</span>{" "}
            {activity.replaces}
          </p>
        )}
        {badges.length > 0 && (
          <div className="mt-auto flex flex-wrap gap-2 pt-1">
            {badges.map((badge) => (
              <MetaBadge key={badge}>{badge}</MetaBadge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sección de actividades
// ---------------------------------------------------------------------------

/** Grid de actividades propuestas con su progreso editable. */
export function PlanActivities({
  planId,
  activities,
}: {
  planId: string
  activities: ActivityWithProgress[]
}) {
  // Semilla única desde las props: quien renderiza pasa `key={planId}` para que
  // cambiar de plan remonte la sección en vez de arrastrar el progreso anterior.
  const [doneFlags, setDoneFlags] = React.useState<boolean[]>(() =>
    activities.map((activity) => activity.done)
  )
  const [saveFailed, setSaveFailed] = React.useState(false)

  // Derivado en cada render: no hay contador que mantener sincronizado.
  const completed = doneFlags.filter(Boolean).length

  async function toggle(index: number, next: boolean) {
    // Optimista: la UI cambia ya y el PUT viaja por detrás.
    setDoneFlags((prev) => withAt(prev, index, next))
    setSaveFailed(false)

    try {
      await setActivityProgress(planId, index, next)
    } catch {
      // Revierte solo si nadie ha vuelto a tocar esa actividad mientras tanto.
      setDoneFlags((prev) =>
        prev[index] === next ? withAt(prev, index, !next) : prev
      )
      setSaveFailed(true)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Actividades para ti
        </span>
        <span
          role="status"
          className="text-xs font-medium tabular-nums text-muted-foreground"
        >
          {completed} de {activities.length} completadas
        </span>
      </div>
      {saveFailed && <SaveErrorNotice />}
      <div className="grid gap-4 sm:grid-cols-2">
        {activities.map((activity, index) => (
          <ActivityCard
            key={`${index}-${activity.title}`}
            activity={activity}
            done={doneFlags[index] ?? false}
            onToggle={(next) => void toggle(index, next)}
          />
        ))}
      </div>
    </div>
  )
}
