"""Repositorios de acceso a datos.

Cada repo recibe una sesión SQLAlchemy en su constructor y encapsula las queries
de su entidad. Ningún repo hace commit/rollback — esa responsabilidad es del
handler (Decisión D4, Pattern B). Los repos usan add/flush/refresh.

Regla de aislamiento (ADR-007): toda query autenticada filtra por user_id.
El acceso a un recurso ajeno devuelve None → el handler responde 404 (no 403).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from coach.db.enums import ActivityProgressStatus
from coach.db.models.activity_progress import ActivityProgress
from coach.db.models.plan import Plan
from coach.db.models.profile import Profile
from coach.db.models.refresh_token import RefreshToken
from coach.db.models.user import User


class UserRepo:
    """Operaciones CRUD sobre la tabla `users`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        """Busca un usuario por email (normalizado a minúsculas)."""
        return self.db.query(User).filter(User.email == email.lower()).first()

    def get_by_id(self, user_id: str) -> User | None:
        """Busca un usuario por su id."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_google_sub(self, google_sub: str) -> User | None:
        """Busca un usuario por su identidad de Google (claim `sub`).

        El `sub` es el identificador estable de la cuenta en Google: no cambia
        aunque el usuario cambie de email, por eso es él —y no el email— quien
        identifica al usuario en el login con Google (ADR-009).
        """
        return self.db.query(User).filter(User.google_sub == google_sub).first()

    def create(
        self,
        email: str,
        password_hash: str | None = None,
        google_sub: str | None = None,
    ) -> User:
        """Crea un nuevo usuario con el email normalizado a minúsculas.

        Una cuenta creada vía Google llega con password_hash=None y google_sub
        informado; una de email+contraseña, al revés.

        No hace commit: llama a flush para obtener el id asignado y refresca
        el objeto. El commit lo hace el handler.
        """
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            password_hash=password_hash,
            google_sub=google_sub,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def link_google_sub(self, user: User, google_sub: str) -> User:
        """Vincula una identidad de Google a una cuenta ya existente.

        Quien llama debe haber comprobado antes que el email de Google está
        verificado y que la cuenta no tiene ya otro google_sub (ADR-009).
        No hace commit; el handler es responsable.
        """
        user.google_sub = google_sub
        self.db.flush()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        """Borra el usuario y, en cascada, todo lo suyo.

        La cascada la resuelve el ORM: `User` declara sus cuatro relaciones
        (perfil, planes, refresh tokens y progreso) con
        `cascade="all, delete-orphan"`, así que SQLAlchemy emite los DELETE
        de las tablas hijas antes que el del usuario. No depende del
        ON DELETE CASCADE del esquema (ver docs/known-issues.md).

        No hace commit: el handler decide cuándo cerrar la transacción.
        """
        self.db.delete(user)
        self.db.flush()


class ProfileRepo:
    """Operaciones de lectura y upsert sobre la tabla `profiles`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: str) -> Profile | None:
        """Devuelve el perfil del usuario o None si aún no existe."""
        return self.db.query(Profile).filter(Profile.user_id == user_id).first()

    def upsert(self, user_id: str, data: dict, schema_version: int = 1) -> Profile:
        """Crea o actualiza el perfil del usuario (idempotente).

        data debe contener: goals, interests, constraints, lang.
        schema_version se incrementa (o se usa el valor pasado) al actualizar.
        No hace commit; el handler es responsable.
        """
        profile = self.get_by_user_id(user_id)
        if profile is None:
            profile = Profile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                goals=data.get("goals", []),
                interests=data.get("interests", []),
                constraints=data["constraints"],
                lang=data.get("lang", "ES"),
                schema_version=schema_version,
            )
            self.db.add(profile)
        else:
            profile.goals = data.get("goals", profile.goals)
            profile.interests = data.get("interests", profile.interests)
            profile.constraints = data["constraints"]
            profile.lang = data.get("lang", profile.lang)
            profile.schema_version = schema_version
        self.db.flush()
        self.db.refresh(profile)
        return profile


class PlanRepo:
    """Operaciones de escritura y lectura sobre la tabla `plans`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, plan: Plan) -> Plan:
        """Persiste un Plan ORM ya construido (por el mapper).

        No hace commit; el handler es responsable.
        """
        self.db.add(plan)
        self.db.flush()
        self.db.refresh(plan)
        return plan

    def get_by_id(self, plan_id: str, user_id: str) -> Plan | None:
        """Devuelve el plan si pertenece al usuario indicado, o None.

        Filtrar por AMBOS campos garantiza el aislamiento entre usuarios:
        un plan ajeno devuelve None → el handler responde 404 (ADR-007).
        """
        return self.db.query(Plan).filter(Plan.id == plan_id, Plan.user_id == user_id).first()

    def list_by_user(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Plan]:
        """Lista los planes del usuario ordenados por fecha descendente.

        Usa el índice compuesto ix_plans_user_id_created_at para eficiencia.
        """
        return (
            self.db.query(Plan)
            .filter(Plan.user_id == user_id)
            .order_by(Plan.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


class ActivityProgressRepo:
    """Operaciones sobre la tabla `activity_progresses`.

    La identidad de una actividad es su posición en el array inmutable
    Plan.activities (ADR-008), de ahí que la clave funcional sea
    (plan_id, activity_index) — respaldada por uq_progress_plan_activity.

    El repo no comprueba propiedad: quien llama ya ha resuelto el plan con
    PlanRepo.get_by_id(plan_id, user_id), que garantiza el aislamiento.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_plan(self, plan_id: str) -> list[ActivityProgress]:
        """Devuelve todas las filas de progreso registradas para un plan."""
        return self.db.query(ActivityProgress).filter(ActivityProgress.plan_id == plan_id).all()

    def upsert(
        self,
        plan_id: str,
        user_id: str,
        activity_index: int,
        status: ActivityProgressStatus,
    ) -> ActivityProgress:
        """Crea o actualiza el progreso de una actividad (idempotente).

        Repetir la llamada con el mismo status no duplica filas ni cambia el
        estado. No hace commit; el handler es responsable.
        """
        progress = (
            self.db.query(ActivityProgress)
            .filter(
                ActivityProgress.plan_id == plan_id,
                ActivityProgress.activity_index == activity_index,
            )
            .first()
        )
        if progress is None:
            progress = ActivityProgress(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                user_id=user_id,
                activity_index=activity_index,
                status=status,
            )
            self.db.add(progress)
        else:
            progress.status = status
        self.db.flush()
        self.db.refresh(progress)
        return progress


class RefreshTokenRepo:
    """Operaciones sobre la tabla `refresh_tokens`.

    Solo persiste el hash del token (nunca el valor en claro), y expone las
    operaciones necesarias para la rotación y revocación de sesiones (ADR-007).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: str, token_hash: str, expires_at: datetime) -> RefreshToken:
        """Persiste un refresh token nuevo a partir de su hash.

        No hace commit; el handler es responsable.
        """
        refresh_token = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        self.db.flush()
        self.db.refresh(refresh_token)
        return refresh_token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Busca un refresh token por su hash almacenado."""
        return self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    def revoke(self, token: RefreshToken) -> None:
        """Marca un refresh token como revocado (no elimina el registro)."""
        token.revoked = True
        self.db.flush()

    def revoke_all_for_user(self, user_id: str) -> None:
        """Revoca todos los refresh tokens activos de un usuario.

        Útil para invalidar todas las sesiones (p.ej. tras un cambio de
        contraseña o una detección de compromiso de cuenta).
        """
        tokens = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .all()
        )
        for token in tokens:
            token.revoked = True
        self.db.flush()
