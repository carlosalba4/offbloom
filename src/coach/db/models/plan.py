"""Modelo ORM para la tabla `plans`.

Cada ejecución del coach produce un Plan inmutable. Los campos plan/activities/
derivation se guardan como snapshot JSON (ADR-008). Nunca se persiste el
RiskSignal interno; solo el DerivationMessage cuando status=DERIVED.

El índice compuesto (user_id, created_at) optimiza las consultas de historial
paginado (GET /plans), que ordena por created_at DESC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coach.db.base import Base
from coach.db.enums import PlanStatus

if TYPE_CHECKING:
    from coach.db.models.activity_progress import ActivityProgress
    from coach.db.models.user import User


class Plan(Base):
    """Snapshot inmutable de una ejecución del coach para un usuario."""

    __tablename__ = "plans"
    __table_args__ = (
        # Índice compuesto para historial paginado ordenado por fecha
        Index("ix_plans_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[PlanStatus] = mapped_column(
        SAEnum(PlanStatus, native_enum=False),
        nullable=False,
    )
    # Snapshots de entrada: permiten auditar con qué perfil/uso se generó el plan
    input_profile_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_usage_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Salida del coach (vacíos cuando status=DERIVED)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    activities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Presente solo cuando status=DERIVED; contiene únicamente DerivationMessage
    derivation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Lista de errores acumulados por los nodos del grafo (puede ser vacía)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    # Campos de auditoría: correlacionan el plan con su traza y el modelo usado
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="plans")
    activity_progresses: Mapped[list[ActivityProgress]] = relationship(
        "ActivityProgress",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
