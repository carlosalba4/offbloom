# ADR-005: Fiabilidad del juez local para evaluar groundedness

- **Estado**: aceptado
- **Fecha**: 2026-06-28

## Contexto
Para medir la fundamentación (groundedness) de los planes montamos una suite con DeepEval usando como juez el LLM local (qwen3:8b), por la decisión previa de no usar API de pago en esta etapa de aprendizaje. La suite daba un score medio de 0.96, aparentemente excelente.

## Hallazgo
Una prueba de discriminación reveló que ese 0.96 no era fiable. Al puntuar tres outputs de control sobre el mismo contexto recuperado, el juez dio 1.00 a un plan deliberadamente inventado (con cifras y estudios falsos ausentes del contexto), 0.89 al plan realmente fundamentado (penalizándolo por una contradicción que el propio juez se inventó) y 0.83 al mixto. El gap entre el bueno y el inventado fue de −0.11: el orden quedó al revés del esperado. El juez no discrimina; tiene sesgo de complacencia.

## Interpretación (el matiz)
El mismo modelo local funcionaba bien como evaluador en el gate de seguridad, donde la tarea es un juicio binario y holístico (¿activar la derivación, sí o no?). En groundedness la tarea es muy distinta: descomponer el plan en afirmaciones y verificar cada una contra el contexto recuperado, un análisis fino que supera a un 8B. No es que el modelo sea malo; es que su capacidad depende de la dificultad de la tarea, y esta lo excede.

## Decisión
La suite de groundedness queda montada y lista (la mecánica es correcta y el juez es intercambiable por configuración), pero sus scores no se consideran fiables hasta sustituir el juez local por uno de API más capaz, lo que se difiere a una fase posterior.

## Lo aprendido
Validar el evaluador es tan importante como evaluar el sistema. Sin la prueba de discriminación, el 0.96 habría sido un falso positivo de calidad que nos habríamos creído.

## Consecuencias
- **Positivas**: La mecánica de groundedness queda construida y rodada: capturar el contexto recuperado, serializar el plan, invocar la métrica. Cambiar de juez no requiere reescribir nada. El juez es intercambiable por configuración (LocalJudge vía variables de entorno), así que migrar a un juez de API será un cambio de config, no de código. La prueba de discriminación queda como herramienta reutilizable para validar el futuro juez de API antes de fiarnos de sus números.
- **Negativas**: Por ahora no tenemos una medida fiable de la fundamentación de los planes: sabemos que la mecánica funciona, pero no podemos afirmar con datos cuánto se apoyan los planes en el corpus. Queda trabajo diferido (sustituir el juez y re-validar) que habrá que retomar antes de presentar métricas de calidad como sólidas.

## Alternativas descartadas
- **Sacar ya una API key** y usar un juez de API. Daría números fiables ahora mismo, pero introduce un coste y una dependencia externa que no se justifican en esta etapa de aprendizaje sin búsqueda de empleo inmediata. Se difiere a una fase posterior (cerca del despliegue), donde aportará más sobre un proyecto ya pulido.
- **Fiarnos del 0.96 del juez local** y dar groundedness por buena. Rechazado: la prueba de discriminación demostró que ese número no mide fundamentación, sino la complacencia del juez. Habría sido un falso positivo de calidad.
- **Intentar afinar el prompt del juez local** o usar un modelo local algo mayor. Rechazado: la tarea (verificar fundamentación afirmación por afirmación) excede a un 8B por naturaleza; afinarlo sería esfuerzo con techo bajo, sin atacar la causa real (la capacidad del modelo para esa tarea).