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
# GNU Affero General License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/>.

"""Caso difícil de retractación selectiva (P5): DOS derivas simultáneas en
sub-objetivos distintos, solo UNA retractada por autorización humana tardía.

Objetivo: verificar que la selectividad es REAL, no casualidad del caso de
un solo sub. Si la deriva del sub NO retractado sigue activa, el veredicto
agregado debe seguir en `confirm` (no bajar a allow solo porque el otro sub
fue autorizado). Es el escenario que el README documenta como "gap conocido"
pero aquí lo usamos para probar que el sistema NO retracta de más.

SKIP en clone fresco sin adi-shield/goal-anchor (no falla silenciosamente).
"""

import pytest

adi_shield = pytest.importorskip("adi_shield")
goal_anchor = pytest.importorskip("goal_anchor")

from adi_shield.bus import LocalSignalBus, Signal
from goal_anchor.anchor import AnchorProposal, GoalAnchor

from trajectory_sentinel.monitor import TrajectorySentinel


def _adi_signal(task_id: str, verdict: str, detail: str) -> Signal:
    return Signal(
        sensor="adi-shield", task_id=task_id, event="tool_call", verdict=verdict, detail=detail
    )


def _force_drift(ga: GoalAnchor, task_id: str, claimed: str):
    """Fuerza alert=True en el DriftMonitor de la tarea (mismo patrón que el
    test simple de la suite): 2 de 4 hitos fuera de ancla -> supera umbral."""
    ga.report_drift(task_id, "i_subobjective", claimed)
    ga.report_drift(task_id, "iii_transitive", claimed)
    sig = ga.report_drift(task_id, "iii_transitive", claimed)
    return sig


def test_two_simultaneous_drifts_only_one_retracted_stays_confirm(tmp_path):
    """Dos subs derivan (A y B) en la MISMA tarea; el humano solo retracta A.
    La deriva de B sigue activa -> veredicto agregado debe seguir `confirm`
    (NO bajar a allow por la retractación de A)."""
    store_path = str(tmp_path / "store.json")
    ga = GoalAnchor(store_path, human_secret="x")
    anchor = ga.propose(
        AnchorProposal(
            task_id="t-sel",
            objective="investiga vuelos",
            subobjectives=["research_prices", "compare_options"],
        )
    )
    ga.confirm(anchor)

    # Deriva del sub A
    drift_a = _force_drift(ga, "t-sel", "exfiltrate_A")
    assert drift_a is not None
    drift_a_sig = drift_a.to_signal("t-sel")
    assert drift_a_sig.event == "drift"

    # Deriva del sub B (mismo monitor de la tarea, otro claimed)
    drift_b = _force_drift(ga, "t-sel", "exfiltrate_B")
    assert drift_b is not None
    drift_b_sig = drift_b.to_signal("t-sel")
    assert drift_b_sig.event == "drift"

    bus = LocalSignalBus()
    sentinel = TrajectorySentinel(bus)
    bus.publish(drift_a_sig)
    bus.publish(drift_b_sig)
    bus.publish(_adi_signal("t-sel", "allow", "cross_boundary"))

    before = sentinel.report("t-sel")
    before_c = before.to_dict()["correlated"]
    # Con dos derivas activas y adi allow -> confirm
    assert before_c["verdict"] == "confirm", before_c

    # Humano retracta SOLO el sub A
    res = ga.confirm_amplification("t-sel", "exfiltrate_A", bus=bus)
    assert res["retraction"], res

    after = sentinel.report("t-sel")
    after_c = after.to_dict()["correlated"]
    # B sigue sin retractar -> NO debe bajar a allow: la deriva de B persiste
    assert after_c["verdict"] == "confirm", (
        f"retractar solo A no debe limpiar la deriva de B: {after_c}"
    )
    assert after_c["mechanism"] == "correlation:drift_despite_allows", after_c
