"""
Validação runtime das 11 AggregationRules do bloco `energy`.

Cada regra é lida do seed REAL (`SeedLoader.load_aggregation_rules()`)
e executada pelo `TemporalAggregationService` real. Os valores
esperados são calculados diretamente a partir dos inputs populados,
com a fórmula escrita à mão no próprio teste -- em nenhum ponto desta
suíte existe `expected = service.aggregate(...)`.

Os inputs de cada dia são deliberadamente distintos e os pesos não são
proporcionais aos valores, de modo que AVERAGE e WEIGHTED_AVERAGE
produzem números diferentes: uma troca de tipo de agregação não passa
despercebida.

`TemporalAggregationService` nunca escreve o resultado de volta no
contexto -- o valor agregado só existe como retorno de `aggregate()`.

Não altera seeds, não altera código de produção.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.domain.forecast.aggregation import AggregationRule
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import ZeroWeightSumError
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.repositories.seed_loader import SeedLoader

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

WEIGHT_VARIABLE_ID = "VAR18003"  # producao_planta_t_h


@pytest.fixture(scope="module")
def rules():
    registry = SeedLoader(SEED_ROOT).load_aggregation_rules()

    return {
        rule.aggregation_rule_id: rule
        for rule in registry.all()
        if rule.aggregation_rule_id.startswith("AGR-ENERGY-")
    }


def _rule_by_target(rules, target_variable_id, aggregation_type=None):
    matches = [
        rule for rule in rules.values()
        if rule.target_variable_id == target_variable_id
        and (
            aggregation_type is None
            or rule.aggregation_type == aggregation_type
        )
    ]

    assert len(matches) == 1, (
        f"{target_variable_id}: esperada 1 regra, "
        f"encontradas {len(matches)}"
    )

    return matches[0]


def _populate(ctx, variable_id, scope_type, scope_value, by_date):
    for day, value in by_date.items():
        ctx.set_variable_value(
            variable_id, value, scope_type, scope_value,
            period_id=day.isoformat(),
        )


# Três dias de setembro com valores e pesos que NÃO são proporcionais
# entre si: média simples e média ponderada divergem.
DAYS = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]

VALUES = [11.0, 23.0, 37.0]
WEIGHTS = [2.0, 5.0, 3.0]

RUN_DATE = DAYS[-1]


def _simple_average():
    return sum(VALUES) / len(VALUES)


def _weighted_average():
    return (
        sum(v * w for v, w in zip(VALUES, WEIGHTS))
        / sum(WEIGHTS)
    )


def _prepare_context(rule, scope_type, scope_value):
    ctx = CalculationContext()

    _populate(
        ctx, rule.source_variable_id, scope_type, scope_value,
        dict(zip(DAYS, VALUES)),
    )

    if rule.weight_variable_id:
        _populate(
            ctx, rule.weight_variable_id, scope_type, scope_value,
            dict(zip(DAYS, WEIGHTS)),
        )

    return ctx


# ============================================================
# Forma das 11 regras
# ============================================================


def test_there_are_exactly_eleven_energy_rules(rules):
    assert len(rules) == 11


def test_rule_type_distribution(rules):
    counts = {}

    for rule in rules.values():
        counts[rule.aggregation_type] = (
            counts.get(rule.aggregation_type, 0) + 1
        )

    assert counts == {
        "MOVING_AVERAGE": 1,
        "AVERAGE": 3,
        "WEIGHTED_AVERAGE": 7,
    }


def test_every_weighted_average_uses_producao_planta_t_h(rules):
    """
    O peso de toda média ponderada do bloco é `producao_planta_t_h`
    (VAR18003) -- nunca substituído por outra grandeza.
    """

    weighted = [
        rule for rule in rules.values()
        if rule.aggregation_type == "WEIGHTED_AVERAGE"
    ]

    assert len(weighted) == 7

    for rule in weighted:
        assert rule.weight_variable_id == WEIGHT_VARIABLE_ID

    for rule in rules.values():
        if rule.aggregation_type != "WEIGHTED_AVERAGE":
            assert rule.weight_variable_id is None


def test_no_rule_declares_an_explicit_window(rules):
    """
    Nenhuma regra fixa janela: a janela é derivada pelo
    TimePeriodResolver a partir de target_frequency e run_date (e, no
    caso de MOVING_AVERAGE, do mês corrente).
    """

    for rule in rules.values():
        assert rule.window_start_date is None
        assert rule.window_end_date is None


def test_all_sources_are_daily(rules):
    for rule in rules.values():
        assert rule.source_frequency == "diário"


def test_ten_rules_target_monthly_and_one_targets_daily(rules):
    monthly = [
        r for r in rules.values() if r.target_frequency == "mensal"
    ]
    daily = [
        r for r in rules.values() if r.target_frequency == "diário"
    ]

    assert len(monthly) == 10
    assert len(daily) == 1
    assert daily[0].aggregation_type == "MOVING_AVERAGE"
    assert daily[0].target_variable_id == "VAR18004"


def test_especifico_demanda_bayer_feeds_two_distinct_rules(rules):
    """
    VAR18050 é origem de DUAS regras com alvos distintos: a média
    simples (VAR18051) e a ponderada (VAR18052). Nenhuma substitui a
    outra -- ambas vêm de linhas distintas da planilha (L57 e L58).
    """

    from_18050 = sorted(
        (rule.target_variable_id, rule.aggregation_type)
        for rule in rules.values()
        if rule.source_variable_id == "VAR18050"
    )

    assert from_18050 == [
        ("VAR18051", "AVERAGE"),
        ("VAR18052", "WEIGHTED_AVERAGE"),
    ]


# ============================================================
# Execução: os 3 AVERAGE
# ============================================================


@pytest.mark.parametrize(
    "target_variable_id,scope_type,scope_value",
    [
        ("VAR18021", "linha", "L4"),
        ("VAR18023", "linha_grupo", "L1_L7"),
        ("VAR18051", "linha_grupo", "L1_L7"),
    ],
)
def test_average_rules_return_the_arithmetic_mean(
    rules, target_variable_id, scope_type, scope_value,
):
    rule = _rule_by_target(rules, target_variable_id, "AVERAGE")

    ctx = _prepare_context(rule, scope_type, scope_value)

    expected = (11.0 + 23.0 + 37.0) / 3

    assert expected == pytest.approx(_simple_average())

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type=scope_type, scope_value=scope_value,
        run_date=RUN_DATE,
    )

    assert result.value == pytest.approx(expected, rel=1e-12)

    # A média ponderada dos mesmos dados daria outro número: o teste
    # falharia se a regra tivesse sido declarada como ponderada.
    assert expected != pytest.approx(_weighted_average())


# ============================================================
# Execução: os 7 WEIGHTED_AVERAGE
# ============================================================


@pytest.mark.parametrize(
    "target_variable_id",
    [
        "VAR18026",
        "VAR18028",
        "VAR18039",
        "VAR18041",
        "VAR18043",
        "VAR18048",
        "VAR18052",
    ],
)
def test_weighted_average_rules_return_sum_vw_over_sum_w(
    rules, target_variable_id,
):
    rule = _rule_by_target(
        rules, target_variable_id, "WEIGHTED_AVERAGE",
    )

    ctx = _prepare_context(rule, "linha_grupo", "L1_L7")

    expected = (
        11.0 * 2.0 + 23.0 * 5.0 + 37.0 * 3.0
    ) / (2.0 + 5.0 + 3.0)

    assert expected == pytest.approx(_weighted_average())

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=RUN_DATE,
    )

    assert result.value == pytest.approx(expected, rel=1e-12)

    assert expected != pytest.approx(_simple_average())


def test_weighted_average_raises_on_zero_weight_sum(rules):
    """
    Σw == 0 é erro explícito, nunca uma divisão silenciosa por zero ou
    um fallback para média simples.
    """

    rule = _rule_by_target(rules, "VAR18043", "WEIGHTED_AVERAGE")

    ctx = CalculationContext()

    _populate(
        ctx, rule.source_variable_id, "linha_grupo", "L1_L7",
        dict(zip(DAYS, VALUES)),
    )
    _populate(
        ctx, rule.weight_variable_id, "linha_grupo", "L1_L7",
        {day: 0.0 for day in DAYS},
    )

    with pytest.raises(ZeroWeightSumError):
        TemporalAggregationService().aggregate(
            rule=rule, calculation_context=ctx,
            scope_type="linha_grupo", scope_value="L1_L7",
            run_date=RUN_DATE,
        )


def test_monthly_window_excludes_the_previous_month(rules):
    """
    Um dia do mês anterior com valor e peso extremos não pode
    contaminar a agregação do mês corrente.
    """

    rule = _rule_by_target(rules, "VAR18028", "WEIGHTED_AVERAGE")

    ctx = _prepare_context(rule, "linha_grupo", "L1_L7")

    for variable_id in (
        rule.source_variable_id, rule.weight_variable_id,
    ):
        ctx.set_variable_value(
            variable_id, 999999.0, "linha_grupo", "L1_L7",
            period_id="2026-08-31",
        )

    result = TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=RUN_DATE,
    )

    assert result.value == pytest.approx(
        _weighted_average(), rel=1e-12,
    )


# ============================================================
# MOVING_AVERAGE — fronteiras
# ============================================================


def _moving_average_context(rule, daily_values):
    ctx = CalculationContext()

    _populate(
        ctx, rule.source_variable_id, "linha_grupo", "L1_L7",
        daily_values,
    )

    return ctx


def _run_moving_average(rule, ctx, run_date):
    return TemporalAggregationService().aggregate(
        rule=rule, calculation_context=ctx,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=run_date,
    ).value


def test_moving_average_rule_shape(rules):
    rule = _rule_by_target(rules, "VAR18004", "MOVING_AVERAGE")

    assert rule.source_variable_id == "VAR18003"
    assert rule.source_frequency == "diário"
    assert rule.target_frequency == "diário"
    assert rule.weight_variable_id is None


def test_moving_average_on_the_first_day_of_the_month(rules):
    """
    No dia 1 a janela month-to-date tem um único dia: a média é o
    próprio valor do dia.
    """

    rule = _rule_by_target(rules, "VAR18004", "MOVING_AVERAGE")

    ctx = _moving_average_context(rule, {date(2026, 9, 1): 11.0})

    assert _run_moving_average(
        rule, ctx, date(2026, 9, 1),
    ) == pytest.approx(11.0)


def test_moving_average_mid_month_uses_only_days_up_to_run_date(rules):
    """
    A janela vai do dia 1 até run_date, inclusive -- e não inclui os
    dias futuros do mesmo mês, ainda que presentes no contexto.
    """

    rule = _rule_by_target(rules, "VAR18004", "MOVING_AVERAGE")

    ctx = _moving_average_context(
        rule,
        {
            date(2026, 9, 1): 11.0,
            date(2026, 9, 2): 23.0,
            date(2026, 9, 3): 37.0,
            # futuro em relação a run_date: deve ser ignorado
            date(2026, 9, 4): 999999.0,
        },
    )

    assert _run_moving_average(
        rule, ctx, date(2026, 9, 3),
    ) == pytest.approx((11.0 + 23.0 + 37.0) / 3)


def test_moving_average_at_month_end_covers_the_whole_month(rules):
    rule = _rule_by_target(rules, "VAR18004", "MOVING_AVERAGE")

    september = [
        date(2026, 9, 1) + timedelta(days=offset)
        for offset in range(30)
    ]

    values = {
        day: float(index + 1)
        for index, day in enumerate(september)
    }

    ctx = _moving_average_context(rule, values)

    expected = sum(range(1, 31)) / 30

    assert expected == pytest.approx(15.5)

    assert _run_moving_average(
        rule, ctx, date(2026, 9, 30),
    ) == pytest.approx(expected)


def test_moving_average_resets_on_month_change(rules):
    """
    Na virada do mês a janela recomeça: o dia 1 de outubro não herda
    nenhum dia de setembro, mesmo com setembro inteiro no contexto.
    """

    rule = _rule_by_target(rules, "VAR18004", "MOVING_AVERAGE")

    values = {
        date(2026, 9, 1) + timedelta(days=offset): 100.0
        for offset in range(30)
    }
    values[date(2026, 10, 1)] = 7.0

    ctx = _moving_average_context(rule, values)

    assert _run_moving_average(
        rule, ctx, date(2026, 9, 30),
    ) == pytest.approx(100.0)

    assert _run_moving_average(
        rule, ctx, date(2026, 10, 1),
    ) == pytest.approx(7.0)
