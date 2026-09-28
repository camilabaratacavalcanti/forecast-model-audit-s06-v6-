"""
Contrato interbloco declarado na coluna `fonte` (Etapa 2.6).

    workbook.fonte -> source_block canônico -> validação interbloco
        -> seed/manifesto (data/seed/interblock_links.json)

Regras:

1. `fonte` preenchida é SEMPRE uma intenção explícita de vínculo: o
   consumidor recebe o valor de uma definição do bloco produtor. Nunca
   é comentário. O source_block canônico é o texto da célula, sem
   strip, sem prefixo removido, sem alias. `source_reference` é só
   proveniência e não participa da resolução.

2. Identidade local ao bloco. O produtor é resolvido no bloco indicado
   por name + frequency + scope_type + scope_value do consumidor — o
   `name` e a `unit` são padronizados entre produtor e consumidor. A
   chave é avaliada por instância concreta, como na identidade local
   (`canonical.check_identity`): toda instância do consumidor precisa
   existir, com o mesmo scope_value, numa única definição do produtor.
   Unidade é validação, não seletor. Sem fallback temporal, sem
   fallback espacial, sem conversão de unidade, sem renomeação.

3. Contexto do consumidor: só uma variável sem expressão própria pode
   declarar `fonte` (uma linha com expressão teria dois produtores; um
   parâmetro tem valor próprio). `fonte` apontando o próprio bloco
   também é contexto inválido.

4. O vínculo resolvido é validado dimensão a dimensão: natureza
   (variable/parameter), unit, value_type, allowed_values,
   declared_result_states e instâncias (conjunto concreto de escopos,
   sem substituir L3 por L1; instância ausente é erro).

5. Ciclos são detectados no grafo de definições que une os vínculos
   interbloco às dependências intrabloco (equações e agregações),
   independentemente da ordem de carga. Todo ciclo que atravesse um
   vínculo interbloco é erro e é reportado por inteiro.

6. Nada é corrigido: um vínculo inválido não é emitido como vínculo;
   fica registrado como rejeitado, com o código do erro e a dimensão
   divergente. Esta etapa não propaga valores em runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.engine.scope_resolver import ScopeResolver
from app.validation.variable_seed_validator import VARIABLE_ID_RANGES

from tools.workbook_seed.canonical import CanonicalEntity, CanonicalModel


# Códigos de erro do contrato.
SOURCE_NOT_FOUND_CODE = "INTERBLOCK_SOURCE_NOT_FOUND"
AMBIGUOUS_CODE = "INTERBLOCK_SOURCE_AMBIGUOUS"
CONTRACT_MISMATCH_CODE = "INTERBLOCK_CONTRACT_MISMATCH"
CYCLE_CODE = "INTERBLOCK_CYCLE"

# Classes de vínculo.
VALID = "VALID"
SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"
CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
INSTANCE_MISMATCH = "INSTANCE_MISMATCH"
CYCLE = "CYCLE"

LINK_CLASSES = (
    VALID,
    SOURCE_NOT_FOUND,
    AMBIGUOUS,
    CONTRACT_MISMATCH,
    INSTANCE_MISMATCH,
    CYCLE,
)

# Estado da resolução (antes da validação do contrato).
RESOLVED = "RESOLVED"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS_RESOLUTION = "AMBIGUOUS"

OFFICIAL_BLOCKS = frozenset(VARIABLE_ID_RANGES)

_REFERENCE = re.compile(r"\b(VAR\d+|PARAM\d+)")


class InterblockContractError(ValueError):
    """Há vínculos declarados em `fonte` que não satisfazem o contrato."""


@dataclass(frozen=True)
class InterblockFinding:
    code: str
    link_class: str
    dimension: str
    consumer_value: object
    producer_value: object
    message: str


@dataclass
class InterblockLink:
    consumer_block: str
    consumer: CanonicalEntity
    source_block: object
    resolution_status: str = NOT_FOUND
    producer: CanonicalEntity | None = None
    findings: list[InterblockFinding] = field(default_factory=list)
    chain: tuple[str, ...] = ()
    chain_status: str = ""

    @property
    def consumer_rows(self) -> tuple[int, ...]:
        return tuple(r.row for r in self.consumer.rows)

    @property
    def validation_status(self) -> str:
        return self.findings[0].link_class if self.findings else VALID

    @property
    def is_valid(self) -> bool:
        return not self.findings

    def instances(self, scope_resolver: ScopeResolver | None = None) -> list[tuple[str, str]]:
        scope_resolver = scope_resolver or ScopeResolver()
        return scope_resolver.resolve_scopes(
            self.consumer.scope_type, self.consumer.scope_value
        )


@dataclass
class InterblockResult:
    links: list[InterblockLink]
    cycles: list[tuple[tuple[str, str], ...]]

    @property
    def valid(self) -> list[InterblockLink]:
        return [link for link in self.links if link.is_valid]

    @property
    def rejected(self) -> list[InterblockLink]:
        return [link for link in self.links if not link.is_valid]

    @property
    def findings(self) -> list[tuple[InterblockLink, InterblockFinding]]:
        return [(link, f) for link in self.links for f in link.findings]


# ------------------------------------------------------------
# Mensagens
# ------------------------------------------------------------

def _scope(entity: CanonicalEntity) -> str:
    return f"{entity.scope_type}/{entity.scope_value}"


def _node(block: str, entity: CanonicalEntity) -> str:
    return f"{block}.{entity.name}[{entity.frequency} {_scope(entity)}]({entity.entity_id})"


def _finding(
    link: InterblockLink,
    code: str,
    link_class: str,
    dimension: str,
    consumer_value,
    producer_value,
    detail: str = "",
) -> InterblockFinding:
    rows = ",".join(str(r) for r in link.consumer_rows)
    message = (
        f"{code}: consumidor {link.consumer_block} linha {rows} "
        f"'{link.consumer.name}' ({link.consumer.frequency} "
        f"{_scope(link.consumer)}), fonte={link.source_block!r}: "
        f"dimensão '{dimension}' — consumidor {consumer_value!r}, "
        f"produtor {producer_value!r}."
    )

    if detail:
        message += f" {detail}"

    finding = InterblockFinding(
        code=code,
        link_class=link_class,
        dimension=dimension,
        consumer_value=consumer_value,
        producer_value=producer_value,
        message=message,
    )
    link.findings.append(finding)

    return finding


# ------------------------------------------------------------
# Resolução e validação de um vínculo
# ------------------------------------------------------------

def declared_links(models: dict[str, CanonicalModel]) -> list[InterblockLink]:
    """Toda definição com `fonte` preenchida, em ordem estável."""

    links = []

    for block in sorted(models):
        for entity in models[block].entities:
            if entity.fonte is not None:
                links.append(
                    InterblockLink(
                        consumer_block=block,
                        consumer=entity,
                        source_block=entity.fonte,
                    )
                )

    return links


def _check_context(link: InterblockLink) -> None:
    consumer = link.consumer

    if not isinstance(link.source_block, str):
        _finding(
            link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, "fonte",
            link.source_block, "nome de bloco (texto)",
            "fonte deve conter apenas o nome do bloco produtor.",
        )

    if consumer.kind != "variable":
        _finding(
            link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, "consumer_context",
            consumer.kind, "variable sem expressão",
            "um parâmetro tem valor próprio e não pode declarar fonte.",
        )

    expressions = [r.expression for r in consumer.rows if r.expression is not None]

    if expressions:
        _finding(
            link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, "consumer_context",
            f"variable_type={consumer.variable_type}; expressão={expressions[0]!r}",
            "variable sem expressão",
            "a linha calcula o próprio valor e também o declara vindo "
            "de outro bloco: dois produtores para a mesma definição.",
        )

    if link.source_block == link.consumer_block:
        _finding(
            link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, "source_block",
            link.source_block, "bloco diferente do consumidor",
            "fonte aponta o próprio bloco.",
        )


def _resolve(
    link: InterblockLink,
    models: dict[str, CanonicalModel],
    scope_resolver: ScopeResolver,
) -> None:
    source = link.source_block

    if not isinstance(source, str) or source == link.consumer_block:
        link.resolution_status = NOT_FOUND
        return

    if source not in models:
        in_taxonomy = source in OFFICIAL_BLOCKS
        _finding(
            link, SOURCE_NOT_FOUND_CODE, SOURCE_NOT_FOUND, "source_block",
            source,
            (
                "bloco da taxonomia oficial sem workbook carregado"
                if in_taxonomy
                else "bloco inexistente na taxonomia oficial"
            ),
            (
                "O produtor não pode ser resolvido nem validado neste build."
                if in_taxonomy
                else "fonte deve conter apenas o nome de um bloco oficial."
            ),
        )
        link.resolution_status = NOT_FOUND
        return

    consumer = link.consumer
    # Identidade avaliada por instância concreta (mesma regra de
    # canonical.check_identity): cada instância do consumidor precisa
    # existir, com o mesmo scope_value, numa definição do produtor com o
    # mesmo name, frequency e scope_type.
    same_axes = [
        e for e in models[source].entities
        if (e.name, e.frequency, e.scope_type)
        == (consumer.name, consumer.frequency, consumer.scope_type)
    ]
    wanted = scope_resolver.resolve_scopes(consumer.scope_type, consumer.scope_value)
    owners = {
        instance: [
            e for e in same_axes
            if instance in scope_resolver.resolve_scopes(e.scope_type, e.scope_value)
        ]
        for instance in wanted
    }
    ambiguous = sorted({e.entity_id for es in owners.values() if len(es) > 1 for e in es})

    if ambiguous:
        link.resolution_status = AMBIGUOUS_RESOLUTION
        _finding(
            link, AMBIGUOUS_CODE, AMBIGUOUS, "identity",
            f"{consumer.name} {consumer.frequency} {_scope(consumer)}",
            ambiguous,
            "mais de uma definição do produtor materializa a identidade.",
        )
        return

    resolved = {es[0].entity_id: es[0] for es in owners.values() if es}

    if len(resolved) == 1 and all(owners.values()):
        link.resolution_status = RESOLVED
        link.producer = next(iter(resolved.values()))
        return

    if len(resolved) > 1 and all(owners.values()):
        link.resolution_status = AMBIGUOUS_RESOLUTION
        _finding(
            link, AMBIGUOUS_CODE, AMBIGUOUS, "identity",
            f"{consumer.name} {consumer.frequency} {_scope(consumer)}",
            sorted(resolved),
            "as instâncias do consumidor são produzidas por definições "
            "distintas: o vínculo não tem um produtor único.",
        )
        return

    link.resolution_status = NOT_FOUND
    same_name = [e for e in models[source].entities if e.name == consumer.name]

    if not same_name:
        _finding(
            link, SOURCE_NOT_FOUND_CODE, SOURCE_NOT_FOUND, "name",
            consumer.name, None,
            f"nenhuma definição chamada {consumer.name!r} no bloco {source}.",
        )
        return

    same_axes = [
        e for e in same_name
        if e.frequency == consumer.frequency and e.scope_type == consumer.scope_type
    ]

    if same_axes:
        # Mesmo name + frequency + scope_type, instâncias diferentes: sem
        # substituição de instância (L3 não serve L1).
        wanted = set(scope_resolver.resolve_scopes(consumer.scope_type, consumer.scope_value))
        offered = set()

        for e in same_axes:
            offered |= set(scope_resolver.resolve_scopes(e.scope_type, e.scope_value))

        _finding(
            link, CONTRACT_MISMATCH_CODE, INSTANCE_MISMATCH, "instances",
            sorted(v for _t, v in wanted),
            sorted(v for _t, v in offered),
            f"instâncias ausentes no produtor: "
            f"{sorted(v for _t, v in wanted - offered)}.",
        )
        return

    dimension = (
        "frequency"
        if all(e.frequency != consumer.frequency for e in same_name)
        else "scope"
    )
    _finding(
        link, SOURCE_NOT_FOUND_CODE, SOURCE_NOT_FOUND, dimension,
        f"{consumer.frequency} {_scope(consumer)}",
        sorted(f"{e.frequency} {_scope(e)}" for e in same_name),
        "sem fallback temporal ou espacial para vínculos interbloco.",
    )


def _check_contract(link: InterblockLink, scope_resolver: ScopeResolver) -> None:
    consumer, producer = link.consumer, link.producer

    if producer is None:
        return

    if consumer.kind != producer.kind:
        _finding(
            link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, "kind",
            consumer.kind, f"{producer.kind} ({producer.entity_id})",
            "consumidor e produtor têm naturezas diferentes; nenhuma "
            "conversão entre parâmetro e variável é feita.",
        )

    for dimension in ("unit", "value_type", "allowed_values", "declared_result_states"):
        mine = getattr(consumer, dimension)
        theirs = getattr(producer, dimension)

        if mine != theirs:
            _finding(
                link, CONTRACT_MISMATCH_CODE, CONTRACT_MISMATCH, dimension,
                mine, theirs,
                "sem conversão." if dimension == "unit" else "",
            )

    wanted = scope_resolver.resolve_scopes(consumer.scope_type, consumer.scope_value)
    offered = set(scope_resolver.resolve_scopes(producer.scope_type, producer.scope_value))
    missing = [s for s in wanted if s not in offered]

    if missing:
        _finding(
            link, CONTRACT_MISMATCH_CODE, INSTANCE_MISMATCH, "instances",
            [v for _t, v in wanted], sorted(v for _t, v in offered),
            f"instâncias ausentes no produtor: {[v for _t, v in missing]}.",
        )


# ------------------------------------------------------------
# Grafo e ciclos
# ------------------------------------------------------------

def seed_dependencies(block: str, seeds: dict) -> list[tuple[tuple[str, str], tuple[str, str]]]:
    """Arestas intrabloco consumidor -> dependência, a partir dos seeds."""

    edges = []

    for equation in seeds.get("equations", []):
        for ref in _REFERENCE.findall(equation["expression"]):
            edges.append(((block, equation["target_variable_id"]), (block, ref)))

    for rule in seeds.get("aggregation_rules", []):
        edges.append(
            ((block, rule["target_variable_id"]), (block, rule["source_variable_id"]))
        )

    return edges


def _strongly_connected(graph: dict) -> list[list]:
    """Tarjan iterativo sobre nós ordenados: resultado independe da ordem."""

    index: dict = {}
    low: dict = {}
    stack: list = []
    on_stack: set = set()
    components = []
    counter = 0

    for root in sorted(graph):
        if root in index:
            continue

        work = [(root, iter(sorted(graph.get(root, ()))))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)

        while work:
            node, successors = work[-1]
            advanced = False

            for successor in successors:
                if successor not in index:
                    index[successor] = low[successor] = counter
                    counter += 1
                    stack.append(successor)
                    on_stack.add(successor)
                    work.append((successor, iter(sorted(graph.get(successor, ())))))
                    advanced = True
                    break

                if successor in on_stack:
                    low[node] = min(low[node], index[successor])

            if advanced:
                continue

            work.pop()

            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

            if low[node] == index[node]:
                component = []

                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)

                    if member == node:
                        break

                components.append(sorted(component))

    return components


def _path(graph: dict, start, goal, allowed: set) -> list:
    """Menor caminho start -> goal dentro de `allowed` (BFS ordenado)."""

    previous = {start: None}
    queue = [start]

    while queue:
        node = queue.pop(0)

        if node == goal:
            path = []

            while node is not None:
                path.append(node)
                node = previous[node]

            return path[::-1]

        for successor in sorted(graph.get(node, ())):
            if successor in allowed and successor not in previous:
                previous[successor] = node
                queue.append(successor)

    return []


def _detect_cycles(
    links: list[InterblockLink],
    dependencies: list[tuple[tuple[str, str], tuple[str, str]]],
    labels: dict,
) -> list[tuple[tuple[str, str], ...]]:
    graph: dict = {}
    interblock_edges = {}

    for consumer, dependency in dependencies:
        graph.setdefault(consumer, set()).add(dependency)

    for link in links:
        if link.producer is None:
            continue

        u = (link.consumer_block, link.consumer.entity_id)
        v = (link.source_block, link.producer.entity_id)
        graph.setdefault(u, set()).add(v)
        interblock_edges.setdefault((u, v), []).append(link)

    cycles = []

    for component in _strongly_connected(graph):
        members = set(component)

        for (u, v), edge_links in sorted(interblock_edges.items()):
            if u not in members or v not in members:
                continue

            back = _path(graph, v, u, members)
            cycle = tuple([u] + back)
            # Forma canônica: começa no menor nó.
            body = list(cycle[:-1])
            start = body.index(min(body))
            cycle = tuple(body[start:] + body[:start] + [body[start]])

            if cycle not in cycles:
                cycles.append(cycle)

            text = " → ".join(labels.get(n, f"{n[0]}.{n[1]}") for n in cycle)

            for link in edge_links:
                _finding(
                    link, CYCLE_CODE, CYCLE, "cycle",
                    labels.get(u), labels.get(v),
                    f"ciclo: {text}.",
                )

    return cycles


def _chains(links: list[InterblockLink]) -> None:
    by_consumer = {(l.consumer_block, l.consumer.entity_id): l for l in links}

    for link in links:
        chain = [f"{link.consumer_block}.{link.consumer.name}"]
        status = VALID
        current = link
        seen = set()

        while True:
            key = (current.consumer_block, current.consumer.entity_id)

            if key in seen:
                status = CYCLE
                break

            seen.add(key)

            if not current.is_valid or current.producer is None:
                status = f"BROKEN_AT:{current.consumer_block}.{current.consumer.name}"
                producer = current.producer.name if current.producer else "?"
                chain.append(f"{current.source_block}.{producer}")
                break

            chain.append(f"{current.source_block}.{current.producer.name}")
            upstream = by_consumer.get((current.source_block, current.producer.entity_id))

            if upstream is None:
                break

            current = upstream

        link.chain = tuple(chain)
        link.chain_status = status


# ------------------------------------------------------------
# Entrada pública
# ------------------------------------------------------------

def validate_interblock(
    models: dict[str, CanonicalModel],
    dependencies: list[tuple[tuple[str, str], tuple[str, str]]] = (),
    scope_resolver: ScopeResolver | None = None,
) -> InterblockResult:
    scope_resolver = scope_resolver or ScopeResolver()
    links = declared_links(models)

    for link in links:
        _check_context(link)
        _resolve(link, models, scope_resolver)
        _check_contract(link, scope_resolver)

    labels = {
        (block, entity.entity_id): _node(block, entity)
        for block, model in models.items()
        for entity in model.entities
    }
    cycles = _detect_cycles(links, list(dependencies), labels)
    _chains(links)

    return InterblockResult(links=links, cycles=cycles)


def require_valid(result: InterblockResult) -> None:
    if result.rejected:
        raise InterblockContractError(
            "\n".join(f.message for _link, f in result.findings)
        )


def _scope_record(entity: CanonicalEntity) -> dict:
    return {"scope_type": entity.scope_type, "scope_value": entity.scope_value}


def link_record(link: InterblockLink, scope_resolver: ScopeResolver | None = None) -> dict:
    """Representação canônica de um vínculo válido."""

    return {
        "consumer_block": link.consumer_block,
        "consumer_definition": link.consumer.entity_id,
        "consumer_frequency": link.consumer.frequency,
        "consumer_scope": _scope_record(link.consumer),
        "source_block": link.source_block,
        "source_definition": link.producer.entity_id,
        "source_frequency": link.producer.frequency,
        "source_scope": _scope_record(link.producer),
        "instances": [
            {"scope_type": t, "scope_value": v}
            for t, v in link.instances(scope_resolver)
        ],
        "consumer_rows": list(link.consumer_rows),
    }


def rejected_record(link: InterblockLink) -> dict:
    return {
        "consumer_block": link.consumer_block,
        "consumer_definition": link.consumer.entity_id,
        "consumer_name": link.consumer.name,
        "consumer_frequency": link.consumer.frequency,
        "consumer_scope": _scope_record(link.consumer),
        "consumer_rows": list(link.consumer_rows),
        "source_block": link.source_block,
        "source_definition": link.producer.entity_id if link.producer else None,
        "resolution_status": link.resolution_status,
        "validation_status": link.validation_status,
        "errors": [
            {
                "code": f.code,
                "class": f.link_class,
                "dimension": f.dimension,
                "consumer_value": f.consumer_value,
                "producer_value": f.producer_value,
                "message": f.message,
            }
            for f in link.findings
        ],
    }


def interblock_seed(models: dict[str, CanonicalModel], result: InterblockResult) -> dict:
    return {
        "contract": "workbook.fonte -> source_block (Etapa 2.6)",
        "workbooks": {
            block: {
                "file_name": models[block].workbook.file_name,
                "sha256": models[block].workbook.sha256,
            }
            for block in sorted(models)
        },
        "links": [link_record(link) for link in result.valid],
        "rejected": [rejected_record(link) for link in result.rejected],
    }


__all__ = [
    "AMBIGUOUS",
    "AMBIGUOUS_CODE",
    "CONTRACT_MISMATCH",
    "CONTRACT_MISMATCH_CODE",
    "CYCLE",
    "CYCLE_CODE",
    "INSTANCE_MISMATCH",
    "InterblockContractError",
    "InterblockFinding",
    "InterblockLink",
    "InterblockResult",
    "LINK_CLASSES",
    "SOURCE_NOT_FOUND",
    "SOURCE_NOT_FOUND_CODE",
    "VALID",
    "declared_links",
    "interblock_seed",
    "link_record",
    "rejected_record",
    "require_valid",
    "seed_dependencies",
    "validate_interblock",
]
