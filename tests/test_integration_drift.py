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

"""End-to-end integration: goal-anchor DriftSignal -> bus Signal ->
trajectory-sentinel correlation (closes the gap Claude flagged in point 4).
"""

from adi_shield.bus import LocalSignalBus, Signal
from goal_anchor.drift import DriftMonitor

from trajectory_sentinel.monitor import TrajectorySentinel


def _adi_signal(task_id: str, verdict: str, detail: str) -> Signal:
    return Signal(sensor="adi-shield", task_id=task_id, event="tool_call",
                  verdict=verdict, detail=detail)


def _wallet_signal(task_id: str, verdict: str, detail: str) -> Signal:
    return Signal(sensor="wallet-guard", task_id=task_id, event="tool_call",
                  verdict=verdict, detail=detail)


def test_drift_signal_publishes_to_bus_with_event_drift():
    dm = DriftMonitor(anchor_subobjectives=["a", "b", "c"], N=10,
                      support_threshold=0.99, drift_threshold=0.34)
    # 2 de 4 hitos fuera de ancla -> d_k = 0.5 > 0.34 -> alert
    dm.update("i_subobjective", "a")
    dm.update("iii_transitive", "a")
    dm.update("iii_transitive", "exfiltrate")
    sig = dm.update("iii_transitive", "exfiltrate2")
    assert sig.alert is True
    bus_sig = sig.to_signal("task-1")
    assert bus_sig is not None
    assert bus_sig.sensor == "goal-anchor"
    assert bus_sig.event == "drift"
    assert bus_sig.verdict == "confirm"
    assert "drift" in bus_sig.detail


def test_end_to_end_correlation_via_bus():
    bus = LocalSignalBus()
    sentinel = TrajectorySentinel(bus)
    tid = "task-e2e"

    # adi-shield y wallet-guard: allow (flujo autorizado, presupuesto ok)
    bus.publish(_adi_signal(tid, "allow", "cross_boundary"))
    bus.publish(_wallet_signal(tid, "allow", "budget_ok"))

    # goal-anchor: deriva (claimed fuera de ancla en paso 4 de T3-like)
    dm = DriftMonitor(anchor_subobjectives=["research_prices", "compare_options", "report_summary"],
                      N=10, support_threshold=0.99, drift_threshold=0.34)
    for step in [
        ("i_subobjective", "research_prices"),
        ("iii_transitive", "research_prices"),
        ("i_subobjective", "compare_options"),
        ("iii_transitive", "exfiltrate_data"),
    ]:
        d = dm.update(step[0], step[1])
    bus.publish(d.to_signal(tid))

    # trajectory-sentinel debe haber correlacionado a confirm
    rec = sentinel.report(tid)
    assert rec is not None
    correlated = rec.to_dict()["correlated"]
    assert correlated["verdict"] == "confirm", correlated
    assert correlated["mechanism"] == "correlation:drift_despite_allows"
