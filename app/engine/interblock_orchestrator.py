"""
Execução coordenada interbloco em runtime (Etapa 3.2).

    executar produtor -> produzir resultado -> transferir pelo vínculo
    -> gravar no ID do consumidor -> executar consumidor

Grafo de execução em nível de DEFINIÇÃO, construído só a partir dos
seeds e do artefato canônico `interblock_links.json` (nunca XLSX, nunca
`fonte`). Nós:

    EQUATION     uma EquationDefinition — executada pelo ForecastEngine
                 existente (materialização de instâncias, período pela
                 frequência do alvo + run_date, gravação no contexto);
    AGGREGATION  uma AggregationRule — executada, instância a instância,
                 pelo TemporalForecastOrchestrator/TemporalAggregation-
                 Service existentes; o resultado é gravado no contexto na
                 chave (alvo, escopo, period_id do ForecastValue);
    TRANSFER     um vínculo canônico válido — executado pelo
                 InterblockValueResolver da Etapa 3.1 (instância exata,
                 período da frequência do vínculo, sem fallback, sem
                 conversão, conflito explícito).

Arestas produtor -> consumidor:

    referência de equação a uma variável  <- nós que a produzem
    agregação                              <- nós que produzem origem/peso
    transferência                          <- nós que produzem o produtor
    variável consumidora de vínculo        <- SÓ o nó TRANSFER do vínculo

Uma cadeia area_41 <- yield <- production vira, portanto,
EQUATION(production) -> TRANSFER(yield) -> [EQUATIONs de yield] ->
TRANSFER(area_41) -> [EQUATIONs de area_41]; não existe aresta
production -> area_41.

Por que não em nível de bloco: production e yield dependem um do outro
como blocos (production.yield <- yield.yield; yield.lth <- production.lth)
sem ciclo entre definições. A ordem entre blocos seria um ciclo falso; a
ordem entre definições é um DAG (verificado pela Etapa 2.6).

Ordem: Kahn com fila ordenada pelo identificador do nó — determinística
e independente da ordem de carga de blocos, vínculos, dicionários ou
PYTHONHASHSEED. Ciclo é erro explícito, com o caminho completo.

Planejamento antes da execução: um alvo cujo fecho depende de uma
variável consumidora de vínculo PENDENTE (bloco oficial não carregado)
falha com INTERBLOCK_SOURCE_NOT_LOADED antes de qualquer cálculo — nada
é executado parcialmente, nenhum valor é inventado. Um vínculo
REJEITADO falha com INTERBLOCK_LINK_REJECTED.

Entradas livres (variáveis sem equação, sem agregação e sem vínculo) e
parâmetros são fornecidos pelo chamador no CalculationContext, como no
runtime existente; o plano os lista em `required_inputs`.

Extensão futura (Etapa 3.3+): os nós carregam apenas identidade e
dependências; o resultado de cada passo fica no CalculationContext e o
rastro (ExecutionTrace) registra eventos. Um valor enriquecido
(value/state/detail) pode ser introduzido no contexto e no trace sem
mudar o planejamento nem a ordem.
"""

from __future__ import annotations

import heapq
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.interblock.registry import InterblockLinkRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.equation_selector import EquationSelector
from app.engine.exceptions import (
    InterblockExecutionCycleError,
    InterblockExecutionPlanError,
    InterblockLinkRejectedError,
    InterblockSourceNotLoadedError,
    VariableNotFoundError,
)
from app.engine.forecast_engine import ForecastEngine
from app.engine.interblock_resolver import InterblockValueResolver
from app.engine.temporal_forecast_orchestrator import TemporalForecastOrchestrator
from app.engine.time_period_resolver import TimePeriodResolver
from app.repositories.seed_loader import SeedLoader


EQUATION = "EQUATION"
AGGREGATION = "AGGREGATION"
TRANSFER = "TRANSFER"

_REFERENCE = re.compile(r"\b(VAR\d+)")


