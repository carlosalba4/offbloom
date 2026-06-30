"""Modelo ORM para la tabla `users`.

Representa una cuenta de usuario. password_hash es nullable para preparar OAuth
futuro (ADR-007) sin migración disruptiva. Todas las entidades hijas se vinculan
mediante ON DELETE CASCADE (ADR-008).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coach.db.base import Base

if TYPE_CHECKING:
    from coach.db.models.activity_progress import ActivityProgress
    from coach.db.models.plan import Plan
    from coach.db.models.profile import Profile
    from coach.db.models.refresh_token import RefreshToken


class User(Base):
    """Cuenta de usuario: credenciales, estado activo y relaciones hija."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # La normalización a minúsculas la aplica UserRepo.create, no el ORM.
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relaciones (cascade desde User hacia todas las entidades hija)
    profile: Mapped[Profile | None] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    plans: Mapped[list[Plan]] = relationship(
        "Plan",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # activity_progresses referenciado desde Plan, pero se lista aquí para
    # que el cascade ON DELETE actúe también a nivel de usuario.
    activity_progresses: Mapped[list[ActivityProgress]] = relationship(
        "ActivityProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
