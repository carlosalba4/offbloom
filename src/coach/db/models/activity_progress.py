"""Modelo ORM para la tabla `activity_progresses`.

Registra el estado PENDING/DONE/SKIPPED de cada actividad de un Plan.
La identidad de la actividad es su posición (activity_index) en el array
snapshotado de Plan.activities — no se añade id a CuratedActivity (ADR-008).

user_id se denormaliza para permitir filtros de propiedad directos sin JOIN.
La restricción única (plan_id, activity_index) garantiza un registro por
actividad por plan.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coach.db.base import Base
from coach.db.enums import ActivityProgressStatus

if TYPE_CHECKING:
    from coach.db.models.plan import Plan
    from coach.db.models.user import User


class ActivityProgress(Base):
    """Progreso de una actividad individual dentro de un plan del coach."""

    __tablename__ = "activity_progresses"
    __table_args__ = (
        UniqueConstraint("plan_id", "activity_index", name="uq_progress_plan_activity"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Denormalizado desde Plan.user_id para autorización directa sin JOIN
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Índice en el array Plan.activities (inmutable); identifica la actividad
    activity_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ActivityProgressStatus] = mapped_column(
        SAEnum(ActivityProgressStatus, native_enum=False),
        default=ActivityProgressStatus.PENDING,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    plan: Mapped[Plan] = relationship("Plan", back_populates="activity_progresses")
    user: Mapped[User] = relationship("User", back_populates="activity_progresses")