@dataclass(frozen=True)
class ExecutionNode:
    kind: str
    node_id: str  # equation_definition_id | aggregation_rule_id | consumer_definition_id
    block: str
    produces: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.node_id}"


@dataclass(frozen=True)
class PendingBlocker:
    """Variável consumidora de vínculo pendente necessária ao plano."""

    consumer_definition_id: str
    consumer_block: str
    consumer_name: str
    source_block: str
    required_by: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    targets: tuple[str, ...]
    steps: tuple[ExecutionNode, ...]
    required_inputs: tuple[str, ...]
    # Preenchido só no modo diagnóstico (`plan(..., on_pending="report")`);
    # um plano com bloqueios nunca é executado.
    pending_blockers: tuple[PendingBlocker, ...] = ()

    @property
    def blocks(self) -> tuple[str, ...]:
        seen = []
        for step in self.steps:
            if step.block not in seen:
                seen.append(step.block)
        return tuple(seen)


@dataclass(frozen=True)
class ExecutionEvent:
    step: int
    kind: str
    node_id: str
    block: str
    variable_id: str
    scope_type: str | None
    scope_value: str | None
    period_id: str | None
    value: object
    status: str  # WRITTEN | UNCHANGED
    source_block: str | None = None  # TRANSFER: bloco e variável lidos
    source_variable_id: str | None = None


@dataclass
class ExecutionTrace:
    run_date: date
    plan: ExecutionPlan
    events: list[ExecutionEvent] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[ExecutionEvent]:
        return [e for e in self.events if e.kind == kind]

    @property
    def step_order(self) -> list[str]:
        return [step.key for step in self.plan.steps]


class ExecutionCatalog:
    """
    Tudo o que o planejador precisa, lido dos seeds: definições (via
    SeedLoader), pertencimento de cada ID ao bloco (arquivos
    `data/seed/<bloco>/…json`) e vínculos canônicos.
    """

    def __init__(
        self,
        variable_definitions,
        equation_definitions: EquationDefinitionRegistry,
        aggregation_rule_instances,
        parameter_instances,
        links: InterblockLinkRegistry,
        block_of: dict[str, str],
    ):
        self.variable_definitions = variable_definitions
        self.equation_definitions = equation_definitions
        self.aggregation_rule_instances = aggregation_rule_instances
        self.parameter_instances = parameter_instances
        self.links = links
        self.block_of = block_of

    @classmethod
    def from_seed_root(cls, seed_root: str | Path) -> "ExecutionCatalog":
        seed_root = Path(seed_root)
        loader = SeedLoader(seed_root)
        links = loader.load_interblock_links()
        block_of: dict[str, str] = {}

        for block in links.loaded_blocks:
            for name, key in (
                ("variables", "variable_id"),
                ("equations", "equation_id"),
                ("aggregation_rules", "aggregation_rule_id"),
            ):
                for record in json.loads(
                    (seed_root / block / f"{name}.json").read_text(encoding="utf-8")
                ):
                    block_of[record[key]] = block

        return cls(
            variable_definitions=loader.load_variable_definitions(),
            equation_definitions=loader.load_equation_definitions(),
            aggregation_rule_instances=loader.load_aggregation_rule_instances(),
            parameter_instances=loader.load_parameter_instances(),
            links=links,
            block_of=block_of,
        )


