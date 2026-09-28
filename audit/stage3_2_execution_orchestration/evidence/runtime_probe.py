"""
Etapa 3.2 — sonda de caixa-preta do orquestrador (subprocesso).

Chamada por `analysis_stage3_2.py`, que NÃO importa o runtime. Lê em
stdin {"mode": "official"|"real_derived", "plan_targets": [...],
"executions": [{"targets": [...], "inputs": [[id, st, sv, period, value]...]}],
"blocked_executions": [[target]...]} e devolve em stdout:

    plans       alvo -> {"status": OK|<código>, "source_block", "steps"}
    executions  eventos do trace + chaves gravadas no contexto
    blocked     alvo -> código do erro e número de chaves escritas

`real_derived` (SINTÉTICO documentado): pendências tratadas como
entradas livres, só nesta sonda — para exercitar as cadeias reais.
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.domain.interblock.registry import InterblockLinkRegistry  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.exceptions import InterblockRuntimeError  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)

SEED = REPO / "data" / "seed"
request = json.load(sys.stdin)
catalog = ExecutionCatalog.from_seed_root(SEED)
if request["mode"] == "real_derived":
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
orchestrator = InterblockExecutionOrchestrator(catalog)
run_date = date.fromisoformat(request["run_date"])

plans = {}
for target in request.get("plan_targets", []):
    try:
        plan = orchestrator.plan([target])
        plans[target] = {"status": "OK", "steps": [s.key for s in plan.steps],
                         "inputs": list(plan.required_inputs)}
    except InterblockRuntimeError as error:
        plans[target] = {"status": error.code, "source_block": error.details.get("source_block")}

executions = []
for execution in request.get("executions", []):
    context = CalculationContext()
    orchestrator.seed_parameters(context)
    for entity_id, scope_type, scope_value, period_id, value in execution["inputs"]:
        context.set_variable_value(entity_id, value, scope_type, scope_value, period_id)
    trace = orchestrator.execute(execution["targets"], context, run_date)
    executions.append({
        "targets": execution["targets"],
        "steps": trace.step_order,
        "events": [[e.step, e.kind, e.node_id, e.block, e.variable_id, e.scope_type, e.scope_value,
                    e.period_id, e.value, e.status, e.source_block, e.source_variable_id]
                   for e in trace.events],
        "context": sorted([k.entity_id, k.scope_type, k.scope_value, k.period_id, v]
                          for k, v in context._scoped_variables.items()),
    })

blocked = {}
for target in request.get("blocked_executions", []):
    context = CalculationContext()
    before = len(context._scoped_variables)
    try:
        orchestrator.execute([target], context, run_date)
        blocked[target] = {"code": "NO_ERROR", "written": len(context._scoped_variables) - before}
    except InterblockRuntimeError as error:
        blocked[target] = {"code": error.code, "source_block": error.details.get("source_block"),
                           "written": len(context._scoped_variables) - before}

json.dump({"plans": plans, "executions": executions, "blocked": blocked}, sys.stdout, default=str)
