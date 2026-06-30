"""Creación del engine SQLAlchemy a partir de la URL configurada en Settings.

- SQLite: añade check_same_thread=False para compatibilidad con el threadpool
  de FastAPI (cada request corre en un hilo distinto).
- PostgreSQL u otro: no se pasan connect_args especiales.
"""

from sqlalchemy import create_engine

from coach.config import settings

# check_same_thread solo aplica a SQLite (los demás drivers no lo soportan)
_connect_args: dict = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
