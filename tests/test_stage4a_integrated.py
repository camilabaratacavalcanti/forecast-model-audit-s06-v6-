"""
Stage 4A.2 — regressão integrada de 5 blocos incluindo o area_41 (REAL_DERIVED_TEST_RESULT).

Validam o harness `audit/stage4a/integrated/run_integrated_4a.py`:
    * execução real ponta a ponta (446 alvos, 458 nós, 13 transferências, 32 datas,
      reexecução, determinismo, cenários de estado do area_41) e reprodução da evidência 4A;
    * invariante central: o subconjunto sem area_41 é idêntico à 3.4C (0 diferenças);
    * testes NEGATIVOS: corrupção de chave dos 4 blocos, corrupção de estado e o
      protocolo de entradas ingênuo precisam ser detectados.
Nenhum teste altera app/, data/, tools/ nem a evidência da 3.4C.

Stage 4C: os testes vivos (classe R) leem a referência do registro de baseline (`current`); os testes
da evidência versionada (classe E) leem o histórico; a guarda dos caminhos da 3.2/3.4 é H no intervalo
da 4A (`d2847ab..0a924e6`) + E da evidência.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4a"
HARNESS = STAGE / "integrated"
EVIDENCE = HARNESS / "evidence"
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(HARNESS))

import common  # noqa: E402
import run_integrated_4a as harness  # noqa: E402

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_registry as reg  # noqa: E402

# classe E (evidência histórica versionada)
EXPECTED = json.loads((STAGE / "contract_expectations.json").read_text(encoding="utf-8"))["integrated"]
STAGE34 = json.loads((common.STAGE34_EVIDENCE / "integrated_summary.json").read_text(encoding="utf-8"))
# classe R (referência do registro; em B0 = os mesmos arquivos)
REF = reg.load_json("stage4a_contract", "contract_expectations.json")["integrated"]
REF34 = reg.load_json("stage3_4c_integrated", "integrated_summary.json")
BASELINE_4A, CLOSURE_4A = "d2847ab36933668bf4a1299b3ffe058827a82037", "0a924e66cfd0774a13e46a332b460b770283a554"


def read_csv(name):
    return list(csv.DictReader((EVIDENCE / name).open(encoding="utf-8")))


@pytest.fixture(scope="module")
def live():
    completed = subprocess.run([sys.executable, str(HARNESS / "run_integrated_4a.py"), "--no-write",
                                *reg.harness_args()], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_five_block_regression_passes_and_reproduces_committed_evidence(live):
    code, summary, stderr = live
    assert code == 0, (summary["problems"], stderr[-2000:])
    assert summary["result"] == "PASS" and summary["problems"] == []
    universe = summary["universe"]
    # B0: 446 / 458 / {238, 207, 13} / 13 transferências / (421, 427) — provado no teste do registro
    assert universe["integrated_targets"] == REF["integrated_targets"] == universe["official_targets"]
    assert universe["planner_nodes"] == REF["planner_nodes"] and universe["nodes_by_kind"] == REF["nodes_by_kind"]
    assert "TRANSFER:VAR16007" in universe["transfers"] and len(universe["transfers"]) == len(REF["transfers"])
    assert (universe["previous_targets"], universe["previous_nodes"]) == (REF["previous_targets"], REF["previous_nodes"])
    assert summary["targets_executed"] == REF["integrated_targets"] and summary["nodes_executed"] == REF["planner_nodes"]
    assert summary["orchestrator_vs_engine"].get("different", 0) == 0
    assert summary["orchestrator_vs_engine"]["compared_area_41"] > 0


def test_non_regression_of_the_421_previous_targets(live):
    _code, summary, _ = live
    report = summary["non_regression_421"]
    assert report["result"] == "PASS" and report["differences"] == 0 and report["targets_different"] == 0
    assert report["targets_compared"] == REF["previous_targets"] and report["keys_compared"] > 30000
    assert report["subset_store_sha256"] == report["reference_store_sha256"] == \
        REF34["determinism"]["RUN_A"]["store_sha256"]


def test_committed_non_regression_report():
    report = json.loads((EVIDENCE / "non_regression_421.json").read_text(encoding="utf-8"))
    assert report["label"] == "REAL_DERIVED_TEST_RESULT"
    assert report["result"] == "PASS"
    assert (report["differences"], report["keys_only_in_4_blocks"], report["keys_new_outside_area_41"]) == (0, 0, 0)
    assert report["isolated_4_block_store_sha256"] == report["reference_store_sha256"]
    assert report["dates"] == 32 and report["window_dates_covered"] == 32
    assert set(report["keys_by_period_kind"]) == {"daily", "monthly", "annual"}


def test_committed_summary_temporal_reexecution_determinism_state():
    summary = json.loads((EVIDENCE / "integrated_summary.json").read_text(encoding="utf-8"))
    assert summary["result"] == "PASS" and summary["label"] == "REAL_DERIVED_TEST_RESULT"
    temporal = summary["temporal"]
    assert temporal["monthly_jan_all_31_windows"] and temporal["annual_ytd_all_32_windows"]
    assert temporal["area_41_monthly_jan_identities"] == 11 == temporal["area_41_annual_identities"]
    stage34 = STAGE34["temporal"]
    assert temporal["monthly_jan_identities"] == stage34["monthly_jan_identities"] + 11
    assert temporal["annual_ytd_identities"] == stage34["annual_ytd_identities"] + 11
    for day, run in summary["reexecution"].items():
        assert run["same_store"] and run["new_keys"] == 0 and run["stated_results"] == 0
        assert run["first_run_transfer_statuses"] == {"WRITTEN": 67} and run["transfer_statuses"] == {"UNCHANGED": 67}
    det = summary["determinism"]
    assert det["identical_results"] and det["identical_store_including_reexecution"]
    assert det["identical_plan_order"] and det["identical_graph"]
    assert {det[k]["hash_seed"] for k in ("HASH_SEED_A", "HASH_SEED_B")} == {"0", "4242"}
    assert det["RUN_B"]["order"] == "B"
    assert len({det[k]["area_41_store_sha256"] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")}) == 1
    assert summary["fixture"]["graph_hashes"]["stage_3_4c"] == summary["fixture"]["graph_hashes"]["A"]
    state = summary["state"]
    for name in ("SA1_transfer_VAR16007_from_yield", "SA2_hes_condition_state", "SA3a_boundary_41c_branch_not_executed",
                 "SA3b_boundary_41c_branch_executed", "SA4_boundary_vazao_ltp_L1_L3", "SA5_F_literal_no_applicable_rule"):
        assert state[name]["problems"] == []
    assert state["SA3a_boundary_41c_branch_not_executed"]["stated_area_41_variables"] == ["VAR16022"]  # IF causal
    assert "VAR16007" in state["SA1_transfer_VAR16007_from_yield"]["stated_area_41_variables"]
    assert state["SA5_F_literal_no_applicable_rule"]["state"] == "NO_APPLICABLE_RULE"
    assert state["SA5_F_literal_no_applicable_rule"]["detail"] is None
    for case in state["SA6_undefined_compositions"].values():
        assert case["error"] == case["expected"]


def test_committed_csv_evidence_is_complete():
    targets, nodes = read_csv("targets.csv"), read_csv("nodes.csv")
    assert len(targets) == 446 and all(r["execution_status"] == "EXECUTED" for r in targets)
    assert sum(1 for r in targets if r["block"] == "area_41") == 25
    assert len(nodes) == 458 and all(r["execution_status"] == "EXECUTED" and r["dates_executed"] == "32" for r in nodes)
    assert sum(1 for r in nodes if r["in_stage_3_4c_plan"] == "True") == 427
    transfers = {r["node"]: r for r in read_csv("transfers.csv")}
    assert len(transfers) == 13 and all(r["executed_events"] == r["verified_events"] for r in transfers.values())
    assert transfers["TRANSFER:VAR16007"]["source_variable"] == "VAR11031"
    assert transfers["TRANSFER:VAR16007"]["executed_events"] == str(32 * 7)
    coverage = read_csv("temporal_coverage.csv")
    assert len(coverage) == 32 and all(r["events"] == str(EXPECTED["events_per_date"]) for r in coverage)


def test_stage_3_4c_evidence_is_untouched():
    """Harnesses e evidência das 3.2/3.4 idênticos ao baseline durante a 4A (H: d2847ab..0a924e6) e a
    evidência (arquivos que não são código) idêntica ao fechamento da 4A também no HEAD (E)."""
    paths = ["audit/stage3_4/integrated", "audit/stage3_4/differential", "audit/stage3_4/mutation",
             "audit/stage3_4/closure", "audit/stage3_4/taxonomy_migration", "audit/stage3_2_execution_orchestration"]
    out = subprocess.run(["git", "diff", "--name-only", BASELINE_4A, CLOSURE_4A, "--", *paths],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout
    evidence = [p for p in subprocess.run(["git", "ls-tree", "-r", "--name-only", CLOSURE_4A, "--", *paths], cwd=REPO,
                                          capture_output=True, text=True, check=True).stdout.split()
                if not p.endswith(".py")]
    changed_evidence = subprocess.run(["git", "diff", "--name-only", CLOSURE_4A, "--", *evidence],
                                      cwd=REPO, capture_output=True, text=True, check=True).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--", *paths],
                               cwd=REPO, capture_output=True, text=True, check=True).stdout
    assert out == "" and untracked == ""
    assert len(evidence) > 20 and changed_evidence == ""


# ------------------------------------------------------------------ negativos

@pytest.fixture(scope="module")
def run5():
    universe = common.Universe("A")
    context, _ = universe.run_sequence()
    return universe, context


def test_negative_corrupted_previous_key_is_detected(run5):
    universe, context = run5
    store = common.ri.store_of(context)
    victim = min(k for k, v in store.items() if k[0] not in universe.area_41_entities and v[0] == "float")
    store[victim] = ["float", repr(float(store[victim][1]) + 1.0), None, None]
    _report, problems = harness.non_regression(universe, store, context)
    assert any("hash do subconjunto" in p for p in problems)
    assert any("valor/state/detail diferente" in p for p in problems)


def test_negative_area_41_change_does_not_touch_the_421_check(run5):
    universe, context = run5
    store = common.ri.store_of(context)
    victim = min(k for k in store if k[0] in universe.area_41_entities)
    store[victim] = ["float", "0.0", None, None]
    _report, problems = harness.non_regression(universe, store, context)
    assert problems == []                      # o invariante é sobre os 4 blocos; o area_41 é coberto pelo oracle/evidência 4A


def test_negative_naive_input_protocol_would_change_previous_targets():
    universe = common.Universe("A")
    context, _ = common.ri.run_sequence(universe.orchestrator, universe.plan, days=common.DAYS[:2])
    naive = common.subset_sha(common.ri.store_of(context), universe.area_41_entities)
    proper, _ = universe.run_sequence(days=common.DAYS[:2])
    reference, _ = common.ri.run_sequence(universe.orchestrator, universe.plan4, days=common.DAYS[:2])
    assert common.subset_sha(common.ri.store_of(proper), universe.area_41_entities) == common.ri.store_sha(reference)
    assert naive != common.ri.store_sha(reference)                 # por isso DR-4A-5


def test_negative_state_corruption_is_detected():
    universe = common.Universe("A")
    scenario = next(s for s in harness.scenarios(universe) if s["name"] == "SA5_F_literal_no_applicable_rule")
    assert scenario["audit"](scenario["stated"]) == []
    corrupted = dict(scenario["stated"])
    must = scenario["must"][0]
    corrupted[must] = ["float", "1.0", None, None]
    assert any("STATE_DIFFERENCE" in p for p in scenario["audit"](corrupted))
    leak = dict(scenario["stated"])
    plain = next(k for k in scenario["plain"] if k[0] == "VAR16018")
    leak[plain] = ["NoneType", "None", "NO_APPLICABLE_RULE", None]
    assert any("vazamento" in p or "esperado sem estado" in p for p in scenario["audit"](leak))


def test_negative_composition_without_contract_is_an_error_not_a_value():
    universe = common.Universe("A")
    cases = harness.composition_errors(universe)
    assert {c["error"] for c in cases.values()} == {"MULTI_STATE_COMBINATION_UNDEFINED",
                                                    "MULTI_DETAIL_COMPOSITION_UNDEFINED"}
