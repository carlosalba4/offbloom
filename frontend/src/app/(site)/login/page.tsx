"use client"

import * as React from "react"
import { Suspense } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"

import { GoogleSignInButton } from "@/components/google-sign-in-button"
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
import { ApiError } from "@/lib/api/client"
import { useAuth } from "@/lib/auth/auth-context"

function LoginForm() {
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
      // El guard (`GuestGuard`) es la única fuente de verdad de a dónde ir
      // tras autenticar: redirige según `has_profile` en cuanto detecta sesión.
      await login(email, password)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Email o contraseña incorrectos.")
      } else {
        setError("No hemos podido iniciar sesión. Inténtalo de nuevo.")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Inicia sesión</CardTitle>
          <CardDescription>Accede para continuar con tu plan.</CardDescription>
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
                autoComplete="current-password"
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
              {submitting ? "Entrando…" : "Entrar"}
            </Button>
          </form>
          <GoogleSignInButton />
          <p className="mt-4 text-center text-sm text-muted-foreground">
            ¿No tienes cuenta?{" "}
            <Link href="/register" className="font-medium text-primary hover:underline">
              Regístrate
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}

function LoginFormFallback() {
  return (
    <main className="flex flex-1 items-center justify-center py-24">
      <Loader2 className="size-6 animate-spin text-primary" aria-label="Cargando" />
    </main>
  )
}

/**
 * Lee `next` de la query string (requiere estar bajo `Suspense`) y se lo pasa
 * a `GuestGuard` como destino post-login por defecto.
 */
function LoginGuestGate() {
  const searchParams = useSearchParams()
  const next = searchParams.get("next")

  return (
    <GuestGuard destination={next ?? "/dashboard"}>
      <LoginForm />
    </GuestGuard>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFormFallback />}>
      <LoginGuestGate />
    </Suspense>
  )
}
