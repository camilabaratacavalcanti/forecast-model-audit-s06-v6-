"""
Etapa 3.3A — sonda de caixa-preta do contrato de resultado (subprocesso).

Chamada por `analysis_stage3_3a.py`, que não importa o runtime. Recebe em
stdin uma lista de comandos e devolve em stdout as observações. Cada
comando exercita a API pública (Result, CalculationContext,
InterblockValueResolver, InterblockExecutionOrchestrator).
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
from app.engine.interblock_resolver import InterblockValueResolver  # noqa: E402
from app.repositories.seed_loader import SeedLoader  # noqa: E402

SEED = REPO / "data" / "seed"


def code_of(error):
    return getattr(error, "code", type(error).__name__)


def triple(result):
    return [result.value, type(result.value).__name__, result.state, result.detail]


def official():
    return InterblockExecutionOrchestrator.from_seed_root(SEED)


def real_derived():
    catalog = ExecutionCatalog.from_seed_root(SEED)
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    return InterblockExecutionOrchestrator(catalog)


out = {}
for command in json.load(sys.stdin):
    kind, cid = command["kind"], command["id"]

    if kind == "construct":
        try:
            out[cid] = ["OK", triple(Result(*command["args"]))]
        except Exception as error:  # noqa: BLE001
            out[cid] = ["ERR", code_of(error)]

    elif kind == "context_roundtrip":
        context = CalculationContext()
        if command.get("declare"):
            definitions = SeedLoader(SEED).load_variable_definitions()
            context.declare_variable_definitions([definitions.get(v) for v in command["declare"]])
        rows = []
        for variable, st, sv, period, args in command["writes"]:
            try:
                context.set_variable_result(variable, Result(*args), st, sv, period)
                rows.append(["OK"])
            except Exception as error:  # noqa: BLE001
                rows.append(["ERR", code_of(error)])
        reads = []
        for variable, st, sv, period in command["reads"]:
            try:
                reads.append(triple(context.get_variable_result(variable, st, sv, period)))
            except Exception as error:  # noqa: BLE001
                reads.append(["ERR", code_of(error)])
        out[cid] = {"writes": rows, "reads": reads}

    elif kind == "transfer":
        registry = SeedLoader(SEED).load_interblock_links()
        context = CalculationContext()
        for variable, st, sv, period, args in command["writes"]:
            context.set_variable_result(variable, Result(*args), st, sv, period)
        resolver = InterblockValueResolver(registry, context)
        errors = []
        for consumer, st, sv, period in command["transfers"]:
            try:
                resolver.transfer_result(consumer, st, sv, period)
            except Exception as error:  # noqa: BLE001
                errors.append([consumer, st, sv, code_of(error)])
        out[cid] = {
            "errors": errors,
            "context": sorted(
                ([k.entity_id, k.scope_type, k.scope_value, k.period_id, *triple(r)]
                 for k, r in context._scoped_results.items()),
                key=lambda row: json.dumps(row, default=str),
            ),
        }

    elif kind == "plans":
        orchestrator = official() if command["mode"] == "official" else real_derived()
        plans = {}
        for target in command["targets"]:
            try:
                plans[target] = ["OK", [s.key for s in orchestrator.plan([target]).steps]]
            except Exception as error:  # noqa: BLE001
                plans[target] = [code_of(error), error.details.get("source_block") if hasattr(error, "details") else None]
        out[cid] = plans

    elif kind == "blocked_execution":
        orchestrator = official()
        results = {}
        for target in command["targets"]:
            context = CalculationContext()
            try:
                orchestrator.execute([target], context, date.fromisoformat(command["run_date"]))
                results[target] = ["NO_ERROR", len(context._scoped_results)]
            except Exception as error:  # noqa: BLE001
                results[target] = [code_of(error), len(context._scoped_results)]
        out[cid] = results

json.dump(out, sys.stdout, default=str, sort_keys=True)
