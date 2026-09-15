"""
FASE C — Execution, atualização progressiva de ForecastValue e
histórico (TD-C01, TD-C02, TD-C03).

Objetivo:
    Provar, com execução real (sem mocks), que:

    - `Execution` representa uma rodada de cálculo (execution_id,
      run_date, forecast_year derivado, model_version, status), com
      um ciclo de vida mínimo RUNNING -> COMPLETED | RUNNING -> FAILED
      (TD-C02);
    - `ForecastValueRegistry` passou a representar o ESTADO VIGENTE
      de cada identidade lógica, atualizando-o (em vez de rejeitar)
      quando uma nova Execution produz um novo valor, e preservando
      o valor substituído em histórico, com sua proveniência
      (execution_id/run_date) recuperável (TD-C01/TD-C03);
    - `ForecastValue.identity()` continua EXATAMENTE como antes
      (variable_id, scope_type, scope_value, frequency, period_id,
      aggregation_rule_id) — execution_id e run_date nunca entram na
      identidade;
    - múltiplas AggregationRules para a mesma variável continuam
      coexistindo sob identidades distintas, cada uma com seu
      próprio histórico independente;
    - `TemporalForecastOrchestrator` é responsável por CRIAR a
      Execution (não o ForecastValue/Registry/AggregationService/
      EquationEngine).
"""

from datetime import date

import pytest

from app.domain.forecast.aggregation import AggregationRule
from app.domain.forecast.collection import (
    ConflictingForecastValueError,
    ForecastValueRegistry,
)
from app.domain.forecast.execution import Execution
from app.domain.forecast.models import ForecastValue
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import VariableNotFoundError
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)


# ============================================================
# E1-E4 — Execution
# ============================================================


def test_e1_execution_creation_has_all_expected_fields():
    execution = Execution.start(
        run_date=date(2026, 9, 15), model_version="v3",
    )

    assert execution.execution_id
    assert execution.run_date == date(2026, 9, 15)
    assert execution.forecast_year == 2026
    assert execution.model_version == "v3"
    assert execution.status == "RUNNING"


def test_e2_forecast_year_is_always_derived_from_run_date():
    execution = Execution.start(run_date=date(2027, 1, 1))
    assert execution.forecast_year == 2027

    with pytest.raises(ValueError):
        Execution(
            execution_id="EXEC-BAD",
            run_date=date(2026, 9, 15),
            forecast_year=2099,
            model_version="v1",
            status="RUNNING",
        )


def test_e3_distinct_executions_have_distinct_ids():
    execution_1 = Execution.start(run_date=date(2026, 9, 15))
    execution_2 = Execution.start(run_date=date(2026, 9, 15))

    assert execution_1.execution_id != execution_2.execution_id


def test_e4_lifecycle_running_to_completed():
    execution = Execution.start(run_date=date(2026, 9, 15))
    assert execution.status == "RUNNING"

    completed = execution.complete()
    assert completed.status == "COMPLETED"
    assert completed.execution_id == execution.execution_id
    # Imutável: a instância original não muda.
    assert execution.status == "RUNNING"


def test_e4_lifecycle_running_to_failed():
    execution = Execution.start(run_date=date(2026, 9, 15))

    failed = execution.fail()
    assert failed.status == "FAILED"


def test_e4_lifecycle_rejects_transition_from_terminal_status():
    execution = Execution.start(run_date=date(2026, 9, 15))
    completed = execution.complete()

    with pytest.raises(ValueError):
        completed.complete()

    with pytest.raises(ValueError):
        completed.fail()


def test_execution_rejects_unsupported_status():
    with pytest.raises(ValueError):
        Execution(
            execution_id="EXEC-BAD",
            run_date=date(2026, 9, 15),
            forecast_year=2026,
            model_version="v1",
            status="PENDING",
        )


# ============================================================
# TD-C01 — Atualização progressiva
# ============================================================


