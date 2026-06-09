"""Retriever del almacén vectorial: búsqueda semántica sobre las colecciones Chroma.

Expone dos funciones públicas para los nodos del grafo:

- ``search_knowledge``: búsqueda semántica sobre la colección de conocimiento;
  cada fragmento lleva su fuente para poder citar.
- ``search_activities``: búsqueda semántica sobre actividades offline, combinada
  con filtro contextual (duración, energía, lugar, social, reemplaza, momento).

El grafo no conoce Chroma: recibe DTOs tipados (``RetrievedChunk``,
``RetrievedActivity``). El encapsulamiento cumple ADR-002.
"""
from __future__ import annotations

import functools

from langchain_chroma import Chroma
from pydantic import BaseModel, ConfigDict, Field

from coach.config import settings
from coach.graph.state import EnergyLevel, Place, RetrievedChunk, SocialPreference, TimeOfDay
from coach.llm.provider import get_embeddings
from coach.rag.ingest import ACTIVITIES_COLLECTION, KNOWLEDGE_COLLECTION

# ---------------------------------------------------------------------------
# Mapas de vocabulario: enum del dominio → string del corpus (español)
# ---------------------------------------------------------------------------

# Niveles en orden ascendente; el índice de lista determina el techo permitido.
_ENERGY_LEVELS: list[str] = ["baja", "media", "alta"]

_ENERGY_MAP: dict[EnergyLevel, str] = {
    EnergyLevel.LOW: "baja",
    EnergyLevel.MEDIUM: "media",
    EnergyLevel.HIGH: "alta",
}

# ANYWHERE → None indica «sin filtro de lugar».
_PLACE_MAP: dict[Place, str | None] = {
    Place.HOME: "casa",
    Place.OUTDOORS: "exterior",
    Place.ANYWHERE: None,
}

# El corpus usa cuatro valores: solo, social, either, cualquiera.
# "either" significa que la actividad encaja tanto en solitario como acompañado;
# se incluye en los dos conjuntos permitidos.
# ANY → None indica «sin filtro social».
_SOCIAL_MAP: dict[SocialPreference, list[str] | None] = {
    SocialPreference.SOLO: ["solo", "either"],
    SocialPreference.WITH_OTHERS: ["social", "either"],
    SocialPreference.ANY: None,
}

# AFTERNOON y EVENING comparten el token "tarde": el corpus no distingue
# tarde/primera-noche. Decisión documentada en el ADR-002 seguimiento §5.
_MOMENT_MAP: dict[TimeOfDay, str] = {
    TimeOfDay.MORNING: "manana",
    TimeOfDay.AFTERNOON: "tarde",
    TimeOfDay.EVENING: "tarde",
    TimeOfDay.NIGHT: "noche",
}


# ---------------------------------------------------------------------------
# DTO de retorno específico del retriever de actividades
# ---------------------------------------------------------------------------


