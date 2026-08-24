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

"""trajectory-sentinel tests: monitor consumes bus, worst-verdict NOT averaged."""

from adi_shield.bus import LocalSignalBus, Signal

from trajectory_sentinel.monitor import SEVERITY, TrajectorySentinel


def _sig(sensor: str, task_id: str, verdict: str) -> Signal:
    return Signal(
        sensor=sensor,
        task_id=task_id,
        event="tool_call",
        verdict=verdict,
        scope_in=True,
        confidence=0.9,
    )


def test_worst_verdict_not_averaged():
    bus = LocalSignalBus()
    mon = TrajectorySentinel(bus)
    # wallet-guard allows, adi-shield blocks -> worst must be block (not mean)
    bus.publish(_sig("wallet-guard", "t1", "allow"))
    bus.publish(_sig("adi-shield", "t1", "block"))
    rec = mon.report("t1")
    assert rec is not None
    assert rec.worst_verdict == "block"
    assert rec.per_sensor == {"wallet-guard": "allow", "adi-shield": "block"}


def test_monitor_is_observer_not_router():
    bus = LocalSignalBus()
    mon = TrajectorySentinel(bus)
    # the monitor records but does NOT modify the signal
    s = _sig("adi-shield", "t2", "confirm")
    bus.publish(s)
    rec = mon.report("t2")
    assert rec is not None
    assert len(rec.signals) == 1
    assert rec.signals[0].verdict == "confirm"
    assert rec.worst_verdict == "confirm"


def test_severity_ordering():
    assert SEVERITY["allow"] < SEVERITY["confirm"] < SEVERITY["block"]
