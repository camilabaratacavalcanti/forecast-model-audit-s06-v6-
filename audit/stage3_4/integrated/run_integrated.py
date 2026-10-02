"""
Stage 3.4C — Integrated Four-Block Regression (REAL_DERIVED_TEST_RESULT).

    python audit/stage3_4/integrated/run_integrated.py [--no-write] [--baseline-dir <dir>]
    python audit/stage3_4/integrated/run_integrated.py --fingerprint A|B   (uso interno: determinismo)

Universo (contrato 3.4A §13–§15, §18):
    446 alvos oficiais (plan_evidence.csv) - 25 de area_41 = 421 alvos integrados
    plano integrado de 421 alvos = 427 nós (218 EQUATION + 197 AGGREGATION + 12 TRANSFER)
    sequência diária contígua 2026-01-01 .. 2026-02-01 (32 datas) no MESMO contexto

Stage 4C: `--baseline-dir <dir>` só muda a FONTE das referências (plan_evidence em `<dir>/stage3_2_plan/`,
universo esperado em `<dir>/stage3_4c_integrated/integrated_summary.json`) e o destino da evidência
(`<dir>/stage3_4c_integrated/`). Sem ele: caminhos e constantes históricos (comportamento idêntico).

Tudo roda sobre o fixture REAL_DERIVED (TEST_FIXTURE_ONLY): nada é
escrito em seeds/links; nenhum bloco ausente é carregado.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from app.domain.equations.registry import EquationDefinitionRegistry  # noqa: E402
from app.domain.results import DetailWithoutStateError, Result  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    AGGREGATION, EQUATION, TRANSFER, InterblockExecutionOrchestrator,
)
from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.time_period_resolver import TimePeriodResolver  # noqa: E402

import checks  # noqa: E402
import fixture  # noqa: E402

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_paths as bp  # noqa: E402  (Stage 4C: só a fonte das referências e o destino)

START, END = date(2026, 1, 1), date(2026, 2, 1)
DAYS = [START + timedelta(days=n) for n in range((END - START).days + 1)]
REEXECUTE = (date(2026, 1, 15), date(2026, 2, 1))
PERIODS = TimePeriodResolver()
INV, VF = "INVALID_INPUT", "VALIDATION_FAILED"


EXPECTED_UNIVERSE_B0 = {"official_targets": 446, "area_41_excluded": 25, "integrated_targets": 421,
                        "planner_nodes": 427, "nodes_by_kind": {EQUATION: 218, AGGREGATION: 197, TRANSFER: 12},
                        "pending_blockers": 0}


def expected_universe():
    """Universo de referência: constantes históricas (default) ou o do summary do baseline indicado.
    None = regeneração (a referência do próprio conjunto ainda não existe)."""
    if bp.is_default():
        return EXPECTED_UNIVERSE_B0
    reference = bp.path("stage3_4c_integrated", "integrated_summary.json")
    if not reference.exists():
        return None
    universe = json.loads(reference.read_text(encoding="utf-8"))["universe"]
    return {k: universe[k] for k in EXPECTED_UNIVERSE_B0}


# ------------------------------------------------------------------ utilidades
def encode(result: Result) -> list:
    return [type(result.value).__name__, repr(result.value), result.state, result.detail]


def store_of(context: CalculationContext) -> dict:
    return {(k.entity_id, k.scope_type, k.scope_value, k.period_id, k.window_end): encode(r)
            for k, r in context._scoped_results.items()}


def store_sha(context: CalculationContext) -> str:
    return sha(sorted([list(k), v] for k, v in store_of(context).items()))


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def sha(obj) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def fresh_context(orchestrator) -> CalculationContext:
    context = CalculationContext()
    context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
    return context


def integrated_plan(orchestrator):
    return orchestrator.plan(orchestrator.targets_of_blocks(fixture.OFFICIAL_BLOCKS))


def execute_day(orchestrator, plan, context, day, overrides=(), injections=()):
    """Entradas determinísticas do dia, sobrescritas/injeções do cenário, execução."""
    fixture.seed_inputs(orchestrator, plan, context, day)
    for variable_id, st, sv, period, result in list(overrides) + list(injections):
        context.set_variable_result(variable_id, result, st, sv, period)
    return orchestrator.execute(plan, context, day)


def events_of(trace) -> list:
    return [[e.step, e.kind, e.node_id, e.block, e.variable_id, e.scope_type, e.scope_value, e.period_id,
             e.status, e.source_block, e.source_variable_id, e.state, e.detail, repr(e.value)]
            for e in trace.events]


def run_sequence(orchestrator, plan, days=DAYS, overrides=None, injections=None, context=None):
    context = context or fresh_context(orchestrator)
    traces = {}
    for day in days:
        traces[day] = execute_day(orchestrator, plan, context, day,
                                  (overrides or (lambda d: []))(day), (injections or (lambda d: []))(day))
    return context, traces


def descendants_of(orchestrator, origins) -> set:
    """Fecho de variáveis descendentes no grafo do planner (deps -> produces)."""
    consumers = defaultdict(set)
    for key, deps in orchestrator._deps.items():
        for variable in deps:
            consumers[variable].add(key)
    seen, stack = set(origins), list(origins)
    while stack:
        for key in consumers.get(stack.pop(), ()):
            for produced in orchestrator._nodes[key].produces:
                if produced not in seen:
                    seen.add(produced)
                    stack.append(produced)
    return seen


def observe(orchestrator, context, traces):
    """Observações por data: nós executados (ordem, nº de eventos), instâncias gravadas por
    variável, registros de transferência (produtor x consumidor) e linha de cobertura."""
    catalog = orchestrator.catalog
    problems = []
    executed_nodes, written, transfer_records, coverage_rows = {}, {}, [], []
    for day, trace in traces.items():
        per_node = Counter((e.kind + ":" + e.node_id) for e in trace.events)
        order = []
        for e in trace.events:
            key = e.kind + ":" + e.node_id
            if not order or order[-1] != key:
                order.append(key)
        executed_nodes[day.isoformat()] = [(k, per_node[k]) for k in order]
        seen = defaultdict(set)
        for e in trace.events:
            seen[e.variable_id].add((e.scope_type, e.scope_value))
            try:
                context.get_variable_result(e.variable_id, e.scope_type, e.scope_value, e.period_id, as_of=day)
            except Exception as exc:  # noqa: BLE001 — evento sem resultado legível é falha
                problems.append(f"ENGINE_FAILURE evento sem resultado {e.variable_id} {day} {exc}")
        written[day.isoformat()] = dict(seen)
        for e in trace.of_kind(TRANSFER):
            link = catalog.links.link_for(e.node_id)
            consumer = context.get_variable_result(e.node_id, e.scope_type, e.scope_value, e.period_id, as_of=day)
            producer = context.get_variable_result(link.source_definition_id, e.scope_type, e.scope_value,
                                                   e.period_id, as_of=day)
            transfer_records.append({"date": day.isoformat(), "node": TRANSFER + ":" + e.node_id,
                                     "instance": f"{e.scope_type}/{e.scope_value}", "period": e.period_id,
                                     "block": e.block, "source_block": e.source_block,
                                     "producer": encode(producer), "consumer": encode(consumer)})
        coverage_rows.append({
            "date": day.isoformat(), "targets": len(seen), "nodes": len(order),
            "transfer_events": len(trace.of_kind(TRANSFER)),
            "monthly_events": sum(1 for e in trace.events if e.period_id and len(e.period_id) == 7),
            "annual_ytd_events": sum(1 for e in trace.events if e.period_id and len(e.period_id) == 4),
            "events": len(trace.events), "errors": 0,
        })
    return executed_nodes, written, transfer_records, coverage_rows, problems


def target_records(traces, targets) -> list:
    """(data, variável, scope_type, scope_value, period_id) de cada evento que grava um alvo."""
    return [(day.isoformat(), e.variable_id, e.scope_type, e.scope_value, e.period_id)
            for day, trace in traces.items() for e in trace.events if e.variable_id in targets]


def expected_periods(orchestrator, targets, days) -> dict:
    """{(variável, data): period_id} pela frequência da definição."""
    definitions = orchestrator.catalog.variable_definitions
    return {(t, d.isoformat()): PERIODS.effective_window(definitions.get(t).frequency, d).period_id
            for t in targets for d in days}


def transfer_expectations(orchestrator, plan) -> dict:
    """{nó TRANSFER: instâncias e blocos do vínculo} a partir do registro de vínculos do fixture."""
    out = {}
    for step in plan.steps:
        if step.kind == TRANSFER:
            link = orchestrator.catalog.links.link_for(step.node_id)
            out[step.key] = {"instances": {f"{st}/{sv}" for st, sv in link.instances},
                             "consumer_block": link.consumer_block, "source_block": link.source_block}
    return out


def node_expectations(orchestrator, plan) -> tuple[dict, dict]:
    """
    expected_events: {nó: nº de instâncias gravadas por data} (materialize_equation /
    instâncias da regra / instâncias do vínculo); expected_instances: {alvo: {(st, sv)}}.
    """
    catalog, engine = orchestrator.catalog, ForecastEngine()
    rules_by_id = defaultdict(list)
    for instance in catalog.aggregation_rule_instances.all():
        rules_by_id[instance.rule.aggregation_rule_id].append(instance)
    expected_events = {}
    for node in plan.steps:
        if node.kind == EQUATION:
            expected_events[node.key] = len(engine.materialize_equation(catalog.equation_definitions.get(node.node_id)))
        elif node.kind == AGGREGATION:
            expected_events[node.key] = len(rules_by_id[node.node_id])
        else:
            expected_events[node.key] = len(catalog.links.link_for(node.node_id).instances)
    expected_instances = {}
    for target in plan.targets:
        definition = catalog.variable_definitions.get(target)
        expected_instances[target] = set(ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value))
    return expected_events, expected_instances


def derived_variables(plan) -> set:
    return {v for step in plan.steps for v in step.produces}


# ------------------------------------------------------------------ determinismo (subprocesso)
def fingerprint(order: str, mutate: bool = False) -> dict:
    """
    Fingerprint de uma sequência completa. `mutate` (só Stage 3.4D, nunca usado pela 3.4C):
    altera UM resultado derivado depois da execução e antes do hash, simulando uma
    execução não determinística para provar que o comparador de fingerprints a rejeita.
    """
    orchestrator = fixture.build(order)
    plan = integrated_plan(orchestrator)
    context, traces = run_sequence(orchestrator, plan)
    if mutate:
        derived = derived_variables(plan)
        victim = min((k for k, r in context._scoped_results.items()
                      if k.entity_id in derived and r.state is None and isinstance(r.value, float)), key=repr)
        context._scoped_results[victim] = Result(context._scoped_results[victim].value + 1.0)
    events = sorted(sorted(map(tuple, events_of(t)), key=lambda e: e[1:]) for t in traces.values())
    results = {"store": sorted([list(k), v] for k, v in store_of(context).items()),
               "events_without_step": [[e[1:] for e in day] for day in events]}
    return {"order": order, "graph_hash": fixture.graph_hash(orchestrator),
            "plan_order": [s.key for s in plan.steps], "results_sha256": sha(results),
            "store_sha256": store_sha(context),
            "hash_seed": os.environ.get("PYTHONHASHSEED")}


# ------------------------------------------------------------------ execução principal
def main() -> int:
    problems: list[str] = []
    evidence: dict = {"label": fixture.LABEL}

    # 1. fixture ----------------------------------------------------------------
    orchestrator = fixture.build("A")
    again = fixture.build("A")
    from tests.test_stage3_2_execution_orchestration import real_derived_orchestrator
    hashes = {"A": fixture.graph_hash(orchestrator), "A_rebuilt": fixture.graph_hash(again),
              "B": fixture.graph_hash(fixture.build("B")),
              "tests_fixture": fixture.graph_hash(real_derived_orchestrator())}
    if len(set(hashes.values())) != 1:
        problems.append(f"FIXTURE_FAILURE hashes de grafo diferentes {hashes}")
    official = InterblockExecutionOrchestrator.from_seed_root(fixture.SEED)
    evidence["fixture"] = {"graph_hashes": hashes, "pending_in_fixture": len(orchestrator.catalog.links.pending()),
                           "pending_official": len(official.catalog.links.pending())}

    # 2. universos ----------------------------------------------------------------
    plan_rows = list(csv.DictReader(
        bp.path("stage3_2_plan", "plan_evidence.csv").open(encoding="utf-8")))
    official_targets = sorted(r["target"] for r in plan_rows)
    all_blocks = fixture.OFFICIAL_BLOCKS + ("area_41",)
    if official_targets != official.targets_of_blocks(all_blocks):
        problems.append("PLANNER_FAILURE plan_evidence.csv != targets_of_blocks (5 blocos)")
    area_41 = sorted(r["target"] for r in plan_rows if r["block"] == "area_41")
    integrated = orchestrator.targets_of_blocks(fixture.OFFICIAL_BLOCKS)
    if integrated != sorted(r["target"] for r in plan_rows if r["block"] != "area_41"):
        problems.append("PLANNER_FAILURE 421 != plan_evidence sem area_41")
    plan = integrated_plan(orchestrator)
    planned = [s.key for s in plan.steps]
    kinds = Counter(s.kind for s in plan.steps)
    universe = {"official_targets": len(official_targets), "area_41_excluded": len(area_41),
                "integrated_targets": len(integrated), "planner_nodes": len(planned),
                "nodes_by_kind": dict(kinds), "pending_blockers": len(plan.pending_blockers),
                "required_inputs": len(plan.required_inputs)}
    reference_universe = expected_universe()
    if reference_universe is None and "--no-write" in sys.argv[1:]:
        problems.append("REFERENCE_MISSING integrated_summary.json do baseline indicado")
    for key, value in (reference_universe or {}).items():
        if universe[key] != value:
            problems.append(f"PLANNER_FAILURE {key} {universe[key]} != {value}")
    evidence["universe"] = universe

    # 3. alvo -> nós, nó -> alvos -------------------------------------------------
    nodes = {s.key: s for s in plan.steps}
    catalog = orchestrator.catalog
    producers = {t: sorted(k for k in orchestrator._producers.get(t, ()) if k in nodes) for t in integrated}
    closure = {t: [s.key for s in orchestrator.plan([t]).steps] for t in integrated}
    dependents = defaultdict(set)
    for target, keys in closure.items():
        for key in keys:
            dependents[key].add(target)
    for target in integrated:
        if not producers[target]:
            problems.append(f"PLANNER_FAILURE alvo sem nó produtor {target}")
        if not set(producers[target]) <= set(closure[target]):
            problems.append(f"PLANNER_FAILURE produtor fora do fecho {target}")
    orphan = sorted(set(planned) - set(dependents))
    if orphan:
        problems.append(f"PLANNER_FAILURE nós sem alvo {orphan[:3]}")
    position = {k: i for i, k in enumerate(planned)}
    upstream = {k: sorted({p for v in orchestrator._deps[k] for p in orchestrator._producers.get(v, ()) if p in nodes})
                for k in planned}
    late = [(k, p) for k in planned for p in upstream[k] if position[p] >= position[k]]
    problems += [f"PLANNER_FAILURE dependência após o consumidor {k} <- {p}" for k, p in late]
    block_edges = sorted({(nodes[p].block, nodes[k].block) for k in planned for p in upstream[k]
                          if nodes[p].block != nodes[k].block})
    cycle_transfers = {k: {"position": position[k], "source_block": catalog.links.link_for(nodes[k].node_id).source_block,
                           "consumer_block": nodes[k].block}
                       for k in planned if nodes[k].kind == TRANSFER and {nodes[k].block,
                       catalog.links.link_for(nodes[k].node_id).source_block} == {"production", "yield"}}
    evidence["graph"] = {"dependencies_precede_consumers": not late, "cross_block_edges": block_edges,
                         "production_yield_cycle_at_block_level": ("production", "yield") in block_edges
                         and ("yield", "production") in block_edges,
                         "production_yield_transfers": cycle_transfers,
                         "annual_aggregation_rules": sum(1 for k in planned if nodes[k].kind == AGGREGATION and any(
                             i.rule.target_frequency == "anual"
                             for i in catalog.aggregation_rule_instances.all()
                             if i.rule.aggregation_rule_id == nodes[k].node_id))}
    expected_events, expected_instances = node_expectations(orchestrator, plan)

    # 4. sequência limpa (RUN_A) -----------------------------------------------------
    context = fresh_context(orchestrator)
    traces, january_snapshot = {}, None
    for day in DAYS:
        if day == date(2026, 2, 1):
            january_snapshot = {k: v for k, v in store_of(context).items() if k[3] == "2026-01"}
        traces[day] = execute_day(orchestrator, plan, context, day)
    final_store = store_of(context)

    executed_nodes, written, transfer_records, coverage_rows, observed_problems = observe(orchestrator, context, traces)
    problems += observed_problems
    problems += checks.check_targets(expected_instances, written)
    problems += checks.check_nodes(planned, expected_events, executed_nodes)
    transfer_nodes = {k for k in planned if k.startswith(TRANSFER)}
    problems += checks.check_transfers(transfer_records, transfer_nodes, transfer_expectations(orchestrator, plan))
    problems += checks.check_target_identities(target_records(traces, set(integrated)),
                                               expected_periods(orchestrator, integrated, DAYS))
    problems += checks.check_result_contract(final_store)
    expected_per_date = (reference_universe or universe)
    if any(r["targets"] != expected_per_date["integrated_targets"] or r["nodes"] != expected_per_date["planner_nodes"]
           for r in coverage_rows):
        problems.append("TEMPORAL_FAILURE data com plano incompleto")

    # 5. orquestrador x engine por bloco (mesmas entradas) ---------------------------
    consistency = Counter()
    for day, trace in traces.items():
        for block in fixture.OFFICIAL_BLOCKS:
            block_nodes = [nodes[k] for k in planned if nodes[k].kind == EQUATION and nodes[k].block == block]
            targets = {n.produces[0] for n in block_nodes}
            registry = EquationDefinitionRegistry()
            for n in block_nodes:
                registry.add(catalog.equation_definitions.get(n.node_id))
            mirror = fresh_context(orchestrator)
            orchestrator.seed_parameters(mirror)
            for key, result in context._scoped_results.items():
                if key.entity_id not in targets:
                    mirror._scoped_results[key] = result
                    mirror._index_window(key)
            with mirror.effective_window(day):
                ForecastEngine().calculate_from_definition_registry(
                    equation_definition_registry=registry, calculation_context=mirror,
                    variable_definition_registry=catalog.variable_definitions, run_date=day)
            for e in trace.events:
                if e.kind == EQUATION and e.variable_id in targets:
                    a = encode(context.get_variable_result(e.variable_id, e.scope_type, e.scope_value,
                                                           e.period_id, as_of=day))
                    b = encode(mirror.get_variable_result(e.variable_id, e.scope_type, e.scope_value,
                                                          e.period_id, as_of=day))
                    consistency["compared"] += 1
                    if a != b:
                        consistency["different"] += 1
                        problems.append(f"ENGINE_FAILURE orquestrador != engine {day} {e.variable_id} {a} {b}")
    evidence["orchestrator_vs_engine"] = dict(consistency)

    # 6. virada de mês e identidade temporal -------------------------------------------
    _counts, temporal_problems = checks.check_temporal(final_store, january_snapshot, [d.isoformat() for d in DAYS],
                                                       derived_variables(plan))
    problems += temporal_problems
    windows = defaultdict(set)
    for k in final_store:
        windows[(k[0], k[1], k[2], k[3])].add(k[4])
    monthly_jan = [v for (e, st, sv, p), v in windows.items() if p == "2026-01" and None not in v]
    monthly_feb = [v for (e, st, sv, p), v in windows.items() if p == "2026-02" and None not in v]
    annual = [v for (e, st, sv, p), v in windows.items() if p == "2026" and None not in v]
    jan_days = {d.isoformat() for d in DAYS if d.month == 1}
    temporal = {
        "dates": len(DAYS), "contiguous": all((b - a).days == 1 for a, b in zip(DAYS, DAYS[1:])),
        "monthly_jan_identities": len(monthly_jan),
        "monthly_jan_all_31_windows": all(v == jan_days for v in monthly_jan),
        "monthly_feb_identities": len(monthly_feb),
        "monthly_feb_windows": sorted({w for v in monthly_feb for w in v}),
        "annual_ytd_identities": len(annual),
        "annual_ytd_all_32_windows": all(len(v) == 32 for v in annual),
        "daily_keys_have_no_window": all(k[4] is None for k in final_store if k[3] and len(k[3]) == 10),
        "coverage_class": "YEAR_TO_DATE_PARTIAL_COVERAGE",
    }
    if not temporal["contiguous"]:
        problems.append("TEMPORAL_FAILURE sequência não contígua")
    evidence["temporal"] = temporal

    # 7. reexecução ----------------------------------------------------------------------
    reexecution = {}
    for day in REEXECUTE:
        before = store_of(context)
        trace = execute_day(orchestrator, plan, context, day)
        statuses = Counter(e.status for e in trace.of_kind(TRANSFER))
        after_store = store_of(context)
        reexecution[day.isoformat()] = {
            "same_store": after_store == before, "new_keys": len(set(after_store) - set(before)),
            "transfer_statuses": dict(statuses),
            "stated_results": sum(1 for v in after_store.values() if v[2] is not None),
            "first_run_events_equal": events_of(trace) == [
                [*ev[:8], "UNCHANGED" if ev[1] == TRANSFER else ev[8], *ev[9:]] for ev in events_of(traces[day])],
        }
        reexecution[day.isoformat()]["first_run_transfer_statuses"] = dict(
            Counter(e.status for e in traces[day].of_kind(TRANSFER)))
        reexecution[day.isoformat()]["store_sha256_after"] = store_sha(context)
        problems += checks.check_reexecution(day.isoformat(), before, after_store, events_of(traces[day]),
                                             events_of(trace))
    evidence["reexecution"] = reexecution

    # 8. determinismo -----------------------------------------------------------------------
    runs = {}
    # RUN_A = processo atual (ORDER_A); RUN_B = ORDER_B (catálogo, vínculos e blocos em ordem
    # inversa); HASH_SEED_A/B = ORDER_A em subprocessos com PYTHONHASHSEED 0 e 4242;
    # REEXECUTION = store após reexecutar 2026-01-15 e 2026-02-01 sobre o contexto de RUN_A.
    for label, order, seed in (("HASH_SEED_A", "A", "0"), ("HASH_SEED_B", "A", "4242"), ("RUN_B", "B", "0")):
        out = subprocess.run([sys.executable, str(HERE / "run_integrated.py"), "--fingerprint", order],
                             cwd=REPO, capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": seed})
        runs[label] = json.loads(out.stdout)
    runs["RUN_A"] = fingerprint("A")
    results = {r["results_sha256"] for r in runs.values()}
    stores = {r["store_sha256"] for r in runs.values()} | {store_sha(context)}
    orders = {canonical(r["plan_order"]) for r in runs.values()}
    graphs = {r["graph_hash"] for r in runs.values()}
    determinism = {label: {"results_sha256": r["results_sha256"], "store_sha256": r["store_sha256"],
                           "graph_hash": r["graph_hash"], "hash_seed": r["hash_seed"], "order": r["order"]}
                   for label, r in runs.items()}
    determinism["REEXECUTION"] = {"store_sha256": store_sha(context)}
    determinism["identical_results"] = len(results) == 1
    determinism["identical_store_including_reexecution"] = len(stores) == 1
    determinism["identical_plan_order"] = len(orders) == 1
    determinism["identical_graph"] = len(graphs) == 1
    problems += checks.check_determinism({**runs, "REEXECUTION": {"store_sha256": store_sha(context)}})
    evidence["determinism"] = determinism

    # 9. estados ---------------------------------------------------------------------------
    evidence["state"] = state_scenarios(orchestrator, plan, problems)

    # 10. isolamento entre contextos: a execução limpa nunca vê estado ------------------
    stated_in_clean = sum(1 for v in store_of(context).values() if v[2] is not None or v[3] is not None)
    problems += checks.check_clean_context(store_of(context))
    evidence["clean_context_stated_results"] = stated_in_clean

    # 11. evidência ----------------------------------------------------------------------------
    block_rows = []
    for block in fixture.OFFICIAL_BLOCKS:
        block_nodes = [nodes[k] for k in planned if nodes[k].block == block]
        c = Counter(n.kind for n in block_nodes)
        block_rows.append({"block": block,
                           "targets": sum(1 for t in integrated if catalog.block_of.get(t) == block),
                           "equation_nodes": c[EQUATION], "aggregation_nodes": c[AGGREGATION],
                           "transfer_nodes": c[TRANSFER],
                           "executed": sum(1 for n in block_nodes
                                           if all(n.key in dict(executed_nodes[d]) for d in executed_nodes))})
    evidence["by_block"] = block_rows
    transfer_rows = []
    for key in [k for k in planned if k.startswith(TRANSFER)]:
        link = catalog.links.link_for(nodes[key].node_id)
        mine = [r for r in transfer_records if r["node"] == key]
        transfer_rows.append({"node": key, "source_block": link.source_block, "source_variable": link.source_definition_id,
                              "target_block": link.consumer_block, "target_variable": link.consumer_definition_id,
                              "frequency": link.frequency, "instances": len(link.instances),
                              "executed_events": len(mine),
                              "verified_events": sum(1 for r in mine if r["producer"] == r["consumer"]),
                              "value_2026-02-01": mine[-1]["consumer"][1] if mine else None,
                              "state_2026-02-01": mine[-1]["consumer"][2] if mine else None,
                              "detail_2026-02-01": mine[-1]["consumer"][3] if mine else None,
                              "execution_status": "EXECUTED" if len(mine) == len(DAYS) * len(link.instances)
                              else "NOT_EXECUTED"})
    evidence["transfers"] = transfer_rows
    evidence["temporal_coverage"] = coverage_rows
    evidence["targets_executed"] = sum(1 for t in integrated
                                       if all(written[d].get(t) == expected_instances[t] for d in written))
    evidence["nodes_executed"] = sum(1 for k in planned if all(k in dict(executed_nodes[d]) for d in executed_nodes))
    evidence["problems"] = problems
    evidence["result"] = "PASS" if not problems else "FAIL"

    if "--no-write" not in sys.argv[1:]:
        out = HERE / "evidence"
        if bp.is_default():
            out.mkdir(exist_ok=True)
        bp.writable("stage3_4c_integrated", "integrated_summary.json").write_text(
            json.dumps(evidence, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
        feb1 = END
        with bp.writable("stage3_4c_integrated", "targets.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle, lineterminator="\n")
            w.writerow(["target", "block", "planner_status", "producer_nodes", "planner_nodes", "executed_nodes",
                        "instances", "execution_status", "result_status", "final_results_2026-02-01"])
            for t in integrated:
                definition = catalog.variable_definitions.get(t)
                period = PERIODS.effective_window(definition.frequency, feb1).period_id
                final = {f"{st}/{sv}": encode(context.get_variable_result(t, st, sv, period, as_of=feb1))
                         for st, sv in sorted(expected_instances[t])}
                executed = [k for k in closure[t] if all(k in dict(executed_nodes[d]) for d in executed_nodes)]
                status = "EXECUTED" if all(written[d].get(t) == expected_instances[t] for d in written) else "NOT_EXECUTED"
                result_status = "VALUE_WITHOUT_STATE" if all(v[2] is None and v[3] is None and v[0] != "NoneType"
                                                             for v in final.values()) else "STATED_OR_EMPTY"
                w.writerow([t, catalog.block_of.get(t), "PLANNED" if t in plan.targets else "NOT_PLANNED",
                            "|".join(producers[t]), "|".join(closure[t]), len(executed), len(expected_instances[t]),
                            status, result_status, canonical(final)])
        with bp.writable("stage3_4c_integrated", "nodes.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle, lineterminator="\n")
            w.writerow(["order", "node", "kind", "block", "result_identity", "dependencies", "upstream_nodes",
                        "events_per_day", "dates_executed", "dependent_targets", "execution_status"])
            for i, key in enumerate(planned):
                n = nodes[key]
                dates = sum(1 for d in executed_nodes if key in dict(executed_nodes[d]))
                identity = "|".join(f"{v}@{catalog.variable_definitions.get(v).frequency}" for v in n.produces)
                w.writerow([i, key, n.kind, n.block, identity, "|".join(sorted(orchestrator._deps[key])),
                            "|".join(upstream[key]), expected_events[key], dates, "|".join(sorted(dependents[key])),
                            "EXECUTED" if dates == len(DAYS) else "NOT_EXECUTED"])
        for name, rows in (("transfers.csv", transfer_rows), ("temporal_coverage.csv", coverage_rows)):
            with bp.writable("stage3_4c_integrated", name).open("w", encoding="utf-8", newline="") as handle:
                w = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
    print(json.dumps({k: evidence[k] for k in ("universe", "targets_executed", "nodes_executed",
                                              "orchestrator_vs_engine", "determinism", "problems", "result")},
                     indent=1, sort_keys=True, default=str))
    return 0 if not problems else 1


# ------------------------------------------------------------------ cenários de estado
def twin(orchestrator, plan, days, overrides, injections):
    clean, _ = run_sequence(orchestrator, plan, days, overrides)
    stated, traces = run_sequence(orchestrator, plan, days, overrides, injections)
    return store_of(clean), store_of(stated), (stated, traces)


def key(variable_id, st, sv, day: date, frequency="diário"):
    period = PERIODS.effective_window(frequency, day).period_id
    window = None if frequency == "diário" else day.isoformat()
    return (variable_id, st, sv, period, window)


def rule_targets(orchestrator, source_variable_id, kind):
    return sorted({i.rule.target_variable_id + "|" + i.rule.target_frequency + "|" + i.rule.aggregation_rule_id
                   for i in orchestrator.catalog.aggregation_rule_instances.all()
                   if i.rule.source_variable_id == source_variable_id and i.rule.aggregation_type == kind})


FEB1 = date(2026, 2, 1)
JAN3, JAN4 = date(2026, 1, 3), date(2026, 1, 4)


# Cada cenário devolve a evidência REAL (execuções gêmeas) e o seu auditor. A Stage 3.4D
# reaplica o mesmo auditor a cópias mutadas da evidência (audit/stage3_4/mutation/).
def scenario_sc1(orchestrator, plan) -> dict:
    """
    SC1 — IF causal EQ12012 + propagação production -> yield/energy/max_ht, 32 datas.
    L3: lth_meta mínimo => condição verdadeira => ramo ativo lê fator_ajuste_lth (VAR12024).
    L4: lth_meta enorme => ramo falso => VAR12024 não é executado.
    VAR12024 (mensal) com estado em janeiro, sem estado em fevereiro.
    """
    def overrides(d):
        return [("VAR12066", "linha", "L3", "2026", Result(0.0001)),
                ("VAR12066", "linha", "L4", "2026", Result(1.0e6))]

    def injections(d):
        if d.month != 1:
            return []
        return [("VAR12024", "linha", sv, "2026-01", Result(None, INV, "fa")) for sv in ("L3", "L4")]
    clean, stated, (context, traces) = twin(orchestrator, plan, DAYS, overrides, injections)
    descendants = descendants_of(orchestrator, {"VAR12024"})
    # Alcance: TODO dia de janeiro — produtor e as três consumidoras em L3 com estado;
    # L1 (outra linha), L4 (ramo inativo) e 2026-02-01 (outro período) sem estado.
    chain = ("VAR12031", "VAR11031", "VAR13062", "VAR18008")
    january = [d for d in DAYS if d.month == 1]
    must = [key(v, "linha", "L3", d) for v in chain for d in january]
    plain = [key(v, "linha", sv, d) for v in chain for sv in ("L1", "L4") for d in january] + \
            [key(v, "linha", sv, FEB1) for v in chain for sv in ("L1", "L3", "L4")]
    transfers = {s.key for s in plan.steps if s.kind == TRANSFER}
    expected_transfers = transfer_expectations(orchestrator, plan)

    def audit(store, context=context, traces=traces):
        p = checks.check_state_diff(clean, store, descendants, INV, "fa")
        # transferências com estado: consumidor == produtor em (value, state, detail)
        _e, _w, records, _c, observed = observe(orchestrator, context, traces)
        p += observed + checks.check_transfers(records, transfers, expected_transfers)
        p += checks.check_expectations(store, must, plain, INV, "fa") + checks.check_result_contract(store)
        return p

    def report(store):
        _e, _w, records, _c, _o = observe(orchestrator, context, traces)
        stated_transfers = Counter(r["node"] for r in records if r["producer"][2] is not None)
        blocks = Counter(orchestrator.catalog.block_of.get(k[0]) for k, v in store.items()
                         if v[2] is not None and k[0] != "VAR12024")
        return {"stated_by_block": dict(blocks),
                "stated_transfer_events_verified": dict(sorted(stated_transfers.items())),
                "descendant_variables": len(descendants),
                "differing_keys": sum(1 for k in clean if clean[k] != store.get(k))}
    return {"clean": clean, "stated": stated, "context": context, "traces": traces, "audit": audit,
            "report": report, "descendants": descendants, "must": must, "plain": plain}


def scenario_sc2(orchestrator, plan) -> dict:
    """
    SC2 — IF causal EQ18003 (energy). VAR18012 (pendente de temperature_lp -> entrada livre
    no fixture): L1 = 10 (< 72: ramo else lê VAR18016); L2 = 100 (> 72: ramo then lê VAR18015).
    """
    days = DAYS[:3]

    def overrides(d):
        return [("VAR18012", "linha", "L1", d.isoformat(), Result(10.0)),
                ("VAR18012", "linha", "L2", d.isoformat(), Result(100.0))]

    def injections(d):
        return [("VAR18016", "linha", sv, "2026-01", Result(None, VF, "t")) for sv in ("L1", "L2")]
    clean, stated, (context, traces) = twin(orchestrator, plan, days, overrides, injections)
    descendants = descendants_of(orchestrator, {"VAR18016"})
    must = [key("VAR18017", "linha", "L1", d) for d in days]
    plain = [key("VAR18017", "linha", "L2", d) for d in days]

    def audit(store):
        return (checks.check_state_diff(clean, store, descendants, VF, "t")
                + checks.check_expectations(store, must, plain, VF, "t") + checks.check_result_contract(store))

    def report(store):
        return {"active_branch_L1": store.get(must[-1]), "inactive_branch_L2": store.get(plain[-1]),
                "stated_variables": sorted({k[0] for k, v in store.items() if v[2] and k[0] != "VAR18016"})}
    return {"clean": clean, "stated": stated, "context": context, "traces": traces, "audit": audit,
            "report": report, "descendants": descendants, "must": must, "plain": plain}


SC3_SOURCES = {"AVERAGE": "VAR11001", "SUM": "VAR13068", "WEIGHTED_AVERAGE": "VAR18047", "MOVING_AVERAGE": "VAR12048"}


def scenario_sc3(orchestrator, plan) -> dict:
    """
    SC3 — Policy B em regras REAIS de cada tipo, injeção em 2026-01-03 (VAR11001 também em 01-04:
    mesmo estado + mesmo detail em dois componentes da janela).
    """
    days = DAYS[:5]
    anchors = {"AVERAGE": ("VAR11001", "linha", "L1"), "SUM": ("VAR13113", None, None),
               "WEIGHTED_AVERAGE": ("VAR18046", None, None), "MOVING_AVERAGE": ("VAR12056", "linha", "L1")}
    vd = orchestrator.catalog.variable_definitions
    injected = []
    for variable_id, st, sv in anchors.values():
        definition = vd.get(variable_id)
        scopes = ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value)
        st, sv = (st, sv) if st else scopes[0]
        injected.append((variable_id, st, sv))

    def inject(d):
        out = []
        for variable_id, st, sv in injected:
            if d == JAN3 or (variable_id == "VAR11001" and d == JAN4):
                out.append((variable_id, st, sv, d.isoformat(), Result(None, INV, "agg")))
        return out
    clean, stated, (context, traces) = twin(orchestrator, plan, days, None, inject)
    descendants = descendants_of(orchestrator, {v for v, _s, _t in injected})
    windows = {}
    for kind, source in SC3_SOURCES.items():
        windows[kind] = []
        for instance in orchestrator.catalog.aggregation_rule_instances.all():
            rule = instance.rule
            if rule.source_variable_id != source or rule.aggregation_type != kind:
                continue
            keys = {d: key(rule.target_variable_id, instance.scope_type, instance.scope_value, d, rule.target_frequency)
                    for d in days[1:]}
            if stated.get(keys[JAN3], [None] * 3)[2] is None and stated.get(keys[days[-1]], [None] * 3)[2] is None:
                continue
            windows[kind].append((rule.aggregation_rule_id, f"{instance.scope_type}/{instance.scope_value}", keys))

    def audit(store):
        p = checks.check_state_diff(clean, store, descendants, INV, "agg")
        for kind, found in windows.items():
            if not found:
                p.append(f"AGGREGATION_FAILURE nenhuma instância real {kind} recebeu estado")
            for _rule, _instance, keys in found:
                p += checks.check_expectations(store, [keys[d] for d in days[2:]], [keys[days[1]]], INV, "agg")
        return p + checks.check_result_contract(store)

    def report(store):
        return {"per_type": {kind: [{"rule": rule, "instance": instance,
                                     "2026-01-02": store.get(keys[days[1]]), "2026-01-03": store.get(keys[JAN3]),
                                     days[-1].isoformat(): store.get(keys[days[-1]])}
                                    for rule, instance, keys in found] for kind, found in windows.items()},
                "injected": injected}
    return {"clean": clean, "stated": stated, "context": context, "traces": traces, "audit": audit,
            "report": report, "descendants": descendants, "windows": windows}


def composition_run(orchestrator, plan, second: Result) -> tuple:
    """
    SC4 — VAR11001 L2 recebe INVALID_INPUT "x" em 2026-01-03 e `second` em 2026-01-04, em
    contexto próprio; a agregação mensal real de VAR11001 compõe os dois na mesma janela.
    Devolve (código do erro ou None, store).
    """
    ctx = fresh_context(orchestrator)
    code = None
    try:
        for d in DAYS[:4]:
            inj = []
            if d == JAN3:
                inj = [("VAR11001", "linha", "L2", d.isoformat(), Result(None, INV, "x"))]
            if d == JAN4:
                inj = [("VAR11001", "linha", "L2", d.isoformat(), second)]
            execute_day(orchestrator, plan, ctx, d, (), inj)
    except Exception as exc:  # noqa: BLE001 — o código do erro é a evidência
        code = getattr(exc, "code", type(exc).__name__)
    return code, store_of(ctx)


def state_scenarios(orchestrator, plan, problems) -> dict:
    report = {}
    for label, build in (("SC1_EQ12012_and_chain", scenario_sc1), ("SC2_EQ18003", scenario_sc2),
                         ("SC3_policy_b_real_rules", scenario_sc3)):
        scenario = build(orchestrator, plan)
        p = scenario["audit"](scenario["stated"])
        report[label] = {"problems": p, **scenario["report"](scenario["stated"])}
        problems += p

    # SC4 — composições sem contrato e detail sem estado (contextos próprios).
    sc4 = {}
    for label, second, expected in (("different_states", Result(None, VF, "x"), "MULTI_STATE_COMBINATION_UNDEFINED"),
                                    ("same_state_different_details", Result(None, INV, "y"),
                                     "MULTI_DETAIL_COMPOSITION_UNDEFINED")):
        code, store = composition_run(orchestrator, plan, second)
        sc4[label] = {"error": code, "expected": expected,
                      "jan3_window_stated": [v for k, v in store.items()
                                             if k[1:3] == ("linha", "L2") and k[3] == "2026-01" and k[4] == "2026-01-03"
                                             and v[2] is not None][:1]}
        if code != expected:
            problems.append(f"AGGREGATION_FAILURE {label}: {code} != {expected}")
    try:
        Result(2.0, None, "x")
        sc4["detail_without_state"] = "ACCEPTED"
        problems.append("STATE_PROPAGATION_FAILURE detail sem estado aceito")
    except DetailWithoutStateError as exc:
        sc4["detail_without_state"] = exc.code
    report["SC4_composition_contracts"] = sc4
    return report


if __name__ == "__main__":
    if "--fingerprint" in sys.argv:
        print(json.dumps(fingerprint(sys.argv[sys.argv.index("--fingerprint") + 1],
                                     mutate="--mutate-one-result" in sys.argv), sort_keys=True))
        sys.exit(0)
    sys.exit(main())
