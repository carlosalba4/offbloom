import type { ReactNode } from "react"

import { SiteHeader } from "@/components/site-header"

/**
 * Chrome público: cabecera de marca sin navegación de app. Cubre landing,
 * login, registro y onboarding (autenticado pero sin sidebar).
 */
export default function SiteLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      {children}
    </>
  )
}
