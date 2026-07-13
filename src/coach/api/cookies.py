"""Helpers centralizados para el transporte del refresh token vía cookie httpOnly.

`set_refresh_cookie` y `clear_refresh_cookie` DEBEN compartir los mismos
atributos (path, domain, samesite, secure): es el requisito para que
`delete_cookie` borre efectivamente la cookie puesta por `set_cookie`.
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
