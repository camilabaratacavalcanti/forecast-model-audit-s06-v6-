"""
Stage 4A.2 — regressão integrada de 5 blocos incluindo o area_41 (REAL_DERIVED_TEST_RESULT).

    python audit/stage4a/integrated/run_integrated_4a.py [--no-write]
    python audit/stage4a/integrated/run_integrated_4a.py --fingerprint A|B   (uso interno: determinismo)

Universo (contrato 4A §1, `contract_expectations.json → integrated`):
    446 alvos (421 da 3.4C + 25 do area_41), 458 nós (238 EQUATION + 207 AGGREGATION + 13 TRANSFER),
    62 entradas livres, 896 eventos por data, 32 datas contíguas 2026-01-01..2026-02-01 no MESMO contexto.

Reutiliza por IMPORT o fixture, os auditores (`checks.py`, com os reforços G1–G5 da 3.4D) e as
utilidades da 3.4C, sem modificá-los. Protocolo de entradas: DR-4A-5 (`audit/stage4a/common.py`).

Invariante central (§2 do contrato): o subconjunto do store sem o area_41 é idêntico ao da 3.4C
(hash versionado + execução dos 4 blocos isolados, chave a chave, + `targets.csv` alvo a alvo).

Evidência nova (DR-4A-2, protocolo L8) em `audit/stage4a/integrated/evidence/`; a evidência da
3.4C é só lida e comparada. Com `--no-write`, a execução também é comparada com a evidência 4A
versionada (regressão do próprio area_41).
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE))

import common  # noqa: E402

from app.domain.equations.registry import EquationDefinitionRegistry  # noqa: E402
from app.domain.results import Result  # noqa: E402
from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.interblock_orchestrator import AGGREGATION, EQUATION, TRANSFER  # noqa: E402

import checks  # noqa: E402  (3.4C/3.4D, sem alteração)

ri, fixture = common.ri, common.fixture
REPO = common.REPO
DAYS = common.DAYS
EVIDENCE = HERE / "evidence"
EXPECTED = json.loads((STAGE / "contract_expectations.json").read_text(encoding="utf-8"))["integrated"]
REEXECUTE = (date(2026, 1, 15), date(2026, 2, 1))
INV, NAR = "INVALID_INPUT", "NO_APPLICABLE_RULE"
FEB1 = date(2026, 2, 1)
JAN = [d for d in DAYS if d.month == 1]
key = ri.key


# ------------------------------------------------------------------ determinismo (subprocesso)
def fingerprint(order: str) -> dict:
    universe = common.Universe(order)
    context, traces = universe.run_sequence()
    store = ri.store_of(context)
    events = sorted(sorted(map(tuple, ri.events_of(t)), key=lambda e: e[1:]) for t in traces.values())
    results = {"store": sorted([list(k), v] for k, v in store.items()),
               "events_without_step": [[e[1:] for e in day] for day in events]}
    return {"order": order, "graph_hash": fixture.graph_hash(universe.orchestrator),
            "plan_order": [s.key for s in universe.plan.steps], "results_sha256": ri.sha(results),
            "store_sha256": ri.store_sha(context),
            "area_41_store_sha256": common.only_sha(store, universe.area_41_entities),
            "previous_store_sha256": common.subset_sha(store, universe.area_41_entities),
            "hash_seed": os.environ.get("PYTHONHASHSEED")}


# ------------------------------------------------------------------ não-regressão (§2 do contrato)
def non_regression(universe, store5: dict, context5) -> tuple[dict, list[str]]:
    """Subconjunto sem area_41 == 3.4C: hash versionado, 4 blocos isolados chave a chave, targets.csv."""
    problems = []
    committed = json.loads((common.STAGE34_EVIDENCE / "integrated_summary.json").read_text(encoding="utf-8"))
    reference_sha = committed["determinism"]["RUN_A"]["store_sha256"]
    subset_sha = common.subset_sha(store5, universe.area_41_entities)
    if subset_sha != reference_sha:
        problems.append(f"NON_REGRESSION_FAILURE hash do subconjunto {subset_sha} != 3.4C {reference_sha}")

    # execução dos 4 blocos isolados (fixture e entradas da 3.4C, sem alteração)
    orchestrator = universe.orchestrator
    context4, _ = ri.run_sequence(orchestrator, universe.plan4)
    store4 = ri.store_of(context4)
    previous = {k: v for k, v in store5.items() if k[0] not in universe.area_41_entities}
    only4, only5 = set(store4) - set(previous), set(previous) - set(store4)
    changed = sorted((k for k in set(store4) & set(previous) if store4[k] != previous[k]), key=repr)
    for label, keys in (("chave só na execução de 4 blocos", only4), ("chave nova fora do area_41", only5),
                        ("valor/state/detail diferente", changed)):
        if keys:
            problems.append(f"NON_REGRESSION_FAILURE {label}: {sorted(keys, key=repr)[:3]}")
    if ri.store_sha(context4) != reference_sha:
        problems.append("NON_REGRESSION_FAILURE execução isolada de 4 blocos != 3.4C versionada")

    # targets.csv da 3.4C: resultado final de 2026-02-01, alvo a alvo
    rows = list(csv.DictReader((common.STAGE34_EVIDENCE / "targets.csv").open(encoding="utf-8")))
    definitions = orchestrator.catalog.variable_definitions
    target_diffs = []
    for row in rows:
        definition = definitions.get(row["target"])
        period = common.PERIODS.effective_window(definition.frequency, FEB1).period_id
        instances = common.ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value)
        final = {f"{st}/{sv}": ri.encode(context5.get_variable_result(row["target"], st, sv, period, as_of=FEB1))
                 for st, sv in sorted(instances)}
        if ri.canonical(final) != row["final_results_2026-02-01"]:
            target_diffs.append(row["target"])
    if target_diffs:
        problems.append(f"NON_REGRESSION_FAILURE alvos da 3.4C com resultado final diferente {target_diffs[:3]}")
    by_kind = Counter({10: "daily", 7: "monthly", 4: "annual"}.get(len(k[3] or ""), "other") for k in previous)
    windows = sorted({k[4] for k in previous if k[4]})
    report = {
        "label": common.LABEL,
        "invariant": "incluir o area_41 não muda value, state, detail nem identidade temporal de nenhuma chave dos 4 blocos",
        "reference": "audit/stage3_4/integrated/evidence/integrated_summary.json determinism.RUN_A.store_sha256",
        "reference_store_sha256": reference_sha,
        "subset_store_sha256": subset_sha,
        "hash_method": "sha256(json.dumps(sorted([list(k), [tipo, repr(valor), state, detail]]), sort_keys=True)) "
                       "sobre as chaves (entity_id, scope_type, scope_value, period_id, window_end) cuja entidade "
                       "não pertence ao area_41 — mesma função run_integrated.store_sha da 3.4C",
        "isolated_4_block_store_sha256": ri.store_sha(context4),
        "keys_compared": len(set(store4) & set(previous)), "keys_only_in_4_blocks": len(only4),
        "keys_new_outside_area_41": len(only5), "differences": len(changed),
        "keys_by_period_kind": dict(sorted(by_kind.items())),
        "window_dates_covered": len(windows), "dates": len(DAYS),
        "targets_compared": len(rows), "targets_different": len(target_diffs),
        "area_41_keys": len(store5) - len(previous),
        "result": "PASS" if not problems else "FAIL",
    }
    return report, problems


# ------------------------------------------------------------------ cenários de estado do area_41
def hes_values(values, days):
    """Sobrescreve hes (L4, L5, L6, L7) nas datas dadas (valor, sem estado)."""
    return lambda d: ([("VAR16021", "linha", line, d.isoformat(), Result(h))
                       for line, h in zip(("L4", "L5", "L6", "L7"), values) if h is not None] if d in days else [])


def combine(*funcs):
    return lambda d: [x for f in funcs if f for x in f(d)]


def twin(universe, days, overrides, injections, drop=()):
    clean, _ = universe.run_sequence(days, overrides)
    stated, traces = universe.run_sequence(days, overrides, injections)
    a, b = ri.store_of(clean), ri.store_of(stated)
    if drop:                                                    # a própria origem (valor sobrescrito) sai do diff
        a = {k: v for k, v in a.items() if k[0] not in drop}
        b = {k: v for k, v in b.items() if k[0] not in drop}
    return a, b, stated, traces


def group_keys(variables, days, freq="diário"):
    return [key(v, st, sv, d, freq) for (v, st, sv) in variables for d in days]


A41_GROUPS = {
    "L1_L3": [("VAR16008", "linha_grupo", "L1_L3"), ("VAR16014", "linha_grupo", "L1_L3"),
              ("VAR16018", "linha_grupo", "L1_L3")] + [("VAR16031", "linha", f"L{i}") for i in (1, 2, 3)],
    "L4_L5": [("VAR16009", "linha_grupo", "L4_L5"), ("VAR16015", "linha_grupo", "L4_L5"),
              ("VAR16025", "linha_grupo", "L4_L5")] + [("VAR16031", "linha", f"L{i}") for i in (4, 5)],
    "L6_L7": [("VAR16010", "linha_grupo", "L6_L7"), ("VAR16016", "linha_grupo", "L6_L7"),
              ("VAR16028", "linha_grupo", "L6_L7")] + [("VAR16031", "linha", f"L{i}") for i in (6, 7)],
}
TOTAL = [("VAR16034", "linha_grupo", "L1_L7")]


def scenario(universe, name, days, overrides, injections, origins, state, detail, must, plain, drop=()):
    """Execuções gêmeas + auditor por diferença (checks.check_state_diff) + casos nomeados."""
    clean, stated, context, traces = twin(universe, days, overrides, injections, drop)
    descendants = ri.descendants_of(universe.orchestrator, set(origins))

    def audit(store):
        p = checks.check_state_diff(clean, store, descendants, state, detail)
        p += checks.check_expectations(store, must, plain, state, detail) + checks.check_result_contract(store)
        return p

    return {"name": name, "clean": clean, "stated": stated, "context": context, "traces": traces,
            "audit": audit, "descendants": descendants, "must": must, "plain": plain, "state": state,
            "detail": detail}


def scenarios(universe) -> list[dict]:
    d4 = DAYS[:4]
    jan2, jan3 = DAYS[1], DAYS[2]
    out = []
    # SA1 — origem na cadeia production -> yield -> transferência VAR16007 (L3), janeiro inteiro.
    sc1_over = lambda d: [("VAR12066", "linha", "L3", "2026", Result(0.0001)),  # noqa: E731
                          ("VAR12066", "linha", "L4", "2026", Result(1.0e6))]
    sc1_inj = lambda d: ([("VAR12024", "linha", sv, "2026-01", Result(None, INV, "fa"))  # noqa: E731
                          for sv in ("L3", "L4")] if d.month == 1 else [])
    must = (group_keys([("VAR16007", "linha", "L3")] + A41_GROUPS["L1_L3"] + TOTAL, JAN)
            + [key("VAR16019", "linha_grupo", "L1_L3", d, "mensal") for d in JAN]
            + [key("VAR16020", "linha_grupo", "L1_L3", d, "anual") for d in DAYS])
    plain = (group_keys(A41_GROUPS["L4_L5"] + A41_GROUPS["L6_L7"] + [("VAR16007", "linha", "L4")], JAN)
             + group_keys(A41_GROUPS["L1_L3"] + TOTAL, [FEB1])
             + [key("VAR16019", "linha_grupo", "L1_L3", FEB1, "mensal")])
    out.append(scenario(universe, "SA1_transfer_VAR16007_from_yield", DAYS, sc1_over, sc1_inj, {"VAR12024"},
                        INV, "fa", must, plain))
    # SA2 — estado em hes@L4 (condição das IFs) em 2026-01-02.
    inj = lambda d: [("VAR16021", "linha", "L4", d.isoformat(), Result(None, INV, "hes"))] if d == jan2 else []  # noqa: E731
    must = (group_keys([("VAR16025", "linha_grupo", "L4_L5"), ("VAR16031", "linha", "L4"),
                        ("VAR16031", "linha", "L5")] + TOTAL, [jan2])
            + [key("VAR16026", "linha_grupo", "L4_L5", d, "mensal") for d in d4[1:]]
            + [key("VAR16032", "linha", sv, d, "mensal") for sv in ("L4", "L5") for d in d4[1:]])
    plain = (group_keys(A41_GROUPS["L1_L3"] + A41_GROUPS["L6_L7"], d4)
             + group_keys([("VAR16025", "linha_grupo", "L4_L5")] + TOTAL, [DAYS[0], jan3])
             + [key("VAR16032", "linha", sv, d, "mensal") for sv in ("L1", "L6", "L7") for d in d4])
    out.append(scenario(universe, "SA2_hes_condition_state", d4, None, inj, {"VAR16021"}, INV, "hes", must, plain))
    # SA3a — desconto_retirada_41c (fronteira) com estado, hes Normal: ramo não executado => nada propaga.
    inj41c = lambda d: [("VAR16022", "linha_grupo", "L4_L5", d.isoformat(), Result(None, INV, "41c"))] if d == jan2 else []  # noqa: E731
    out.append(scenario(universe, "SA3a_boundary_41c_branch_not_executed", d4, None, inj41c, {"VAR16022"},
                        INV, "41c", [], group_keys([("VAR16025", "linha_grupo", "L4_L5")] + TOTAL, d4)))
    # SA3b — mesmo estado, hes (1 By pass e LC, 1 By pass e LC): ramo executado => propaga.
    out.append(scenario(universe, "SA3b_boundary_41c_branch_executed", d4,
                        hes_values(("1 By pass e LC", "1 By pass e LC", None, None), d4), inj41c, {"VAR16022"},
                        INV, "41c", group_keys([("VAR16025", "linha_grupo", "L4_L5")] + TOTAL, [jan2]),
                        group_keys([("VAR16025", "linha_grupo", "L4_L5")] + TOTAL, [DAYS[0], jan3])
                        + group_keys(A41_GROUPS["L6_L7"], d4)))
    # SA4 — vazao_ltp L1_L3 (fronteira mensal) com estado em janeiro: isolamento entre grupos.
    inj_ltp = lambda d: [("VAR16001", "linha_grupo", "L1_L3", "2026-01", Result(None, INV, "ltp"))] if d.month == 1 else []  # noqa: E731
    out.append(scenario(universe, "SA4_boundary_vazao_ltp_L1_L3", d4, None, inj_ltp, {"VAR16001"}, INV, "ltp",
                        group_keys([("VAR16004", "linha_grupo", "L1_L3"), ("VAR16018", "linha_grupo", "L1_L3")]
                                   + [("VAR16031", "linha", f"L{i}") for i in (1, 2, 3)] + TOTAL, d4),
                        group_keys(A41_GROUPS["L4_L5"] + A41_GROUPS["L6_L7"]
                                   + [("VAR16005", "linha_grupo", "L4_L5"), ("VAR16006", "linha_grupo", "L6_L7")]
                                   + [("VAR16014", "linha_grupo", "L1_L3")], d4)))
    # SA5 — "F" -> NO_APPLICABLE_RULE: (Normal, 1BPLC) L4/L5 em 01-02 e 01-03; (1BPLC, Normal) L6/L7 em 01-03.
    f_over = combine(hes_values(("Normal", "1 By pass e LC", None, None), [jan2, jan3]),
                     hes_values((None, None, "1 By pass e LC", "Normal"), [jan3]))
    must = (group_keys([("VAR16025", "linha_grupo", "L4_L5"), ("VAR16031", "linha", "L4"),
                        ("VAR16031", "linha", "L5")] + TOTAL, [jan2, jan3])
            + group_keys([("VAR16028", "linha_grupo", "L6_L7"), ("VAR16031", "linha", "L6"),
                          ("VAR16031", "linha", "L7")], [jan3])
            + [key("VAR16026", "linha_grupo", "L4_L5", d, "mensal") for d in d4[1:]]
            + [key("VAR16027", "linha_grupo", "L4_L5", d, "anual") for d in d4[1:]]
            + [key("VAR16029", "linha_grupo", "L6_L7", d, "mensal") for d in d4[2:]]
            + [key("VAR16035", "linha_grupo", "L1_L7", d, "mensal") for d in d4[1:]]
            + [key("VAR16036", "linha_grupo", "L1_L7", d, "anual") for d in d4[1:]]
            + [key("VAR16032", "linha", sv, d, "mensal") for sv in ("L4", "L5") for d in d4[1:]])
    plain = (group_keys(A41_GROUPS["L1_L3"], d4)
             + group_keys([("VAR16025", "linha_grupo", "L4_L5")] + TOTAL, [DAYS[0], DAYS[3]])
             + group_keys([("VAR16028", "linha_grupo", "L6_L7")], [DAYS[0], jan2, DAYS[3]])
             + [key("VAR16029", "linha_grupo", "L6_L7", d, "mensal") for d in d4[:2]]
             + [key("VAR16019", "linha_grupo", "L1_L3", d, "mensal") for d in d4]
             + [key("VAR16032", "linha", sv, d, "mensal") for sv in ("L1", "L2", "L3") for d in d4])
    out.append(scenario(universe, "SA5_F_literal_no_applicable_rule", d4, None, f_over, {"VAR16021"}, NAR, None,
                        must, plain, drop={"VAR16021"}))
    return out


def composition_errors(universe) -> dict:
    """SA6 — composições sem contrato no area_41 (equação e agregação), contextos próprios."""
    d4 = DAYS[:4]
    jan2, jan3 = DAYS[1], DAYS[2]
    cases = {
        "equation_total_two_states": (
            combine(hes_values(("Normal", "1 By pass e LC", "1 By pass e LC", "1 By pass e LC"), [jan2])),
            lambda d: [("VAR16023", "linha_grupo", "L6_L7", d.isoformat(), Result(None, INV, "41c"))] if d == jan2 else [],
            "MULTI_STATE_COMBINATION_UNDEFINED"),
        "aggregation_window_two_states": (
            combine(hes_values(("Normal", "1 By pass e LC", None, None), [jan2]),
                    hes_values(("1 By pass e LC", "1 By pass e LC", None, None), [jan3])),
            lambda d: [("VAR16022", "linha_grupo", "L4_L5", d.isoformat(), Result(None, INV, "41c"))] if d == jan3 else [],
            "MULTI_STATE_COMBINATION_UNDEFINED"),
        "aggregation_window_same_state_two_details": (
            hes_values(("1 By pass e LC", "1 By pass e LC", None, None), d4),
            lambda d: ([("VAR16022", "linha_grupo", "L4_L5", d.isoformat(),
                         Result(None, INV, "a" if d == jan2 else "b"))] if d in (jan2, jan3) else []),
            "MULTI_DETAIL_COMPOSITION_UNDEFINED"),
    }
    out = {}
    for name, (overrides, injections, expected) in cases.items():
        code = None
        try:
            universe.run_sequence(d4, overrides, injections)
        except Exception as exc:  # noqa: BLE001 — o código do erro é a evidência
            code = getattr(exc, "code", type(exc).__name__)
        out[name] = {"error": code, "expected": expected}
    return out


def state_coverage(universe, problems: list) -> dict:
    report = {}
    for sc in scenarios(universe):
        p = sc["audit"](sc["stated"])
        problems += p
        stated = {k: v for k, v in sc["stated"].items() if v[2] is not None}
        report[sc["name"]] = {
            "problems": p, "state": sc["state"], "detail": sc["detail"],
            "must_keys": len(sc["must"]), "plain_keys": len(sc["plain"]),
            "differing_keys": sum(1 for k in sc["clean"] if sc["clean"][k] != sc["stated"].get(k)),
            "stated_area_41_variables": sorted({k[0] for k in stated if k[0] in universe.area_41_entities}),
            "stated_by_block": dict(Counter(universe.orchestrator.catalog.block_of.get(k[0]) for k in stated)),
            "descendant_variables": len(sc["descendants"]),
        }
    sa6 = composition_errors(universe)
    for name, case in sa6.items():
        if case["error"] != case["expected"]:
            problems.append(f"AGGREGATION_FAILURE {name}: {case['error']} != {case['expected']}")
    report["SA6_undefined_compositions"] = sa6
    return report


# ------------------------------------------------------------------ execução principal
def main() -> int:  # noqa: C901 — sequência linear de verificações, espelhando a 3.4C
    problems: list[str] = []
    evidence: dict = {"label": common.LABEL}
    universe = common.Universe("A")
    orchestrator, plan = universe.orchestrator, universe.plan
    catalog = orchestrator.catalog

    # 1. fixture --------------------------------------------------------------------
    hashes = {"A": fixture.graph_hash(orchestrator), "A_rebuilt": fixture.graph_hash(fixture.build("A")),
              "B": fixture.graph_hash(fixture.build("B"))}
    committed34 = json.loads((common.STAGE34_EVIDENCE / "integrated_summary.json").read_text(encoding="utf-8"))
    hashes["stage_3_4c"] = committed34["fixture"]["graph_hashes"]["A"]
    if len(set(hashes.values())) != 1:
        problems.append(f"FIXTURE_FAILURE hashes de grafo diferentes {hashes}")
    evidence["fixture"] = {"graph_hashes": hashes, "pending_in_fixture": len(catalog.links.pending()),
                           "input_protocol": "DR-4A-5: índices da 3.4C preservados; area_41 em 51..61"}

    # 2. universo (expectativas do contrato 4A) -------------------------------------
    plan_rows = list(csv.DictReader(
        (REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv").open(encoding="utf-8")))
    targets = orchestrator.targets_of_blocks(common.BLOCKS5)
    if sorted(r["target"] for r in plan_rows) != targets:
        problems.append("PLANNER_FAILURE plan_evidence.csv != targets_of_blocks (5 blocos)")
    planned = [s.key for s in plan.steps]
    universe_obs = {
        "official_targets": len(plan_rows), "integrated_targets": len(plan.targets),
        "area_41_targets": sum(1 for t in plan.targets if t in universe.area_41_entities),
        "planner_nodes": len(planned), "nodes_by_kind": dict(sorted(Counter(s.kind for s in plan.steps).items())),
        "transfers": sorted(k for k in planned if k.startswith(TRANSFER)),
        "required_inputs": len(plan.required_inputs), "pending_blockers": len(plan.pending_blockers),
        "previous_targets": len(universe.plan4.targets), "previous_nodes": len(universe.plan4.steps),
        "dates": len(DAYS),
    }
    for field, value in universe_obs.items():
        if EXPECTED.get(field) != value:
            problems.append(f"PLANNER_FAILURE {field} {value} != contrato {EXPECTED.get(field)}")
    if not set(s.key for s in universe.plan4.steps) <= set(planned):
        problems.append("PLANNER_FAILURE plano de 4 blocos não está contido no de 5")
    evidence["universe"] = universe_obs

    # 3. grafo: produtor, fecho, ordem ------------------------------------------------
    nodes = {s.key: s for s in plan.steps}
    producers = {t: sorted(k for k in orchestrator._producers.get(t, ()) if k in nodes) for t in plan.targets}
    closure = {t: [s.key for s in orchestrator.plan([t]).steps] for t in plan.targets}
    dependents = defaultdict(set)
    for target, keys in closure.items():
        for k in keys:
            dependents[k].add(target)
    for target in plan.targets:
        if not producers[target] or not set(producers[target]) <= set(closure[target]):
            problems.append(f"PLANNER_FAILURE produtor ausente/fora do fecho {target}")
    if set(planned) - set(dependents):
        problems.append("PLANNER_FAILURE nós sem alvo")
    position = {k: i for i, k in enumerate(planned)}
    upstream = {k: sorted({p for v in orchestrator._deps[k] for p in orchestrator._producers.get(v, ()) if p in nodes})
                for k in planned}
    late = [(k, p) for k in planned for p in upstream[k] if position[p] >= position[k]]
    problems += [f"PLANNER_FAILURE dependência após o consumidor {k} <- {p}" for k, p in late]
    evidence["graph"] = {"dependencies_precede_consumers": not late,
                         "cross_block_edges": sorted({(nodes[p].block, nodes[k].block) for k in planned
                                                      for p in upstream[k] if nodes[p].block != nodes[k].block}),
                         "area_41_closure_nodes": len(orchestrator.plan(
                             orchestrator.targets_of_blocks(("area_41",))).steps)}
    expected_events, expected_instances = ri.node_expectations(orchestrator, plan)
    if sum(expected_events.values()) != EXPECTED["events_per_date"]:
        problems.append("PLANNER_FAILURE eventos por data != contrato")

    # 4. sequência limpa (RUN_A, 32 datas, mesmo contexto) ------------------------------
    context = universe.fresh_context()
    traces, january_snapshot = {}, None
    for day in DAYS:
        if day == FEB1:
            january_snapshot = {k: v for k, v in ri.store_of(context).items() if k[3] == "2026-01"}
        traces[day] = universe.execute_day(context, day)
    final_store = ri.store_of(context)
    executed_nodes, written, transfer_records, coverage_rows, observed = ri.observe(orchestrator, context, traces)
    problems += observed
    problems += checks.check_targets(expected_instances, written)
    problems += checks.check_nodes(planned, expected_events, executed_nodes)
    transfer_nodes = {k for k in planned if k.startswith(TRANSFER)}
    problems += checks.check_transfers(transfer_records, transfer_nodes, ri.transfer_expectations(orchestrator, plan))
    problems += checks.check_target_identities(ri.target_records(traces, set(plan.targets)),
                                               ri.expected_periods(orchestrator, plan.targets, DAYS))
    problems += checks.check_result_contract(final_store)
    if any(r["targets"] != EXPECTED["integrated_targets"] or r["nodes"] != EXPECTED["planner_nodes"]
           or r["events"] != EXPECTED["events_per_date"]
           or r["transfer_events"] != EXPECTED["transfer_events_per_date"] for r in coverage_rows):
        problems.append("TEMPORAL_FAILURE data com plano incompleto")

    # 5. orquestrador x engine por bloco (mesmas entradas) --------------------------------
    consistency = Counter()
    for day, trace in traces.items():
        for block in common.BLOCKS5:
            block_nodes = [nodes[k] for k in planned if nodes[k].kind == EQUATION and nodes[k].block == block]
            produced = {n.produces[0] for n in block_nodes}
            registry = EquationDefinitionRegistry()
            for n in block_nodes:
                registry.add(catalog.equation_definitions.get(n.node_id))
            mirror = ri.fresh_context(orchestrator)
            orchestrator.seed_parameters(mirror)
            for k, result in context._scoped_results.items():
                if k.entity_id not in produced:
                    mirror._scoped_results[k] = result
                    mirror._index_window(k)
            with mirror.effective_window(day):
                ForecastEngine().calculate_from_definition_registry(
                    equation_definition_registry=registry, calculation_context=mirror,
                    variable_definition_registry=catalog.variable_definitions, run_date=day)
            for e in trace.events:
                if e.kind == EQUATION and e.variable_id in produced:
                    a = ri.encode(context.get_variable_result(e.variable_id, e.scope_type, e.scope_value,
                                                              e.period_id, as_of=day))
                    b = ri.encode(mirror.get_variable_result(e.variable_id, e.scope_type, e.scope_value,
                                                             e.period_id, as_of=day))
                    consistency["compared"] += 1
                    consistency[f"compared_{block}"] += 1
                    if a != b:
                        consistency["different"] += 1
                        problems.append(f"ENGINE_FAILURE orquestrador != engine {day} {e.variable_id} {a} {b}")
    evidence["orchestrator_vs_engine"] = dict(sorted(consistency.items()))

    # 6. temporal -------------------------------------------------------------------------
    counts, temporal_problems = checks.check_temporal(final_store, january_snapshot, [d.isoformat() for d in DAYS],
                                                      ri.derived_variables(plan))
    problems += temporal_problems
    windows = defaultdict(set)
    for k in final_store:
        windows[k[:4]].add(k[4])
    jan_days = {d.isoformat() for d in JAN}
    monthly_jan = [v for (e, st, sv, p), v in windows.items() if p == "2026-01" and None not in v]
    monthly_feb = [v for (e, st, sv, p), v in windows.items() if p == "2026-02" and None not in v]
    annual = [v for (e, st, sv, p), v in windows.items() if p == "2026" and None not in v]
    a41_windows = {k: v for k, v in windows.items() if k[0] in universe.area_41_entities and None not in v}
    evidence["temporal"] = {
        "dates": len(DAYS), "contiguous": all((b - a).days == 1 for a, b in zip(DAYS, DAYS[1:])),
        "monthly_jan_identities": len(monthly_jan), "monthly_jan_all_31_windows": all(v == jan_days for v in monthly_jan),
        "monthly_feb_identities": len(monthly_feb),
        "annual_ytd_identities": len(annual), "annual_ytd_all_32_windows": all(len(v) == 32 for v in annual),
        "area_41_monthly_jan_identities": sum(1 for k in a41_windows if k[3] == "2026-01"),
        "area_41_annual_identities": sum(1 for k, v in a41_windows.items() if k[3] == "2026" and len(v) == 32),
        "daily_keys_have_no_window": all(k[4] is None for k in final_store if k[3] and len(k[3]) == 10),
        "check_temporal_counts": counts, "coverage_class": "YEAR_TO_DATE_PARTIAL_COVERAGE",
    }
    if not (evidence["temporal"]["monthly_jan_all_31_windows"] and evidence["temporal"]["annual_ytd_all_32_windows"]):
        problems.append("TEMPORAL_FAILURE janelas mensais/anuais incompletas")

    # 7. reexecução ------------------------------------------------------------------------
    reexecution = {}
    for day in REEXECUTE:
        before = ri.store_of(context)
        trace = universe.execute_day(context, day)
        after = ri.store_of(context)
        reexecution[day.isoformat()] = {
            "same_store": after == before, "new_keys": len(set(after) - set(before)),
            "first_run_transfer_statuses": dict(Counter(e.status for e in traces[day].of_kind(TRANSFER))),
            "transfer_statuses": dict(Counter(e.status for e in trace.of_kind(TRANSFER))),
            "stated_results": sum(1 for v in after.values() if v[2] is not None),
            "store_sha256_after": ri.store_sha(context)}
        problems += checks.check_reexecution(day.isoformat(), before, after, ri.events_of(traces[day]),
                                             ri.events_of(trace))
    evidence["reexecution"] = reexecution

    # 8. determinismo -------------------------------------------------------------------------
    runs = {}
    for label, order, seed in (("HASH_SEED_A", "A", "0"), ("HASH_SEED_B", "A", "4242"), ("RUN_B", "B", "0")):
        out = subprocess.run([sys.executable, str(HERE / "run_integrated_4a.py"), "--fingerprint", order],
                             cwd=REPO, capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": seed})
        runs[label] = json.loads(out.stdout)
    runs["RUN_A"] = fingerprint("A")
    determinism = {label: {f: r[f] for f in ("results_sha256", "store_sha256", "graph_hash", "hash_seed", "order",
                                              "area_41_store_sha256", "previous_store_sha256")}
                   for label, r in runs.items()}
    determinism["REEXECUTION"] = {"store_sha256": ri.store_sha(context)}
    determinism["identical_results"] = len({r["results_sha256"] for r in runs.values()}) == 1
    determinism["identical_store_including_reexecution"] = len(
        {r["store_sha256"] for r in runs.values()} | {ri.store_sha(context)}) == 1
    determinism["identical_plan_order"] = len({ri.canonical(r["plan_order"]) for r in runs.values()}) == 1
    determinism["identical_graph"] = len({r["graph_hash"] for r in runs.values()}) == 1
    problems += checks.check_determinism({**runs, "REEXECUTION": {"store_sha256": ri.store_sha(context)}})
    if len({r["area_41_store_sha256"] for r in runs.values()}) != 1:
        problems.append("DETERMINISM_FAILURE area_41_store_sha256 diverge entre execuções")
    evidence["determinism"] = determinism

    # 9. não-regressão dos 421 -----------------------------------------------------------------
    non_reg, non_reg_problems = non_regression(universe, final_store, context)
    problems += non_reg_problems
    evidence["non_regression_421"] = {k: non_reg[k] for k in ("result", "differences", "keys_compared",
                                                              "targets_compared", "targets_different",
                                                              "subset_store_sha256", "reference_store_sha256")}

    # 10. estados do area_41 ---------------------------------------------------------------------
    evidence["state"] = state_coverage(universe, problems)
    problems += checks.check_clean_context(ri.store_of(context))
    evidence["clean_context_stated_results"] = sum(1 for v in ri.store_of(context).values()
                                                   if v[2] is not None or v[3] is not None)

    # 11. regressão contra a evidência 4A versionada (só leitura, --no-write) --------------------------
    summary_path = EVIDENCE / "integrated_summary.json"
    if "--no-write" in sys.argv[1:] and summary_path.exists():
        committed = json.loads(summary_path.read_text(encoding="utf-8"))
        for label in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B"):
            for field in ("results_sha256", "area_41_store_sha256", "graph_hash"):
                if determinism[label][field] != committed["determinism"][label][field]:
                    problems.append(f"EVIDENCE_REGRESSION {label}.{field} != evidência 4A versionada")
        if determinism["REEXECUTION"] != committed["determinism"]["REEXECUTION"]:
            problems.append("EVIDENCE_REGRESSION REEXECUTION.store_sha256 != evidência 4A versionada")
        evidence["regression_vs_committed_4a_evidence"] = "COMPARED"
    else:
        evidence["regression_vs_committed_4a_evidence"] = "NOT_COMPARED (regeneração)"

    # 12. evidência --------------------------------------------------------------------------------
    block_rows = []
    for block in common.BLOCKS5:
        block_nodes = [nodes[k] for k in planned if nodes[k].block == block]
        c = Counter(n.kind for n in block_nodes)
        block_rows.append({"block": block, "targets": sum(1 for t in plan.targets if catalog.block_of.get(t) == block),
                           "equation_nodes": c[EQUATION], "aggregation_nodes": c[AGGREGATION],
                           "transfer_nodes": c[TRANSFER],
                           "executed": sum(1 for n in block_nodes
                                           if all(n.key in dict(executed_nodes[d]) for d in executed_nodes))})
    evidence["by_block"] = block_rows
    transfer_rows = []
    for k in [k for k in planned if k.startswith(TRANSFER)]:
        link = catalog.links.link_for(nodes[k].node_id)
        mine = [r for r in transfer_records if r["node"] == k]
        transfer_rows.append({"node": k, "source_block": link.source_block, "source_variable": link.source_definition_id,
                              "target_block": link.consumer_block, "target_variable": link.consumer_definition_id,
                              "frequency": link.frequency, "instances": len(link.instances),
                              "executed_events": len(mine),
                              "verified_events": sum(1 for r in mine if r["producer"] == r["consumer"]),
                              "value_2026-02-01": mine[-1]["consumer"][1] if mine else None,
                              "state_2026-02-01": mine[-1]["consumer"][2] if mine else None,
                              "execution_status": "EXECUTED" if len(mine) == len(DAYS) * len(link.instances)
                              else "NOT_EXECUTED"})
    evidence["transfers"] = transfer_rows
    evidence["temporal_coverage"] = coverage_rows
    evidence["targets_executed"] = sum(1 for t in plan.targets
                                       if all(written[d].get(t) == expected_instances[t] for d in written))
    evidence["nodes_executed"] = sum(1 for k in planned if all(k in dict(executed_nodes[d]) for d in executed_nodes))
    if evidence["targets_executed"] != EXPECTED["integrated_targets"] or evidence["nodes_executed"] != EXPECTED["planner_nodes"]:
        problems.append("TARGET_NOT_EXECUTED alvos/nós executados != contrato")
    evidence["problems"] = problems
    evidence["result"] = "PASS" if not problems else "FAIL"

    if "--no-write" not in sys.argv[1:]:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / "integrated_summary.json").write_text(
            json.dumps(evidence, indent=1, sort_keys=True, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
        (EVIDENCE / "non_regression_421.json").write_text(
            json.dumps(non_reg, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        with (EVIDENCE / "targets.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle, lineterminator="\n")
            w.writerow(["target", "block", "planner_status", "producer_nodes", "planner_nodes", "executed_nodes",
                        "instances", "execution_status", "result_status", "final_results_2026-02-01"])
            for t in plan.targets:
                definition = catalog.variable_definitions.get(t)
                period = common.PERIODS.effective_window(definition.frequency, FEB1).period_id
                final = {f"{st}/{sv}": ri.encode(context.get_variable_result(t, st, sv, period, as_of=FEB1))
                         for st, sv in sorted(expected_instances[t])}
                executed = [k for k in closure[t] if all(k in dict(executed_nodes[d]) for d in executed_nodes)]
                status = "EXECUTED" if all(written[d].get(t) == expected_instances[t] for d in written) else "NOT_EXECUTED"
                result_status = "VALUE_WITHOUT_STATE" if all(v[2] is None and v[3] is None and v[0] != "NoneType"
                                                             for v in final.values()) else "STATED_OR_EMPTY"
                w.writerow([t, catalog.block_of.get(t), "PLANNED", "|".join(producers[t]), "|".join(closure[t]),
                            len(executed), len(expected_instances[t]), status, result_status, ri.canonical(final)])
        with (EVIDENCE / "nodes.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle, lineterminator="\n")
            w.writerow(["order", "node", "kind", "block", "result_identity", "dependencies", "upstream_nodes",
                        "events_per_day", "dates_executed", "dependent_targets", "in_stage_3_4c_plan", "execution_status"])
            plan4 = {s.key for s in universe.plan4.steps}
            for i, k in enumerate(planned):
                n = nodes[k]
                dates = sum(1 for d in executed_nodes if k in dict(executed_nodes[d]))
                identity = "|".join(f"{v}@{catalog.variable_definitions.get(v).frequency}" for v in n.produces)
                w.writerow([i, k, n.kind, n.block, identity, "|".join(sorted(orchestrator._deps[k])),
                            "|".join(upstream[k]), expected_events[k], dates, "|".join(sorted(dependents[k])),
                            k in plan4, "EXECUTED" if dates == len(DAYS) else "NOT_EXECUTED"])
        for name, rows in (("transfers.csv", transfer_rows), ("temporal_coverage.csv", coverage_rows)):
            with (EVIDENCE / name).open("w", encoding="utf-8", newline="") as handle:
                w = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
    print(json.dumps({k: evidence[k] for k in ("universe", "targets_executed", "nodes_executed", "non_regression_421",
                                              "orchestrator_vs_engine", "problems", "result")},
                     indent=1, sort_keys=True, default=str, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    if "--fingerprint" in sys.argv:
        print(json.dumps(fingerprint(sys.argv[sys.argv.index("--fingerprint") + 1]), sort_keys=True))
        sys.exit(0)
    sys.exit(main())
