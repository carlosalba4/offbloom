"""Paquete de modelos ORM.

Importar este módulo registra todas las tablas en Base.metadata, lo que Alembic
necesita para el autogenerate y lo que create_all() necesita en tests.

El orden de importación respeta el grafo de dependencias de FK:
User → Profile, RefreshToken → Plan → ActivityProgress.
"""

from coach.db.models.activity_progress import ActivityProgress
from coach.db.models.plan import Plan
from coach.db.models.profile import Profile
from coach.db.models.refresh_token import RefreshToken
from coach.db.models.user import User

__all__ = ["User", "Profile", "RefreshToken", "Plan", "ActivityProgress"]
