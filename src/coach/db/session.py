"""Session factory y generador get_db() para inyección por dependencia en FastAPI.

Decisión D4 (plan aprobado): el COMMIT lo hace el handler (Pattern B).
get_db solo hace rollback ante excepción y close en finally. Los repos NO hacen
commit; usan add/flush/refresh.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from coach.db.engine import engine

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Generador síncrono que abre una sesión por request y la cierra al final.

    Patrón de uso como dependencia FastAPI (vía Depends) o directamente en tests.
    El commit lo hace siempre el handler tras la lógica de negocio.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
