"use client"

/**
 * Primitivas de formulario compartidas entre `/onboarding` (perfil) y
 * `/dashboard` (check-in de uso): chips de selección múltiple con opción de
 * añadir, `Select` genérico para enums, y el mensaje de error de campo.
 */

import * as React from "react"
import { Plus, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { EnumOption } from "@/lib/coach"

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
export function ChipGroup({
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
export function EnumSelect<T extends string>({
  value,
  onChange,
  options,
  placeholder,
  invalid,
}: EnumSelectProps<T>) {
  return (
    <Select value={value ?? ""} onValueChange={(v) => onChange(v as T)}>
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

export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="text-sm text-destructive">{message}</p>
}
