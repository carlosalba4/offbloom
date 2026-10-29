"use client"

import { Suspense } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useRedirectIfAuthenticated } from "@/lib/auth/use-require-auth"

const GENERIC_ERROR = "Algo ha fallado al iniciar sesión con Google. Inténtalo de nuevo."

/** Mensajes por slug de `?error=` (ver `_google_error_redirect` en el backend). */
const ERROR_MESSAGES: Record<string, string> = {
  email_not_verified:
    "Tu cuenta de Google no tiene el email verificado. Verifícalo en Google e inténtalo de nuevo.",
  account_already_linked:
    "Ese email ya está asociado a otra cuenta de Google. Entra con la cuenta con la que te registraste o usa tu email y contraseña.",
  access_denied: "Has cancelado el inicio de sesión con Google.",
}

function Spinner({ label }: { label: string }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 py-24">
      <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
      <p className="text-sm text-muted-foreground" role="status">
        {label}
      </p>
    </main>
  )
}

function GoogleCallbackError({ message }: { message: string }) {
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>No hemos podido iniciar sesión con Google</CardTitle>
          <CardDescription role="alert">{message}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild size="lg" className="w-full">
            <Link href="/login">Volver a iniciar sesión</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}

/**
 * Éxito: el backend ya dejó la cookie de refresh. NO se lanza un refresh
 * propio: el cold start de `AuthProvider` ya hace `POST /auth/refresh` en esta
 * carga de página, y un segundo refresh concurrente con la misma cookie
 * (rotativa) fallaría y cerraría la sesión. Basta con esperar a que `status`
 * se resuelva; la redirección es la misma que la del login normal.
 */
function GoogleCallbackSuccess() {
  const { status } = useRedirectIfAuthenticated("/dashboard")

  if (status === "unauthenticated") {
    return <GoogleCallbackError message={GENERIC_ERROR} />
  }
  return <Spinner label="Completando el inicio de sesión…" />
}

function GoogleCallbackGate() {
  const searchParams = useSearchParams()
  const error = searchParams.get("error")

  if (error !== null) {
    return <GoogleCallbackError message={ERROR_MESSAGES[error] ?? GENERIC_ERROR} />
  }
  return <GoogleCallbackSuccess />
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={<Spinner label="Cargando…" />}>
      <GoogleCallbackGate />
    </Suspense>
  )
}
