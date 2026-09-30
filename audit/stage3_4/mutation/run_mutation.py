"""
Stage 3.4D — Mutation & Audit Closure.

    python audit/stage3_4/mutation/run_mutation.py [--no-write]

Prova de mutation resistance dos auditores dos Stages 3.4B e 3.4C:

    execução REAL (planner + orquestrador + engine, fixture REAL_DERIVED;
    runtime 7877551 x HEAD no diferencial)
        -> evidência real (traces, contextos, stores, fingerprints, casos)
        -> mutação controlada, local, em memória / cópia temporária
        -> auditor REAL (o mesmo código usado por run_integrated.py /
           run_differential.py / contrato de resultado do app)
        -> detecção esperada

Cada mutação tem ID estável, contrato (M1..M10), ponto de mutação, artefato,
campo, valor antes/depois, detecção esperada e detecção obtida. Controles
positivos provam que a evidência correta continua aceita.

Nada aqui altera app/, data/, tools/, seeds, workbooks ou o registro de
vínculos: as mutações de proveniência operam numa cópia temporária de
data/seed. Todo resultado de execução é REAL_DERIVED_TEST_RESULT.
"""

from __future__ import annotations

import copy
import csv
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INTEGRATED = REPO / "audit" / "stage3_4" / "integrated"
DIFFERENTIAL = REPO / "audit" / "stage3_4" / "differential"
for path in (REPO, INTEGRATED, DIFFERENTIAL, HERE):
    sys.path.insert(0, str(path))
sys.path.append(str(HERE.parent / "taxonomy_migration"))

import checks  # noqa: E402
import fixture  # noqa: E402
import taxonomy_guard  # noqa: E402
import provenance  # noqa: E402
import run_differential as differential  # noqa: E402
import run_integrated as integrated  # noqa: E402

from app.domain.interblock.registry import InterblockLinkRegistry  # noqa: E402
from app.domain.results import DetailWithoutStateError, Result  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    TRANSFER, ExecutionCatalog, ExecutionPlan, ExecutionTrace, InterblockExecutionOrchestrator,
)

BASELINE = "043fe9c36d9d02664db8be7dd29c0fd7014c73f8"
DAYS = integrated.DAYS
DAYS_ISO = [d.isoformat() for d in DAYS]
JAN5, JAN10, JAN15, JAN20, FEB1 = (date(2026, 1, 5), date(2026, 1, 10), date(2026, 1, 15),
                                   date(2026, 1, 20), date(2026, 2, 1))
INV, VF = integrated.INV, integrated.VF
key = integrated.key


def codes(problems: list[str]) -> list[str]:
    return sorted({p.split()[0] for p in problems})


def git(*args) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True).stdout


# ============================================================== evidência real
class World:
    """Toda a evidência real, produzida uma vez; as mutações trabalham sobre cópias."""

    def __init__(self):
        o = self.orchestrator = fixture.build("A")
        plan = self.plan = integrated.integrated_plan(o)
        self.planned = [s.key for s in plan.steps]
        self.targets = set(plan.targets)
        self.transfer_nodes = {k for k in self.planned if k.startswith(TRANSFER)}
        self.events_exp, self.instances_exp = integrated.node_expectations(o, plan)
        self.transfers_exp = integrated.transfer_expectations(o, plan)
        self.periods = integrated.expected_periods(o, plan.targets, DAYS)
        self.derived = integrated.derived_variables(plan)
        # RUN_A limpo, 32 datas, snapshot de janeiro antes de 2026-02-01 (como a 3.4C)
        self.context = integrated.fresh_context(o)
        self.traces, self.snapshot = {}, None
        for day in DAYS:
            if day == FEB1:
                self.snapshot = {k: v for k, v in integrated.store_of(self.context).items() if k[3] == "2026-01"}
            self.traces[day] = integrated.execute_day(o, plan, self.context, day)
        self.store = integrated.store_of(self.context)
        # FIRST_RUN x REEXECUTION (2026-01-15 e 2026-02-01) no mesmo contexto
        self.reexecution = {}
        for day in integrated.REEXECUTE:
            before = integrated.store_of(self.context)
            trace = integrated.execute_day(o, plan, self.context, day)
            self.reexecution[day] = {"before": before, "after": integrated.store_of(self.context),
                                     "first": integrated.events_of(self.traces[day]),
                                     "re": integrated.events_of(trace)}
        # cenários de estado reais (as mesmas funções usadas pela 3.4C)
        self.sc1 = integrated.scenario_sc1(o, plan)
        self.sc2 = integrated.scenario_sc2(o, plan)
        self.sc3 = integrated.scenario_sc3(o, plan)
        # fingerprints reais: RUN_A (processo atual), RUN_B (ORDER_B), HASH_SEED_A/B (subprocessos)
        self.runs = {"RUN_A": integrated.fingerprint("A")}
        for label, order, seed in (("HASH_SEED_A", "A", "0"), ("HASH_SEED_B", "A", "4242"), ("RUN_B", "B", "0")):
            self.runs[label] = fingerprint_subprocess(order, seed)
        self.runs["REEXECUTION"] = {"store_sha256": integrated.sha(sorted([list(k), v] for k, v in
                                                                           integrated.store_of(self.context).items()))}
        # diferencial 3.4B: runtime 7877551 x HEAD, isolado (git archive + python -I)
        self.differential = differential.produce()
        # proveniência
        self.baseline_links = git("show", f"{BASELINE}:data/seed/interblock_links.json")
        self.summary_34c = json.loads((INTEGRATED / "evidence" / "integrated_summary.json").read_text(encoding="utf-8"))
        self.official = InterblockExecutionOrchestrator.from_seed_root(fixture.SEED)

    # ---------------------------------------------------------- auditores reais
    def audit_run(self, traces, context=None) -> list[str]:
        """Auditor de cobertura da 3.4C (alvos, nós, transferências) sobre traces dados."""
        context = context or self.context
        executed, written, records, _rows, observed = integrated.observe(self.orchestrator, context, traces)
        return (observed + checks.check_targets(self.instances_exp, written)
                + checks.check_nodes(self.planned, self.events_exp, executed)
                + checks.check_transfers(records, self.transfer_nodes, self.transfers_exp)
                + checks.check_target_identities(integrated.target_records(traces, self.targets), self.periods))

    def audit_temporal(self, store) -> list[str]:
        return checks.check_temporal(store, self.snapshot, DAYS_ISO, self.derived)[1]

    def audit_clean_context(self, store) -> list[str]:
        return checks.check_clean_context(store) + checks.check_result_contract(store)

    def audit_differential(self, reference, candidate) -> list[str]:
        evaluated = differential.evaluate(reference, candidate)
        found = {t for _k, types in evaluated["differences"] for t in types}
        found |= {f"COVERAGE_{kind.upper()}" for c in evaluated["cov"].values()
                  for kind in ("duplicates", "missing", "unexpected") if c[kind]}
        return [f"{code} {evaluated['problems'][:2]}" for code in sorted(found)] or evaluated["problems"]

    def audit_provenance(self, seed_root=None, **overrides) -> list[str]:
        arguments = {"official_registry": self.official.catalog.links,
                     "fixture_registry": self.orchestrator.catalog.links,
                     "fixture_hash": fixture.graph_hash(self.orchestrator),
                     "expected_fixture_hash": self.summary_34c["fixture"]["graph_hashes"]["A"],
                     "evidence": self.summary_34c}
        arguments.update(overrides)
        return provenance.check_provenance(seed_root or fixture.SEED, self.baseline_links, **arguments)


