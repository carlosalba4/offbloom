"""Base declarativa de SQLAlchemy 2.0 para todos los modelos ORM del proyecto."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base común que registra todos los modelos en un mismo MetaData."""
