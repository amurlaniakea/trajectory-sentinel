# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Copyright (C) 2026 Pedro Sordo Martínez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/>.

"""Correlación agregada de 2+ vectores (trajectory-sentinel, SDD gap).

El monitor por defecto solo jerarquiza el PEOR veredicto por tarea (worst-
verdict). Eso no ve ataques que ningún sensor ve solo: p.ej. adi-shield y
wallet-guard dan ALLOW (flujo autorizado, presupuesto ok) pero goal-anchor
detecta DERIVA de objetivo. Cada señal por separado es benigna; la
COMBINACIÓN es sospechosa. Este módulo cruza las señales y emite un veredicto
agregado por correlación.

Determinista y 0-LLM (igual que el resto del ecosistema). Reglas documentadas
y testeables.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

SEVERITY = {"allow": 0, "confirm": 1, "block": 2, "kill": 3}


class SensorCalibration:
    """Calibración por sensor (SDD trajectory-sentinel R4).

    El campo `confidence` de cada sensor es un score BRUTO, no comparable
    entre sensores (0.7 de adi-shield != 0.7 de goal-anchor). Antes de
    combinar scores para un KILL agregado, hay que normalizar por sensor
    con curvas de calibración empíricas sobre benchmark. Esto evita el
    promedio naïf que el SDD prohíbe explícitamente.

    Por defecto (sin curva) es identidad: la calibración es OPCIONAL y no
    cambia el comportamiento actual (que usa worst-verdict, no KILL agregado
    por score). Se activa pasando curvas cuando se implemente KILL agregado.
    """

    def __init__(self, curves: dict[str, Callable] | None = None) -> None:
        # curves[sensor] = fn(score_bruto) -> score_calibrado en [0,1]
        self._curves = curves or {}

    def calibrate(self, sensor: str, raw: float) -> float:
        fn = self._curves.get(sensor)
        if fn is None:
            return max(0.0, min(1.0, raw))  # identidad por defecto
        return max(0.0, min(1.0, fn(raw)))


@dataclass
class CorrelatedVerdict:
    verdict: str  # allow | confirm | block
    mechanism: str  # por qué se correlacionó
    reason: str

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "mechanism": self.mechanism,
            "reason": self.reason,
        }


def correlate(signals: list[dict]) -> CorrelatedVerdict:
    """Cruza señales de múltiples sensores para una tarea.

    `signals`: lista de dicts {sensor, verdict, mechanism}.
    Reglas (en orden, primera que aplique):
      1. block/kill de cualquier sensor -> block (worst-verdict ya lo haría,
         pero lo hacemos explícito y cortamos).
      2. goal-anchor reporta deriva (mechanism contiene 'drift' o 'semantic')
         MIENTRAS los demás sensores dan allow -> correlación sospechosa:
         escala a CONFIRM agregado (atención humana). Un ataque que redirige
         el objetivo pero pasa los demás chequeos es exactamente el caso
         WebTrap que solo goal-anchor ve.
      3. >=2 sensores distintos en confirm simultáneo -> CONFIRM agregado
         (ambigüedad acumulada de múltiples fuentes).
      4. sino -> allow (no hay señal correlacionada).
    """
    if not signals:
        return CorrelatedVerdict("allow", "no_signals", "sin señales que correlar")

    verdicts = {s["sensor"]: s.get("verdict", "allow") for s in signals}

    # El bus de adi-shield NO tiene campo 'mechanism'; usa 'event' y 'detail'.
    # goal-anchor publica Signal(event="drift", detail="drift:soft_X"/"drift:alert").
    # La deriva se detecta ESTRICTAMENTE por event == "drift" (no por substring
    # del detail, para no colisionar con eventos de retractacion).
    def _is_drift(sig: dict) -> bool:
        # Comprobacion ESTRICTA por evento, no por substring del detail (punto 4
        # de auditoria: 'drift' en detail hacia que drift_retract tambien
        # contara como deriva). El evento del bus es el campo canonico.
        return sig.get("event") == "drift"

    # 1. cualquier block/kill corta
    for s in signals:
        if SEVERITY.get(s.get("verdict", "allow"), 0) >= SEVERITY["block"]:
            return CorrelatedVerdict(
                "block",
                f"hard_{s['sensor']}_block",
                f"{s['sensor']} bloqueó; correlación no anula block",
            )

    # 2. goal-anchor deriva mientras otros allow
    # P5: retractacion SELECTIVA por sub-objetivo. Puede haber varias senales
    # de deriva (una por sub) y varias de retract (una por sub). Consideramos
    # TODAS las derivas activas, no solo la primera: el veredicto agregado
    # baja a allow SOLO si TODAS las derivas de la tarea fueron retractadas;
    # si queda CUALQUIER sub con deriva sin autorizar, sigue en confirm
    # (no retractamos de mas ni ignoramos derivas distintas de la primera).
    ga_signals = [s for s in signals if s.get("sensor") == "goal-anchor"]
    drift_sigs = [s for s in ga_signals if s.get("event") == "drift"]
    # Subs con deriva activa (del :sub= en el detail de cada senal de drift).
    drift_subs = set()
    for s in drift_sigs:
        gm = re.search(r":sub=([^:\s]+)", s.get("detail", ""))
        if gm:
            drift_subs.add(gm.group(1))
        else:
            # deriva sin sub conocido: se trata como sub unico no retractable
            drift_subs.add("")
    # Subs retractados por autorizacion humana tardia (P5).
    # formato: retract:drift:<sub>:hitos=[...]
    retracted_subs = set()
    for s in ga_signals:
        if s.get("event") == "drift_retract":
            m = re.search(r"retract:drift:([^:]+):", s.get("detail", ""))
            if m:
                retracted_subs.add(m.group(1))
    if drift_sigs:
        others = [v for k, v in verdicts.items() if k != "goal-anchor"]
        others_all_allow = others and all(v == "allow" for v in others)
        if others_all_allow:
            active = drift_subs - retracted_subs
            if not active:
                # TODAS las derivas de la tarea fueron autorizadas
                # retroactivamente -> la correlacion revisa y baja a allow.
                # QUEDA REGISTRO de las retractaciones (no se ocultan).
                return CorrelatedVerdict(
                    "allow",
                    "correlation:drift_retracted",
                    "goal-anchor retracto TODAS las derivas de la tarea "
                    "(autorizacion humana tardia): correlacion revisa y baja a allow",
                )
            # queda >=1 sub con deriva activa sin autorizar -> confirm
            return CorrelatedVerdict(
                "confirm",
                "correlation:drift_despite_allows",
                "goal-anchor detecta deriva pero adi-shield/wallet-guard dan allow: "
                "ataque WebTrap que solo el ancla ve -> atencion humana",
            )

    # 3. >=2 sensores en confirm simultáneo
    confirming = [k for k, v in verdicts.items() if v == "confirm"]
    if len(confirming) >= 2:
        return CorrelatedVerdict(
            "confirm",
            "correlation:multi_confirm",
            f"múltiples sensores ({confirming}) en confirm simultáneo",
        )

    return CorrelatedVerdict("allow", "no_correlation", "sin correlación sospechosa")
