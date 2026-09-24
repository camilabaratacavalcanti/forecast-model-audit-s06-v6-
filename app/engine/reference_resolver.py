"""
Resolução de referências nome -> ID na construção de seeds.

Um workbook escreve expressões em NOMES; o seed grava IDs. Um mesmo
nome pode existir em várias definições (frequências e escopos
diferentes), então o vínculo precisa considerar a identidade completa:

    nome + frequência + escopo

Regras, nesta ordem:

1. Parâmetros: a referência só pode ser a um parâmetro se houver um
   com esse nome; havendo mais de um, o escopo decide (passos 4-5).
2. Frequência: prefere-se a mesma frequência da equação consumidora;
   se não houver nenhuma, todas as definições do nome concorrem (ex.:
   entrada mensal consumida por equação diária).
3. Escopo explícito (`nome@L1_L3`): só concorrem definições que
   materializam uma instância exatamente nesse escopo.
4. Escopo implícito: para cada instância concreta do consumidor, a
   definição escolhida é a do escopo mais específico na hierarquia
   espacial do runtime (`get_spatial_candidates`: linha -> grupo ->
   planta). Todas as instâncias do consumidor precisam apontar para
   a MESMA definição — uma expressão grava um único ID.
5. Persistindo mais de um candidato, um `tie_breaker` opcional do
   builder pode decidir; senão, erro explícito.

Nunca escolhe em silêncio: toda ambiguidade residual é erro.
"""

from __future__ import annotations

import re
from typing import Callable, Mapping, Sequence

from app.engine.scope_resolver import ScopeResolver
from app.engine.scoped_reference import scope_type_for
from app.engine.spatial_candidate_resolver import get_spatial_candidates


Scope = tuple[str, str | None]
TieBreaker = Callable[[list[dict]], dict | None]

_SPATIAL_SCOPE_TYPES = {"linha", "linha_grupo", "planta"}

_SCOPE_SUFFIX = r"(@L[1-7](?:_L[1-7])?)?"


class ReferenceResolutionError(ValueError):
    """Referência ambígua após nome+frequência+escopo."""


