"""Eval manual de groundedness/faithfulness del plan del coach (DeepEval).

Mide, sobre los casos del listón alto que SÍ generan plan, si el `WeeklyPlan` que
emite el Planificador está FUNDAMENTADO en los fragmentos de conocimiento
recuperados por el RAG. Usa la `FaithfulnessMetric` de DeepEval con un LLM-judge
LOCAL (qwen3:8b vía Ollama, ver `evals/groundedness/judge.py`).

VEREDICTO ORIENTATIVO
---------------------
El juez local (8B) es RUIDOSO: los números son una SEÑAL para detectar planes que
se despegan del corpus, no una verdad absoluta. Por defecto la suite SIEMPRE
termina con código 0 (informativa). Solo si `EVAL_GROUND_ENFORCE` está activo
falla (código 1) cuando el score medio cae por debajo del umbral.

Evalúa hasta el plan, así que SÍ necesita el RAG (Chroma + embeddings) además de
Ollama sirviendo el modelo de chat. Es una herramienta de diagnóstico que se
corre a voluntad.

REQUISITOS DE EJECUCIÓN
-----------------------
- Ollama encendido sirviendo el modelo de chat `qwen3:8b` y los embeddings `bge-m3`:

      ollama serve
      ollama pull qwen3:8b
      ollama pull bge-m3

- Índice de Chroma construido (corpus ingerido), porque el Planificador llama al
  retriever (`search_knowledge`).

Uso:

    uv run python scripts/eval_groundedness.py

Variables de entorno:

- `EVAL_GROUND_RUNS`      (int, default 1): ejecuciones por caso. Cada ejecución
                          es, al menos, una llamada al Analista + una al
                          Planificador + varias llamadas al juez.
- `EVAL_GROUND_THRESHOLD` (float, default 0.7): umbral blando informativo de la
                          `FaithfulnessMetric`. Marca qué runs quedan "bajo
                          umbral" en el reporte.
- `EVAL_GROUND_ENFORCE`   (bool, default off): si se activa (1/true/yes/on), la
                          suite FALLA (código 1) cuando el score medio < umbral.
                          Por defecto NO bloquea (solo informa).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# Arranque al ejecutar el script directamente (`uv run python scripts/eval_groundedness.py`):
# Python pone scripts/ en sys.path pero NO la raíz del proyecto. El paquete `coach` se
# importa igual porque está INSTALADO en el entorno (src-layout, ver pyproject), pero
# `evals/` vive en la raíz y no está empaquetado, así que hay que añadir la raíz al path
# antes de importarlo.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from coach.graph.state import CoachState  # noqa: E402
from evals.groundedness.dataset import (  # noqa: E402
    GroundednessCase,
    build_groundedness_cases,
)
from evals.groundedness.judge import LocalJudge  # noqa: E402
from evals.groundedness.runner import (  # noqa: E402
    PlanRun,
    retrieval_context,
    run_plan,
    serialize_plan,
)


def _env_int(name: str, default: int) -> int:
    """Lee un entero de entorno; cae al default si está ausente o es inválido."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"AVISO: {name}={raw!r} no es un entero; uso {default}.")
        return default


def _env_float(name: str, default: float) -> float:
    """Lee un float de entorno; cae al default si está ausente o es inválido."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"AVISO: {name}={raw!r} no es un número; uso {default}.")
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Lee un booleano de entorno (1/true/yes/on); cae al default si está ausente."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def print_section(title: str) -> None:
    """Imprime un encabezado de sección legible."""
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _truncate(text: str, width: int) -> str:
    """Recorta `text` a una sola línea de a lo sumo `width` caracteres."""
    flat = " ".join(text.split())
    if len(flat) <= width:
        return flat
    return flat[: max(0, width - 1)] + "…"


def _force_utf8_output() -> None:
    """Fuerza UTF-8 (con reemplazo) en stdout/stderr.

    En la consola de Windows (cp1252) caracteres como el emoji ✨ que imprime
    deepeval rompen la salida con `UnicodeEncodeError` y tumbarían el script antes
    del reporte. Con `errors="replace"` ningún carácter no representable puede
    abortar la ejecución (a lo sumo sale como '?').
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _summarize_input(state: CoachState) -> str:
    """Resume el perfil y los disparadores del caso como `input` del TestCase.

    La `FaithfulnessMetric` no usa el `input` para puntuar (contrasta
    actual_output contra retrieval_context), pero un resumen legible hace el
    reporte de DeepEval interpretable.
    """
    parts: list[str] = []
    profile = state.get("profile")
    if profile is not None and profile.goals:
        parts.append("Objetivos: " + "; ".join(profile.goals) + ".")
    usage = state.get("usage")
    if usage is not None and usage.self_reported_triggers:
        parts.append("Disparadores: " + "; ".join(usage.self_reported_triggers) + ".")
    return " ".join(parts) if parts else "(sin resumen)"


@dataclass
class ScoredRun:
    """Resultado de evaluar una corrida con plan contra la métrica de faithfulness."""

    label: str
    score: float
    reason: str
    num_chunks: int


@dataclass
class SkippedRun:
    """Una corrida sin plan (derivada o degradada) que se excluye del scoring."""

    label: str
    derived: bool


def _make_metric(judge: LocalJudge, threshold: float) -> FaithfulnessMetric:
    """Construye la `FaithfulnessMetric` con el juez local en modo síncrono."""
    return FaithfulnessMetric(
        model=judge,
        threshold=threshold,
        async_mode=False,
        include_reason=True,
    )


