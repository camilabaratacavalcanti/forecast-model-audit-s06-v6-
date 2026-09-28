"""
Gramática das agregações temporais escritas em texto nos workbooks.

Cada agregação é derivada SEMANTICAMENTE da expressão da própria
linha (nunca do número da linha do Excel):

    Média|Somatório <mensal|anual> de todos os resultados diários de '<origem>'[ por linha]
        -> AVERAGE | SUM, origem diária
    Média móvel dos dados de '<origem>' entre o 1º e o dia atual de cada mês.
        -> MOVING_AVERAGE, origem diária
    [Média Ponderada <mensal|anual> de todos os resultados diários: ]
    média_ponderada_dados_diários( (<origem>[diário] * <peso>[diário]) / <peso>[diário] )
        -> WEIGHTED_AVERAGE, origem e peso diários

Uma expressão que menciona um marcador de agregação mas não casa com
nenhuma forma é erro explícito — nunca é tratada como equação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


SOURCE_FREQUENCY = "diário"

_PERIOD = r"(mensal|anual)"
_NAME = r"([A-Za-zÀ-ÿ_][\wÀ-ÿ]*)"
_DAILY = r"(?:\[diário\])?"

_SIMPLE = re.compile(
    rf"^(Média|Somatório) {_PERIOD} de todos os resultados diários de "
    rf"'{_NAME}'( por linha)?$"
)

_MOVING = re.compile(
    rf"^Média móvel dos dados de '{_NAME}' entre o 1º e o dia atual de "
    r"cada mês\.$"
)

_WEIGHTED = re.compile(
    rf"^(?:Média Ponderada {_PERIOD} de todos os resultados diários: )?"
    r"média_ponderada_dados_diários\s*\(\s*\(\s*"
    rf"{_NAME}{_DAILY}\s*\*\s*{_NAME}{_DAILY}\s*\)\s*/\s*"
    rf"{_NAME}{_DAILY}\s*\)$"
)

_MARKERS = (
    "resultados diários",
    "Média móvel",
    "média_ponderada",
    "Média Ponderada",
    "Somatório",
)

_OPERATION = {"Média": "AVERAGE", "Somatório": "SUM"}


class AggregationSyntaxError(ValueError):
    """Texto de agregação fora da gramática aprovada."""


@dataclass(frozen=True)
class AggregationSpec:
    aggregation_type: str
    source_name: str
    source_frequency: str
    # Frequência de destino declarada no próprio texto (None quando o
    # texto não a declara: vale a frequência da linha).
    declared_target_frequency: str | None
    weight_name: str | None = None


def looks_like_aggregation(expression) -> bool:
    return isinstance(expression, str) and any(
        marker in expression for marker in _MARKERS
    )


def parse_aggregation(expression) -> AggregationSpec | None:
    """None quando a expressão não é uma agregação."""

    if not looks_like_aggregation(expression):
        return None

    match = _SIMPLE.match(expression)

    if match:
        operation, period, source, _per_line = match.groups()
        return AggregationSpec(
            aggregation_type=_OPERATION[operation],
            source_name=source,
            source_frequency=SOURCE_FREQUENCY,
            declared_target_frequency=period,
        )

    match = _MOVING.match(expression)

    if match:
        return AggregationSpec(
            aggregation_type="MOVING_AVERAGE",
            source_name=match.group(1),
            source_frequency=SOURCE_FREQUENCY,
            declared_target_frequency=None,
        )

    match = _WEIGHTED.match(expression)

    if match:
        period, source, weight, divisor = match.groups()

        if weight != divisor:
            raise AggregationSyntaxError(
                f"Média ponderada com pesos diferentes no numerador "
                f"({weight}) e no denominador ({divisor}): {expression!r}"
            )

        return AggregationSpec(
            aggregation_type="WEIGHTED_AVERAGE",
            source_name=source,
            source_frequency=SOURCE_FREQUENCY,
            declared_target_frequency=period,
            weight_name=weight,
        )

    raise AggregationSyntaxError(
        f"Expressão de agregação fora da gramática aprovada: {expression!r}"
    )
