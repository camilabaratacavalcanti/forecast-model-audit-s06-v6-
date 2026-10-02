"""
Stage 3.4C — regressão integrada dos quatro blocos oficiais (REAL_DERIVED_TEST_RESULT).

Validam o harness em `audit/stage3_4/integrated/`:
    * execução real ponta a ponta (421 alvos, 427 nós, 12 transferências,
      32 datas contíguas 2026-01-01..2026-02-01, reexecução, determinismo,
      cenários de estado) e reprodução exata da evidência versionada;
    * universos derivados do planner / plan_evidence.csv (nunca de lista fixa);
    * testes NEGATIVOS com dados reais: omissão de alvo, omissão de nó,
      corrupção de transferência e corrupção de estado precisam ser detectadas;
    * hash do grafo do fixture estável e sensível.
Nenhum teste altera app/, data/, tools/, seeds ou vínculos.

Stage 4C (classe R): a referência das comparações vivas vem do registro de baseline (`current`);
em B0 é a evidência histórica e os literais 446/421/427/12/60 continuam provados em
`test_stage4c_baseline_registry.py`. O teste do summary versionado (classe E) lê o histórico.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "audit" / "stage3_4" / "integrated"
EVIDENCE = HARNESS / "evidence"
sys.path.insert(0, str(HARNESS))

import checks  # noqa: E402
import fixture  # noqa: E402
import run_integrated as harness  # noqa: E402

from app.domain.results import Result  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    AGGREGATION, EQUATION, TRANSFER, ExecutionPlan,
)

DAYS = [date(2026, 1, 1) + timedelta(days=n) for n in range(32)]

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_registry as reg  # noqa: E402

SET = "stage3_4c_integrated"


def reference_csv(name):
    return list(csv.DictReader(reg.path(SET, name).open(encoding="utf-8")))


def reference_universe():
    return reg.load_json(SET, "integrated_summary.json")["universe"]


def read_csv(name):
    return list(csv.DictReader((EVIDENCE / name).open(encoding="utf-8")))


# ------------------------------------------------------------ execução real completa

@pytest.fixture(scope="module")
def live():
    completed = subprocess.run([sys.executable, str(HARNESS / "run_integrated.py"), "--no-write",
                                *reg.harness_args()], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_integrated_regression_passes(live):
    code, summary, stderr = live
    assert code == 0, (summary["problems"], stderr[-2000:])
    assert summary["result"] == "PASS" and summary["problems"] == []
    ref = reference_universe()                       # B0: 446/25/421/427/{218,197,12}/0 (teste do registro)
    assert summary["universe"] == {
        "official_targets": ref["official_targets"], "area_41_excluded": ref["area_41_excluded"],
        "integrated_targets": ref["integrated_targets"], "planner_nodes": ref["planner_nodes"],
        "nodes_by_kind": ref["nodes_by_kind"], "pending_blockers": 0,
        "required_inputs": summary["universe"]["required_inputs"]}
    assert set(summary["universe"]["nodes_by_kind"]) == {EQUATION, AGGREGATION, TRANSFER}
    assert summary["targets_executed"] == ref["integrated_targets"] and summary["nodes_executed"] == ref["planner_nodes"]
    assert len({ref["official_targets"], ref["integrated_targets"], ref["planner_nodes"]}) == 3   # 446 != 421 != 427
    assert summary["orchestrator_vs_engine"].get("different", 0) == 0
    assert summary["orchestrator_vs_engine"]["compared"] > 0


def test_live_run_reproduces_committed_evidence_and_is_deterministic(live):
    _code, summary, _ = live
    committed = reg.load_json(SET, "integrated_summary.json")
    det = summary["determinism"]
    for label in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B"):
        assert det[label]["results_sha256"] == committed["determinism"][label]["results_sha256"]
        assert det[label]["graph_hash"] == committed["determinism"][label]["graph_hash"]
    assert det["REEXECUTION"] == committed["determinism"]["REEXECUTION"]
    assert {det[k]["hash_seed"] for k in ("HASH_SEED_A", "HASH_SEED_B")} == {"0", "4242"}
    assert det["RUN_B"]["order"] == "B"
    assert det["identical_results"] and det["identical_plan_order"] and det["identical_graph"]
    assert det["identical_store_including_reexecution"]


# ------------------------------------------------------------ evidência versionada

def test_committed_summary_contract():
    s = json.loads((EVIDENCE / "integrated_summary.json").read_text(encoding="utf-8"))
    assert s["label"] == "REAL_DERIVED_TEST_RESULT" and s["result"] == "PASS" and s["problems"] == []
    assert s["fixture"]["pending_in_fixture"] == 0 and s["fixture"]["pending_official"] == 16
    assert len(set(s["fixture"]["graph_hashes"].values())) == 1
    t = s["temporal"]
    assert t["coverage_class"] == "YEAR_TO_DATE_PARTIAL_COVERAGE" and "FULL_YEAR" not in json.dumps(s)
    assert t["dates"] == 32 and t["contiguous"] and t["monthly_jan_all_31_windows"]
    assert t["monthly_feb_windows"] == ["2026-02-01"] and t["annual_ytd_all_32_windows"]
    assert t["daily_keys_have_no_window"]
    for day in ("2026-01-15", "2026-02-01"):
        r = s["reexecution"][day]
        assert r["same_store"] and r["new_keys"] == 0 and r["first_run_events_equal"]
        assert r["first_run_transfer_statuses"] == {"WRITTEN": 60} and r["transfer_statuses"] == {"UNCHANGED": 60}
    assert s["clean_context_stated_results"] == 0
    st = s["state"]
    assert st["SC1_EQ12012_and_chain"]["problems"] == []
    assert len(st["SC1_EQ12012_and_chain"]["stated_transfer_events_verified"]) == 11     # VAR18011: origem é entrada
    g = s["graph"]
    assert g["dependencies_precede_consumers"] and g["production_yield_cycle_at_block_level"]
    assert g["annual_aggregation_rules"] == 48
    assert set(st["SC1_EQ12012_and_chain"]["stated_by_block"]) == set(fixture.OFFICIAL_BLOCKS)
    assert st["SC2_EQ18003"]["active_branch_L1"][2:] == ["VALIDATION_FAILED", "t"]
    assert st["SC2_EQ18003"]["inactive_branch_L2"][2:] == [None, None]
    assert set(st["SC3_policy_b_real_rules"]["per_type"]) == {"AVERAGE", "SUM", "WEIGHTED_AVERAGE", "MOVING_AVERAGE"}
    assert all(st["SC3_policy_b_real_rules"]["per_type"].values())
    sc4 = st["SC4_composition_contracts"]
    assert sc4["different_states"]["error"] == "MULTI_STATE_COMBINATION_UNDEFINED"
    assert sc4["same_state_different_details"]["error"] == "MULTI_DETAIL_COMPOSITION_UNDEFINED"
    assert sc4["detail_without_state"] == "DETAIL_WITHOUT_STATE"


def test_committed_targets_nodes_transfers_and_coverage_are_complete():
    orchestrator = fixture.build("A")
    integrated = orchestrator.targets_of_blocks(fixture.OFFICIAL_BLOCKS)       # derivado, não fixo
    plan = orchestrator.plan(integrated)
    ref = reference_universe()
    targets = reference_csv("targets.csv")
    assert [r["target"] for r in targets] == integrated and len(integrated) == ref["integrated_targets"]
    assert {r["execution_status"] for r in targets} == {"EXECUTED"}
    assert all(r["producer_nodes"] for r in targets)
    nodes = reference_csv("nodes.csv")
    assert [r["node"] for r in nodes] == [s.key for s in plan.steps] and len(nodes) == ref["planner_nodes"]
    assert {r["execution_status"] for r in nodes} == {"EXECUTED"} and {r["dates_executed"] for r in nodes} == {"32"}
    assert all(r["dependent_targets"] and r["result_identity"] for r in nodes)
    assert all(r["planner_nodes"] and int(r["executed_nodes"]) == len(r["planner_nodes"].split("|")) for r in targets)
    assert {r["result_status"] for r in targets} == {"VALUE_WITHOUT_STATE"}
    transfers = reference_csv("transfers.csv")
    assert len(transfers) == ref["nodes_by_kind"][TRANSFER]
    assert all(r["executed_events"] == r["verified_events"] == str(32 * int(r["instances"])) for r in transfers)
    assert {r["execution_status"] for r in transfers} == {"EXECUTED"}
    coverage = reference_csv("temporal_coverage.csv")
    assert [r["date"] for r in coverage] == [d.isoformat() for d in DAYS]
    transfer_events = sum(len(orchestrator.catalog.links.link_for(s.node_id).instances)       # B0: 60
                          for s in plan.steps if s.kind == TRANSFER)
    assert {(r["targets"], r["nodes"], r["transfer_events"], r["errors"]) for r in coverage} == {
        (str(ref["integrated_targets"]), str(ref["planner_nodes"]), str(transfer_events), "0")}


def test_area_41_is_outside_the_integrated_universe():
    orchestrator = fixture.build("A")
    integrated = set(orchestrator.targets_of_blocks(fixture.OFFICIAL_BLOCKS))
    area_41 = set(orchestrator.targets_of_blocks(("area_41",)))
    assert len(area_41) == 25 and not integrated & area_41


# ------------------------------------------------------------ fixture

def test_fixture_graph_hash_is_stable_across_orders_and_sensitive_to_links():
    a, b = fixture.build("A"), fixture.build("B")
    assert fixture.graph_hash(a) == fixture.graph_hash(fixture.build("A")) == fixture.graph_hash(b)
    assert [s.key for s in harness.integrated_plan(a).steps] == [s.key for s in harness.integrated_plan(b).steps]
    official = harness.InterblockExecutionOrchestrator.from_seed_root(fixture.SEED)   # 16 pendências
    assert fixture.graph_hash(official) != fixture.graph_hash(a)


# ------------------------------------------------------------ testes negativos (dados reais)

@pytest.fixture(scope="module")
def short():
    orchestrator = fixture.build("A")
    plan = harness.integrated_plan(orchestrator)
    context, traces = harness.run_sequence(orchestrator, plan, DAYS[:2])
    return orchestrator, plan, context, traces


def expected_of(orchestrator, plan):
    nodes = {s.key: s for s in plan.steps}
    engine = harness.ForecastEngine()
    catalog = orchestrator.catalog
    events = {}
    for key, node in nodes.items():
        if node.kind == EQUATION:
            events[key] = len(engine.materialize_equation(catalog.equation_definitions.get(node.node_id)))
        elif node.kind == AGGREGATION:
            events[key] = sum(1 for i in catalog.aggregation_rule_instances.all()
                              if i.rule.aggregation_rule_id == node.node_id)
        else:
            events[key] = len(catalog.links.link_for(node.node_id).instances)
    instances = {}
    for target in plan.targets:
        definition = catalog.variable_definitions.get(target)
        instances[target] = set(harness.ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value))
    return events, instances


def test_unmutated_short_run_passes_every_check(short):
    orchestrator, plan, context, traces = short
    executed, written, records, _rows, problems = harness.observe(orchestrator, context, traces)
    events, instances = expected_of(orchestrator, plan)
    assert problems == []
    assert checks.check_targets(instances, written) == []
    assert checks.check_nodes([s.key for s in plan.steps], events, executed) == []
    assert checks.check_transfers(records, {s.key for s in plan.steps if s.kind == TRANSFER}) == []


def leaf_target(orchestrator, plan):
    consumed = {v for deps in orchestrator._deps.values() for v in deps}
    return next(t for t in plan.targets if t not in consumed)


def test_negative_target_omission_is_detected(short):
    orchestrator, plan, _context, _traces = short
    _events, instances = expected_of(orchestrator, plan)
    omitted = leaf_target(orchestrator, plan)
    reduced = orchestrator.plan([t for t in plan.targets if t != omitted])     # plano real sem o alvo
    context, traces = harness.run_sequence(orchestrator, reduced, DAYS[:1])
    _executed, written, _records, _rows, _ = harness.observe(orchestrator, context, traces)
    problems = checks.check_targets(instances, written)
    assert problems and all(p.startswith("TARGET_NOT_EXECUTED") for p in problems)
    assert any(omitted in p for p in problems)
    # instância isolada ausente também é omissão
    _e, full_written, _r, _rows, _ = harness.observe(orchestrator, *short[2:])
    target = next(t for t in plan.targets if len(instances[t]) > 1)
    full_written["2026-01-02"] = dict(full_written["2026-01-02"])
    full_written["2026-01-02"][target] = set(list(instances[target])[1:])
    assert any(target in p for p in checks.check_targets(instances, full_written))


def test_negative_node_omission_is_detected(short):
    orchestrator, plan, _context, _traces = short
    events, _instances = expected_of(orchestrator, plan)
    dropped = plan.steps[-1]
    crippled = ExecutionPlan(plan.targets, plan.steps[:-1], plan.required_inputs)   # engine sem o nó
    context, traces = harness.run_sequence(orchestrator, crippled, DAYS[:1])
    executed, *_ = harness.observe(orchestrator, context, traces)
    problems = checks.check_nodes([s.key for s in plan.steps], events, executed)
    assert problems == [f"PLANNER_ONLY_NODE 2026-01-01 {dropped.key}"]
    # nó executado fora do plano, repetido ou com contagem errada
    day = [("EQUATION:EQ_FANTASMA", 1)] + [(s.key, events[s.key]) for s in plan.steps]
    assert any(p.startswith("ENGINE_ONLY_NODE") for p in checks.check_nodes([s.key for s in plan.steps], events,
                                                                            {"d": day}))
    twice = [(s.key, events[s.key]) for s in plan.steps] + [(plan.steps[0].key, 1)]
    assert "NODE_EXECUTED_TWICE d" in checks.check_nodes([s.key for s in plan.steps], events, {"d": twice})
    wrong = [(s.key, events[s.key] + (s is plan.steps[0])) for s in plan.steps]
    assert any(p.startswith("NODE_EVENT_COUNT") for p in checks.check_nodes([s.key for s in plan.steps], events,
                                                                            {"d": wrong}))


def test_negative_transfer_corruption_is_detected():
    orchestrator = fixture.build("A")
    plan = harness.integrated_plan(orchestrator)
    context, traces = harness.run_sequence(orchestrator, plan, DAYS[:1])
    context.set_variable_result("VAR11031", Result(999.0), "linha", "L2", "2026-01-01")   # consumidor adulterado
    _executed, _written, records, _rows, _ = harness.observe(orchestrator, context, traces)
    problems = checks.check_transfers(records, {s.key for s in plan.steps if s.kind == TRANSFER})
    assert len(problems) == 1 and problems[0].startswith("INTERBLOCK_FAILURE 2026-01-01 TRANSFER:VAR11031 linha/L2")
    missing = [r for r in records if r["node"] != "TRANSFER:VAR18011"]
    assert "INTERBLOCK_FAILURE transferência não executada: TRANSFER:VAR18011" in \
        checks.check_transfers(missing, {s.key for s in plan.steps if s.kind == TRANSFER})


def test_negative_state_corruption_is_detected():
    orchestrator = fixture.build("A")
    plan = harness.integrated_plan(orchestrator)

    def inject(d):
        return [("VAR11001", "linha", "L1", d.isoformat(), Result(None, "INVALID_INPUT", "neg"))] if d == DAYS[1] else []
    clean, stated, _ = harness.twin(orchestrator, plan, DAYS[:2], None, inject)
    descendants = harness.descendants_of(orchestrator, {"VAR11001"})
    assert checks.check_state_diff(clean, stated, descendants, "INVALID_INPUT", "neg") == []
    changed = [k for k in clean if clean[k] != stated[k]]
    assert changed                                                               # a injeção propagou
    outsider = next(k for k in clean if k[0] not in descendants)
    leaked = {**stated, outsider: ["NoneType", "None", "INVALID_INPUT", "neg"]}
    assert any("vazamento" in p for p in checks.check_state_diff(clean, leaked, descendants, "INVALID_INPUT", "neg"))
    victim = next(k for k in changed if k[0] != "VAR11001")
    wrong_detail = {**stated, victim: ["NoneType", "None", "INVALID_INPUT", "outro"]}
    assert checks.check_state_diff(clean, wrong_detail, descendants, "INVALID_INPUT", "neg")
    dropped = {k: v for k, v in stated.items() if k != victim}
    assert checks.check_state_diff(clean, dropped, descendants, "INVALID_INPUT", "neg")
    assert checks.check_expectations(clean, [victim], [], "INVALID_INPUT", "neg")      # estado perdido
    assert checks.check_expectations(stated, [], [victim], "INVALID_INPUT", "neg")     # estado indevido
