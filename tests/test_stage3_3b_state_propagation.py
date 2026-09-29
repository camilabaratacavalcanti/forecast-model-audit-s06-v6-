"""
Etapa 3.3B — propagação causal de estado e isolamento.

Contrato (Etapa 2.2 D1/D2/D3 + R1 da 2.3; Etapa 3.3A):

    * Result(value, state, detail); estados = NO_APPLICABLE_RULE,
      INVALID_INPUT, VALIDATION_FAILED. Um resultado com estado não tem
      valor (value None, §13).
    * "F" só é estado para a variável alvo que o declara
      (declared_result_states); tradução por variável, nunca global.
    * O estado propaga somente pelas dependências reais da equação
      (referências da expressão) e pelas transferências interbloco;
      proximidade (mesmo bloco, instância, período, execução) não propaga.
    * Estados diferentes numa mesma equação: MULTI_STATE_COMBINATION_UNDEFINED.
      Details diferentes: MULTI_DETAIL_COMPOSITION_UNDEFINED. Nenhuma
      prioridade ou composição é escolhida.
    * Agregação temporal state-aware: STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C.

Cenários:
    SYNTHETIC     catálogo mínimo em memória (documentado abaixo).
    REAL_DERIVED  seeds reais, pendências tratadas como entradas livres
                  SOMENTE no fixture (mesmo fixture da Etapa 3.2).
    OFFICIAL      seeds oficiais sem alteração.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import (
    AggregationRule,
    AggregationRuleInstance,
    AggregationRuleInstanceRegistry,
)
from app.domain.interblock.registry import InterblockLinkRegistry
from app.domain.parameters.registry import ParameterInstanceRegistry
from app.domain.results import (
    DetailWithoutStateError,
    Result,
    ResultContractError,
    StateAwareAggregationPendingError,
    StatedResultConsumedAsValueError,
    StatefulResultOnScalarApiError,
)
from app.domain.state_propagation import (
    MultiDetailCompositionUndefinedError,
    MultiStateCombinationUndefinedError,
    inherit_from_dependencies,
    translate_declared_literal,
)
from app.domain.values import RESULT_STATE_TAXONOMY
from app.domain.variables.models import DeclaredResultState, VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    CalculationValueError,
    InterblockConsumerValueConflictError,
    InterblockSourceNotLoadedError,
    VariableNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.engine.interblock_orchestrator import (
    AGGREGATION,
    EQUATION,
    TRANSFER,
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)
from app.engine.scope_resolver import ScopeResolver
from tests.test_stage3_2_execution_orchestration import (
    LINES,
    SEED,
    eq,
    execute_real,
    link,
    real_derived_orchestrator,
    real_inputs,
    vdef,
)


REPO = Path(__file__).resolve().parents[1]
RUN = date(2026, 9, 1)
DAY = "2026-09-01"
MONTH = "2026-09"
YEAR = "2026"

INVALID = "INVALID_INPUT"
NAR = "NO_APPLICABLE_RULE"
VFAIL = "VALIDATION_FAILED"


# ============================================================
# Catálogo SINTÉTICO (documentado)
# ============================================================
#
# production (linha L1_L7, diário):
#   A  VAR12911 entrada
#   B  VAR12912 = A * 2                  cadeia A -> B -> C
#   C  VAR12913 = B + 1
#   D  VAR12914 = A + 5                  ramo A -> D
#   M  VAR12915 = B + D                  merge B -> M <- D
#   X  VAR12916 entrada;  Y VAR12917 = X * 3        independente
#   P  VAR12918, Q VAR12919 entradas; S VAR12920 = P + Q; S2 VAR12921 = Q + P
#   FD VAR12922 = "F" if A > 100 else A  (declara NO_APPLICABLE_RULE -> "F")
#   FR VAR12923 = "F" if A > 100 else A  (NÃO declara: "F" é valor bruto)
#   G  VAR12924 = FD + 1
#   MX VAR12925 = A + X                  duas origens independentes
#   BM VAR12926 mensal  = AVERAGE(B)     agregação diário -> mensal
#   AN VAR12927 anual entrada
#   GR VAR12929 linha_grupo L1_L3 = C@L1 + C@L2 + C@L3
#   GS VAR12930 linha_grupo L4_L5 = C@L4 + C@L5
# yield:    YB VAR11911 <- production.B;  YC VAR11912 = YB + 1
#           YI VAR11913 entrada;          YJ VAR11914 = YI + 1   (mesmo bloco, independente)
# area_41:  AB VAR16911 <- yield.YB;      AC VAR16912 = AB * 10
#           AY VAR16913 <- yield.YC
# energy:   EM VAR18911 <- production.BM (mensal)
#           EA VAR18912 <- production.AN (anual)

A, B, C, D, M = "VAR12911", "VAR12912", "VAR12913", "VAR12914", "VAR12915"
X, Y, P, Q, S, S2 = "VAR12916", "VAR12917", "VAR12918", "VAR12919", "VAR12920", "VAR12921"
FD, FR, G, MX, BM, AN = "VAR12922", "VAR12923", "VAR12924", "VAR12925", "VAR12926", "VAR12927"
GR, GS = "VAR12929", "VAR12930"
YB, YC, YI, YJ = "VAR11911", "VAR11912", "VAR11913", "VAR11914"
AB, AC, AY = "VAR16911", "VAR16912", "VAR16913"
EM, EA = "VAR18911", "VAR18912"

DECLARES_F = (DeclaredResultState(state=NAR, literal="F"),)


def declaring(definition):
    return VariableDefinition(
        definition.variable_definition_id, definition.variable_name, definition.description,
        definition.unit, definition.variable_type, definition.frequency, definition.scope_type,
        definition.scope_value, definition.source_reference, definition.status,
        definition.value_type, declared_result_states=DECLARES_F,
    )


def prop_catalog(equations_order=None, links_order=None, blocks_order=None):
    calc = {"variable_type": "calculado"}
    variables = {
        "production": [
            vdef(A, "a"), vdef(B, "b", **calc), vdef(C, "c", **calc), vdef(D, "d", **calc),
            vdef(M, "m", **calc), vdef(X, "x"), vdef(Y, "y", **calc), vdef(P, "p"), vdef(Q, "q"),
            vdef(S, "s", **calc), vdef(S2, "s2", **calc),
            declaring(vdef(FD, "f_decl", **calc)), vdef(FR, "f_raw", **calc),
            vdef(G, "g", **calc), vdef(MX, "mx", **calc),
            vdef(BM, "b_mes", "mensal", **calc), vdef(AN, "an", "anual"),
            vdef(GR, "gr", scope_type="linha_grupo", scope_value="L1_L3", **calc),
            vdef(GS, "gs", scope_type="linha_grupo", scope_value="L4_L5", **calc),
        ],
        "yield": [vdef(YB, "yb"), vdef(YC, "yc", **calc), vdef(YI, "yi"), vdef(YJ, "yj", **calc)],
        "area_41": [vdef(AB, "ab"), vdef(AC, "ac", **calc), vdef(AY, "ay")],
        "energy": [vdef(EM, "em", "mensal"), vdef(EA, "ea", "anual")],
    }
    equations = [
        ("production", eq("EQ12911", B, f"{A} * 2")),
        ("production", eq("EQ12912", C, f"{B} + 1")),
        ("production", eq("EQ12913", D, f"{A} + 5")),
        ("production", eq("EQ12914", M, f"{B} + {D}")),
        ("production", eq("EQ12915", Y, f"{X} * 3")),
        ("production", eq("EQ12916", S, f"{P} + {Q}")),
        ("production", eq("EQ12917", S2, f"{Q} + {P}")),
        ("production", eq("EQ12918", FD, f'"F" if {A} > 100 else {A}')),
        ("production", eq("EQ12919", FR, f'"F" if {A} > 100 else {A}')),
        ("production", eq("EQ12920", G, f"{FD} + 1")),
        ("production", eq("EQ12921", MX, f"{A} + {X}")),
        ("production", eq("EQ12922", GR, f"{C}@L1 + {C}@L2 + {C}@L3", "linha_grupo", "L1_L3")),
        ("production", eq("EQ12923", GS, f"{C}@L4 + {C}@L5", "linha_grupo", "L4_L5")),
        ("yield", eq("EQ11911", YC, f"{YB} + 1")),
        ("yield", eq("EQ11912", YJ, f"{YI} + 1")),
        ("area_41", eq("EQ16911", AC, f"{AB} * 10")),
    ]
    if equations_order is not None:
        equations = [equations[i] for i in equations_order]
    rule = AggregationRule(
        aggregation_rule_id="AGR-PRODUCTION-B_MES", source_variable_id=B,
        source_frequency="diário", target_variable_id=BM, target_frequency="mensal",
        aggregation_type="AVERAGE",
    )
    links = [
        link("yield", YB, "production", B),
        link("area_41", AB, "yield", YB),
        link("area_41", AY, "yield", YC),
        link("energy", EM, "production", BM, "mensal"),
        link("energy", EA, "production", AN, "anual"),
    ]
    if links_order is not None:
        links = [links[i] for i in links_order]
    payload = {
        "workbooks": {b: {} for b in variables},
        "taxonomy": {"official_blocks": ["production", "yield", "area_41", "energy", "maintenance"]},
        "links": links, "pending": [], "rejected": [],
    }
    order = blocks_order or list(variables)
    raw = {
        b: [{"variable_id": v.variable_definition_id, "variable_name": v.variable_name,
             "unit": v.unit, "frequency": v.frequency, "scope_type": v.scope_type,
             "scope_value": v.scope_value, "value_type": v.value_type} for v in variables[b]]
        for b in order
    }
    variable_registry = VariableDefinitionRegistry()
    block_of = {}
    for b in order:
        for v in variables[b]:
            variable_registry.add(v)
            block_of[v.variable_definition_id] = b
    equation_registry = EquationDefinitionRegistry()
    for b, e in equations:
        equation_registry.add(e)
        block_of[e.equation_definition_id] = b
    aggregations = AggregationRuleInstanceRegistry()
    for scope_type, scope_value in ScopeResolver().resolve_scopes("linha", "L1_L7"):
        aggregations.add(AggregationRuleInstance.create(rule, scope_type, scope_value))
    block_of[rule.aggregation_rule_id] = "production"
    catalog = ExecutionCatalog(
        variable_registry, equation_registry, aggregations, ParameterInstanceRegistry(),
        InterblockLinkRegistry.from_payload(payload, raw), block_of,
    )
    return InterblockExecutionOrchestrator(catalog)


def seed_inputs(context, overrides=None, day=DAY):
    """Entradas numéricas; `overrides` = {(var, line): Result} só nas instâncias pedidas."""
    overrides = overrides or {}
    for i, line in enumerate(LINES, start=1):
        for variable, value in ((A, 10.0 * i), (X, 1.0 * i), (P, 2.0 * i), (Q, 3.0 * i), (YI, 7.0 * i)):
            result = overrides.get((variable, line), Result(value))
            context.set_variable_result(variable, result, "linha", line, day)
        context.set_variable_result(AN, overrides.get((AN, line), Result(500.0 + i)), "linha", line, YEAR)


def run_prop(targets, overrides=None, orchestrator=None, context=None, run_date=RUN):
    orchestrator = orchestrator or prop_catalog()
    context = context or CalculationContext()
    seed_inputs(context, overrides, run_date.isoformat())
    return orchestrator.execute(targets, context, run_date), context


def res(context, variable, line, period=DAY, scope_type="linha"):
    return context.get_variable_result(variable, scope_type, line, period)


def stated(state, detail=None):
    return Result(None, state, detail)


def snapshot(context):
    return sorted(
        ((k.entity_id, k.scope_type or "", k.scope_value or "", k.period_id or ""),
         (r.value, r.state, r.detail))
        for k, r in context._scoped_results.items()
    )


# ============================================================
# 1..5 Estado básico
# ============================================================

def test_01_taxonomy_is_exactly_the_three_proven_states_and_no_ok():
    assert set(RESULT_STATE_TAXONOMY) == {NAR, INVALID, VFAIL}
    assert "OK" not in RESULT_STATE_TAXONOMY
    with pytest.raises(ResultContractError):
        Result(None, "OK")
    with pytest.raises(ResultContractError):
        Result(None, "BLOCKED_BY_UPSTREAM_ERROR")


def test_02_stated_result_has_no_value_and_valueless_plain_result_is_rejected():
    assert stated(INVALID).value is None
    with pytest.raises(ResultContractError):
        Result(None)
    assert Result(3.0).is_plain and not stated(NAR).is_plain


def test_03_input_state_and_detail_are_stored_and_read_back_unchanged():
    context = CalculationContext()
    detail = "  leitura  manual \n"
    context.set_variable_result(A, stated(VFAIL, detail), "linha", "L3", DAY)
    assert res(context, A, "L3") == Result(None, VFAIL, detail)


def test_04_declared_literal_f_becomes_no_applicable_rule_only_for_the_declaring_target():
    trace, context = run_prop([FD, FR], {(A, "L2"): Result(150.0)})
    assert res(context, FD, "L2") == stated(NAR)
    assert res(context, FR, "L2") == Result("F")           # não declara: valor bruto
    assert res(context, FD, "L1") == Result(10.0)
    assert translate_declared_literal("F", None) == Result("F")
    assert translate_declared_literal("G", declaring(vdef(FD, "f"))) == Result("G")


def test_05_parameters_stay_non_stateful():
    context = CalculationContext()
    context.set_parameter_value("PAR99901", 1.5, "linha", "L1", DAY)
    assert context.get_parameter_value("PAR99901", "linha", "L1", DAY) == 1.5
    with pytest.raises(CalculationValueError):
        context.set_parameter_value("PAR99901", Result(None, INVALID), "linha", "L1", DAY)


# ============================================================
# 6..10 Propagação simples
# ============================================================

def test_06_direct_dependency_inherits_the_state():
    _, context = run_prop([B], {(A, "L2"): stated(INVALID)})
    assert res(context, B, "L2") == stated(INVALID)


def test_07_state_propagates_transitively_along_the_chain():
    _, context = run_prop([C], {(A, "L2"): stated(INVALID)})
    assert res(context, B, "L2") == stated(INVALID)
    assert res(context, C, "L2") == stated(INVALID)


def test_08_single_origin_detail_is_preserved_byte_for_byte():
    detail = " sensor\toffline "
    _, context = run_prop([C], {(A, "L2"): stated(INVALID, detail)})
    assert res(context, C, "L2") == Result(None, INVALID, detail)


def test_09_translated_state_propagates_to_the_heir_which_does_not_redeclare_it():
    _, context = run_prop([G], {(A, "L4"): Result(999.0)})
    assert res(context, FD, "L4") == stated(NAR)
    assert res(context, G, "L4") == stated(NAR)
    assert res(context, G, "L3") == Result(31.0)


def test_10_each_of_the_three_states_propagates_unchanged():
    for state in sorted(RESULT_STATE_TAXONOMY):
        _, context = run_prop([C], {(A, "L1"): stated(state)})
        assert res(context, C, "L1") == stated(state)


# ============================================================
# 11..15 Isolamento
# ============================================================

def test_11_a_to_b_with_independent_c_same_block_is_untouched():
    """A->B com X->Y independente no MESMO bloco e instância."""
    _, context = run_prop([B, Y], {(A, "L2"): stated(INVALID)})
    assert res(context, B, "L2") == stated(INVALID)
    assert res(context, Y, "L2") == Result(6.0)


def test_12_chain_a_b_c_with_independent_x_y():
    _, context = run_prop([C, Y], {(A, "L2"): stated(INVALID)})
    assert res(context, C, "L2") == stated(INVALID)
    for i, line in enumerate(LINES, start=1):
        assert res(context, Y, line) == Result(3.0 * i)


def test_13_other_instances_of_the_same_variable_are_untouched():
    _, context = run_prop([C], {(A, "L2"): stated(INVALID)})
    for i, line in enumerate(LINES, start=1):
        if line != "L2":
            assert res(context, C, line) == Result(20.0 * i + 1)


def test_14_same_block_same_execution_unrelated_variable_is_untouched():
    _, context = run_prop([YC, YJ], {(A, "L1"): stated(INVALID)})
    assert res(context, YC, "L1") == stated(INVALID)
    assert res(context, YJ, "L1") == Result(8.0)


def test_15_other_periods_are_untouched():
    context = CalculationContext()
    orchestrator = prop_catalog()
    run_prop([C], {(A, "L2"): stated(INVALID)}, orchestrator, context, date(2026, 9, 1))
    run_prop([C], None, orchestrator, context, date(2026, 9, 2))
    assert res(context, C, "L2", "2026-09-01") == stated(INVALID)
    assert res(context, C, "L2", "2026-09-02") == Result(41.0)


# ============================================================
# 16..19 Branching
# ============================================================

def test_16_fan_out_a_to_b_and_a_to_d_both_inherit():
    _, context = run_prop([B, D], {(A, "L5"): stated(VFAIL, "x")})
    assert res(context, B, "L5") == Result(None, VFAIL, "x")
    assert res(context, D, "L5") == Result(None, VFAIL, "x")


def test_17_merge_of_the_same_origin_is_a_single_state_not_a_combination():
    """B->M<-D, ambos herdando o MESMO estado/detail de A: sem combinação."""
    _, context = run_prop([M], {(A, "L5"): stated(VFAIL, "x")})
    assert res(context, M, "L5") == Result(None, VFAIL, "x")


def test_18_merge_with_one_stated_and_one_plain_branch_inherits_the_state():
    _, context = run_prop([MX], {(A, "L3"): stated(INVALID)})
    assert res(context, MX, "L3") == stated(INVALID)
    assert res(context, MX, "L4") == Result(44.0)


def test_19_group_reference_inherits_only_from_referenced_instances():
    _, context = run_prop([GR, GS], {(A, "L2"): stated(INVALID)})
    assert res(context, GR, "L1_L3", scope_type="linha_grupo") == stated(INVALID)
    assert res(context, GS, "L4_L5", scope_type="linha_grupo") == Result(81.0 + 101.0)


# ============================================================
# 20..25 Dependência múltipla
# ============================================================

def test_20_different_states_raise_multi_state_combination_undefined():
    with pytest.raises(MultiStateCombinationUndefinedError) as error:
        run_prop([MX], {(A, "L3"): stated(INVALID), (X, "L3"): stated(VFAIL)})
    assert error.value.code == "MULTI_STATE_COMBINATION_UNDEFINED"
    assert INVALID in str(error.value) and VFAIL in str(error.value)


def test_21_multi_state_error_is_independent_of_operand_order():
    messages = set()
    for target in (S, S2):
        with pytest.raises(MultiStateCombinationUndefinedError) as error:
            run_prop([target], {(P, "L1"): stated(NAR), (Q, "L1"): stated(INVALID)})
        messages.add(str(error.value).replace(target, "<T>"))
    assert len(messages) == 1


def test_22_same_state_different_details_raise_multi_detail_composition_undefined():
    for target in (S, S2):
        with pytest.raises(MultiDetailCompositionUndefinedError) as error:
            run_prop([target], {(P, "L1"): stated(INVALID, "p"), (Q, "L1"): stated(INVALID, "q")})
        assert error.value.code == "MULTI_DETAIL_COMPOSITION_UNDEFINED"


def test_23_same_state_and_detail_from_two_origins_is_order_independent():
    results = set()
    for target in (S, S2):
        _, context = run_prop([target], {(P, "L1"): stated(INVALID, "d"), (Q, "L1"): stated(INVALID, "d")})
        results.add(res(context, target, "L1"))
    assert results == {Result(None, INVALID, "d")}


def test_24_no_priority_between_states_is_chosen_for_any_pair():
    """Política de combinação NÃO definida pelo contrato: cada par é erro."""
    states = sorted(RESULT_STATE_TAXONOMY)
    for first in states:
        for second in states:
            if first == second:
                continue
            with pytest.raises(MultiStateCombinationUndefinedError):
                inherit_from_dependencies("T", [
                    (("P", "linha", "L1", DAY), stated(first)),
                    (("Q", "linha", "L1", DAY), stated(second)),
                ])


def test_25_detail_without_state_is_invalid_at_construction():
    """
    LEGACY_TEST_EXPECTATION (fechamento 3.3B, D33B-03): antes a dependência
    com detail e sem estado levantava DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED
    na propagação; agora detail sem estado é inválido já no Result.
    """
    with pytest.raises(DetailWithoutStateError) as error:
        Result(1.0, None, "nota")
    assert error.value.code == "DETAIL_WITHOUT_STATE"
    assert inherit_from_dependencies("T", [(("P", "linha", "L1", DAY), Result(1.0))]) is None


# ============================================================
# 26..30 Interbloco
# ============================================================

def test_26_transfer_carries_the_stated_result_unchanged():
    trace, context = run_prop([YB], {(A, "L2"): stated(INVALID, "d")})
    assert res(context, YB, "L2") == Result(None, INVALID, "d")
    event = [e for e in trace.of_kind(TRANSFER) if e.scope_value == "L2"][0]
    assert (event.value, event.state, event.detail) == (None, INVALID, "d")


def test_27_state_crosses_production_yield_area_41_and_feeds_equations():
    _, context = run_prop([AC, AY], {(A, "L2"): stated(INVALID)})
    for variable in (B, YB, YC, AB, AC, AY):
        assert res(context, variable, "L2") == stated(INVALID)
    assert res(context, AC, "L1") == Result(200.0)


def test_28_transfer_never_creates_a_state():
    trace, context = run_prop([AB])
    assert {(e.state, e.detail) for e in trace.of_kind(TRANSFER)} == {(None, None)}
    assert all(res(context, AB, line).is_plain for line in LINES)


def test_29_transfer_keeps_link_instance_and_period_identity():
    trace, context = run_prop([AB], {(A, "L6"): stated(NAR)})
    events = [e for e in trace.of_kind(TRANSFER) if e.state is not None]
    assert sorted((e.node_id, e.scope_type, e.scope_value, e.period_id, e.source_block) for e in events) == [
        (YB, "linha", "L6", DAY, "production"), (AB, "linha", "L6", DAY, "yield"),
    ]


def test_30_rerun_with_a_different_state_is_the_existing_conflict_not_an_overwrite():
    orchestrator = prop_catalog()
    _, context = run_prop([YB], {(A, "L2"): stated(INVALID)}, orchestrator)
    context.set_variable_result(YB, stated(VFAIL), "linha", "L2", DAY)
    with pytest.raises(InterblockConsumerValueConflictError):
        orchestrator.execute([YB], context, RUN)
    assert res(context, YB, "L2") == stated(VFAIL)
    assert res(context, B, "L2") == stated(INVALID)


# ============================================================
# 31..35 Temporal
# ============================================================

def test_31_inherited_state_is_stored_on_the_target_period_only():
    _, context = run_prop([C], {(A, "L2"): stated(INVALID)})
    keys = [k for k in context._scoped_results if k.entity_id == C and k.scope_value == "L2"]
    assert [k.period_id for k in keys] == [DAY]


def test_32_daily_to_monthly_aggregation_over_a_state_composes_it():
    """
    LEGACY_TEST_EXPECTATION (Etapa 3.3C): antes, fronteira
    STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C; agora Policy B — o estado
    herdado (sem value) é preservado no resultado mensal, sem value.
    """
    _, context = run_prop([BM], {(A, "L2"): stated(INVALID)})
    assert res(context, BM, "L2", MONTH) == stated(INVALID)
    assert res(context, BM, "L1", MONTH) == Result(20.0)


def test_33_aggregation_without_state_is_unchanged():
    trace, context = run_prop([BM])
    assert res(context, BM, "L2", MONTH) == Result(40.0)
    assert {e.period_id for e in trace.of_kind(AGGREGATION)} == {MONTH}


def test_34_monthly_consumer_receives_the_aggregated_state():
    """LEGACY_TEST_EXPECTATION (Etapa 3.3C): o estado agregado atravessa o vínculo mensal."""
    _, context = run_prop([EM], {(A, "L2"): stated(INVALID, "d")})
    assert res(context, EM, "L2", MONTH) == stated(INVALID, "d")
    assert res(context, EM, "L3", MONTH) == Result(60.0)


def test_35_annual_state_transfers_on_the_annual_period():
    trace, context = run_prop([EA], {(AN, "L7"): stated(VFAIL)})
    assert res(context, EA, "L7", YEAR) == stated(VFAIL)
    assert res(context, EA, "L6", YEAR) == Result(506.0)
    assert {e.period_id for e in trace.events} == {YEAR}


# ============================================================
# 36..39 Runtime
# ============================================================

def test_36_equation_event_records_state_and_no_value():
    trace, _ = run_prop([B], {(A, "L2"): stated(INVALID, "d")})
    event = [e for e in trace.of_kind(EQUATION) if e.scope_value == "L2"][0]
    assert (event.value, event.state, event.detail, event.status) == (None, INVALID, "d", "WRITTEN")


def test_37_scalar_api_on_a_stated_result_is_an_explicit_error():
    _, context = run_prop([B], {(A, "L2"): stated(INVALID)})
    with pytest.raises(StatefulResultOnScalarApiError) as error:
        context.get_variable_value(B, "linha", "L2", DAY)
    assert error.value.code == "STATEFUL_RESULT_ON_SCALAR_API"
    assert not isinstance(error.value, (ValueError, VariableNotFoundError, ArithmeticError))


def test_38_direct_evaluator_never_uses_a_state_as_a_number():
    context = CalculationContext()
    context.set_variable_result(A, stated(INVALID), "linha", "L1", DAY)
    evaluator = ExpressionEvaluator(context, default_scope_type="linha", default_scope_value="L1",
                                    default_period_id=DAY)
    with pytest.raises(StatedResultConsumedAsValueError) as error:
        evaluator.evaluate(ExpressionParser().parse(f"{A} * 2"))
    assert error.value.code == "STATED_RESULT_CONSUMED_AS_VALUE"
    assert not isinstance(error.value, (ValueError, ArithmeticError))


def test_39_state_errors_are_not_masked_as_math_or_not_found():
    for error in (MultiStateCombinationUndefinedError, MultiDetailCompositionUndefinedError,
                  DetailWithoutStateError, StateAwareAggregationPendingError):
        assert issubclass(error, ResultContractError)
        assert not issubclass(error, (ValueError, ArithmeticError, LookupError))


# ============================================================
# 40..43 Determinismo
# ============================================================

SCENARIO = {(A, "L2"): stated(INVALID, "d"), (X, "L5"): stated(VFAIL), (A, "L6"): Result(999.0)}
TARGETS = [C, M, Y, G, FR, AC, AY, GR, GS, EA]


def fingerprint(orchestrator=None):
    trace, context = run_prop(TARGETS, SCENARIO, orchestrator)
    events = [(e.kind, e.node_id, e.variable_id, e.scope_type, e.scope_value, e.period_id,
               e.value, e.state, e.detail, e.status) for e in trace.events]
    return trace.step_order, events, snapshot(context)


def test_40_same_input_same_result():
    assert fingerprint() == fingerprint()


def test_41_equation_order_does_not_matter():
    base = fingerprint()
    assert fingerprint(prop_catalog(equations_order=list(range(15, -1, -1)))) == base


def test_42_block_and_link_order_do_not_matter():
    base = fingerprint()
    assert fingerprint(prop_catalog(blocks_order=["energy", "area_41", "yield", "production"])) == base
    assert fingerprint(prop_catalog(links_order=[4, 2, 0, 3, 1])) == base


_HASH_SNIPPET = """
import hashlib, sys
sys.path.insert(0, {repo!r})
from tests.test_stage3_3b_state_propagation import fingerprint, real_f_fingerprint
print(hashlib.sha256(repr(fingerprint()).encode()).hexdigest())
print(hashlib.sha256(repr(real_f_fingerprint()).encode()).hexdigest())
"""


def test_43_hash_seed_does_not_matter():
    outputs = set()
    for seed in ("0", "123", "987654321"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outputs.add(subprocess.check_output(
            [sys.executable, "-c", _HASH_SNIPPET.format(repo=str(REPO))], env=env, cwd=REPO,
        ))
    assert len(outputs) == 1


# ============================================================
# REAL_DERIVED — cadeias reais (seeds, equações e vínculos reais)
# ============================================================

@pytest.fixture(scope="module")
def real_derived():
    return real_derived_orchestrator()


A41_F_TARGETS = ["VAR16031", "VAR16034"]


def run_real_f(orchestrator, hes_l5="1 By pass e LC"):
    """hes L4 = Normal e L5 fora de todo ramo de EQ16011 -> "F" em VAR16025."""
    plan = orchestrator.plan(A41_F_TARGETS)
    context = CalculationContext()
    context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
    real_inputs(orchestrator, plan, context)
    context.set_variable_value("VAR16021", "Normal", "linha", "L4", DAY)
    context.set_variable_value("VAR16021", hes_l5, "linha", "L5", DAY)
    return orchestrator.execute(plan, context, RUN), context


def real_f_fingerprint():
    trace, context = run_real_f(real_derived_orchestrator())
    return trace.step_order, snapshot(context)


def test_real_a41_f_producer_and_declared_heirs(real_derived):
    trace, context = run_real_f(real_derived)
    group = lambda v, g: context.get_variable_result(v, "linha_grupo", g, DAY)
    assert group("VAR16025", "L4_L5") == stated(NAR)
    assert res(context, "VAR16031", "L4") == stated(NAR)
    assert res(context, "VAR16031", "L5") == stated(NAR)
    assert group("VAR16034", "L1_L7") == stated(NAR)
    # Isolamento: L1..L3 (VAR16018) e L6..L7 (VAR16028) não dependem de VAR16025.
    assert group("VAR16028", "L6_L7").is_plain and group("VAR16018", "L1_L3").is_plain
    for line in ("L1", "L2", "L3", "L6", "L7"):
        assert res(context, "VAR16031", line).is_plain
    assert "F" not in [r.value for r in context._scoped_results.values()]


def test_real_a41_no_f_when_a_branch_applies(real_derived):
    _, context = run_real_f(real_derived, hes_l5="Normal")
    assert all(r.is_plain for r in context._scoped_results.values())


def test_real_lth_meta_state_crosses_production_yield_area_41(real_derived):
    plan = real_derived.plan(["VAR16008"])
    context = CalculationContext()
    real_inputs(real_derived, plan, context)
    context.set_variable_result("VAR12066", stated(INVALID, "meta"), "linha", "L2", YEAR)
    trace = real_derived.execute(plan, context, RUN)
    for variable in ("VAR12031", "VAR11031", "VAR16007"):
        assert res(context, variable, "L2") == Result(None, INVALID, "meta")
        assert res(context, variable, "L4").is_plain
    assert context.get_variable_result("VAR16008", "linha_grupo", "L1_L3", DAY) == Result(None, INVALID, "meta")
    assert trace.step_order == ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"]


def test_official_lth_meta_state_transfers_to_energy_unchanged():
    official = InterblockExecutionOrchestrator.from_seed_root(SEED)
    plan = official.plan(["VAR18011"])
    context = CalculationContext()
    for i, line in enumerate(LINES, start=1):
        context.set_variable_value("VAR12066", 1000.0 + i, "linha", line, YEAR)
    context.set_variable_result("VAR12066", stated(VFAIL), "linha", "L3", YEAR)
    official.execute(plan, context, RUN)
    assert res(context, "VAR18011", "L3", YEAR) == stated(VFAIL)
    assert res(context, "VAR18011", "L4", YEAR) == Result(1004.0)


# ============================================================
# 44..48 Regressão
# ============================================================

@pytest.mark.parametrize("block,target", [
    ("yield", "VAR11031"), ("production", "VAR12046"), ("energy", "VAR18002"), ("max_ht", "VAR13039"),
])
def test_44_47_real_blocks_stateless_numeric_behavior_unchanged(real_derived, block, target):
    trace, context = execute_real(real_derived, [target])
    assert all(r.is_plain for r in context._scoped_results.values())
    assert all(e.state is None and e.detail is None for e in trace.events)
    written = [r.value for k, r in context._scoped_results.items() if k.entity_id == target]
    assert written and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in written)


def test_45_area_41_real_chain_numeric_values_unchanged(real_derived):
    trace, context = execute_real(real_derived, ["VAR16008"])
    lth = {l: context.get_variable_value("VAR12031", "linha", l, DAY) for l in LINES}
    assert context.get_variable_value("VAR16008", "linha_grupo", "L1_L3", DAY) == pytest.approx(
        (lth["L1"] + lth["L2"] + lth["L3"]) / 3
    )


def test_48_topology_d32_01_preserved_and_d32_02_resolved(real_derived):
    """LEGACY_TEST_EXPECTATION (D33B-04): D32-02 não é mais conflito; janelas coexistem."""
    official = InterblockExecutionOrchestrator.from_seed_root(SEED)
    with pytest.raises(InterblockSourceNotLoadedError):                       # D32-01
        official.plan(["VAR16008"])
    assert [s.key for s in official.plan(["VAR16008"], on_pending="report").steps] == [
        "EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004",
    ]
    orchestrator = prop_catalog()                                             # D32-02
    context = CalculationContext()
    for day in (1, 2):
        seed_inputs(context, {(A, l): Result(float(day)) for l in LINES}, f"2026-09-0{day}")
    orchestrator.execute([EM], context, date(2026, 9, 1))
    orchestrator.execute([EM], context, date(2026, 9, 2))
    assert context.result_windows(EM, "linha", "L1", MONTH) == ("2026-09-01", "2026-09-02")
    assert context.get_variable_value(EM, "linha", "L1", MONTH, as_of=date(2026, 9, 1)) == 2.0
    assert context.get_variable_value(EM, "linha", "L1", MONTH, as_of=date(2026, 9, 2)) == 3.0


def test_forbidden_artifacts_are_not_touched_by_the_propagation_module():
    tree = ast.parse((REPO / "app/domain/state_propagation.py").read_text(encoding="utf-8"))
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imports <= {"__future__", "app.domain.results"}
    # Nenhuma conversão espalhada: o literal "F" só aparece no código como
    # a constante central que já existia (app/domain/values.py); a
    # tradução por variável usa o literal declarado no seed.
    holders = sorted(
        str(p.relative_to(REPO)) for p in (REPO / "app").rglob("*.py")
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
        if isinstance(n, ast.Constant) and n.value == "F"
    )
    assert holders == ["app/domain/values.py"]