def fingerprint_subprocess(order: str, seed: str, mutate: bool = False) -> dict:
    command = [sys.executable, str(INTEGRATED / "run_integrated.py"), "--fingerprint", order]
    if mutate:
        command.append("--mutate-one-result")
    out = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONHASHSEED": seed})
    return json.loads(out.stdout)


# ============================================================== utilitários de mutação
def with_events(world, day, events, traces=None):
    """Cópia dos traces de UMA data com a lista de eventos mutada (as demais datas não entram)."""
    return {day: ExecutionTrace(day, world.plan, events)}


def events(world, day):
    return list(world.traces[day].events)


def find(evts, **fields):
    return next(i for i, e in enumerate(evts) if all(getattr(e, k) == v for k, v in fields.items()))


def describe(e) -> str:
    return f"{e.kind}:{e.node_id} {e.variable_id} {e.scope_type}/{e.scope_value} {e.period_id}"


class Swap:
    """Troca temporária de UM resultado num CalculationContext real (restaurado ao sair)."""

    def __init__(self, context, identity, result):
        self.context, self.identity, self.result = context, identity, result
        self.key = next(k for k in context._scoped_results
                        if (k.entity_id, k.scope_type, k.scope_value, k.period_id, k.window_end) == identity)

    def __enter__(self):
        self.original = self.context._scoped_results[self.key]
        self.context._scoped_results[self.key] = self.result
        return self

    def __exit__(self, *exc):
        self.context._scoped_results[self.key] = self.original


def mutated_store(store, identity, encoded):
    out = dict(store)
    before = out.get(identity)
    out[identity] = encoded
    return out, before


def encoded(result) -> list:
    return integrated.encode(result)


# ============================================================== mutações
MUTATIONS = []


def mutation(mutation_id, contract, description, point, artifact, field, expected, mechanism, real_path):
    def register(fn):
        MUTATIONS.append({"mutation_id": mutation_id, "contract": contract, "mutation_description": description,
                          "mutation_point": point, "artifact": artifact, "field": field,
                          "expected_detection": expected, "detection_mechanism": mechanism,
                          "real_path": real_path, "production_code_touched": "NO", "run": fn})
        return fn
    return register


C_RUN = "3.4C integrated: real planner + orchestrator + engine trace"
C_STATE = "3.4C integrated: real state scenario (twin runs)"
C_TEMP = "3.4C integrated: real temporal store"
C_REEX = "3.4C integrated: real FIRST_RUN x REEXECUTION"
C_DET = "3.4C integrated: real fingerprints (subprocess / ORDER_B)"
B_DIFF = "3.4B differential: real 7877551 x HEAD runner output"
APP = "app result/aggregation contract (real engine execution)"
PROV = "REAL_DERIVED fixture + persisted registry (temporary copy)"


# ---------------- M1 target coverage
@mutation("MUT-T01", "M1", "remove todos os eventos do alvo VAR13001 em 2026-01-15", "ExecutionTrace.events após a execução",
          "trace 2026-01-15", "events[VAR13001]", "TARGET_NOT_EXECUTED", "checks.check_targets (observe)", C_RUN)
def mut_t01(w):
    evts = events(w, JAN15)
    kept = [e for e in evts if e.variable_id != "VAR13001"]
    return {"before": f"{len(evts) - len(kept)} eventos VAR13001", "after": "0 eventos VAR13001",
            "problems": w.audit_run(with_events(w, JAN15, kept))}


@mutation("MUT-T02", "M1", "duplica o evento do alvo VAR12031 linha/L3 em 2026-01-15", "ExecutionTrace.events",
          "trace 2026-01-15", "events[VAR12031 L3]", "TARGET_DUPLICATED", "checks.check_target_identities", C_RUN)
def mut_t02(w):
    evts = events(w, JAN15)
    i = find(evts, variable_id="VAR12031", scope_value="L3")
    return {"before": f"{describe(evts[i])} x1", "after": f"{describe(evts[i])} x2",
            "problems": w.audit_run(with_events(w, JAN15, evts[:i + 1] + [evts[i]] + evts[i + 1:]))}


@mutation("MUT-T03", "M1", "alvo mensal VAR13002 linha/L1 em 2026-02-01 registrado no período 2026-01",
          "ExecutionEvent.period_id", "trace 2026-02-01", "period_id", "TARGET_WRONG_PERIOD",
          "checks.check_target_identities", C_RUN)
def mut_t03(w):
    evts = events(w, FEB1)
    i = find(evts, variable_id="VAR13002", scope_value="L1")
    before = evts[i].period_id
    evts[i] = dataclasses.replace(evts[i], period_id="2026-01")
    return {"before": before, "after": "2026-01", "problems": w.audit_run(with_events(w, FEB1, evts))}


# ---------------- M2 planner coverage
@mutation("MUT-N01", "M2", "remove da evidência todos os eventos do nó EQUATION:EQ12012 em 2026-01-15",
          "ExecutionTrace.events", "trace 2026-01-15", "events[EQUATION:EQ12012]", "PLANNER_ONLY_NODE",
          "checks.check_nodes", C_RUN)
def mut_n01(w):
    evts = events(w, JAN15)
    kept = [e for e in evts if not (e.kind == "EQUATION" and e.node_id == "EQ12012")]
    return {"before": f"{len(evts) - len(kept)} eventos EQ12012", "after": "0",
            "problems": w.audit_run(with_events(w, JAN15, kept))}


@mutation("MUT-N02", "M2", "acrescenta evento de nó inexistente no plano (EQUATION:EQ_NOT_PLANNED)",
          "ExecutionTrace.events", "trace 2026-01-15", "node_id", "ENGINE_ONLY_NODE", "checks.check_nodes", C_RUN)
def mut_n02(w):
    evts = events(w, JAN15)
    i = find(evts, kind="EQUATION")
    ghost = dataclasses.replace(evts[i], node_id="EQ_NOT_PLANNED")
    return {"before": "sem EQ_NOT_PLANNED", "after": describe(ghost),
            "problems": w.audit_run(with_events(w, JAN15, evts + [ghost]))}


@mutation("MUT-N03", "M2", "repete ao fim do dia todos os eventos do nó EQUATION:EQ12012",
          "ExecutionTrace.events", "trace 2026-01-15", "events[EQUATION:EQ12012]", "NODE_EXECUTED_TWICE",
          "checks.check_nodes", C_RUN)
def mut_n03(w):
    evts = events(w, JAN15)
    again = [e for e in evts if e.kind == "EQUATION" and e.node_id == "EQ12012"]
    return {"before": "EQ12012 x1", "after": "EQ12012 x2",
            "problems": w.audit_run(with_events(w, JAN15, evts + again))}


