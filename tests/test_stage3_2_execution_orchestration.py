"""
Etapa 3.2 — execução coordenada interbloco.

Três tipos de cenário, sempre identificados no nome do fixture:

    OFFICIAL      seeds e artefato canônico oficiais, sem alteração.
                  Na configuração atual, todo valor CALCULADO de
                  production/max_ht depende de entradas cujo produtor é o
                  bloco `maintenance` (pendente, D26-01): o orquestrador
                  recusa esses planos com INTERBLOCK_SOURCE_NOT_LOADED. A
                  única cadeia interbloco executável é
                  production.lth_meta (entrada externa) -> energy.lth_meta.

    REAL_DERIVED  (SINTÉTICO documentado) seeds, equações, IDs e vínculos
                  reais; a ÚNICA alteração é, só no fixture de teste,
                  tratar os registros `pending` como entradas livres
                  fornecidas pelo teste. Serve para comprovar a mecânica
                  das cadeias reais (production -> yield -> area_41,
                  production -> energy, production -> max_ht) com as
                  equações reais. Não é comportamento do runtime.

    SYNTHETIC     (SINTÉTICO documentado) catálogo mínimo montado em
                  memória para frequência, instância, ciclo, cadeia
                  quebrada e isolamento com controle total dos valores.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import (
    AggregationRule,
    AggregationRuleInstance,
    AggregationRuleInstanceRegistry,
)
from app.domain.interblock.registry import InterblockLinkRegistry
from app.domain.parameters.registry import ParameterInstanceRegistry
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    InterblockConsumerValueConflictError,
    InterblockExecutionCycleError,
    InterblockInstanceNotDeclaredError,
    InterblockPeriodFrequencyMismatchError,
    InterblockSeedError,
    InterblockSourceNotLoadedError,
    InterblockSourceValueNotFoundError,
    VariableNotFoundError,
)
from app.engine.forecast_engine import ForecastEngine
from app.engine.interblock_orchestrator import (
    AGGREGATION,
    EQUATION,
    TRANSFER,
    ExecutionCatalog,
    InterblockExecutionOrchestrator,
)
from app.engine.interblock_resolver import InterblockValueResolver
from app.engine.scope_resolver import ScopeResolver
from app.engine.time_period_resolver import TimePeriodResolver


REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "data" / "seed"
LINES = [f"L{i}" for i in range(1, 8)]
RUN = date(2026, 9, 1)
PERIOD = {"diário": "2026-09-01", "mensal": "2026-09", "anual": "2026"}


# ============================================================
# Catálogo SINTÉTICO
# ============================================================

def vdef(vid, name, frequency="diário", scope_type="linha", scope_value="L1_L7",
         variable_type="entrada", unit="-"):
    return VariableDefinition(
        vid, name, None, unit, variable_type, frequency, scope_type, scope_value,
        f"{name}.xlsx", "ativo", "numerico",
    )


def eq(eid, target, expression, scope_type="linha", scope_value="L1_L7"):
    return EquationDefinition(eid, target, 1, scope_type, scope_value, expression, "t", "PUBLISHED")


def link(consumer_block, consumer, source_block, source, frequency="diário",
         scope_type="linha", scope_value="L1_L7", instances=None):
    instances = instances if instances is not None else (
        LINES if scope_type == "linha" else [scope_value]
    )
    return {
        "consumer_block": consumer_block, "consumer_definition": consumer,
        "consumer_frequency": frequency,
        "consumer_scope": {"scope_type": scope_type, "scope_value": scope_value},
        "source_block": source_block, "source_definition": source,
        "source_frequency": frequency,
        "source_scope": {"scope_type": scope_type, "scope_value": scope_value},
        "instances": [{"scope_type": scope_type, "scope_value": v} for v in instances],
    }


def synthetic(links_order=None, extra_links=(), extra_equations=(), blocks_order=None):
    """
    production: P_in (entrada) -> P_out = P_in*2 (EQ) -> P_mes (AVERAGE mensal);
                P_ano (entrada anual); P_grp (linha_grupo) = P_out@L1..L7
    yield:      Y_lth <- production.P_out;  Y_calc = Y_lth + 1
    area_41:    A_lth <- yield.Y_lth;       A_calc = A_lth * 10;
                A_ycalc <- yield.Y_calc
    energy:     E_mes <- production.P_mes (mensal); E_ano <- production.P_ano (anual);
                E_grp <- production.P_grp (linha_grupo); E_pend <- maintenance (pendente);
                E_use = E_pend + 1
    """
    variables = {
        "production": [
            vdef("VAR12901", "p_in"), vdef("VAR12902", "p_out", variable_type="calculado"),
            vdef("VAR12903", "p_mes", "mensal", variable_type="calculado"),
            vdef("VAR12904", "p_ano", "anual"),
            vdef("VAR12905", "p_grp", scope_type="linha_grupo", variable_type="calculado"),
            vdef("VAR12906", "p_indep", variable_type="calculado"),
        ],
        "yield": [vdef("VAR11901", "y_lth"), vdef("VAR11902", "y_calc", variable_type="calculado")],
        "area_41": [
            vdef("VAR16901", "a_lth"), vdef("VAR16902", "a_calc", variable_type="calculado"),
            vdef("VAR16903", "a_ycalc"),
        ],
        "energy": [
            vdef("VAR18901", "e_mes", "mensal"), vdef("VAR18902", "e_ano", "anual"),
            vdef("VAR18903", "e_grp", scope_type="linha_grupo"), vdef("VAR18904", "e_pend"),
            vdef("VAR18905", "e_use", variable_type="calculado"),
        ],
    }
    equations = [
        ("production", eq("EQ12901", "VAR12902", "VAR12901 * 2")),
        ("production", eq("EQ12902", "VAR12905", " + ".join(f"VAR12902@{l}" for l in LINES),
                          "linha_grupo", "L1_L7")),
        ("production", eq("EQ12903", "VAR12906", "VAR12901 + 100")),
        ("yield", eq("EQ11901", "VAR11902", "VAR11901 + 1")),
        ("area_41", eq("EQ16901", "VAR16902", "VAR16901 * 10")),
        ("energy", eq("EQ18901", "VAR18905", "VAR18904 + 1")),
        *extra_equations,
    ]
    rule = AggregationRule(
        aggregation_rule_id="AGR-PRODUCTION-P_MES", source_variable_id="VAR12902",
        source_frequency="diário", target_variable_id="VAR12903", target_frequency="mensal",
        aggregation_type="AVERAGE",
    )
    links = [
        link("yield", "VAR11901", "production", "VAR12902"),
        link("area_41", "VAR16901", "yield", "VAR11901"),
        link("area_41", "VAR16903", "yield", "VAR11902"),
        link("energy", "VAR18901", "production", "VAR12903", "mensal"),
        link("energy", "VAR18902", "production", "VAR12904", "anual"),
        link("energy", "VAR18903", "production", "VAR12905", scope_type="linha_grupo"),
        *extra_links,
    ]
    if links_order is not None:
        links = [links[i] for i in links_order]
    payload = {
        "workbooks": {b: {} for b in variables},
        "taxonomy": {"official_blocks": ["production", "yield", "area_41", "energy", "maintenance"]},
        "links": links,
        "pending": [{
            "consumer_block": "energy", "consumer_definition": "VAR18904", "consumer_name": "e_pend",
            "consumer_frequency": "diário",
            "consumer_scope": {"scope_type": "linha", "scope_value": "L1_L7"},
            "source_block": "maintenance", "source_definition": None,
        }],
        "rejected": [],
    }
    order = blocks_order or list(variables)
    raw = {
        b: [{"variable_id": v.variable_definition_id, "variable_name": v.variable_name,
             "unit": v.unit, "frequency": v.frequency, "scope_type": v.scope_type,
             "scope_value": v.scope_value, "value_type": v.value_type} for v in variables[b]]
        for b in order
    }
    registry = InterblockLinkRegistry.from_payload(payload, raw)

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
        registry, block_of,
    )
    return InterblockExecutionOrchestrator(catalog)


def inputs(context, values=None):
    values = values or {}
    for i, line in enumerate(LINES, start=1):
        context.set_variable_value("VAR12901", values.get(line, 10.0 * i), "linha", line, PERIOD["diário"])
        context.set_variable_value("VAR12904", 1000.0 + i, "linha", line, PERIOD["anual"])


def run(orchestrator, targets, values=None, context=None, run_date=RUN):
    context = context or CalculationContext()
    inputs(context, values)
    return orchestrator.execute(targets, context, run_date), context


def position(trace, key):
    return trace.step_order.index(key)


# ============================================================
# Fixtures com os seeds reais
# ============================================================

@pytest.fixture(scope="module")
def official():
    return InterblockExecutionOrchestrator.from_seed_root(SEED)


@pytest.fixture(scope="module")
def real_derived():
    """SINTÉTICO documentado: pendências tratadas como entradas livres."""
    catalog = ExecutionCatalog.from_seed_root(SEED)
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    return InterblockExecutionOrchestrator(catalog)


def real_inputs(orchestrator, plan, context, run_date=RUN, offset=0.0):
    orchestrator.seed_parameters(context)
    resolver = TimePeriodResolver()
    for i, variable in enumerate(plan.required_inputs):
        d = orchestrator.catalog.variable_definitions.get(variable)
        period = resolver.effective_window(d.frequency, run_date).period_id
        for k, (scope_type, scope_value) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
            value = d.allowed_values[0] if d.is_categorical else 1.0 + 0.01 * i + 0.001 * k + offset
            context.set_variable_value(variable, value, scope_type, scope_value, period)


def execute_real(orchestrator, targets, run_date=RUN, offset=0.0):
    plan = orchestrator.plan(targets)
    context = CalculationContext()
    real_inputs(orchestrator, plan, context, run_date, offset)
    return orchestrator.execute(plan, context, run_date), context


# ============================================================
# Execução (1..7)
# ============================================================

def test_01_03_producer_runs_before_consumer_transfer_between_and_value_received():
    orchestrator = synthetic()
    trace, context = run(orchestrator, ["VAR11902"])
    assert trace.step_order == ["EQUATION:EQ12901", "TRANSFER:VAR11901", "EQUATION:EQ11901"]
    kinds = [e.kind for e in trace.events]
    assert kinds.index(TRANSFER) > max(i for i, k in enumerate(kinds) if k == EQUATION and trace.events[i].block == "production")
    for i, line in enumerate(LINES, start=1):
        assert context.get_variable_value("VAR12902", "linha", line, PERIOD["diário"]) == 20.0 * i
        assert context.get_variable_value("VAR11901", "linha", line, PERIOD["diário"]) == 20.0 * i
        assert context.get_variable_value("VAR11902", "linha", line, PERIOD["diário"]) == 20.0 * i + 1


def test_04_three_block_chain_without_shortcut():
    orchestrator = synthetic()
    trace, context = run(orchestrator, ["VAR16902", "VAR16903"])
    order = trace.step_order
    assert order.index("EQUATION:EQ12901") < order.index("TRANSFER:VAR11901") < order.index("TRANSFER:VAR16901")
    assert order.index("TRANSFER:VAR11901") < order.index("EQUATION:EQ11901") < order.index("TRANSFER:VAR16903")
    for event in trace.of_kind(TRANSFER):
        if event.node_id == "VAR16901":
            assert (event.source_block, event.source_variable_id) == ("yield", "VAR11901")
        if event.node_id == "VAR16903":
            assert (event.source_block, event.source_variable_id) == ("yield", "VAR11902")
    assert not [e for e in trace.of_kind(TRANSFER) if e.block == "area_41" and e.source_block == "production"]
    assert context.get_variable_value("VAR16902", "linha", "L3", PERIOD["diário"]) == 600.0
    assert context.get_variable_value("VAR16903", "linha", "L3", PERIOD["diário"]) == 61.0


def test_05_broken_chain_fails():
    orchestrator = synthetic()
    context = CalculationContext()  # sem a entrada do produtor
    with pytest.raises(VariableNotFoundError):
        orchestrator.execute(["VAR16902"], context, RUN)
    with pytest.raises(VariableNotFoundError):
        context.get_variable_value("VAR16901", "linha", "L1", PERIOD["diário"])


def test_06_producer_not_executed_fails():
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    with pytest.raises(InterblockSourceValueNotFoundError):
        resolver.transfer("VAR11901", "linha", "L1", PERIOD["diário"])
    # Executar só o trecho do consumidor não roda o produtor por conta própria.
    plan = orchestrator.plan(["VAR11902"])
    partial = type(plan)(plan.targets, tuple(s for s in plan.steps if s.block != "production"),
                         plan.required_inputs)
    with pytest.raises(InterblockSourceValueNotFoundError):
        orchestrator.execute(partial, context, RUN)


def test_07_pending_link_fails_before_any_execution():
    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    snapshot = dict(context._scoped_variables)
    with pytest.raises(InterblockSourceNotLoadedError) as error:
        orchestrator.execute(["VAR18905"], context, RUN)
    assert error.value.code == "INTERBLOCK_SOURCE_NOT_LOADED"
    assert error.value.details["source_block"] == "maintenance"
    assert context._scoped_variables == snapshot  # nada executado, nada inventado


# ============================================================
# Frequência (8..12)
# ============================================================

def test_08_daily_to_daily():
    trace, context = run(synthetic(), ["VAR11901"])
    assert {e.period_id for e in trace.of_kind(TRANSFER)} == {"2026-09-01"}


def test_09_monthly_to_monthly():
    orchestrator = synthetic()
    context = CalculationContext()
    for day in (1, 2, 3):
        for i, line in enumerate(LINES, start=1):
            context.set_variable_value("VAR12901", float(day * i), "linha", line, f"2026-09-0{day}")
        if day < 3:
            orchestrator.execute(["VAR12902"], context, date(2026, 9, day))
    trace = orchestrator.execute(["VAR18901"], context, date(2026, 9, 3))
    assert trace.step_order == ["EQUATION:EQ12901", "AGGREGATION:AGR-PRODUCTION-P_MES", "TRANSFER:VAR18901"]
    for i, line in enumerate(LINES, start=1):
        expected = (2 * i + 4 * i + 6 * i) / 3
        assert context.get_variable_value("VAR12903", "linha", line, "2026-09") == expected
        assert context.get_variable_value("VAR18901", "linha", line, "2026-09") == expected
    assert {e.period_id for e in trace.of_kind(TRANSFER)} == {"2026-09"}


def test_10_annual_to_annual():
    trace, context = run(synthetic(), ["VAR18902"])
    assert {e.period_id for e in trace.of_kind(TRANSFER)} == {"2026"}
    assert context.get_variable_value("VAR18902", "linha", "L4", "2026") == 1004.0


def test_11_incompatible_frequency_link_is_rejected():
    with pytest.raises(InterblockSeedError):
        synthetic(extra_links=[{**link("energy", "VAR18901", "production", "VAR12902", "mensal"),
                                "source_frequency": "diário"}])


def test_12_incompatible_period_fails_without_fallback():
    orchestrator = synthetic()
    context = CalculationContext()
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    context.set_variable_value("VAR12903", 5.0, "linha", "L1", "2026-09-01")  # granularidade errada
    context.set_variable_value("VAR12903", 6.0, "linha", "L1", "2026")
    with pytest.raises(InterblockSourceValueNotFoundError):
        resolver.transfer("VAR18901", "linha", "L1", "2026-09")
    with pytest.raises(InterblockPeriodFrequencyMismatchError):
        resolver.transfer("VAR18901", "linha", "L1", "2026-09-01")
    # Execução real: o mensal só existe via agregação no próprio período.
    trace, ctx = run(orchestrator, ["VAR18901"])
    assert ctx.get_variable_value("VAR18901", "linha", "L1", "2026-09") == 20.0
    with pytest.raises(VariableNotFoundError):
        ctx.get_variable_value("VAR18901", "linha", "L1", "2026-08")


# ============================================================
# Instância (13..16)
# ============================================================

def test_13_same_instance():
    trace, context = run(synthetic(), ["VAR11901"])
    for event in trace.of_kind(TRANSFER):
        assert context.get_variable_value("VAR12902", event.scope_type, event.scope_value, event.period_id) == event.value


def test_14_unknown_instance_fails():
    orchestrator = synthetic()
    _trace, context = run(orchestrator, ["VAR11901"])
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    with pytest.raises(InterblockInstanceNotDeclaredError):
        resolver.resolve("VAR11901", "linha", "L8", PERIOD["diário"])


def test_15_l3_does_not_substitute_l1():
    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    context._scoped_variables = {
        k: v for k, v in context._scoped_variables.items()
        if not (k.entity_id == "VAR12901" and k.scope_value == "L1")
    }
    with pytest.raises(Exception):
        orchestrator.execute(["VAR11901"], context, RUN)
    with pytest.raises(VariableNotFoundError):
        context.get_variable_value("VAR11901", "linha", "L1", PERIOD["diário"])


def test_16_linha_does_not_substitute_linha_grupo():
    orchestrator = synthetic()
    trace, context = run(orchestrator, ["VAR18903"])
    [event] = trace.of_kind(TRANSFER)
    assert (event.scope_type, event.scope_value) == ("linha_grupo", "L1_L7")
    assert event.value == sum(20.0 * i for i in range(1, 8))
    resolver = InterblockValueResolver(orchestrator.catalog.links, context)
    with pytest.raises(InterblockInstanceNotDeclaredError):
        resolver.resolve("VAR18903", "linha", "L1", PERIOD["diário"])
    with pytest.raises(InterblockInstanceNotDeclaredError):
        resolver.resolve("VAR11901", "linha_grupo", "L1_L7", PERIOD["diário"])


# ============================================================
# Determinismo (17..20)
# ============================================================

def _fingerprint(trace, context):
    return (
        trace.step_order,
        [(e.kind, e.node_id, e.variable_id, e.scope_type, e.scope_value, e.period_id, e.value, e.status)
         for e in trace.events],
        sorted((k.entity_id, k.scope_type or "", k.scope_value or "", k.period_id or "", v)
               for k, v in context._scoped_variables.items()),
    )


TARGETS = ["VAR16902", "VAR16903", "VAR18901", "VAR18902", "VAR18903"]


def test_17_same_input_same_result():
    assert _fingerprint(*run(synthetic(), TARGETS)) == _fingerprint(*run(synthetic(), TARGETS))


def test_18_block_order_does_not_matter():
    base = _fingerprint(*run(synthetic(), TARGETS))
    for order in (["energy", "area_41", "yield", "production"], ["yield", "energy", "production", "area_41"]):
        assert _fingerprint(*run(synthetic(blocks_order=order), TARGETS)) == base


def test_19_link_order_does_not_matter():
    base = _fingerprint(*run(synthetic(), TARGETS))
    for order in ([5, 4, 3, 2, 1, 0], [2, 0, 4, 1, 5, 3]):
        assert _fingerprint(*run(synthetic(links_order=order), TARGETS)) == base


_HASH_SNIPPET = """
import hashlib, json, sys
sys.path.insert(0, {repo!r})
from tests.test_stage3_2_execution_orchestration import synthetic, run, TARGETS, _fingerprint
from tests.test_stage3_2_execution_orchestration import real_derived_orchestrator, execute_real
print(hashlib.sha256(repr(_fingerprint(*run(synthetic(), TARGETS))).encode()).hexdigest())
print(hashlib.sha256(repr(_fingerprint(*execute_real(real_derived_orchestrator(), ["VAR18002"]))).encode()).hexdigest())
"""


def real_derived_orchestrator():
    catalog = ExecutionCatalog.from_seed_root(SEED)
    payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    payload["pending"] = []
    raw = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in payload["workbooks"]}
    catalog.links = InterblockLinkRegistry.from_payload(payload, raw)
    return InterblockExecutionOrchestrator(catalog)


def test_20_hash_seed_does_not_matter():
    outputs = set()
    for seed in ("0", "123", "987654321"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outputs.add(subprocess.check_output(
            [sys.executable, "-c", _HASH_SNIPPET.format(repo=str(REPO))], env=env, cwd=REPO,
        ))
    assert len(outputs) == 1


# ============================================================
# Isolamento (21..23)
# ============================================================

def test_21_one_block_does_not_contaminate_another():
    orchestrator = synthetic()
    context = CalculationContext()
    inputs(context)
    before = dict(context._scoped_variables)
    trace = orchestrator.execute(["VAR18902"], context, RUN)  # energy <- production (anual)
    changed = {k.entity_id for k, v in context._scoped_variables.items() if before.get(k) != v}
    assert changed == {"VAR18902"}
    assert {s.block for s in trace.plan.steps} == {"energy"}
    # yield: só o que o plano de yield toca; p_indep (production, independente) intocado.
    trace = orchestrator.execute(["VAR11902"], context, RUN)
    assert not [k for k in context._scoped_variables if k.entity_id == "VAR12906"]
    assert not [k for k in context._scoped_variables if k.entity_id.startswith("VAR18") and k.entity_id != "VAR18902"]


def test_22_periods_stay_isolated():
    orchestrator = synthetic()
    context = CalculationContext()
    for day, factor in ((1, 1.0), (2, 3.0)):
        for i, line in enumerate(LINES, start=1):
            context.set_variable_value("VAR12901", factor * i, "linha", line, f"2026-09-0{day}")
        orchestrator.execute(["VAR11902"], context, date(2026, 9, day))
    for i, line in enumerate(LINES, start=1):
        assert context.get_variable_value("VAR11901", "linha", line, "2026-09-01") == 2.0 * i
        assert context.get_variable_value("VAR11901", "linha", line, "2026-09-02") == 6.0 * i


def test_23_repeated_execution_does_not_duplicate_transfer():
    orchestrator = synthetic()
    trace1, context = run(orchestrator, ["VAR16902"])
    before = dict(context._scoped_variables)
    trace2 = orchestrator.execute(["VAR16902"], context, RUN)
    assert context._scoped_variables == before
    assert {e.status for e in trace1.of_kind(TRANSFER)} == {"WRITTEN"}
    assert {e.status for e in trace2.of_kind(TRANSFER)} == {"UNCHANGED"}
    assert len(trace2.of_kind(TRANSFER)) == len(trace1.of_kind(TRANSFER))
    # Valor incompatível já presente no consumidor: erro 3.1, sem overwrite.
    context.set_variable_value("VAR11901", -1.0, "linha", "L2", PERIOD["diário"])
    with pytest.raises(InterblockConsumerValueConflictError):
        orchestrator.execute(["VAR16902"], context, RUN)
    assert context.get_variable_value("VAR11901", "linha", "L2", PERIOD["diário"]) == -1.0


def test_cycle_fails_with_the_full_cycle():
    # SINTÉTICO: uma equação de production realimenta a entrada P_in a
    # partir de area_41 (A_calc), fechando production -> yield -> area_41
    # -> production em nível de definição.
    orchestrator = synthetic(extra_equations=[("production", eq("EQ12909", "VAR12901", "VAR16902 + 0"))])
    with pytest.raises(InterblockExecutionCycleError) as error:
        orchestrator.plan(["VAR16902"])
    cycle = error.value.details["cycle"]
    assert cycle[0] == cycle[-1]
    assert {"EQUATION:EQ12909", "EQUATION:EQ12901", "TRANSFER:VAR11901", "TRANSFER:VAR16901",
            "EQUATION:EQ16901"} <= set(cycle)
    assert set(error.value.details["blocks"]) == {"production", "yield", "area_41"}


# ============================================================
# Regressão dos blocos isolados (24..27)
# ============================================================

def _direct_engine(orchestrator, plan, context, run_date=RUN):
    """Caminho existente: ForecastEngine direto sobre as equações do plano."""
    registry = EquationDefinitionRegistry()
    for step in plan.steps:
        if step.kind == EQUATION:
            registry.add(orchestrator.catalog.equation_definitions.get(step.node_id))
    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=registry, calculation_context=context,
        variable_definition_registry=orchestrator.catalog.variable_definitions, run_date=run_date,
    )


@pytest.mark.parametrize("block, target", [
    ("production", "VAR12031"),   # lth
    ("yield", "VAR11226"),        # yield (calculado; entradas livres + lth local)
    ("energy", "VAR18002"),
    ("max_ht", "VAR13039"),
])
def test_24_27_isolated_block_behaves_as_the_existing_engine(real_derived, block, target):
    """
    Equações do bloco executadas pelo orquestrador x pelo ForecastEngine
    direto (caminho existente), com as mesmas entradas: resultados
    idênticos. Entradas de outros blocos fornecidas diretamente no ID
    local (como o runtime existente sempre fez fora do orquestrador).
    """

    orchestrator = real_derived
    plan = orchestrator.plan([target])
    local_steps = tuple(s for s in plan.steps if s.block == block and s.kind == EQUATION)
    local_plan = type(plan)((target,), local_steps, ())
    produced_locally = {orchestrator.catalog.equation_definitions.get(s.node_id).target_variable_id for s in local_steps}

    def prepare():
        context = CalculationContext()
        orchestrator.seed_parameters(context)
        resolver = TimePeriodResolver()
        needed = set()
        for s in local_steps:
            import re
            needed |= set(re.findall(r"VAR\d+", orchestrator.catalog.equation_definitions.get(s.node_id).expression))
        for i, variable in enumerate(sorted(needed - produced_locally)):
            d = orchestrator.catalog.variable_definitions.get(variable)
            period = resolver.effective_window(d.frequency, RUN).period_id
            for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
                value = d.allowed_values[0] if d.is_categorical else 2.0 + 0.01 * i + 0.001 * k
                context.set_variable_value(variable, value, st, sv, period)
        return context

    via_orchestrator = prepare()
    orchestrator.execute(local_plan, via_orchestrator, RUN)
    via_engine = prepare()
    _direct_engine(orchestrator, local_plan, via_engine)
    assert via_orchestrator._scoped_variables == via_engine._scoped_variables
    assert [k for k in via_engine._scoped_variables if k.entity_id == target]


def test_24_27_official_block_plans_report_the_pending_boundary(official):
    """OFFICIAL: por bloco, quais alvos são executáveis hoje sem pendência."""
    computable = {}
    for block in ("production", "yield", "energy", "max_ht", "area_41"):
        ok = 0
        for target in official.targets_of_blocks([block]):
            try:
                official.plan([target])
                ok += 1
            except InterblockSourceNotLoadedError as error:
                assert error.details["source_block"] in {
                    "maintenance", "forecast", "temperature_lp", "area_04_13", "alumina",
                }
        computable[block] = ok
    assert computable["yield"] > 0
    assert computable["production"] == 0 and computable["max_ht"] == 0


def test_yield_official_execution_matches_existing_engine(official):
    """OFFICIAL: um alvo de yield sem dependência pendente executa pelo orquestrador."""
    targets = [t for t in official.targets_of_blocks(["yield"])]
    for target in targets:
        try:
            plan = official.plan([target])
        except InterblockSourceNotLoadedError:
            continue
        if all(s.kind == EQUATION for s in plan.steps) and len(plan.steps) >= 2:
            break
    else:
        pytest.fail("nenhum alvo de yield executável")
    ctx_a = CalculationContext()
    real_inputs(official, plan, ctx_a)
    official.execute(plan, ctx_a, RUN)
    ctx_b = CalculationContext()
    real_inputs(official, plan, ctx_b)
    _direct_engine(official, plan, ctx_b)
    assert ctx_a._scoped_variables == ctx_b._scoped_variables


# ============================================================
# Cadeias reais (28..30)
# ============================================================

def test_28_official_real_chain_production_yield_area_41_is_blocked_by_maintenance(official):
    """OFFICIAL: a cadeia é planejada na ordem correta e recusada pela pendência."""
    with pytest.raises(InterblockSourceNotLoadedError) as error:
        official.plan(["VAR16008"])
    assert error.value.details["source_block"] == "maintenance"
    plan = official.plan(["VAR16008"], on_pending="report")
    keys = [s.key for s in plan.steps]
    assert keys == ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"]
    assert {b.source_block for b in plan.pending_blockers} == {"maintenance"}
    assert sorted(b.consumer_name for b in plan.pending_blockers) == sorted(
        [f"reducao_lth_{s}" for s in ("calcinacao", "clarificacao", "digestao", "precipitacao")]
        + [f"tempo_{s}" for s in ("calcinacao", "clarificacao", "digestao", "precipitacao")]
    )
    with pytest.raises(InterblockSourceNotLoadedError):
        official.execute(plan, CalculationContext(), RUN)


def test_28_real_derived_chain_production_yield_area_41(real_derived):
    trace, context = execute_real(real_derived, ["VAR16008"])
    order = trace.step_order
    assert order == ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"]
    transfers = {e.node_id: e for e in trace.of_kind(TRANSFER) if e.scope_value == "L2"}
    assert (transfers["VAR11031"].source_block, transfers["VAR11031"].source_variable_id) == ("production", "VAR12031")
    assert (transfers["VAR16007"].source_block, transfers["VAR16007"].source_variable_id) == ("yield", "VAR11031")
    period = PERIOD["diário"]
    lth = {l: context.get_variable_value("VAR12031", "linha", l, period) for l in LINES}
    for line in LINES:
        assert context.get_variable_value("VAR11031", "linha", line, period) == lth[line]
        assert context.get_variable_value("VAR16007", "linha", line, period) == lth[line]
    assert context.get_variable_value("VAR16008", "linha_grupo", "L1_L3", period) == pytest.approx(
        (lth["L1"] + lth["L2"] + lth["L3"]) / 3
    )


def test_29_real_derived_chain_production_energy(real_derived):
    trace, context = execute_real(real_derived, ["VAR18002"])  # energy EQ18001 = VAR18001 / 24
    order = trace.step_order
    assert order.index("EQUATION:EQ12012") < order.index("TRANSFER:VAR11031")
    assert order.index("TRANSFER:VAR12062") < order.index("TRANSFER:VAR18001") < order.index("EQUATION:EQ18001")
    producao = "VAR12046"
    period = PERIOD["diário"]
    for line in LINES:
        value = context.get_variable_value(producao, "linha", line, period)
        assert context.get_variable_value("VAR18001", "linha", line, period) == value
        assert context.get_variable_value("VAR18002", "linha", line, period) == pytest.approx(value / 24)


def test_29_official_chain_production_lth_meta_to_energy(official):
    """OFFICIAL: única cadeia interbloco executável hoje (produtor = entrada externa)."""
    plan = official.plan(["VAR18011"])
    assert [s.key for s in plan.steps] == ["TRANSFER:VAR18011"]
    assert plan.required_inputs == ("VAR12066",)
    context = CalculationContext()
    for i, line in enumerate(LINES, start=1):
        context.set_variable_value("VAR12066", 1000.0 + 50 * i, "linha", line, "2026")
    trace = official.execute(plan, context, RUN)
    assert {e.period_id for e in trace.events} == {"2026"}
    for i, line in enumerate(LINES, start=1):
        assert context.get_variable_value("VAR18011", "linha", line, "2026") == 1000.0 + 50 * i


def test_30_real_derived_chain_production_max_ht(real_derived):
    trace, context = execute_real(real_derived, ["VAR13039"])  # (VAR13062*VAR13008)/1000
    assert trace.step_order == ["EQUATION:EQ12012", "TRANSFER:VAR13062", "EQUATION:EQ13014"]
    period = PERIOD["diário"]
    for line in LINES:
        lth = context.get_variable_value("VAR12031", "linha", line, period)
        assert context.get_variable_value("VAR13062", "linha", line, period) == lth
        factor = context.get_variable_value("VAR13008", "linha", line, period)
        assert context.get_variable_value("VAR13039", "linha", line, period) == pytest.approx(lth * factor / 1000)


def test_30_official_max_ht_is_blocked_by_maintenance(official):
    with pytest.raises(InterblockSourceNotLoadedError) as error:
        official.plan(["VAR13039"])
    assert error.value.details["source_block"] == "maintenance"


# ============================================================
# Contrato preservado
# ============================================================

def test_orchestrator_uses_only_canonical_artifacts():
    import ast

    tree = ast.parse((REPO / "app/engine/interblock_orchestrator.py").read_text(encoding="utf-8"))
    tokens = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            tokens |= {getattr(node, "module", None) or ""} | {a.name for a in node.names}
        elif isinstance(node, ast.Attribute):
            tokens.add(node.attr)
        elif isinstance(node, ast.Name):
            tokens.add(node.id)
    assert not [t for t in tokens if t and t.startswith(("openpyxl", "tools"))]
    assert "fonte" not in tokens and "source_reference" not in tokens


def test_pending_boundary_is_never_filled(official):
    for pending in official.catalog.links.pending():
        with pytest.raises(InterblockSourceNotLoadedError):
            official.plan([pending.consumer_definition_id])
