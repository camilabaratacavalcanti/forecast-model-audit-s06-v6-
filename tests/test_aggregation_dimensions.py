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
    result = TemporalAggregationService().aggregate(
        _rule(factor=24.0), _hourly_context(), "linha", "L1", date(2026, 3, 3)
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


def test_existing_rules_keep_default_factor(seed_rules_and_issues):
    rules, _definitions, _issues = seed_rules_and_issues

    assert {rule.integration_factor for rule in rules} == {1.0}


def test_max_ht_hourly_sums_are_the_pinned_pending_set(seed_rules_and_issues):
    """
    PENDÊNCIA (decisão do dono do bloco max_ht): 34 SUMs somam taxas
    horárias (kg/h, m³/h) em destinos rotulados kg|m³/mês|ano. O
    workbook descreve o destino como "soma dos resultados diários";
    converter exige integration_factor=24 e a premissa de dia de 24 h.
    Nenhum destino é `saída` nem é consumido por equação.
    """

    _rules, _definitions, issues = seed_rules_and_issues

    max_ht = [
        issue for issue in issues
        if issue.aggregation_rule_id.startswith("AGR-MAX_HT-")
    ]

    assert len(max_ht) == 34
    assert {(i.source_unit, i.target_unit) for i in max_ht} == {
        ("kg/h", "kg/mês"), ("kg/h", "kg/ano"),
        ("m³/h", "m³/mês"), ("m³/h", "m³/ano"),
    }


def test_max_ht_pending_set_is_resolved_by_factor_24(seed_rules_and_issues):
    """A correção está disponível na plataforma (mutação local)."""

    rules, definitions, issues = seed_rules_and_issues

    pending_ids = {
        issue.aggregation_rule_id
        for issue in issues
        if issue.aggregation_rule_id.startswith("AGR-MAX_HT-")
    }

    corrected = [
        dataclasses.replace(rule, integration_factor=24.0)
        for rule in rules
        if rule.aggregation_rule_id in pending_ids
    ]

    assert find_sum_dimension_issues(corrected, definitions) == []


def test_production_tpd_sums_are_the_pinned_pending_set(seed_rules_and_issues):
    """
    PENDÊNCIA (dono do bloco production): 3 SUMs de tpd com destino
    também rotulado tpd (deveria ser t/mês | t/ano). Problema de
    rótulo de unidade; o fator exigido seria 1.
    """

    _rules, _definitions, issues = seed_rules_and_issues

    production = sorted(
        issue.aggregation_rule_id
        for issue in issues
        if issue.aggregation_rule_id.startswith("AGR-PRODUCTION-")
    )

    assert production == [
        "AGR-PRODUCTION-CONSUMO_MPSA-GRUPO-L1_L7-ANUAL-SUM",
        "AGR-PRODUCTION-PRODUCAO_PLANTA-GRUPO-L1_L7-ANUAL-SUM",
        "AGR-PRODUCTION-PRODUCAO_PLANTA-GRUPO-L1_L7-MENSAL-SUM",
    ]


def test_no_other_block_has_dimensional_issues(seed_rules_and_issues):
    _rules, _definitions, issues = seed_rules_and_issues

    assert len(issues) == 37
