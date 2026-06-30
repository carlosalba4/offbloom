"""Entorno de ejecución de Alembic.

Añade src/ al sys.path para poder importar el paquete coach, lee la URL de la
DB desde Settings (coach.config), e importa Base + todos los modelos ORM para
que autogenerate pueda detectar las tablas.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Ajuste de sys.path: src/ debe estar accesible para importar coach.*
# ---------------------------------------------------------------------------
_src_path = str(Path(__file__).resolve().parents[1] / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# ---------------------------------------------------------------------------
# Imports del proyecto (después del ajuste de sys.path)
# ---------------------------------------------------------------------------
import coach.db.models  # noqa: E402, F401 — registra tablas en Base.metadata
from coach.config import settings  # noqa: E402
from coach.db.base import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración de Alembic
# ---------------------------------------------------------------------------
alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Sobreescribe la URL con la de Settings (ignora el placeholder de alembic.ini)
alembic_config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Funciones de migración
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Ejecuta las migraciones en modo offline (sin conexión real a la DB)."""
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones en modo online (con conexión real a la DB)."""
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
