"""Enumeraciones de persistencia para las tablas de la DB.

Decisión D3 (ADR-006): se almacenan como VARCHAR con native_enum=False para
garantizar portabilidad SQLite → PostgreSQL sin depender de tipos ENUM nativos.
"""

import enum


class PlanStatus(enum.StrEnum):
    """Estado de un plan generado por el coach."""

    GENERATED = "GENERATED"
    DERIVED = "DERIVED"


class ActivityProgressStatus(enum.StrEnum):
    """Estado de progreso de una actividad dentro de un plan."""

    PENDING = "PENDING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
