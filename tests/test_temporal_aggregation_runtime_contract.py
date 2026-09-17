"""
Validação runtime de WEIGHTED_AVERAGE e MOVING_AVERAGE, fechando a
lacuna identificada na auditoria de fechamento Yield+Production:

    Yield:       yield_lth_total (WEIGHTED_AVERAGE)
    Production:  producao_planta_movel (MOVING_AVERAGE)

Três níveis de validação, nunca misturados:

    Nível A — mecanismo genérico (TemporalAggregationService.aggregate
              com uma AggregationRule sintética, independente de
              qualquer variável real de Yield/Production);
    Nível B — regra real registrada no seed (campos da AggregationRule
              carregada por SeedLoader.load_aggregation_rules());
    Nível C — execução real via TemporalForecastOrchestrator.run_aggregation
              (o mesmo wrapper fino já usado pela plataforma, que
              delega integralmente a TemporalAggregationService —
              nenhuma lógica é duplicada) com a AggregationRule REAL
              do seed e valores de origem plausíveis no
              CalculationContext.

Em nenhum teste desta suíte o valor agregado (target_variable_id) é
escrito manualmente no CalculationContext -- `TemporalAggregationService`
nunca escreve automaticamente de volta no contexto (ver docstring do
serviço); o único jeito do resultado existir é o retorno real de
`aggregate()`/`run_aggregation()`. Os "expected" são sempre calculados
diretamente a partir dos inputs populados, nunca reaproveitando o
retorno do serviço.

Não altera seeds, não altera código de produção.
"""

from datetime import date
from pathlib import Path

import pytest

from app.domain.forecast.aggregation import AggregationRule
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import ZeroWeightSumError
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)
from app.repositories.seed_loader import SeedLoader

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


@pytest.fixture(scope="module")
def aggregation_rules():
    return SeedLoader(SEED_ROOT).load_aggregation_rules()


def _real_rule(aggregation_rules, aggregation_rule_id):
    for rule in aggregation_rules.all():
        if rule.aggregation_rule_id == aggregation_rule_id:
            return rule

    raise AssertionError(
        f"AggregationRule real não encontrada: {aggregation_rule_id}"
    )


def _populate_daily(ctx, variable_id, scope_type, scope_value, values_by_date):
    for d, value in values_by_date.items():
        ctx.set_variable_value(
            variable_id, value, scope_type, scope_value,
            period_id=d.isoformat(),
        )


# ============================================================
# Nível B — inspeção das regras reais registradas no seed
# ============================================================


def test_level_b_yield_lth_total_weighted_average_rule_shape(
    aggregation_rules,
):
    mensal = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-YIELD_LTH_TOTAL-GRUPO-L1_L7-MENSAL-WEIGHTED_AVERAGE",
    )
    anual = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-YIELD_LTH_TOTAL-GRUPO-L1_L7-ANUAL-WEIGHTED_AVERAGE",
    )

    for rule, target_id, target_freq in [
        (mensal, "VAR12022", "mensal"),
        (anual, "VAR12023", "anual"),
    ]:
        assert rule.source_variable_id == "VAR12021"
        assert rule.source_frequency == "diário"
        assert rule.target_variable_id == target_id
        assert rule.target_frequency == target_freq
        assert rule.aggregation_type == "WEIGHTED_AVERAGE"
        assert rule.weight_variable_id == "VAR12060"
        # Sem janela explícita: a janela é derivada de target_frequency
        # (ver Nível A/C abaixo).
        assert rule.window_start_date is None
        assert rule.window_end_date is None


def test_level_b_producao_planta_movel_moving_average_rule_shape(
    aggregation_rules,
):
    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE",
    )

    assert rule.source_variable_id == "VAR12060"
    assert rule.source_frequency == "diário"
    assert rule.target_variable_id == "VAR12063"
    assert rule.target_frequency == "diário"
    assert rule.aggregation_type == "MOVING_AVERAGE"
    assert rule.weight_variable_id is None
    # Sem janela explícita: cai no ramo especial "mês progressivo"
    # de `_resolve_window` (MTD), independentemente de target_frequency
    # ser "diário" -- é isso que permite um valor diário cujo
    # conteúdo é o acumulado do mês até aquele dia.
    assert rule.window_start_date is None
    assert rule.window_end_date is None


