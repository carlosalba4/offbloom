"""Validación MANUAL del juez de groundedness: ¿DISCRIMINA o complace?

Esta NO es la suite de evals (esa vive en `scripts/eval_groundedness.py` y
`evals/groundedness/*`). Es una herramienta de DIAGNÓSTICO, manual y ORIENTATIVA,
para comprobar que el juez local (qwen3:8b, 8B) no sufre el sesgo de complacencia
típico de los modelos pequeños: dar score ALTO a cualquier salida sin contrastar
de verdad contra el contexto.

Cómo lo comprueba
-----------------
Sobre UN caso real (`scroll-nocturno-fomo` por defecto) corre el coach hasta el
plan para obtener el CONTEXTO RECUPERADO REAL del RAG, y luego puntúa con la
MISMA `FaithfulnessMetric` tres outputs de control sobre ese mismo contexto:

- `real-bueno`: el plan real, fundamentado     -> se espera score ALTO.
- `mixto`:      plausible pero con datos falsos -> se espera score INTERMEDIO.
- `inventado`:  despegado del contexto          -> se espera score BAJO.

Un juez sano produce `real-bueno >= mixto >= inventado` y una separación clara
entre el bueno y el inventado. Si todos sacan score alto, el juez NO discrimina.

El objetivo real es LEER las razones: que el juez justifique POR QUÉ baja la nota
del inventado (cifras/estudios ausentes del contexto). Por eso el reporte imprime
las razones lo más completas posible.

REQUISITOS DE EJECUCIÓN
-----------------------
- Ollama encendido sirviendo el modelo de chat `qwen3:8b` y los embeddings `bge-m3`:

      ollama serve
      ollama pull qwen3:8b
      ollama pull bge-m3

- Índice de Chroma construido (corpus ingerido), porque el Planificador llama al
  retriever (`search_knowledge`).

Esta herramienta SIEMPRE termina con código 0: nunca falla, solo informa.

Uso:

    uv run python scripts/eval_groundedness_discrimination.py

Variables de entorno:

- `EVAL_GROUND_THRESHOLD`     (float, default 0.7): umbral blando informativo de
                              la `FaithfulnessMetric`. Solo marcador, no bloquea.
- `EVAL_GROUND_DISC_CASE`     (str, default `scroll-nocturno-fomo`): etiqueta del
                              caso del banco sobre el que validar al juez.
- `EVAL_GROUND_DISC_RETRIES`  (int, default 3): reintentos para conseguir un plan
                              real con contexto (el Analista 8B es no determinista
                              y puede derivar o degradar).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# Arranque al ejecutar el script directamente (`uv run python scripts/...`):
# Python pone scripts/ en sys.path pero NO la raíz del proyecto. El paquete `coach`
# se importa igual porque está INSTALADO en el entorno (src-layout, ver pyproject),
# pero `evals/` vive en la raíz y no está empaquetado, así que hay que añadir la
# raíz al path antes de importarlo.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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


def _make_metric(judge: LocalJudge, threshold: float) -> FaithfulnessMetric:
    """Construye la `FaithfulnessMetric` con el juez local en modo síncrono."""
    return FaithfulnessMetric(
        model=judge,
        threshold=threshold,
        async_mode=False,
        include_reason=True,
    )


# --- Outputs de control escritos a mano ---------------------------------------
#
# Son textos FIJOS sobre el tema del caso (scroll nocturno / FOMO / sueño). No se
# generan con el LLM: la gracia es que sabemos de antemano cuáles están
# fundamentados y cuáles no, para juzgar al juez (no al coach).

# Mezcla afirmaciones plausibles y fundamentadas en el dominio (intenciones y
# sustituciones razonables) con afirmaciones INVENTADas (un dato numérico y un
# estudio falsos) que NO deberían estar en el contexto recuperado.
MIXED_OUTPUT = (
    "Foco semanal: reducir el scroll nocturno para proteger el sueño.\n"
    "Intenciones:\n"
    "- Dejar el teléfono fuera del dormitorio una hora antes de dormir.\n"
    "- Sustituir el scroll en la cama por diez minutos de lectura en papel.\n"
    "Sustituciones:\n"
    "- Revisar redes al acostarse -> preparar la ropa del día siguiente.\n"
    "- Mirar el móvil al despertar -> beber un vaso de agua y estirar.\n"
    "Además, está demostrado que apagar las notificaciones aumenta la "
    "concentración exactamente un 47 % según un ensayo clínico de 2021."
)

# Totalmente despegado del contexto: afirmaciones plausibles pero AUSENTES del
# corpus, con cifras falsas, un estudio inexistente y mecanismos no citados.
FABRICATED_OUTPUT = (
    "Foco semanal: optimizar la higiene del sueño con técnicas avanzadas.\n"
    "Intenciones:\n"
    "- Usar gafas de bloqueo de luz azul, que reducen el insomnio un 63 %.\n"
    "- Tomar magnesio antes de dormir para subir la melatonina un 30 %.\n"
    "Sustituciones:\n"
    "- Scroll nocturno -> meditación de ondas theta a 6 Hz.\n"
    "- Cafeína por la tarde -> infusión de raíz de valeriana certificada.\n"
    "Un estudio de la Universidad de Brentwood (2019) concluyó que estas "
    "medidas elevan la calidad del sueño un 80 % en solo dos semanas."
)


@dataclass(frozen=True)
class ControlOutput:
    """Un output de control con su expectativa cualitativa de score."""

    label: str
    text: str
    expectation: str


@dataclass
class ScoredControl:
    """Resultado de puntuar un output de control con la métrica de faithfulness."""

    label: str
    expectation: str
    score: float
    reason: str


def _build_controls(run: PlanRun) -> list[ControlOutput]:
    """Arma los tres outputs de control sobre el contexto del plan real."""
    assert run.plan is not None  # garantizado por el llamador
    return [
        ControlOutput(
            label="real-bueno",
            text=serialize_plan(run.plan),
            expectation="alto",
        ),
        ControlOutput(
            label="mixto",
            text=MIXED_OUTPUT,
            expectation="intermedio",
        ),
        ControlOutput(
            label="inventado",
            text=FABRICATED_OUTPUT,
            expectation="bajo",
        ),
    ]


def _score_control(
    control: ControlOutput,
    context: list[str],
    judge: LocalJudge,
    threshold: float,
) -> ScoredControl:
    """Puntúa un output de control con la `FaithfulnessMetric` contra `context`."""
    test_case = LLMTestCase(
        input=f"Validación del juez (control: {control.label})",
        actual_output=control.text,
        retrieval_context=context,
    )
    metric = _make_metric(judge, threshold)
    metric.measure(test_case)
    score = float(metric.score) if metric.score is not None else 0.0
    reason = metric.reason or "(sin motivo)"
    return ScoredControl(
        label=control.label,
        expectation=control.expectation,
        score=score,
        reason=reason,
    )


def _obtain_plan_run(case: GroundednessCase, retries: int) -> PlanRun | None:
    """Reintenta `run_plan` hasta lograr un plan con contexto, o None si no lo hay.

    El Analista (8B) es no determinista: puede derivar (gate marca riesgo en un
    caso seguro) o el Planificador puede degradar sin emitir plan. Reintentamos
    para darle margen; si tras `retries` intentos no hay `plan` y `retrieved`,
    devolvemos None.
    """
    for attempt in range(1, retries + 1):
        print(f"[{attempt}/{retries}] Generando plan real para '{case.label}' ...")
        try:
            run = run_plan(case.state)
        except Exception as exc:  # noqa: BLE001
            # RAG/Ollama caídos o cualquier fallo de infraestructura: no es un fallo
            # de la validación, así que lo reportamos y reintentamos sin romper.
            print(f"  fallo al ejecutar el coach: {_truncate(str(exc), 200)}; reintento ...")
            continue
        if run.plan is not None and run.retrieved:
            return run
        if run.derived:
            print("  el gate derivó (marcó riesgo); reintento ...")
        elif run.plan is None:
            print("  el Planificador degradó (sin plan); reintento ...")
        else:
            print("  el plan vino sin contexto recuperado; reintento ...")
    return None


def _print_context(context: list[str]) -> None:
    """Imprime un resumen legible del contexto recuperado usado para puntuar."""
    print_section("CONTEXTO RECUPERADO (resumido)")
    print(f"Fragmentos recuperados: {len(context)}")
    for index, chunk in enumerate(context, start=1):
        print(f"  [{index}] {_truncate(chunk, 100)}")


def _print_results(scored: list[ScoredControl], threshold: float) -> None:
    """Imprime la tabla con los tres controles juntos: label, score y razón."""
    print_section("RESULTADO POR CONTROL (mismo contexto, mismo juez)")
    for row in scored:
        print()
        print(f"CONTROL: {row.label}  (esperado: {row.expectation})")
        print(f"  SCORE : {row.score:.2f}  (umbral marcador {threshold:.2f})")
        # La razón se imprime entera (recortada solo si es enorme): el objetivo es
        # LEER cómo justifica el juez la nota, sobre todo la del inventado.
        print(f"  REASON: {_truncate(row.reason, 600)}")


def _print_verdict(scored: list[ScoredControl]) -> None:
    """Imprime el veredicto orientativo: orden esperado y separación (gap)."""
    print_section("VEREDICTO (ORIENTATIVO) — ¿el juez DISCRIMINA?")
    by_label = {row.label: row.score for row in scored}
    good = by_label.get("real-bueno", 0.0)
    mixed = by_label.get("mixto", 0.0)
    fabricated = by_label.get("inventado", 0.0)

    ordered = good >= mixed >= fabricated
    gap = good - fabricated

    print(f"Scores: real-bueno={good:.2f}  mixto={mixed:.2f}  inventado={fabricated:.2f}")
    if ordered:
        print("Orden esperado (real-bueno >= mixto >= inventado): SÍ se cumple.")
    else:
        print(
            "Orden esperado (real-bueno >= mixto >= inventado): NO se cumple. "
            "Señal de que el juez no ordena por fundamentación."
        )

    print(f"Separación real-bueno - inventado (gap): {gap:.2f}")
    if gap >= 0.3:
        print("Hay separación CLARA: el juez distingue lo fundamentado de lo inventado.")
    elif gap > 0.0:
        print("Separación DÉBIL: discrimina poco; léete las razones con cuidado.")
    else:
        print(
            "SIN separación: el juez le da igual o más al inventado. "
            "Sesgo de complacencia probable; el juez no sirve tal cual."
        )

    print()
    print(
        "Recordatorio: esto es orientativo. Un 8B es ruidoso; lo que importa es si\n"
        "las RAZONES de arriba justifican bien por qué baja la nota del inventado."
    )


def main() -> int:
    """Valida la discriminación del juez sobre un caso real. Siempre devuelve 0."""
    _force_utf8_output()
    threshold = _env_float("EVAL_GROUND_THRESHOLD", 0.7)
    case_label = os.environ.get("EVAL_GROUND_DISC_CASE", "scroll-nocturno-fomo")
    retries = max(1, _env_int("EVAL_GROUND_DISC_RETRIES", 3))

    print_section("VALIDACIÓN DEL JUEZ DE GROUNDEDNESS — ¿DISCRIMINA O COMPLACE?")
    print(
        "Herramienta MANUAL y ORIENTATIVA. Puntúa tres outputs de control sobre el\n"
        "MISMO contexto real para ver si el juez local (8B) baja la nota a lo que no\n"
        "está fundamentado, o si le da score alto a todo (complacencia).\n"
        f"Caso: {case_label}  ·  Reintentos: {retries}  ·  Umbral marcador: {threshold:.2f}"
    )

    cases = {case.label: case for case in build_groundedness_cases()}
    case = cases.get(case_label)
    if case is None:
        available = ", ".join(sorted(cases))
        print(
            f"\nEl caso {case_label!r} no está en el banco de groundedness. "
            f"Disponibles: {available}.\n"
            "Ajusta EVAL_GROUND_DISC_CASE. No hay nada que validar."
        )
        return 0

    run = _obtain_plan_run(case, retries)
    if run is None:
        print(
            f"\nTras {retries} intentos no se obtuvo un plan real con contexto para "
            f"'{case_label}'.\n"
            "Causas posibles: el gate derivó repetidamente, el Planificador degradó, "
            "o el RAG/Ollama no están disponibles.\n"
            "Arranca Ollama (qwen3:8b + bge-m3) y construye el índice de Chroma, y "
            "reintenta. No hay validación que reportar."
        )
        return 0

    context = retrieval_context(run.retrieved)
    _print_context(context)

    judge = LocalJudge()
    controls = _build_controls(run)
    scored: list[ScoredControl] = []
    for control in controls:
        print(f"\nPuntuando control '{control.label}' ...")
        scored.append(_score_control(control, context, judge, threshold))

    _print_results(scored, threshold)
    _print_verdict(scored)
    return 0


if __name__ == "__main__":
    sys.exit(main())
