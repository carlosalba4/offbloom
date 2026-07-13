# ADR-011: Refresh token en cookie httpOnly

- **Estado**: aceptado — **enmienda parcial de ADR-007**
- **Fecha**: 2026-07-03

> Esta decisión **enmienda parcialmente ADR-007**: cambia **solo el transporte del
> refresh token** (de body/cliente a cookie httpOnly). **No lo supersede.** El resto de
> ADR-007 sigue vigente sin cambios: access token corto en memoria del cliente, refresh
> **rotativo persistido en DB como hash SHA-256**, y aislamiento por usuario bloqueante.
> La rotación/revocación en DB es **agnóstica al transporte** y no se toca.

## Contexto
ADR-007 fijó el par access+refresh, pero dejaba el **refresh token en el body** de la
respuesta (`/login`, `/refresh`), de modo que el cliente lo guardaba y lo reenviaba en el
body. Eso hace el refresh **accesible por JavaScript**: un XSS podría robar un token de
**larga vida** (14 días) y mantener sesión persistente pese a la rotación. El access token
efímero (~30 min) tiene una ventana de exposición pequeña, pero el refresh no.

Movemos el refresh a una **cookie httpOnly** para que deje de ser accesible por JS,
neutralizando el robo de refresh por XSS sin cambiar el modelo de rotación/revocación ya
auditado en DB.

## Decisión

### Transporte del refresh
- El refresh viaja **solo** en una **cookie httpOnly** emitida por el servidor
  (`Set-Cookie` en `/login` y en cada rotación de `/refresh`; borrado en `/logout`).
- Atributos de la cookie:
  - `HttpOnly` — fuera del alcance de `document.cookie`/JS.
  - `Path=/auth` — la cookie solo se adjunta a los endpoints de auth, no a toda la API.
  - `Max-Age` = **14 días**, alineado con `refresh_token_expire_days` y con la expiración
    persistida en DB (una sola fuente de verdad de vida del refresh).
  - `Secure`, `SameSite` y `Domain` **parametrizados por env** (nada hardcodeado,
    CLAUDE.md §2). Defaults de desarrollo: `SameSite=Lax`; `Secure`/`Domain` se activan
    según despliegue.

### Topología de transporte: A (directo cross-origin)
Elegimos **A: navegador ↔ FastAPI directo cross-origin**:
- CORS con **`allow_credentials=True`** y **origen explícito** leído de config (no
  comodín; `allow_credentials=True` es incompatible con `*`).
- El frontend hace `fetch(..., { credentials: 'include' })` en los endpoints de auth.

Se descarta para Fase 1 la opción **B: proxy same-origin / BFF** (Next reenvía a FastAPI
desde el mismo origen, la cookie se vuelve first-party). B añade una capa de infra y de
despliegue que no aporta valor en el MVP y se aleja del espíritu directo de ADR-007.
**Migrar a B sería aditivo**: no rompe el contrato de tokens ni el modelo de DB; si una
topología futura lo exige, se adopta sin reescritura.

### Contrato de endpoints
- `TokenResponse` pasa a ser **access-only**: `{access_token, token_type}`. El refresh ya
  **no** aparece en ningún body.
- `POST /auth/login`: body `{email, password}` → `TokenResponse` + `Set-Cookie` (refresh).
- `POST /auth/refresh`: **sin body**, lee la cookie → `TokenResponse` + **rota** la cookie.
- `POST /auth/logout`: **sin body**, lee la cookie → 200 + **borra** la cookie.
- `GET /auth/me`: Bearer → `{id, email, has_profile}`. Fuente de hidratación de sesión.

### Postura CSRF
El único vector CSRF que introduce la cookie son `/auth/refresh` y `/auth/logout` (los
demás endpoints sensibles usan **Bearer**, no fijable cross-site → inmunes):
- **`SameSite=Lax`** impide que el navegador adjunte la cookie en peticiones cross-site
  iniciadas por terceros, así que un sitio atacante no puede disparar `/refresh` o
  `/logout` con la cookie de la víctima.
- Aun si se enviara, un CSRF a `/refresh` **solo rotaría** el token: es una **molestia**,
  no un robo. La respuesta (el nuevo access) va al **origen atacante**, y **CORS la
  bloquea** (no hay `allow_credentials` para ese origen), de modo que el atacante no puede
  leerla.
- **Conclusión Fase 1**: `SameSite=Lax` es **suficiente**, sin token CSRF adicional. Si
  una topología futura obliga a **`SameSite=None`** (contexto verdaderamente cross-site),
  hay que **reconsiderar** e introducir defensa **double-submit token**.

## Consecuencias
- **Positivas**: el refresh de larga vida queda **fuera del alcance de JS** (XSS ya no lo
  roba); el contrato de endpoints es más limpio (`/refresh` y `/logout` sin body); la vida
  del refresh tiene una sola fuente (DB + `Max-Age`); el modelo de rotación/revocación de
  ADR-007 se conserva intacto.
- **Negativas / seguimiento**: se añade dependencia de **CORS con credenciales** y de una
  **config de cookie correcta** por entorno; la **topología de despliegue de producción
  queda parametrizada por env** y su **elección concreta** (same-site vs cross-site, valor
  de `SameSite`/`Domain`/`Secure`) se **decidirá y documentará** cuando se fije el
  despliegue — **no** se asume ninguna hipótesis cerrada (p. ej. "misma eTLD+1").
  `revoke_all_for_user` (cierre de sesión global) **sigue sin endpoint expuesto**
  (aplazado, como en ADR-007).

## Alternativas descartadas
- **Proxy same-origin / BFF (opción B)** — la cookie se vuelve first-party y desaparece la
  necesidad de CORS con credenciales, pero añade una capa de infra y despliegue que no
  aporta valor en Fase 1; queda como migración **aditiva** para el futuro.
- **Seguir con el refresh en el body (ADR-007 original)** — lo mantiene **accesible por
  JS**; es justo el riesgo XSS que esta decisión elimina.
- **Sesiones server-side clásicas (cookie de sesión + store)** — más infraestructura y
  acoplamiento; **ya descartado en ADR-007** y sin motivo para reabrirlo.
