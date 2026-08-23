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
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""jed_bridge: adaptador de formato de traza entre trajectory-sentinel y el benchmark JED.

ESTE MÓDULO ES UN ADAPTADOR DESACOPLADO. No toca monitor.py ni correlation.py.
No importa sensores (adi_shield, scope_lib, goal_anchor, wallet_guard): recibe
YA los datos estructurados de TrajectoryRecord (vía .to_dict()) y solo los
reformatea a la estructura de traza que el benchmark de la industria (JED /
Kaggle AI Agent Security) entiende:

    JED Trace = {
        "prompts": [str, ...],                 # lo que se envió al agente
        "events": [{"tool": str, "args": {}, "result": str}, ...]  # tool events en orden
    }

Mapa de responsabilidad (solo formato, NO semántica):
    - TrajectoryRecord.signals  -> events (tool = sensor, args = detail, result = verdict)
    - TrajectoryRecord no tiene "prompts" directos (es observador del bus); el puente
      los deja vacíos salvo que el llamador los aporte. El runtime es quien conoce los
      prompts reales (ver agent_shield_runtime/jed_trace.py).

NO se activa en el pipeline: monitor.py NO importa este módulo. Es para revisión
humana y para alimentar red-team offline (blankbox) contra el propio stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Replicamos la estructura mínima de JED localmente para no acoplar al SDK ajeno.
# (Si el SDK oficial está instalado, estos nombres coinciden con aicomp_sdk.core.)
@dataclass
class JedToolEvent:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass
class JedTrace:
    prompts: list[str] = field(default_factory=list)
    events: list[JedToolEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "prompts": self.prompts,
            "events": [
                {"tool": e.tool, "args": e.args, "result": e.result} for e in self.events
            ],
        }


# Mapa de veredictos internos -> result JED (lo que el sensor decidió)
_VERDICT_TO_RESULT = {
    "allow": "executed",
    "confirm": "flagged_for_review",
    "block": "blocked",
    "kill": "killed",
}


def record_to_jed_trace(record: Any, prompts: list[str] | None = None) -> JedTrace:
    """Convierte un TrajectoryRecord (o su .to_dict()) a JedTrace.

    Args:
        record: instancia de TrajectoryRecord, o dict devuelto por .to_dict().
        prompts: opcional; secuencia de prompts del agente si el llamador la conoce.

    El adaptador solo LEE campos estructurados; no importa sensores.
    """
    if hasattr(record, "to_dict"):
        d = record.to_dict()
    else:
        d = record

    prompts_list: list[str] = list(prompts) if prompts else []
    events: list[JedToolEvent] = []
    for sig in d.get("signals", []):
        # sig es dict: {sensor, verdict, event, detail, ...}
        tool = sig.get("sensor") or "unknown"
        args = {"event": sig.get("event"), "detail": sig.get("detail")}
        result = _VERDICT_TO_RESULT.get(sig.get("verdict", "allow"), "executed")
        events.append(JedToolEvent(tool=tool, args=args, result=result))
    return JedTrace(prompts=prompts_list, events=events)


def export_trace_jed(record: Any, prompts: list[str] | None = None) -> dict:
    """API de conveniencia: devuelve el dict de traza JED (listo para blankbox)."""
    return record_to_jed_trace(record, prompts).to_dict()
