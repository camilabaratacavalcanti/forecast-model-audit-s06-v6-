"""
Stage 4B.2 — harness temporal anual (REAL_DERIVED_TEST_RESULT).

Validam `audit/stage4b/temporal/run_temporal_4b.py`:
    * execução viva de T2 (2028, bissexto; 62 datas) com todas as verificações por data,
      reexecução, conflito de entrada e determinismo (ORDER_A/B, PYTHONHASHSEED 0/4242);
    * evidência versionada de T1 (396 datas, virada 2026 -> 2027) e T3 (792 datas):
      janelas em todos os fins de mês, 365 janelas anuais ao fim de 2026, 2027 nasce com 1,
      períodos encerrados imutáveis, invariante de prefixo contra a 4A, estado ao longo do ano.
Nenhum teste altera app/, data/ ou tools/.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "audit" / "stage4b" / "temporal"
EVIDENCE = HARNESS / "evidence"
sys.path[:0] = [str(REPO / "audit" / "stage4b"), str(HARNESS), str(REPO / "audit" / "stage4a")]

import independent_calendar as cal  # noqa: E402
import run_temporal_4b as harness  # noqa: E402

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_registry as reg  # noqa: E402  (Stage 4C: referência do registro, classe R)

REF = reg.load_json("stage4b_contract", "contract_expectations_4b.json")["temporal"]


def summary(label):
    return json.loads((EVIDENCE / label / "temporal_summary.json").read_text(encoding="utf-8"))


def rows(label, name):
    return list(csv.DictReader((EVIDENCE / label / name).open(encoding="utf-8")))


@pytest.fixture(scope="module")
def live_t2():
    completed = subprocess.run([sys.executable, str(HARNESS / "run_temporal_4b.py"), "--range", "T2", "--no-write",
                                *reg.harness_args()], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_t2_leap_year_passes(live_t2):
    code, out, stderr = live_t2
    assert code == 0, (out["problems"], stderr[-1500:])
    assert out["dates"] == {"count": 62, "first": "2028-01-01", "last": "2028-03-02"}
    assert out["per_date"] == {"targets": [REF["targets"]], "nodes": [REF["planner_nodes"]],      # B0: 446/458/896/67
                               "events": [REF["events_per_date"]], "transfer_events": [REF["transfer_events_per_date"]]}
    assert out["closed_periods"] == {"checked": 2, "unchanged": 2}


@pytest.mark.parametrize("label,count", [("T1", 396), ("T2", 62), ("T3", 792)])
def test_committed_runs_cover_every_date(label, count):
    s = summary(label)
    assert s["result"] == "PASS" and s["problems"] == [] and s["label"] == "REAL_DERIVED_TEST_RESULT"
    assert s["dates"]["count"] == count == len(cal.days(*(cal.RANGES[label])))
    assert s["per_date"] == {"targets": [446], "nodes": [458], "events": [896], "transfer_events": [67]}
    assert s["closed_periods"]["checked"] == s["closed_periods"]["unchanged"] > 0
    coverage = rows(label, "temporal_coverage.csv")
    assert [r["date"] for r in coverage] == [d.isoformat() for d in cal.days(*(cal.RANGES[label]))]


@pytest.mark.parametrize("label", ["T1", "T2", "T3"])
def test_identities_and_windows_follow_the_calendar(label):
    for r in rows(label, "identities_by_date.csv"):
        expected = cal.expected_windows(__import__("datetime").date.fromisoformat(r["date"]))
        assert int(r["monthly_windows_each"]) == expected["monthly"]
        assert int(r["annual_windows_each"]) == expected["annual"]
        assert (r["monthly_identities"], r["annual_identities"]) == ("324", "196")
        assert r["new_keys"] == r["expected_new_keys"]


def test_t1_turn_of_year_and_closed_periods():
    s = summary("T1")
    ids = {r["date"]: r for r in rows("T1", "identities_by_date.csv")}
    assert ids["2026-12-31"]["annual_windows_each"] == "365" and ids["2027-01-01"]["annual_windows_each"] == "1"
    assert ids["2027-01-01"]["monthly_windows_each"] == "1"
    assert s["year_ends"] == ["2026-12-31"] and len(s["month_ends"]) == 13
    snapshots = json.loads((EVIDENCE / "T1" / "period_snapshots.json").read_text(encoding="utf-8"))
    assert "2026" in snapshots and all(v["unchanged"] for v in snapshots.values())
    assert len([p for p in snapshots if len(p) == 7]) == 12              # jan..dez de 2026 encerrados
    reex = json.loads((EVIDENCE / "T1" / "reexecution.json").read_text(encoding="utf-8"))
    for day in ("2026-02-28", "2026-12-31", "2027-01-01"):
        assert reex[day]["same_store"] and reex[day]["new_keys"] == 0
        assert reex[day]["first_run_transfer_statuses"] == {"WRITTEN": 67}
        assert reex[day]["transfer_statuses"] == {"UNCHANGED": 67}
    assert reex["conflict_on_changed_upstream_input"]["error"] == "INTERBLOCK_CONSUMER_VALUE_CONFLICT"
    e3 = reex["missing_new_year_input"]
    assert e3["date"] == "2027-01-01" and e3["previous_year_value_exists"] and e3["error"]["type"] == "VariableNotFoundError"


@pytest.mark.parametrize("label", ["T1", "T3"])
def test_prefix_invariant_against_stage_4a(label):
    p = summary(label)["prefix_invariant"]
    assert p["differences"] == 0 and p["keys_compared"] > 30000
    assert p["prefix_subset_sha256"] == p["reference_4a_store_sha256"] == p["recomputed_4a_store_sha256"]


def test_state_over_the_year_and_isolation_between_years():
    state = json.loads((EVIDENCE / "T1" / "state_scenarios.json").read_text(encoding="utf-8"))
    assert state["problems"] == [] and state["must_keys"] > 0 and state["plain_keys"] > 0
    assert state["l4_l5_2026_keys_identical_to_clean"] is True
    assert set(state["injections"]) == {"2026-03-10", "2026-12-31", "2027-01-01"}


def test_determinism_configurations():
    t2, t1 = summary("T2")["determinism"], summary("T1")["determinism"]
    assert set(t2) == {"RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B"} and set(t1) == {"RUN_A", "RUN_B"}
    for runs in (t1, t2):
        assert len({r["results_sha256"] for r in runs.values()}) == 1
        assert len({r["store_sha256"] for r in runs.values()}) == 1
    assert {t2[k]["hash_seed"] for k in ("HASH_SEED_A", "HASH_SEED_B")} == {"0", "4242"}
    assert t2["RUN_B"]["order"] == "B" and t1["RUN_B"]["order"] == "B"


def test_performance_ratio_within_limit_and_t3_leap_and_two_year_ends():
    for label in ("T1", "T2", "T3"):
        assert summary(label)["performance"]["ratio_last_over_first"] <= 3.0
    t3 = summary("T3")
    assert t3["year_ends"] == ["2026-12-31", "2027-12-31"]
    ids = {r["date"]: r for r in rows("T3", "identities_by_date.csv")}
    assert ids["2027-12-31"]["annual_windows_each"] == "365" and ids["2028-02-29"]["annual_windows_each"] == "60"
    assert ids["2028-02-29"]["monthly_windows_each"] == "29"


def test_negative_period_snapshot_is_sensitive():
    store = {("V", "linha", "L1", "2026-01", "2026-01-05"): ["float", "1.0", None, None],
             ("V", "linha", "L1", "2026-02", "2026-02-01"): ["float", "2.0", None, None]}
    before = harness.prefix_snapshot(store, "2026-01")
    store[("V", "linha", "L1", "2026-01", "2026-01-05")] = ["float", "1.5", None, None]
    assert harness.prefix_snapshot(store, "2026-01") != before
    store2 = dict(store)
    store2[("V", "linha", "L1", "2026-02", "2026-02-01")] = ["float", "9.0", None, None]
    assert harness.prefix_snapshot(store2, "2026-01") == harness.prefix_snapshot(store, "2026-01")
