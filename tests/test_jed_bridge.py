"""Test aislado de jed_bridge (trajectory-sentinel).

NO importa sensores: usa un dict con la forma de TrajectoryRecord.to_dict().
Verifica que el adaptador traduce señales -> events JED y no toca el núcleo.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trajectory_sentinel.jed_bridge import record_to_jed_trace, export_trace_jed


def _fake_record_dict() -> dict:
    return {
        "task_id": "T1",
        "worst_verdict": "block",
        "per_sensor": {"adi-shield": "block", "scope-lib": "allow"},
        "signal_count": 2,
        "signals": [
            {"sensor": "adi-shield", "verdict": "block", "event": "injection", "detail": "roleplay"},
            {"sensor": "scope-lib", "verdict": "allow", "event": "scope_ok", "detail": "within"},
        ],
    }


def main() -> None:
    trace = record_to_jed_trace(_fake_record_dict(), prompts=["haz X"])
    d = trace.to_dict()
    assert d["prompts"] == ["haz X"], d
    assert len(d["events"]) == 2, d
    assert d["events"][0]["tool"] == "adi-shield"
    assert d["events"][0]["result"] == "blocked", d  # block -> blocked
    assert d["events"][1]["result"] == "executed", d  # allow -> executed
    # API de conveniencia
    d2 = export_trace_jed(_fake_record_dict())
    assert d2["events"][1]["tool"] == "scope-lib"
    print(f"[ok] jed_bridge: {len(d['events'])} events traducidos, prompts={d['prompts']}")


if __name__ == "__main__":
    main()
