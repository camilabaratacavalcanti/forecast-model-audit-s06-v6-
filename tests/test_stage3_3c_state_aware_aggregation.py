"""
Etapa 3.3C — agregação consciente de Result (Policy B).

Composição (núcleo único da 3.3B, `compose_states`):
    present_states = {r.state para r com state}; None não conflita.
    0 -> sem estado; 1 -> estado propagado; >1 -> MULTI_STATE_COMBINATION_UNDEFINED.
    Mesmo estado: details iguais (inclusive todos None) -> propaga;
    diferentes (inclusive None x texto) -> MULTI_DETAIL_COMPOSITION_UNDEFINED.
Matemática: a aritmética existente de cada agregador, inalterada, só
quando todo componente tem value; componente com estado e sem value ->
value agregado None (com o estado composto).
Agregadores do runtime: AVERAGE, SUM (com integration_factor),
WEIGHTED_AVERAGE (pesos também são componentes), MOVING_AVERAGE.
"""

from __future__ import annotations

import hashlib
import itertools
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.forecast.aggregation import AggregationRule
from app.domain.results import Result, ResultContractError
from app.domain.state_propagation import (
    MultiDetailCompositionUndefinedError,
    MultiStateCombinationUndefinedError,
    compose_aggregated_result,
)
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    AggregationFailureError,
    EmptyAggregationWindowError,
    InterblockConsumerValueConflictError,
    NonNumericAggregationError,
    ZeroWeightSumError,
)
from app.engine.interblock_orchestrator import AGGREGATION, TRANSFER
from app.engine.temporal_aggregation_service import TemporalAggregationService
from tests.test_stage3_2_execution_orchestration import LINES, real_derived_orchestrator, synthetic

REPO = Path(__file__).resolve().parents[1]
NAR, INVALID, VFAIL = "NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"
S, S1, S2 = INVALID, NAR, VFAIL
DAYS = ["2026-09-01", "2026-09-02", "2026-09-03"]
RUN = date(2026, 9, 3)
SOURCE, TARGET, WEIGHT = "VAR19901", "VAR19902", "VAR19903"
WEIGHTS = [1.0, 2.0, 3.0]

AGGREGATORS = ["AVERAGE", "SUM", "SUM_X24", "WEIGHTED_AVERAGE", "MOVING_AVERAGE"]


def rule(kind, window=None):
    extra = {}
    if kind == "SUM_X24":
        kind, extra = "SUM", {"integration_factor": 24.0}
    if kind == "WEIGHTED_AVERAGE":
        extra["weight_variable_id"] = WEIGHT
    if window:
        extra["window_start_date"], extra["window_end_date"] = window
    return AggregationRule(
        aggregation_rule_id=f"AGR-3.3C-{kind}", source_variable_id=SOURCE, source_frequency="diário",
        target_variable_id=TARGET, target_frequency="mensal", aggregation_type=kind, **extra,
    )


def expected_value(kind, values, weights=WEIGHTS):
    """Aritmética contratual de cada agregador (independente do serviço)."""
    if kind == "SUM":
        return sum(values)
    if kind == "SUM_X24":
        return sum(v * 24.0 for v in values)
    if kind == "WEIGHTED_AVERAGE":
        return sum(v * w for v, w in zip(values, weights)) / sum(weights)
    return sum(values) / len(values)


def aggregate(kind, results, weights=None, run_date=RUN):
    context = CalculationContext()
    for day, result in zip(DAYS, results):
        context.set_variable_result(SOURCE, result, "linha", "L1", day)
    for day, weight in zip(DAYS, weights or [Result(w) for w in WEIGHTS]):
        context.set_variable_result(WEIGHT, weight, "linha", "L1", day)
    return TemporalAggregationService().aggregate(rule(kind), context, "linha", "L1", run_date).result


def R(value, state=None, detail=None):
    return Result(value, state, detail)


# ============================================================
# 21.1 .. 21.9 — cenários de composição, em TODOS os agregadores
# ============================================================

