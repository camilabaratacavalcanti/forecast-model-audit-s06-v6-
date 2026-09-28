"""
Registro dos vínculos interbloco canônicos (Etapa 3.1).

Carrega `interblock_links.json` e o confere contra os seeds de variáveis
dos blocos carregados antes de aceitar qualquer vínculo. Um registro que
não satisfaz o contrato não é tratado como vínculo válido: o
carregamento falha com `InterblockSeedError` (ou `InterblockCycleError`).

Conferências (todas determinísticas, sem reler workbook nem `fonte`):

    - estrutura de cada registro (campos obrigatórios e tipos);
    - consumidor e produtor em blocos distintos, ambos carregados;
    - cada ID pertence ao seed do bloco declarado (identidade local);
    - frequência e escopo do registro iguais aos da definição;
    - mesma frequência no consumidor e no produtor (sem conversão);
    - mesma unidade e mesmo value_type (sem conversão de unidade);
    - instâncias não vazias, sem repetição, existentes no consumidor e
      no produtor (sem substituição de instância);
    - um consumidor aparece no máximo uma vez (links/pending/rejected);
    - pendência: bloco fonte oficial (taxonomia do seed) e não carregado,
      sem produtor;
    - ausência de ciclo entre vínculos.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.interblock.models import (
    InterblockLink,
    PendingInterblockLink,
    RejectedInterblockLink,
)
from app.engine.exceptions import InterblockCycleError, InterblockSeedError
from app.engine.scope_resolver import ScopeResolver


INTERBLOCK_SEED_FILE = "interblock_links.json"

_LINK_FIELDS = (
    "consumer_block", "consumer_definition", "consumer_frequency", "consumer_scope",
    "source_block", "source_definition", "source_frequency", "source_scope", "instances",
)
_PENDING_FIELDS = (
    "consumer_block", "consumer_definition", "consumer_name", "consumer_frequency",
    "consumer_scope", "source_block", "source_definition",
)


class InterblockLinkRegistry:
    """
    Vínculos canônicos indexados pela definição consumidora.

    Não produz nem consome valores: apenas responde qual é o vínculo de
    um consumidor. O transporte de valores fica em
    `app.engine.interblock_resolver.InterblockValueResolver`.
    """

    def __init__(
        self,
        links: list[InterblockLink],
        pending: list[PendingInterblockLink],
        rejected: list[RejectedInterblockLink],
        loaded_blocks: tuple[str, ...],
    ):
        self._links = {link.consumer_definition_id: link for link in links}
        self._pending = {p.consumer_definition_id: p for p in pending}
        self._rejected = {r.consumer_definition_id: r for r in rejected}
        self.loaded_blocks = tuple(sorted(loaded_blocks))
        self._order = _topological_order(self._links)

    # --------------------------------------------------------
    # Consulta
    # --------------------------------------------------------

    def links(self) -> list[InterblockLink]:
        """Vínculos válidos em ordem de dependência (produtor antes)."""

        return [self._links[consumer] for consumer in self._order]

    def pending(self) -> list[PendingInterblockLink]:
        return [self._pending[k] for k in sorted(self._pending)]

    def rejected(self) -> list[RejectedInterblockLink]:
        return [self._rejected[k] for k in sorted(self._rejected)]

    def link_for(self, consumer_definition_id: str) -> InterblockLink | None:
        return self._links.get(consumer_definition_id)

    def pending_for(self, consumer_definition_id: str) -> PendingInterblockLink | None:
        return self._pending.get(consumer_definition_id)

    def rejected_for(self, consumer_definition_id: str) -> RejectedInterblockLink | None:
        return self._rejected.get(consumer_definition_id)

    # --------------------------------------------------------
    # Carregamento
    # --------------------------------------------------------

    @classmethod
    def from_seed_root(
        cls,
        seed_root: str | Path,
        scope_resolver: ScopeResolver | None = None,
    ) -> "InterblockLinkRegistry":
        seed_root = Path(seed_root)
        path = seed_root / INTERBLOCK_SEED_FILE

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise InterblockSeedError(f"{path}: artefato ilegível ({error}).") from error

        blocks = payload.get("workbooks")

        if not isinstance(blocks, dict) or not blocks:
            raise InterblockSeedError(f"{path}: seção 'workbooks' ausente ou vazia.")

        block_variables = {}

        for block in sorted(blocks):
            variables_path = seed_root / block / "variables.json"

            try:
                block_variables[block] = json.loads(variables_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise InterblockSeedError(
                    f"{variables_path}: seed do bloco carregado '{block}' ilegível ({error})."
                ) from error

        return cls.from_payload(payload, block_variables, scope_resolver)

    @classmethod
    def from_payload(
        cls,
        payload: dict,
        block_variables: dict[str, list[dict]],
        scope_resolver: ScopeResolver | None = None,
    ) -> "InterblockLinkRegistry":
        resolver = scope_resolver or ScopeResolver()

        for section in ("links", "pending", "rejected"):
            if not isinstance(payload.get(section), list):
                raise InterblockSeedError(f"seção '{section}' ausente ou não é lista.")

        loaded = tuple(sorted(block_variables))
        official = payload.get("taxonomy", {}).get("official_blocks")

        if not isinstance(official, list) or not official:
            raise InterblockSeedError("taxonomia oficial ausente do artefato canônico.")

        definitions = {
            block: {v["variable_id"]: v for v in variables}
            for block, variables in block_variables.items()
        }
        seen_consumers: set[str] = set()

        def consumer_once(record):
            consumer = record.get("consumer_definition")

            if consumer in seen_consumers:
                raise InterblockSeedError(
                    f"consumidor {consumer} declarado mais de uma vez no artefato canônico."
                )

            seen_consumers.add(consumer)

        links = []

        for record in payload["links"]:
            consumer_once(record)
            links.append(_link(record, definitions, loaded, resolver))

        pending = []

        for record in payload["pending"]:
            consumer_once(record)
            pending.append(_pending(record, definitions, loaded, set(official), resolver))

        rejected = []

        for record in payload["rejected"]:
            consumer_once(record)
            rejected.append(
                RejectedInterblockLink(
                    consumer_block=record.get("consumer_block"),
                    consumer_definition_id=record.get("consumer_definition"),
                    source_block=record.get("source_block"),
                    error_codes=tuple(e.get("code") for e in record.get("errors", [])),
                )
            )

        return cls(links, pending, rejected, loaded)


# ------------------------------------------------------------
# Conferência de registros
# ------------------------------------------------------------

def _require(record: dict, fields: tuple[str, ...], section: str) -> None:
    missing = [f for f in fields if f not in record]

    if missing:
        raise InterblockSeedError(
            f"registro de '{section}' sem os campos {missing}: {record!r}."
        )


def _scope(record: dict, field: str) -> tuple[str, str | None]:
    scope = record[field]

    if not isinstance(scope, dict) or "scope_type" not in scope or "scope_value" not in scope:
        raise InterblockSeedError(f"'{field}' inválido: {scope!r}.")

    return scope["scope_type"], scope["scope_value"]


def _definition(definitions: dict, block: str, definition_id, role: str, record: dict) -> dict:
    variables = definitions.get(block)

    if variables is None:
        raise InterblockSeedError(
            f"{role}: bloco '{block}' não está carregado ({record!r})."
        )

    definition = variables.get(definition_id)

    if definition is None:
        raise InterblockSeedError(
            f"{role}: {definition_id!r} não é definição do bloco '{block}' "
            "(identidade local ao bloco)."
        )

    return definition


def _check_axes(definition: dict, frequency, scope, role: str, definition_id: str) -> None:
    if definition["frequency"] != frequency:
        raise InterblockSeedError(
            f"{role} {definition_id}: frequência do vínculo {frequency!r} difere "
            f"da definição {definition['frequency']!r}."
        )

    if (definition["scope_type"], definition["scope_value"]) != scope:
        raise InterblockSeedError(
            f"{role} {definition_id}: escopo do vínculo {scope!r} difere da "
            f"definição {(definition['scope_type'], definition['scope_value'])!r}."
        )


def _link(record: dict, definitions: dict, loaded: tuple, resolver: ScopeResolver) -> InterblockLink:
    _require(record, _LINK_FIELDS, "links")
    consumer_block = record["consumer_block"]
    source_block = record["source_block"]

    if consumer_block == source_block:
        raise InterblockSeedError(f"vínculo dentro do mesmo bloco '{consumer_block}': {record!r}.")

    consumer_scope = _scope(record, "consumer_scope")
    source_scope = _scope(record, "source_scope")
    consumer = _definition(definitions, consumer_block, record["consumer_definition"], "consumidor", record)
    producer = _definition(definitions, source_block, record["source_definition"], "produtor", record)

    _check_axes(consumer, record["consumer_frequency"], consumer_scope, "consumidor", record["consumer_definition"])
    _check_axes(producer, record["source_frequency"], source_scope, "produtor", record["source_definition"])

    if record["consumer_frequency"] != record["source_frequency"]:
        raise InterblockSeedError(
            f"{record['consumer_definition']} <- {record['source_definition']}: frequências "
            f"{record['consumer_frequency']!r} x {record['source_frequency']!r} "
            "(sem conversão entre blocos)."
        )

    for dimension in ("unit", "value_type"):
        if consumer[dimension] != producer[dimension]:
            raise InterblockSeedError(
                f"{record['consumer_definition']} <- {record['source_definition']}: "
                f"{dimension} {consumer[dimension]!r} x {producer[dimension]!r} "
                "(sem conversão)."
            )

    raw_instances = record["instances"]

    if not isinstance(raw_instances, list) or not raw_instances:
        raise InterblockSeedError(f"{record['consumer_definition']}: instâncias ausentes.")

    instances = []

    for item in raw_instances:
        if not isinstance(item, dict) or set(item) != {"scope_type", "scope_value"}:
            raise InterblockSeedError(f"{record['consumer_definition']}: instância inválida {item!r}.")
        instances.append((item["scope_type"], item["scope_value"]))

    if len(set(instances)) != len(instances):
        raise InterblockSeedError(f"{record['consumer_definition']}: instância repetida {instances}.")

    consumer_instances = set(resolver.resolve_scopes(*consumer_scope))
    producer_instances = set(resolver.resolve_scopes(*source_scope))

    for instance in instances:
        if instance not in consumer_instances or instance not in producer_instances:
            raise InterblockSeedError(
                f"{record['consumer_definition']} <- {record['source_definition']}: "
                f"instância {instance} não existe no consumidor e no produtor "
                "(sem substituição de instância)."
            )

    return InterblockLink(
        consumer_block=consumer_block,
        consumer_definition_id=record["consumer_definition"],
        consumer_frequency=record["consumer_frequency"],
        consumer_scope_type=consumer_scope[0],
        consumer_scope_value=consumer_scope[1],
        source_block=source_block,
        source_definition_id=record["source_definition"],
        source_frequency=record["source_frequency"],
        source_scope_type=source_scope[0],
        source_scope_value=source_scope[1],
        instances=tuple(instances),
        unit=consumer["unit"],
        consumer_rows=tuple(record.get("consumer_rows", ())),
    )


def _pending(
    record: dict,
    definitions: dict,
    loaded: tuple,
    official: set,
    resolver: ScopeResolver,
) -> PendingInterblockLink:
    _require(record, _PENDING_FIELDS, "pending")
    consumer_scope = _scope(record, "consumer_scope")
    consumer = _definition(
        definitions, record["consumer_block"], record["consumer_definition"], "consumidor", record
    )
    _check_axes(consumer, record["consumer_frequency"], consumer_scope, "consumidor", record["consumer_definition"])
    source_block = record["source_block"]

    if source_block in loaded:
        raise InterblockSeedError(
            f"{record['consumer_definition']}: pendência para bloco carregado '{source_block}'."
        )

    if source_block not in official:
        raise InterblockSeedError(
            f"{record['consumer_definition']}: pendência para bloco fora da taxonomia "
            f"oficial {source_block!r}."
        )

    if record["source_definition"] is not None:
        raise InterblockSeedError(
            f"{record['consumer_definition']}: pendência com produtor "
            f"{record['source_definition']!r} (produtor fictício)."
        )

    return PendingInterblockLink(
        consumer_block=record["consumer_block"],
        consumer_definition_id=record["consumer_definition"],
        consumer_name=record["consumer_name"],
        consumer_frequency=record["consumer_frequency"],
        consumer_scope_type=consumer_scope[0],
        consumer_scope_value=consumer_scope[1],
        source_block=source_block,
        instances=tuple(resolver.resolve_scopes(*consumer_scope)),
        consumer_rows=tuple(record.get("consumer_rows", ())),
    )


def _topological_order(links: dict[str, InterblockLink]) -> list[str]:
    """
    Consumidores em ordem produtor-antes-do-consumidor, desempate por ID:
    independe da ordem do artefato. Ciclo é erro antes de qualquer
    execução.
    """

    order: list[str] = []
    state: dict[str, int] = {}

    def visit(consumer: str, path: list[str]) -> None:
        if state.get(consumer) == 2:
            return

        if state.get(consumer) == 1:
            cycle = path[path.index(consumer):] + [consumer]
            raise InterblockCycleError(
                "ciclo entre vínculos canônicos: " + " → ".join(cycle),
                cycle=tuple(cycle),
            )

        state[consumer] = 1
        upstream = links[consumer].source_definition_id

        if upstream in links:
            visit(upstream, path + [consumer])

        state[consumer] = 2
        order.append(consumer)

    for consumer in sorted(links):
        visit(consumer, [])

    return order


__all__ = ["INTERBLOCK_SEED_FILE", "InterblockLinkRegistry"]