def test_c01_1_same_identity_same_value_is_idempotent():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40001", "linha", "L4", "mensal", 2026, "2026-09", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40001", "linha", "L4", "mensal", 2026, "2026-09", 80.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 80.0
    assert current.execution_id == "EXEC-002"


def test_c01_2_same_identity_different_value_updates_current():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40002", "linha", "L4", "mensal", 2026, "2026-09", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40002", "linha", "L4", "mensal", 2026, "2026-09", 82.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 82.0
    assert current.execution_id == "EXEC-002"

    history = registry.history(value_1.identity())
    assert len(history) == 1
    assert history[0].value == 80.0
    assert history[0].execution_id == "EXEC-001"


def test_c01_3_different_identity_keeps_both_values():
    registry = ForecastValueRegistry()

    value_l1 = ForecastValue(
        "VAR40003", "linha", "L1", "mensal", 2026, "2026-09", 10.0,
        execution_id="EXEC-001",
    )
    value_l2 = ForecastValue(
        "VAR40003", "linha", "L2", "mensal", 2026, "2026-09", 20.0,
        execution_id="EXEC-001",
    )

    registry.add(value_l1)
    registry.add(value_l2)

    assert len(registry) == 2
    assert registry.get(value_l1.identity()).value == 10.0
    assert registry.get(value_l2.identity()).value == 20.0
    assert registry.history(value_l1.identity()) == []


def test_c01_4_progressive_update_across_three_run_dates():
    context = CalculationContext()
    # value do dia = o próprio número do dia (1..12), para que a
    # média da janela até run_date seja calculável de forma
    # independente: average(1..N) = (N+1)/2.
    for day in range(1, 13):
        context.set_variable_value(
            "VAR40004", float(day), "linha", "L4",
            period_id=f"2026-09-{day:02d}",
        )

    rule = AggregationRule(
        "AGR-C01-4", "VAR40004", "diário", "VAR40004_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    executions = []
    for day in [10, 11, 12]:
        run_date = date(2026, 9, day)
        execution = orchestrator.start_execution(run_date=run_date)
        executions.append(execution)

        result = orchestrator.run_aggregation(
            rule=rule, calculation_context=context,
            scope_type="linha", scope_value="L4",
            run_date=run_date, execution=execution,
        )
        registry.add(result)
        execution.complete()

    current = registry.get(result.identity())
    assert current.value == pytest.approx((12 + 1) / 2)
    assert current.execution_id == executions[-1].execution_id

    history = registry.history(result.identity())
    assert [h.value for h in history] == [
        pytest.approx((10 + 1) / 2), pytest.approx((11 + 1) / 2),
    ]
    assert [h.execution_id for h in history] == [
        executions[0].execution_id, executions[1].execution_id,
    ]


def test_c01_5_multiple_aggregation_rules_coexist_after_updates():
    context = CalculationContext()
    for day in range(1, 15):
        context.set_variable_value(
            "VAR40005", 10.0 + day, "linha", "L2",
            period_id=f"2026-09-{day:02d}",
        )

    rule_sum = AggregationRule(
        "AGR-C01-5-SUM", "VAR40005", "diário", "VAR40005_M",
        "mensal", "SUM",
    )
    rule_avg = AggregationRule(
        "AGR-C01-5-AVG", "VAR40005", "diário", "VAR40005_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    execution_1 = orchestrator.start_execution(date(2026, 9, 10))
    result_sum_1 = orchestrator.run_aggregation(
        rule=rule_sum, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 10), execution=execution_1,
    )
    result_avg_1 = orchestrator.run_aggregation(
        rule=rule_avg, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 10), execution=execution_1,
    )
    registry.add(result_sum_1)
    registry.add(result_avg_1)
    execution_1.complete()

    assert len(registry) == 2
    assert result_sum_1.identity() != result_avg_1.identity()

    execution_2 = orchestrator.start_execution(date(2026, 9, 14))
    result_sum_2 = orchestrator.run_aggregation(
        rule=rule_sum, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 14), execution=execution_2,
    )
    result_avg_2 = orchestrator.run_aggregation(
        rule=rule_avg, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 14), execution=execution_2,
    )
    registry.add(result_sum_2)
    registry.add(result_avg_2)
    execution_2.complete()

    # Continuam apenas 2 identidades vigentes (SUM e AVERAGE), cada
    # uma atualizada de forma independente.
    assert len(registry) == 2
    assert registry.get(result_sum_1.identity()).value == pytest.approx(
        result_sum_2.value
    )
    assert registry.get(result_avg_1.identity()).value == pytest.approx(
        result_avg_2.value
    )
    assert len(registry.history(result_sum_1.identity())) == 1
    assert len(registry.history(result_avg_1.identity())) == 1
    assert (
        registry.history(result_sum_1.identity())[0].execution_id
        == execution_1.execution_id
    )