SCENARIOS = {
    # nome: (inputs, estado esperado | erro, detail esperado)
    "21.1_no_state": ([R(10.0), R(20.0), R(30.0)], None, None),
    "21.2_single_state_repeated": ([R(10.0, S), R(20.0, S), R(30.0, S)], S, None),
    "21.3_state_plus_none": ([R(10.0, S), R(20.0), R(30.0)], S, None),
    "21.4_different_states": ([R(10.0, S1), R(20.0, S2), R(30.0)], MultiStateCombinationUndefinedError, None),
    "21.5_same_state_same_detail": ([R(10.0, S, "D"), R(20.0, S, "D"), R(30.0)], S, "D"),
    "21.6_same_state_different_details": ([R(10.0, S, "D1"), R(20.0, S, "D2"), R(30.0)],
                                          MultiDetailCompositionUndefinedError, None),
    "21.7_same_state_none_and_text": ([R(10.0, S, None), R(20.0, S, "D"), R(30.0)],
                                      MultiDetailCompositionUndefinedError, None),
    "21.8_no_detail": ([R(10.0, S), R(20.0, S), R(30.0)], S, None),
    "21.9a_S_S_S": ([R(10.0, S), R(20.0, S), R(30.0, S)], S, None),
    "21.9b_S_None_S": ([R(10.0, S), R(20.0), R(30.0, S)], S, None),
    "21.9c_S1_S2_S1": ([R(10.0, S1), R(20.0, S2), R(30.0, S1)], MultiStateCombinationUndefinedError, None),
    "21.9d_SD1_SD1_SD1": ([R(10.0, S, "D1"), R(20.0, S, "D1"), R(30.0, S, "D1")], S, "D1"),
    "21.9e_SD1_SD2_SD1": ([R(10.0, S, "D1"), R(20.0, S, "D2"), R(30.0, S, "D1")],
                          MultiDetailCompositionUndefinedError, None),
}


@pytest.mark.parametrize("kind", AGGREGATORS)
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_policy_b_scenarios_on_every_aggregator(kind, name):
    inputs, want, detail = SCENARIOS[name]
    if isinstance(want, type):
        with pytest.raises(want) as error:
            aggregate(kind, inputs)
        assert isinstance(error.value, ResultContractError)
        assert not isinstance(error.value, (ValueError, TypeError, ArithmeticError))
        return
    result = aggregate(kind, inputs)
    assert result.value == pytest.approx(expected_value(kind, [r.value for r in inputs]))
    assert (result.state, result.detail) == (want, detail)


@pytest.mark.parametrize("kind", AGGREGATORS)
def test_21_10_order_does_not_change_the_semantic_result(kind):
    base = [R(10.0, S, "D"), R(20.0), R(30.0, S, "D")]
    outcomes = set()
    for order in itertools.permutations(range(3)):
        inputs = [base[i] for i in order]
        weights = [Result(WEIGHTS[i]) for i in order]      # pares valor/peso preservados
        result = aggregate(kind, inputs, weights)
        outcomes.add((round(result.value, 9), result.state, result.detail))
    assert len(outcomes) == 1


@pytest.mark.parametrize("kind", AGGREGATORS)
def test_21_10_conflict_errors_are_identical_in_every_order(kind):
    base = [R(10.0, S1), R(20.0, S2), R(30.0, S1, "x")]
    messages = set()
    for order in itertools.permutations(range(3)):
        with pytest.raises(MultiStateCombinationUndefinedError) as error:
            aggregate(kind, [base[i] for i in order])
        messages.add(str(error.value))
    assert len(messages) == 1


@pytest.mark.parametrize("kind", AGGREGATORS)
def test_21_11_empty_aggregation_keeps_the_existing_explicit_error(kind):
    empty = (date(2026, 10, 1), date(2026, 10, 31))           # janela depois de run_date
    context = CalculationContext()
    with pytest.raises(EmptyAggregationWindowError):
        TemporalAggregationService().aggregate(rule(kind, empty), context, "linha", "L1", RUN)


@pytest.mark.parametrize("kind", AGGREGATORS)
def test_valueless_stated_component_gives_no_value_and_keeps_the_state(kind):
    result = aggregate(kind, [R(None, S, "herdado"), R(20.0), R(30.0)])
    assert result == Result(None, S, "herdado")


@pytest.mark.parametrize("kind", AGGREGATORS)
def test_valueless_components_never_hide_a_conflict(kind):
    with pytest.raises(MultiStateCombinationUndefinedError):
        aggregate(kind, [R(None, S1), R(20.0, S2), R(30.0)])


def test_weights_are_components_of_weighted_average():
    result = aggregate("WEIGHTED_AVERAGE", [R(10.0), R(20.0), R(30.0)],
                       [Result(1.0), Result(2.0, S, "peso"), Result(3.0)])
    assert result == Result(expected_value("WEIGHTED_AVERAGE", [10.0, 20.0, 30.0]), S, "peso")
    with pytest.raises(MultiStateCombinationUndefinedError):
        aggregate("WEIGHTED_AVERAGE", [R(10.0, S1), R(20.0), R(30.0)],
                  [Result(1.0), Result(2.0, S2), Result(3.0)])