@mutation("MUT-N04", "M2", "remove um único evento (instância) do nó de agregação que produz VAR13001",
          "ExecutionTrace.events", "trace 2026-01-15", "events[VAR13001 linha/L4]", "NODE_EVENT_COUNT",
          "checks.check_nodes", C_RUN)
def mut_n04(w):
    evts = events(w, JAN15)
    i = find(evts, variable_id="VAR13001", scope_value="L4")
    return {"before": "7 eventos", "after": "6 eventos",
            "problems": w.audit_run(with_events(w, JAN15, evts[:i] + evts[i + 1:]))}


@mutation("MUT-N05", "M2", "o orquestrador real executa um plano sem o último nó (ExecutionPlan em memória)",
          "ExecutionPlan.steps antes da execução", "plan 2026-01-01", "steps[-1]", "PLANNER_ONLY_NODE",
          "checks.check_nodes", "3.4C integrated: real orchestrator execution of a crippled plan")
def mut_n05(w):
    crippled = ExecutionPlan(w.plan.targets, w.plan.steps[:-1], w.plan.required_inputs)
    context, traces = integrated.run_sequence(w.orchestrator, crippled, DAYS[:1])
    return {"before": f"{len(w.plan.steps)} nós", "after": f"{len(crippled.steps)} nós (sem {w.plan.steps[-1].key})",
            "problems": w.audit_run(traces, context)}


# ---------------- M3 interblock
@mutation("MUT-TX01", "M3", "remove o evento de transferência VAR11031 linha/L2 em 2026-01-15", "ExecutionTrace.events",
          "trace 2026-01-15", "events[TRANSFER:VAR11031 L2]", "INTERBLOCK_FAILURE", "checks.check_transfers", C_RUN)
def mut_tx01(w):
    evts = events(w, JAN15)
    i = find(evts, kind=TRANSFER, node_id="VAR11031", scope_value="L2")
    return {"before": "7 instâncias", "after": "6 instâncias (sem linha/L2)",
            "problems": w.audit_run(with_events(w, JAN15, evts[:i] + evts[i + 1:]))}


@mutation("MUT-TX02", "M3", "valor recebido pela consumidora VAR11031 linha/L2 em 2026-01-15 alterado",
          "CalculationContext (consumidor) após a execução", "context RUN_A", "value", "INTERBLOCK_FAILURE",
          "checks.check_transfers (consumer == producer)", C_RUN)
def mut_tx02(w):
    identity = ("VAR11031", "linha", "L2", "2026-01-15", None)
    with Swap(w.context, identity, Result(999.0)) as swap:
        problems = w.audit_run({JAN15: w.traces[JAN15]})
    return {"before": encoded(swap.original), "after": encoded(Result(999.0)), "problems": problems}


@mutation("MUT-TX03", "M3", "state recebido por VAR11031 linha/L3 em 2026-01-10 trocado (value e detail mantidos)",
          "CalculationContext (consumidor, cenário SC1)", "context SC1", "state", "INTERBLOCK_FAILURE",
          "checks.check_transfers + check_state_diff (SC1 auditor)", C_STATE)
def mut_tx03(w):
    identity = ("VAR11031", "linha", "L3", "2026-01-10", None)
    ctx = w.sc1["context"]
    with Swap(ctx, identity, Result(None, VF, "fa")) as swap:
        problems = w.sc1["audit"](integrated.store_of(ctx))
    return {"before": encoded(swap.original), "after": encoded(Result(None, VF, "fa")), "problems": problems}


@mutation("MUT-TX04", "M3", "detail recebido por VAR11031 linha/L3 em 2026-01-10 trocado (value e state mantidos)",
          "CalculationContext (consumidor, cenário SC1)", "context SC1", "detail", "INTERBLOCK_FAILURE",
          "checks.check_transfers + check_state_diff (SC1 auditor)", C_STATE)
def mut_tx04(w):
    identity = ("VAR11031", "linha", "L3", "2026-01-10", None)
    ctx = w.sc1["context"]
    with Swap(ctx, identity, Result(None, INV, "fb")) as swap:
        problems = w.sc1["audit"](integrated.store_of(ctx))
    return {"before": encoded(swap.original), "after": encoded(Result(None, INV, "fb")), "problems": problems}


@mutation("MUT-TX05", "M3", "duplica o evento de transferência VAR18006 em 2026-01-15", "ExecutionTrace.events",
          "trace 2026-01-15", "events[TRANSFER:VAR18006]", "INTERBLOCK_FAILURE", "checks.check_transfers (duplicidade)",
          C_RUN)
def mut_tx05(w):
    evts = events(w, JAN15)
    i = find(evts, kind=TRANSFER, node_id="VAR18006")
    return {"before": "1 evento", "after": "2 eventos",
            "problems": w.audit_run(with_events(w, JAN15, evts[:i + 1] + [evts[i]] + evts[i + 1:]))}


@mutation("MUT-TX06", "M3", "transferência VAR11031 linha/L2 atribuída ao alvo VAR13062 (bloco consumidor yield mantido)",
          "ExecutionEvent.node_id/variable_id", "trace 2026-01-15", "node_id", "INTERBLOCK_FAILURE",
          "checks.check_transfers (instâncias e bloco do vínculo)", C_RUN)
def mut_tx06(w):
    evts = events(w, JAN15)
    i = find(evts, kind=TRANSFER, node_id="VAR11031", scope_value="L2")
    evts[i] = dataclasses.replace(evts[i], node_id="VAR13062", variable_id="VAR13062")
    return {"before": "TRANSFER:VAR11031 -> yield", "after": "TRANSFER:VAR13062 (block yield)",
            "problems": w.audit_run(with_events(w, JAN15, evts))}


# ---------------- M4 state propagation / isolation
def sc1_store_mutation(w, identity, value):
    store, before = mutated_store(w.sc1["stated"], identity, value)
    return {"before": before, "after": value, "problems": w.sc1["audit"](store)}


@mutation("MUT-S01", "M4", "descendente de EQ12012 (VAR12031 linha/L3, 2026-01-20) perde o estado propagado",
          "store do cenário SC1 após a execução", "store SC1", "state/detail", "STATE_DIFFERENCE",
          "check_expectations (alcance) do auditor SC1", C_STATE)
def mut_s01(w):
    identity = key("VAR12031", "linha", "L3", JAN20)
    return sc1_store_mutation(w, identity, w.sc1["clean"][identity])


@mutation("MUT-S02", "M4", "estado INVALID_INPUT/fa aparece num não-descendente (VAR13001 linha/L3, 2026-01-10)",
          "store do cenário SC1", "store SC1", "state/detail", "STATE_DIFFERENCE",
          "check_state_diff (vazamento) do auditor SC1", C_STATE)
def mut_s02(w):
    identity = key("VAR13001", "linha", "L3", JAN10, "anual")
    assert "VAR13001" not in w.sc1["descendants"]
    return sc1_store_mutation(w, identity, ["NoneType", "None", INV, "fa"])