class ReferenceNotFoundError(ReferenceResolutionError, KeyError):
    """Nome inexistente (KeyError mantido por compatibilidade)."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


def build_name_index(entities: Sequence[dict]) -> dict[str, list[dict]]:
    """Indexa entidades por nome, preservando TODAS as ocorrências."""

    index: dict[str, list[dict]] = {}

    for entity in entities:
        index.setdefault(entity["name"], []).append(entity)

    return index


def _instance_scopes(
    scope_type: str | None,
    scope_value: str | None,
    scope_resolver: ScopeResolver,
) -> list[Scope]:
    if scope_type is None:
        return [(None, None)]

    return scope_resolver.resolve_scopes(scope_type, scope_value)


def _spatial_chain(scope: Scope) -> list[Scope]:
    scope_type, scope_value = scope

    if scope_type in _SPATIAL_SCOPE_TYPES:
        return get_spatial_candidates(scope_type, scope_value)

    return [scope]


def _describe(pool: Sequence[dict]) -> str:
    return ", ".join(
        f"{entity['entity_id']}"
        f"[{entity.get('frequency')}, "
        f"{entity.get('scope_type')}/{entity.get('scope_value')}]"
        for entity in pool
    )


def _filter_by_explicit_scope(
    name: str,
    pool: list[dict],
    explicit_scope_value: str,
    scope_resolver: ScopeResolver,
) -> list[dict]:
    explicit_scope = (scope_type_for(explicit_scope_value), explicit_scope_value)

    matches = [
        entity
        for entity in pool
        if explicit_scope
        in _instance_scopes(
            entity.get("scope_type"),
            entity.get("scope_value"),
            scope_resolver,
        )
    ]

    if not matches:
        raise ReferenceResolutionError(
            f"Referência {name}@{explicit_scope_value}: nenhuma "
            "definição materializa uma instância nesse escopo "
            f"(candidatas: {_describe(pool)})."
        )

    return matches


def _filter_by_consumer_scope(
    name: str,
    pool: list[dict],
    consumer_scope: Scope,
    scope_resolver: ScopeResolver,
) -> list[dict]:
    """
    Vincula a referência implícita à definição que o runtime
    efetivamente encontraria para cada instância do consumidor.
    """

    scopes_by_entity = [
        (
            entity,
            set(
                _instance_scopes(
                    entity.get("scope_type"),
                    entity.get("scope_value"),
                    scope_resolver,
                )
            ),
        )
        for entity in pool
    ]

    bound: list[dict] | None = None

    for consumer_instance in _instance_scopes(
        consumer_scope[0], consumer_scope[1], scope_resolver
    ):
        selected: list[dict] = []

        for candidate_scope in _spatial_chain(consumer_instance):
            selected = [
                entity
                for entity, scopes in scopes_by_entity
                if candidate_scope in scopes
            ]

            if selected:
                break

        if not selected:
            # Nenhuma definição alcançável a partir desta instância:
            # o escopo não resolve a ambiguidade; o chamador decide.
            return pool

        if bound is None:
            bound = selected
        elif [e["entity_id"] for e in bound] != [
            e["entity_id"] for e in selected
        ]:
            raise ReferenceResolutionError(
                f"Referência {name}: instâncias do consumidor "
                f"{consumer_scope[0]}/{consumer_scope[1]} resolvem para "
                f"definições diferentes ({_describe(bound)} vs "
                f"{_describe(selected)}). Uma expressão grava um único "
                "ID: use escopo explícito (@) ou divida a definição "
                "consumidora por escopo."
            )

    return bound if bound is not None else pool


def resolve_reference(
    name: str,
    index: Mapping[str, list[dict]],
    frequency: str | None,
    consumer_scope: Scope | None = None,
    explicit_scope_value: str | None = None,
    tie_breaker: TieBreaker | None = None,
    scope_resolver: ScopeResolver | None = None,
) -> str:
    """
    Resolve `name` para o ID da entidade correspondente.

    `consumer_scope` é o (scope_type, scope_value) DECLARADO da
    definição consumidora (ex.: ("linha", "L1_L7")).
    `explicit_scope_value` é o sufixo `@` da própria referência.
    """

    scope_resolver = scope_resolver or ScopeResolver()

    candidates = index.get(name)

    if not candidates:
        raise ReferenceNotFoundError(
            f"Referência não encontrada na planilha: {name}"
        )

    parameters = [c for c in candidates if c["kind"] == "parameter"]

    if parameters:
        pool = parameters
    else:
        same_frequency = [
            c for c in candidates if c.get("frequency") == frequency
        ]
        pool = same_frequency or list(candidates)

    if explicit_scope_value is not None:
        pool = _filter_by_explicit_scope(
            name, pool, explicit_scope_value, scope_resolver
        )
    elif len(pool) > 1 and consumer_scope is not None:
        pool = _filter_by_consumer_scope(
            name, pool, consumer_scope, scope_resolver
        )

    if len(pool) > 1 and tie_breaker is not None:
        chosen = tie_breaker(pool)

        if chosen is not None:
            return chosen["entity_id"]

    if len(pool) > 1:
        kind = "Parâmetro" if parameters else "Referência"
        raise ReferenceResolutionError(
            f"{kind} ambígua ({name}, frequência {frequency}, escopo "
            f"{consumer_scope}): {_describe(pool)}"
        )

    return pool[0]["entity_id"]


# Literais de texto entre aspas simples ou duplas (capturados, para que
# re.split os devolva nas posições ímpares).
_STRING_LITERAL = re.compile(r"(\"[^\"]*\"|'[^']*')")


def translate_expression(
    expression: str,
    index: Mapping[str, list[dict]],
    frequency: str | None,
    consumer_scope: Scope | None = None,
    tie_breaker: TieBreaker | None = None,
    scope_resolver: ScopeResolver | None = None,
) -> str:
    """
    Reescreve uma expressão escrita em nomes para IDs, preservando o
    sufixo `@escopo` e usando-o na resolução.

    Os nomes são substituídos do mais longo para o mais curto para que
    `lth_total` não seja quebrado pela substituição de `lth`.

    Constantes de texto ("ABERTO", 'F') são preservadas literalmente:
    um nome que aparece dentro de aspas não é uma referência.
    """

    scope_resolver = scope_resolver or ScopeResolver()

    segments = _STRING_LITERAL.split(expression)

    translated = "".join(
        segment
        if position % 2
        else _translate_code_segment(
            segment,
            index,
            frequency,
            consumer_scope,
            tie_breaker,
            scope_resolver,
        )
        for position, segment in enumerate(segments)
    )

    return translated.strip()


def _translate_code_segment(
    segment: str,
    index: Mapping[str, list[dict]],
    frequency: str | None,
    consumer_scope: Scope | None,
    tie_breaker: TieBreaker | None,
    scope_resolver: ScopeResolver,
) -> str:
    translated = segment

    for name in sorted(index, key=len, reverse=True):
        pattern = re.compile(
            rf"(?<![\w@]){re.escape(name)}\b{_SCOPE_SUFFIX}"
        )

        if not pattern.search(translated):
            continue

        def _replace(match: re.Match, _name: str = name) -> str:
            suffix = match.group(1) or ""
            entity_id = resolve_reference(
                _name,
                index,
                frequency,
                consumer_scope=consumer_scope,
                explicit_scope_value=suffix[1:] or None,
                tie_breaker=tie_breaker,
                scope_resolver=scope_resolver,
            )
            return f"{entity_id}{suffix}"

        translated = pattern.sub(_replace, translated)

    return re.sub(r"\s+", " ", translated)
