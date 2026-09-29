"""
Etapa 3.3C — sonda de caixa-preta da agregação consciente de Result.

Chamada por `analysis_stage3_3c.py` (que não importa o runtime). Usa só
APIs públicas: Result, CalculationContext, AggregationRule,
TemporalAggregationService.aggregate e InterblockExecutionOrchestrator.
Não chama a função de composição diretamente e não calcula expectativas.

Comandos:
    aggregate  uma regra (tipo, integration_factor, janela explícita
               opcional) sobre uma série diária de Results
               [value, state, detail] (e pesos, na WEIGHTED_AVERAGE);
               devolve ["OK", value, state, detail] ou ["ERR", código].
    chain      seeds reais (REAL_DERIVED): só os passos AGGREGATION e
               TRANSFER do plano de `target`, em várias datas no MESMO
               contexto; por passo, os Results de origem de cada
               instância; devolve códigos, status das transferências e
               o contexto final com a identidade completa.
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.domain.forecast.aggregation import AggregationRule  # noqa: E402
from app.domain.interblock.registry import InterblockLinkRegistry  # noqa: E402
from app.domain.results import Result  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)
from app.engine.temporal_aggregation_service import TemporalAggregationService  # noqa: E402

SEED = REPO / "data" / "seed"


def code_of(error):
    return getattr(error, "code", type(error).__name__)


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

    if kind == "aggregate":
        extra = {}
        if command.get("integration_factor", 1) != 1:
            extra["integration_factor"] = command["integration_factor"]
        if command["type"] == "WEIGHTED_AVERAGE":
            extra["weight_variable_id"] = "VAR19993"
        if command.get("window"):
            extra["window_start_date"] = date.fromisoformat(command["window"][0])
            extra["window_end_date"] = date.fromisoformat(command["window"][1])
        rule = AggregationRule(
            aggregation_rule_id="AGR-AUDIT", source_variable_id="VAR19991", source_frequency="diário",
            target_variable_id="VAR19992", target_frequency="mensal", aggregation_type=command["type"], **extra,
        )
        context = CalculationContext(categorical_variable_ids=["VAR19991"])
        try:
            for day, (value, state, detail) in zip(command["days"], command["sources"]):
                context.set_variable_result("VAR19991", Result(value, state, detail), "linha", "L1", day)
            for day, (value, state, detail) in zip(command["days"], command.get("weights") or []):
                context.set_variable_result("VAR19993", Result(value, state, detail), "linha", "L1", day)
            fv = TemporalAggregationService().aggregate(
                rule, context, "linha", "L1", date.fromisoformat(command["run_date"]))
            out[cid] = ["OK", fv.value, fv.state, fv.detail, fv.result.value, fv.result.state, fv.result.detail]
        except Exception as error:  # noqa: BLE001
            out[cid] = ["ERR", code_of(error), [c.__name__ for c in type(error).__mro__]]

    elif kind == "chain":
        orchestrator = real_derived()
        plan = orchestrator.plan([command["target"]])
        steps = tuple(s for s in plan.steps if s.kind in ("AGGREGATION", "TRANSFER"))
        partial = type(plan)(plan.targets, steps, ())
        agg = next(s for s in steps if s.kind == "AGGREGATION")
        instances = sorted(
            (i for i in orchestrator.catalog.aggregation_rule_instances.all()
             if i.rule.aggregation_rule_id == agg.node_id),
            key=lambda i: (i.scope_type or "", i.scope_value or ""),
        )
        rule = instances[0].rule
        link = orchestrator.catalog.links.link_for(command["target"])
        context = CalculationContext()
        record = {"steps": [s.key for s in steps], "rule": [rule.aggregation_rule_id, rule.aggregation_type,
                  rule.source_variable_id, rule.target_variable_id, rule.target_frequency],
                  "link": [link.source_definition_id, command["target"], [list(i) for i in link.instances]],
                  "instances": [[i.scope_type, i.scope_value] for i in instances], "runs": []}
        for step in command["steps"]:
            for day, series in step.get("sources", {}).items():
                for k, inst in enumerate(instances):
                    value, state, detail = series
                    value = None if value is None else value + k
                    context.set_variable_result(rule.source_variable_id, Result(value, state, detail),
                                                inst.scope_type, inst.scope_value, day)
            run = {"run_date": step["run_date"], "code": None, "transfers": []}
            try:
                trace = orchestrator.execute(partial, context, date.fromisoformat(step["run_date"]))
                run["transfers"] = sorted(
                    [e.node_id, e.scope_type, e.scope_value, e.period_id, e.status, e.value, e.state, e.detail]
                    for e in trace.events if e.kind == "TRANSFER")
            except Exception as error:  # noqa: BLE001
                run["code"] = code_of(error)
            record["runs"].append(run)
        record["context"] = sorted(
            ([k.entity_id, k.scope_type, k.scope_value, k.period_id, k.window_end, r.value, r.state, r.detail]
             for k, r in context._scoped_results.items()),
            key=lambda row: json.dumps(row, default=str),
        )
        out[cid] = record

json.dump(out, sys.stdout, default=str, sort_keys=True)
