"""Fixtures compartidas para la suite de tests de persistencia.

Usa SQLite en memoria (StaticPool) para garantizar aislamiento total:
nunca toca offbloom.db ni ningún archivo de desarrollo.
"""

from __future__ import annotations

import os

# Debe fijarse ANTES de cualquier `import coach.*`: Settings() se instancia al
# importar coach.config y jwt_secret_key es obligatorio (sin default).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-production-0123456789")

from typing import Any  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import coach.db.models  # noqa: E402, F401  — registra todas las tablas en Base.metadata
from coach.api import deps  # noqa: E402
from coach.db.base import Base  # noqa: E402
from coach.graph.state import (  # noqa: E402
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


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """Cliente HTTP con get_db sobreescrito para usar la sesión en memoria.

    TestClient se instancia sin entrar en el context manager async, por lo
    que el lifespan (compilación del grafo del coach) nunca se dispara.
    """
    from coach.main import app  # noqa: PLC0415 — import perezoso, tras fijar JWT_SECRET_KEY

    app.dependency_overrides[deps.get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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


def auth_headers(
    client: TestClient,
    email: str = "user@example.com",
    password: str = "password123",
) -> dict[str, str]:
    """Registra (si hace falta) y autentica a un usuario; devuelve el header Bearer.

    Reutiliza el flujo register -> login de test_auth_endpoints.py. Si el email
    ya existe (409), continúa directamente con el login.
    """
    register_resp = client.post("/auth/register", json={"email": email, "password": password})
    assert register_resp.status_code in (201, 409)

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


# ---------------------------------------------------------------------------
# Doble de grafo — inyectable en app.state.graph sin disparar el lifespan real
# ---------------------------------------------------------------------------

# Sentinel — detecta si app.state.graph existía antes del test
_SENTINEL = object()


class _FakeGraph:
    """Doble mínimo de grafo: registra los argumentos de invocación y devuelve/lanza a demanda."""

    def __init__(
        self,
        *,
        returns: Any = None,
        raises: BaseException | None = None,
    ) -> None:
        self._returns = returns
        self._raises = raises
        self.invoked_with: Any = None

    def invoke(self, state: Any, config: Any = None) -> Any:
        self.invoked_with = state
        if self._raises is not None:
            raise self._raises
        return self._returns


@pytest.fixture()
def graph_client(client: TestClient):
    """Factory fixture que inyecta un _FakeGraph en app.state y lo restaura al terminar.

    Uso dentro de un test::

        def test_algo(graph_client):
            fake = graph_client(returns={...})
            resp = client.post("/plans", json=payload, headers=...)

    El valor previo de app.state.graph (si existía) se restaura en el teardown.
    """
    from coach.main import app  # noqa: PLC0415 — import perezoso, tras fijar JWT_SECRET_KEY

    prev = getattr(app.state, "graph", _SENTINEL)

    def _factory(
        *,
        returns: Any = None,
        raises: BaseException | None = None,
    ) -> _FakeGraph:
        fake = _FakeGraph(returns=returns, raises=raises)
        app.state.graph = fake
        return fake

    yield _factory

    if prev is _SENTINEL:
        try:
            del app.state.graph
        except AttributeError:
            pass
    else:
        app.state.graph = prev
