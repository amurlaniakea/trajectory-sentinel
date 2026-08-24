# trajectory-sentinel

Monitor unificado que consume las señales de adi-shield, wallet-guard,
goal-anchor (y memlineage) vía el bus local, y presenta el peor veredicto por
tarea para revisión humana. Sensor del ecosistema de defensa de agentes IA
(scope-lib, adi-shield, wallet-guard, goal-anchor).

## Estado

MVP implementado y auditado.

## Qué hace (alcance real del MVP)

Este MVP es un **observador del bus**, no un router ni un correlador agregado:

- Consume las señales de los otros sensores por el bus local (no las muta).
- Calcula el **peor veredicto por tarea** (`allow < confirm < block < kill`),
  sin promediar la confianza a ciegas (cumple SDD R4).
- Expone `report` / `summarize` para revisión humana.

## Estado de correlación agregada (2026-07-19, implementado)

El SDD promete **correlación agregada de 2+ vectores** (AC1: cruzar las señales
de los sensores para detectar ataques que ninguno ve solo). Estado actual:

**IMPLEMENTADO:** `src/trajectory_sentinel/correlation.py` —
`CorrelationEngine` determnista que cruza las señales de una tarea
(adi-shield, wallet-guard, goal-anchor) y emite un veredicto agregado por
CORRELACIÓN, no solo worst-verdict. Reglas (0-LLM, deterministas):
- cualquier `block`/`kill` corta (worst-verdict ya lo haría, se hace explícito);
- `goal-anchor` reporta deriva (mechanism contiene `drift`/`semantic`) MIENTRAS
  los demás dan `allow` → escala a `confirm` agregado (caso WebTrap que solo el
  ancla ve, p.ej. T1/T2/T4 de goal-anchor donde adi-shield/wallet-guard pasan);
- ≥2 sensores en `confirm` simultáneo → `confirm` agregado (ambigüedad acumulada);
**Retractación selectiva POR SUB-OBJETIVO (correlation.py, regla 2):** la
correlación considera TODAS las derivas activas de la tarea (una por
sub-objetivo) y solo baja a `allow` (`correlation:drift_retracted`) cuando
TODAS han sido retractadas por autorización humana tardía. Si queda
CUALQUIER sub con deriva sin autorizar, el veredicto agregado sigue en
`confirm` (`correlation:drift_despite_allows`) — no se retracta de más ni se
silencia la deriva de un sub distinto de la primera. Cubierto por
`tests/test_integration_drift_selective.py` (dos derivas simultáneas, solo una
retractada → sigue `confirm`).

**Requisito de versión de goal-anchor (aviso honesto):** la retractación
selectiva depende de que `goal-anchor` emita el sub-objetivo en la señal de
deriva vía el campo `DriftSignal.subobjective` (serializado como
`:sub=<sub>` en el `detail` de `event="drift"`). Esto está presente en
`goal-anchor` **`main`** (>= commit donde P5 añadió `subobjective`). Instalar
desde la rama por defecto correcta de `goal-anchor` es obligatorio: versiones
que no incluyan `:sub=` en la señal de deriva (p.ej. la rama `scaffold/`
histórica, o cualquier checkout que no sea `main`) NO propagan el sub al
correlador y la retractación selectiva no puede emparejar deriva con
retractación — en ese caso el veredicto no baja de `confirm` a `allow` tras
una retractación aprobada. La CI de este repo instala `goal-anchor` desde su
`main` y corre los tests de integración (no se skipean) para detectar esta
regresión.

El `TrajectoryRecord.to_dict()` ya incluye la clave `correlated` con el
veredicto correlacionado por tarea. Tests: `tests/test_correlation.py` (7 casos
de correlación, incl. retractación), `tests/test_integration_drift.py` (E2E
bus real: DriftMonitor → Signal → TrajectorySentinel, incl. ampliación tardía
que retracta y revisa la correlación) y `tests/test_integration_drift_selective.py`
(caso difícil: dos derivas, una retractada → sigue `confirm`).

**Gap HONESTO que queda:** la correlación depende de que goal-anchor emite la
señal de deriva. Hasta que la Capa 2 de goal-anchor tenga un backend semántico
real operacional, la deriva semántica sutil (T1/T2/T4) no llega como señal a
trajectory-sentinel, así que la regla `correlation:drift_despite_allows` no se
dispara para esos casos. Es decir: el ecosistema completo cierra el vector
WebTrap BRUSCO hoy, pero el WebTrap SUTIL requiere el embedder semántico real
en Capa 2 (trabajo posterior acordado, documentado, no oculto).

## Instalación

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

Depende de `adi-shield` (bus local / esquema Signal).

## Calidad

- `ruff check .` limpio antes de cualquier PR.
- `pytest` con output crudo en todo PR.
- Sin push automático: Sil revisa el diff.

## Licencia

AGPL-3.0-or-later · Autor: Pedro Sordo Martínez (amurlaniakea@gmail.com) ·
Año: 2026
