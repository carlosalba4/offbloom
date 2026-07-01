"""Primitivas criptográficas puras de autenticación.

Sin dependencias de base de datos ni de FastAPI: solo hashing de contraseñas
(argon2-cffi) y emisión/verificación de tokens (pyjwt + sha256 para refresh).
Toda la lógica de orquestación (repos, casos de uso) vive en `service.py`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from coach.config import settings

_password_hasher = PasswordHasher()

# Hash precomputado de una contraseña ficticia. Se usa para que el flujo de
# login tarde lo mismo exista o no el usuario (mitiga ataques de timing que
# revelarían si un email está registrado).
_DUMMY_HASH: str = _password_hasher.hash("dummy-password-for-constant-time-check")


class InvalidTokenError(Exception):
    """Se lanza cuando un access token es inválido, ha expirado o tiene un
    tipo de claim inesperado. Envuelve los errores concretos de pyjwt para
    no filtrar detalles de la librería subyacente a las capas superiores.
    """


def hash_password(password: str) -> str:
    """Genera el hash argon2 de una contraseña en claro."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una contraseña en claro contra su hash argon2.

    Devuelve False ante cualquier mismatch o hash malformado, sin propagar
    la excepción (la capa de servicio decide qué hacer con el resultado).
    """
    try:
        _password_hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def create_access_token(user_id: str) -> str:
    """Emite un access token JWT firmado con HS256.

    Claims: sub (id de usuario), iat, exp (según settings) y type="access".
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decodifica y valida un access token, devolviendo el `sub` (user id).

    Lanza InvalidTokenError si la firma es inválida, el token ha expirado o
    el claim `type` no es "access".
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token inválido o expirado") from exc

    if payload.get("type") != "access":
        raise InvalidTokenError("Tipo de token inesperado")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Token sin claim 'sub' válido")

    return subject


def generate_refresh_token() -> str:
    """Genera un refresh token opaco y criptográficamente aleatorio."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Calcula el digest SHA-256 de un refresh token para persistirlo.

    El valor en claro nunca se guarda: solo este hash determinista permite
    localizarlo de nuevo en la base de datos al presentarlo el cliente.
    """
    return hashlib.sha256(token.encode()).hexdigest()
