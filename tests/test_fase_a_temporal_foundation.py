"""
FASE A — Fundação temporal mínima do Forecast Platform.

Objetivo:
    Provar, com execução real (sem mocks), que o motor existente
    passou a ser capaz de calcular por período (diário/mensal/anual),
    respeitando o run_date como limite da janela efetiva, sem quebrar
    nenhum dos contratos já estabelecidos:

        - frequency continua existindo apenas em VariableDefinition;
        - EquationDefinition/EquationInstance nunca carregam
          frequency;
        - ParameterDefinition/ParameterInstance nunca carregam
          frequency (um Parameter é constante dentro do ForecastYear);
        - DependencyGraph permanece espacial/estrutural, sem
          period_id nos nós;
        - "VAR@Lx" continua controlando apenas o espaço — o período
          vem sempre do contexto de execução, nunca de nova sintaxe;
        - uma equação anual (frequency="anual" na VariableDefinition
          alvo) é calculada diretamente, com period_id=YYYY, sem
          nenhuma agregação temporal (Fase B).

Este módulo cobre os 10 cenários mínimos exigidos para a Fase A, mais
um teste de integração usando o seed real do Yield (106
EquationDefinitions, inalteradas).
"""

from datetime import date
from pathlib import Path

import pytest

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.forecast_engine import ForecastEngine
from app.engine.run_context import RunContext
from app.engine.time_period_resolver import TimePeriodResolver
from app.repositories.seed_loader import SeedLoader


# ============================================================
# 1-3, 4-5 — TimePeriodResolver.effective_window
# ============================================================


def test_1_daily_effective_window():
    resolver = TimePeriodResolver()

    period = resolver.effective_window(
        frequency="diário",
        run_date=date(2026, 9, 14),
    )

    assert period.period_id == "2026-09-14"
    assert period.start_date == date(2026, 9, 14)
    assert period.end_date == date(2026, 9, 14)


def test_2_monthly_effective_window():
    resolver = TimePeriodResolver()

    period = resolver.effective_window(
        frequency="mensal",
        run_date=date(2026, 9, 14),
    )

    assert period.period_id == "2026-09"
    assert period.start_date == date(2026, 9, 1)
    assert period.end_date == date(2026, 9, 14)


def test_3_annual_effective_window():
    resolver = TimePeriodResolver()

    period = resolver.effective_window(
        frequency="anual",
        run_date=date(2026, 9, 14),
    )

    assert period.period_id == "2026"
    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 9, 14)


def test_4_progressive_monthly_window_never_extends_to_month_end():
    """
    A janela mensal efetiva nunca deve se estender até o fim do mês
    de calendário (2026-09-30) quando run_date é anterior a isso —
    diferente do comportamento de `resolve()`, que gera meses
    completos (ver test_partial_month_horizon).
    """

    resolver = TimePeriodResolver()

    period = resolver.effective_window(
        frequency="mensal",
        run_date=date(2026, 9, 14),
    )

    assert period.start_date == date(2026, 9, 1)
    assert period.end_date == date(2026, 9, 14)
    assert period.end_date != date(2026, 9, 30)


def test_5_progressive_annual_window_never_extends_to_year_end():
    resolver = TimePeriodResolver()

    period = resolver.effective_window(
        frequency="anual",
        run_date=date(2026, 9, 14),
    )

    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 9, 14)
    assert period.end_date != date(2026, 12, 31)


def test_effective_window_rejects_unsupported_frequency():
    resolver = TimePeriodResolver()

    with pytest.raises(ValueError, match="Unsupported frequency"):
        resolver.effective_window(
            frequency="semanal",
            run_date=date(2026, 9, 14),
        )


def test_existing_resolve_behavior_is_unchanged_by_annual_support():
    """
    Regressão explícita: adicionar "anual" a SUPPORTED_FREQUENCIES
    não pode alterar o comportamento já testado de resolve() para
    "mensal" (meses completos, mesmo em horizonte parcial).
    """

    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        "mensal",
        date(2027, 1, 15),
        date(2027, 3, 10),
    )

    assert periods[0].start_date == date(2027, 1, 1)
    assert periods[0].end_date == date(2027, 1, 31)
    assert periods[-1].start_date == date(2027, 3, 1)
    assert periods[-1].end_date == date(2027, 3, 31)


def test_resolve_supports_annual_frequency():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        "anual",
        date(2026, 1, 1),
        date(2027, 12, 31),
    )

    assert [p.period_id for p in periods] == ["2026", "2027"]
    assert periods[0].start_date == date(2026, 1, 1)
    assert periods[0].end_date == date(2026, 12, 31)


# ============================================================
# 6 — Escopo + período: VAR@L2 em period=2026-09-14
# ============================================================


