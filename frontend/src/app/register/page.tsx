"use client"

import * as React from "react"
import Link from "next/link"

import { GuestGuard } from "@/components/route-guard"
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
import * as auth from "@/lib/api/auth"
import { ApiError } from "@/lib/api/client"
import { useAuth } from "@/lib/auth/auth-context"

function RegisterForm() {
  const { login } = useAuth()

  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      // El backend no emite tokens en /auth/register: encadenamos un login
      // con las mismas credenciales para arrancar la sesión. El guard
      // (`GuestGuard`) redirige a /onboarding en cuanto detecta la sesión
      // recién creada, porque `has_profile` es `false`.
      await auth.register(email, password)
      await login(email, password)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Ya existe una cuenta con ese email.")
      } else {
        setError("No hemos podido crear tu cuenta. Inténtalo de nuevo.")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Crea tu cuenta</CardTitle>
          <CardDescription>
            Regístrate para que el coach prepare tu plan.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" disabled={submitting} className="mt-2">
              {submitting ? "Creando cuenta…" : "Crear cuenta"}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            ¿Ya tienes cuenta?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Inicia sesión
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}

export default function RegisterPage() {
  return (
    <GuestGuard>
      <RegisterForm />
    </GuestGuard>
  )
}
