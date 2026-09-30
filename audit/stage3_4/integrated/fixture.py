"""
Stage 3.4C — fixture REAL_DERIVED (TEST_FIXTURE_ONLY, DR-2) e entradas.

REAL_DERIVED: catálogo oficial carregado dos seeds; o registro de vínculos
é reconstruído EM MEMÓRIA a partir de `interblock_links.json` com
`pending = []`, de modo que as variáveis consumidoras dos 16 vínculos
pendentes viram entradas livres do plano. Nada é escrito em disco; seeds,
links e proveniência não mudam; nenhum bloco ausente é "carregado". Todo
resultado obtido aqui é REAL_DERIVED_TEST_RESULT.

É a mesma receita de `tests/test_stage3_2_execution_orchestration.py::
real_derived_orchestrator` (o hash do grafo é comparado com o dele).

ORDER_B: o MESMO conteúdo com ordem de inserção invertida em todos os
registros do catálogo (variáveis, equações, instâncias de agregação,
parâmetros, `block_of`), na lista de vínculos e na ordem dos blocos
passados ao registro de vínculos. O planner não é alterado.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import AggregationRuleInstanceRegistry
from app.domain.interblock.registry import InterblockLinkRegistry
from app.domain.parameters.registry import ParameterInstanceRegistry
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.interblock_orchestrator import ExecutionCatalog, InterblockExecutionOrchestrator
from app.engine.scope_resolver import ScopeResolver
from app.engine.time_period_resolver import TimePeriodResolver

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "data" / "seed"
OFFICIAL_BLOCKS = ("production", "yield", "energy", "max_ht")
LABEL = "REAL_DERIVED_TEST_RESULT"


def _links(order: str) -> InterblockLinkRegistry:
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []                                    # só em memória (fixture)
    blocks = list(payload["workbooks"])
    if order == "B":
        payload["links"] = list(reversed(payload["links"]))
        blocks = list(reversed(blocks))
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in blocks}
    return InterblockLinkRegistry.from_payload(payload, raw)


def _reversed(registry, factory):
    rebuilt = factory()
    for item in reversed(list(registry.all())):
        rebuilt.add(item)
    return rebuilt


def build(order: str = "A") -> InterblockExecutionOrchestrator:
    catalog = ExecutionCatalog.from_seed_root(SEED)
    catalog.links = _links(order)
    if order == "B":
        catalog = ExecutionCatalog(
            _reversed(catalog.variable_definitions, VariableDefinitionRegistry),
            _reversed(catalog.equation_definitions, EquationDefinitionRegistry),
            _reversed(catalog.aggregation_rule_instances, AggregationRuleInstanceRegistry),
            _reversed(catalog.parameter_instances, ParameterInstanceRegistry),
            catalog.links,
            dict(reversed(list(catalog.block_of.items()))),
        )
    return InterblockExecutionOrchestrator(catalog)


def graph_hash(orchestrator: InterblockExecutionOrchestrator) -> str:
    """Hash do grafo lógico: nós (tipo, id, bloco, produz, depende), vínculos, pendências."""
    links = orchestrator.catalog.links
    canonical = {
        "nodes": sorted([k, n.block, sorted(n.produces), sorted(orchestrator._deps[k])]
                        for k, n in orchestrator._nodes.items()),
        "links": sorted([link.consumer_block, link.consumer_definition_id, link.source_block, link.source_definition_id,
                         link.frequency, sorted(map(list, link.instances))] for link in links.links()),
        "pending": sorted([p.consumer_definition_id, p.source_block] for p in links.pending()),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def input_value(i: int, k: int, frequency: str, day: date) -> float:
    """
    Entrada determinística da variável de índice i (ordem de `required_inputs`)
    no escopo de índice k. Só as entradas DIÁRIAS dependem do dia; mensais e
    anuais dependem apenas do período (reexecução reproduz as mesmas entradas).
    """
    value = 1.0 + 0.01 * i + 0.001 * k
    if frequency == "diário":
        value += 0.0001 * day.timetuple().tm_yday
    return value


def seed_inputs(orchestrator, plan, context: CalculationContext, day: date) -> None:
    orchestrator.seed_parameters(context)
    periods = TimePeriodResolver()
    for i, variable_id in enumerate(plan.required_inputs):
        definition = orchestrator.catalog.variable_definitions.get(variable_id)
        period = periods.effective_window(definition.frequency, day).period_id
        for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value)):
            value = (definition.allowed_values[0] if definition.is_categorical
                     else input_value(i, k, definition.frequency, day))
            context.set_variable_value(variable_id, value, st, sv, period)
