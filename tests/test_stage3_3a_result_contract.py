"""
Etapa 3.3A — contrato global de resultado value + state + detail.

Cenários:
    SYNTHETIC     catálogo mínimo da Etapa 3.2 (reutilizado de
                  tests/test_stage3_2_execution_orchestration.py).
    REAL_DERIVED  seeds reais com as pendências tratadas como entradas
                  livres só no fixture (mesma definição da Etapa 3.2).
    OFFICIAL      seeds e artefato canônico oficiais.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.forecast.collection import ForecastValueRegistry
from app.domain.forecast.models import ForecastValue
from app.domain.results import (
    Result,
    ResultContractError,
    ResultIdentity,
    ResultValueDomainError,
    StateAwareAggregationPendingError,
    StatePropagationPendingError,
    as_result,
    check_value_domain,
)
from app.domain.values import RESULT_STATE_TAXONOMY
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    InterblockConsumerValueConflictError,
    InterblockSourceNotLoadedError,
    VariableNotFoundError,
)
from app.engine.interblock_orchestrator import TRANSFER, InterblockExecutionOrchestrator
from app.engine.interblock_resolver import InterblockValueResolver
from app.repositories.seed_loader import SeedLoader
from tests.test_stage3_2_execution_orchestration import (
    LINES,
    PERIOD,
    RUN,
    _direct_engine,
    execute_real,
    inputs,
    real_derived_orchestrator,
    real_inputs,
    run,
    synthetic,
)


REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "data" / "seed"
DAY = PERIOD["diário"]
DETAILS = ("  espaço nas pontas  ", "linha1\nlinha2", "acentuação ção ÿ €", "", "\t")


@pytest.fixture(scope="module")
def official():
    return InterblockExecutionOrchestrator.from_seed_root(SEED)


@pytest.fixture(scope="module")
def real_derived():
    return real_derived_orchestrator()


def hes_definition():
    definitions = SeedLoader(SEED).load_variable_definitions()
    return definitions.get("VAR16021")  # area_41.hes: categorica com allowed_values


# ============================================================
# Representação (1..6)
# ============================================================

def test_01_result_with_value_only():
    for value in (42, 42.5, "LC", "F"):
        result = Result(value)
        assert (result.value, result.state, result.detail) == (value, None, None)
        assert result.is_plain and type(result.value) is type(value)
    assert as_result(42) == Result(42)
    assert as_result(Result(1, "INVALID_INPUT")) == Result(1, "INVALID_INPUT")


def test_02_result_with_value_and_state():
    result = Result(0.0, "INVALID_INPUT")
    assert (result.value, result.state, result.detail) == (0.0, "INVALID_INPUT", None)
    assert not result.is_plain


def test_03_result_with_value_state_and_detail():
    result = Result("F", "NO_APPLICABLE_RULE", "nenhuma regra aplicável para L3")
    assert (result.value, result.state, result.detail) == (
        "F", "NO_APPLICABLE_RULE", "nenhuma regra aplicável para L3",
    )


def test_04_detail_is_preserved_exactly():
    context = CalculationContext()
    for i, detail in enumerate(DETAILS):
        context.set_variable_result("VAR99001", Result(1.0, "VALIDATION_FAILED", detail), "linha", f"L{i + 1}", DAY)
        assert context.get_variable_result("VAR99001", "linha", f"L{i + 1}", DAY).detail == detail


@pytest.mark.parametrize("state", ["OK", "no_applicable_rule", "NO_APPLICABLE_RULE ", "F", "", "ERROR"])
def test_05_invalid_state_is_rejected(state):
    with pytest.raises(ResultContractError):
        Result(1.0, state)
    with pytest.raises(ResultContractError):
        CalculationContext().set_variable_result("VAR99001", Result(1.0, state), "linha", "L1")


@pytest.mark.parametrize("state", sorted(RESULT_STATE_TAXONOMY))
def test_06_valid_state_is_accepted(state):
    context = CalculationContext()
    context.set_variable_result("VAR99001", Result(1.0, state), "linha", "L1", DAY)
    assert context.get_variable_result("VAR99001", "linha", "L1", DAY).state == state
    assert RESULT_STATE_TAXONOMY == {"NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"}


def test_06b_structural_values_are_not_converted():
    for bad in (True, None, [1], {"v": 1}):
        with pytest.raises(ResultContractError):
            Result(bad)
    with pytest.raises(ResultContractError):
        Result(1.0, None, 123)


# ============================================================
# allowed_values (7..10)
# ============================================================

def test_07_value_in_allowed_values_is_accepted():
    definition = hes_definition()
    assert definition.allowed_values == ("Normal", "LC", "Overhaul/Parada", "1 By pass", "1 By pass e LC")
    context = CalculationContext()
    context.declare_variable_definitions([definition])
    for option in definition.allowed_values:
        context.set_variable_value("VAR16021", option, "linha", "L4", DAY)
    context.set_variable_result("VAR16021", Result("LC", "INVALID_INPUT", "d"), "linha", "L5", DAY)
    # "F" (falha condicional) não é valor de negócio: regra existente.
    context.set_variable_value("VAR16021", "F", "linha", "L6", DAY)


@pytest.mark.parametrize("value", ["Parado", "lc", "LC ", "normal"])
def test_08_value_outside_allowed_values_is_rejected(value):
    context = CalculationContext()
    context.declare_variable_definitions([hes_definition()])
    with pytest.raises(ResultValueDomainError) as error:
        context.set_variable_value("VAR16021", value, "linha", "L4", DAY)
    assert error.value.code == "RESULT_VALUE_OUTSIDE_ALLOWED_VALUES"
    with pytest.raises(VariableNotFoundError):
        context.get_variable_result("VAR16021", "linha", "L4", DAY)


def test_09_no_allowed_values_means_no_artificial_validation():
    definitions = SeedLoader(SEED).load_variable_definitions()
    numeric = definitions.get("VAR12031")
    assert numeric.allowed_values is None
    context = CalculationContext()
    context.declare_variable_definitions([numeric])
    context.set_variable_value("VAR12031", -1e9, "linha", "L1", DAY)
    check_value_domain("X", "qualquer texto", None)
    # Sem declarar definições, nada muda em relação ao comportamento anterior.
    CalculationContext(categorical_variable_ids=["VAR16021"]).set_variable_value("VAR16021", "Parado", "linha", "L4")


def test_10_domain_validation_is_centralized(monkeypatch):
    import app.engine.calculation_context as context_module

    calls = []
    real = context_module.check_value_domain

    def spy(variable_id, value, allowed):
        calls.append((variable_id, value, allowed))
        return real(variable_id, value, allowed)

    monkeypatch.setattr(context_module, "check_value_domain", spy)
    context = CalculationContext()
    context.declare_variable_definitions([hes_definition()])
    context.set_variable_value("VAR16021", "LC", "linha", "L4", DAY)
    context.set_variable_result("VAR16021", Result("Normal"), "linha", "L5", DAY)
    assert [c[:2] for c in calls] == [("VAR16021", "LC"), ("VAR16021", "Normal")]

    # Nenhum outro módulo de app/ implementa checagem de allowed_values em runtime.
    # (código, não comentários: atributos/nomes/textos no AST)
    offenders = []
    for path in (REPO / "app").rglob("*.py"):
        if "validation" in path.parts or path.name in ("results.py", "models.py", "calculation_context.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Attribute) and node.attr == "allowed_values") or (
                isinstance(node, ast.Name) and node.id == "allowed_values"
            ):
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


# ============================================================
# Contexto (11..15)
# ============================================================

def test_11_two_instances():
    context = CalculationContext()
    context.set_variable_result("VAR99001", Result(1.0, "INVALID_INPUT", "a"), "linha", "L1", DAY)
    context.set_variable_result("VAR99001", Result(2.0), "linha", "L2", DAY)
    assert context.get_variable_result("VAR99001", "linha", "L1", DAY) == Result(1.0, "INVALID_INPUT", "a")
    assert context.get_variable_result("VAR99001", "linha", "L2", DAY) == Result(2.0)


def test_12_two_periods():
    context = CalculationContext()
    context.set_variable_result("VAR99001", Result(1.0, "VALIDATION_FAILED"), "linha", "L1", "2026-09-01")
    context.set_variable_result("VAR99001", Result(2.0), "linha", "L1", "2026-09-02")
    assert context.get_variable_result("VAR99001", "linha", "L1", "2026-09-01").state == "VALIDATION_FAILED"
    assert context.get_variable_result("VAR99001", "linha", "L1", "2026-09-02").state is None


def test_13_two_frequencies():
    # production.lth diário (VAR12031) e mensal (VAR12032): identidades distintas.
    context = CalculationContext()
    context.set_variable_result("VAR12031", Result(10.0, "INVALID_INPUT", "d"), "linha", "L1", "2026-09-01")
    context.set_variable_result("VAR12032", Result(11.0), "linha", "L1", "2026-09")
    with pytest.raises(VariableNotFoundError):
        context.get_variable_result("VAR12031", "linha", "L1", "2026-09")
    assert context.get_variable_result("VAR12032", "linha", "L1", "2026-09") == Result(11.0)
    assert ResultIdentity("VAR12031", "linha", "L1", "diário", "2026-09-01") != ResultIdentity(
        "VAR12032", "linha", "L1", "mensal", "2026-09"
    )


def test_14_same_variable_different_identities():
    context = CalculationContext()
    keys = [("linha", "L1", DAY), ("linha", "L2", DAY), ("linha", "L1", "2026-09-02"), ("linha_grupo", "L1_L7", DAY)]
    for i, key in enumerate(keys):
        context.set_variable_result("VAR99001", Result(float(i), "INVALID_INPUT", f"d{i}"), *key)
    for i, key in enumerate(keys):
        assert context.get_variable_result("VAR99001", *key) == Result(float(i), "INVALID_INPUT", f"d{i}")
    assert context.get_variable_value("VAR99001", "linha", "L2", DAY) == 1.0  # API legada lê value


def test_15_existing_conflict_is_still_detected():
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    context.set_variable_result("VAR12902", Result(5.0, "INVALID_INPUT", "x"), "linha", "L1", DAY)
    context.set_variable_value("VAR11901", 5.0, "linha", "L1", DAY)  # mesmo value, sem estado
    with pytest.raises(InterblockConsumerValueConflictError):
        resolver.transfer_result("VAR11901", "linha", "L1", DAY)
    assert context.get_variable_result("VAR11901", "linha", "L1", DAY) == Result(5.0)
    context.set_variable_value("VAR12901", 1.0, "linha", "L1", DAY)
    with pytest.raises(InterblockConsumerValueConflictError):  # conflito 3.1/3.2 por valor
        context.set_variable_value("VAR11901", 9.0, "linha", "L1", DAY)
        resolver.transfer("VAR11901", "linha", "L1", DAY)


# ============================================================
# Interblock (16..21)
# ============================================================

@pytest.mark.parametrize("result", [
    Result(1234.5),
    Result(7, "INVALID_INPUT"),
    Result("F", "NO_APPLICABLE_RULE", "sem regra aplicável"),
    Result(0.1 + 0.2, "VALIDATION_FAILED", DETAILS[1]),
])
def test_16_21_transfer_preserves_the_whole_result(result):
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    context.set_variable_result("VAR12902", result, "linha", "L3", DAY)
    moved = resolver.transfer_result("VAR11901", "linha", "L3", DAY)
    received = context.get_variable_result("VAR11901", "linha", "L3", DAY)
    assert moved == received == result                           # 16, 17, 18
    assert type(received.value) is type(result.value)            # 21: sem conversão
    assert received.detail == result.detail
    with pytest.raises(VariableNotFoundError):                   # 19: só a instância pedida
        context.get_variable_result("VAR11901", "linha", "L1", DAY)
    with pytest.raises(VariableNotFoundError):                   # 20: só o período pedido
        context.get_variable_result("VAR11901", "linha", "L3", "2026-09")


def test_16_21_chain_preserves_state_and_detail_through_every_hop():
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    original = Result(3.25, "VALIDATION_FAILED", "limite excedido")
    context.set_variable_result("VAR12902", original, "linha", "L5", DAY)
    resolver.transfer_result("VAR11901", "linha", "L5", DAY)
    resolver.transfer_result("VAR16901", "linha", "L5", DAY)
    assert context.get_variable_result("VAR16901", "linha", "L5", DAY) == original


def test_16_21_orchestrated_transfer_carries_state_detail_in_trace():
    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    context.set_variable_result("VAR12904", Result(1004.0, "INVALID_INPUT", "valor fora da faixa"), "linha", "L4", "2026")
    trace = orchestrator.execute(["VAR18902"], context, RUN)
    [event] = [e for e in trace.of_kind(TRANSFER) if e.scope_value == "L4"]
    assert (event.value, event.state, event.detail) == (1004.0, "INVALID_INPUT", "valor fora da faixa")
    assert context.get_variable_result("VAR18902", "linha", "L4", "2026") == Result(
        1004.0, "INVALID_INPUT", "valor fora da faixa"
    )
    assert context.get_variable_result("VAR18902", "linha", "L3", "2026") == Result(1003.0)


def test_consumer_domain_is_validated_on_transfer():
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    context.declare_variable_definitions(orchestrator.catalog.variable_definitions.all())
    context._value_domains["VAR11901"] = ("A", "B")  # SINTÉTICO: domínio no consumidor
    context._categorical_variable_ids |= {"VAR11901", "VAR12902"}
    context.set_variable_value("VAR12902", "C", "linha", "L1", DAY)
    with pytest.raises(ResultValueDomainError):
        resolver.transfer_result("VAR11901", "linha", "L1", DAY)


# ============================================================
# Fronteiras explícitas (sem semântica inventada)
# ============================================================

def test_equation_reading_a_stated_result_is_an_explicit_boundary():
    """
    LEGACY_TEST_EXPECTATION (Etapa 3.3B): na 3.3A uma equação que lia um
    resultado com estado levantava STATE_PROPAGATION_PENDING_STAGE_3.3B.
    Com a propagação causal (contrato 2.2 D3/§16) o descendente HERDA o
    estado sem valor; a leitura direta como valor (evaluator sem o
    EquationEngine) continua sendo erro explícito, com código próprio.
    """

    from app.domain.results import StatedResultConsumedAsValueError
    from app.engine.expression_evaluator import ExpressionEvaluator
    from app.engine.expression_parser import ExpressionParser

    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    context.set_variable_result("VAR12901", Result(10.0, "INVALID_INPUT"), "linha", "L1", DAY)
    orchestrator.execute(["VAR12902"], context, RUN)
    assert context.get_variable_result("VAR12902", "linha", "L1", DAY) == Result(None, "INVALID_INPUT")
    assert context.get_variable_result("VAR12902", "linha", "L2", DAY) == Result(40.0)

    evaluator = ExpressionEvaluator(context, "linha", "L1", DAY)
    with pytest.raises(StatedResultConsumedAsValueError) as error:
        evaluator.evaluate(ExpressionParser().parse("VAR12901 * 2"))
    assert error.value.code == "STATED_RESULT_CONSUMED_AS_VALUE"


def test_aggregation_over_a_stated_result_is_an_explicit_boundary():
    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    orchestrator.execute(["VAR12902"], context, RUN)
    context._scoped_results[next(k for k in context._scoped_results if k.entity_id == "VAR12902" and k.scope_value == "L2")] = Result(40.0, None, "nota")
    plan = orchestrator.plan(["VAR12903"])
    only_aggregation = type(plan)(plan.targets, tuple(s for s in plan.steps if s.kind == "AGGREGATION"), ())
    with pytest.raises(StateAwareAggregationPendingError) as error:
        orchestrator.execute(only_aggregation, context, RUN)
    assert error.value.code == "STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C"


def test_forecast_value_carries_state_and_detail():
    from app.engine.temporal_forecast_orchestrator import TemporalForecastOrchestrator

    definitions = SeedLoader(SEED).load_variable_definitions()
    context = CalculationContext()
    context.set_variable_result("VAR12031", Result(5.0, "INVALID_INPUT", "d"), "linha", "L1", "2026-09-01")
    value = TemporalForecastOrchestrator().direct_forecast_value(
        "VAR12031", "linha", "L1", definitions, context, date(2026, 9, 1),
    )
    assert value.result == Result(5.0, "INVALID_INPUT", "d")
    registry = ForecastValueRegistry()
    registry.add(value)
    changed = ForecastValue(**{**value.__dict__, "state": None, "detail": None})
    with pytest.raises(Exception):
        registry.add(changed)  # mesma execução, resultado diferente só no estado


# ============================================================
# Orquestrador (22..26)
# ============================================================

def test_22_simple_chain_still_works():
    trace, context = run(synthetic(), ["VAR11902"])
    assert trace.step_order == ["EQUATION:EQ12901", "TRANSFER:VAR11901", "EQUATION:EQ11901"]
    assert context.get_variable_result("VAR11902", "linha", "L3", DAY) == Result(61.0)
    assert all(e.state is None and e.detail is None for e in trace.events)


def test_23_production_yield_area_41_same_topology(real_derived, official):
    trace, _ = execute_real(real_derived, ["VAR16008"])
    assert trace.step_order == ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"]
    assert [s.key for s in official.plan(["VAR16008"], on_pending="report").steps] == trace.step_order


def test_24_production_energy_same_topology(real_derived):
    trace, context = execute_real(real_derived, ["VAR18002"])
    order = trace.step_order
    assert len(order) == 20
    assert order.index("EQUATION:EQ12012") < order.index("TRANSFER:VAR11031") < order.index("TRANSFER:VAR12062")
    assert order.index("TRANSFER:VAR12062") < order.index("TRANSFER:VAR18001") < order.index("EQUATION:EQ18001")
    for line in LINES:
        assert context.get_variable_result("VAR18001", "linha", line, DAY) == context.get_variable_result(
            "VAR12046", "linha", line, DAY
        )


def test_25_production_max_ht_same_topology(real_derived):
    trace, _ = execute_real(real_derived, ["VAR13039"])
    assert trace.step_order == ["EQUATION:EQ12012", "TRANSFER:VAR13062", "EQUATION:EQ13014"]


def test_23_25_planning_code_is_unchanged_since_stage_3_2():
    """_build_graph, _upstream, plan, _order, _find_cycle idênticos aos de a733487."""
    baseline = subprocess.check_output(
        ["git", "show", "a733487:app/engine/interblock_orchestrator.py"], cwd=REPO,
    ).decode("utf-8")
    current = (REPO / "app/engine/interblock_orchestrator.py").read_text(encoding="utf-8")

    def functions(source):
        tree = ast.parse(source)
        return {
            node.name: ast.dump(node)
            for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "InterblockExecutionOrchestrator"
            for node in cls.body if isinstance(node, ast.FunctionDef)
        }

    before, after = functions(baseline), functions(current)
    for name in ("_build_graph", "_upstream", "targets_of_blocks", "plan", "_order", "_find_cycle"):
        assert before[name] == after[name], name


def test_26_pending_dependency_still_fails(official):
    with pytest.raises(InterblockSourceNotLoadedError) as error:
        official.plan(["VAR16008"])
    assert error.value.code == "INTERBLOCK_SOURCE_NOT_LOADED"
    context = CalculationContext()
    with pytest.raises(InterblockSourceNotLoadedError):
        official.execute(["VAR13039"], context, RUN)
    assert context._scoped_results == {}


# ============================================================
# Regressão (27..31)
# ============================================================

@pytest.mark.parametrize("block, target", [
    ("yield", "VAR11226"),
    ("production", "VAR12031"),
    ("energy", "VAR18002"),
    ("max_ht", "VAR13039"),
])
def test_28_31_block_results_are_plain_and_identical_to_the_existing_engine(real_derived, block, target):
    orchestrator = real_derived
    plan = orchestrator.plan([target])
    local = type(plan)((target,), tuple(s for s in plan.steps if s.block == block and s.kind == "EQUATION"), ())

    import re
    needed, produced = set(), set()
    for step in local.steps:
        definition = orchestrator.catalog.equation_definitions.get(step.node_id)
        produced.add(definition.target_variable_id)
        needed |= set(re.findall(r"VAR\d+", definition.expression))
    fake = type(plan)((), (), tuple(sorted(needed - produced)))

    def prepare():
        context = CalculationContext()
        real_inputs(orchestrator, fake, context)
        return context

    a, b = prepare(), prepare()
    orchestrator.execute(local, a, RUN)
    _direct_engine(orchestrator, local, b)
    assert a._scoped_results == b._scoped_results
    assert all(result.is_plain for result in a._scoped_results.values())
    assert [k for k in a._scoped_results if k.entity_id == target]


def test_27_legacy_scalar_view_is_derived_from_the_canonical_store():
    context = CalculationContext()
    context.set_variable_result("VAR99001", Result(1.0, "INVALID_INPUT", "d"), "linha", "L1", DAY)
    view = context._scoped_variables
    assert list(view.values()) == [1.0]
    view.clear()  # cópia: não altera o armazenamento canônico
    assert context.get_variable_result("VAR99001", "linha", "L1", DAY).state == "INVALID_INPUT"


# ============================================================
# Determinismo (32..34)
# ============================================================

def _fingerprint(trace, context):
    return (
        trace.step_order,
        [(e.kind, e.node_id, e.scope_type, e.scope_value, e.period_id, e.value, e.state, e.detail, e.status)
         for e in trace.events],
        sorted((k.entity_id, k.scope_type or "", k.scope_value or "", k.period_id or "",
                repr(r.value), r.state or "", r.detail or "")
               for k, r in context._scoped_results.items()),
    )


TARGETS = ["VAR16902", "VAR16903", "VAR18901", "VAR18902", "VAR18903"]


def _stated_run(orchestrator):
    context = CalculationContext()
    inputs(context)
    context.set_variable_result("VAR12904", Result(1002.0, "VALIDATION_FAILED", "d2"), "linha", "L2", "2026")
    return orchestrator.execute(TARGETS, context, RUN), context


def test_32_load_order_does_not_matter():
    base = _fingerprint(*_stated_run(synthetic()))
    for order in (["energy", "area_41", "yield", "production"], ["yield", "energy", "production", "area_41"]):
        assert _fingerprint(*_stated_run(synthetic(blocks_order=order))) == base
    for order in ([5, 4, 3, 2, 1, 0], [2, 0, 4, 1, 5, 3]):
        assert _fingerprint(*_stated_run(synthetic(links_order=order))) == base


_SNIPPET = """
import hashlib, sys
sys.path.insert(0, {repo!r})
from tests.test_stage3_3a_result_contract import synthetic, _stated_run, _fingerprint
print(hashlib.sha256(repr(_fingerprint(*_stated_run(synthetic()))).encode()).hexdigest())
"""


def test_33_hash_seed_does_not_matter():
    outputs = {
        subprocess.check_output(
            [sys.executable, "-c", _SNIPPET.format(repo=str(REPO))],
            env={**os.environ, "PYTHONHASHSEED": seed}, cwd=REPO,
        )
        for seed in ("0", "55", "987654321")
    }
    assert len(outputs) == 1


def test_34_repeated_execution_is_identical_and_idempotent():
    orchestrator = synthetic()
    trace1, context = _stated_run(orchestrator)
    before = dict(context._scoped_results)
    trace2 = orchestrator.execute(TARGETS, context, RUN)
    assert context._scoped_results == before
    assert {e.status for e in trace2.of_kind(TRANSFER)} == {"UNCHANGED"}
    # Execução nova e independente com as mesmas entradas: resultado idêntico.
    assert _fingerprint(*_stated_run(synthetic()))[1:] == _fingerprint(*_stated_run(synthetic()))[1:]
    assert _fingerprint(trace1, context)[2] == _fingerprint(*_stated_run(synthetic()))[2]
