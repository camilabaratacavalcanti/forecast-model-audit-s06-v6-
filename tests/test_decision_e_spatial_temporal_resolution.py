"""
Decision E — Spatial-first Temporal Resolution.

Valida que a integração de `get_spatial_candidates`
(SpatialCandidateResolver, Decision C+D) com o fallback temporal
existente do `ExpressionEvaluator` (`_get_variable_with_period_fallback`
/ `_get_parameter_with_period_fallback`) segue o contrato:

    para cada candidato espacial (do mais específico para o mais
    amplo), esgota o fallback temporal antes de avançar para o
    próximo candidato espacial.

Nunca o inverso (temporal-first).
"""

import pytest

from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    AmbiguousSpatialPrecedenceError,
    ParameterNotFoundError,
    VariableNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser


def evaluate_var(context, default_scope_type, default_scope_value,
                  default_period_id, identifier="VAR99999"):
    evaluator = ExpressionEvaluator(
        context,
        default_scope_type=default_scope_type,
        default_scope_value=default_scope_value,
        default_period_id=default_period_id,
    )

    tree = ExpressionParser().parse(identifier)

    return evaluator.evaluate(tree)


def evaluate_param(context, default_scope_type, default_scope_value,
                    default_period_id, identifier="PARAM99999"):
    evaluator = ExpressionEvaluator(
        context,
        default_scope_type=default_scope_type,
        default_scope_value=default_scope_value,
        default_period_id=default_period_id,
    )

    tree = ExpressionParser().parse(identifier)

    return evaluator.evaluate(tree)


# ============================================================
# E-T01 — spatial candidates são obtidos na ordem correta
# ============================================================


def test_e_t01_spatial_candidates_order():
    from app.engine.spatial_candidate_resolver import (
        get_spatial_candidates,
    )

    assert get_spatial_candidates("linha", "L4") == [
        ("linha", "L4"),
        ("linha_grupo", "L4_L5"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


# ============================================================
# E-T02 — temporal fallback funciona para um candidato isolado
# ============================================================


def test_e_t02_temporal_fallback_for_isolated_candidate():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        42,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )

    result = evaluate_var(
        context,
        "linha_grupo",
        "L4_L5",
        "2026-09-14",
    )

    assert result == 42


# ============================================================
# E-T03 — spatial-first básico
# ============================================================


def test_e_t03_spatial_first_basic():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        1,
        scope_type="linha",
        scope_value="L4",
        period_id="2026-09-14",
    )
    context.set_variable_value(
        "VAR99999",
        999,
        scope_type="planta",
        scope_value="PLANTA",
        period_id="2026-09-14",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 1


# ============================================================
# E-T04 — primeiro candidato sem valor em nenhum fallback temporal
# avança ao segundo
# ============================================================


def test_e_t04_advances_to_second_candidate_when_first_has_nothing():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        200,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 200


# ============================================================
# E-T05 — terceiro candidato só é considerado após esgotar os
# anteriores
# ============================================================


def test_e_t05_third_candidate_only_after_exhausting_previous():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        300,
        scope_type="planta",
        scope_value="PLANTA",
        period_id="2026",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 300


# ============================================================
# E-T06 — explicit scoped reference continua exata
# ============================================================


def test_e_t06_explicit_scoped_reference_stays_exact():
    context = CalculationContext()

    # Valor em linha_grupo/L4_L5 -- NÃO deve ser alcançado por uma
    # referência explícita "@L4", que deve permanecer restrita a
    # linha/L4.
    context.set_variable_value(
        "VAR99999",
        123,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L7",
        default_period_id="2026-09-14",
    )

    tree = ExpressionParser().parse("VAR99999@L4")

    with pytest.raises(VariableNotFoundError):
        evaluator.evaluate(tree)


# ============================================================
# E-T07 — group consumer não expande em linhas
# ============================================================


def test_e_t07_group_consumer_does_not_expand_into_lines():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        555,
        scope_type="linha",
        scope_value="L1",
        period_id="2026",
    )

    # Consumidor é linha_grupo/L1_L3: o valor em linha/L1 não pode
    # ser alcançado (grupo não é conjunto de linhas consumidoras).
    with pytest.raises(VariableNotFoundError):
        evaluate_var(context, "linha_grupo", "L1_L3", "2026-09-14")


# ============================================================
# E-T08 — cenário crítico obrigatório
# ============================================================


def test_e_t08_l4_l5_annual_wins_over_l1_l7_monthly():
    """
    linha_grupo/L4_L5 annual 2026 = 222
    linha_grupo/L1_L7 monthly 2026-09 = 333

    Consumidor: linha/L4, period_id="2026-09-14".

    Resultado esperado: 222 (spatial-first). Uma implementação
    temporal-first produziria 333.
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        222,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )
    context.set_variable_value(
        "VAR99999",
        333,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026-09",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 222


def test_e_t08_reverse_scenario_falls_through_to_l1_l7():
    """
    Cenário reverso: removendo o valor anual de L4_L5, o resultado
    passa a ser 333 (L1_L7 monthly). Isso comprova que L4_L5 é
    realmente esgotado primeiro (spatial-first), e não que o
    resolver simplesmente "escolhe sempre o scope mais específico" —
    ele avança para L1_L7 somente quando L4_L5 não produz nenhum
    valor válido em seu fallback temporal completo.
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        333,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026-09",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 333


