"""
Etapa 3.3B — sonda de caixa-preta da propagação de estado e da identidade
temporal (subprocesso).

Chamada por `analysis_stage3_3b.py`, que não importa o runtime. Recebe em
stdin uma lista de comandos e devolve em stdout as observações. Usa só a
API pública (Result, CalculationContext, InterblockExecutionOrchestrator).
Nenhuma expectativa é calculada aqui.

Comandos:
    run        executa `targets` (official/derived) numa data, com
               entradas genéricas e `overrides` [var, scope_type,
               scope_value, period, value, state, detail].
    sequence   várias execuções no MESMO contexto (`steps`: run_date +
               overrides); por passo: código de erro e status das
               transferências; ao final, o contexto inteiro.
    construct  constrói Result(*args) e tenta gravá-lo no contexto.
    plans      passos do plano oficial por alvo (topologia).

Entradas genéricas: numérico = 1.0 + 0.01*i + 0.001*k (+ 0.1*dia para
frequência diária, para que janelas diferentes tenham valores
diferentes); categórico = valor pedido ou o primeiro de allowed_values.
O contexto é despejado com a identidade completa
[variável, scope_type, scope_value, period_id, window_end, value, state, detail].
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.domain.interblock.registry import InterblockLinkRegistry  # noqa: E402
from app.domain.results import Result  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)
from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.time_period_resolver import TimePeriodResolver  # noqa: E402

SEED = REPO / "data" / "seed"


def code_of(error):
    return getattr(error, "code", type(error).__name__)


def official():
    return InterblockExecutionOrchestrator.from_seed_root(SEED)


def real_derived():
    catalog = ExecutionCatalog.from_seed_root(SEED)
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    return InterblockExecutionOrchestrator(catalog)


def dump(context):
    return sorted(
        ([k.entity_id, k.scope_type, k.scope_value, k.period_id, getattr(k, "window_end", None),
          r.value, r.state, r.detail]
         for k, r in context._scoped_results.items()),
        key=lambda row: json.dumps(row, default=str),
    )


def set_inputs(orchestrator, plan, context, run_date, categorical):
    orchestrator.seed_parameters(context)
    resolver = TimePeriodResolver()
    for i, variable in enumerate(plan.required_inputs):
        d = orchestrator.catalog.variable_definitions.get(variable)
        period = resolver.effective_window(d.frequency, run_date).period_id
        day_offset = 0.1 * run_date.day if d.frequency == "diário" else 0.0
        for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
            if d.is_categorical:
                value = categorical.get(f"{variable}@{sv}", d.allowed_values[0])
            else:
                value = 1.0 + 0.01 * i + 0.001 * k + day_offset
            context.set_variable_value(variable, value, st, sv, period)


def apply_overrides(context, overrides):
    for variable, st, sv, period, value, state, detail in overrides:
        context.set_variable_result(variable, Result(value, state, detail), st, sv, period)


def failure(record, error):
    record["code"] = code_of(error)
    record["error_type"] = type(error).__name__
    record["error_bases"] = [c.__name__ for c in type(error).__mro__]


out = {}
for command in json.load(sys.stdin):
    kind, cid = command["kind"], command["id"]

    if kind == "run":
        orchestrator = official() if command["mode"] == "official" else real_derived()
        run_date = date.fromisoformat(command["run_date"])
        context = CalculationContext()
        context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
        record = {"code": None, "steps": [], "required_inputs": [], "scalar_reads": []}
        try:
            plan = orchestrator.plan(command["targets"])
            record["steps"] = [s.key for s in plan.steps]
            record["required_inputs"] = list(plan.required_inputs)
            set_inputs(orchestrator, plan, context, run_date, command.get("categorical", {}))
            apply_overrides(context, command.get("overrides", []))
            orchestrator.execute(plan, context, run_date)
        except Exception as error:  # noqa: BLE001
            failure(record, error)
        for variable, st, sv, period in command.get("scalar_reads", []):
            try:
                record["scalar_reads"].append(["OK", context.get_variable_value(variable, st, sv, period)])
            except Exception as error:  # noqa: BLE001
                record["scalar_reads"].append(["ERR", code_of(error)])
        record["context"] = dump(context)
        out[cid] = record

    elif kind == "sequence":
        orchestrator = official() if command["mode"] == "official" else real_derived()
        context = CalculationContext()
        context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
        plan = orchestrator.plan(command["targets"])
        record = {"steps": [s.key for s in plan.steps], "runs": []}
        for step in command["steps"]:
            run_date = date.fromisoformat(step["run_date"])
            run = {"run_date": step["run_date"], "code": None, "transfers": []}
            try:
                set_inputs(orchestrator, plan, context, run_date, {})
                apply_overrides(context, step.get("overrides", []))
                trace = orchestrator.execute(plan, context, run_date)
                run["transfers"] = sorted(
                    [e.node_id, e.scope_type, e.scope_value, e.period_id, e.status]
                    for e in trace.events if e.kind == "TRANSFER"
                )
            except Exception as error:  # noqa: BLE001
                failure(run, error)
            record["runs"].append(run)
        record["context"] = dump(context)
        out[cid] = record

    elif kind == "construct":
        record = {}
        try:
            result = Result(*command["args"])
            record["construct"] = ["OK", [result.value, result.state, result.detail]]
        except Exception as error:  # noqa: BLE001
            record["construct"] = ["ERR", code_of(error)]
        context = CalculationContext()
        try:
            context.set_variable_result("VAR12031", Result(*command["args"]), "linha", "L1", "2026-09-01")
            record["write"] = ["OK"]
        except Exception as error:  # noqa: BLE001
            record["write"] = ["ERR", code_of(error)]
        record["context"] = dump(context)
        out[cid] = record

    elif kind == "plans":
        orchestrator = official()
        plans = {}
        for target in command["targets"]:
            try:
                plans[target] = ["OK", [s.key for s in orchestrator.plan([target]).steps]]
            except Exception as error:  # noqa: BLE001
                plans[target] = [code_of(error), None]
        out[cid] = plans

json.dump(out, sys.stdout, default=str, sort_keys=True)
