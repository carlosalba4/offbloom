"""Tests para src/coach/rag/store.py: _build_where y search_activities.

Todos los tests son deterministas y nunca llaman a Ollama ni embeben de verdad.
Se aísla Chroma mockeando `coach.rag.store._get_store` e inyectando un conjunto
fijo de actividades; `_build_where` se prueba importándola directamente.

Estructura: Arrange – Act – Assert (AAA).
"""
from __future__ import annotations

from typing import Any

import pytest

from coach.graph.state import EnergyLevel, Place, SocialPreference, TimeOfDay
from coach.rag.store import _build_where, search_activities

# ---------------------------------------------------------------------------
# Stubs locales y helpers de construcción
# ---------------------------------------------------------------------------


class _FakeDoc:
    """Stub mínimo de Document de LangChain.

    Solo expone `.page_content` y `.metadata`, que son los únicos atributos
    que usa `store.py` al iterar los resultados de `similarity_search`.
    """

    def __init__(self, page_content: str, metadata: dict[str, Any]) -> None:
        self.page_content = page_content
        self.metadata = metadata


class _FakeStore:
    """Tienda vectorial falsa que graba los argumentos de cada llamada.

    `similarity_search` replica el recorte de Chroma por `k`: devuelve
    `self._docs[:k]` y guarda todos los argumentos en `self.last_call`
    para poder inspeccionarlos en los asserts.
    """

    def __init__(self, docs: list[_FakeDoc] | None = None) -> None:
        self._docs: list[_FakeDoc] = docs or []
        self.last_call: dict[str, Any] = {}

    def similarity_search(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[_FakeDoc]:
        """Replica el comportamiento de Chroma: guarda args y recorta a k."""
        self.last_call = {"query": query, "k": k, "filter": filter}
        return self._docs[:k]


def _act(
    *,
    id: str = "act-001",
    name_es: str = "Actividad test",
    name_en: str = "Test activity",
    categoria: str = "general",
    duracion_min: int = 20,
    energia: str = "baja",
    lugar: str = "casa",
    social: str = "solo",
    materiales: str = "ninguno",
    reemplaza: str = "scroll_nocturno",
    momento: str = "manana",
    content: str = "Descripción de la actividad de prueba.",
) -> _FakeDoc:
    """Construye un _FakeDoc con los metadatos del corpus de actividades.

    Todos los parámetros tienen defaults razonables para reducir el boilerplate
    en los tests; solo se sobreescriben los campos relevantes para cada caso.
    """
    return _FakeDoc(
        page_content=content,
        metadata={
            "id": id,
            "name_es": name_es,
            "name_en": name_en,
            "categoria": categoria,
            "duracion_min": duracion_min,
            "energia": energia,
            "lugar": lugar,
            "social": social,
            "materiales": materiales,
            "reemplaza": reemplaza,
            "momento": momento,
        },
    )


# ---------------------------------------------------------------------------
# 1. _build_where — filtro nativo Chroma
# ---------------------------------------------------------------------------


def test_build_where_no_params_returns_none() -> None:
    # Arrange — ningún parámetro de contexto proporcionado

    # Act
    result = _build_where(None, None, None, None)

    # Assert
    assert result is None


def test_build_where_single_condition_returns_direct_dict_without_and() -> None:
    # Arrange — solo max_duration_min → exactamente una condición

    # Act
    result = _build_where(30, None, None, None)

    # Assert — dict directo, sin envolver en $and
    assert result == {"duracion_min": {"$lte": 30}}
    assert "$and" not in result  # type: ignore[operator]


def test_build_where_two_conditions_uses_and_operator() -> None:
    # Arrange — duración + energía → ≥2 condiciones

    # Act
    result = _build_where(30, EnergyLevel.LOW, None, None)

    # Assert
    assert result is not None
    assert "$and" in result
    clauses: list[dict[str, Any]] = result["$and"]  # type: ignore[assignment]
    assert isinstance(clauses, list)
    assert len(clauses) == 2


def test_build_where_duration_generates_lte_condition() -> None:
    # Arrange / Act
    result = _build_where(45, None, None, None)

    # Assert
    assert result == {"duracion_min": {"$lte": 45}}


@pytest.mark.parametrize(
    ("energy", "expected_levels"),
    [
        (EnergyLevel.LOW, ["baja"]),
        (EnergyLevel.MEDIUM, ["baja", "media"]),
        (EnergyLevel.HIGH, ["baja", "media", "alta"]),
    ],
)
def test_build_where_energy_ceiling_includes_all_levels_up_to_user(
    energy: EnergyLevel,
    expected_levels: list[str],
) -> None:
    # Arrange — energía sola → única condición, resultado directo

    # Act
    result = _build_where(None, energy, None, None)

    # Assert
    assert result is not None
    in_list: list[str] = result["energia"]["$in"]  # type: ignore[index]
    assert in_list == expected_levels


def test_build_where_place_home_includes_cualquiera_wildcard() -> None:
    # Arrange / Act
    result = _build_where(None, None, Place.HOME, None)

    # Assert
    assert result == {"lugar": {"$in": ["casa", "cualquiera"]}}


def test_build_where_place_outdoors_includes_cualquiera_wildcard() -> None:
    # Arrange / Act
    result = _build_where(None, None, Place.OUTDOORS, None)

    # Assert
    assert result == {"lugar": {"$in": ["exterior", "cualquiera"]}}


def test_build_where_place_anywhere_adds_no_condition() -> None:
    # Arrange — ANYWHERE como único parámetro → sin condición alguna

    # Act
    result = _build_where(None, None, Place.ANYWHERE, None)

    # Assert
    assert result is None


def test_build_where_social_solo_includes_either() -> None:
    # Arrange / Act
    result = _build_where(None, None, None, SocialPreference.SOLO)

    # Assert
    assert result == {"social": {"$in": ["solo", "either"]}}


def test_build_where_social_with_others_includes_either() -> None:
    # Arrange / Act
    result = _build_where(None, None, None, SocialPreference.WITH_OTHERS)

    # Assert
    assert result == {"social": {"$in": ["social", "either"]}}


def test_build_where_social_any_adds_no_condition() -> None:
    # Arrange — ANY como único parámetro → sin condición alguna

    # Act
    result = _build_where(None, None, None, SocialPreference.ANY)

    # Assert
    assert result is None


def test_build_where_four_conditions_all_present_in_and_list() -> None:
    # Arrange — los cuatro parámetros con valores que generan condición

    # Act
    result = _build_where(60, EnergyLevel.MEDIUM, Place.HOME, SocialPreference.SOLO)

    # Assert
    assert result is not None
    assert "$and" in result
    clauses: list[dict[str, Any]] = result["$and"]  # type: ignore[assignment]
    assert len(clauses) == 4
    keys = [list(c.keys())[0] for c in clauses]
    assert "duracion_min" in keys
    assert "energia" in keys
    assert "lugar" in keys
    assert "social" in keys


# ---------------------------------------------------------------------------
# 2. search_activities — filtro Python + integración con _get_store mockeado
# ---------------------------------------------------------------------------


def test_search_activities_replaces_filter_keeps_matching_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — dos actividades: una con trigger coincidente, otra sin él
    doc_match = _act(id="a1", reemplaza="scroll_nocturno, aburrimiento")
    doc_no_match = _act(id="a2", reemplaza="ansiedad_social")
    fake_store = _FakeStore(docs=[doc_match, doc_no_match])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta", replaces=["scroll_nocturno"])

    # Assert
    ids = {r.id for r in results}
    assert "a1" in ids
    assert "a2" not in ids


def test_search_activities_replaces_filter_none_keeps_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — sin filtro replaces → ambas actividades deben pasar
    doc1 = _act(id="r1", reemplaza="trigger_a")
    doc2 = _act(id="r2", reemplaza="trigger_b")
    fake_store = _FakeStore(docs=[doc1, doc2])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta", replaces=None)

    # Assert
    ids = {r.id for r in results}
    assert "r1" in ids
    assert "r2" in ids


def test_search_activities_moment_morning_keeps_manana_discards_tarde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — una actividad de mañana y otra de tarde
    doc_morning = _act(id="b1", momento="manana")
    doc_evening = _act(id="b2", momento="tarde")
    fake_store = _FakeStore(docs=[doc_morning, doc_evening])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta", moment=TimeOfDay.MORNING)

    # Assert
    ids = {r.id for r in results}
    assert "b1" in ids
    assert "b2" not in ids


def test_search_activities_moment_cualquiera_always_matches_any_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — actividad con comodín "cualquiera" debe encajar con cualquier momento
    doc_any = _act(id="c1", momento="cualquiera")
    doc_night = _act(id="c2", momento="noche")
    fake_store = _FakeStore(docs=[doc_any, doc_night])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act — pedimos MORNING; c1 tiene "cualquiera" → debe incluirse, c2 no
    results = search_activities("consulta", moment=TimeOfDay.MORNING)

    # Assert
    ids = {r.id for r in results}
    assert "c1" in ids
    assert "c2" not in ids


def test_search_activities_fetch_k_is_at_least_20_for_small_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — k=3 → fetch_k debe ser max(3*5, 20) = 20
    fake_store = _FakeStore(docs=[])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    search_activities("consulta", k=3)

    # Assert
    assert fake_store.last_call["k"] == 20


def test_search_activities_fetch_k_scales_above_20_for_larger_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — k=5 → fetch_k debe ser max(5*5, 20) = 25
    fake_store = _FakeStore(docs=[])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    search_activities("consulta", k=5)

    # Assert
    assert fake_store.last_call["k"] == 25


def test_search_activities_truncates_results_to_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — 30 actividades que pasan todos los filtros Python; k=3
    docs = [
        _act(id=f"act-{i}", reemplaza="scroll_nocturno", momento="manana")
        for i in range(30)
    ]
    fake_store = _FakeStore(docs=docs)
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta", k=3)

    # Assert — resultado truncado a k, y el store recibió fetch_k = max(3*5,20) = 20
    assert len(results) == 3
    assert fake_store.last_call["k"] == 20


def test_search_activities_dto_replaces_field_is_tokenized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — reemplaza con múltiples tokens separados por comas
    doc = _act(id="d1", reemplaza="scroll_nocturno, redes_sociales, youtube")
    fake_store = _FakeStore(docs=[doc])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta")

    # Assert — el DTO expone una lista de tokens limpios (sin espacios)
    assert len(results) == 1
    assert set(results[0].replaces) == {"scroll_nocturno", "redes_sociales", "youtube"}


def test_search_activities_dto_moment_field_is_tokenized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — momento con múltiples tokens
    doc = _act(id="e1", momento="manana, tarde, noche")
    fake_store = _FakeStore(docs=[doc])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    results = search_activities("consulta")

    # Assert
    assert len(results) == 1
    assert set(results[0].moment) == {"manana", "tarde", "noche"}


def test_search_activities_passes_where_filter_to_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — con max_duration_min → _build_where genera un filtro no nulo
    fake_store = _FakeStore(docs=[])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    search_activities("consulta", max_duration_min=30)

    # Assert — el store recibió el filtro de duración construido por _build_where
    assert fake_store.last_call["filter"] == {"duracion_min": {"$lte": 30}}


def test_search_activities_passes_none_filter_when_no_chroma_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — sin parámetros de filtro Chroma → filter=None al store
    fake_store = _FakeStore(docs=[])
    monkeypatch.setattr("coach.rag.store._get_store", lambda name: fake_store)

    # Act
    search_activities("consulta")

    # Assert
    assert fake_store.last_call["filter"] is None