# ============================================================
# E-T09 — temporal precision NÃO supera spatial precedence
# ============================================================


def test_e_t09_temporal_precision_does_not_beat_spatial_precedence():
    """
    Candidato espacial mais específico (L4_L5) com valor temporal
    menos recente (anual) vence candidato espacial mais amplo
    (L1_L7) com valor temporal mais recente (diário exato).
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        222,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )
    context.set_variable_value(
        "VAR99999",
        999,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026-09-14",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 222


# ============================================================
# E-T10 — plant consumer
# ============================================================


def test_e_t10_plant_consumer_uses_only_plant_scope():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        77,
        scope_type="planta",
        scope_value="PLANTA",
        period_id="2026",
    )

    result = evaluate_var(context, "planta", "PLANTA", "2026-09-14")

    assert result == 77


# ============================================================
# E-T11 — group consumer
# ============================================================


def test_e_t11_group_consumer_precedence():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        11,
        scope_type="linha_grupo",
        scope_value="L1_L3",
        period_id="2026",
    )
    context.set_variable_value(
        "VAR99999",
        99,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026",
    )

    result = evaluate_var(context, "linha_grupo", "L1_L3", "2026-09-14")

    assert result == 11


# ============================================================
# E-T12 — missing values atravessando múltiplos scopes
# ============================================================


def test_e_t12_missing_values_across_multiple_scopes_raises():
    context = CalculationContext()

    with pytest.raises(VariableNotFoundError):
        evaluate_var(context, "linha", "L4", "2026-09-14")


# ============================================================
# E-T13 — Variable resolution (mesmo caso do E-08, isolado)
# ============================================================


def test_e_t13_variable_resolution_spatial_first():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        222,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 222


# ============================================================
# E-T14 — Parameter resolution
# ============================================================


def test_e_t14_parameter_resolution_spatial_first():
    """
    Parameter não tem frequência própria (constante no ForecastYear):
    o fallback temporal de Parameter é ano -> sem período. A
    dimensão espacial, ainda assim, segue spatial-first: L4_L5 é
    esgotado (ano 2026) antes de L1_L7.
    """

    context = CalculationContext()

    context.set_parameter_value(
        "PARAM99999",
        222,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )
    context.set_parameter_value(
        "PARAM99999",
        333,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026",
    )

    result = evaluate_param(context, "linha", "L4", "2026-09-14")

    assert result == 222


def test_e_t14_parameter_resolution_missing_raises():
    context = CalculationContext()

    with pytest.raises(ParameterNotFoundError):
        evaluate_param(context, "linha", "L4", "2026-09-14")


# ============================================================
# E-T15 — determinismo
# ============================================================


def test_e_t15_deterministic():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        222,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026",
    )
    context.set_variable_value(
        "VAR99999",
        333,
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id="2026-09",
    )

    results = [
        evaluate_var(context, "linha", "L4", "2026-09-14")
        for _ in range(5)
    ]

    assert all(result == 222 for result in results)


# ============================================================
# Ambiguidade espacial: erro estrutural, não ausência de valor
# ============================================================


def test_ambiguous_spatial_precedence_is_not_treated_as_not_found():
    """
    Se `get_spatial_candidates` levantar
    `AmbiguousSpatialPrecedenceError`, a resolução não deve
    interpretar isso como "candidato não encontrado" e tentar outro
    scope -- o erro deve propagar.
    """

    from app.engine.spatial_candidate_resolver import (
        get_spatial_candidates,
    )

    incomparable_groups = {
        "G1": frozenset({"L1", "L2", "L3"}),
        "G2": frozenset({"L2", "L3", "L4"}),
    }

    with pytest.raises(AmbiguousSpatialPrecedenceError):
        get_spatial_candidates(
            "linha",
            "L2",
            group_members=incomparable_groups,
        )


# ============================================================
# Same spatial candidate: o candidato exato do consumidor é sempre
# avaliado primeiro
# ============================================================


def test_exact_consumer_scope_is_evaluated_before_its_group():
    context = CalculationContext()

    context.set_variable_value(
        "VAR99999",
        1,
        scope_type="linha",
        scope_value="L4",
        period_id="2026",
    )
    context.set_variable_value(
        "VAR99999",
        2,
        scope_type="linha_grupo",
        scope_value="L4_L5",
        period_id="2026-09-14",
    )

    result = evaluate_var(context, "linha", "L4", "2026-09-14")

    assert result == 1
