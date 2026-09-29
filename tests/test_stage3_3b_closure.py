"""
Etapa 3.3B — fechamento do contrato.

    D33B-01  estados diferentes -> MULTI_STATE_COMBINATION_UNDEFINED
    D33B-02  mesmo estado, details diferentes -> MULTI_DETAIL_COMPOSITION_UNDEFINED
    D33B-03  detail sem state é inválido (DETAIL_WITHOUT_STATE)
    causal   só dependências EXECUTADAS propagam estado (ramo de IF não
             escolhido não contribui)
    D33B-04  identidade temporal = (variável, escopo, period_id, janela
             efetiva); resolve D32-02; idempotência x conflito

Cenários SINTÉTICOS (documentados em cada catálogo) e REAL_DERIVED
(seeds reais, pendências como entradas livres só no fixture).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import AggregationRuleInstanceRegistry
from app.domain.forecast.models import ForecastValue
from app.domain.interblock.registry import InterblockLinkRegistry
from app.domain.parameters.registry import ParameterInstanceRegistry
from app.domain.results import (
    AmbiguousResultWindowError,
    DetailWithoutStateError,
    Result,
    ResultContractError,
    StatedResultConsumedAsValueError,
    results_equivalent,
)
from app.domain.state_propagation import (
    MultiDetailCompositionUndefinedError,
    MultiStateCombinationUndefinedError,
    inherit_from_dependencies,
)
from app.domain.values import RESULT_STATE_TAXONOMY
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext, CalculationKey
from app.engine.exceptions import (
    InterblockConsumerValueConflictError,
    VariableNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.engine.interblock_orchestrator import (
    TRANSFER,
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)
from tests.test_stage3_2_execution_orchestration import (
    LINES,
    eq,
    link,
    real_derived_orchestrator,
    real_inputs,
    synthetic,
    vdef,
)


REPO = Path(__file__).resolve().parents[1]
DAY = "2026-09-01"
D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)
NAR, INVALID, VFAIL = "NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"


def stated(state, detail=None):
    return Result(None, state, detail)


def dep(name, result):
    return ((name, "linha", "L1", DAY), result)


# ============================================================
# D33B-01 / D33B-02 / D33B-03 — contrato (unidade)
# ============================================================

def test_valid_result_without_state_or_detail():
    assert Result(1.0).is_plain
    assert inherit_from_dependencies("T", [dep("A", Result(1.0)), dep("B", Result("LC"))]) is None


def test_single_state_propagates_with_its_detail():
    assert inherit_from_dependencies("T", [dep("A", stated(INVALID, "d")), dep("B", Result(2.0))]) == \
        stated(INVALID, "d")


def test_state_without_detail_is_valid_and_propagates():
    assert inherit_from_dependencies("T", [dep("A", stated(NAR))]) == stated(NAR)


def test_same_state_same_detail_many_dependencies_propagates():
    deps = [dep(n, stated(VFAIL, "x")) for n in ("A", "B", "C")]
    assert inherit_from_dependencies("T", deps) == stated(VFAIL, "x")
    assert inherit_from_dependencies("T", list(reversed(deps))) == stated(VFAIL, "x")


def test_same_state_all_details_none_propagates():
    assert inherit_from_dependencies("T", [dep("A", stated(INVALID)), dep("B", stated(INVALID))]) == stated(INVALID)


@pytest.mark.parametrize("first, second", [
    (s1, s2) for s1 in sorted(RESULT_STATE_TAXONOMY) for s2 in sorted(RESULT_STATE_TAXONOMY) if s1 != s2
])
def test_d33b_01_different_states_are_an_explicit_error_in_any_order(first, second):
    messages = set()
    for deps in ([dep("A", stated(first)), dep("B", stated(second))],
                 [dep("B", stated(second)), dep("A", stated(first))]):
        with pytest.raises(MultiStateCombinationUndefinedError) as error:
            inherit_from_dependencies("T", deps)
        messages.add(str(error.value))
    assert len(messages) == 1                        # determinístico, sem ordem
    assert error.value.code == "MULTI_STATE_COMBINATION_UNDEFINED"
    # nada foi escolhido nem inventado: ambos listados, nenhum estado novo
    assert first in messages.pop() and "OK" not in RESULT_STATE_TAXONOMY


@pytest.mark.parametrize("details", [("a", "b"), ("a", None), (None, "b"), ("a", "a ")])
def test_d33b_02_same_state_different_details_is_an_explicit_error(details):
    for order in (details, tuple(reversed(details))):
        deps = [dep(f"V{i}", stated(INVALID, d)) for i, d in enumerate(order)]
        with pytest.raises(MultiDetailCompositionUndefinedError) as error:
            inherit_from_dependencies("T", deps)
        assert error.value.code == "MULTI_DETAIL_COMPOSITION_UNDEFINED"


@pytest.mark.parametrize("state, detail, valid", [
    (None, None, True), (INVALID, None, True), (INVALID, "texto", True), (None, "texto", False),
])
def test_d33b_03_detail_requires_state(state, detail, valid):
    value = None if state else 1.0
    if valid:
        result = Result(value, state, detail)
        assert (result.state, result.detail) == (state, detail)
        fv = ForecastValue("VAR1", "linha", "L1", "diário", 2026, DAY, value, state=state, detail=detail)
        assert fv.result == result
    else:
        with pytest.raises(DetailWithoutStateError) as error:
            Result(value, state, detail)
        assert error.value.code == "DETAIL_WITHOUT_STATE"
        with pytest.raises(DetailWithoutStateError):
            ForecastValue("VAR1", "linha", "L1", "diário", 2026, DAY, 1.0, state=None, detail=detail)


def test_d33b_03_no_path_can_store_detail_without_state():
    context = CalculationContext()
    with pytest.raises(DetailWithoutStateError):
        context.set_variable_result("VAR12901", Result(1.0, None, "x"), "linha", "L1", DAY)
    with pytest.raises(VariableNotFoundError):
        context.get_variable_result("VAR12901", "linha", "L1", DAY)
    # o Result é imutável: não há caminho para "remover" o estado depois
    with pytest.raises(Exception):
        stated(INVALID, "x").__setattr__("state", None)


# ============================================================
# Propagação causal — catálogo SINTÉTICO com IF
# ============================================================
#
# production (linha L1_L7, diário):
#   K VAR12941, K2 VAR12942 condições (entrada); A VAR12943, B VAR12944,
#   C VAR12945 operandos (entrada)
#   T  VAR12946 = A if K > 0 else B
#   N  VAR12947 = (A if K2 > 0 else B) if K > 0 else C        (aninhado)
#   SC VAR12948 = A if (K > 0 and K2 > 0) else B              (curto-circuito)
#   W  VAR12949 = A + B                                        (sem IF)
# yield:  YT VAR11941 <- production.T;  YU VAR11942 = YT * 2

K, K2, A, B, C = "VAR12941", "VAR12942", "VAR12943", "VAR12944", "VAR12945"
T, N, SC, W = "VAR12946", "VAR12947", "VAR12948", "VAR12949"
YT, YU = "VAR11941", "VAR11942"


def if_catalog():
    calc = {"variable_type": "calculado"}
    variables = {
        "production": [vdef(K, "k"), vdef(K2, "k2"), vdef(A, "a"), vdef(B, "b"), vdef(C, "c"),
                       vdef(T, "t", **calc), vdef(N, "n", **calc), vdef(SC, "sc", **calc),
                       vdef(W, "w", **calc)],
        "yield": [vdef(YT, "yt"), vdef(YU, "yu", **calc)],
    }
    equations = [
        ("production", eq("EQ12941", T, f"{A} if {K} > 0 else {B}")),
        ("production", eq("EQ12942", N, f"({A} if {K2} > 0 else {B}) if {K} > 0 else {C}")),
        ("production", eq("EQ12943", SC, f"{A} if ({K} > 0 and {K2} > 0) else {B}")),
        ("production", eq("EQ12944", W, f"{A} + {B}")),
        ("yield", eq("EQ11941", YU, f"{YT} * 2")),
    ]
    payload = {
        "workbooks": {b: {} for b in variables},
        "taxonomy": {"official_blocks": ["production", "yield"]},
        "links": [link("yield", YT, "production", T)], "pending": [], "rejected": [],
    }
    raw = {b: [{"variable_id": v.variable_definition_id, "variable_name": v.variable_name, "unit": v.unit,
                "frequency": v.frequency, "scope_type": v.scope_type, "scope_value": v.scope_value,
                "value_type": v.value_type} for v in vs] for b, vs in variables.items()}
    registry, block_of = VariableDefinitionRegistry(), {}
    for b, vs in variables.items():
        for v in vs:
            registry.add(v)
            block_of[v.variable_definition_id] = b
    equation_registry = EquationDefinitionRegistry()
    for b, e in equations:
        equation_registry.add(e)
        block_of[e.equation_definition_id] = b
    return InterblockExecutionOrchestrator(ExecutionCatalog(
        registry, equation_registry, AggregationRuleInstanceRegistry(), ParameterInstanceRegistry(),
        InterblockLinkRegistry.from_payload(payload, raw), block_of,
    ))


def run_if(targets, k=1.0, k2=1.0, a=Result(10.0), b=Result(20.0), c=Result(30.0), context=None, day=D1):
    context = context or CalculationContext()
    for line in LINES:
        for var, value in ((K, k), (K2, k2), (A, a), (B, b), (C, c)):
            context.set_variable_result(var, value if isinstance(value, Result) else Result(value),
                                        "linha", line, day.isoformat())
    trace = if_catalog().execute(targets, context, day)
    return trace, context


def got(context, variable, line="L1", period=DAY):
    return context.get_variable_result(variable, "linha", line, period)


def test_if_case_1_active_branch_with_state_propagates():
    _, context = run_if([T], k=1.0, a=stated(INVALID, "a"))
    assert got(context, T) == stated(INVALID, "a")


def test_if_case_2_inactive_branch_state_does_not_propagate():
    _, context = run_if([T], k=1.0, b=stated(INVALID, "b"))
    assert got(context, T) == Result(10.0)


def test_if_case_3_two_states_in_different_branches_only_active_counts():
    _, context = run_if([T], k=1.0, a=stated(NAR), b=stated(INVALID))
    assert got(context, T) == stated(NAR)          # e não MULTI_STATE_COMBINATION_UNDEFINED
    _, context = run_if([T], k=-1.0, a=stated(NAR), b=stated(INVALID))
    assert got(context, T) == stated(INVALID)


def test_if_case_4_condition_change_switches_the_state():
    context = CalculationContext()
    run_if([T], k=1.0, b=stated(VFAIL), context=context, day=D1)
    run_if([T], k=-1.0, b=stated(VFAIL), context=context, day=D2)
    assert got(context, T, period="2026-09-01") == Result(10.0)
    assert got(context, T, period="2026-09-02") == stated(VFAIL)


def test_if_case_5_nested_conditionals_keep_causality():
    _, context = run_if([N], k=1.0, k2=1.0, b=stated(INVALID), c=stated(VFAIL))
    assert got(context, N) == Result(10.0)
    _, context = run_if([N], k=1.0, k2=-1.0, a=stated(NAR), c=stated(VFAIL))
    assert got(context, N) == Result(20.0)
    _, context = run_if([N], k=-1.0, a=stated(NAR), b=stated(INVALID), c=stated(VFAIL, "c"))
    assert got(context, N) == stated(VFAIL, "c")


def test_if_condition_with_state_executes_no_branch():
    _, context = run_if([T], k=stated(INVALID, "cond"), a=stated(NAR), b=stated(VFAIL))
    assert got(context, T) == stated(INVALID, "cond")


def test_short_circuit_does_not_execute_the_second_operand():
    _, context = run_if([SC], k=-1.0, k2=stated(INVALID))
    assert got(context, SC) == Result(20.0)            # K > 0 falso: K2 não executado
    _, context = run_if([SC], k=1.0, k2=stated(INVALID))
    assert got(context, SC) == stated(INVALID)         # K2 executado e indecidível


def test_without_if_every_operand_is_executed():
    with pytest.raises(MultiStateCombinationUndefinedError):
        run_if([W], a=stated(NAR), b=stated(INVALID))


def test_if_case_6_interblock_carries_only_the_executed_state():
    trace, context = run_if([YU], k=1.0, b=stated(INVALID))
    assert got(context, YT) == Result(10.0) and got(context, YU) == Result(20.0)
    trace, context = run_if([YU], k=-1.0, b=stated(INVALID, "b"))
    assert got(context, YT) == stated(INVALID, "b") and got(context, YU) == stated(INVALID, "b")
    assert {(e.state, e.detail) for e in trace.of_kind(TRANSFER)} == {(INVALID, "b")}


def test_direct_evaluator_single_pass_and_explicit_boundary():
    context = CalculationContext()
    for var, result in ((K, Result(1.0)), (A, Result(10.0)), (B, stated(INVALID))):
        context.set_variable_result(var, result, "linha", "L1", DAY)
    evaluator = ExpressionEvaluator(context, "linha", "L1", DAY)
    parse = ExpressionParser().parse
    assert evaluator.evaluate(parse(f"{A} if {K} > 0 else {B}")) == 10.0   # ramo inativo não consumido
    with pytest.raises(StatedResultConsumedAsValueError):
        evaluator.evaluate(parse(f"{B} if {K} > 0 else {A}"))
    value, origins = evaluator.evaluate_with_state(parse(f"{B} * 2 + {A}"))
    assert value is None and [key[0] for key, _r in origins] == [B]


def test_real_a41_inactive_branch_state_does_not_propagate():
    """
    REAL_DERIVED: EQ16011 usa desconto_retirada_41d (VAR16024) só no ramo
    "1 By pass". Com hes L4/L5 = Normal o ramo não é executado.
    """
    orchestrator = real_derived_orchestrator()

    def run(hes_l4):
        plan = orchestrator.plan(["VAR16025"])
        context = CalculationContext()
        context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
        real_inputs(orchestrator, plan, context)
        context.set_variable_value("VAR16021", hes_l4, "linha", "L4", DAY)
        context.set_variable_value("VAR16021", "Normal", "linha", "L5", DAY)
        context.set_variable_result("VAR16024", stated(INVALID, "41d"), "linha_grupo", "L4_L5", DAY)
        orchestrator.execute(plan, context, D1)
        return context.get_variable_result("VAR16025", "linha_grupo", "L4_L5", DAY)

    assert run("Normal").is_plain
    assert run("1 By pass") == stated(INVALID, "41d")


# ============================================================
# D33B-04 — identidade temporal
# ============================================================

def test_results_equivalent_is_explicit_about_types():
    assert results_equivalent(Result(2), Result(2.0))
    assert not results_equivalent(Result("2"), Result(2))
    assert not results_equivalent(Result(float("nan")), Result(float("nan")))
    assert results_equivalent(stated(INVALID, "d"), stated(INVALID, "d"))
    assert not results_equivalent(stated(INVALID, "d"), stated(INVALID, "d "))
    assert not results_equivalent(stated(INVALID), stated(VFAIL))
    assert not results_equivalent(stated(INVALID), Result(1.0))


def test_window_rule():
    window = CalculationContext.window_for
    assert window("2026-09", "2026-09-02") == "2026-09-02"
    assert window("2026", "2026-09-02") == "2026-09-02"
    assert window("2026-09-02", "2026-09-02") is None       # diário: a janela é o próprio dia
    assert window("2026-08", "2026-09-02") is None          # período que não contém a data
    assert window("2026-09", None) is None and window(None, "2026-09-02") is None


def daily_inputs(context, day, factor=1.0):
    for i, line in enumerate(LINES, start=1):
        context.set_variable_value("VAR12901", factor * day.day * i, "linha", line, day.isoformat())
        context.set_variable_value("VAR12904", 1000.0 + i, "linha", line, "2026")


MONTHLY = ["VAR18901", "VAR11901"]   # energy.e_mes (mensal) + yield.y_lth (diário)


def store(context):
    return sorted((tuple(str(x) for x in (k.entity_id, k.scope_type, k.scope_value, k.period_id, k.window_end)),
                   (r.value, r.state, r.detail)) for k, r in context._scoped_results.items())


def run_days(days, context=None):
    orchestrator = synthetic()
    context = context or CalculationContext()
    traces = []
    for day in days:
        daily_inputs(context, day)
        traces.append(orchestrator.execute(MONTHLY, context, day))
    return traces, context


def test_case_a_different_periods_coexist_without_conflict():
    _, context = run_days([D1, D2])
    assert context.get_variable_value("VAR11901", "linha", "L1", "2026-09-01") == 2.0
    assert context.get_variable_value("VAR11901", "linha", "L1", "2026-09-02") == 4.0
    assert context.result_windows("VAR18901", "linha", "L1", "2026-09") == ("2026-09-01", "2026-09-02")


def test_case_b_same_period_same_result_is_idempotent():
    orchestrator = synthetic()
    context = CalculationContext()
    daily_inputs(context, D1)
    orchestrator.execute(MONTHLY, context, D1)
    before = store(context)
    trace = orchestrator.execute(MONTHLY, context, D1)
    assert store(context) == before
    assert {e.status for e in trace.of_kind(TRANSFER)} == {"UNCHANGED"}


def test_case_c_same_period_different_result_is_a_conflict():
    orchestrator = synthetic()
    context = CalculationContext()
    daily_inputs(context, D1)
    orchestrator.execute(MONTHLY, context, D1)
    daily_inputs(context, D1, factor=5.0)                     # produtor muda no MESMO período
    with pytest.raises(InterblockConsumerValueConflictError):
        orchestrator.execute(MONTHLY, context, D1)
    assert context.get_variable_value("VAR11901", "linha", "L1", "2026-09-01") == 2.0   # sem sobrescrita


def test_case_d_three_periods_in_sequence_all_accessible():
    _, context = run_days([D1, D2, D3])
    for day, mean in ((D1, 2.0), (D2, 3.0), (D3, 4.0)):       # média de 2*d em L1 até d
        assert context.get_variable_value("VAR18901", "linha", "L1", "2026-09", as_of=day) == mean
        assert context.get_variable_value("VAR11901", "linha", "L1", day.isoformat()) == 2.0 * day.day


def run_out_of_order(days):
    """
    A janela mensal até d exige os resultados diários 1..d (a média é
    sobre a janela): primeiro os diários na ordem dada, depois as
    janelas mensais na mesma ordem dada.
    """
    orchestrator = synthetic()
    context = CalculationContext()
    for day in days:
        daily_inputs(context, day)
        orchestrator.execute(["VAR11901", "VAR18902"], context, day)
    for day in days:
        orchestrator.execute(["VAR18901"], context, day)
    return context


def test_case_e_out_of_order_execution_gives_the_same_store():
    forward = run_out_of_order([D1, D2, D3])
    for order in ([D3, D1, D2], [D2, D3, D1]):
        assert store(run_out_of_order(order)) == store(forward)
    assert forward.get_variable_value("VAR18901", "linha", "L1", "2026-09", as_of=D3) == 4.0


def test_case_f_rerun_p1_after_p2_is_idempotent():
    traces, context = run_days([D1, D2])
    before = store(context)
    traces, context = run_days([D1], context)
    assert store(context) == before
    assert {e.status for e in traces[0].of_kind(TRANSFER)} == {"UNCHANGED"}


def test_case_g_interblock_producer_and_consumer_keep_their_period():
    traces, context = run_days([D1, D2, D1])
    for day in (D1, D2):
        for line in LINES:
            assert context.get_variable_result("VAR11901", "linha", line, day.isoformat()) == \
                context.get_variable_result("VAR12902", "linha", line, day.isoformat())
            assert context.get_variable_result("VAR18901", "linha", line, "2026-09", as_of=day) == \
                context.get_variable_result("VAR12903", "linha", line, "2026-09", as_of=day)
    assert {e.status for e in traces[2].of_kind(TRANSFER)} == {"UNCHANGED"}


def test_state_at_one_period_does_not_leak_to_another():
    orchestrator = synthetic()
    context = CalculationContext()
    daily_inputs(context, D1)
    context.set_variable_result("VAR12901", stated(INVALID), "linha", "L2", "2026-09-01")
    orchestrator.execute(["VAR11901"], context, D1)
    daily_inputs(context, D2)
    orchestrator.execute(["VAR11901"], context, D2)
    assert context.get_variable_result("VAR11901", "linha", "L2", "2026-09-01") == stated(INVALID)
    assert context.get_variable_result("VAR11901", "linha", "L2", "2026-09-02") == Result(8.0)


def test_ambiguous_window_read_is_explicit_never_a_choice():
    _, context = run_days([D1, D2])
    with pytest.raises(AmbiguousResultWindowError) as error:
        context.get_variable_result("VAR18901", "linha", "L1", "2026-09")
    assert error.value.code == "RESULT_WINDOW_AMBIGUOUS"
    assert isinstance(error.value, ResultContractError) and not isinstance(error.value, LookupError)
    _, single = run_days([D1])
    assert single.get_variable_value("VAR18901", "linha", "L1", "2026-09") == 2.0


def test_period_level_values_keep_their_identity():
    """Entradas do período inteiro (sem janela) continuam como antes."""
    _, context = run_days([D1, D2])
    assert CalculationKey("VAR12904", "linha", "L1", "2026") in context._scoped_results
    assert context.get_variable_value("VAR12904", "linha", "L1", "2026") == 1001.0
    assert context.result_windows("VAR12904", "linha", "L1", "2026") == ()
    daily = [k for k in context._scoped_results if k.period_id and len(k.period_id) == 10]
    assert daily and all(k.window_end is None for k in daily)


def test_no_context_clear_between_periods():
    _, context = run_days([D1, D2, D3])
    assert {k.period_id for k in context._scoped_results if k.entity_id == "VAR12901"} == {
        "2026-09-01", "2026-09-02", "2026-09-03"}


_HASH_SNIPPET = """
import hashlib, sys
sys.path.insert(0, {repo!r})
from tests.test_stage3_3b_closure import run_days, run_out_of_order, store, run_if, D1, D2, D3, stated, T, N, YU
c = run_out_of_order([D3, D1, D2])
_, i = run_if([T, N, YU], k=-1.0, b=stated("INVALID_INPUT", "b"))
print(hashlib.sha256(repr((store(c), store(i))).encode()).hexdigest())
"""


def test_hash_seed_determinism():
    outputs = set()
    for seed in ("0", "1", "4242", "987654321"):
        outputs.add(subprocess.check_output(
            [sys.executable, "-c", _HASH_SNIPPET.format(repo=str(REPO))],
            env={**os.environ, "PYTHONHASHSEED": seed}, cwd=REPO,
        ))
    assert len(outputs) == 1


def test_no_new_states_and_no_policy_b():
    assert set(RESULT_STATE_TAXONOMY) == {NAR, INVALID, VFAIL}
    source = (REPO / "app/engine/temporal_aggregation_service.py").read_text(encoding="utf-8")
    assert "require_plain_for_aggregation" in source
    assert "BLOCKED_BY_UPSTREAM_ERROR" not in (REPO / "app/domain/values.py").read_text(encoding="utf-8")