# ============================================================
# TD-C04 — mesma Execution, mesma identity: idempotência estrita
# vs. conflito explícito
# ============================================================


def test_c04_1_same_execution_same_identity_same_value_is_noop():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40100", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-SAME",
    )
    value_2 = ForecastValue(
        "VAR40100", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-SAME",
    )

    registry.add(value_1)
    registry.add(value_2)

    assert len(registry) == 1
    assert registry.get(value_1.identity()).value == 80.0
    assert registry.get(value_1.identity()).execution_id == "EXEC-SAME"
    assert registry.history(value_1.identity()) == []


def test_c04_2_same_execution_same_identity_different_value_raises():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40101", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-SAME",
    )
    value_2_conflicting = ForecastValue(
        "VAR40101", "linha", "L4", "diário", 2026, "2026-09-14", 999.0,
        execution_id="EXEC-SAME",
    )

    registry.add(value_1)

    with pytest.raises(ConflictingForecastValueError):
        registry.add(value_2_conflicting)

    # current e history permanecem intactos após o erro.
    assert registry.get(value_1.identity()).value == 80.0
    assert registry.get(value_1.identity()).execution_id == "EXEC-SAME"
    assert registry.history(value_1.identity()) == []


def test_c04_3_new_execution_same_value_archives_previous_and_updates_execution_id():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40102", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40102", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 80.0
    assert current.execution_id == "EXEC-002"

    history = registry.history(value_1.identity())
    assert len(history) == 1
    assert history[0].value == 80.0
    assert history[0].execution_id == "EXEC-001"


def test_c04_4_new_execution_different_value_updates_current_and_archives():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40103", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40103", "linha", "L4", "diário", 2026, "2026-09-14", 82.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 82.0
    assert current.execution_id == "EXEC-002"

    history = registry.history(value_1.identity())
    assert len(history) == 1
    assert history[0].value == 80.0
    assert history[0].execution_id == "EXEC-001"


# ============================================================
# TD-C03 — execution_id / histórico
# ============================================================


def test_c03_1_current_execution_id_matches_latest_execution():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40006", "linha", "L1", "diário", 2026, "2026-09-14", 5.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40006", "linha", "L1", "diário", 2026, "2026-09-14", 6.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    assert (
        registry.get(value_1.identity()).execution_id == "EXEC-002"
    )


def test_c03_2_previous_execution_id_remains_recoverable_in_history():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40007", "linha", "L1", "diário", 2026, "2026-09-14", 5.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40007", "linha", "L1", "diário", 2026, "2026-09-14", 6.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    history = registry.history(value_1.identity())
    assert history[0].execution_id == "EXEC-001"


def test_c03_3_same_value_different_execution_preserves_history_reference():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40008", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40008", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 80.0
    assert current.execution_id == "EXEC-002"

    history = registry.history(value_1.identity())
    assert len(history) == 1
    assert history[0].execution_id == "EXEC-001"
    assert history[0].value == 80.0