@mutation("MUT-S03", "M4", "resultado com estado do SC1 copiado para o contexto limpo RUN_A",
          "CalculationContext limpo", "context RUN_A", "VAR12031 linha/L3 2026-01-10", "STATE_PROPAGATION_FAILURE",
          "checks.check_clean_context", C_STATE)
def mut_s03(w):
    identity = ("VAR12031", "linha", "L3", "2026-01-10", None)
    leaked = Result(None, INV, "fa")
    with Swap(w.context, identity, leaked) as swap:
        problems = w.audit_clean_context(integrated.store_of(w.context))
    return {"before": encoded(swap.original), "after": encoded(leaked), "problems": problems}


@mutation("MUT-S04", "M4", "grava Result(value, state=None, detail='fa') pelo contrato real de resultado",
          "construção de Result", "Result", "detail", "DETAIL_WITHOUT_STATE", "app.domain.results.Result",
          APP)
def mut_s04(w):
    try:
        Result(1.25, None, "fa")
        problems = []
    except DetailWithoutStateError as exc:
        problems = [f"{exc.code} {exc}"]
    return {"before": "Result(1.25, None, None)", "after": "Result(1.25, None, 'fa')", "problems": problems}


@mutation("MUT-S05", "M4", "detail sem state na evidência do contexto limpo (VAR12031 linha/L1, 2026-01-10)",
          "store RUN_A", "store RUN_A", "detail", "DETAIL_WITHOUT_STATE", "checks.check_result_contract", C_STATE)
def mut_s05(w):
    identity = key("VAR12031", "linha", "L1", JAN10)
    before = w.store[identity]
    store, _ = mutated_store(w.store, identity, [*before[:3], "fa"])
    return {"before": before, "after": store[identity], "problems": w.audit_clean_context(store)}


@mutation("MUT-S06", "M4", "estado vaza para outra linha não injetada (VAR12031 linha/L1, 2026-01-10)",
          "store SC1", "store SC1", "state/detail", "STATE_DIFFERENCE", "check_expectations (plain) do auditor SC1",
          C_STATE)
def mut_s06(w):
    return sc1_store_mutation(w, key("VAR12031", "linha", "L1", JAN10), ["NoneType", "None", INV, "fa"])


@mutation("MUT-S07", "M4", "estado de janeiro vaza para 2026-02-01 (VAR12031 linha/L3)",
          "store SC1", "store SC1", "state/detail", "STATE_DIFFERENCE", "check_expectations (plain) do auditor SC1",
          C_STATE)
def mut_s07(w):
    return sc1_store_mutation(w, key("VAR12031", "linha", "L3", FEB1), ["NoneType", "None", INV, "fa"])


@mutation("MUT-S08", "M4", "detail perdido num descendente transferido (VAR11031 linha/L3, 2026-01-10)",
          "store SC1", "store SC1", "detail", "STATE_DIFFERENCE", "check_state_diff do auditor SC1", C_STATE)
def mut_s08(w):
    return sc1_store_mutation(w, key("VAR11031", "linha", "L3", JAN10), ["NoneType", "None", INV, None])


@mutation("MUT-S09", "M4", "EQ12012: estado atravessa o ramo INATIVO (VAR12031 linha/L4, 2026-01-05)",
          "store SC1", "store SC1", "state/detail", "STATE_DIFFERENCE", "check_expectations (plain) do auditor SC1",
          C_STATE)
def mut_s09(w):
    return sc1_store_mutation(w, key("VAR12031", "linha", "L4", JAN5), ["NoneType", "None", INV, "fa"])


@mutation("MUT-S10", "M4", "EQ18003: estado atravessa o ramo INATIVO (VAR18017 linha/L2, 2026-01-03)",
          "store SC2", "store SC2", "state/detail", "STATE_DIFFERENCE", "check_expectations (plain) do auditor SC2",
          C_STATE)
def mut_s10(w):
    identity = w.sc2["plain"][-1]
    store, before = mutated_store(w.sc2["stated"], identity, ["NoneType", "None", VF, "t"])
    return {"before": before, "after": store[identity], "problems": w.sc2["audit"](store)}


@mutation("MUT-S11", "M4", "EQ18003: ramo ATIVO não propaga (VAR18017 linha/L1, 2026-01-02 volta ao valor limpo)",
          "store SC2", "store SC2", "state/detail", "STATE_DIFFERENCE", "check_expectations (alcance) do auditor SC2",
          C_STATE)
def mut_s11(w):
    identity = w.sc2["must"][1]
    store, before = mutated_store(w.sc2["stated"], identity, w.sc2["clean"][identity])
    return {"before": before, "after": store[identity], "problems": w.sc2["audit"](store)}


# ---------------- M5 state-aware aggregation
def sc3_key(w, kind, day):
    return w.sc3["windows"][kind][0][2][day]


def sc3_mutation(w, kind, day, value):
    identity = sc3_key(w, kind, day)
    store, before = mutated_store(w.sc3["stated"], identity, value)
    return {"before": before, "after": value, "problems": w.sc3["audit"](store)}


@mutation("MUT-A01", "M5", "agregação mensal real de VAR11001 linha/L2 recebe INVALID_INPUT e VALIDATION_FAILED",
          "entrada injetada na execução real", "context SC4", "state", "MULTI_STATE_COMBINATION_UNDEFINED",
          "compose_states (engine real)", APP)
def mut_a01(w):
    code, _store = integrated.composition_run(w.orchestrator, w.plan, Result(None, VF, "x"))
    return {"before": "INVALID_INPUT/x + INVALID_INPUT/x", "after": "INVALID_INPUT/x + VALIDATION_FAILED/x",
            "problems": [code] if code else []}


@mutation("MUT-A02", "M5", "agregação mensal real de VAR11001 linha/L2 recebe mesmo state com details diferentes",
          "entrada injetada na execução real", "context SC4", "detail", "MULTI_DETAIL_COMPOSITION_UNDEFINED",
          "compose_states (engine real)", APP)
def mut_a02(w):
    code, _store = integrated.composition_run(w.orchestrator, w.plan, Result(None, INV, "y"))
    return {"before": "INVALID_INPUT/x + INVALID_INPUT/x", "after": "INVALID_INPUT/x + INVALID_INPUT/y",
            "problems": [code] if code else []}


@mutation("MUT-A03", "M5", "AVERAGE real perde o estado (janela 2026-01-04 volta ao valor limpo)",
          "store SC3", "store SC3", "state", "STATE_DIFFERENCE", "check_expectations do auditor SC3", C_STATE)
def mut_a03(w):
    identity = sc3_key(w, "AVERAGE", date(2026, 1, 4))
    return sc3_mutation(w, "AVERAGE", date(2026, 1, 4), w.sc3["clean"][identity])


@mutation("MUT-A04", "M5", "SUM real perde o detail (janela 2026-01-05)", "store SC3", "store SC3", "detail",
          "STATE_DIFFERENCE", "check_state_diff / check_expectations do auditor SC3", C_STATE)
def mut_a04(w):
    return sc3_mutation(w, "SUM", JAN5, ["NoneType", "None", INV, None])


@mutation("MUT-A05", "M5", "WEIGHTED_AVERAGE real devolve valor junto com o estado (deveria ser state-only)",
          "store SC3", "store SC3", "value", "STATE_DIFFERENCE", "check_state_diff (state-only) do auditor SC3", C_STATE)