def test_existing_mathematical_errors_are_preserved():
    with pytest.raises(AggregationFailureError):
        aggregate("AVERAGE", [R("F"), R(20.0), R(30.0)])
    with pytest.raises(AggregationFailureError):
        aggregate("SUM", [R("F", S), R(20.0), R(30.0)])       # estado + "F": matemática ainda falha
    with pytest.raises(ZeroWeightSumError):
        aggregate("WEIGHTED_AVERAGE", [R(10.0), R(20.0), R(30.0)], [Result(0.0)] * 3)
    context = CalculationContext(categorical_variable_ids=[SOURCE])
    for day in DAYS:
        context.set_variable_result(SOURCE, Result("LC"), "linha", "L1", day)
    with pytest.raises(NonNumericAggregationError):
        TemporalAggregationService().aggregate(rule("AVERAGE"), context, "linha", "L1", RUN)


def test_semantic_composition_runs_before_the_math():
    """Conflito semântico nunca é mascarado por erro matemático."""
    with pytest.raises(MultiStateCombinationUndefinedError):
        aggregate("AVERAGE", [R("F", S1), R(20.0, S2), R(30.0)])
    with pytest.raises(MultiDetailCompositionUndefinedError):
        aggregate("WEIGHTED_AVERAGE", [R(10.0, S, "a"), R(20.0, S, "b"), R(30.0)], [Result(0.0)] * 3)


def test_compose_aggregated_result_unit():
    key = lambda i: ("V", "linha", "L1", DAYS[i])  # noqa: E731
    calls = []

    def math():
        calls.append(1)
        return 7.0

    assert compose_aggregated_result("T", [(key(0), R(1.0)), (key(1), R(2.0))], math) == R(7.0)
    assert compose_aggregated_result("T", [(key(0), R(1.0, S, "d")), (key(1), R(2.0))], math) == R(7.0, S, "d")
    assert compose_aggregated_result("T", [(key(0), R(None, S)), (key(1), R(2.0))], math) == R(None, S)
    assert len(calls) == 2                                    # sem value: a matemática não roda
    with pytest.raises(MultiStateCombinationUndefinedError):
        compose_aggregated_result("T", [(key(0), R(1.0, S1)), (key(1), R(2.0, S2))], math)
    assert len(calls) == 2                                    # conflito: a matemática não roda


def test_no_new_states_and_no_priority():
    from app.domain.values import RESULT_STATE_TAXONOMY

    assert set(RESULT_STATE_TAXONOMY) == {NAR, INVALID, VFAIL}
    source = (REPO / "app/domain/state_propagation.py").read_text(encoding="utf-8")
    assert "priority" not in source.lower().replace("nenhuma prioridade", "")


# ============================================================
# 21.13 .. 21.15 — orquestrador: interbloco, temporal, reexecução
# ============================================================
#
# SINTÉTICO (catálogo da Etapa 3.2): production P_out VAR12902 (diário)
# -> AGR AVERAGE -> P_mes VAR12903 (mensal) -> energy E_mes VAR18901.

def agg_and_transfer_plan(orchestrator):
    plan = orchestrator.plan(["VAR18901"])
    return type(plan)(plan.targets, tuple(s for s in plan.steps if s.kind in (AGGREGATION, TRANSFER)), ())


def set_sources(context, day, per_line):
    for line in LINES:
        context.set_variable_result("VAR12902", per_line.get(line, Result(10.0)), "linha", line, day)


def test_21_13_interblock_aggregated_result_reaches_the_consumer_unchanged():
    orchestrator = synthetic()
    context = CalculationContext()
    set_sources(context, DAYS[0], {"L2": Result(10.0, S, "d1")})
    set_sources(context, DAYS[1], {"L2": Result(30.0, S, "d1"), "L3": Result(None, VFAIL, "v")})
    trace = orchestrator.execute(agg_and_transfer_plan(orchestrator), context, date(2026, 9, 2))
    for line, want in (("L1", Result(10.0)), ("L2", Result(20.0, S, "d1")), ("L3", Result(None, VFAIL, "v"))):
        assert context.get_variable_result("VAR12903", "linha", line, "2026-09") == want
        assert context.get_variable_result("VAR18901", "linha", line, "2026-09") == want
    events = {(e.kind, e.scope_value): (e.value, e.state, e.detail) for e in trace.events}
    assert events[(AGGREGATION, "L2")] == events[(TRANSFER, "L2")] == (20.0, S, "d1")


