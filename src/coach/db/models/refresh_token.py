"""Modelo ORM para la tabla `refresh_tokens`.

Persiste los refresh tokens rotativos para habilitar logout real y revocación
global de sesiones (ADR-007). Solo se guarda el hash del token, nunca el valor
en claro.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coach.db.base import Base

if TYPE_CHECKING:
    from coach.db.models.user import User


class RefreshToken(Base):
    """Refresh token rotativo con estado de revocación y expiración."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Solo el hash del token (Argon2 o SHA-256); el valor en claro nunca se persiste
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")
