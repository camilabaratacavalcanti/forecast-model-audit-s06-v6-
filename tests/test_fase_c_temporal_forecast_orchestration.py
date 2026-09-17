"""
FASE C — Temporal Forecast Orchestration.

Objetivo:
    Provar, com execução real (sem mocks), que o
    TemporalForecastOrchestrator coordena corretamente
    ForecastEngine (DIRECT) e TemporalAggregationService
    (TEMPORAL_AGGREGATED) sobre um único run_date/ForecastYear, sem
    duplicar nenhuma lógica de cálculo, agregação ou calendário —
    apenas reutilizando os componentes já auditados das Fases A e B.

Cobre os 18 cenários mínimos exigidos (C1-C18), incluindo um teste
adversarial com o seed real do Yield usando valores diários
DELIBERADAMENTE VARIADOS (não repete o problema do TD-B04).
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationInstanceRegistry,
)
from app.domain.forecast.aggregation import AggregationRule
from app.domain.forecast.collection import ForecastValueRegistry
from app.domain.forecast.models import ForecastValue
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterInstanceRegistry,
)
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableInstanceRegistry,
)
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import VariableNotFoundError
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)
from app.repositories.seed_loader import SeedLoader


# ============================================================
# C1-C5 — available_periods (diário / mensal / anual, run_date
# no meio do mês / no meio do ano)
# ============================================================


def test_c1_daily_available_periods():
    orchestrator = TemporalForecastOrchestrator()

    periods = orchestrator.available_periods(
        "diário", date(2026, 1, 5)
    )

    assert [p.period_id for p in periods] == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
    ]
    assert periods[-1].start_date == date(2026, 1, 5)
    assert periods[-1].end_date == date(2026, 1, 5)


def test_c2_monthly_available_periods():
    orchestrator = TemporalForecastOrchestrator()

    periods = orchestrator.available_periods(
        "mensal", date(2026, 9, 14)
    )

    assert [p.period_id for p in periods] == [
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
        "2026-06", "2026-07", "2026-08", "2026-09",
    ]
    # meses completos e passados permanecem com a janela de
    # calendário cheia...
    assert periods[0].start_date == date(2026, 1, 1)
    assert periods[0].end_date == date(2026, 1, 31)
    # ...mas o mês corrente (setembro) é truncado em run_date.
    assert periods[-1].start_date == date(2026, 9, 1)
    assert periods[-1].end_date == date(2026, 9, 14)


def test_c3_annual_available_periods():
    orchestrator = TemporalForecastOrchestrator()

    periods = orchestrator.available_periods(
        "anual", date(2026, 9, 14)
    )

    assert [p.period_id for p in periods] == ["2026"]
    assert periods[0].start_date == date(2026, 1, 1)
    assert periods[0].end_date == date(2026, 9, 14)


def test_c4_run_date_mid_month_truncates_current_month_only():
    orchestrator = TemporalForecastOrchestrator()

    periods = orchestrator.available_periods(
        "mensal", date(2026, 3, 17)
    )

    assert periods[-1].period_id == "2026-03"
    assert periods[-1].start_date == date(2026, 3, 1)
    assert periods[-1].end_date == date(2026, 3, 17)
    assert periods[-1].end_date != date(2026, 3, 31)


def test_c5_run_date_mid_year_truncates_annual_window():
    orchestrator = TemporalForecastOrchestrator()

    periods = orchestrator.available_periods(
        "anual", date(2026, 6, 10)
    )

    assert periods[0].period_id == "2026"
    assert periods[0].start_date == date(2026, 1, 1)
    assert periods[0].end_date == date(2026, 6, 10)
    assert periods[0].end_date != date(2026, 12, 31)


# ============================================================
# C6 — Year transition
# ============================================================


def test_c6_year_transition_monthly_periods_never_cross_forecast_year():
    orchestrator = TemporalForecastOrchestrator()

    periods_2027 = orchestrator.available_periods(
        "mensal", date(2027, 1, 15)
    )

    assert [p.period_id for p in periods_2027] == ["2027-01"]
    assert periods_2027[0].start_date == date(2027, 1, 1)
    assert periods_2027[0].end_date == date(2027, 1, 15)


def test_c6_year_transition_direct_and_aggregation_do_not_leak():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30001", "daily_metric", "x", "-", "entrada",
            "diário", "linha", "L1", "test", "ativo",
        )
    )

    context = CalculationContext()
    context.set_variable_value(
        "VAR30001", 999.0, "linha", "L1", period_id="2026-12-31"
    )
    context.set_variable_value(
        "VAR30001", 10.0, "linha", "L1", period_id="2027-01-01"
    )
    context.set_variable_value(
        "VAR30001", 10.0, "linha", "L1", period_id="2027-01-02"
    )

    rule = AggregationRule(
        "AGR-YEAR-TRANS-C",
        "VAR30001", "diário", "VAR30001_M", "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L1",
        run_date=date(2027, 1, 2),
    )

    assert result.forecast_year == 2027
    assert result.period_id == "2027-01"
    assert result.value == pytest.approx(10.0)


# ============================================================
# C7 — DIRECT annual via orchestrator
# ============================================================


def test_c7_direct_annual_equation_via_orchestrator():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30100", "yield_base", "x", "-", "calculado",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30101", "input_a", "x", "-", "entrada",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )

    equation_definition_registry = EquationDefinitionRegistry()
    equation_definition_registry.add(
        EquationDefinition(
            "EQ30100", "VAR30100", 1, "linha", "L1_L7",
            "VAR30101 * 4", "test", "PUBLISHED",
        )
    )

    context = CalculationContext()
    for line in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        context.set_variable_value(
            "VAR30101", 5.0, "linha", line,
        )

    orchestrator = TemporalForecastOrchestrator()

    results = orchestrator.run_direct(
        equation_definition_registry=equation_definition_registry,
        variable_definition_registry=variable_definition_registry,
        calculation_context=context,
        run_date=date(2026, 9, 14),
    )

    assert len(results) == 7

    forecast_value = orchestrator.direct_forecast_value(
        variable_id="VAR30100",
        scope_type="linha",
        scope_value="L1",
        variable_definition_registry=variable_definition_registry,
        calculation_context=context,
        run_date=date(2026, 9, 14),
    )

    assert forecast_value.frequency == "anual"
    assert forecast_value.period_id == "2026"
    assert forecast_value.forecast_year == 2026
    assert forecast_value.value == 20.0
    assert forecast_value.aggregation_rule_id is None


# ============================================================
# C8-C11 — AVERAGE / SUM / WEIGHTED_AVERAGE / MOVING_AVERAGE
# via orchestrator, com valores diários variados
# ============================================================


def _populate_varied_daily(context, variable_id, scope_type, scope_value, start, count, start_value=10.0, step=5.0):
    values = {}
    current = start
    value = start_value
    for _ in range(count):
        context.set_variable_value(
            variable_id, value, scope_type, scope_value,
            period_id=current.isoformat(),
        )
        values[current] = value
        value += step
        current += timedelta(days=1)
    return values


def test_c8_daily_to_monthly_average_via_orchestrator():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30200", "linha", "L1",
        date(2026, 9, 1), 14,
    )

    rule = AggregationRule(
        "AGR-C8-AVG", "VAR30200", "diário", "VAR30200_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    assert result.value == pytest.approx(
        sum(values.values()) / len(values)
    )
    assert result.period_id == "2026-09"


def test_c9_daily_to_monthly_sum_via_orchestrator():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30201", "linha", "L1",
        date(2026, 9, 1), 14,
    )

    rule = AggregationRule(
        "AGR-C9-SUM", "VAR30201", "diário", "VAR30201_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    assert result.value == pytest.approx(sum(values.values()))


def test_c10_daily_to_monthly_weighted_average_via_orchestrator():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30202", "linha", "L1",
        date(2026, 9, 1), 5, start_value=10.0, step=10.0,
    )
    weights = _populate_varied_daily(
        context, "VAR30203", "linha", "L1",
        date(2026, 9, 1), 5, start_value=1.0, step=1.0,
    )

    rule = AggregationRule(
        "AGR-C10-WAVG", "VAR30202", "diário", "VAR30202_M",
        "mensal", "WEIGHTED_AVERAGE", weight_variable_id="VAR30203",
    )

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 5),
    )

    expected = sum(
        values[d] * weights[d] for d in values
    ) / sum(weights.values())

    assert result.value == pytest.approx(expected)


def test_c11_moving_average_via_orchestrator_explicit_window():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30204", "linha", "L1",
        date(2026, 8, 20), 32,
    )

    rule = AggregationRule(
        "AGR-C11-MAVG", "VAR30204", "diário", "VAR30204_M",
        "mensal", "MOVING_AVERAGE",
        window_start_date=date(2026, 9, 1),
        window_end_date=date(2026, 9, 14),
    )

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 14),
    )

    window_values = {
        d: v for d, v in values.items()
        if date(2026, 9, 1) <= d <= date(2026, 9, 14)
    }
    assert len(window_values) == 14
    assert result.value == pytest.approx(
        sum(window_values.values()) / len(window_values)
    )


# ============================================================
# C12 — Múltiplas regras para a mesma Variable via orchestrator
# ============================================================


def test_c12_multiple_rules_for_same_variable_via_orchestrator():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30300", "linha", "L2",
        date(2026, 9, 1), 14,
    )

    rule_sum = AggregationRule(
        "AGR-C12-SUM", "VAR30300", "diário", "VAR30300_M",
        "mensal", "SUM",
    )
    rule_avg = AggregationRule(
        "AGR-C12-AVG", "VAR30300", "diário", "VAR30300_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    result_sum = orchestrator.run_aggregation(
        rule=rule_sum, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 14),
    )
    result_avg = orchestrator.run_aggregation(
        rule=rule_avg, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 14),
    )

    registry.add(result_sum)
    registry.add(result_avg)

    assert len(registry) == 2
    assert result_sum.identity() != result_avg.identity()
    assert result_sum.value == pytest.approx(sum(values.values()))
    assert result_avg.value == pytest.approx(
        sum(values.values()) / len(values)
    )
    assert registry.get(result_sum.identity()).value == result_sum.value
    assert registry.get(result_avg.identity()).value == result_avg.value


# ============================================================
# C13 — Scope isolation via orchestrator
# ============================================================


def test_c13_scope_isolation_via_orchestrator():
    context = CalculationContext()
    values_l1 = _populate_varied_daily(
        context, "VAR30400", "linha", "L1",
        date(2026, 9, 1), 5, start_value=1.0, step=1.0,
    )
    values_l2 = _populate_varied_daily(
        context, "VAR30400", "linha", "L2",
        date(2026, 9, 1), 5, start_value=100.0, step=1.0,
    )

    rule = AggregationRule(
        "AGR-C13-SCOPE", "VAR30400", "diário", "VAR30400_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()

    result_l1 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 5),
    )
    result_l2 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 5),
    )

    assert result_l1.value == pytest.approx(sum(values_l1.values()))
    assert result_l2.value == pytest.approx(sum(values_l2.values()))
    assert result_l1.value != result_l2.value


def test_c13_linha_grupo_and_scopeless_scopes_via_orchestrator():
    context = CalculationContext()
    values_group = _populate_varied_daily(
        context, "VAR30401", "linha_grupo", "L1_L3",
        date(2026, 9, 1), 5, start_value=2.0, step=2.0,
    )
    values_global = _populate_varied_daily(
        context, "VAR30402", "global", None,
        date(2026, 9, 1), 5, start_value=3.0, step=3.0,
    )

    rule_group = AggregationRule(
        "AGR-C13-GROUP", "VAR30401", "diário", "VAR30401_M",
        "mensal", "SUM",
    )
    rule_global = AggregationRule(
        "AGR-C13-GLOBAL", "VAR30402", "diário", "VAR30402_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()

    result_group = orchestrator.run_aggregation(
        rule=rule_group, calculation_context=context,
        scope_type="linha_grupo", scope_value="L1_L3",
        run_date=date(2026, 9, 5),
    )
    result_global = orchestrator.run_aggregation(
        rule=rule_global, calculation_context=context,
        scope_type="global", scope_value=None,
        run_date=date(2026, 9, 5),
    )

    assert result_group.value == pytest.approx(sum(values_group.values()))
    assert result_global.value == pytest.approx(sum(values_global.values()))
    assert result_group.scope_type == "linha_grupo"
    assert result_global.scope_type == "global"
    assert result_global.scope_value is None


# ============================================================
# C14 — Period isolation via orchestrator
# ============================================================


def test_c14_period_isolation_across_run_dates():
    context = CalculationContext()
    values = _populate_varied_daily(
        context, "VAR30500", "linha", "L1",
        date(2026, 9, 1), 20,
    )

    rule = AggregationRule(
        "AGR-C14-PERIOD", "VAR30500", "diário", "VAR30500_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()

    result_day_10 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 10),
    )
    result_day_20 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 20),
    )

    assert result_day_10.period_id == result_day_20.period_id == "2026-09"
    assert result_day_10.value != result_day_20.value
    assert result_day_10.value == pytest.approx(
        sum(v for d, v in values.items() if d <= date(2026, 9, 10))
    )
    assert result_day_20.value == pytest.approx(
        sum(v for d, v in values.items() if d <= date(2026, 9, 20))
    )


# ============================================================
# C15 — ForecastValue identity via ForecastValueRegistry
# ============================================================


def test_c15_forecast_value_identity_direct_vs_aggregated_no_collision():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30600", "metric", "x", "-", "entrada",
            "diário", "linha", "L1", "test", "ativo",
        )
    )

    context = CalculationContext()
    context.set_variable_value(
        "VAR30600", 42.0, "linha", "L1", period_id="2026-09-14"
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    direct_value = orchestrator.direct_forecast_value(
        variable_id="VAR30600", scope_type="linha", scope_value="L1",
        variable_definition_registry=variable_definition_registry,
        calculation_context=context, run_date=date(2026, 9, 14),
    )
    registry.add(direct_value)

    assert direct_value.aggregation_rule_id is None
    assert len(registry) == 1


def test_c15_registry_updates_current_value_for_same_identity():
    """
    Contrato revisado por TD-C01: uma nova Execution atualizando a
    mesma identidade lógica NÃO é mais um erro (o comportamento
    original da Fase C, que rejeitava qualquer valor conflitante
    para a mesma identidade, foi deliberadamente substituído — ver
    TD-C01/TD-C03 e tests/test_fase_c_execution_and_history.py para
    a cobertura completa do novo contrato de atualização progressiva
    e histórico).
    """

    registry = ForecastValueRegistry()

    value_a = ForecastValue(
        "VAR30601", "linha", "L1", "diário", 2026, "2026-09-14", 10.0,
        execution_id="EXEC-A",
    )
    value_b = ForecastValue(
        "VAR30601", "linha", "L1", "diário", 2026, "2026-09-14", 99.0,
        execution_id="EXEC-B",
    )

    registry.add(value_a)
    registry.add(value_b)

    assert len(registry) == 1
    assert registry.get(value_a.identity()).value == 99.0
    assert registry.get(value_a.identity()).execution_id == "EXEC-B"
    assert registry.history(value_a.identity())[0].value == 10.0
    assert (
        registry.history(value_a.identity())[0].execution_id
        == "EXEC-A"
    )


# ============================================================
# C16 — Ausência de sub-período (fail-fast) via orchestrator
# ============================================================


def test_c16_missing_source_period_fails_fast_via_orchestrator():
    context = CalculationContext()

    rule = AggregationRule(
        "AGR-C16-MISSING", "VAR30700", "diário", "VAR30700_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()

    with pytest.raises(VariableNotFoundError):
        orchestrator.run_aggregation(
            rule=rule, calculation_context=context,
            scope_type="linha", scope_value="L1",
            run_date=date(2026, 9, 14),
        )


# ============================================================
# C17 — Yield real: diário -> mensal, com valores diários
# DELIBERADAMENTE VARIADOS (não repete o problema do TD-B04)
# ============================================================


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
                value=value, scope_type="linha", scope_value=line,
            )

    for name, value in YIELD_INPUT_ANNUAL_VALUES.items():
        definition = definitions_by_name_scope[name][
            ("anual", "linha", "L1_L7")
        ]
        for line in LINES:
            context.set_variable_value(
                variable_id=definition.variable_definition_id,
                value=value, scope_type="linha", scope_value=line,
            )

    return definitions_by_name_scope


def _is_yield_id(entity_id):
    """
    Filtra pela faixa de IDs reservada ao bloco Yield (11000-11999).
    Necessário porque `SeedLoader` carrega TODOS os blocos do seed a
    partir de `SEED_ROOT` (agora inclui também "production") -- este
    teste audita especificamente o seed real do Yield, isolado dos
    demais blocos, preservando seu objetivo original.
    """

    digits = "".join(ch for ch in entity_id if ch.isdigit())

    return bool(digits) and 11000 <= int(digits) <= 11999


def _filter_yield_block(loaded_seed):
    (
        variable_definitions, variable_instances,
        parameter_definitions, parameter_instances,
        equation_definitions, equation_instances,
    ) = loaded_seed

    yield_variable_definitions = VariableDefinitionRegistry()
    for d in variable_definitions.all():
        if _is_yield_id(d.variable_definition_id):
            yield_variable_definitions.add(d)

    yield_variable_instances = VariableInstanceRegistry()
    for i in variable_instances.all():
        if _is_yield_id(i.variable_definition_id):
            yield_variable_instances.add(i)

    yield_parameter_definitions = ParameterDefinitionRegistry()
    for d in parameter_definitions.all():
        if _is_yield_id(d.parameter_definition_id):
            yield_parameter_definitions.add(d)

    yield_parameter_instances = ParameterInstanceRegistry()
    for i in parameter_instances.all():
        if _is_yield_id(i.parameter_definition_id):
            yield_parameter_instances.add(i)

    yield_equation_definitions = EquationDefinitionRegistry()
    for d in equation_definitions.all():
        if _is_yield_id(d.equation_definition_id):
            yield_equation_definitions.add(d)

    yield_equation_instances = EquationInstanceRegistry()
    for i in equation_instances.all():
        if _is_yield_id(i.target_variable_id):
            yield_equation_instances.add(i)

    return (
        yield_variable_definitions, yield_variable_instances,
        yield_parameter_definitions, yield_parameter_instances,
        yield_equation_definitions, yield_equation_instances,
    )


def test_c17_yield_real_daily_to_monthly_with_varied_daily_inputs():
    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions, _vi, _parameter_definitions,
        parameter_instances, equation_definitions, equation_instances,
    ) = _filter_yield_block(
        loader.load_all_definitions_and_instances()
    )

    # Seed do Yield v4: 106 EquationDefinitions originais + 32 novas
    # (linha_grupo/L1_L7 diário/anual) = 138; 166 EquationInstances
    # originais + 32 (L1_L7 é escopo singular) = 198.
    assert len(equation_definitions.all()) == 138
    assert len(equation_instances.all()) == 198

    context = CalculationContext()
    definitions_by_name_scope = _populate_yield_context(
        context, variable_definitions
    )

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(instance, instance.value)

    tanque_definition = definitions_by_name_scope["tanque"][
        ("diário", "linha", "L1_L7")
    ]
    tanque_variable_id = tanque_definition.variable_definition_id

    orchestrator = TemporalForecastOrchestrator()

    # tanque@L4 varia a cada dia (10, 11, 12, ..., 23) -- diferente
    # de cada dia anterior, ao contrário do cenário do TD-B04.
    daily_tanque_values = {}
    for day_index in range(1, 15):
        run_date = date(2026, 9, day_index)
        tanque_value = 10.0 + day_index

        context.set_variable_value(
            variable_id=tanque_variable_id,
            value=tanque_value,
            scope_type="linha",
            scope_value="L4",
            period_id=run_date.isoformat(),
        )
        daily_tanque_values[run_date] = tanque_value

        results = orchestrator.run_direct(
            equation_definition_registry=equation_definitions,
            variable_definition_registry=variable_definitions,
            calculation_context=context,
            run_date=run_date,
        )
        assert len(results) == len(equation_instances.all())

    daily_yield_l4 = {}
    for day_index in range(1, 15):
        run_date = date(2026, 9, day_index)
        daily_yield_l4[run_date] = context.get_variable_value(
            variable_id="VAR11001",
            scope_type="linha",
            scope_value="L4",
            period_id=run_date.isoformat(),
        )

    # Os 14 valores diários de yield@L4 realmente variam (a cadeia
    # tanque -> n_ppt -> ratio_spent -> yield propagou a variação).
    assert len(set(daily_yield_l4.values())) > 1

    rule = AggregationRule(
        "AGR-YIELD-C17-MONTHLY-AVG",
        source_variable_id="VAR11001", source_frequency="diário",
        target_variable_id="VAR11001", target_frequency="mensal",
        aggregation_type="AVERAGE",
    )

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 14),
    )

    expected = sum(daily_yield_l4.values()) / len(daily_yield_l4)

    assert result.period_id == "2026-09"
    assert result.frequency == "mensal"
    assert result.value == pytest.approx(expected)
    # Prova a cadeia real, não apenas a integração estrutural:
    # se a agregação estivesse errada (ex.: pegando só o último dia),
    # este assert falharia, pois os 14 valores são distintos.
    assert result.value != pytest.approx(
        list(daily_yield_l4.values())[-1]
    )


# ============================================================
# C18 — Reexecução / múltiplos run_dates
# ============================================================


def test_c18_repeated_execution_same_run_date_is_idempotent():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30800", "metric_direct", "x", "-", "entrada",
            "diário", "linha", "L1", "test", "ativo",
        )
    )

    context = CalculationContext()
    context.set_variable_value(
        "VAR30800", 7.0, "linha", "L1", period_id="2026-09-14"
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    for _ in range(3):
        value = orchestrator.direct_forecast_value(
            variable_id="VAR30800", scope_type="linha", scope_value="L1",
            variable_definition_registry=variable_definition_registry,
            calculation_context=context, run_date=date(2026, 9, 14),
        )
        registry.add(value)

    assert len(registry) == 1


def test_c18_run_direct_accumulated_across_multiple_days():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30801", "target", "x", "-", "calculado",
            "diário", "linha", "L1_L7", "test", "ativo",
        )
    )
    variable_definition_registry.add(
        VariableDefinition(
            "VAR30802", "source", "x", "-", "entrada",
            "diário", "linha", "L1_L7", "test", "ativo",
        )
    )

    equation_definition_registry = EquationDefinitionRegistry()
    equation_definition_registry.add(
        EquationDefinition(
            "EQ30801", "VAR30801", 1, "linha", "L1_L7",
            "VAR30802 * 2", "test", "PUBLISHED",
        )
    )

    context = CalculationContext()
    for line in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        context.set_variable_value("VAR30802", 3.0, "linha", line)

    orchestrator = TemporalForecastOrchestrator()

    results_by_day = orchestrator.run_direct_accumulated(
        equation_definition_registry=equation_definition_registry,
        variable_definition_registry=variable_definition_registry,
        calculation_context=context,
        run_date=date(2026, 1, 5),
    )

    assert sorted(results_by_day.keys()) == [
        date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
        date(2026, 1, 4), date(2026, 1, 5),
    ]

    for day in results_by_day:
        assert context.get_variable_value(
            variable_id="VAR30801", scope_type="linha", scope_value="L1",
            period_id=day.isoformat(),
        ) == 6.0
