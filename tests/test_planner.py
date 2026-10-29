"""Tests para la limpieza de referencias a fragmentos de src/coach/graph/nodes/planner.py.

Tests deterministas que no llaman a Ollama ni a Chroma: ejercitan los helpers
puros del Planificador construyendo sus entradas a mano.

Estructura: Arrange – Act – Assert (AAA).
"""

from __future__ import annotations

import pytest

from coach.graph.nodes.planner import _clean_plan_text, _strip_fragment_refs
from coach.graph.state import Citation, Swap, WeeklyPlan

# ---------------------------------------------------------------------------
# _strip_fragment_refs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Haz X (fragmento 1)", "Haz X"),
        ("Haz X (fragmento 1, fragmento 2)", "Haz X"),
        ("Haz X (fragmentos 1 y 2)", "Haz X"),
        ("Haz X (Fragmento 3).", "Haz X."),
        ("Haz X [2].", "Haz X."),
        ("Haz X (fragmento [1]) y luego Y", "Haz X y luego Y"),
    ],
)
def test_strip_fragment_refs_removes_references(text: str, expected: str) -> None:
    # Arrange: texto con referencia interna a fragmentos (parametrizado)

    # Act
    result = _strip_fragment_refs(text)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "text",
    [
        "Sal a caminar 20 minutos después de comer (10 min de margen).",
        "Lee un fragmento en voz alta (un fragmento corto de tu libro favorito).",
        "  Texto con espacios que no se tocan  ",
    ],
)
def test_strip_fragment_refs_keeps_text_without_references(text: str) -> None:
    # Arrange: texto sin referencias a fragmentos (parametrizado)

    # Act
    result = _strip_fragment_refs(text)

    # Assert
    assert result == text


# ---------------------------------------------------------------------------
# _clean_plan_text
# ---------------------------------------------------------------------------


def test_clean_plan_text_cleans_visible_fields_and_keeps_citations() -> None:
    # Arrange
    citations = [Citation(source="Principios de OffBloom", chunk_id="sustituir::0")]
    plan = WeeklyPlan(
        weekly_focus="Recuperar las noches (fragmento 1)",
        intentions=["Dejar el móvil fuera del dormitorio (fragmentos 1 y 2)", "Leer más"],
        swaps=[Swap(habit="Scroll nocturno [2]", alternative="Leer en papel (fragmento 2)")],
        citations=citations,
    )

    # Act
    cleaned = _clean_plan_text(plan)

    # Assert
    assert cleaned.weekly_focus == "Recuperar las noches"
    assert cleaned.intentions == ["Dejar el móvil fuera del dormitorio", "Leer más"]
    assert cleaned.swaps == [Swap(habit="Scroll nocturno", alternative="Leer en papel")]
    assert cleaned.citations == citations
