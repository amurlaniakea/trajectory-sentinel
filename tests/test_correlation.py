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
    # El bus de adi-shield usa 'event'/'detail', no 'mechanism'.
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "event": "tool_call",
         "detail": "cross_boundary"},
        {"sensor": "wallet-guard", "verdict": "allow", "event": "tool_call",
         "detail": "budget_ok"},
        {"sensor": "goal-anchor", "verdict": "confirm", "event": "drift",
         "detail": "drift:alert_soft_0.9"},
    ])
    assert v.verdict == "confirm"
    assert v.mechanism == "correlation:drift_despite_allows"


def test_goal_anchor_semantic_drift_correlates():
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "event": "tool_call", "detail": "x"},
        {"sensor": "goal-anchor", "verdict": "confirm", "event": "drift",
         "detail": "semantic:drift_0.8"},
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


def test_drift_retract_reviews_correlated_verdict():
    # caso del matiz del usuario: hubo deriva (confirm) que correlacionó a
    # confirm; luego goal-anchor retracta -> el veredicto agregado se REVISA
    # y baja a allow, pero registra drift_retracted (no se oculta).
    v = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "event": "tool_call",
         "detail": "cross_boundary"},
        {"sensor": "wallet-guard", "verdict": "allow", "event": "tool_call",
         "detail": "budget_ok"},
        {"sensor": "goal-anchor", "verdict": "confirm", "event": "drift",
         "detail": "drift:alert_soft_0.5"},
    ])
    assert v.verdict == "confirm"
    assert v.mechanism == "correlation:drift_despite_allows"
    # llega la retractacion
    v2 = correlate([
        {"sensor": "adi-shield", "verdict": "allow", "event": "tool_call",
         "detail": "cross_boundary"},
        {"sensor": "wallet-guard", "verdict": "allow", "event": "tool_call",
         "detail": "budget_ok"},
        {"sensor": "goal-anchor", "verdict": "confirm", "event": "drift",
         "detail": "drift:alert_soft_0.5"},
        {"sensor": "goal-anchor", "verdict": "allow", "event": "drift_retract",
         "detail": "drift_retract:verify:hitos=[2]"},
    ])
    assert v2.verdict == "allow"
    assert v2.mechanism == "correlation:drift_retracted"
