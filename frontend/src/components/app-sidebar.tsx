"use client"

/**
 * Barra lateral de las áreas autenticadas con navegación (chrome de `(app)`).
 * Custom y ligera: sin librería de sidebar, solo Tailwind + lucide-react, en
 * línea con el resto de componentes artesanales del repo.
 *
 * Responsive a mano: el anclaje se hace con `sticky`, en ambos formatos —
 * franja superior fija en móvil, columna fija a la izquierda en `md+` —
 * con los mismos enlaces.
 */

import * as React from "react"
import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import { CalendarCheck, ListChecks, LogOut, UserRound } from "lucide-react"

import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth/auth-context"

interface NavItem {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  isActive: (pathname: string) => boolean
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/dashboard",
    label: "Check-in",
    icon: CalendarCheck,
    isActive: (pathname) => pathname === "/dashboard",
  },
  {
    href: "/plans",
    label: "Mis planes",
    icon: ListChecks,
    isActive: (pathname) => pathname === "/plans" || pathname.startsWith("/plans/"),
  },
  {
    href: "/profile",
    label: "Perfil",
    icon: UserRound,
    isActive: (pathname) => pathname === "/profile",
  },
]

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
      )}
    >
      <Icon className="size-4.5 shrink-0" />
      {item.label}
    </Link>
  )
}

export function AppSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = React.useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      router.replace("/login")
    }
  }

  return (
    <nav className="sticky top-0 z-30 flex shrink-0 flex-col border-b border-sidebar-border bg-sidebar text-sidebar-foreground md:h-dvh md:w-64 md:overflow-y-auto md:border-b-0 md:border-r">
      <div className="flex items-center gap-2 px-4 py-4 md:px-5 md:py-6">
        <span className="font-serif text-lg font-semibold tracking-tight">
          OffBloom
        </span>
      </div>

      <div className="flex flex-1 flex-col justify-between gap-4 px-3 pb-4 md:px-3">
        <div className="flex flex-row flex-wrap gap-1 md:flex-col">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} active={item.isActive(pathname)} />
          ))}
        </div>

        <div className="flex flex-col gap-2 border-t border-sidebar-border pt-3 md:mt-auto">
          {user?.email && (
            <p className="truncate px-3 text-xs text-sidebar-foreground/70">
              {user.email}
            </p>
          )}
          <button
            type="button"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
            className="flex items-center gap-3 rounded-xl px-3 py-2 text-left text-sm font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground disabled:opacity-60"
          >
            <LogOut className="size-4.5 shrink-0" />
            {loggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
          </button>
        </div>
      </div>
    </nav>
  )
}
