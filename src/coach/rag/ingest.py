"""Ingesta del corpus de bienestar digital en el almacén vectorial Chroma.

Carga y trocea los ficheros Markdown (colección ``knowledge``) y el catálogo
de actividades JSONL (colección ``activities``), los embebe con bge-m3 vía
``coach.llm.get_embeddings()`` y los persiste en Chroma embebido.

Ejecución:
    uv run python -m coach.rag.ingest
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from langchain_chroma import Chroma
from langchain_core.documents import Document

from coach.config import settings
from coach.llm.provider import get_embeddings

# ---------------------------------------------------------------------------
# Constantes de colección
# ---------------------------------------------------------------------------
KNOWLEDGE_COLLECTION: str = "knowledge"
ACTIVITIES_COLLECTION: str = "activities"


# ---------------------------------------------------------------------------
# Helpers de parseo
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str] | None:
    """Separa el bloque frontmatter YAML del cuerpo Markdown.

    El bloque debe estar delimitado por ``---`` al inicio del fichero.
    Devuelve ``(metadatos, cuerpo)`` o ``None`` si no hay frontmatter (lo que
    excluye ficheros como ``00-manifiesto.md`` de la ingesta).
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    yaml_text = text[4:end]
    body = text[end + 5:]
    metadata: dict[str, object] = yaml.safe_load(yaml_text) or {}
    return metadata, body


def _chunk_by_heading(body: str) -> list[tuple[str, str]]:
    """Trocea el cuerpo Markdown por líneas de encabezado (``#``).

    Cada encabezado abre un chunk nuevo. Devuelve una lista de tuplas
    ``(heading_text, texto_completo_incluyendo_heading)``. Los chunks cuyo
    texto queda vacío tras el strip se descartan.
    """
    chunks: list[tuple[str, str]] = []
    current_heading: str = ""
    current_lines: list[str] = []

    for line in body.splitlines(keepends=True):
        if line.startswith("#"):
            # Guarda el chunk anterior si tiene contenido
            if current_lines:
                section_text = "".join(current_lines).strip()
                if section_text:
                    chunks.append((current_heading, section_text))
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Último chunk
    if current_lines:
        section_text = "".join(current_lines).strip()
        if section_text:
            chunks.append((current_heading, section_text))

    return chunks


# ---------------------------------------------------------------------------
# Cargadores de corpus
# ---------------------------------------------------------------------------


