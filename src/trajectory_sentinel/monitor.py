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

"""trajectory-sentinel: async monitor / trajectory observer.

Consumes the LOCAL signal bus (adi-shield, wallet-guard publish there) and
produces a per-task trajectory record. It is an ASYNC CONSUMER, NOT a
real-time router: the sensors make the blocking decision inline; the monitor
only observes and aggregates AFTER the fact for human review / logging.

Confidence is NOT averaged blindly (SDD R4): we keep per-sensor confidence
and report the WORST (min) verdict-severity, never a smoothed mean that
could hide a hard block from one sensor behind a soft allow from another.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from adi_shield.bus import LocalSignalBus, Signal

SEVERITY = {"allow": 0, "confirm": 1, "block": 2, "kill": 3}


@dataclass
class TrajectoryRecord:
    task_id: str
    signals: list[Signal] = field(default_factory=list)
    worst_verdict: str = "allow"
    per_sensor: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "worst_verdict": self.worst_verdict,
            "per_sensor": self.per_sensor,
            "signal_count": len(self.signals),
            "signals": [s.to_dict() for s in self.signals],
        }


class TrajectorySentinel:
    def __init__(self, bus: LocalSignalBus) -> None:
        self.bus = bus
        self.records: dict[str, TrajectoryRecord] = defaultdict(
            lambda: TrajectoryRecord(task_id="")
        )
        self.bus.subscribe_all(self._on_signal)

    def _on_signal(self, s: Signal) -> None:
        rec = self.records[s.task_id]
        if rec.task_id == "":
            rec.task_id = s.task_id
        rec.signals.append(s)
        # worst severity wins; NOT an average
        if SEVERITY.get(s.verdict, 0) > SEVERITY.get(rec.worst_verdict, 0):
            rec.worst_verdict = s.verdict
        rec.per_sensor[s.sensor] = s.verdict

    def report(self, task_id: str) -> TrajectoryRecord | None:
        rec = self.records.get(task_id)
        return rec

    def summarize(self) -> dict[str, Any]:
        return {tid: r.to_dict() for tid, r in self.records.items()}
