"""
Stage 4B.3a — oracle temporal independente (REAL_DERIVED_TEST_RESULT).

O oracle (`audit/stage4b/oracle/oracle_temporal.py`) é Python puro (datetime/calendar, sem app/):
calcula janelas e recalcula todas as agregações a partir dos diários brutos da execução.
Os testes provam a concordância com o engine (T1 + T2 versionados; T2 ao vivo), a pureza do
módulo e que o confronto detecta um desvio (não é vacuamente verde).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ORACLE = REPO / "audit" / "stage4b" / "oracle"
sys.path[:0] = [str(ORACLE), str(REPO / "audit" / "stage4b"), str(REPO / "audit" / "stage4a")]

import oracle_temporal as oracle  # noqa: E402
import run_oracle_4b as driver  # noqa: E402

TYPES = ["AVERAGE", "MOVING_AVERAGE", "SUM", "WEIGHTED_AVERAGE"]


@pytest.fixture(scope="module")
def live_t2():
    completed = subprocess.run([sys.executable, str(ORACLE / "run_oracle_4b.py"), "--no-write", "--ranges", "T2"],
                               cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_oracle_t2_and_stated_run(live_t2):
    code, out, stderr = live_t2
    assert code == 0, (out["problems"][:5], stderr[-1000:])
    assert out["agree"] == out["compared"] == out["bitwise_equal"]
    assert out["types_covered"] == TYPES
    assert out["by_range"]["STATED_2026-01-01_10"]["aggregations"]["AVERAGE"]["state"] > 0


def test_committed_oracle_covers_every_aggregation_on_t1_and_t2():
    s = json.loads((ORACLE / "evidence" / "oracle_temporal_summary.json").read_text(encoding="utf-8"))
    assert s["result"] == "PASS" and s["label"] == "REAL_DERIVED_TEST_RESULT"
    assert (s["rules"], s["rule_instances"]) == (207, 417)
    assert s["by_range"]["T1"]["compared"] == 417 * 396 and s["by_range"]["T2"]["compared"] == 417 * 62
    assert s["agree"] == s["compared"] == s["bitwise_equal"]
    for label in ("T1", "T2"):
        assert s["by_range"][label]["calendar_mismatches"] == 0
        assert sorted(s["by_range"][label]["aggregations"]) == TYPES
    assert any("não correção de negócio" in x for x in s["limitations"])
    assert s["tolerance"] == {"rel_tol": 1e-12, "abs_tol": 1e-12, "states": "igualdade exata"}


def test_oracle_module_is_pure():
    assert driver.oracle_is_pure() == []
    probe = ("import sys; sys.path.insert(0, %r); import oracle_temporal; "
             "print(sorted(m for m in sys.modules if m == 'app' or m.startswith(('app.', 'tools'))))" % str(ORACLE))
    out = subprocess.run([sys.executable, "-I", "-c", probe], cwd=REPO, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_oracle_windows_are_calendar_arithmetic():
    monthly = {"aggregation_type": "AVERAGE", "target_frequency": "mensal", "aggregation_rule_id": "m"}
    annual = {"aggregation_type": "SUM", "target_frequency": "anual", "aggregation_rule_id": "a"}
    moving = {"aggregation_type": "MOVING_AVERAGE", "target_frequency": "diário", "aggregation_rule_id": "x"}
    assert len(oracle.window(monthly, date(2028, 2, 29))) == 29
    assert len(oracle.window(annual, date(2028, 2, 29))) == 60
    assert len(oracle.window(annual, date(2026, 12, 31))) == 365
    assert oracle.window(moving, date(2026, 3, 1)) == [date(2026, 3, 1)]          # reinício mensal
    assert oracle.target_key({**annual, "target_variable_id": "V", "scope_type": "linha", "scope_value": "L1"},
                             date(2027, 1, 1)) == ("V", "linha", "L1", "2027", "2027-01-01")


def _tiny_store():
    store = {}
    for n, value in enumerate((1.0, 2.0, 4.0), start=1):
        store[("S", "linha", "L1", f"2026-01-0{n}", None)] = ["float", repr(value), None, None]
    return store


def test_negative_oracle_detects_a_changed_daily_value_and_a_wrong_aggregate():
    rule = {"aggregation_rule_id": "R", "aggregation_type": "AVERAGE", "source_variable_id": "S",
            "target_variable_id": "T", "target_frequency": "mensal", "scope_type": "linha", "scope_value": "L1",
            "integration_factor": 1.0}
    store = _tiny_store()
    expected = oracle.aggregate(rule, store, date(2026, 1, 3))
    assert expected == ("VALUE", 7.0 / 3)
    store[oracle.target_key(rule, date(2026, 1, 3))] = ["float", repr(7.0 / 3 + 1e-9), None, None]
    assert driver.compare(driver.engine_result(store, oracle.target_key(rule, date(2026, 1, 3))), expected) == (False, False)
    store[("S", "linha", "L1", "2026-01-02", None)] = ["NoneType", "None", "INVALID_INPUT", "x"]
    assert oracle.aggregate(rule, store, date(2026, 1, 3)) == ("STATE", ("INVALID_INPUT", "x"))
    del store[("S", "linha", "L1", "2026-01-01", None)]
    with pytest.raises(KeyError):                                       # lacuna: o oracle também não inventa
        oracle.aggregate(rule, store, date(2026, 1, 3))