def test_21_14_temporal_same_window_different_window_different_period():
    orchestrator = synthetic()
    plan = agg_and_transfer_plan(orchestrator)
    context = CalculationContext()
    set_sources(context, DAYS[0], {"L2": Result(10.0, S, "a")})
    set_sources(context, DAYS[1], {"L2": Result(20.0)})
    set_sources(context, "2026-10-01", {"L2": Result(5.0, VFAIL)})
    orchestrator.execute(plan, context, date(2026, 9, 1))
    orchestrator.execute(plan, context, date(2026, 9, 2))
    orchestrator.execute(plan, context, date(2026, 10, 1))
    read = lambda period, as_of: context.get_variable_result("VAR18901", "linha", "L2", period, as_of=as_of)  # noqa: E731
    assert read("2026-09", date(2026, 9, 1)) == Result(10.0, S, "a")       # janela até 09-01
    assert read("2026-09", date(2026, 9, 2)) == Result(15.0, S, "a")       # janela até 09-02
    assert read("2026-10", date(2026, 10, 1)) == Result(5.0, VFAIL)        # outro período
    assert context.result_windows("VAR12903", "linha", "L2", "2026-09") == ("2026-09-01", "2026-09-02")


def test_21_15_reexecution_idempotent_and_conflict():
    orchestrator = synthetic()
    plan = agg_and_transfer_plan(orchestrator)
    context = CalculationContext()
    set_sources(context, DAYS[0], {"L2": Result(10.0, S, "a")})
    orchestrator.execute(plan, context, date(2026, 9, 1))
    before = dict(context._scoped_results)
    trace = orchestrator.execute(plan, context, date(2026, 9, 1))
    assert context._scoped_results == before
    assert {e.status for e in trace.of_kind(TRANSFER)} == {"UNCHANGED"}
    # mesma identidade, Result diferente na origem: a agregação recalcula
    # (como sempre) e a transferência detecta o conflito sem sobrescrever
    context.set_variable_result("VAR12902", Result(10.0, S, "b"), "linha", "L2", DAYS[0])
    with pytest.raises(InterblockConsumerValueConflictError):
        orchestrator.execute(plan, context, date(2026, 9, 1))
    assert context.get_variable_result("VAR18901", "linha", "L2", "2026-09") == Result(10.0, S, "a")


def test_real_seed_monthly_aggregation_to_energy_carries_the_state():
    """
    REAL_DERIVED: AGR-PRODUCTION-LTH_TOTAL (AVERAGE diário -> mensal) e o
    vínculo mensal production -> energy VAR18010, com seeds reais.
    """
    orchestrator = real_derived_orchestrator()
    plan = orchestrator.plan(["VAR18010"])
    steps = tuple(s for s in plan.steps if s.kind in (AGGREGATION, TRANSFER))
    agg = next(s for s in steps if s.kind == AGGREGATION)
    instances = sorted((i for i in orchestrator.catalog.aggregation_rule_instances.all()
                        if i.rule.aggregation_rule_id == agg.node_id),
                       key=lambda i: (i.scope_type or "", i.scope_value or ""))
    context = CalculationContext()
    for k, inst in enumerate(instances):
        for day in DAYS[:2]:
            context.set_variable_result(inst.rule.source_variable_id, Result(100.0 + k, S, "lth"),
                                        inst.scope_type, inst.scope_value, day)
    orchestrator.execute(type(plan)(plan.targets, steps, ()), context, date(2026, 9, 2))
    link = orchestrator.catalog.links.link_for("VAR18010")
    for scope_type, scope_value in link.instances:
        k = [(i.scope_type, i.scope_value) for i in instances].index((scope_type, scope_value))
        assert context.get_variable_result("VAR18010", scope_type, scope_value, "2026-09") == \
            Result(100.0 + k, S, "lth")


# ============================================================
# determinismo
# ============================================================

_HASH_SNIPPET = """
import sys
sys.path.insert(0, {repo!r})
from tests.test_stage3_3c_state_aware_aggregation import SCENARIOS, AGGREGATORS, aggregate
out = []
for kind in AGGREGATORS:
    for name in sorted(SCENARIOS):
        try:
            r = aggregate(kind, SCENARIOS[name][0])
            out.append((kind, name, repr(r)))
        except Exception as e:
            out.append((kind, name, type(e).__name__, str(e)))
print(repr(out))
"""


def test_hash_seed_determinism():
    outputs = set()
    for seed in ("0", "1", "4242", "987654321"):
        outputs.add(hashlib.sha256(subprocess.check_output(
            [sys.executable, "-c", _HASH_SNIPPET.format(repo=str(REPO))],
            env={**os.environ, "PYTHONHASHSEED": seed}, cwd=REPO,
        )).hexdigest())
    assert len(outputs) == 1
