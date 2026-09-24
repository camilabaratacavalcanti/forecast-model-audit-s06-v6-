"""
Dimensão temporal das unidades usadas por agregações SUM.

Uma SUM temporal transforma uma série de TAXAS diárias (ex.: t/d,
kg/h) em uma QUANTIDADE do período de destino (t/mês, kg/ano). Para a
unidade de destino ser verdadeira, cada valor diário precisa estar em
"quantidade por dia" antes da soma:

    taxa em /d  -> fator 1   (t/d somado por dia = t no período)
    taxa em /h  -> fator 24  (kg/h * 24 h/d = kg/d, supondo que o valor
                              diário é a taxa média do dia de 24 h)

Este módulo apenas descreve unidades; não decide regras de negócio.
Uma regra cuja unidade de destino não é a quantidade do período, ou
cujo fator declarado não corresponde ao exigido pela dimensão, é
reportada por `check_sum_dimensions` — nunca corrigida em silêncio.
"""

from dataclasses import dataclass


HOURS_PER_DAY = 24.0

# Aliases de unidade já usados nos seeds.
_ALIASES = {
    "tpd": "t/d",
}

# Base temporal de uma taxa -> fator para "por dia".
RATE_BASIS_TO_DAILY = {
    "h": HOURS_PER_DAY,
    "d": 1.0,
}

# Base temporal da quantidade do período de destino.
PERIOD_BASIS_BY_FREQUENCY = {
    "mensal": "mês",
    "anual": "ano",
}


@dataclass(frozen=True)
class TemporalUnit:
    numerator: str
    basis: str | None  # "h", "d", "mês", "ano" ou None (sem base temporal)


def parse_unit(unit: str) -> TemporalUnit:
    """`kg/h` -> (kg, h); `tpd` -> (t, d); `%` -> (%, None)."""

    unit = _ALIASES.get(unit, unit)

    if "/" not in unit:
        return TemporalUnit(unit, None)

    numerator, basis = unit.rsplit("/", 1)

    if basis not in RATE_BASIS_TO_DAILY and basis not in (
        PERIOD_BASIS_BY_FREQUENCY.values()
    ):
        # Razão não temporal (kg/t, g/l, GJ/t, m²/kg): não é taxa.
        return TemporalUnit(unit, None)

    return TemporalUnit(numerator, basis)


def required_sum_factor(
    source_unit: str,
    target_unit: str,
    target_frequency: str,
) -> float | None:
    """
    Fator exigido para que SUM(source) seja expresso em `target_unit`.

    Retorna None quando a combinação não é dimensionalmente coerente
    (origem não é taxa, numeradores diferentes, destino não é a
    quantidade do período de destino).
    """

    source = parse_unit(source_unit)
    target = parse_unit(target_unit)

    if source.basis not in RATE_BASIS_TO_DAILY:
        return None

    if target.numerator != source.numerator:
        return None

    if target.basis != PERIOD_BASIS_BY_FREQUENCY.get(target_frequency):
        return None

    return RATE_BASIS_TO_DAILY[source.basis]


def check_sum_dimensions(
    source_unit: str,
    target_unit: str,
    target_frequency: str,
    integration_factor: float,
) -> str | None:
    """
    Retorna None se a SUM é dimensionalmente coerente com o fator
    declarado; caso contrário, uma descrição do problema.
    """

    required = required_sum_factor(
        source_unit, target_unit, target_frequency
    )

    if required is None:
        return (
            f"SUM de {source_unit} para {target_unit} "
            f"({target_frequency}) não é dimensionalmente coerente: o "
            "destino deveria ser a quantidade do período "
            f"({parse_unit(source_unit).numerator}/"
            f"{PERIOD_BASIS_BY_FREQUENCY.get(target_frequency, '?')})."
        )

    if integration_factor != required:
        return (
            f"SUM de {source_unit} para {target_unit} exige "
            f"integration_factor={required:g}; declarado "
            f"{integration_factor:g}."
        )

    return None
