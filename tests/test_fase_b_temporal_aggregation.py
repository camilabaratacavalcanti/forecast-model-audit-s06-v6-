"""
FASE B — Temporal Aggregation.

Objetivo:
    Provar, com execução real (sem mocks), que a plataforma agora
    consegue derivar um ForecastValue de uma frequência a partir de
    resultados já calculados em outra frequência (AVERAGE, SUM,
    WEIGHTED_AVERAGE, MOVING_AVERAGE), como uma camada independente
    de EquationDefinition/EquationEngine/DependencyGraph, respeitando:

        - a janela efetiva truncada em run_date (nunca datas
          futuras, nunca o mês/ano de calendário inteiro);
        - scope e period como dimensões distintas e preservadas;
        - múltiplas AggregationRules para a mesma Variable/frequência
          sem colisão de identidade (aggregation_rule_id);
        - ForecastYear como fronteira (sem vazamento entre anos);
        - o comportamento determinístico e não-silencioso quando
          SUM(weight) == 0;
        - que uma Equation DIRECT anual continua funcionando sem
          nenhuma AggregationRule.

Nenhuma das 106 EquationDefinitions do Yield é alterada por este
módulo.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import AggregationRule
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    EmptyAggregationWindowError,
    InvalidAggregationRuleError,
    VariableNotFoundError,
    ZeroWeightSumError,
)
from app.engine.forecast_engine import ForecastEngine
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.repositories.seed_loader import SeedLoader


SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

YIELD_INPUT_DAILY_VALUES = {
    "lth": 500.0,
    "oee": 0.9,
    "ltp_lth": 1.1,
    "ltp_a_c": 1.5,
    "sl_solids": 140.0,
    "ssa_sf": 3.0,
    "ssa_sg": 1.5,
    "eoc_temp": 74.0,
    "eoc_solids": 250.0,
    "tanque": 12.0,
    "ltp_tc": 273.0,
}

YIELD_INPUT_ANNUAL_VALUES = {
    "lth_base": 500.0,
    "oee_base": 0.9,
    "ltp_lth_base": 1.1,
    "ltp_a_c_base": 1.5,
    "sl_solids_base": 140.0,
    "ratio_spent_base": 0.5,
    "ssa_sf_base": 3.0,
    "ssa_sg_base": 1.5,
    "n_ppt_base": 10.0,
    "eoc_temp_base": 74.0,
    "eoc_solids_base": 250.0,
}


def _populate_yield_context(context, variable_definitions):
    definitions_by_name_scope = {}

    for d in variable_definitions.all():
        definitions_by_name_scope.setdefault(d.variable_name, {})[
            (d.frequency, d.scope_type, d.scope_value)
        ] = d

    for name, value in YIELD_INPUT_DAILY_VALUES.items():
        definition = definitions_by_name_scope[name][
            ("diário", "linha", "L1_L7")
        ]

        for line in LINES:
            context.set_variable_value(
                variable_id=definition.variable_definition_id,
                value=value,
                scope_type="linha",
                scope_value=line,
            )

    for name, value in YIELD_INPUT_ANNUAL_VALUES.items():
        definition = definitions_by_name_scope[name][
            ("anual", "linha", "L1_L7")
        ]

        for line in LINES:
            context.set_variable_value(
                variable_id=definition.variable_definition_id,
                value=value,
                scope_type="linha",
                scope_value=line,
            )


def _populate_daily(
    context,
    variable_id,
    scope_type,
    scope_value,
    values_by_date,
):
    for day, value in values_by_date.items():
        context.set_variable_value(
            variable_id=variable_id,
            value=value,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=day.isoformat(),
        )


def _daily_range(start, end, start_value, step=1.0):
    values = {}
    current = start
    value = start_value
    while current <= end:
        values[current] = value
        value += step
        current += timedelta(days=1)
    return values


# ============================================================
# A1 — AVERAGE simples
# ============================================================


def test_a1_average_simple():
    context = CalculationContext()

    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 14), start_value=10.0
    )
    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-AVG-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    expected = sum(values.values()) / len(values)

    assert result.variable_id == "VARMONTHLY"
    assert result.frequency == "mensal"
    assert result.period_id == "2026-09"
    assert result.forecast_year == 2026
    assert result.scope_type == "linha"
    assert result.scope_value == "L1"
    assert result.aggregation_rule_id == "AGR-AVG-001"
    assert result.value == pytest.approx(expected)


# ============================================================
# A2 — SUM
# ============================================================


def test_a2_sum():
    context = CalculationContext()

    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 14), start_value=100.0
    )
    _populate_daily(context, "VARPROD", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-SUM-001",
        source_variable_id="VARPROD",
        source_frequency="diário",
        target_variable_id="VARPROD_MONTHLY",
        target_frequency="mensal",
        aggregation_type="SUM",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    assert result.value == pytest.approx(sum(values.values()))
    assert result.period_id == "2026-09"


# ============================================================
# A3 — WEIGHTED_AVERAGE
# ============================================================


def test_a3_weighted_average():
    context = CalculationContext()

    day_values = {
        date(2026, 9, 1): 10.0,
        date(2026, 9, 2): 20.0,
        date(2026, 9, 3): 30.0,
    }
    day_weights = {
        date(2026, 9, 1): 1.0,
        date(2026, 9, 2): 2.0,
        date(2026, 9, 3): 3.0,
    }

    _populate_daily(context, "VARVAL", "linha", "L4", day_values)
    _populate_daily(context, "VARWEIGHT", "linha", "L4", day_weights)

    rule = AggregationRule(
        aggregation_rule_id="AGR-WAVG-001",
        source_variable_id="VARVAL",
        source_frequency="diário",
        target_variable_id="VARVAL_MONTHLY",
        target_frequency="mensal",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARWEIGHT",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L4",
        run_date=date(2026, 9, 3),
    )

    expected = (10 * 1 + 20 * 2 + 30 * 3) / (1 + 2 + 3)

    assert result.value == pytest.approx(expected)


# ============================================================
# A4 — SUM(weight) == 0
# ============================================================


def test_a4_weighted_average_zero_weight_sum_raises_explicit_error():
    context = CalculationContext()

    day_values = {
        date(2026, 9, 1): 10.0,
        date(2026, 9, 2): 20.0,
    }
    day_weights = {
        date(2026, 9, 1): 0.0,
        date(2026, 9, 2): 0.0,
    }

    _populate_daily(context, "VARVAL", "linha", "L4", day_values)
    _populate_daily(context, "VARWEIGHT", "linha", "L4", day_weights)

    rule = AggregationRule(
        aggregation_rule_id="AGR-WAVG-002",
        source_variable_id="VARVAL",
        source_frequency="diário",
        target_variable_id="VARVAL_MONTHLY",
        target_frequency="mensal",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARWEIGHT",
    )

    service = TemporalAggregationService()

    with pytest.raises(ZeroWeightSumError):
        service.aggregate(
            rule=rule,
            calculation_context=context,
            scope_type="linha",
            scope_value="L4",
            run_date=date(2026, 9, 2),
        )


# ============================================================
# A5/A6 — MOVING_AVERAGE com janela explícita, inclusiva
# ============================================================


def test_a5_moving_average_uses_explicit_window():
    context = CalculationContext()

    # Popula um horizonte maior do que a janela da regra, para provar
    # que apenas [start_date, end_date] é considerado.
    values = _daily_range(
        date(2026, 8, 20), date(2026, 9, 20), start_value=1.0
    )
    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-MAVG-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMOVAVG",
        target_frequency="mensal",
        aggregation_type="MOVING_AVERAGE",
        window_start_date=date(2026, 9, 1),
        window_end_date=date(2026, 9, 14),
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    window_values = {
        d: v
        for d, v in values.items()
        if date(2026, 9, 1) <= d <= date(2026, 9, 14)
    }

    assert len(window_values) == 14
    assert result.value == pytest.approx(
        sum(window_values.values()) / len(window_values)
    )


def test_a6_moving_average_window_is_inclusive_on_both_ends():
    context = CalculationContext()

    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 14), start_value=0.0, step=0.0
    )
    values[date(2026, 9, 1)] = 100.0
    values[date(2026, 9, 14)] = 200.0

    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-MAVG-002",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMOVAVG",
        target_frequency="mensal",
        aggregation_type="SUM",
        window_start_date=date(2026, 9, 1),
        window_end_date=date(2026, 9, 14),
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    # Se a janela não fosse inclusiva em ambos os extremos, algum dos
    # dois valores (100 ou 200) ficaria de fora e a soma não bateria.
    assert result.value == pytest.approx(300.0)


# ============================================================
# A7 — Janela mensal progressiva (nunca o mês inteiro)
# ============================================================


def test_a7_monthly_progressive_window_never_reads_future_days():
    context = CalculationContext()

    # Popula somente 01..14 — se o serviço tentasse ler 15..30,
    # receberia VariableNotFoundError.
    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 14), start_value=5.0
    )
    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-AVG-PROG-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    assert result.value == pytest.approx(
        sum(values.values()) / len(values)
    )


# ============================================================
# A8 — Janela anual progressiva
# ============================================================


def test_a8_annual_progressive_window_never_reads_future_days():
    context = CalculationContext()

    # Só até 2026-01-05: se o serviço lesse além disso, receberia
    # VariableNotFoundError.
    values = _daily_range(
        date(2026, 1, 1), date(2026, 1, 5), start_value=1.0
    )
    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-AVG-ANNUAL-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARANNUAL",
        target_frequency="anual",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 1, 5),
    )

    assert result.period_id == "2026"
    assert result.value == pytest.approx(
        sum(values.values()) / len(values)
    )


# ============================================================
# A9/A10 — Múltiplas regras para a mesma Variable
# ============================================================


def test_a9_a10_multiple_rules_for_same_variable_do_not_collide():
    context = CalculationContext()

    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 14), start_value=10.0
    )
    _populate_daily(context, "VARPROD", "linha", "L2", values)

    rule_sum = AggregationRule(
        aggregation_rule_id="AGR-PROD-SUM",
        source_variable_id="VARPROD",
        source_frequency="diário",
        target_variable_id="VARPROD_MONTHLY",
        target_frequency="mensal",
        aggregation_type="SUM",
    )

    rule_avg = AggregationRule(
        aggregation_rule_id="AGR-PROD-AVG",
        source_variable_id="VARPROD",
        source_frequency="diário",
        target_variable_id="VARPROD_MONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result_sum = service.aggregate(
        rule=rule_sum,
        calculation_context=context,
        scope_type="linha",
        scope_value="L2",
        run_date=date(2026, 9, 14),
    )

    result_avg = service.aggregate(
        rule=rule_avg,
        calculation_context=context,
        scope_type="linha",
        scope_value="L2",
        run_date=date(2026, 9, 14),
    )

    # Mesma variable_id, escopo, frequência e period_id...
    assert result_sum.variable_id == result_avg.variable_id
    assert result_sum.scope_value == result_avg.scope_value
    assert result_sum.period_id == result_avg.period_id
    assert result_sum.frequency == result_avg.frequency

    # ...mas identidades e valores distintos, graças à regra.
    assert result_sum.identity() != result_avg.identity()
    assert result_sum.aggregation_rule_id == "AGR-PROD-SUM"
    assert result_avg.aggregation_rule_id == "AGR-PROD-AVG"
    assert result_sum.value != result_avg.value
    assert result_sum.value == pytest.approx(sum(values.values()))
    assert result_avg.value == pytest.approx(
        sum(values.values()) / len(values)
    )


# ============================================================
# A11 — Preservação de scope
# ============================================================


def test_a11_scope_is_preserved_and_never_mixed():
    context = CalculationContext()

    values_l1 = _daily_range(
        date(2026, 9, 1), date(2026, 9, 5), start_value=1.0
    )
    values_l2 = _daily_range(
        date(2026, 9, 1), date(2026, 9, 5), start_value=100.0
    )

    _populate_daily(context, "VARDAILY", "linha", "L1", values_l1)
    _populate_daily(context, "VARDAILY", "linha", "L2", values_l2)

    rule = AggregationRule(
        aggregation_rule_id="AGR-SCOPE-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="SUM",
    )

    service = TemporalAggregationService()

    result_l1 = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 5),
    )

    result_l2 = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L2",
        run_date=date(2026, 9, 5),
    )

    assert result_l1.value == pytest.approx(sum(values_l1.values()))
    assert result_l2.value == pytest.approx(sum(values_l2.values()))
    assert result_l1.value != result_l2.value
    assert result_l1.scope_value == "L1"
    assert result_l2.scope_value == "L2"


# ============================================================
# A12 — Preservação de period
# ============================================================


def test_a12_period_is_preserved_across_different_run_dates():
    context = CalculationContext()

    values = _daily_range(
        date(2026, 9, 1), date(2026, 9, 20), start_value=1.0
    )
    _populate_daily(context, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-PERIOD-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="SUM",
    )

    service = TemporalAggregationService()

    result_day_10 = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 10),
    )

    result_day_20 = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 9, 20),
    )

    # Mesmo period_id (mesmo mês)...
    assert result_day_10.period_id == "2026-09"
    assert result_day_20.period_id == "2026-09"

    # ...mas janelas e valores diferentes (progressivo).
    assert result_day_10.value != result_day_20.value

    expected_day_10 = sum(
        v for d, v in values.items() if d <= date(2026, 9, 10)
    )
    expected_day_20 = sum(
        v for d, v in values.items() if d <= date(2026, 9, 20)
    )

    assert result_day_10.value == pytest.approx(expected_day_10)
    assert result_day_20.value == pytest.approx(expected_day_20)


# ============================================================
# A13 — Agregação anual ponderada (fixture mínimo, variável não
# presente no seed real)
# ============================================================


def test_a13_annual_weighted_average_with_synthetic_fixture():
    """
    Reproduz o exemplo da Fase B (yield_lth_total diário ponderado
    por producao_planta -> anual). yield_lth_total/producao_planta
    não existem no seed real do Yield — usamos IDs sintéticos
    exclusivamente para provar o mecanismo, sem alterar o seed de
    negócio.
    """

    context = CalculationContext()

    day_values = {
        date(2026, 1, 1): 50.0,
        date(2026, 1, 2): 60.0,
        date(2026, 1, 3): 70.0,
    }
    day_weights = {
        date(2026, 1, 1): 10.0,
        date(2026, 1, 2): 20.0,
        date(2026, 1, 3): 30.0,
    }

    _populate_daily(
        context, "VARSYN_YIELD_LTH", "linha", "L4", day_values
    )
    _populate_daily(
        context, "VARSYN_PROD_PLANTA", "linha", "L4", day_weights
    )

    rule = AggregationRule(
        aggregation_rule_id="AGR-YIELD-LTH-ANNUAL-WAVG",
        source_variable_id="VARSYN_YIELD_LTH",
        source_frequency="diário",
        target_variable_id="VARSYN_YIELD_LTH_ANNUAL",
        target_frequency="anual",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARSYN_PROD_PLANTA",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L4",
        run_date=date(2026, 1, 3),
    )

    expected = (50 * 10 + 60 * 20 + 70 * 30) / (10 + 20 + 30)

    assert result.frequency == "anual"
    assert result.period_id == "2026"
    assert result.value == pytest.approx(expected)


# ============================================================
# A14 — Equation DIRECT anual continua funcionando (sem
# AggregationRule/AggregationService envolvidos)
# ============================================================


def test_a14_direct_annual_equation_still_works_without_aggregation():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR20100", "yield_base", "x", "-", "calculado",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )
    variable_definition_registry.add(
        VariableDefinition(
            "VAR20101", "input_a", "x", "-", "entrada",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )

    equation_definition_registry = EquationDefinitionRegistry()
    equation_definition_registry.add(
        EquationDefinition(
            "EQ20100", "VAR20100", 1, "linha", "L1_L7",
            "VAR20101 * 3", "test", "PUBLISHED",
        )
    )

    context = CalculationContext()

    for line in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        context.set_variable_value(
            variable_id="VAR20101",
            value=10.0,
            scope_type="linha",
            scope_value=line,
        )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definition_registry,
        calculation_context=context,
        variable_definition_registry=variable_definition_registry,
        run_date=date(2026, 9, 14),
    )

    assert len(results) == 7

    assert context.get_variable_value(
        variable_id="VAR20100",
        scope_type="linha",
        scope_value="L1",
        period_id="2026",
    ) == 30.0


# ============================================================
# A15 — Year transition: sem vazamento entre ForecastYears
# ============================================================


def test_a15_year_transition_does_not_leak_values_across_years():
    context = CalculationContext()

    # Dezembro/2026 com um valor propositalmente muito diferente.
    december_values = _daily_range(
        date(2026, 12, 1), date(2026, 12, 31), start_value=999.0
    )
    _populate_daily(
        context, "VARDAILY", "linha", "L1", december_values
    )

    # Janeiro/2027 com valores reais do cenário sob teste.
    january_values = {
        date(2027, 1, 1): 10.0,
        date(2027, 1, 2): 10.0,
        date(2027, 1, 3): 10.0,
        date(2027, 1, 4): 10.0,
        date(2027, 1, 5): 10.0,
        date(2027, 1, 6): 10.0,
        date(2027, 1, 7): 10.0,
        date(2027, 1, 8): 10.0,
        date(2027, 1, 9): 10.0,
        date(2027, 1, 10): 10.0,
        date(2027, 1, 11): 10.0,
        date(2027, 1, 12): 10.0,
        date(2027, 1, 13): 10.0,
        date(2027, 1, 14): 10.0,
        date(2027, 1, 15): 10.0,
    }
    _populate_daily(
        context, "VARDAILY", "linha", "L1", january_values
    )

    rule = AggregationRule(
        aggregation_rule_id="AGR-YEAR-TRANSITION-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2027, 1, 15),
    )

    assert result.forecast_year == 2027
    assert result.period_id == "2027-01"
    # Se algum dia de dezembro/2026 tivesse vazado para a janela,
    # a média não seria exatamente 10.0.
    assert result.value == pytest.approx(10.0)


def test_a15_previous_december_aggregation_is_unaffected_too():
    """
    Confirma a simetria: uma agregação de dezembro/2026 (executada
    antes da virada) também não é afetada por dados de
    janeiro/2027 — a fronteira de ForecastYear funciona nos dois
    sentidos.
    """

    context = CalculationContext()

    december_values = _daily_range(
        date(2026, 12, 1), date(2026, 12, 31), start_value=5.0, step=0.0
    )
    _populate_daily(
        context, "VARDAILY", "linha", "L1", december_values
    )

    rule = AggregationRule(
        aggregation_rule_id="AGR-YEAR-TRANSITION-002",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2026, 12, 31),
    )

    assert result.forecast_year == 2026
    assert result.period_id == "2026-12"
    assert result.value == pytest.approx(5.0)


# ============================================================
# Validação da AggregationRule
# ============================================================


def test_aggregation_rule_rejects_unsupported_type():
    with pytest.raises(InvalidAggregationRuleError):
        AggregationRule(
            aggregation_rule_id="AGR-INVALID-001",
            source_variable_id="VARX",
            source_frequency="diário",
            target_variable_id="VARY",
            target_frequency="mensal",
            aggregation_type="MEDIAN",
        )


def test_aggregation_rule_requires_weight_variable_for_weighted_average():
    with pytest.raises(InvalidAggregationRuleError):
        AggregationRule(
            aggregation_rule_id="AGR-INVALID-002",
            source_variable_id="VARX",
            source_frequency="diário",
            target_variable_id="VARY",
            target_frequency="mensal",
            aggregation_type="WEIGHTED_AVERAGE",
        )


def test_aggregation_rule_rejects_partial_explicit_window():
    with pytest.raises(InvalidAggregationRuleError):
        AggregationRule(
            aggregation_rule_id="AGR-INVALID-003",
            source_variable_id="VARX",
            source_frequency="diário",
            target_variable_id="VARY",
            target_frequency="mensal",
            aggregation_type="MOVING_AVERAGE",
            window_start_date=date(2026, 9, 1),
        )


def test_aggregation_rule_rejects_inverted_explicit_window():
    with pytest.raises(InvalidAggregationRuleError):
        AggregationRule(
            aggregation_rule_id="AGR-INVALID-004",
            source_variable_id="VARX",
            source_frequency="diário",
            target_variable_id="VARY",
            target_frequency="mensal",
            aggregation_type="MOVING_AVERAGE",
            window_start_date=date(2026, 9, 14),
            window_end_date=date(2026, 9, 1),
        )


def test_aggregate_raises_when_a_source_day_is_missing():
    """
    Se um sub-período dentro da janela não foi calculado/armazenado,
    o serviço propaga o erro explicitamente (fail-fast), em vez de
    ignorar o dia silenciosamente ou tratá-lo como zero.
    """

    context = CalculationContext()

    rule = AggregationRule(
        aggregation_rule_id="AGR-MISSING-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    with pytest.raises(VariableNotFoundError):
        service.aggregate(
            rule=rule,
            calculation_context=context,
            scope_type="linha",
            scope_value="L1",
            run_date=date(2026, 9, 14),
        )


def test_aggregate_raises_empty_window_error_when_run_date_precedes_explicit_window():
    """
    Uma janela explícita (MOVING_AVERAGE) cujo run_date é anterior a
    `window_start_date` produz uma janela efetiva vazia — nenhum
    period_id de origem a enumerar. O serviço reporta isso de forma
    explícita (EmptyAggregationWindowError), nunca com um resultado
    arbitrário como zero.
    """

    context = CalculationContext()

    rule = AggregationRule(
        aggregation_rule_id="AGR-EMPTY-001",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARMONTHLY",
        target_frequency="mensal",
        aggregation_type="MOVING_AVERAGE",
        window_start_date=date(2026, 9, 1),
        window_end_date=date(2026, 9, 14),
    )

    service = TemporalAggregationService()

    with pytest.raises(EmptyAggregationWindowError):
        service.aggregate(
            rule=rule,
            calculation_context=context,
            scope_type="linha",
            scope_value="L1",
            run_date=date(2026, 8, 1),
        )


# ============================================================
# Integração — seed real do Yield (106 EquationDefinitions, 166
# EquationInstances, inalteradas). A camada de agregação opera sobre
# resultados diários já calculados pelo ForecastEngine, sem tocar em
# nenhuma EquationDefinition.
# ============================================================


def test_yield_real_seed_preserved_and_aggregated_on_top_of_results():
    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions,
        _vi,
        _parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loader.load_all_definitions_and_instances()

    # O seed do Yield inclui, desde a implementação do v4
    # (EquationDefinitions L1_L7 + AggregationRules), 138
    # EquationDefinitions (106 originais + 32 novas de
    # linha_grupo/L1_L7 diário/anual) e 198 EquationInstances
    # (166 originais + 32, já que L1_L7 é escopo singular, sem
    # materialização por linha). As 106 originais não foram
    # alteradas — apenas adições.
    assert len(equation_definitions.all()) == 138
    assert len(equation_instances.all()) == 198

    context = CalculationContext()

    _populate_yield_context(context, variable_definitions)

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(
            instance,
            instance.value,
        )

    engine = ForecastEngine()

    # Simula 14 execuções diárias (mesmos inputs em cada dia, o que
    # é suficiente para provar o mecanismo de agregação) — a cadeia
    # real tanque_base -> tanque -> n_ppt -> ratio_spent -> yield ->
    # yield linha_grupo é recalculada, ponta a ponta, a cada dia.
    for day in range(1, 15):
        run_date = date(2026, 9, day)

        results = engine.calculate_from_definition_registry(
            equation_definition_registry=equation_definitions,
            calculation_context=context,
            variable_definition_registry=variable_definitions,
            run_date=run_date,
        )

        assert len(results) == len(equation_instances.all())

    # yield@L4 (VAR11001) foi calculado e armazenado para cada um
    # dos 14 dias, sob seu próprio period_id diário.
    daily_yield_l4 = context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L4",
        period_id="2026-09-14",
    )
    assert isinstance(daily_yield_l4, (int, float))

    # A camada de agregação (Fase B) deriva um yield mensal a partir
    # dos 14 resultados diários já calculados pelo Yield real —
    # nenhuma EquationDefinition participa desta etapa.
    rule = AggregationRule(
        aggregation_rule_id="AGR-YIELD-L4-MONTHLY-AVG",
        source_variable_id="VAR11001",
        source_frequency="diário",
        target_variable_id="VAR11001",
        target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    service = TemporalAggregationService()

    result = service.aggregate(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L4",
        run_date=date(2026, 9, 14),
    )

    assert result.period_id == "2026-09"
    assert result.frequency == "mensal"
    # Os inputs são idênticos em todos os 14 dias, logo a média
    # mensal deve ser exatamente igual ao valor diário.
    assert result.value == pytest.approx(daily_yield_l4)

    # A cadeia estrutural do Yield permanece intacta: a agregação
    # linha_grupo (produzida por uma das 106 EquationDefinitions
    # reais) continua disponível normalmente, sob o period_id diário.
    yield_l1_l3 = context.get_variable_value(
        variable_id="VAR11016",
        scope_type="linha_grupo",
        scope_value="L1_L3",
        period_id="2026-09-14",
    )
    assert isinstance(yield_l1_l3, (int, float))
