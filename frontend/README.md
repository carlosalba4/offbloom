# OffBloom — Frontend

Web client for the OffBloom coach. It talks to the FastAPI backend in the repository root.

## Stack

- Next.js 16 (App Router) + React 19
- TypeScript
- Tailwind CSS v4
- shadcn/ui (on top of Radix UI), lucide-react icons

## Getting started

```bash
npm install
npm run dev          # -> http://localhost:3000
```

The backend URL comes from `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`). The backend must allow this origin via its `FRONTEND_ORIGIN` setting (default: `http://localhost:3000`).

Other scripts: `npm run build`, `npm run start`, `npm run lint`.

## Routes

Two route groups under `src/app/`:

- **`(site)`** — public pages:
  - `/` — landing
  - `/login`, `/register` — email/password and Google sign-in
  - `/auth/google/callback` — completes the Google sign-in session
  - `/onboarding` — initial profile (requires a session)
- **`(app)`** — authenticated area with sidebar; the layout wraps every page in `RouteGuard`:
  - `/dashboard`
  - `/plans`, `/plans/[id]` — plan history and detail
  - `/profile`

## Session handling

All backend calls go through a single client, `src/lib/api/client.ts`:

- The **access token** (short-lived JWT) lives **only in memory** (held by `AuthProvider`) and is sent as `Authorization: Bearer`. It is never written to localStorage, sessionStorage or cookies.
- The **refresh token** lives in an **httpOnly cookie** (`Path=/auth`) managed by the browser; every request uses `credentials: "include"`.
- A **401 interceptor** performs a single shared (single-flight) `POST /auth/refresh` and retries the original request once. If the refresh fails, the session is cleared. `/auth/login` and `/auth/refresh` are excluded to avoid loops.
- On a cold start, the session is restored with `POST /auth/refresh` followed by `GET /auth/me`.

The TypeScript types in `src/lib/coach.ts` mirror the backend's Pydantic models by hand — keep them in sync.
