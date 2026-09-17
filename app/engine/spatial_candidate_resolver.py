"""
Objetivo:
    Dado um scope consumidor (linha, linha_grupo ou planta), produzir
    a lista ordenada de scopes candidatos para uma futura resolução
    espacial de valor — da mais específica para a mais ampla.

    Este módulo NÃO busca valores, NÃO executa agregação (sum,
    average, weighted_average etc.) e NÃO conhece período/frequência.
    Ele apenas responde: "quais scopes podem ser considerados, e em
    qual ordem?".

Responsabilidade (Decision C — Projection):
    A projeção implícita permitida é exclusivamente de um scope mais
    amplo para um scope mais específico:

        planta       -> linha_grupo
        planta       -> linha
        linha_grupo  -> linha

    Nunca o inverso. Um scope de linha_grupo nunca é expandido em
    múltiplas linhas: ele é uma unidade espacial própria.

Responsabilidade (Decision D — Precedence):
    A ordem dos candidatos reflete a especificidade espacial,
    definida por inclusão de conjuntos (members(G1) ⊂ members(G2)),
    nunca por tamanho/quantidade de membros. Quando dois candidatos
    linha_grupo que contêm o mesmo scope consumidor não são
    comparáveis por inclusão, a ambiguidade é explícita
    (AmbiguousSpatialPrecedenceError) em vez de escolhida em silêncio.

Fora do escopo deste módulo (etapas futuras):
    - busca de valor (CalculationContext, Registries, ForecastValue);
    - fallback temporal (period_id, frequência, ano);
    - integração com ExpressionEvaluator;
    - qualquer forma de agregação.
"""

from functools import cmp_to_key
from typing import Mapping

from app.engine.exceptions import AmbiguousSpatialPrecedenceError
from app.engine.scope_resolver import ScopeResolver


def _ordered_by_inclusion(
    scope_type: str,
    scope_value: str,
    group_ids: list[str],
    group_members: Mapping[str, frozenset[str]],
) -> list[str]:
    """
    Ordena `group_ids` do mais específico para o mais amplo, usando
    exclusivamente a relação de inclusão de conjuntos entre seus
    `members`. Levanta AmbiguousSpatialPrecedenceError se dois grupos
    do conjunto não forem comparáveis entre si.
    """

    for i in range(len(group_ids)):
        for j in range(i + 1, len(group_ids)):
            members_a = group_members[group_ids[i]]
            members_b = group_members[group_ids[j]]

            if not (
                members_a < members_b
                or members_b < members_a
            ):
                raise AmbiguousSpatialPrecedenceError(
                    scope_type=scope_type,
                    scope_value=scope_value,
                    candidate_a=group_ids[i],
                    candidate_b=group_ids[j],
                )

    def compare(a: str, b: str) -> int:
        if group_members[a] < group_members[b]:
            return -1

        return 1

    return sorted(group_ids, key=cmp_to_key(compare))


def get_spatial_candidates(
    scope_type: str,
    scope_value: str,
    group_members: Mapping[str, frozenset[str]] = (
        ScopeResolver.GROUP_MEMBERS
    ),
) -> list[tuple[str, str]]:
    """
    Retorna os scopes candidatos para o scope consumidor
    (scope_type, scope_value), ordenados do mais específico
    (o próprio scope consumidor) para o mais amplo
    (planta/PLANTA por último, quando aplicável).

    `group_members` é injetável apenas para permitir testar cenários
    controlados de ambiguidade sem alterar
    `ScopeResolver.GROUP_MEMBERS` (a fonte de verdade real).
    """

    if scope_type == "planta":
        if scope_value != ScopeResolver.PLANT_SCOPE:
            raise ValueError(
                f"Invalid plant scope_value: {scope_value}"
            )

        # planta não possui scope espacial superior: é o único
        # candidato para si mesma.
        return [ScopeResolver.CANONICAL_PLANT_SCOPE]

    if scope_type == "linha_grupo":
        if scope_value not in group_members:
            raise ValueError(
                f"Unknown line group: {scope_value}"
            )

        own_members = group_members[scope_value]

        supersets = [
            group_id
            for group_id, members in group_members.items()
            if group_id != scope_value
            and own_members < members
        ]

        ordered_supersets = _ordered_by_inclusion(
            scope_type,
            scope_value,
            supersets,
            group_members,
        )

        return (
            [("linha_grupo", scope_value)]
            + [
                ("linha_grupo", group_id)
                for group_id in ordered_supersets
            ]
            + [ScopeResolver.CANONICAL_PLANT_SCOPE]
        )

    if scope_type == "linha":
        if scope_value not in ScopeResolver.LINE_SCOPES:
            raise ValueError(
                f"Invalid line scope_value: {scope_value}"
            )

        containing_groups = [
            group_id
            for group_id, members in group_members.items()
            if scope_value in members
        ]

        ordered_groups = _ordered_by_inclusion(
            scope_type,
            scope_value,
            containing_groups,
            group_members,
        )

        return (
            [("linha", scope_value)]
            + [
                ("linha_grupo", group_id)
                for group_id in ordered_groups
            ]
            + [ScopeResolver.CANONICAL_PLANT_SCOPE]
        )

    raise ValueError(
        f"Unsupported scope_type for spatial candidate "
        f"resolution: {scope_type}"
    )