# ============================================================
# Nível A — WEIGHTED_AVERAGE, mecanismo genérico
# ============================================================


def test_level_a_weighted_average_controlled_formula():
    """
    Fórmula documentada:

        Σ(value_i * weight_i) / Σ(weight_i)

    Dia 1: value=10, weight=1
    Dia 2: value=20, weight=2
    Dia 3: value=40, weight=3

    Expected = (10*1 + 20*2 + 40*3) / (1+2+3), calculado aqui
    diretamente -- nunca via TemporalAggregationService.
    """

    ctx = CalculationContext()
    days = {
        date(2026, 9, 1): (10.0, 1.0),
        date(2026, 9, 2): (20.0, 2.0),
        date(2026, 9, 3): (40.0, 3.0),
    }
    _populate_daily(ctx, "VARVAL", "linha", "L1", {d: v for d, (v, _) in days.items()})
    _populate_daily(ctx, "VARWEIGHT", "linha", "L1", {d: w for d, (_, w) in days.items()})

    rule = AggregationRule(
        aggregation_rule_id="AGR-WA-CONTROLLED",
        source_variable_id="VARVAL",
        source_frequency="diário",
        target_variable_id="VARVAL_M",
        target_frequency="mensal",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARWEIGHT",
    )

    expected = (10.0 * 1.0 + 20.0 * 2.0 + 40.0 * 3.0) / (1.0 + 2.0 + 3.0)

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 3),
    )

    print(f"\nWA controlado: expected={expected} actual={result.value}")
    assert result.value == pytest.approx(expected, rel=1e-12)


def test_level_a_weighted_average_window_excludes_day_before_month():
    """
    Um dia de agosto com valor/peso extremos NÃO deve contaminar a
    agregação de setembro (janela mensal derivada de target_frequency
    = mês corrente de run_date).
    """

    ctx = CalculationContext()
    # dia fora da janela (agosto), valor/peso deliberadamente extremos
    ctx.set_variable_value("VARVAL", 999999.0, "linha", "L1", period_id="2026-08-31")
    ctx.set_variable_value("VARWEIGHT", 999999.0, "linha", "L1", period_id="2026-08-31")

    days = {
        date(2026, 9, 1): (10.0, 1.0),
        date(2026, 9, 2): (20.0, 2.0),
    }
    _populate_daily(ctx, "VARVAL", "linha", "L1", {d: v for d, (v, _) in days.items()})
    _populate_daily(ctx, "VARWEIGHT", "linha", "L1", {d: w for d, (_, w) in days.items()})

    rule = AggregationRule(
        aggregation_rule_id="AGR-WA-WINDOW",
        source_variable_id="VARVAL",
        source_frequency="diário",
        target_variable_id="VARVAL_M",
        target_frequency="mensal",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARWEIGHT",
    )

    expected_without_august = (10.0 * 1.0 + 20.0 * 2.0) / (1.0 + 2.0)

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 2),
    )

    print(
        f"\nWA janela: expected(sem agosto)={expected_without_august} "
        f"actual={result.value}"
    )
    # Se 31/08 tivesse contaminado, o resultado estaria próximo de
    # 999999 -- muito longe do valor esperado.
    assert result.value == pytest.approx(expected_without_august, rel=1e-12)
    assert result.value < 1000.0


def test_level_a_weighted_average_zero_weight_sum_raises_existing_error():
    """
    Contrato já existente (não inventado nesta tarefa): soma de pesos
    zero levanta ZeroWeightSumError, sem divisão por zero silenciosa.
    """

    ctx = CalculationContext()
    ctx.set_variable_value("VARVAL", 10.0, "linha", "L1", period_id="2026-09-01")
    ctx.set_variable_value("VARWEIGHT", 0.0, "linha", "L1", period_id="2026-09-01")

    rule = AggregationRule(
        aggregation_rule_id="AGR-WA-ZERO",
        source_variable_id="VARVAL",
        source_frequency="diário",
        target_variable_id="VARVAL_M",
        target_frequency="mensal",
        aggregation_type="WEIGHTED_AVERAGE",
        weight_variable_id="VARWEIGHT",
    )

    with pytest.raises(ZeroWeightSumError):
        TemporalAggregationService().aggregate(
            rule=rule, calculation_context=ctx,
            scope_type="linha", scope_value="L1",
            run_date=date(2026, 9, 1),
        )


