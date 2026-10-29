"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { googleLoginUrl } from "@/lib/api/auth"

/** Logo "G" de Google en SVG inline (lucide no incluye logos de marca). */
function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.46a5.52 5.52 0 0 1-2.4 3.62v3h3.88c2.27-2.09 3.58-5.17 3.58-8.81Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.94-2.92l-3.88-3c-1.07.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.28v3.1A12 12 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.29 14.28A7.2 7.2 0 0 1 4.91 12c0-.79.14-1.56.38-2.28v-3.1H1.28A12 12 0 0 0 0 12c0 1.94.46 3.77 1.28 5.38l4.01-3.1Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.77c1.76 0 3.34.61 4.59 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.28 6.62l4.01 3.1C6.23 6.88 8.88 4.77 12 4.77Z"
      />
    </svg>
  )
}

/**
 * Separador "o" + botón que arranca el login con Google. Es una navegación de
 * página completa (no fetch): el backend redirige a Google y, a la vuelta, a
 * /auth/google/callback.
 */
export function GoogleSignInButton() {
  const [redirecting, setRedirecting] = React.useState(false)

  function handleClick() {
    setRedirecting(true)
    window.location.href = googleLoginUrl()
  }

  return (
    <>
      <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        o
        <span className="h-px flex-1 bg-border" />
      </div>
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="w-full"
        disabled={redirecting}
        onClick={handleClick}
      >
        <GoogleLogo />
        {redirecting ? "Redirigiendo…" : "Iniciar sesión con Google"}
      </Button>
    </>
  )
}
