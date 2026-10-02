"""
Fase H (correções estruturais) — conversão dimensional de SUM.

O mecanismo é genérico (AggregationRule.integration_factor +
app.domain.units); os seeds reais são apenas inspecionados. As regras
existentes dimensionalmente incoerentes ficam fixadas em uma lista
explícita de pendências: nenhuma é corrigida sem decisão do dono do
bloco, e nenhuma nova incoerência entra sem fazer este teste falhar.
"""

import dataclasses
from datetime import date
from pathlib import Path

import pytest

from app.domain.forecast.aggregation import AggregationRule
from app.domain.units import (
    check_sum_dimensions,
    parse_unit,
    required_sum_factor,
)
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import InvalidAggregationRuleError
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.repositories.seed_loader import SeedLoader
from app.validation.aggregation_dimension_validator import (
    find_sum_dimension_issues,
)


SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


# ------------------------------------------------------------
# Unidades
# ------------------------------------------------------------


@pytest.mark.parametrize(
    "unit,numerator,basis",
    [
        ("kg/h", "kg", "h"),
        ("m³/h", "m³", "h"),
        ("t/d", "t", "d"),
        ("tpd", "t", "d"),
        ("kg/mês", "kg", "mês"),
        ("t/ano", "t", "ano"),
        ("kg/t", "kg/t", None),
        ("g/l", "g/l", None),
        ("%", "%", None),
        ("-", "-", None),
    ],
)
def test_parse_unit(unit, numerator, basis):
    parsed = parse_unit(unit)

    assert (parsed.numerator, parsed.basis) == (numerator, basis)


@pytest.mark.parametrize(
    "source,target,frequency,factor",
    [
        ("kg/h", "kg/mês", "mensal", 24.0),
        ("m³/h", "m³/ano", "anual", 24.0),
        ("t/d", "t/mês", "mensal", 1.0),
        ("kg/d", "kg/ano", "anual", 1.0),
        ("tpd", "t/mês", "mensal", 1.0),
        ("tpd", "tpd", "mensal", None),       # destino não é quantidade
        ("kg/h", "t/mês", "mensal", None),    # numeradores diferentes
        ("kg/h", "kg/ano", "mensal", None),   # base != frequência
        ("kg/t", "kg/t", "mensal", None),     # origem não é taxa
    ],
)
def test_required_sum_factor(source, target, frequency, factor):
    assert required_sum_factor(source, target, frequency) == factor


def test_check_sum_dimensions_reports_wrong_factor():
    assert check_sum_dimensions("kg/h", "kg/mês", "mensal", 24.0) is None
    assert "24" in check_sum_dimensions("kg/h", "kg/mês", "mensal", 1.0)
    assert "coerente" in check_sum_dimensions("tpd", "tpd", "mensal", 1.0)


# ------------------------------------------------------------
# AggregationRule.integration_factor
# ------------------------------------------------------------


def _rule(kind="SUM", factor=1.0, **extra):
    return AggregationRule(
        aggregation_rule_id="AGG92001",
        source_variable_id="VAR92001",
        source_frequency="diário",
        target_variable_id="VAR92002",
        target_frequency="mensal",
        aggregation_type=kind,
        integration_factor=factor,
        **extra,
    )


def test_integration_factor_defaults_to_one():
    rule = AggregationRule(
        "AGG92001", "VAR92001", "diário", "VAR92002", "mensal", "SUM"
    )

    assert rule.integration_factor == 1.0


@pytest.mark.parametrize("factor", [0, -24, True, "24", None, float("nan")])
def test_integration_factor_must_be_positive_number(factor):
    with pytest.raises(InvalidAggregationRuleError):
        _rule(factor=factor)


@pytest.mark.parametrize("kind", ["AVERAGE", "MOVING_AVERAGE"])
def test_integration_factor_only_for_sum(kind):
    with pytest.raises(InvalidAggregationRuleError):
        _rule(kind=kind, factor=24.0)


def _hourly_context():
    context = CalculationContext()
    for day, value in enumerate([10.0, 20.0, 30.0], start=1):
        context.set_variable_value(
            "VAR92001", value, "linha", "L1", f"2026-03-{day:02d}"
        )
    return context


