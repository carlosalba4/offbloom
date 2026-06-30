"""Modelo ORM para la tabla `profiles`.

Relación 1-1 con User. Guarda los objetivos, intereses, restricciones e idioma
del usuario en columnas JSON para portabilidad SQLite → Postgres.
schema_version permite evolucionar la forma del perfil de forma controlada (ADR-008).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coach.db.base import Base

if TYPE_CHECKING:
    from coach.db.models.user import User


class Profile(Base):
    """Perfil persistente del usuario: objetivos, intereses, restricciones, idioma."""

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # unique=True garantiza la cardinalidad 1-1 con User
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    goals: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    interests: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # constraints es obligatorio (sin valor por defecto): debe proveerse siempre
    constraints: Mapped[dict] = mapped_column(JSON, nullable=False)
    lang: Mapped[str] = mapped_column(String(8), default="ES", nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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

    user: Mapped[User] = relationship("User", back_populates="profile")