def test_c03_4_different_values_keep_both_in_history_and_current():
    registry = ForecastValueRegistry()

    value_1 = ForecastValue(
        "VAR40009", "linha", "L4", "diário", 2026, "2026-09-14", 80.0,
        execution_id="EXEC-001",
    )
    value_2 = ForecastValue(
        "VAR40009", "linha", "L4", "diário", 2026, "2026-09-14", 82.0,
        execution_id="EXEC-002",
    )

    registry.add(value_1)
    registry.add(value_2)

    current = registry.get(value_1.identity())
    assert current.value == 82.0

    history = registry.history(value_1.identity())
    assert len(history) == 1
    assert history[0].value == 80.0
    assert history[0].execution_id == "EXEC-001"


# ============================================================
# Integração completa: Orchestrator -> Execution ->
# ForecastValueRegistry -> atualização progressiva -> histórico
# ============================================================


def test_integration_orchestrator_execution_registry_progressive_history():
    context = CalculationContext()
    for day in range(1, 21):
        context.set_variable_value(
            "VAR40010", float(day), "linha", "L4",
            period_id=f"2026-09-{day:02d}",
        )

    rule = AggregationRule(
        "AGR-INTEGRATION", "VAR40010", "diário", "VAR40010_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    execution_day10 = orchestrator.start_execution(
        run_date=date(2026, 9, 10), model_version="v1",
    )
    result_day10 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 10), execution=execution_day10,
    )
    registry.add(result_day10)
    execution_day10 = execution_day10.complete()

    assert execution_day10.status == "COMPLETED"
    assert registry.get(result_day10.identity()).value == pytest.approx(
        sum(range(1, 11))
    )
    assert registry.history(result_day10.identity()) == []

    execution_day20 = orchestrator.start_execution(
        run_date=date(2026, 9, 20), model_version="v1",
    )
    result_day20 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 20), execution=execution_day20,
    )
    registry.add(result_day20)
    execution_day20 = execution_day20.complete()

    assert result_day10.identity() == result_day20.identity()

    current = registry.get(result_day10.identity())
    assert current.value == pytest.approx(sum(range(1, 21)))
    assert current.execution_id == execution_day20.execution_id
    assert current.run_date == date(2026, 9, 20)

    history = registry.history(result_day10.identity())
    assert len(history) == 1
    assert history[0].value == pytest.approx(sum(range(1, 11)))
    assert history[0].execution_id == execution_day10.execution_id
    assert history[0].run_date == date(2026, 9, 10)


