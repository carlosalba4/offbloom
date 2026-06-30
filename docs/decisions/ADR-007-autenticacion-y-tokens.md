# ADR-007: Autenticación, tokens y aislamiento por usuario

- **Estado**: aceptado
- **Fecha**: 2026-06-30

## Contexto
Con cuentas y datos personales (perfil de bienestar, historial), OffBloom necesita
autenticación y un aislamiento estricto entre usuarios desde la Fase 1. El dominio es
sensible (CLAUDE.md §8), así que el control de acceso debe ser bloqueante y no filtrar
información. Queremos además logout real ("cerrar sesión en todos los dispositivos")
sin montar infraestructura de sesiones pesada, y dejar la puerta abierta a OAuth sin
una migración disruptiva.

## Decisión
- **Email + contraseña** con hash **argon2** (`auth/security.py`).
- **JWT con pyjwt**: **access token corto** (`access_token_expire_minutes`, vive solo en
  memoria del cliente) + **refresh token ROTATIVO persistido en DB** (tabla
  `RefreshToken`, `refresh_token_expire_days`). Rotar/revocar el refresh en DB permite
  **logout real** y cierre de sesión global desde Fase 1.
- **`password_hash` NULLABLE**, preparado para login OAuth futuro (ADR-009, Fase 4) sin
  migración disruptiva.
- **Aislamiento por usuario bloqueante**: toda query autenticada filtra por
  `current_user.id`; el acceso a un recurso ajeno devuelve **404, no 403** (no se revela
  su existencia). `user_id` se **denormaliza** en `Plan` y `ActivityProgress` para que
  el filtro de propiedad sea directo. `get_current_user` (en `api/deps.py`) valida el
  access token y carga el `User`.

## Consecuencias
- **Positivas**: logout real y revocación global sin servidor de sesiones; access token
  efímero reduce la ventana de un token filtrado; argon2 es resistente a fuerza bruta;
  la regla 404-no-403 no filtra existencia de recursos; OAuth futuro no rompe el
  esquema.
- **Negativas**: la rotación de refresh añade estado en DB y lógica de revocación que
  hay que mantener correcta; denormalizar `user_id` obliga a mantener coherencia en las
  escrituras; gestionar la expiración/limpieza de refresh tokens es trabajo extra.

## Alternativas descartadas
- **Solo access token (JWT stateless)** — sin estado en DB no hay logout real ni
  revocación; inaceptable para un dominio sensible.
- **Sesiones server-side clásicas (cookie + store)** — más infraestructura; el par
  access+refresh cubre el caso con menos acoplamiento al frontend.
- **bcrypt en vez de argon2** — argon2 es el estándar recomendado actual; sin razón para
  el más antiguo en un proyecto nuevo.
- **Devolver 403 en recurso ajeno** — revela la existencia del recurso; 404 es más
  seguro.
- **OAuth desde Fase 1** — scope creep; el `password_hash` nullable deja el camino
  abierto sin pagar el coste ahora.