def test_sum_applies_integration_factor():
    # C (Stage 5A, D-5A-2): antes, SUM com integration_factor=24 multiplicava a soma das taxas horárias
    # (60 m³/h -> 1440). Agora o runtime recusa fator != 1 e a conversão é explícita no workbook por uma
    # variável intermediária `*_ag` (m³/d = m³/h × 24); a SUM de fator 1 sobre ela dá o MESMO 1440.
    with pytest.raises(InvalidAggregationRuleError, match="D-5A-2"):
        _rule(factor=24.0)

    context = _hourly_context()
    for day, value in enumerate([10.0, 20.0, 30.0], start=1):
        context.set_variable_value(          # VAR92003 = VAR92001_ag: quantidade diária
            "VAR92003", value * 24, "linha", "L1", f"2026-03-{day:02d}"
        )
    result = TemporalAggregationService().aggregate(
        dataclasses.replace(_rule(), source_variable_id="VAR92003"), context, "linha", "L1", date(2026, 3, 3)
    )

    assert result.value == pytest.approx(60.0 * 24)


def test_sum_without_factor_is_unchanged():
    result = TemporalAggregationService().aggregate(
        _rule(), _hourly_context(), "linha", "L1", date(2026, 3, 3)
    )

    assert result.value == 60.0


def test_average_is_unchanged():
    result = TemporalAggregationService().aggregate(
        _rule(kind="AVERAGE"), _hourly_context(), "linha", "L1", date(2026, 3, 3)
    )

    assert result.value == 20.0


# ------------------------------------------------------------
# Seeds reais: pendências explícitas
# ------------------------------------------------------------


@pytest.fixture(scope="module")
def seed_rules_and_issues():
    loader = SeedLoader(SEED_ROOT)
    rules = loader.load_aggregation_rules()
    definitions = loader.load_variable_definitions()
    return rules, definitions, find_sum_dimension_issues(rules.all(), definitions)


def test_sum_factors_follow_the_approved_workbook_units(seed_rules_and_issues):
    """
    O builder deriva `integration_factor` das unidades aprovadas
    (app.domain.units.required_sum_factor). Nos workbooks aprovados
    (Etapa 2.3: 30 SUMs, "fator 1" ou "fator 24"), só as duas SUMs de
    m³/h do MaxHT v9 exigem 24; as demais somam taxas diárias (fator 1).

    C (Stage 5A, D-5A-2): o MaxHT v13 soma `lth_total_ag` (m³/d) nas duas
    SUMs de `lth_total_somatorio`; não há mais fator 24 (antes
    {1.0: {t/d, kg/d}, 24.0: {m³/h}} com 2 regras de fator 24).
    """

    rules, definitions, _issues = seed_rules_and_issues

    sums = [rule for rule in rules.all() if rule.aggregation_type == "SUM"]

    assert len(sums) == 30

    by_factor = {}
    for rule in sums:
        source_unit = definitions.get(rule.source_variable_id).unit
        by_factor.setdefault(rule.integration_factor, set()).add(source_unit)

    assert by_factor == {1.0: {"t/d", "kg/d", "m³/d"}}
    assert sum(1 for rule in sums if rule.integration_factor == 24.0) == 0
    assert sorted(
        rule.aggregation_rule_id for rule in sums
        if definitions.get(rule.source_variable_id).unit == "m³/d"
    ) == [
        "AGR-MAX_HT-LTH_TOTAL_SOMATORIO-GRUPO-L1_L7-ANUAL-SUM",
        "AGR-MAX_HT-LTH_TOTAL_SOMATORIO-GRUPO-L1_L7-MENSAL-SUM",
    ]

    non_sums = [rule for rule in rules.all() if rule.aggregation_type != "SUM"]
    assert {rule.integration_factor for rule in non_sums} == {1.0}


def test_no_seed_rule_has_dimensional_issues(seed_rules_and_issues):
    _rules, _definitions, issues = seed_rules_and_issues

    assert issues == []