def test_execution_run_date_mismatch_is_rejected():
    context = CalculationContext()
    context.set_variable_value(
        "VAR40011", 5.0, "linha", "L1", period_id="2026-09-14"
    )

    rule = AggregationRule(
        "AGR-MISMATCH", "VAR40011", "diário", "VAR40011_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    execution = orchestrator.start_execution(run_date=date(2026, 9, 14))

    with pytest.raises(ValueError):
        orchestrator.run_aggregation(
            rule=rule, calculation_context=context,
            scope_type="linha", scope_value="L1",
            run_date=date(2026, 9, 15),  # deliberadamente != execution.run_date
            execution=execution,
        )


def test_execution_failure_is_the_caller_responsibility():
    context = CalculationContext()

    rule = AggregationRule(
        "AGR-FAIL", "VAR40012", "diário", "VAR40012_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    execution = orchestrator.start_execution(run_date=date(2026, 9, 14))

    with pytest.raises(VariableNotFoundError):
        orchestrator.run_aggregation(
            rule=rule, calculation_context=context,
            scope_type="linha", scope_value="L1",
            run_date=date(2026, 9, 14), execution=execution,
        )

    failed_execution = execution.fail()
    assert failed_execution.status == "FAILED"
    assert execution.status == "RUNNING"


# ============================================================
# Cenário literal exigido: EXEC-001/80 -> EXEC-002/81 -> EXEC-003/82
# ============================================================


def test_literal_scenario_exec_001_002_003_progressive_values():
    context = CalculationContext()
    # value do dia = o próprio dia (1..12): average(1..10)=5.5,
    # average(1..11)=6, average(1..12)=6.5 -- não usamos 80/81/82
    # como valor bruto do dia porque o resultado é uma AGREGAÇÃO
    # (média da janela), não o dado de um único dia; o que importa
    # aqui é que os TRÊS resultados sejam distintos e progressivos,
    # exatamente como no exemplo literal do pedido (80 -> 81 -> 82).
    for day in range(1, 13):
        context.set_variable_value(
            "VAR40200", float(day), "linha", "L4",
            period_id=f"2026-09-{day:02d}",
        )

    rule = AggregationRule(
        "AGR-LITERAL", "VAR40200", "diário", "VAR40200_M",
        "mensal", "SUM",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    execution_001 = orchestrator.start_execution(
        run_date=date(2026, 9, 10), execution_id="EXEC-001",
    )
    value_001 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 10), execution=execution_001,
    )
    registry.add(value_001)

    execution_002 = orchestrator.start_execution(
        run_date=date(2026, 9, 11), execution_id="EXEC-002",
    )
    value_002 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 11), execution=execution_002,
    )
    registry.add(value_002)

    execution_003 = orchestrator.start_execution(
        run_date=date(2026, 9, 12), execution_id="EXEC-003",
    )
    value_003 = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 12), execution=execution_003,
    )
    registry.add(value_003)

    current = registry.get(value_001.identity())
    assert current.value == pytest.approx(sum(range(1, 13)))
    assert current.execution_id == "EXEC-003"

    history = registry.history(value_001.identity())
    assert [h.execution_id for h in history] == ["EXEC-001", "EXEC-002"]
    assert history[0].value == pytest.approx(sum(range(1, 11)))
    assert history[1].value == pytest.approx(sum(range(1, 12)))


# ============================================================
# TD-C02 — uma única Execution pode produzir vários ForecastValues
# ============================================================


def test_single_execution_produces_multiple_distinct_forecast_values():
    """
    Confirma concretamente (não apenas por leitura de código) que o
    desenho atual do orchestrator já permite associar uma única
    Execution a várias chamadas de run_aggregation/
    direct_forecast_value, cada uma produzindo um ForecastValue
    distinto — sem que nenhuma delas precise criar sua própria
    Execution.
    """

    context = CalculationContext()
    for day in range(1, 15):
        context.set_variable_value(
            "VAR40300", 10.0 + day, "linha", "L1",
            period_id=f"2026-09-{day:02d}",
        )
        context.set_variable_value(
            "VAR40301", 20.0 + day, "linha", "L2",
            period_id=f"2026-09-{day:02d}",
        )

    rule_a = AggregationRule(
        "AGR-MULTI-A", "VAR40300", "diário", "VAR40300_M",
        "mensal", "SUM",
    )
    rule_b = AggregationRule(
        "AGR-MULTI-B", "VAR40301", "diário", "VAR40301_M",
        "mensal", "AVERAGE",
    )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    execution = orchestrator.start_execution(
        run_date=date(2026, 9, 14), model_version="v1",
    )

    result_a = orchestrator.run_aggregation(
        rule=rule_a, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 14), execution=execution,
    )
    result_b = orchestrator.run_aggregation(
        rule=rule_b, calculation_context=context,
        scope_type="linha", scope_value="L2",
        run_date=date(2026, 9, 14), execution=execution,
    )
    registry.add(result_a)
    registry.add(result_b)

    execution = execution.complete()

    assert len(registry) == 2
    assert result_a.identity() != result_b.identity()
    assert result_a.execution_id == execution.execution_id
    assert result_b.execution_id == execution.execution_id
    assert execution.status == "COMPLETED"