def test_6_scope_and_period_resolve_var_at_l2_for_given_period():
    context = CalculationContext()

    context.set_variable_value(
        variable_id="VAR10001",
        value=42.0,
        scope_type="linha",
        scope_value="L2",
        period_id="2026-09-14",
    )

    # Um valor do mesmo VAR@L2, em outro período, não deve colidir.
    context.set_variable_value(
        variable_id="VAR10001",
        value=999.0,
        scope_type="linha",
        scope_value="L2",
        period_id="2026-09-13",
    )

    definition = EquationDefinition(
        "EQ10001", "VAR10002", 1, "linha", "L2", "VAR10001@L2",
        "test", "PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L2",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
        period_id="2026-09-14",
    )

    assert result == 42.0


# ============================================================
# 7 — Regressão de escopo explícito, com e sem período
# ============================================================


def _build_explicit_scope_instance():
    definition = EquationDefinition(
        "EQ10002", "VAR10099", 1, "linha", "L5",
        "VAR10001@L2 + VAR10001@L3", "test", "PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    return definition, instance


def test_7_explicit_scope_regression_without_period():
    context = CalculationContext()

    context.set_variable_value(
        "VAR10001", 20.0, scope_type="linha", scope_value="L2"
    )
    context.set_variable_value(
        "VAR10001", 30.0, scope_type="linha", scope_value="L3"
    )
    context.set_variable_value(
        "VAR10001", 100.0, scope_type="linha", scope_value="L5"
    )

    definition, instance = _build_explicit_scope_instance()

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 50.0


def test_7_explicit_scope_regression_with_period_unchanged():
    """
    O mesmo cenário, agora com um período de execução informado: o
    resultado deve permanecer 50 — "VAR@L2" continua significando L2
    independentemente do escopo L5 da própria instance e
    independentemente de haver ou não período informado.
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR10001",
        20.0,
        scope_type="linha",
        scope_value="L2",
        period_id="2026-09-14",
    )
    context.set_variable_value(
        "VAR10001",
        30.0,
        scope_type="linha",
        scope_value="L3",
        period_id="2026-09-14",
    )
    context.set_variable_value(
        "VAR10001",
        100.0,
        scope_type="linha",
        scope_value="L5",
        period_id="2026-09-14",
    )

    definition, instance = _build_explicit_scope_instance()

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
        period_id="2026-09-14",
    )

    assert result == 50.0


# ============================================================
# 8 — Isolamento de Parameter por ForecastYear
# ============================================================


def test_8_parameter_year_isolation():
    context = CalculationContext()

    context.set_parameter_value(
        "PARAM10001",
        10.0,
        scope_type="global",
        scope_value=None,
        period_id="2026",
    )
    context.set_parameter_value(
        "PARAM10001",
        20.0,
        scope_type="global",
        scope_value=None,
        period_id="2027",
    )

    assert context.get_parameter_value(
        "PARAM10001",
        scope_type="global",
        scope_value=None,
        period_id="2026",
    ) == 10.0

    assert context.get_parameter_value(
        "PARAM10001",
        scope_type="global",
        scope_value=None,
        period_id="2027",
    ) == 20.0


def test_8_parameter_year_isolation_through_expression_evaluator():
    """
    Um Parameter referenciado dentro de uma expressão, calculada em
    um período diário/mensal, deve resolver para o valor do
    ForecastYear correspondente (o Parameter não tem granularidade
    diária/mensal própria — apenas anual).
    """

    context = CalculationContext()

    context.set_parameter_value(
        "PARAM10001",
        10.0,
        scope_type="linha",
        scope_value="L2",
        period_id="2026",
    )
    context.set_parameter_value(
        "PARAM10001",
        99.0,
        scope_type="linha",
        scope_value="L2",
        period_id="2027",
    )

    definition = EquationDefinition(
        "EQ10003", "VAR10098", 1, "linha", "L2", "PARAM10001",
        "test", "PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L2",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
        # period_id diário DENTRO do ano 2026: o Parameter deve
        # resolver o valor do ano 2026, não falhar por não existir
        # um valor diário exato.
        period_id="2026-09-14",
    )

    assert result == 10.0


# ============================================================
# 9 — Anual DIRECT (sem AggregationService)
# ============================================================


def test_9_annual_equation_is_calculated_direct_with_year_period_id():
    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR10100", "yield_base", "x", "-", "calculado",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )
    variable_definition_registry.add(
        VariableDefinition(
            "VAR10101", "input_a", "x", "-", "entrada",
            "anual", "linha", "L1_L7", "test", "ativo",
        )
    )

    equation_definition_registry = EquationDefinitionRegistry()
    equation_definition_registry.add(
        EquationDefinition(
            "EQ10100", "VAR10100", 1, "linha", "L1_L7",
            "VAR10101 * 2", "test", "PUBLISHED",
        )
    )

    context = CalculationContext()

    for line in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        context.set_variable_value(
            variable_id="VAR10101",
            value=100.0,
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

    for line in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        assert context.get_variable_value(
            variable_id="VAR10100",
            scope_type="linha",
            scope_value=line,
            period_id="2026",
        ) == 200.0


# ============================================================
# 10 — Transição de ForecastYear
# ============================================================


def test_10_forecast_year_transition_end_of_year():
    run_context = RunContext.from_run_date(date(2026, 12, 31))

    assert run_context.forecast_year == 2026


def test_10_forecast_year_transition_start_of_next_year():
    run_context = RunContext.from_run_date(date(2027, 1, 1))

    assert run_context.forecast_year == 2027


# ============================================================
# Contratos preservados — verificações adicionais
# ============================================================


def test_expression_evaluator_default_period_id_defaults_to_none():
    """
    Chamadas existentes que não informam período (nem em
    EquationEngine.calculate_instance, nem diretamente no
    ExpressionEvaluator) continuam funcionando exatamente como
    antes.
    """

    from app.engine.expression_evaluator import ExpressionEvaluator

    context = CalculationContext(variables={"VAR1": 5.0})

    evaluator = ExpressionEvaluator(context)

    assert evaluator.default_period_id is None


def test_calculate_from_definition_registry_without_temporal_args_is_atemporal():
    """
    Sem variable_definition_registry/run_date, o comportamento
    permanece exatamente o de antes (period_id=None em todo o
    fluxo) — retrocompatibilidade explícita.
    """

    variable_definition_registry = VariableDefinitionRegistry()
    variable_definition_registry.add(
        VariableDefinition(
            "VAR10200", "x", "x", "-", "calculado",
            "diário", "linha", "L1", "test", "ativo",
        )
    )

    equation_definition_registry = EquationDefinitionRegistry()
    equation_definition_registry.add(
        EquationDefinition(
            "EQ10200", "VAR10200", 1, "linha", "L1", "1 + 1",
            "test", "PUBLISHED",
        )
    )

    context = CalculationContext()

    engine = ForecastEngine()

    engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definition_registry,
        calculation_context=context,
    )

    # Armazenado sem period_id (comportamento legado preservado).
    assert context.get_variable_value(
        variable_id="VAR10200",
        scope_type="linha",
        scope_value="L1",
    ) == 2


# ============================================================
# Integração — seed real do Yield (106 EquationDefinitions,
# inalteradas), agora com dimensão temporal ativada.
# ============================================================


SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

INPUT_DAILY_VALUES = {
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
}

INPUT_ANNUAL_VALUES = {
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

    for name, value in INPUT_DAILY_VALUES.items():
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

    for name, value in INPUT_ANNUAL_VALUES.items():
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


def test_yield_real_seed_executes_with_temporal_dimension_enabled():
    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions,
        _vi,
        _parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loader.load_all_definitions_and_instances()

    context = CalculationContext()

    _populate_yield_context(context, variable_definitions)

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(
            instance,
            instance.value,
        )

    engine = ForecastEngine()

    run_date = date(2026, 9, 14)

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definitions,
        calculation_context=context,
        variable_definition_registry=variable_definitions,
        run_date=run_date,
    )

    # As 106 EquationDefinitions reais não foram alteradas: mesma
    # quantidade de EquationInstances calculadas de antes (166).
    assert len(results) == len(equation_instances.all())

    # n_ppt é diário: seu period_id efetivo deve ser exatamente
    # run_date (2026-09-14), nunca o mês inteiro.
    n_ppt_l4 = context.get_variable_value(
        variable_id="VAR11012",
        scope_type="linha",
        scope_value="L4",
        period_id="2026-09-14",
    )
    assert n_ppt_l4 == pytest.approx(18 - 12.0)

    # yield@L4 (diário) deve estar disponível sob o mesmo period_id.
    yield_l4 = context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L4",
        period_id="2026-09-14",
    )
    assert isinstance(yield_l4, (int, float))

    # Agregação linha_grupo (também diária nesta base) permanece
    # calculável sob o mesmo period_id, comprovando que a dimensão
    # temporal não quebrou a cadeia de dependências espaciais.
    yield_l1_l3 = context.get_variable_value(
        variable_id="VAR11016",
        scope_type="linha_grupo",
        scope_value="L1_L3",
        period_id="2026-09-14",
    )
    assert isinstance(yield_l1_l3, (int, float))


def test_yield_real_seed_still_works_without_temporal_dimension():
    """
    Regressão explícita: o mesmo teste de integração pré-existente
    (test_yield_seed_integration.py) continua funcionando sem passar
    variable_definition_registry/run_date — o caminho atemporal
    original não foi quebrado pela evolução temporal.
    """

    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions,
        _vi,
        _parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loader.load_all_definitions_and_instances()

    context = CalculationContext()

    _populate_yield_context(context, variable_definitions)

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(
            instance,
            instance.value,
        )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definitions,
        calculation_context=context,
    )

    assert len(results) == len(equation_instances.all())

    assert context.get_variable_value(
        variable_id="VAR11012",
        scope_type="linha",
        scope_value="L4",
    ) == pytest.approx(18 - 12.0)
