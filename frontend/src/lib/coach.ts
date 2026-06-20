/**
 * Capa de dominio del cliente: tipos espejo del contrato de la API (`CoachRequest`),
 * catálogos de opciones con etiqueta legible en español ↔ valor exacto que espera
 * el backend, y el armado puro del request.
 *
 * Contrato backend: src/coach/main.py (CoachRequest) y src/coach/graph/state.py
 * (UserProfile, Constraints, UsageData, CategoryUsage y enums).
 */

// ---------------------------------------------------------------------------
// Enums (los valores DEBEN coincidir con los del backend)
// ---------------------------------------------------------------------------

export type EnergyLevel = "LOW" | "MEDIUM" | "HIGH"
export type Place = "HOME" | "OUTDOORS" | "ANYWHERE"
export type SocialPreference = "SOLO" | "WITH_OTHERS" | "ANY"
export type TimeOfDay = "MORNING" | "AFTERNOON" | "EVENING" | "NIGHT"
export type Lang = "ES" | "EN"

// ---------------------------------------------------------------------------
// Tipos del request (espejo de los modelos Pydantic)
// ---------------------------------------------------------------------------

export interface Constraints {
  available_minutes: number
  energy: EnergyLevel
  place: Place
  social: SocialPreference
}

export interface UserProfile {
  goals: string[]
  interests: string[]
  constraints: Constraints
  lang: Lang
}

export interface CategoryUsage {
  category: string
  minutes_per_day: number
}

export interface UsageData {
  categories: CategoryUsage[]
  peak_windows: TimeOfDay[]
  self_reported_triggers: string[]
}

export interface CoachRequest {
  profile: UserProfile
  usage: UsageData
}

// ---------------------------------------------------------------------------
// Tipos de la respuesta (espejo del contrato de la API — CoachResponse)
// ---------------------------------------------------------------------------

export interface Swap {
  habit: string
  alternative: string
}

export interface Citation {
  source: string
  chunk_id: string | null
}

export interface WeeklyPlan {
  weekly_focus: string
  intentions: string[]
  swaps: Swap[]
  citations: Citation[]
}

/** Corresponde al enum `ResourceType` del backend (src/coach/graph/state.py). */
export type ResourceType =
  | "MENTAL_HEALTH"
  | "MEDICAL"
  | "CRISIS_SUPPORT"
  | "GENERAL"

export interface DerivationMessage {
  message: string
  resource_type: ResourceType
}

export interface CuratedActivity {
  title: string
  reason: string
  why_it_fits: string
  replaces: string | null
  source: string | null
  duration_min: number | null
  energy: EnergyLevel | null
  place: Place | null
  social: SocialPreference | null
  moment: TimeOfDay | null
}

/** Respuesta completa del endpoint POST /coach. */
export interface CoachResponse {
  plan: WeeklyPlan | null
  activities: CuratedActivity[]
  derivation: DerivationMessage | null
  errors: string[]
}

// ---------------------------------------------------------------------------
// Catálogos de opciones (etiqueta español → valor de API)
// ---------------------------------------------------------------------------

export interface EnumOption<T extends string> {
  value: T
  label: string
}

export const ENERGY_OPTIONS: ReadonlyArray<EnumOption<EnergyLevel>> = [
  { value: "LOW", label: "Baja" },
  { value: "MEDIUM", label: "Media" },
  { value: "HIGH", label: "Alta" },
]

export const PLACE_OPTIONS: ReadonlyArray<EnumOption<Place>> = [
  { value: "HOME", label: "En casa" },
  { value: "OUTDOORS", label: "Al aire libre" },
  { value: "ANYWHERE", label: "En cualquier sitio" },
]

export const SOCIAL_OPTIONS: ReadonlyArray<EnumOption<SocialPreference>> = [
  { value: "SOLO", label: "A solas" },
  { value: "WITH_OTHERS", label: "Con otras personas" },
  { value: "ANY", label: "Me da igual" },
]