def mut_a05(w):
    return sc3_mutation(w, "WEIGHTED_AVERAGE", date(2026, 1, 3), ["float", "11.884293149167227", INV, "agg"])


@mutation("MUT-A06", "M5", "MOVING_AVERAGE real com detail sem state (janela 2026-01-04)", "store SC3", "store SC3",
          "state", "DETAIL_WITHOUT_STATE", "checks.check_result_contract (auditor SC3)", C_STATE)
def mut_a06(w):
    return sc3_mutation(w, "MOVING_AVERAGE", date(2026, 1, 4), ["NoneType", "None", None, "agg"])


# ---------------- M6 temporal identity
MONTHLY = ("VAR13002", "linha", "L1", "2026-01")


@mutation("MUT-TM01", "M6", "janelas 2026-01-14 e 2026-01-15 de VAR13002 linha/L1 colapsadas numa só identidade",
          "store RUN_A", "store RUN_A", "window_end", "TEMPORAL_FAILURE", "checks.check_temporal", C_TEMP)
def mut_tm01(w):
    store = dict(w.store)
    moved = store.pop((*MONTHLY, "2026-01-15"))
    store[(*MONTHLY, "2026-01-14")] = moved
    return {"before": "window_end 2026-01-14 e 2026-01-15", "after": "window_end 2026-01-14 (valor da 15)",
            "problems": w.audit_temporal(store)}


@mutation("MUT-TM02", "M6", "reexecução de 2026-01-15 cria nova identidade para a mesma janela",
          "store após REEXECUTION", "store REEXECUTION 2026-01-15", "window_end", "REEXECUTION_FAILURE",
          "checks.check_reexecution + checks.check_temporal", C_REEX)
def mut_tm02(w):
    r = w.reexecution[JAN15]
    after = dict(r["after"])
    after[(*MONTHLY, "2026-01-15T00:00:00")] = after[(*MONTHLY, "2026-01-15")]
    problems = checks.check_reexecution("2026-01-15", r["before"], after, r["first"], r["re"]) + w.audit_temporal(after)
    return {"before": "1 identidade (window 2026-01-15)", "after": "2 identidades (2026-01-15, 2026-01-15T00:00:00)",
            "problems": problems}


@mutation("MUT-TM03", "M6", "resultado de 2026-02-01 contamina a janela 2026-01-10 de VAR13002 linha/L1",
          "store RUN_A", "store RUN_A", "value", "TEMPORAL_FAILURE", "checks.check_temporal (snapshot de janeiro)",
          C_TEMP)
def mut_tm03(w):
    identity = (*MONTHLY, "2026-01-10")
    feb = w.store[("VAR13002", "linha", "L1", "2026-02", "2026-02-01")]
    store, before = mutated_store(w.store, identity, feb)
    return {"before": before, "after": feb, "problems": w.audit_temporal(store)}


@mutation("MUT-TM04", "M6", "identidade mensal derivada gravada sem janela (window_end None)",
          "store RUN_A", "store RUN_A", "window_end", "TEMPORAL_FAILURE", "checks.check_temporal", C_TEMP)
def mut_tm04(w):
    store = dict(w.store)
    store[(*MONTHLY, None)] = store[(*MONTHLY, "2026-01-31")]
    return {"before": "31 janelas", "after": "31 janelas + window None", "problems": w.audit_temporal(store)}


@mutation("MUT-TM05", "M6", "janela 2026-02-01 atribuída ao período 2026-01 (identidade temporal incorreta)",
          "store RUN_A", "store RUN_A", "period_id", "TEMPORAL_FAILURE", "checks.check_temporal", C_TEMP)
def mut_tm05(w):
    store = dict(w.store)
    feb = store.pop(("VAR13002", "linha", "L1", "2026-02", "2026-02-01"))
    store[(*MONTHLY, "2026-02-01")] = feb
    return {"before": "period 2026-02", "after": "period 2026-01", "problems": w.audit_temporal(store)}


# ---------------- M7 reexecution
def reexecution_problems(w, day, after=None, re_events=None):
    r = w.reexecution[day]
    return checks.check_reexecution(day.isoformat(), r["before"], r["after"] if after is None else after,
                                    r["first"], r["re"] if re_events is None else re_events)


def real_reexecution(w, day, overrides):
    """Reexecuta `day` numa CÓPIA do contexto RUN_A com entradas sobrescritas (execução real)."""
    context = copy.deepcopy(w.context)
    before = integrated.store_of(context)
    try:
        trace = integrated.execute_day(w.orchestrator, w.plan, context, day, overrides)
    except Exception as exc:  # noqa: BLE001 — o código do erro do engine é a detecção
        return before, [f"{getattr(exc, 'code', type(exc).__name__)} {exc}"[:300]]
    return before, checks.check_reexecution(day.isoformat(), before, integrated.store_of(context),
                                            w.reexecution[day]["first"], integrated.events_of(trace))


@mutation("MUT-R01", "M7", "reexecução REAL de 2026-01-15 com entrada diferente sem transferência a jusante (VAR13003 L1)",
          "entrada da segunda execução (cópia do contexto)", "context REEXECUTION (deepcopy)", "input value",
          "REEXECUTION_FAILURE", "checks.check_reexecution", "3.4C integrated: real re-execution on a context copy")
def mut_r01(w):
    before, problems = real_reexecution(w, JAN15, [("VAR13003", "linha", "L1", "2026-01-15", Result(7.0))])
    return {"before": before[key("VAR13003", "linha", "L1", JAN15)], "after": encoded(Result(7.0)), "problems": problems}


@mutation("MUT-R06", "M7", "reexecução REAL de 2026-01-15 com entrada diferente a montante de uma transferência "
          "(VAR11001 L1 -> yield VAR11226 -> production VAR12062)", "entrada da segunda execução (cópia do contexto)",
          "context REEXECUTION (deepcopy)", "input value", "INTERBLOCK_CONSUMER_VALUE_CONFLICT",
          "InterblockResolver.transfer_result (engine real)", "3.4C integrated: real re-execution on a context copy")
def mut_r06(w):
    before, problems = real_reexecution(w, JAN15, [("VAR11001", "linha", "L1", "2026-01-15", Result(7.0))])
    return {"before": before[key("VAR11001", "linha", "L1", JAN15)], "after": encoded(Result(7.0)), "problems": problems}


@mutation("MUT-R02", "M7", "transferência duplicada na reexecução de 2026-02-01", "eventos REEXECUTION",
          "events REEXECUTION 2026-02-01", "events[TRANSFER:VAR18009]", "REEXECUTION_FAILURE",
          "checks.check_reexecution (duplicidade)", C_REEX)
def mut_r02(w):
    re = list(w.reexecution[FEB1]["re"])
    i = next(i for i, e in enumerate(re) if e[1] == TRANSFER and e[2] == "VAR18009")
    return {"before": "1 evento", "after": "2 eventos",
            "problems": reexecution_problems(w, FEB1, re_events=re[:i + 1] + [re[i]] + re[i + 1:])}


