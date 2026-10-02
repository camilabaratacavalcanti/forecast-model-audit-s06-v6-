"""
Stage 4B.1 — contrato temporal anual, virada de ano e ciclos (REAL_DERIVED_TEST_RESULT).

Provam: o recálculo independente (python -I, sem app/) do calendário, das identidades e dos
ciclos confere com as expectativas congeladas; os experimentos E1–E5 registrados (engine real)
não mostram colisão, carry-over, alteração de período encerrado nem média parcial silenciosa;
o grafo é acíclico no nível de instância; e os detectores (Tarjan, defasagem) não são vacuamente verdes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4b"
sys.path[:0] = [str(STAGE), str(REPO / "audit" / "stage4a")]

import independent_calendar as cal  # noqa: E402

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_registry as reg  # noqa: E402  (Stage 4C: expectativas do registro, classe R)

REF_IND = reg.load_json("stage4b_contract", "contract_expectations_4b.json")["independent"]

AUDIT = json.loads((STAGE / "evidence" / "contract_audit_4b.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def independent():
    completed = subprocess.run([sys.executable, "-I", str(STAGE / "independent_calendar.py"), "--check",
                                *reg.harness_args()], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout)


def test_independent_recount_matches_frozen_expectations(independent):
    code, out = independent
    assert code == 0, out["problems"]
    assert out["imports_app_or_tools"] == []
    assert (out["calendar"]["T1"]["dates"], out["calendar"]["T2"]["dates"], out["calendar"]["T3"]["dates"]) == (396, 62, 792)
    assert out["calendar"]["T2"]["feb_29_dates"] == ["2028-02-29"]
    # B0: 324 / 196 (teste do registro)
    assert out["identity_profile"]["derived_mensal"] == REF_IND["identity_profile"]["derived_mensal"]
    assert out["identity_profile"]["derived_anual"] == REF_IND["identity_profile"]["derived_anual"]


def test_calendar_expectations_are_pure_calendar_arithmetic():
    assert cal.expected_windows(date(2026, 12, 31))["annual"] == 365
    assert cal.expected_windows(date(2027, 1, 1))["annual"] == 1
    assert cal.expected_windows(date(2028, 2, 29))["annual"] == 60
    assert cal.expected_windows(date(2028, 2, 29))["month_length"] == 29
    assert cal.expected_windows(date(2026, 2, 28))["month_end"] is True
    assert len(cal.days(date(2026, 1, 1), date(2028, 3, 2))) == 792


def test_store_growth_predicted_from_seeds_matches_engine():
    growth = dict(map(tuple, AUDIT["performance"]["store_growth_per_date"]))
    assert set(growth) == {1109, 1143}
    assert growth[1143] == 11                                       # dia 1 de fev..dez (11 meses)


def test_e1_turn_of_year_windows_and_snapshot():
    e1 = AUDIT["E1_turn_of_year"]
    assert e1["per_date"]["2026-12-31"]["VAR16020_annual_windows"] == 365
    assert e1["per_date"]["2027-01-01"]["VAR16019_monthly_windows"] == 1
    assert e1["per_date"]["2027-01-01"]["VAR16020_annual_windows"] == 1
    assert e1["annual_2026_windows_per_identity"] == [[365, 196]]
    assert e1["annual_2027_windows_per_identity"] == [[3, 196]]
    assert e1["year_2026_closed_unchanged"] and e1["snapshot_2026_12_unchanged"]
    assert all(v["transfer_events"] == 67 and v["events"] == 896 for v in e1["per_date"].values())


def test_e2_gaps_fail_explicitly():
    e2 = AUDIT["E2_gaps"]
    assert e2["policy"] == "EXPLICIT_FAILURE"
    assert e2["skip_2026_01_06_then_run_01_07"]["type"] == "VariableNotFoundError"
    assert "2026-01-06" in e2["skip_2026_01_06_then_run_01_07"]["message"]


def test_e3_no_carry_over_of_new_period_inputs():
    e3 = AUDIT["E3_missing_new_period_input"]
    for label in ("annual_input_VAR12066_2027", "monthly_input_VAR16001_2027-01_unconditional",
                  "monthly_input_VAR12024_2027-01_if_branch_forced"):
        assert e3[label]["previous_period_value_exists"] is True
        assert e3[label]["error"]["type"] == "VariableNotFoundError"
    assert e3["monthly_input_VAR12024_2027-01_if_branch_inactive"]["error"] is None
    assert e3["VAR12024_not_read_when_branch_inactive"]["differences_excluding_VAR12024"] == 0


def test_e4_closed_periods_and_e5_calendar():
    e4 = AUDIT["E4_closed_periods"]
    for day in ("2026-06-15", "2026-12-31"):
        assert e4[day]["new_keys"] == 0 and e4[day]["changed_keys"] == 0
        assert e4[day]["transfer_statuses"] == {"UNCHANGED": 67}
    assert e4["year_2026_unchanged"] is True
    e5 = AUDIT["E5_calendar"]
    assert all(e5["2026"].values())
    assert (e5["2028"]["feb_windows_VAR16019"], e5["2028"]["mar_windows_VAR16019"],
            e5["2028"]["annual_windows_VAR16020"]) == (29, 2, 62)
    assert e5["2028"]["feb_29_daily_present"] is True


def test_no_identity_collision_between_frequencies_months_years():
    c = AUDIT["collisions"]
    assert c["entities_with_wrong_period_format"] == [] and c["windows_outside_their_period"] == []
    assert c["monthly_and_annual_ids_share_entity"] == []
    m = AUDIT["mechanics"]
    assert m["distinct_ids_on_2026_01_01"] is True
    assert m["window_for"]["2026|2027-01-01"] is None and m["window_for"]["2026-01|2026-02-01"] is None


def test_instance_graph_is_acyclic_and_block_cycle_is_production_yield(independent):
    _code, out = independent
    cycles = out["cycles"]
    assert cycles["instance_cycles"] == [] and cycles["variable_cycles"] == []
    assert cycles["block_cycles"] == [["production", "yield"]]
    assert cycles["lag_references"] == [] and cycles["self_aggregations"] == [] and cycles["explicit_windows"] == []
    assert AUDIT["empirical_acyclicity"]["topological_order_valid"] is True


def test_negative_tarjan_detects_instance_cycles_and_self_loops():
    assert cal.cyclic_components({("A", "L1"): {("B", "L1")}, ("B", "L1"): {("A", "L1")}}) == \
        [[("A", "L1"), ("B", "L1")]]
    assert cal.cyclic_components({("A", "L1"): {("A", "L1")}}) == [[("A", "L1")]]
    assert cal.cyclic_components({("A", "L1"): {("A", "L2")}, ("A", "L2"): set()}) == []


def test_negative_lag_detector_flags_previous_period_syntax():
    for text in ("VAR11001[t-1] + 1", "lag(VAR11001)", "VAR11001[-1]", "prev(VAR11001)"):
        assert cal.LAG.search(text), text
    assert not cal.LAG.search("( VAR16007@L1 + VAR16007@L2 ) / 2")


def test_performance_within_contract_limit():
    p = AUDIT["performance"]
    assert p["ratio_late_over_early"] <= 3.0
    assert p["estimate_seconds"]["T3_792"] <= 7200


def test_contract_document_records_decisions_and_findings():
    text = (STAGE / "STAGE_4B_DECISION_CONTRACT.md").read_text(encoding="utf-8")
    for token in ("DR-4B-1", "DR-4B-2", "DR-4B-3", "DR-4B-4", "DR-4B-5", "DR-4B-6", "DR-4B-7",
                  "F4B-01", "F4B-02", "EXPLICIT_FAILURE", "NENHUM", "ACÍCLICO", "PROPOSED_ACCEPTED_BY_DEFAULT"):
        assert token in text
