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

"""Tests for the aggregated correlation engine (trajectory-sentinel)."""

from trajectory_sentinel.correlation import correlate


def test_single_allow_is_allow():
    sig = [{"sensor": "adi-shield", "verdict": "allow", "mechanism": "x"}]
    assert correlate(sig).verdict == "allow"


def test_block_short_circuits():
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "mechanism": "x"},
        {"sensor": "wallet-guard", "verdict": "block", "mechanism": "budget"},
    ])
    assert v.verdict == "block"
    assert "wallet-guard" in v.mechanism


def test_goal_anchor_drift_while_others_allow_correlates():
    # WebTrap: goal-anchor ve deriva, los demás dan allow
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "mechanism": "cross_boundary"},
        {"sensor": "wallet-guard", "verdict": "allow", "mechanism": "budget_ok"},
        {"sensor": "goal-anchor", "verdict": "allow", "mechanism": "drift:soft_0.9"},
    ])
    assert v.verdict == "confirm"
    assert v.mechanism == "correlation:drift_despite_allows"


def test_goal_anchor_semantic_drift_correlates():
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "mechanism": "x"},
        {"sensor": "goal-anchor", "verdict": "allow", "mechanism": "semantic:drift_0.8"},
    ])
    assert v.verdict == "confirm"


def test_multi_confirm_correlates():
    v = correlate([
        {"sensor": "adi-shield", "verdict": "confirm", "mechanism": "instruction_from_data"},
        {"sensor": "wallet-guard", "verdict": "confirm", "mechanism": "adi_confirm"},
    ])
    assert v.verdict == "confirm"
    assert v.mechanism == "correlation:multi_confirm"


def test_no_correlation_when_one_confirm_alone():
    # un solo confirm sin deriva ni otro confirm -> allow
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "mechanism": "x"},
        {"sensor": "wallet-guard", "verdict": "confirm", "mechanism": "adi_confirm"},
    ])
    assert v.verdict == "allow"