def _score_plan(
    case: GroundednessCase,
    run: PlanRun,
    judge: LocalJudge,
    threshold: float,
) -> ScoredRun:
    """Evalúa el plan de una corrida con la `FaithfulnessMetric` y captura el score."""
    assert run.plan is not None  # garantizado por el llamador
    test_case = LLMTestCase(
        input=_summarize_input(case.state),
        actual_output=serialize_plan(run.plan),
        retrieval_context=retrieval_context(run.retrieved),
    )
    metric = _make_metric(judge, threshold)
    metric.measure(test_case)
    score = float(metric.score) if metric.score is not None else 0.0
    reason = metric.reason or "(sin motivo)"
    return ScoredRun(
        label=case.label,
        score=score,
        reason=reason,
        num_chunks=len(run.retrieved),
    )


def print_per_case_table(scored: list[ScoredRun], threshold: float) -> None:
    """Imprime una fila por corrida con plan: score, nº de chunks y motivo."""
    label_w = 30
    score_w = 7
    chunks_w = 7
    reason_w = 60

    header = (
        f"{'CASE':<{label_w}}  {'SCORE':<{score_w}}  {'CHUNKS':<{chunks_w}}  {'REASON':<{reason_w}}"
    )
    print_section("RESULTADO POR CORRIDA (con plan)")
    print(header)
    print("-" * len(header))
    for row in scored:
        flag = " " if row.score >= threshold else "*"
        print(
            f"{_truncate(row.label, label_w):<{label_w}}  "
            f"{row.score:<{score_w}.2f}  "
            f"{row.num_chunks:<{chunks_w}}  "
            f"{flag}{_truncate(row.reason, reason_w)}"
        )
    print()
    print(f"Leyenda: '*' marca corridas por debajo del umbral ({threshold:.2f}).")


def print_summary(
    scored: list[ScoredRun],
    skipped: list[SkippedRun],
    threshold: float,
) -> None:
    """Imprime el score medio, las corridas bajo umbral y las corridas sin plan."""
    print_section("RESUMEN — groundedness/faithfulness del plan")
    if scored:
        mean = sum(row.score for row in scored) / len(scored)
        below = [row for row in scored if row.score < threshold]
        print(f"Corridas con plan (puntuadas): {len(scored)}")
        print(f"Score medio (faithfulness):    {mean:.2f}  (umbral {threshold:.2f})")
        print(f"Corridas bajo umbral:          {len(below)}/{len(scored)}")
        for row in below:
            print(f"  bajo umbral: {_truncate(row.label, 40)} = {row.score:.2f}")
    else:
        print("Corridas con plan (puntuadas): 0  (no se pudo puntuar ningún plan)")

    derived = [s for s in skipped if s.derived]
    degraded = [s for s in skipped if not s.derived]
    print()
    print(f"Corridas SIN plan (excluidas): {len(skipped)}")
    if derived:
        labels = ", ".join(_truncate(s.label, 28) for s in derived)
        print(f"  derivadas (gate marcó riesgo en caso seguro): {len(derived)} -> {labels}")
    if degraded:
        labels = ", ".join(_truncate(s.label, 28) for s in degraded)
        print(f"  degradadas (Planificador sin plan):           {len(degraded)} -> {labels}")


def main() -> int:
    """Ejecuta el banco hasta el plan, puntúa faithfulness y decide el código de salida."""
    _force_utf8_output()
    runs_per_case = max(1, _env_int("EVAL_GROUND_RUNS", 1))
    threshold = _env_float("EVAL_GROUND_THRESHOLD", 0.7)
    enforce = _env_bool("EVAL_GROUND_ENFORCE", False)

    mode = "ENFORCE (falla si score medio < umbral)" if enforce else "informativo (siempre exit 0)"
    print_section("EVAL DE GROUNDEDNESS — ORIENTATIVA, NO VERDAD ABSOLUTA")
    print(
        "El juez es un LLM local (8B) y es RUIDOSO: trata los scores como una señal\n"
        "para detectar planes que se despegan del corpus, no como una nota exacta.\n"
        f"Modo de bloqueo: {mode}."
    )

    cases = build_groundedness_cases()
    judge = LocalJudge()
    scored: list[ScoredRun] = []
    skipped: list[SkippedRun] = []

    total = len(cases) * runs_per_case
    done = 0
    for case in cases:
        for _ in range(runs_per_case):
            done += 1
            print(f"[{done}/{total}] Generando y puntuando plan: {case.label} ...")
            run = run_plan(case.state)
            if run.plan is None:
                skipped.append(SkippedRun(label=case.label, derived=run.derived))
                continue
            scored.append(_score_plan(case, run, judge, threshold))

    print_per_case_table(scored, threshold)
    print_summary(scored, skipped, threshold)

    print_section("VEREDICTO (ORIENTATIVO)")
    if not scored:
        print(
            "Sin corridas puntuables: no se pudo generar ningún plan (¿Ollama/Chroma "
            "disponibles?). No hay señal de groundedness que reportar."
        )
        return 0

    mean = sum(row.score for row in scored) / len(scored)
    if enforce and mean < threshold:
        print(
            f"FAIL (enforce): score medio {mean:.2f} < umbral {threshold:.2f}. "
            "Revisa si el plan se está despegando del corpus recuperado."
        )
        return 1

    print(
        f"OK (informativo): score medio {mean:.2f} (umbral {threshold:.2f}). "
        "Recuerda: señal del juez local, no veredicto definitivo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