@mutation("MUT-R03", "M7", "estado residual após a reexecução (VAR12031 linha/L2, 2026-02-01)", "store REEXECUTION",
          "store REEXECUTION 2026-02-01", "state/detail", "REEXECUTION_FAILURE", "checks.check_reexecution", C_REEX)
def mut_r03(w):
    identity = key("VAR12031", "linha", "L2", FEB1)
    after, before = mutated_store(w.reexecution[FEB1]["after"], identity, ["NoneType", "None", INV, "residual"])
    return {"before": before, "after": after[identity], "problems": reexecution_problems(w, FEB1, after=after)}


@mutation("MUT-R04", "M7", "reexecução regrava a transferência (status WRITTEN em vez de UNCHANGED)",
          "eventos REEXECUTION", "events REEXECUTION 2026-01-15", "status", "REEXECUTION_FAILURE",
          "checks.check_reexecution", C_REEX)
def mut_r04(w):
    re = [list(e) for e in w.reexecution[JAN15]["re"]]
    i = next(i for i, e in enumerate(re) if e[1] == TRANSFER)
    re[i][8] = "WRITTEN"
    return {"before": "UNCHANGED", "after": "WRITTEN", "problems": reexecution_problems(w, JAN15, re_events=re)}


@mutation("MUT-R05", "M7", "evento da reexecução com valor diferente do FIRST_RUN (store intacto)",
          "eventos REEXECUTION", "events REEXECUTION 2026-01-15", "value", "REEXECUTION_FAILURE",
          "checks.check_reexecution", C_REEX)
def mut_r05(w):
    re = [list(e) for e in w.reexecution[JAN15]["re"]]
    i = next(i for i, e in enumerate(re) if e[1] == "EQUATION")
    before = re[i][13]
    re[i][13] = "0.0"
    return {"before": before, "after": "0.0", "problems": reexecution_problems(w, JAN15, re_events=re)}


# ---------------- M8 determinism
def determinism_problems(w, label, run):
    return checks.check_determinism({**w.runs, label: run})


@mutation("MUT-DT01", "M8", "execução com PYTHONHASHSEED=4242 diverge em um resultado",
          "resultado da execução em subprocesso antes do hash", "fingerprint HASH_SEED_B", "results_sha256",
          "DETERMINISM_FAILURE", "checks.check_determinism", C_DET)
def mut_dt01(w):
    run = fingerprint_subprocess("A", "4242", mutate=True)
    return {"before": w.runs["HASH_SEED_B"]["results_sha256"], "after": run["results_sha256"],
            "problems": determinism_problems(w, "HASH_SEED_B", run)}


@mutation("MUT-DT02", "M8", "ordem dos blocos ORDER_B altera a ordem do plano (dois nós trocados)",
          "fingerprint RUN_B", "fingerprint RUN_B", "plan_order", "DETERMINISM_FAILURE", "checks.check_determinism",
          C_DET)
def mut_dt02(w):
    run = dict(w.runs["RUN_B"])
    order = list(run["plan_order"])
    order[0], order[-1] = order[-1], order[0]
    run["plan_order"] = order
    return {"before": f"{w.runs['RUN_B']['plan_order'][0]} ... {w.runs['RUN_B']['plan_order'][-1]}",
            "after": f"{order[0]} ... {order[-1]}", "problems": determinism_problems(w, "RUN_B", run)}


@mutation("MUT-DT03", "M8", "ordem dos links ORDER_B com um vínculo divergente (grafo diferente)",
          "registro de vínculos do fixture ORDER_B em memória", "fixture ORDER_B", "links", "DETERMINISM_FAILURE",
          "fixture.graph_hash + checks.check_determinism", C_DET)
