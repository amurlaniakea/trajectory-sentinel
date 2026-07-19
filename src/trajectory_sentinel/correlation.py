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

from dataclasses import dataclass

SEVERITY = {"allow": 0, "confirm": 1, "block": 2, "kill": 3}


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

    sensors = {s["sensor"]: s for s in signals}
    verdicts = {s["sensor"]: s.get("verdict", "allow") for s in signals}
    # El bus de adi-shield NO tiene campo 'mechanism'; usa 'event' y 'detail'.
    # goal-anchor publica Signal(event="drift", detail="drift:soft_X"/"drift:alert").
    # Aceptamos ambos: event == "drift" O detail conteniendo 'drift'/'semantic'.
    def _is_drift(sig: dict) -> bool:
        ev = sig.get("event", "")
        det = sig.get("detail", "")
        return (ev == "drift") or ("drift" in det) or ("semantic" in det)

    # 1. cualquier block/kill corta
    for s in signals:
        if SEVERITY.get(s.get("verdict", "allow"), 0) >= SEVERITY["block"]:
            return CorrelatedVerdict(
                "block", f"hard_{s['sensor']}_block",
                f"{s['sensor']} bloqueó; correlación no anula block",
            )

    # 2. goal-anchor deriva mientras otros allow
    ga = sensors.get("goal-anchor")
    if ga is not None:
        ga_is_drift = _is_drift(ga)
        others = [v for k, v in verdicts.items() if k != "goal-anchor"]
        others_all_allow = others and all(v == "allow" for v in others)
        if ga_is_drift and others_all_allow:
            return CorrelatedVerdict(
                "confirm", "correlation:drift_despite_allows",
                "goal-anchor detecta deriva pero adi-shield/wallet-guard dan allow: "
                "ataque WebTrap que solo el ancla ve -> atención humana",
            )

    # 3. >=2 sensores en confirm simultáneo
    confirming = [k for k, v in verdicts.items() if v == "confirm"]
    if len(confirming) >= 2:
        return CorrelatedVerdict(
            "confirm", "correlation:multi_confirm",
            f"múltiples sensores ({confirming}) en confirm simultáneo",
        )

    return CorrelatedVerdict("allow", "no_correlation", "sin correlación sospechosa")
