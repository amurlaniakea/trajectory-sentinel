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

## Gap conocido (NO implementado en este MVP)

El SDD promete **correlación agregada de 2+ vectores** (AC1: cruzar las señales
de los sensores para detectar ataques que ninguno ve solo). Ese mecanismo
**aún no existe** en el código: `trajectory-sentinel` hoy solo registra y
jerarquiza señales individuales por tarea. Es un MVP honesto de la fase de
observador, no del correlador. Queda pendiente como trabajo posterior antes
de declararlo cobertura completa del SDD.

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