# ============================================================
# Nível C — WEIGHTED_AVERAGE real: yield_lth_total
# ============================================================


def test_level_c_yield_lth_total_weighted_average_monthly_real_rule(
    aggregation_rules,
):
    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-YIELD_LTH_TOTAL-GRUPO-L1_L7-MENSAL-WEIGHTED_AVERAGE",
    )

    run_date = date(2026, 9, 5)
    # Janela mensal derivada: 2026-09-01 .. run_date (2026-09-05).
    yield_lth_total = {
        date(2026, 9, 1): 100.0,
        date(2026, 9, 2): 105.0,
        date(2026, 9, 3): 98.0,
        date(2026, 9, 4): 110.0,
        date(2026, 9, 5): 102.0,
    }
    producao_planta = {
        date(2026, 9, 1): 500.0,
        date(2026, 9, 2): 520.0,
        date(2026, 9, 3): 480.0,
        date(2026, 9, 4): 560.0,
        date(2026, 9, 5): 510.0,
    }

    ctx = CalculationContext()
    _populate_daily(ctx, rule.source_variable_id, "linha_grupo", "L1_L7", yield_lth_total)
    _populate_daily(ctx, rule.weight_variable_id, "linha_grupo", "L1_L7", producao_planta)

    expected = sum(
        yield_lth_total[d] * producao_planta[d] for d in yield_lth_total
    ) / sum(producao_planta.values())

    orchestrator = TemporalForecastOrchestrator()
    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=run_date,
    )

    print(
        "\nyield_lth_total (mensal, real rule):",
        f"\n  source(yield_lth_total)={yield_lth_total}",
        f"\n  weight(producao_planta)={producao_planta}",
        f"\n  expected={expected} actual={result.value} "
        f"diff={abs(result.value - expected)}",
    )

    assert result.variable_id == "VAR12022"
    assert result.period_id == "2026-09"
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_level_c_yield_lth_total_weighted_average_annual_real_rule(
    aggregation_rules,
):
    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-YIELD_LTH_TOTAL-GRUPO-L1_L7-ANUAL-WEIGHTED_AVERAGE",
    )

    run_date = date(2026, 1, 3)
    # Janela anual derivada: 2026-01-01 .. run_date (2026-01-03).
    yield_lth_total = {
        date(2026, 1, 1): 90.0,
        date(2026, 1, 2): 95.0,
        date(2026, 1, 3): 88.0,
    }
    producao_planta = {
        date(2026, 1, 1): 400.0,
        date(2026, 1, 2): 420.0,
        date(2026, 1, 3): 410.0,
    }

    ctx = CalculationContext()
    _populate_daily(ctx, rule.source_variable_id, "linha_grupo", "L1_L7", yield_lth_total)
    _populate_daily(ctx, rule.weight_variable_id, "linha_grupo", "L1_L7", producao_planta)

    expected = sum(
        yield_lth_total[d] * producao_planta[d] for d in yield_lth_total
    ) / sum(producao_planta.values())

    orchestrator = TemporalForecastOrchestrator()
    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=run_date,
    )

    print(
        "\nyield_lth_total (anual, real rule):",
        f"\n  expected={expected} actual={result.value}",
    )

    assert result.variable_id == "VAR12023"
    assert result.period_id == "2026"
    assert result.value == pytest.approx(expected, rel=1e-9)


# ============================================================
# Nível A — MOVING_AVERAGE, mecanismo genérico (janela progressiva,
# SEM window_start/end explícitos -- o ramo real que
# producao_planta_movel usa, ainda não coberto pela suíte existente)
# ============================================================


