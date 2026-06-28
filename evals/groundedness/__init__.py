"""Suite de evals de groundedness/faithfulness del plan del coach (DeepEval).

Mide si el plan semanal que emite el Planificador está FUNDAMENTADO en los
fragmentos de conocimiento recuperados por el RAG (filosofía "sustituir, no
prohibir", anclada en el corpus). Usa la `FaithfulnessMetric` de DeepEval con un
LLM-judge local (qwen3:8b vía Ollama). El runner manual vive en
`scripts/eval_groundedness.py`.
"""
