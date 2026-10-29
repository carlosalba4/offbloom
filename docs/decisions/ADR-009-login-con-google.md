# ADR-009: Login con Google (OIDC) dirigido por el backend

- **Estado**: aceptado — **extensión de ADR-007**
- **Fecha**: 2026-08-02

> Esta decisión **extiende ADR-007**: añade un segundo camino de entrada (Google)
> que desemboca en **exactamente la misma sesión** ya definida allí (access token
> JWT corto + refresh rotativo persistido como hash SHA-256, transportado en la
> cookie httpOnly que fijó ADR-011). **No cambia nada** del modelo de sesión,
> rotación ni revocación.

## Contexto

Hasta ahora la única forma de entrar era email+contraseña. Un "Iniciar sesión con
Google" reduce la fricción de alta y evita a la persona gestionar otra
contraseña. ADR-007 ya lo anticipó: dejó `users.password_hash` **nullable**
precisamente "para OAuth futuro (Fase 4) sin migración disruptiva".

Las decisiones que había que tomar: dónde guardar la identidad de Google, qué
librería usar, cómo protegerse de CSRF en el redirect, y —la más delicada—
cuándo es legítimo **vincular** una identidad de Google a una cuenta que ya
existe.

## Decisión

### 1. Flujo: Authorization Code + OIDC, dirigido por el backend

Dos endpoints bajo el router `/auth` ya existente:

- `GET /auth/google/login` — genera el `state` y redirige a Google.
- `GET /auth/google/callback` — valida el `state`, canjea el `code`
  servidor-a-servidor (con el `client_secret`) y emite la sesión.

Dirigido por el backend, no por el frontend: el `client_secret` y el canje del
código nunca tocan el navegador. El callback vive **bajo `/auth`** a propósito,
porque la cookie de refresh se emite con `Path=/auth` (ADR-011); montarlo fuera
haría que el navegador no la devolviese luego a `/auth/refresh`.

### 2. Identidad: `google_sub` como columna de `users`, no tabla aparte

Columna `users.google_sub` (`String(255)`, **nullable**, **UNIQUE**, indexada).

- **Nullable** porque la mayoría de cuentas siguen siendo de contraseña; SQLite y
  Postgres admiten múltiples `NULL` en una columna `UNIQUE`, así que conviven sin
  problema.
- **UNIQUE** para que una identidad de Google no pueda apuntar a dos cuentas.

Se descarta una tabla `oauth_identities` **por ahora**: solo hay un proveedor
externo previsto, y esa tabla solo paga su complejidad (join, repo y cascade
extra) cuando un usuario puede tener varias identidades. La migración es un
`ADD COLUMN` nullable, no disruptivo. Si entra un segundo proveedor, se extrae
entonces.

Se identifica por el **`sub`** de Google, nunca por el email: el `sub` es estable
aunque el usuario cambie de email. Corolario: en logins sucesivos el email
guardado **no** se actualiza (podría chocar con el `UNIQUE` de otra cuenta).

### 3. Sin Authlib: cliente propio con httpx + pyjwt

`authlib.integrations.starlette_client` es async-first y guarda el `state` en la
sesión de Starlette, lo que obligaría a añadir `authlib` **+ `itsdangerous` +
`SessionMiddleware`** y a convertir los handlers en `async def`, rompiendo la
uniformidad síncrona de toda la aplicación (SQLAlchemy sync, todos los handlers
`def`).

El flujo son dos operaciones —construir una URL y hacer un `POST`—, así que se
implementan en `coach/auth/google.py` con **httpx** y **pyjwt**, que ya eran
dependencias. **Cero dependencias nuevas.** El módulo no conoce FastAPI ni
SQLAlchemy y recibe las credenciales por constructor, así que se testea con
valores ficticios y sin red.

### 4. `state` anti-CSRF por double-submit cookie

El `state` (32 bytes de `secrets.token_urlsafe`) viaja a la vez en la URL de
Google y en una cookie httpOnly de vida corta (10 min, `Path=/auth`). El callback
exige que ambos coincidan (`secrets.compare_digest`). Sin tabla, sin estado en
servidor y sin `SessionMiddleware`.

`SameSite=Lax` basta porque el callback llega como **navegación GET de nivel
superior** desde Google, caso en el que Lax sí envía la cookie (mismo
razonamiento que ADR-011).

### 5. Firma del `id_token`: no se verifica, y es deliberado

El `id_token` no llega por el navegador sino **directamente del token endpoint de
Google sobre TLS con el servidor autenticado**. OIDC Core §3.1.3.7 (punto 6)
permite exactamente ese caso: el propio TLS sustituye a la validación de firma.
Así se evita descargar y cachear el JWKS de Google.