class RetrievedActivity(BaseModel):
    """DTO de actividad recuperada del almacén vectorial.

    Conserva los campos tal como están en el corpus (strings del corpus,
    listas para reemplaza/momento). El nodo Curador es responsable de
    interpretar estos strings y construir el modelo ``CuratedActivity``
    con los enums de ``state.py``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Identificador único de la actividad.")
    text: str = Field(description="Descripción de la actividad (page_content del corpus).")
    name_es: str = Field(description="Nombre de la actividad en español.")
    name_en: str = Field(description="Nombre de la actividad en inglés.")
    category: str = Field(description="Categoría temática de la actividad.")
    duration_min: int = Field(description="Duración estimada en minutos.")
    energy: str = Field(description="Nivel de energía requerido (baja/media/alta).")
    place: str = Field(description="Lugar de realización (casa/exterior/cualquiera).")
    social: str = Field(description="Preferencia social (solo/social/either/cualquiera).")
    materials: str = Field(description="Materiales necesarios.")
    replaces: list[str] = Field(description="Triggers de uso digital que esta actividad sustituye.")
    moment: list[str] = Field(description="Momentos del día en que encaja la actividad.")


# ---------------------------------------------------------------------------
# Helper privado: store cacheado por nombre de colección
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=2)
def _get_store(collection_name: str) -> Chroma:
    """Devuelve una instancia Chroma cacheada para la colección indicada.

    El caché evita reinstanciar el cliente en cada llamada al retriever.
    La construcción replica exactamente la de ``ingest.py`` para garantizar
    compatibilidad de colección y función de embedding.
    """
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
    )


# ---------------------------------------------------------------------------
# Helper privado: tokenización de campos con comas
# ---------------------------------------------------------------------------


def _tokens(value: str) -> set[str]:
    """Divide un string con comas en un conjunto de tokens normalizados.

    Usado para los metadatos ``reemplaza`` y ``momento`` del corpus, que
    Chroma almacena como strings con comas (restricción de tipos de metadatos).
    """
    return {token.strip() for token in value.split(",") if token.strip()}


# ---------------------------------------------------------------------------
# Helper privado: construcción del filtro Chroma (where)
# ---------------------------------------------------------------------------


def _build_where(
    max_duration_min: int | None,
    energy: EnergyLevel | None,
    place: Place | None,
    social: SocialPreference | None,
) -> dict[str, object] | None:
    """Construye el dict ``where`` nativo de Chroma a partir de los parámetros de contexto.

    Reglas de combinación (sintaxis nativa Chroma):
    - 0 condiciones → ``None`` (sin filtro, recupera todo).
    - 1 condición → dict directo.
    - ≥2 condiciones → ``{"$and": [...]}``.

    Los valores centinela ANYWHERE y ANY producen ``None`` y no generan condición.
    """
    conditions: list[dict[str, object]] = []

    # Duración: solo actividades que caben en el tiempo disponible del usuario
    if max_duration_min is not None:
        conditions.append({"duracion_min": {"$lte": max_duration_min}})

    # Energía: actividades con nivel ≤ al disponible (baja < media < alta)
    if energy is not None:
        level_str = _ENERGY_MAP[energy]
        level_idx = _ENERGY_LEVELS.index(level_str)
        allowed_levels = _ENERGY_LEVELS[: level_idx + 1]
        conditions.append({"energia": {"$in": allowed_levels}})

    # Lugar: la actividad encaja si es el lugar del usuario O "cualquiera"
    if place is not None:
        place_str = _PLACE_MAP[place]
        if place_str is not None:  # Place.ANYWHERE → sin filtro
            conditions.append({"lugar": {"$in": [place_str, "cualquiera"]}})

    # Social: la actividad debe encajar con la preferencia del usuario
    if social is not None:
        social_values = _SOCIAL_MAP[social]
        if social_values is not None:  # SocialPreference.ANY → sin filtro
            conditions.append({"social": {"$in": social_values}})

    if len(conditions) == 0:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


# ---------------------------------------------------------------------------
# Funciones públicas del retriever
# ---------------------------------------------------------------------------


def search_knowledge(query: str, k: int = 4) -> list[RetrievedChunk]:
    """Busca fragmentos de conocimiento semánticamente relevantes para la consulta.

    Realiza una búsqueda por similitud sobre la colección ``knowledge`` y
    devuelve los ``k`` fragmentos más cercanos como ``RetrievedChunk``
    (modelo definido en ``state.py``). El campo ``source`` permite citar la
    fuente en el plan semanal.

    Args:
        query: Texto de consulta en español o inglés (bge-m3 es multilingüe).
        k: Número de fragmentos a devolver.

    Returns:
        Lista de ``RetrievedChunk`` ordenados por relevancia semántica.
    """
    store = _get_store(KNOWLEDGE_COLLECTION)
    docs = store.similarity_search(query, k=k)

    chunks: list[RetrievedChunk] = []
    for doc in docs:
        meta = doc.metadata
        chunks.append(
            RetrievedChunk(
                id=meta.get("id", ""),
                text=doc.page_content,
                category=meta.get("categoria", ""),
                source=meta.get("fuente", ""),
            )
        )
    return chunks


def search_activities(
    query: str,
    *,
    max_duration_min: int | None = None,
    energy: EnergyLevel | None = None,
    place: Place | None = None,
    social: SocialPreference | None = None,
    replaces: list[str] | None = None,
    moment: TimeOfDay | None = None,
    k: int = 3,
) -> list[RetrievedActivity]:
    """Busca actividades offline relevantes para la consulta y el contexto del usuario.

    Combina búsqueda semántica con filtros contextuales en dos capas:

    1. **Filtro nativo Chroma** (``where``): filtra por ``duracion_min`` ($lte),
       ``energia`` ($in niveles ≤ usuario), ``lugar`` ($in [mapeado, "cualquiera"]),
       ``social`` ($in valores compatibles). Reduce candidatos en el servidor.
    2. **Filtro Python** sobre strings con comas (``reemplaza``, ``momento``):
       conserva la actividad si algún trigger del usuario está en ``reemplaza``,
       y si el momento mapeado está en ``momento`` o ``momento`` contiene "cualquiera".

    Se recupera un pool mayor (``fetch_k = max(k * 5, 20)``) para compensar el
    recorte del filtro Python, y se trunca a ``k`` tras filtrar.

    Args:
        query: Texto de consulta para la búsqueda semántica.
        max_duration_min: Duración máxima aceptable en minutos (inclusive).
        energy: Nivel de energía disponible; se permiten actividades con nivel ≤ este.
        place: Lugar donde puede realizar la actividad.
        social: Preferencia social del usuario.
        replaces: Triggers de uso digital del Analista; conserva actividades que
            reemplacen al menos uno.
        moment: Momento del día; conserva actividades que encajen o sean "cualquiera".
        k: Número máximo de resultados a devolver.

    Returns:
        Lista de hasta ``k`` ``RetrievedActivity`` que encajan con el contexto.
    """
    store = _get_store(ACTIVITIES_COLLECTION)
    where = _build_where(max_duration_min, energy, place, social)
    fetch_k = max(k * 5, 20)

    docs = store.similarity_search(query, k=fetch_k, filter=where)

    results: list[RetrievedActivity] = []
    for doc in docs:
        meta = doc.metadata

        # Filtro por reemplaza: al menos un trigger del usuario debe estar en los tokens
        if replaces is not None:
            activity_replaces = _tokens(meta.get("reemplaza", ""))
            if not any(trigger in activity_replaces for trigger in replaces):
                continue

        # Filtro por momento: el token mapeado presente O "cualquiera" en el campo
        if moment is not None:
            activity_moments = _tokens(meta.get("momento", ""))
            moment_token = _MOMENT_MAP[moment]
            if moment_token not in activity_moments and "cualquiera" not in activity_moments:
                continue

        results.append(
            RetrievedActivity(
                id=meta.get("id", ""),
                text=doc.page_content,
                name_es=meta.get("name_es", ""),
                name_en=meta.get("name_en", ""),
                category=meta.get("categoria", ""),
                duration_min=int(meta.get("duracion_min", 0)),
                energy=meta.get("energia", ""),
                place=meta.get("lugar", ""),
                social=meta.get("social", ""),
                materials=meta.get("materiales", ""),
                replaces=list(_tokens(meta.get("reemplaza", ""))),
                moment=list(_tokens(meta.get("momento", ""))),
            )
        )

        if len(results) >= k:
            break

    return results