def mut_dt03(w):
    payload = json.loads((fixture.SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    payload["links"] = list(reversed(payload["links"]))
    dropped = payload["links"].pop(0)
    blocks = list(reversed(payload["workbooks"]))
    raw = {b: json.loads((fixture.SEED / b / "variables.json").read_text(encoding="utf-8")) for b in blocks}
    catalog = ExecutionCatalog.from_seed_root(fixture.SEED)
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    run = dict(w.runs["RUN_B"], graph_hash=fixture.graph_hash(InterblockExecutionOrchestrator(catalog)))
    return {"before": w.runs["RUN_B"]["graph_hash"],
            "after": f"{run['graph_hash']} (sem vínculo {dropped['consumer_definition']})",
            "problems": determinism_problems(w, "RUN_B", run)}


@mutation("MUT-DT04", "M8", "ordem de inserção equivalente (ORDER_B) com um resultado divergente",
          "resultado da execução ORDER_B antes do hash", "fingerprint RUN_B (processo atual)", "results_sha256",
          "DETERMINISM_FAILURE", "checks.check_determinism", C_DET)
def mut_dt04(w):
    run = integrated.fingerprint("B", mutate=True)
    return {"before": w.runs["RUN_B"]["results_sha256"], "after": run["results_sha256"],
            "problems": determinism_problems(w, "RUN_B", run)}


# ---------------- M9 differential
def candidate_case(w, operation):
    candidate = copy.deepcopy(w.differential["candidate"])
    index = next(i for i, c in enumerate(candidate["cases"]) if c["operation_type"] == operation)
    return candidate, index


def differential_mutation(w, candidate, before, after):
    return {"before": before, "after": after,
            "problems": w.audit_differential(w.differential["reference"], candidate)}


@mutation("MUT-D01", "M9", "valor numérico de um caso de equação do candidate alterado",
          "saída do runner candidate", "differential candidate", "outcome.value", "VALUE_DIFFERENCE",
          "run_differential.evaluate / compare.compare_case", B_DIFF)
def mut_d01(w):
    candidate, i = candidate_case(w, "EQUATION")
    outcome = candidate["cases"][i]["outcome"]
    before = outcome[2]
    outcome[2] = [before[0], repr(float(before[1]) + 1e-9)]
    return differential_mutation(w, candidate, before, outcome[2])


@mutation("MUT-D02", "M9", "somente o state de um caso do candidate alterado", "saída do runner candidate",
          "differential candidate", "outcome.state", "STATE_DIFFERENCE", "run_differential.evaluate", B_DIFF)
def mut_d02(w):
    candidate, i = candidate_case(w, "AGGREGATION")
    outcome = candidate["cases"][i]["outcome"]
    before, outcome[3] = outcome[3], INV
    return differential_mutation(w, candidate, before, INV)


@mutation("MUT-D03", "M9", "somente o detail de um caso do candidate alterado", "saída do runner candidate",
          "differential candidate", "outcome.detail", "DETAIL_DIFFERENCE", "run_differential.evaluate", B_DIFF)
def mut_d03(w):
    candidate, i = candidate_case(w, "EQUATION")
    outcome = candidate["cases"][i]["outcome"]
    before, outcome[4] = outcome[4], "x"
    return differential_mutation(w, candidate, before, "x")


@mutation("MUT-D04", "M9", "um resultado removido do candidate", "saída do runner candidate", "differential candidate",
          "cases[i]", "MISSING_CANDIDATE_RESULT", "run_differential.evaluate / compare.coverage", B_DIFF)
def mut_d04(w):
    candidate, i = candidate_case(w, "AGGREGATION")
    removed = candidate["cases"].pop(i)
    return differential_mutation(w, candidate, removed["instance_id"], "ausente")


@mutation("MUT-D05", "M9", "um resultado duplicado no candidate", "saída do runner candidate", "differential candidate",
          "cases[i]", "COVERAGE_DUPLICATES", "run_differential.evaluate / compare.coverage", B_DIFF)
def mut_d05(w):
    candidate, i = candidate_case(w, "EQUATION")
    candidate["cases"].append(copy.deepcopy(candidate["cases"][i]))
    return differential_mutation(w, candidate, "1 caso", "2 casos")


@mutation("MUT-D06", "M9", "identidade (period_id) de um caso de agregação do candidate alterada",
          "saída do runner candidate", "differential candidate", "period_id", "STRUCTURAL_DIFFERENCE",
          "run_differential.evaluate / compare.compare_case", B_DIFF)
def mut_d06(w):
    candidate, i = candidate_case(w, "AGGREGATION")
    case = candidate["cases"][i]
    before = case["period_id"]
    case["period_id"] = "1999"
    return differential_mutation(w, candidate, before, "1999")


# ---------------- M10 fixture / provenance
@mutation("MUT-P01", "M10", "evidência do fixture rotulada como resultado operacional", "integrated_summary.json (cópia)",
          "evidence 3.4C", "label", "PROVENANCE_FAILURE", "provenance.check_provenance", PROV)
def mut_p01(w):
    evidence = dict(w.summary_34c, label="OPERATIONAL_RESULT")
    return {"before": w.summary_34c["label"], "after": "OPERATIONAL_RESULT",
            "problems": w.audit_provenance(evidence=evidence)}


@mutation("MUT-P02", "M10", "fixture com a representação dos 16 pendentes alterada (15 mascarados, 1 mantido)",
          "registro de vínculos do fixture em memória", "fixture ORDER_A", "pending", "FIXTURE_FAILURE",
          "provenance.check_provenance (grafo + pendências do fixture)", PROV)
def mut_p02(w):
    payload = json.loads((fixture.SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = payload["pending"][:1]
    raw = {b: json.loads((fixture.SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog = ExecutionCatalog.from_seed_root(fixture.SEED)
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    mutated = InterblockExecutionOrchestrator(catalog)
    problems = w.audit_provenance(fixture_registry=mutated.catalog.links, fixture_hash=fixture.graph_hash(mutated))
    official = sorted(p.consumer_definition_id for p in w.official.catalog.links.pending())
    assert len(official) == 16                                    # o oficial não foi tocado
    return {"before": "fixture pending = 0", "after": "fixture pending = 1", "problems": problems}


@mutation("MUT-P03", "M10", "registro oficial em memória com as 16 pendências mascaradas", "registro oficial em memória",
          "official registry (memória)", "pending", "PENDING_LINKS_ALTERED", "provenance.check_provenance", PROV)
def mut_p03(w):
    return {"before": "16 pendências", "after": "0 pendências",
            "problems": w.audit_provenance(official_registry=w.orchestrator.catalog.links)}


@mutation("MUT-P04", "M10", "registro persistente com pending = [] (cópia temporária de data/seed)",
          "interblock_links.json numa cópia temporária", "data/seed (cópia)", "pending", "PENDING_LINKS_ALTERED",
          "provenance.check_provenance (bytes + pendências persistidas)", PROV)
def mut_p04(w):
    with tempfile.TemporaryDirectory(prefix="stage3_4d_") as tmp:
        seed = Path(tmp) / "seed"
        shutil.copytree(fixture.SEED, seed)
        payload = json.loads((seed / "interblock_links.json").read_text(encoding="utf-8"))
        payload["pending"] = []
        (seed / "interblock_links.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        problems = w.audit_provenance(seed_root=seed)
    return {"before": "16 pendências persistidas", "after": "0 pendências persistidas", "problems": problems}


@mutation("MUT-P05", "M10", "pendência persistida mascarada como resolvida (resolution_status) na cópia temporária",
          "interblock_links.json numa cópia temporária", "data/seed (cópia)", "pending[0].resolution_status",
          "PENDING_LINKS_ALTERED", "provenance.check_provenance", PROV)
def mut_p05(w):
    with tempfile.TemporaryDirectory(prefix="stage3_4d_") as tmp:
        seed = Path(tmp) / "seed"
        shutil.copytree(fixture.SEED, seed)
        payload = json.loads((seed / "interblock_links.json").read_text(encoding="utf-8"))
        before = payload["pending"][0]["resolution_status"]
        payload["pending"][0]["resolution_status"] = "RESOLVED_BY_FIXTURE"
        (seed / "interblock_links.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        problems = w.audit_provenance(seed_root=seed)
    return {"before": before, "after": "RESOLVED_BY_FIXTURE", "problems": problems}


@mutation("MUT-P06", "M10", "evidência do fixture reclassificada como OPERATIONAL", "integrated_summary.json (cópia)",
          "evidence 3.4C", "classification", "PROVENANCE_FAILURE", "provenance.check_provenance", PROV)
def mut_p06(w):
    evidence = dict(w.summary_34c, classification="OPERATIONAL")
    return {"before": "TEST_FIXTURE_ONLY (implícito)", "after": "OPERATIONAL",
            "problems": w.audit_provenance(evidence=evidence)}


# ============================================================== controles positivos
def positive_controls(w) -> list[dict]:
    controls = []

    def control(control_id, family, description, problems):
        controls.append({"control_id": control_id, "family": family, "description": description,
                         "result": "ACCEPT" if not problems else "REJECT", "problems": problems[:3]})

    control("PC-TARGET-NODE-TRANSFER", "M1/M2/M3", "RUN_A 32 datas: alvos, nós e transferências",
            w.audit_run(w.traces))
    control("PC-STATE-SC1", "M3/M4", "SC1 (EQ12012 + cadeia interbloco, 32 datas)", w.sc1["audit"](w.sc1["stated"]))
    control("PC-STATE-SC2", "M4", "SC2 (EQ18003)", w.sc2["audit"](w.sc2["stated"]))
    control("PC-AGGREGATION-SC3", "M5", "SC3 (Policy B em AVERAGE/SUM/WEIGHTED/MOVING reais)",
            w.sc3["audit"](w.sc3["stated"]))
    code, _store = integrated.composition_run(w.orchestrator, w.plan, Result(None, INV, "x"))
    control("PC-AGGREGATION-SAME-STATE-SAME-DETAIL", "M5", "mesmo state + mesmo detail compõe sem erro",
            [code] if code else [])
    valid = []
    for result in ((1.0, None, None), (None, INV, None), (None, INV, "d"), (2.0, VF, "d")):
        try:
            Result(*result)
        except Exception as exc:  # noqa: BLE001
            valid.append(f"{type(exc).__name__} {result}")
    control("PC-RESULT-CONTRACT", "M4/M5", "combinações válidas de Result aceitas", valid)
    control("PC-CLEAN-CONTEXT", "M4", "contexto limpo sem estado e contrato de resultado",
            w.audit_clean_context(w.store))
    control("PC-TEMPORAL", "M6", "identidade temporal (32 datas, virada de mês, YTD)", w.audit_temporal(w.store))
    for day in integrated.REEXECUTE:
        control(f"PC-REEXECUTION-{day.isoformat()}", "M7", "mesma janela -> mesma identidade e store",
                reexecution_problems(w, day))
    control("PC-DETERMINISM", "M8", "RUN_A = RUN_B = HASH_SEED_A = HASH_SEED_B = REEXECUTION",
            checks.check_determinism(w.runs))
    control("PC-DIFFERENTIAL", "M9", "7877551 x HEAD sem mutação",
            differential.evaluate(w.differential["reference"], w.differential["candidate"])["problems"]
            + w.differential["problems"])
    control("PC-PROVENANCE", "M10", "registro persistente, 16 pendências, fixture em memória, rótulo",
            w.audit_provenance())
    return controls


# ============================================================== artefatos protegidos
PROTECTED_OK = ("NO PRODUCTION CHANGES", "AUTHORIZED TAXONOMY MIGRATION (D-TAX-01)")


def protected_artifacts() -> dict:
    diff = git("diff", "--stat", BASELINE, "--", "app", "data", "tools").decode()
    status = git("status", "--porcelain", "--", "app", "data", "tools").decode()
    taxonomy = taxonomy_guard.classify_git(BASELINE)
    if not diff and not status:
        result = PROTECTED_OK[0]
    elif taxonomy["taxonomy_only"]:          # única exceção: diff provadamente taxonômico
        result = PROTECTED_OK[1]
    else:
        result = "PRODUCTION CHANGED"
    return {"baseline": BASELINE, "diff_vs_baseline_app_data_tools": diff, "working_tree_app_data_tools": status,
            "taxonomy_guard": {k: taxonomy[k] for k in ("files", "problems", "taxonomy_only")}, "result": result}


def persisted_links_status(world) -> str:
    persisted = (fixture.SEED / "interblock_links.json").read_bytes()
    if persisted == world.baseline_links:
        return "EQUAL_TO_BASELINE"
    verdict = taxonomy_guard.classify({"data/seed/interblock_links.json": (world.baseline_links, persisted)})
    return "AUTHORIZED_TAXONOMY_MIGRATION" if verdict["taxonomy_only"] else "CHANGED"


# ============================================================== execução
def main() -> int:
    world = World()
    results = []
    for m in MUTATIONS:
        outcome = m["run"](world)
        actual = codes(outcome["problems"])
        detected = m["expected_detection"] in actual
        results.append({"mutation_id": m["mutation_id"], "contract": m["contract"],
                        "expected_detection": m["expected_detection"], "actual_detection": "|".join(actual),
                        "detected": "TRUE" if detected else "FALSE",
                        "rejected": "TRUE" if outcome["problems"] else "FALSE",
                        "before": json.dumps(outcome["before"], ensure_ascii=False, default=str),
                        "after": json.dumps(outcome["after"], ensure_ascii=False, default=str),
                        "detection_mechanism": m["detection_mechanism"], "production_code_touched": "NO",
                        "result": "PASS" if detected else "FAIL",
                        "problems_sample": " || ".join(outcome["problems"][:2])[:400]})
    controls = positive_controls(world)
    protected = protected_artifacts()
    by_contract = {}
    for r in results:
        c = by_contract.setdefault(r["contract"], {"defined": 0, "detected": 0})
        c["defined"] += 1
        c["detected"] += r["detected"] == "TRUE"
    detected = sum(r["detected"] == "TRUE" for r in results)
    summary = {
        "stage": "3.4D", "baseline": BASELINE, "label": fixture.LABEL,
        "mutations_defined": len(MUTATIONS), "mutations_executed": len(results),
        "mutations_detected": detected, "mutations_missed": len(results) - detected,
        "detection_rate": f"{100 * detected / len(results):.1f}%",
        "by_contract": by_contract,
        "real_path": {kind: sum(1 for m in MUTATIONS if m["real_path"] == kind)
                      for kind in sorted({m["real_path"] for m in MUTATIONS})},
        "synthetic_only_mutations": 0,
        "positive_controls": {"total": len(controls), "accepted": sum(c["result"] == "ACCEPT" for c in controls),
                              "rejected_unexpectedly": [c["control_id"] for c in controls if c["result"] != "ACCEPT"]},
        "fixture": {"REAL_DERIVED": "TEST_FIXTURE_ONLY",
                    "official_pending_links": len(world.official.catalog.links.pending()),
                    "fixture_pending_links": len(world.orchestrator.catalog.links.pending()),
                    "fixture_graph_hash": fixture.graph_hash(world.orchestrator),
                    "persisted_links_status": persisted_links_status(world)},
        "unmutated_baselines": {"differential_problems": world.differential["problems"],
                                "differential_candidate_cases": len(world.differential["candidate"]["cases"]),
                                "integrated_fingerprint_RUN_A": world.runs["RUN_A"]["results_sha256"]},
        "protected_artifacts": protected,
        "missed": [r["mutation_id"] for r in results if r["detected"] != "TRUE"],
    }
    code_rows = []
    if "--skip-code-mutants" not in sys.argv[1:]:
        import code_mutants
        code_summary, code_rows = code_mutants.run_all()
        summary["code_mutants"] = code_summary
    else:
        summary["code_mutants"] = "SKIPPED (--skip-code-mutants)"
    code_ok = not code_rows or (summary["code_mutants"]["surviving"] == 0
                                and summary["code_mutants"]["positive_control"]["result"] == "ACCEPT"
                                and summary["code_mutants"]["repository_untouched"])
    ok = (code_ok and summary["mutations_missed"] == 0 and not summary["positive_controls"]["rejected_unexpectedly"]
          and protected["result"] in PROTECTED_OK and summary["fixture"]["official_pending_links"] == 16
          and summary["fixture"]["persisted_links_status"] in ("EQUAL_TO_BASELINE", "AUTHORIZED_TAXONOMY_MIGRATION"))
    summary["result"] = "PASS" if ok else "FAIL"

    if "--no-write" not in sys.argv[1:]:
        matrix_fields = ["mutation_id", "contract", "mutation_description", "mutation_point", "artifact", "field",
                         "expected_detection", "detection_mechanism", "real_path", "production_code_touched"]
        with (HERE / "mutation_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=matrix_fields, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(MUTATIONS)
        with (HERE / "mutation_results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(results)
        with (HERE / "positive_controls.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(controls[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows([{**c, "problems": " || ".join(c["problems"])} for c in controls])
        if code_rows:
            with (HERE / "code_mutation_results.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(code_rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(code_rows)
        (HERE / "mutation_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n",
                                                    encoding="utf-8")
    print(json.dumps({"summary": summary, "code_mutants": [{k: r[k] for k in ("mutant_id", "detected_by", "result")}
                                                            for r in code_rows], "results": [{k: r[k] for k in ("mutation_id", "expected_detection",
                                                                         "actual_detection", "result")}
                                                      for r in results]}, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
