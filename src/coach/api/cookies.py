"""Helpers centralizados para las cookies httpOnly de autenticación.

Dos pares: el refresh token (la sesión) y el `state` anti-CSRF del flujo OAuth.
En cada par, el `set_*` y el `clear_*` DEBEN compartir los mismos atributos
(path, domain, samesite, secure): es el requisito para que `delete_cookie`
borre efectivamente la cookie puesta por `set_cookie`.
"""

from __future__ import annotations

from fastapi import Response

from coach.config import settings


def set_refresh_cookie(response: Response, token: str) -> None:
    """Adjunta el refresh token como cookie httpOnly en la respuesta."""
    response.set_cookie(
        key=settings.cookie_refresh_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Borra la cookie de refresh token (logout)."""
    response.delete_cookie(
        key=settings.cookie_refresh_name,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        httponly=True,
    )


def set_oauth_state_cookie(response: Response, state: str) -> None:
    """Guarda el `state` anti-CSRF del flujo OAuth en una cookie efímera.

    SameSite=Lax (el valor por defecto de la app) es suficiente: el callback de
    Google llega como navegación GET de nivel superior, caso en el que Lax SÍ
    envía la cookie. El TTL es corto (minutos) porque solo tiene que sobrevivir
    a la pantalla de consentimiento.
    """
    response.set_cookie(
        key=settings.cookie_oauth_state_name,
        value=state,
        max_age=settings.oauth_state_expire_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )


def clear_oauth_state_cookie(response: Response) -> None:
    """Borra la cookie de `state` (siempre, tras consumirla en el callback)."""
    response.delete_cookie(
        key=settings.cookie_oauth_state_name,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        httponly=True,
    )