class InterblockExecutionOrchestrator:
    def __init__(
        self,
        catalog: ExecutionCatalog,
        forecast_engine: ForecastEngine | None = None,
        temporal_orchestrator: TemporalForecastOrchestrator | None = None,
        time_period_resolver: TimePeriodResolver | None = None,
    ):
        self.catalog = catalog
        self.forecast_engine = forecast_engine or ForecastEngine()
        self.temporal_orchestrator = temporal_orchestrator or TemporalForecastOrchestrator(
            forecast_engine=self.forecast_engine
        )
        self.time_period_resolver = time_period_resolver or TimePeriodResolver()
        self._nodes, self._producers, self._deps = self._build_graph()

    @classmethod
    def from_seed_root(cls, seed_root: str | Path) -> "InterblockExecutionOrchestrator":
        return cls(ExecutionCatalog.from_seed_root(seed_root))

    # --------------------------------------------------------
    # Grafo
    # --------------------------------------------------------

    def _build_graph(self):
        catalog = self.catalog
        nodes: dict[str, ExecutionNode] = {}
        producers: dict[str, set[str]] = {}
        needs: dict[str, set[str]] = {}  # node key -> variáveis de que depende

        for definition in catalog.equation_definitions.all():
            if definition.status not in EquationSelector.ACTIVE_STATUSES:
                continue
            node = ExecutionNode(
                EQUATION, definition.equation_definition_id,
                catalog.block_of[definition.equation_definition_id],
                (definition.target_variable_id,),
            )
            nodes[node.key] = node
            needs[node.key] = set(_REFERENCE.findall(definition.expression))

        rules = {}
        for instance in catalog.aggregation_rule_instances.all():
            rules[instance.rule.aggregation_rule_id] = instance.rule
        for rule_id, rule in rules.items():
            node = ExecutionNode(
                AGGREGATION, rule_id, catalog.block_of[rule_id], (rule.target_variable_id,),
            )
            nodes[node.key] = node
            needs[node.key] = {rule.source_variable_id} | (
                {rule.weight_variable_id} if rule.weight_variable_id else set()
            )

        for link in catalog.links.links():
            node = ExecutionNode(
                TRANSFER, link.consumer_definition_id, link.consumer_block,
                (link.consumer_definition_id,),
            )
            nodes[node.key] = node
            needs[node.key] = {link.source_definition_id}

        for key, node in nodes.items():
            for variable in node.produces:
                producers.setdefault(variable, set()).add(key)

        # Consumidor de vínculo: só a transferência o produz.
        for link in catalog.links.links():
            owners = producers.get(link.consumer_definition_id, set())
            extra = sorted(k for k in owners if not k.startswith(TRANSFER))
            if extra:
                raise InterblockExecutionPlanError(
                    f"{link.consumer_block} {link.consumer_definition_id} é consumidor de "
                    f"vínculo e também é produzido localmente por {extra}: dois produtores.",
                    consumer_definition_id=link.consumer_definition_id,
                )

        return nodes, producers, needs

    def _upstream(self, key: str) -> set[str]:
        result = set()
        for variable in self._deps[key]:
            result |= self._producers.get(variable, set())
        return result

    # --------------------------------------------------------
    # Planejamento
    # --------------------------------------------------------

    def targets_of_blocks(self, blocks) -> list[str]:
        blocks = set(blocks)
        return sorted({
            variable
            for node in self._nodes.values()
            if node.block in blocks
            for variable in node.produces
        })

    def plan(self, targets, on_pending: str = "raise") -> ExecutionPlan:
        """
        Fecho de dependências dos alvos, em ordem topológica.

        on_pending="raise" (padrão): dependência de vínculo pendente é
        INTERBLOCK_SOURCE_NOT_LOADED. on_pending="report": diagnóstico —
        o plano completo é devolvido com `pending_blockers` e não pode
        ser executado.
        """

        if on_pending not in ("raise", "report"):
            raise ValueError(f"on_pending inválido: {on_pending!r}")

        targets = tuple(sorted(set(targets)))
        blockers: dict[str, PendingBlocker] = {}
        links = self.catalog.links
        selected: set[str] = set()
        inputs: set[str] = set()
        stack = [(t, (t,)) for t in reversed(targets)]
        visited: set[str] = set()

        while stack:
            variable, path = stack.pop()
            if variable in visited:
                continue
            visited.add(variable)

            pending = links.pending_for(variable)
            if pending is not None and on_pending == "report":
                blockers.setdefault(variable, PendingBlocker(
                    variable, pending.consumer_block, pending.consumer_name,
                    pending.source_block, tuple(reversed(path)),
                ))
                continue
            if pending is not None:
                raise InterblockSourceNotLoadedError(
                    f"{pending.consumer_block}.{pending.consumer_name} ({variable}) é necessária "
                    f"para {' <- '.join(reversed(path))} e depende do bloco "
                    f"'{pending.source_block}', cujo workbook não está carregado.",
                    consumer_block=pending.consumer_block,
                    consumer_definition_id=variable,
                    consumer_name=pending.consumer_name,
                    source_block=pending.source_block,
                    frequency=pending.consumer_frequency,
                    scope=(pending.consumer_scope_type, pending.consumer_scope_value),
                    required_by=path,
                )
            rejected = links.rejected_for(variable)
            if rejected is not None:
                raise InterblockLinkRejectedError(
                    f"{variable}: vínculo reprovado no build {list(rejected.error_codes)}.",
                    consumer_definition_id=variable,
                    required_by=path,
                )

            owners = self._producers.get(variable)
            if not owners:
                if variable not in self.catalog.block_of:
                    raise InterblockExecutionPlanError(
                        f"{variable} não pertence a nenhum bloco carregado.",
                        variable_id=variable,
                    )
                inputs.add(variable)
                continue

            for key in sorted(owners):
                if key in selected:
                    continue
                selected.add(key)
                for dependency in sorted(self._deps[key]):
                    stack.append((dependency, path + (dependency,)))

        steps = self._order(selected)

        return ExecutionPlan(
            targets=targets,
            steps=steps,
            required_inputs=tuple(sorted(inputs)),
            pending_blockers=tuple(blockers[k] for k in sorted(blockers)),
        )

    def _order(self, selected: set[str]) -> tuple[ExecutionNode, ...]:
        indegree = {key: 0 for key in selected}
        downstream: dict[str, list[str]] = {key: [] for key in selected}

        for key in selected:
            for up in self._upstream(key):
                if up in selected and up != key:
                    indegree[key] += 1
                    downstream[up].append(key)

        ready = [key for key, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        order = []

        while ready:
            key = heapq.heappop(ready)
            order.append(key)
            for down in sorted(downstream[key]):
                indegree[down] -= 1
                if indegree[down] == 0:
                    heapq.heappush(ready, down)

        if len(order) != len(selected):
            remaining = sorted(k for k in selected if k not in order)
            cycle = self._find_cycle(set(remaining))
            raise InterblockExecutionCycleError(
                "ciclo no grafo de execução: " + " -> ".join(
                    f"{self._nodes[k].block}.{k}" for k in cycle
                ),
                cycle=tuple(cycle),
                blocks=tuple(sorted({self._nodes[k].block for k in cycle})),
            )

        return tuple(self._nodes[key] for key in order)

    def _find_cycle(self, keys: set[str]) -> list[str]:
        start = min(keys)
        path, seen = [start], {start: 0}
        current = start
        while True:
            nxt = min(k for k in self._upstream(current) if k in keys)
            if nxt in seen:
                cycle = path[seen[nxt]:] + [nxt]
                return list(reversed(cycle))
            seen[nxt] = len(path)
            path.append(nxt)
            current = nxt

    # --------------------------------------------------------
    # Execução
    # --------------------------------------------------------

    def seed_parameters(self, context: CalculationContext) -> None:
        """Valores de parâmetros dos seeds (ParameterInstance) no contexto."""

        for instance in self.catalog.parameter_instances.all():
            context.set_parameter_instance_value(instance, instance.value)

    def execute(
        self,
        targets_or_plan,
        context: CalculationContext,
        run_date: date,
    ) -> ExecutionTrace:
        plan = targets_or_plan if isinstance(targets_or_plan, ExecutionPlan) else self.plan(targets_or_plan)

        if plan.pending_blockers:
            blocker = plan.pending_blockers[0]
            raise InterblockSourceNotLoadedError(
                f"plano com dependência pendente: {blocker.consumer_block}."
                f"{blocker.consumer_name} ({blocker.consumer_definition_id}) depende do "
                f"bloco '{blocker.source_block}', cujo workbook não está carregado.",
                consumer_block=blocker.consumer_block,
                consumer_definition_id=blocker.consumer_definition_id,
                consumer_name=blocker.consumer_name,
                source_block=blocker.source_block,
                required_by=blocker.required_by,
            )

        trace = ExecutionTrace(run_date=run_date, plan=plan)
        resolver = InterblockValueResolver(self.catalog.links, context)

        for index, node in enumerate(plan.steps):
            if node.kind == EQUATION:
                self._run_equation(index, node, context, run_date, trace)
            elif node.kind == AGGREGATION:
                self._run_aggregation(index, node, context, run_date, trace)
            else:
                self._run_transfer(index, node, resolver, context, run_date, trace)

        return trace

    def _run_equation(self, index, node, context, run_date, trace):
        registry = EquationDefinitionRegistry()
        definition = self.catalog.equation_definitions.get(node.node_id)
        registry.add(definition)
        results = self.forecast_engine.calculate_from_definition_registry(
            equation_definition_registry=registry,
            calculation_context=context,
            variable_definition_registry=self.catalog.variable_definitions,
            run_date=run_date,
        )
        frequency = self.catalog.variable_definitions.get(definition.target_variable_id).frequency
        period_id = self.time_period_resolver.effective_window(frequency, run_date).period_id
        for instance_id in sorted(results):
            instance = next(
                i for i in self.forecast_engine.materialize_equation(definition)
                if i.equation_instance_id == instance_id
            )
            trace.events.append(ExecutionEvent(
                index, EQUATION, node.node_id, node.block, definition.target_variable_id,
                instance.scope_type, instance.scope_value, period_id, results[instance_id], "WRITTEN",
            ))

    def _run_aggregation(self, index, node, context, run_date, trace):
        instances = sorted(
            (i for i in self.catalog.aggregation_rule_instances.all()
             if i.rule.aggregation_rule_id == node.node_id),
            key=lambda i: (i.scope_type or "", i.scope_value or ""),
        )
        for instance in instances:
            value = self.temporal_orchestrator.run_aggregation_instance(
                instance=instance, calculation_context=context, run_date=run_date,
            )
            context.set_variable_value(
                value.variable_id, value.value, value.scope_type, value.scope_value, value.period_id,
            )
            trace.events.append(ExecutionEvent(
                index, AGGREGATION, node.node_id, node.block, value.variable_id,
                value.scope_type, value.scope_value, value.period_id, value.value, "WRITTEN",
            ))

    def _run_transfer(self, index, node, resolver, context, run_date, trace):
        link = self.catalog.links.link_for(node.node_id)
        period_id = self.time_period_resolver.effective_window(link.frequency, run_date).period_id
        for scope_type, scope_value in link.instances:
            try:
                context.get_variable_value(node.node_id, scope_type, scope_value, period_id)
                present = True
            except VariableNotFoundError:
                present = False
            value = resolver.transfer(node.node_id, scope_type, scope_value, period_id)
            trace.events.append(ExecutionEvent(
                index, TRANSFER, node.node_id, node.block, node.node_id,
                scope_type, scope_value, period_id, value, "UNCHANGED" if present else "WRITTEN",
                link.source_block, link.source_definition_id,
            ))


__all__ = [
    "AGGREGATION",
    "EQUATION",
    "TRANSFER",
    "ExecutionCatalog",
    "ExecutionEvent",
    "ExecutionNode",
    "ExecutionPlan",
    "ExecutionTrace",
    "PendingBlocker",
    "InterblockExecutionOrchestrator",
]
