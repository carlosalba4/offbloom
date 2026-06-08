# Corpus de conocimiento — DetoxApp (contenido base)

Base de conocimiento que **fundamenta al coach** (RAG). El Planificador y el
Curador recuperan de aquí para que el consejo esté apoyado en contenido, no
inventado.

## Qué es y qué NO es
- Es contenido de bienestar digital **general**, redactado como punto de partida.
- **No es consejo médico ni psicológico.** Para malestar persistente o señales de
  riesgo, el coach redirige a ayuda profesional (ver `08-seguridad-y-limites.md`).
- Antes de producción: **revisar y ampliar** con fuentes vetadas (p. ej. principios
  de TCC, literatura de formación de hábitos, guías de uso de pantallas de
  organismos de salud, Center for Humane Technology, etc.). El campo `fuente` del
  frontmatter marca que es contenido base, no una cita académica real.

## Estructura
- Documentos `.md` con *frontmatter* (técnicas, psicoeducación, rutinas, seguridad).
- `actividades.jsonl`: catálogo estructurado de actividades offline, con metadatos
  de contexto para que el **Curador** las case con la situación de la persona.

## Para el rag-engineer (ingesta)
- Trocea los `.md` por secciones (encabezados). Guarda como metadatos de Chroma:
  `id`, `categoria`, `tags`, `lang`, `fuente` (para citar la procedencia).
- Cada línea de `actividades.jsonl` es un documento: embebe `descripcion` y guarda
  el resto de campos como metadatos filtrables (duración, energía, lugar, etc.).
- Embeddings con **bge-m3** (multilingüe): el corpus está en español pero la
  recuperación funciona también para usuarias en inglés (cross-lingüe). Si quieres
  cobertura nativa en inglés, añade documentos `.md` en inglés más adelante.

## Tono del contenido
Compasivo y sin juicios. Reencuadre, no castigo. Nada de culpabilizar ni de
lenguaje alarmista.
