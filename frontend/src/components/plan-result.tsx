"use client"

/**
 * Pantalla de resultado del coach: orquesta los tres casos del
 * `CoachResponse` (derivación, plan con actividades, o plan parcial con
 * errores). Extraído de `/onboarding` para reutilizarlo también en
 * `/dashboard` tras cada check-in — mismas props, sin rediseño.
 */

import * as React from "react"
import { ArrowRight, Check, HeartHandshake } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  ENERGY_OPTIONS,
  PLACE_OPTIONS,
  TIME_OPTIONS,
  type CoachResponse,
  type CuratedActivity,
  type EnergyLevel,
  type Place,
  type ResourceType,
  type TimeOfDay,
  type WeeklyPlan,
} from "@/lib/coach"

// ---------------------------------------------------------------------------
// Lookups de etiquetas
// ---------------------------------------------------------------------------

// Etiquetas legibles para el tipo de recurso de una derivación.
const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  MENTAL_HEALTH: "Salud mental",
  MEDICAL: "Atención médica",
  CRISIS_SUPPORT: "Apoyo en crisis",
  GENERAL: "Recurso general",
}

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

/** Caso A — derivación: mensaje sereno y cálido, sin tono de error. */
function DerivationCard({
  derivation,
}: {
  derivation: NonNullable<CoachResponse["derivation"]>
}) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-accent/40 bg-accent/10 p-6">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent/30 text-accent-foreground">
          <HeartHandshake className="size-5" />
        </span>
        <span className="text-xs font-semibold uppercase tracking-widest text-accent-foreground/80">
          {RESOURCE_TYPE_LABELS[derivation.resource_type]}
        </span>
      </div>
      <p className="text-base leading-relaxed text-foreground">
        {derivation.message}
      </p>
    </div>
  )
}

/** Aviso discreto cuando llega plan pero `errors` trae algo. */
function PartialErrorNotice() {
  return (
    <div className="rounded-xl border border-accent/30 bg-muted px-4 py-3 text-sm text-muted-foreground">
      Algunas piezas del plan no se pudieron preparar. El resto está listo para
      ti.
    </div>
  )
}

/** Hero con el foco de la semana. */
function FocusHero({ focus }: { focus: string }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-semibold uppercase tracking-widest text-primary">
        Tu foco de esta semana
      </span>
      <h2 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-foreground sm:text-4xl">
        {focus}
      </h2>
    </div>
  )
}

/** Lista de intenciones con check teal sutil. */
function IntentionsList({ intentions }: { intentions: string[] }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Tus intenciones
      </span>
      <ul className="flex flex-col gap-2.5">
        {intentions.map((intention) => (
          <li key={intention} className="flex items-start gap-3">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Check className="size-3.5" />
            </span>
            <span className="text-sm leading-relaxed text-foreground">
              {intention}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Sustituciones: hábito → alternativa, de forma visual. */
function SwapsList({ swaps }: { swaps: WeeklyPlan["swaps"] }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Sustituciones
      </span>
      <ul className="flex flex-col gap-2">
        {swaps.map((swap) => (
          <li
            key={`${swap.habit}-${swap.alternative}`}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl bg-muted px-4 py-3 text-sm"
          >
            <span className="text-muted-foreground line-through">
              {swap.habit}
            </span>
            <ArrowRight className="size-4 shrink-0 text-primary" />
            <span className="font-medium text-primary">{swap.alternative}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Tarjeta de una actividad curada, con su metainfo como badges. */
function ActivityCard({ activity }: { activity: CuratedActivity }) {
  const badges: string[] = []
  if (activity.duration_min != null) badges.push(`${activity.duration_min} min`)
  if (activity.energy) badges.push(`Energía: ${ENERGY_LABELS[activity.energy]}`)
  if (activity.place) badges.push(PLACE_LABELS[activity.place])
  if (activity.moment) badges.push(TIME_LABELS[activity.moment])

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5">
      <h3 className="font-serif text-lg font-semibold leading-snug text-foreground">
        {activity.title}
      </h3>
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
  )
}

/** Grid de actividades propuestas. */
function ActivitiesGrid({ activities }: { activities: CuratedActivity[] }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Actividades para ti
      </span>
      <div className="grid gap-4 sm:grid-cols-2">
        {activities.map((activity) => (
          <ActivityCard key={activity.title} activity={activity} />
        ))}
      </div>
    </div>
  )
}

/** Citas al pie, discretas y deduplicadas por fuente. */
function CitationsFooter({ citations }: { citations: WeeklyPlan["citations"] }) {
  const sources = Array.from(new Set(citations.map((c) => c.source)))
  if (sources.length === 0) return null

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-4">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Fuentes
      </span>
      <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
        {sources.map((source) => (
          <li key={source}>{source}</li>
        ))}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pantalla de resultado
// ---------------------------------------------------------------------------

/** Pantalla de resultado: orquesta los tres casos del `CoachResponse`. */
export function PlanResult({
  response,
  onReset,
}: {
  response: CoachResponse
  onReset: () => void
}) {
  const { plan, activities, derivation, errors } = response

  return (
    <section className="flex flex-col gap-8">
      {derivation ? (
        <DerivationCard derivation={derivation} />
      ) : (
        plan && (
          <div className="flex flex-col gap-8">
            <FocusHero focus={plan.weekly_focus} />
            {errors.length > 0 && <PartialErrorNotice />}
            {plan.intentions.length > 0 && (
              <IntentionsList intentions={plan.intentions} />
            )}
            {plan.swaps.length > 0 && <SwapsList swaps={plan.swaps} />}
            {activities.length > 0 && (
              <ActivitiesGrid activities={activities} />
            )}
            <CitationsFooter citations={plan.citations} />
          </div>
        )
      )}

      <Button
        type="button"
        variant="outline"
        size="lg"
        className="self-center px-8 text-base"
        onClick={onReset}
      >
        Crear otro plan
      </Button>
    </section>
  )
}