Lo que **sí** se valida siempre, porque es lo que impide aceptar un token ajeno o
caducado: `iss` (lo emitió Google), `aud` (se emitió para ESTA aplicación) y
`exp`. Hay tests que lo comprueban uno por uno.

### 6. Resolución de usuario: find-or-link-or-create

En `AuthService.login_with_google(identity)`, por orden:

0. Si `email_verified` es **false** → rechazo (ver §7).
1. ¿Existe una cuenta con ese `google_sub`? → es él, se emite sesión.
2. ¿Existe una cuenta con ese email? → **vincular** (guardar el `google_sub`) y
   emitir sesión. Salvo que esa cuenta ya tenga **otro** `google_sub`: entonces
   se rechaza, para no sobrescribir el vínculo de otra identidad.
3. Si no existe ninguna → crear cuenta con ese `google_sub` y `password_hash=NULL`.

La sesión se emite reutilizando `AuthService._issue_tokens`, el mismo método que
usa el login por contraseña: **cero duplicación de la lógica de sesión**.

### 7. Guardarraíl: sin `email_verified` no se entra

Si Google no certifica el email, **se rechaza siempre**, exista o no la cuenta.

Vincular por un email no probado sería un secuestro de cuentas: bastaría con
declarar el email de otra persona. Y "crear una cuenta nueva" no es alternativa
cuando el email ya está registrado, porque `users.email` es `UNIQUE`. Una regla
única —y no una excepción por caso— es más fácil de razonar, de auditar y de
testear. En la práctica Google devuelve `true` para cuentas normales.

El claim se normaliza de forma conservadora (`true`/`"true"` → `True`; cualquier
otra cosa → `False`): ante lo inesperado, se falla hacia el lado seguro.

### 8. El access token nunca viaja en la URL

El callback **solo** deja la cookie httpOnly de refresh y redirige a
`{FRONTEND_ORIGIN}/auth/google/callback`. El frontend obtiene el access token con
el `POST /auth/refresh` que ya existe y ya sabe usar.

Se descarta el patrón habitual de devolverlo en el fragmento
(`#access_token=...`) porque dejaría un token válido en la barra de direcciones y
en el historial del navegador.

### 9. Códigos de respuesta

- Fallo de `state` (ausente o no coincide) → **400 JSON**. Es un fallo de
  protocolo o un intento de CSRF: no se redirige nunca.
- Cualquier otro desenlace fallido (el usuario canceló, falló el canje, email no
  verificado, cuenta ya vinculada) → **302** a
  `{FRONTEND_ORIGIN}/auth/google/callback?error=<slug>`, para que el frontend
  muestre un mensaje. Quien llega aquí es un navegador, no un cliente de la API:
  un 4xx crudo sería una página en blanco. En ninguno de estos casos se emite
  sesión ni cookie de refresh.
- Credenciales de Google no configuradas → **503**. El login con Google es
  opcional: la aplicación arranca sin él y solo falla el endpoint que lo necesita.

## Consecuencias

**A favor**
- Una cuenta, dos formas de entrar: quien se registró con contraseña y luego usa
  Google acaba en la MISMA cuenta, con sus planes y su perfil intactos.
- Ninguna dependencia nueva; la aplicación sigue siendo síncrona de punta a punta.
- La sesión es indistinguible de la del login por contraseña: `/auth/refresh`,
  `/auth/logout` y la rotación funcionan sin cambios.

**En contra / a vigilar**
- Una cuenta creada por Google no tiene contraseña, así que **no puede borrarse**
  por `DELETE /me` (que exige reautenticación por contraseña, ADR-008). Queda
  pendiente: o un "establecer contraseña", o una reautenticación por Google.
- No hay desvinculación (`unlink`) ni gestión de varias identidades por usuario.
- Si Google cambia el `sub` de una cuenta (no lo hace, pero es una suposición
  externa), el usuario acabaría con una cuenta duplicada.

## Alternativas descartadas

| Alternativa | Por qué no |
| --- | --- |
| Tabla `oauth_identities` | Complejidad que solo se paga con varios proveedores por usuario. |
| Authlib | Async-first + `SessionMiddleware` + 2 dependencias; rompe el patrón sync. |
| `state` firmado como JWT | El double-submit con cookie ya da integridad y caducidad sin claims que gestionar. |
| Access token en el fragmento de la URL | Deja un token válido en el historial del navegador. |
| Flujo dirigido por el frontend (token de Google al backend) | Obliga a validar firma con JWKS y expone más superficie en el cliente. |
| Vincular con `email_verified=false` si el email coincide | Secuestro de cuentas trivial. |
