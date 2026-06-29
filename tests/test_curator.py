"""Tests para src/coach/graph/nodes/curator.py.

Tests deterministas que no llaman a Ollama ni a Chroma: ejercitan los helpers
puros del Curador construyendo sus entradas a mano.

Estructura: Arrange – Act – Assert (AAA).
"""

from __future__ import annotations

from coach.graph.nodes.curator import _ActivityChoice, _to_curated
from coach.graph.state import Lang
from coach.rag.store import RetrievedActivity

# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------


def _make_activity() -> RetrievedActivity:
    """Construye un `RetrievedActivity` de prueba con momento "tarde, noche"."""
    return RetrievedActivity(
        id="act-001",
        text="Lectura tranquila antes de dormir.",
        name_es="Lectura nocturna",
        name_en="Night reading",
        category="lectura",
        duration_min=20,
        energy="baja",
        place="casa",
        social="solo",
        materials="un libro",
        replaces=["scroll_nocturno"],
        moment=["tarde", "noche"],
    )


# ---------------------------------------------------------------------------
# _to_curated — el momento se omite deliberadamente (parche, ver known-issues)
# ---------------------------------------------------------------------------


def test_to_curated_emits_none_moment() -> None:
    # Arrange: candidato con momento en el corpus y elección del LLM.
    activity = _make_activity()
    choice = _ActivityChoice(
        activity_id="act-001",
        reason="Sustituye el scroll nocturno por algo relajante.",
        why_it_fits="Encaja con tu tiempo y preferencia en casa.",
        replaces="scroll_nocturno",
    )

    # Act
    curated = _to_curated(choice, activity, Lang.ES)

    # Assert: el Curador no adivina el momento; lo deja en None.
    assert curated.moment is None
