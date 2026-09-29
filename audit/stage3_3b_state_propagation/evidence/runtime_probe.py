"""
Etapa 3.3B — sonda de caixa-preta da propagação de estado (subprocesso).

Chamada por `analysis_stage3_3b.py`, que não importa o runtime. Recebe em
stdin uma lista de comandos e devolve em stdout as observações. Usa só a
API pública (Result, CalculationContext, InterblockExecutionOrchestrator).
Nenhuma expectativa é calculada aqui.

Comandos:
    run     executa `targets` no modo official/derived com entradas
            genéricas (numérico 1.0 + 0.01*i + 0.001*k; categórico = o
            valor pedido ou o primeiro de allowed_values) e as
            `overrides` [var, scope_type, scope_value, period, value,
            state, detail] gravadas por set_variable_result. Devolve o
            código de erro (ou None), os passos do plano, as entradas
            requeridas e todo o contexto final.
    plans   passos do plano oficial por alvo (topologia).
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
        ([k.entity_id, k.scope_type, k.scope_value, k.period_id, r.value, r.state, r.detail]
         for k, r in context._scoped_results.items()),
        key=lambda row: json.dumps(row, default=str),
    )


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
            orchestrator.seed_parameters(context)
            resolver = TimePeriodResolver()
            categorical = command.get("categorical", {})
            for i, variable in enumerate(plan.required_inputs):
                d = orchestrator.catalog.variable_definitions.get(variable)
                period = resolver.effective_window(d.frequency, run_date).period_id
                for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
                    if d.is_categorical:
                        value = categorical.get(f"{variable}@{sv}", d.allowed_values[0])
                    else:
                        value = 1.0 + 0.01 * i + 0.001 * k
                    context.set_variable_value(variable, value, st, sv, period)
            for variable, st, sv, period, value, state, detail in command.get("overrides", []):
                context.set_variable_result(variable, Result(value, state, detail), st, sv, period)
            orchestrator.execute(plan, context, run_date)
        except Exception as error:  # noqa: BLE001
            record["code"] = code_of(error)
            record["error_type"] = type(error).__name__
            record["error_bases"] = [c.__name__ for c in type(error).__mro__]
        for variable, st, sv, period in command.get("scalar_reads", []):
            try:
                record["scalar_reads"].append(["OK", context.get_variable_value(variable, st, sv, period)])
            except Exception as error:  # noqa: BLE001
                record["scalar_reads"].append(["ERR", code_of(error)])
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