def _load_knowledge() -> tuple[list[Document], list[str]]:
    """Carga y trocea los ficheros ``.md`` del corpus de conocimiento.

    Itera en orden estable (sorted) el directorio ``settings.corpus_dir``.
    Los ficheros sin frontmatter (p. ej. ``00-manifiesto.md``) se saltan.
    Por cada sección Markdown crea un ``Document`` con metadatos estrictos
    (sin ``None`` ni listas; Chroma solo acepta str/int/float/bool).

    IDs de Chroma deterministas: ``"{doc_id}::{indice_seccion}"``.
    """
    corpus_path = Path(settings.corpus_dir)
    documents: list[Document] = []
    ids: list[str] = []

    for md_file in sorted(corpus_path.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8")
        parsed = _parse_frontmatter(raw)
        if parsed is None:
            continue

        meta, body = parsed
        doc_id: str = str(meta.get("id") or md_file.stem)
        titulo: str = str(meta.get("titulo") or "")
        categoria: str = str(meta.get("categoria") or "")
        lang: str = str(meta.get("lang") or "es")
        fuente: str = str(meta.get("fuente") or "")

        # tags es lista en el frontmatter → convertir a str
        raw_tags = meta.get("tags")
        if isinstance(raw_tags, list):
            tags: str = ", ".join(str(t) for t in raw_tags)
        elif raw_tags is not None:
            tags = str(raw_tags)
        else:
            tags = ""

        chunks = _chunk_by_heading(body)
        for i, (heading, section_text) in enumerate(chunks):
            doc = Document(
                page_content=section_text,
                metadata={
                    "id": doc_id,
                    "titulo": titulo,
                    "categoria": categoria,
                    "tags": tags,
                    "lang": lang,
                    "fuente": fuente,
                    "seccion": heading,
                },
            )
            documents.append(doc)
            ids.append(f"{doc_id}::{i}")

    return documents, ids


def _load_activities() -> tuple[list[Document], list[str]]:
    """Carga el catálogo de actividades desde ``actividades.jsonl``.

    Cada línea = un documento. ``page_content`` = campo ``descripcion``.
    Las listas (``reemplaza``, ``momento``) se unen con comas para cumplir
    la restricción de metadatos de Chroma (solo str/int/float/bool).
    """
    jsonl_path = Path(settings.corpus_dir) / "actividades.jsonl"
    documents: list[Document] = []
    ids: list[str] = []

    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record: dict[str, object] = json.loads(line)

            activity_id: str = str(record.get("id") or "")
            descripcion: str = str(record.get("descripcion") or "")

            # Listas → str
            raw_reemplaza = record.get("reemplaza")
            reemplaza: str = (
                ", ".join(str(x) for x in raw_reemplaza)
                if isinstance(raw_reemplaza, list)
                else str(raw_reemplaza or "")
            )

            raw_momento = record.get("momento")
            momento: str = (
                ", ".join(str(x) for x in raw_momento)
                if isinstance(raw_momento, list)
                else str(raw_momento or "")
            )

            doc = Document(
                page_content=descripcion,
                metadata={
                    "id": activity_id,
                    "categoria": str(record.get("categoria") or ""),
                    "duracion_min": int(record.get("duracion_min") or 0),
                    "energia": str(record.get("energia") or ""),
                    "lugar": str(record.get("lugar") or ""),
                    "social": str(record.get("social") or ""),
                    "materiales": str(record.get("materiales") or ""),
                    "name_es": str(record.get("name_es") or ""),
                    "name_en": str(record.get("name_en") or ""),
                    "reemplaza": reemplaza,
                    "momento": momento,
                },
            )
            documents.append(doc)
            ids.append(activity_id)

    return documents, ids


# ---------------------------------------------------------------------------
# Gestión del store
# ---------------------------------------------------------------------------


def _reset_collection(name: str) -> Chroma:
    """Vacía la colección ``name`` y devuelve una instancia Chroma limpia.

    La secuencia delete + recrear garantiza idempotencia: relanzar la ingesta
    produce exactamente el mismo contenido, sin duplicados.
    """
    store = Chroma(
        collection_name=name,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
    )
    store.delete_collection()
    return Chroma(
        collection_name=name,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
    )


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------


def ingest() -> dict[str, int]:
    """Ejecuta la ingesta completa del corpus en las dos colecciones Chroma.

    Carga y trocea el conocimiento y las actividades, resetea ambas
    colecciones (idempotencia) y añade los documentos con IDs deterministas.

    Devuelve el recuento de documentos ingestados por colección.
    """
    knowledge_docs, knowledge_ids = _load_knowledge()
    activities_docs, activities_ids = _load_activities()

    knowledge_store = _reset_collection(KNOWLEDGE_COLLECTION)
    knowledge_store.add_documents(documents=knowledge_docs, ids=knowledge_ids)

    activities_store = _reset_collection(ACTIVITIES_COLLECTION)
    activities_store.add_documents(documents=activities_docs, ids=activities_ids)

    return {
        KNOWLEDGE_COLLECTION: len(knowledge_docs),
        ACTIVITIES_COLLECTION: len(activities_docs),
    }


def main() -> None:
    """CLI: ejecuta la ingesta e imprime los recuentos por colección."""
    counts = ingest()
    for collection, count in counts.items():
        print(f"{collection}: {count} documentos ingestados")


if __name__ == "__main__":
    main()
