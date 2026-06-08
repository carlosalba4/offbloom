# PRD — Wellbeing Coach

> Documento de producto, versión profesional y delgada. No académico: solo lo que
> aporta valor de producto.

## 1. Problema

Reducir el uso del móvil con apps que solo *bloquean* falla: el hábito ocupaba un
hueco (descanso, conexión, alivio del aburrimiento o del estrés) y, si solo se
quita sin poner nada en su lugar, el vacío empuja a la recaída. Falta
acompañamiento que **sustituya**, no que prohíba.

## 2. Persona principal

**Profesional de 25-40 años con *scroll* nocturno.** Trabaja, es consciente de que
el móvil por la noche le roba sueño y tiempo de calidad, y quiere recuperarlos
**sin renunciar al móvil**. Espera propuestas concretas y de baja fricción, no
sermones ni bloqueos.

Personas secundarias / futuras (no encajonar el producto): estudiante con
problemas de foco y procrastinación; *knowledge worker* en burnout digital
("always-on"). El diseño no debe cerrarles la puerta, pero el MVP se optimiza para
la persona principal.

## 3. Propuesta de valor — "sustituir, no prohibir"

El diferencial es el **Curador**: propone alternativas *offline* **contextualizadas**
(según tiempo disponible, energía, lugar y momento de la persona), no una lista
fija. El consejo está **fundamentado por el corpus** (RAG), no inventado.

La **privacidad es una capacidad de la arquitectura**: cualquiera puede
self-hostar 100% local con Ollama. No es una promesa sobre el demo alojado (que
corre con un proveedor de nube).

## 4. Alcance del MVP

- **Onboarding**: objetivos, intereses y restricciones (tiempo, energía, lugar,
  preferencia social).
- **Datos de uso simulados o autoreportados** — sin integración real del tiempo de
  pantalla del SO.
- **Coach agéntico** Analista → Planificador → Curador, con un **gate de seguridad**
  previo a la planificación.
- **Salida**: un plan semanal + 3 actividades contextualizadas, con **cita de la
  fuente** del corpus.
- **API** (FastAPI) + **frontend** (Next.js).

## 5. Fuera de alcance (MVP)

Móvil nativo, integración real del tiempo de pantalla del SO, predicción/ML,
social y gamificación, multi-usuario con persistencia de cuentas.

## 6. Seguridad (requisito bloqueante)

El coach toca un dominio sensible (bienestar). Ante **señales de riesgo** (malestar
persistente, uso que interfiere seriamente con sueño/trabajo/relaciones, sensación
de no poder parar) **no planifica**: deriva con empatía a ayuda profesional, sin
consejo clínico ni nombres de fármacos, y **sin teléfonos hardcodeados** —apunta a
recursos mantenidos y adecuados a la región. Lo verifican las evals de seguridad y
es bloqueante. Referencia de comportamiento: `data/corpus/08-seguridad-y-limites.md`.

## 7. Criterios de éxito

- La **demo de 90s** funciona end-to-end (onboarding → plan + actividades).
- Las **evals** de relevancia, *groundedness* y seguridad superan su umbral.
- Toda ejecución del grafo queda **trazada en Langfuse**.
