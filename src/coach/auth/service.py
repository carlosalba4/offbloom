"""Casos de uso de autenticación: registro, login (contraseña o Google), refresh,
logout y baja de cuenta.

`AuthService` orquesta los repositorios de persistencia y las primitivas de
`security.py`. Nunca hace commit (Pattern B / Decisión D4): esa
responsabilidad es del handler que invoca al servicio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from coach.auth.google import GoogleIdentity
from coach.auth.security import (
    _DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from coach.config import settings
from coach.db.models.user import User
from coach.db.repositories import RefreshTokenRepo, UserRepo


class EmailAlreadyExists(Exception):
    """El email ya está registrado por otra cuenta."""


class InvalidCredentials(Exception):
    """Email o contraseña incorrectos (mensaje genérico, no distingue caso)."""


class InvalidRefreshToken(Exception):
    """El refresh token no existe, está revocado o ha expirado."""


class UnverifiedGoogleEmail(Exception):
    """Google no certifica que el usuario sea dueño del email que declara."""


class GoogleAccountAlreadyLinked(Exception):
    """La cuenta con ese email ya está vinculada a OTRA identidad de Google."""


def _as_aware_utc(value: datetime) -> datetime:
    """Normaliza un datetime a aware-UTC.

    SQLite no conserva el offset de zona horaria al releer una columna
    DateTime(timezone=True): el valor vuelve "naive" aunque se guardó en UTC.
    Como esta capa siempre escribe en UTC, es seguro asumir UTC si falta tzinfo.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class AuthService:
    """Orquesta el registro, login, rotación de refresh tokens, logout y baja."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepo(db)
        self.refresh_tokens = RefreshTokenRepo(db)

    def register(self, email: str, password: str) -> User:
        """Crea una cuenta nueva con contraseña hasheada.

        Lanza EmailAlreadyExists si el email ya está en uso.
        """
        if self.users.get_by_email(email) is not None:
            raise EmailAlreadyExists("Ese email ya está registrado")

        return self.users.create(email, hash_password(password))

    def authenticate(self, email: str, password: str) -> tuple[str, str]:
        """Verifica credenciales y emite un par (access_token, refresh_token).

        El refresh token se persiste solo como hash. Ante email inexistente
        o contraseña incorrecta se lanza SIEMPRE InvalidCredentials, con un
        coste temporal equivalente (se verifica contra un hash dummy cuando
        el usuario no existe) para no revelar si el email está registrado.
        """
        user = self.users.get_by_email(email)

        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentials("Credenciales inválidas")

        # No se separan con "or" para evitar que el cortocircuito salte
        # verify_password: mantener la llamada en ambas ramas iguala el
        # timing (relevante cuando el usuario viene de OAuth y aún no tiene
        # password_hash).
        if user.password_hash is None:
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentials("Credenciales inválidas")

        if not verify_password(password, user.password_hash):
            raise InvalidCredentials("Credenciales inválidas")

        return self._issue_tokens(user.id)

    def login_with_google(self, identity: GoogleIdentity) -> tuple[str, str]:
        """Resuelve la cuenta que corresponde a una identidad de Google y la loguea.

        Devuelve el MISMO par (access_token, refresh_token) que `authenticate`:
        quien entra por Google acaba con una sesión idéntica a la de contraseña.

        Resolución, en orden (ADR-009):

        1. Si ya hay una cuenta con ese `sub`, es él. El email NO se actualiza
           en logins sucesivos: la identidad es el `sub`, y sobrescribir el
           email podría chocar con el UNIQUE de otra cuenta.
        2. Si no, y existe una cuenta con ese email, se VINCULA (se le guarda
           el `sub`) — salvo que ya tuviera otro `sub` distinto.
        3. Si no existe ninguna, se crea una cuenta nueva sin contraseña.

        GUARDARRAÍL: si Google no ha verificado el email se rechaza de entrada,
        exista o no la cuenta. Vincular por un email no probado permitiría a
        cualquiera que declarase el email de otra persona apropiarse de su
        cuenta; y crear una cuenta con él es imposible de todos modos cuando el
        email ya está registrado, porque `users.email` es UNIQUE.
        """
        if not identity.email_verified:
            raise UnverifiedGoogleEmail("Google no ha verificado ese email")

        existing = self.users.get_by_google_sub(identity.sub)
        if existing is not None:
            return self._issue_tokens(existing.id)

        by_email = self.users.get_by_email(identity.email)
        if by_email is not None:
            if by_email.google_sub is not None:
                raise GoogleAccountAlreadyLinked(
                    "Esa cuenta ya está vinculada a otra identidad de Google"
                )
            self.users.link_google_sub(by_email, identity.sub)
            return self._issue_tokens(by_email.id)

        user = self.users.create(
            email=identity.email,
            password_hash=None,
            google_sub=identity.sub,
        )
        return self._issue_tokens(user.id)

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Rota un refresh token válido: revoca el actual y emite uno nuevo.

        Lanza InvalidRefreshToken si el token no existe, está revocado o
        ha expirado.
        """
        token_hash = hash_refresh_token(refresh_token)
        stored = self.refresh_tokens.get_by_hash(token_hash)

        if stored is None or stored.revoked or _as_aware_utc(stored.expires_at) < datetime.now(UTC):
            raise InvalidRefreshToken("Refresh token inválido o expirado")

        self.refresh_tokens.revoke(stored)
        return self._issue_tokens(stored.user_id)

    def logout(self, refresh_token: str) -> None:
        """Revoca el refresh token indicado, de forma idempotente.

        No lanza si el token no existe o ya estaba revocado: el logout
        siempre "tiene éxito" desde el punto de vista del cliente.
        """
        token_hash = hash_refresh_token(refresh_token)
        stored = self.refresh_tokens.get_by_hash(token_hash)
        if stored is not None:
            self.refresh_tokens.revoke(stored)

    def delete_account(self, user: User, password: str) -> None:
        """Reautentica al usuario por contraseña y borra su cuenta entera.

        El usuario llega ya autenticado por su access token; esta contraseña
        es un paso adicional (step-up) para que un token robado no baste para
        destruir la cuenta. Lanza InvalidCredentials si no coincide, sin haber
        tocado nada.

        Una cuenta sin password_hash (registrada por un proveedor externo) no
        puede reautenticarse por contraseña: se rechaza, verificando igual
        contra el hash dummy para no delatar el caso por el tiempo de respuesta.
        """
        if user.password_hash is None:
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentials("Credenciales inválidas")

        if not verify_password(password, user.password_hash):
            raise InvalidCredentials("Credenciales inválidas")

        self.users.delete(user)

    def _issue_tokens(self, user_id: str) -> tuple[str, str]:
        """Genera y persiste un nuevo par (access, refresh) para un usuario."""
        access = create_access_token(user_id)
        refresh_plaintext = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        self.refresh_tokens.create(
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_plaintext),
            expires_at=expires_at,
        )
        return access, refresh_plaintext
