"""Tests de fronteras arquitectónicas — REGLA DE ORO AUTOMATIZADA.

Garantizan que los módulos de dominio (graph/, rag/) NO importan coach.db,
y que la única dirección permitida (db → graph) está documentada por la
presencia de la importación en mappers.py.

ADR-006: las capas de dominio son independientes de la persistencia.
Estructura AAA. Comentarios en español, nombres en inglés.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Ruta base del paquete coach calculada relativa a este archivo de test
_COACH_ROOT = Path(__file__).resolve().parents[1] / "src" / "coach"

# Patrón que detecta cualquier importación de coach.db
_IMPORT_DB_PATTERN = re.compile(r"^\s*(import coach\.db|from coach\.db)", re.MULTILINE)


def _collect_python_files(directory: Path) -> list[Path]:
    """Devuelve todos los .py bajo el directorio dado (recursivo)."""
    return list(directory.rglob("*.py"))


# ===========================================================================
# Regla: graph/ y rag/ no pueden importar coach.db
# ===========================================================================


class TestDomainDoesNotImportDb:
    def test_graph_modules_do_not_import_coach_db(self):
        # Arrange
        graph_dir = _COACH_ROOT / "graph"
        assert graph_dir.exists(), f"Directorio graph/ no encontrado en {graph_dir}"
        py_files = _collect_python_files(graph_dir)

        # Act + Assert — cualquier archivo infractor falla el test con nombre explícito
        infractors = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if _IMPORT_DB_PATTERN.search(source):
                infractors.append(str(py_file))

        assert infractors == [], (
            "Los siguientes archivos de graph/ importan coach.db en violación de ADR-006:\n"
            + "\n".join(f"  - {f}" for f in infractors)
        )

    def test_rag_modules_do_not_import_coach_db(self):
        # Arrange
        rag_dir = _COACH_ROOT / "rag"

        # Tolerancia: si rag/ aún no existe se marca como skip (no fallo)
        if not rag_dir.exists():
            pytest.skip("Directorio rag/ no encontrado; se omite el test.")

        py_files = _collect_python_files(rag_dir)

        # Act + Assert
        infractors = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if _IMPORT_DB_PATTERN.search(source):
                infractors.append(str(py_file))

        assert infractors == [], (
            "Los siguientes archivos de rag/ importan coach.db en violación de ADR-006:\n"
            + "\n".join(f"  - {f}" for f in infractors)
        )


# ===========================================================================
# Sanity check: la dirección permitida db → graph está presente en mappers.py
# ===========================================================================


class TestPermittedDirectionDbToGraph:
    def test_mappers_imports_from_coach_graph_state(self):
        # Arrange
        mappers_file = _COACH_ROOT / "db" / "mappers.py"
        assert mappers_file.exists(), f"mappers.py no encontrado en {mappers_file}"

        # Act
        source = mappers_file.read_text(encoding="utf-8")
        allowed_import_present = "from coach.graph.state import" in source

        # Assert — documenta que db → graph es la única dirección permitida
        assert allowed_import_present, (
            "mappers.py debería importar desde coach.graph.state "
            "(dirección permitida db → graph según ADR-006)."
        )


# ===========================================================================
# Cobertura adicional: ningún archivo de graph/ usa import directo de modelos ORM
# ===========================================================================


class TestGraphDoesNotImportOrmModels:
    def test_graph_does_not_import_orm_models_package(self):
        # Arrange
        graph_dir = _COACH_ROOT / "graph"
        assert graph_dir.exists()
        py_files = _collect_python_files(graph_dir)
        orm_import_pattern = re.compile(
            r"^\s*(import coach\.db\.models|from coach\.db\.models)", re.MULTILINE
        )

        # Act
        infractors = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if orm_import_pattern.search(source):
                infractors.append(str(py_file))

        # Assert
        assert infractors == [], (
            "Los siguientes archivos de graph/ importan modelos ORM directamente:\n"
            + "\n".join(f"  - {f}" for f in infractors)
        )