def test_level_a_moving_average_progressive_window_no_explicit_dates():
    """
    Sem window_start_date/window_end_date, MOVING_AVERAGE usa o mês
    corrente progressivo (1º dia do mês até run_date), MESMO com
    target_frequency="diário" -- é este o ramo real usado por
    producao_planta_movel, não coberto pelos testes A5/A6/C11
    existentes (que sempre fixam janela explícita).
    """

    ctx = CalculationContext()
    values = {
        date(2026, 9, 1): 10.0,
        date(2026, 9, 2): 20.0,
        date(2026, 9, 3): 30.0,
        date(2026, 9, 4): 40.0,
    }
    _populate_daily(ctx, "VARDAILY", "linha", "L1", values)

    rule = AggregationRule(
        aggregation_rule_id="AGR-MA-PROGRESSIVE",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARDAILY_MOVEL",
        target_frequency="diário",
        aggregation_type="MOVING_AVERAGE",
    )

    service = TemporalAggregationService()

    expected_by_run_date = {
        date(2026, 9, 1): sum([10.0]) / 1,
        date(2026, 9, 2): sum([10.0, 20.0]) / 2,
        date(2026, 9, 3): sum([10.0, 20.0, 30.0]) / 3,
        date(2026, 9, 4): sum([10.0, 20.0, 30.0, 40.0]) / 4,
    }

    for run_date, expected in expected_by_run_date.items():
        result = service.aggregate(
            rule=rule, calculation_context=ctx,
            scope_type="linha", scope_value="L1",
            run_date=run_date,
        )
        print(f"\nMA progressivo {run_date}: expected={expected} actual={result.value}")
        assert result.value == pytest.approx(expected, rel=1e-12)
        assert result.period_id == run_date.isoformat()


def test_level_a_moving_average_day_before_month_excluded():
    """
    Fronteira: 08/31 com valor extremo não pode entrar na janela de
    setembro (mês progressivo), mesmo estando logo antes do início.
    Prova que a janela não está deslocada em um dia.
    """

    ctx = CalculationContext()
    ctx.set_variable_value("VARDAILY", 999999.0, "linha", "L1", period_id="2026-08-31")
    ctx.set_variable_value("VARDAILY", 10.0, "linha", "L1", period_id="2026-09-01")

    rule = AggregationRule(
        aggregation_rule_id="AGR-MA-BOUNDARY",
        source_variable_id="VARDAILY",
        source_frequency="diário",
        target_variable_id="VARDAILY_MOVEL",
        target_frequency="diário",
        aggregation_type="MOVING_AVERAGE",
    )

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 1),
    )

    assert result.value == pytest.approx(10.0, rel=1e-12)


# ============================================================
# Nível C — MOVING_AVERAGE real: producao_planta_movel
# ============================================================


PRODUCAO_PLANTA_VALUES = {
    date(2026, 9, 1): 501.0,
    date(2026, 9, 2): 512.0,
    date(2026, 9, 3): 498.0,
    date(2026, 9, 4): 523.0,
    date(2026, 9, 5): 509.0,
    date(2026, 9, 6): 517.0,
    date(2026, 9, 7): 495.0,
    date(2026, 9, 8): 530.0,
    date(2026, 9, 9): 508.0,
    date(2026, 9, 10): 519.0,
    date(2026, 9, 11): 503.0,
    date(2026, 9, 12): 527.0,
    date(2026, 9, 13): 511.0,
    date(2026, 9, 14): 522.0,
}


def _ctx_with_producao_planta(rule):
    ctx = CalculationContext()
    _populate_daily(
        ctx, rule.source_variable_id, "linha_grupo", "L1_L7",
        PRODUCAO_PLANTA_VALUES,
    )
    return ctx


