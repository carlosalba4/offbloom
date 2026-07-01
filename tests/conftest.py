"""Fixtures compartidas para la suite de tests de persistencia.

Usa SQLite en memoria (StaticPool) para garantizar aislamiento total:
nunca toca offbloom.db ni ningún archivo de desarrollo.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import coach.db.models  # noqa: F401  — registra todas las tablas en Base.metadata
from coach.db.base import Base
from coach.graph.state import (
    CategoryUsage,
    Constraints,
    EnergyLevel,
    Lang,
    Place,
    SocialPreference,
    TimeOfDay,
    UsageData,
    UserProfile,
)


@pytest.fixture()
def db_session() -> Session:
    """Sesión SQLAlchemy sobre SQLite en memoria, con scope de función.

    Crea el schema al inicio y lo destruye al final para garantizar que
    cada test parte de un estado limpio.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Helpers de dominio reutilizados en varios archivos de test
# ---------------------------------------------------------------------------


def make_profile(
    lang: Lang = Lang.ES,
    goals: list[str] | None = None,
    interests: list[str] | None = None,
) -> UserProfile:
    """Construye un UserProfile válido para tests."""
    return UserProfile(
        goals=goals or ["reducir tiempo de pantalla"],
        interests=interests or ["lectura", "senderismo"],
        constraints=Constraints(
            available_minutes=45,
            energy=EnergyLevel.MEDIUM,
            place=Place.HOME,
            social=SocialPreference.SOLO,
        ),
        lang=lang,
    )


def make_usage() -> UsageData:
    """Construye un UsageData válido para tests."""
    return UsageData(
        categories=[CategoryUsage(category="redes_sociales", minutes_per_day=90)],
        peak_windows=[TimeOfDay.EVENING],
        self_reported_triggers=["aburrimiento"],
    )
