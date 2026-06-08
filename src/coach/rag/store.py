"""Vector store wiring (chromadb + multilingual bge-m3 embeddings).

TODO(rag-engineer): build the persistent Chroma store using
coach.llm.get_embeddings(), and expose a clean retriever for the graph nodes.
"""
from __future__ import annotations
