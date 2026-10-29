"""Cliente OIDC de Google para el flujo Authorization Code (ADR-009).

Módulo puro: no conoce FastAPI ni SQLAlchemy. Solo sabe construir la URL de
autorización y canjear un `code` por la identidad del usuario, hablando
servidor-a-servidor con Google mediante httpx síncrono (coherente con el resto
de la aplicación, que es sync de punta a punta).

No se usa Authlib a propósito: su integración con Starlette es async-first y
guarda el `state` en la sesión del framework, lo que obligaría a añadir
SessionMiddleware y a volver asíncronos los handlers. El flujo son dos
operaciones (construir una URL y hacer un POST), así que se implementan aquí
sin dependencias nuevas.

Las credenciales llegan por constructor, nunca leyendo `settings` desde dentro:
así el cliente es testeable con valores ficticios y sin tocar la red.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

# Endpoints públicos de Google (no son secretos; los secretos van en settings).
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Google emite el claim `iss` en cualquiera de estas dos formas.
_VALID_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

# openid -> id_token; email -> claims email/email_verified; profile -> name.
SCOPE = "openid email profile"

_HTTP_TIMEOUT_SECONDS = 10.0


class GoogleOAuthError(Exception):
    """Falló el diálogo con Google o la identidad recibida no es utilizable."""


@dataclass(frozen=True)
class GoogleIdentity:
    """Identidad verificada que Google devuelve en el `id_token`.

    `sub` es el identificador estable de la cuenta: no cambia aunque el usuario
    cambie su email, por eso es él quien identifica al usuario (nunca el email).
    """

    sub: str
    email: str
    email_verified: bool
    name: str | None = None


def _coerce_email_verified(value: Any) -> bool:
    """Normaliza `email_verified`, que Google puede enviar como bool o string.

    Ante cualquier valor inesperado devuelve False: el guardarraíl de
    vinculación debe fallar hacia el lado seguro.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


class GoogleOAuthClient:
    """Cliente del Authorization Code Flow de Google, síncrono y sin estado."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout: float = _HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self._client_secret = client_secret
        self._timeout = timeout

    def build_authorization_url(self, state: str) -> str:
        """Construye la URL de consentimiento de Google para un `state` dado.

        `access_type=online` porque no necesitamos refresh token de Google: la
        sesión de la aplicación es nuestra (JWT + refresh propio) y a Google
        solo se le pregunta la identidad una vez, al entrar.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, code: str) -> GoogleIdentity:
        """Canjea el `code` por el `id_token` y extrae de él la identidad.

        El canje va servidor-a-servidor e incluye el client_secret, así que el
        `code` que llega por el navegador no basta para suplantar a nadie.
        Lanza GoogleOAuthError ante cualquier fallo de red, respuesta no-200 o
        token malformado.
        """
        try:
            with httpx.Client(timeout=self._timeout) as http:
                response = http.post(
                    TOKEN_ENDPOINT,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise GoogleOAuthError("No se pudo contactar con Google") from exc

        if response.status_code != httpx.codes.OK:
            raise GoogleOAuthError(
                f"Google rechazó el canje del código (HTTP {response.status_code})"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleOAuthError("Respuesta de Google ilegible") from exc

        id_token = payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise GoogleOAuthError("Google no devolvió un id_token")

        return self.identity_from_id_token(id_token)

    def identity_from_id_token(self, id_token: str) -> GoogleIdentity:
        """Valida el `id_token` y lo convierte en GoogleIdentity.

        NO se verifica la FIRMA del token, y es deliberado: el token no llega
        por el navegador sino directamente del token endpoint de Google sobre
        un canal TLS con el servidor autenticado. OIDC Core §3.1.3.7 (punto 6)
        permite exactamente este caso —el propio TLS sustituye a la validación
        de firma— y así se evita descargar y cachear el JWKS de Google.

        Lo que sí se valida siempre, porque es lo que impide aceptar un token
        ajeno o caducado: `iss` (lo emitió Google), `aud` (se emitió para ESTA
        aplicación) y `exp` (sigue vigente).
        """
        try:
            claims = jwt.decode(
                id_token,
                audience=self.client_id,
                options={
                    "verify_signature": False,
                    "verify_aud": True,
                    "verify_exp": True,
                    "require": ["exp", "iss", "aud", "sub"],
                },
            )
        except jwt.PyJWTError as exc:
            raise GoogleOAuthError("El id_token de Google no es válido") from exc

        if claims.get("iss") not in _VALID_ISSUERS:
            raise GoogleOAuthError("El id_token no lo emitió Google")

        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise GoogleOAuthError("El id_token no trae un `sub` utilizable")

        email = claims.get("email")
        if not isinstance(email, str) or not email:
            raise GoogleOAuthError("El id_token no trae email (¿falta el scope?)")

        name = claims.get("name")
        return GoogleIdentity(
            sub=sub,
            email=email,
            email_verified=_coerce_email_verified(claims.get("email_verified")),
            name=name if isinstance(name, str) else None,
        )