@pytest.mark.parametrize(
    "run_date,window_days",
    [
        (date(2026, 9, 1), [date(2026, 9, 1)]),
        (date(2026, 9, 2), [date(2026, 9, 1), date(2026, 9, 2)]),
        (
            date(2026, 9, 7),
            [date(2026, 9, d) for d in range(1, 8)],
        ),
        (
            date(2026, 9, 14),
            [date(2026, 9, d) for d in range(1, 15)],
        ),
    ],
    ids=["first-day-of-window", "second-day", "mid-month", "main-target-date"],
)
def test_level_c_producao_planta_movel_real_rule(
    aggregation_rules, run_date, window_days,
):
    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE",
    )

    ctx = _ctx_with_producao_planta(rule)

    expected = sum(
        PRODUCAO_PLANTA_VALUES[d] for d in window_days
    ) / len(window_days)

    orchestrator = TemporalForecastOrchestrator()
    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=run_date,
    )

    print(
        f"\nproducao_planta_movel run_date={run_date}: "
        f"window={window_days} expected={expected} actual={result.value}",
    )

    assert result.variable_id == "VAR12063"
    assert result.period_id == run_date.isoformat()
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_level_c_producao_planta_movel_day_before_month_not_included(
    aggregation_rules,
):
    """
    Fronteira com dado real: um valor de agosto extremo (posicionado
    imediatamente antes do início do forecast month) não deve
    contaminar o dia 01/09 -- prova ausência de deslocamento de 1 dia
    na janela MTD real.
    """

    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE",
    )

    ctx = _ctx_with_producao_planta(rule)
    ctx.set_variable_value(
        rule.source_variable_id, 999999.0, "linha_grupo", "L1_L7",
        period_id="2026-08-31",
    )

    orchestrator = TemporalForecastOrchestrator()
    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=date(2026, 9, 1),
    )

    assert result.value == pytest.approx(
        PRODUCAO_PLANTA_VALUES[date(2026, 9, 1)], rel=1e-9,
    )


def test_level_c_producao_planta_movel_causality_inside_vs_outside_window(
    aggregation_rules,
):
    """
    Teste de causalidade (spec seção 19): alterar um dia DENTRO da
    janela muda o resultado; alterar um dia FORA da janela (mês
    anterior) não muda nada.
    """

    rule = _real_rule(
        aggregation_rules,
        "AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE",
    )
    run_date = date(2026, 9, 7)
    window_days = [date(2026, 9, d) for d in range(1, 8)]

    def run(day10_value, day_outside_value):
        ctx = _ctx_with_producao_planta(rule)
        ctx.set_variable_value(
            rule.source_variable_id, day10_value, "linha_grupo", "L1_L7",
            period_id="2026-09-05",
        )
        ctx.set_variable_value(
            rule.source_variable_id, day_outside_value, "linha_grupo",
            "L1_L7", period_id="2026-08-20",
        )
        orchestrator = TemporalForecastOrchestrator()
        return orchestrator.run_aggregation(
            rule=rule, calculation_context=ctx,
            scope_type="linha_grupo", scope_value="L1_L7",
            run_date=run_date,
        ).value

    baseline = run(
        PRODUCAO_PLANTA_VALUES[date(2026, 9, 5)], 111.0,
    )
    perturbed_inside = run(9999.0, 111.0)
    perturbed_outside = run(
        PRODUCAO_PLANTA_VALUES[date(2026, 9, 5)], 8888888.0,
    )

    expected_baseline = sum(
        PRODUCAO_PLANTA_VALUES[d] for d in window_days
    ) / len(window_days)
    expected_perturbed_inside = (
        sum(PRODUCAO_PLANTA_VALUES[d] for d in window_days if d != date(2026, 9, 5))
        + 9999.0
    ) / len(window_days)

    print(
        f"\nCausalidade: baseline={baseline} "
        f"perturbado(dentro da janela, 05/09)={perturbed_inside} "
        f"perturbado(fora da janela, 20/08)={perturbed_outside}",
    )

    assert baseline == pytest.approx(expected_baseline, rel=1e-9)
    assert perturbed_inside == pytest.approx(
        expected_perturbed_inside, rel=1e-9,
    )
    assert perturbed_inside != pytest.approx(baseline, rel=1e-6), (
        "Alterar um dia dentro da janela não mudou o resultado"
    )
    assert perturbed_outside == pytest.approx(baseline, rel=1e-12), (
        "Alterar um dia fora da janela alterou o resultado "
        "-- vazamento de janela temporal"
    )