export const TIME_OPTIONS: ReadonlyArray<EnumOption<TimeOfDay>> = [
  { value: "MORNING", label: "Mañana" },
  { value: "AFTERNOON", label: "Tarde" },
  { value: "EVENING", label: "Noche" },
  { value: "NIGHT", label: "Madrugada" },
]

// Listas predefinidas, alineadas con la persona principal y el corpus.
export const GOAL_OPTIONS: readonly string[] = [
  "Dormir mejor",
  "Reducir scroll nocturno",
  "Recuperar tiempo de calidad",
  "Menos ansiedad",
  "Más foco",
]

export const INTEREST_OPTIONS: readonly string[] = [
  "Lectura",
  "Cocina",
  "Naturaleza / aire libre",
  "Música",
  "Ejercicio",
  "Manualidades",
]

export const TRIGGER_OPTIONS: readonly string[] = [
  "Aburrimiento",
  "Ansiedad antes de dormir",
  "FOMO",
  "Costumbre",
  "Estrés",
]

// Categorías de uso fijas (etiqueta = valor enviado como `category`).
export const USAGE_CATEGORIES: readonly string[] = [
  "Redes sociales",
  "Vídeo corto",
  "Mensajería",
  "Juegos",
  "Noticias / navegación",
]

// ---------------------------------------------------------------------------
// Estado del formulario y armado del request
// ---------------------------------------------------------------------------

export interface OnboardingForm {
  goals: string[]
  interests: string[]
  availableMinutes: number | null
  energy: EnergyLevel | null
  place: Place | null
  social: SocialPreference | null
  /** Minutos/día por categoría; las vacías o ≤ 0 se descartan al armar el request. */
  categoryMinutes: Record<string, number | null>
  peakWindows: TimeOfDay[]
  triggers: string[]
}

export function createEmptyForm(): OnboardingForm {
  return {
    goals: [],
    interests: [],
    availableMinutes: null,
    energy: null,
    place: null,
    social: null,
    categoryMinutes: {},
    peakWindows: [],
    triggers: [],
  }
}

/**
 * Arma un `CoachRequest` a partir del formulario. Asume que ya validó (campos de
 * enum y `availableMinutes` no nulos); descarta categorías con minutos ≤ 0 y fija
 * el idioma a ES. Función pura, sin efectos secundarios.
 */
export function buildCoachRequest(form: OnboardingForm): CoachRequest {
  const categories: CategoryUsage[] = USAGE_CATEGORIES.flatMap((category) => {
    const minutes = form.categoryMinutes[category]
    return minutes && minutes > 0
      ? [{ category, minutes_per_day: minutes }]
      : []
  })

  return {
    profile: {
      goals: form.goals,
      interests: form.interests,
      constraints: {
        available_minutes: form.availableMinutes ?? 0,
        energy: form.energy as EnergyLevel,
        place: form.place as Place,
        social: form.social as SocialPreference,
      },
      lang: "ES",
    },
    usage: {
      categories,
      peak_windows: form.peakWindows,
      self_reported_triggers: form.triggers,
    },
  }
}

// ---------------------------------------------------------------------------
// Cliente HTTP
// ---------------------------------------------------------------------------

/**
 * Envía un `CoachRequest` al endpoint POST /coach y devuelve la respuesta
 * tipada. La URL base se lee de `NEXT_PUBLIC_API_URL` (inlined en el bundle
 * del cliente por Next.js en build time); si no está definida, cae al
 * fallback de desarrollo local.
 *
 * Lanza un `Error` con mensaje legible si la respuesta HTTP no es 2xx.
 */
export async function postCoach(req: CoachRequest): Promise<CoachResponse> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
  const res = await fetch(`${base}/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    // Intenta extraer el campo `detail` que devuelve FastAPI en errores
    let detail = res.statusText
    try {
      const json = (await res.json()) as { detail?: string }
      if (typeof json.detail === "string") detail = json.detail
    } catch {
      // La respuesta no es JSON — usa statusText como mensaje
    }
    throw new Error(`Error ${res.status}: ${detail}`)
  }

  return res.json() as Promise<CoachResponse>
}
