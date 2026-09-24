"""
Fase B (correções estruturais) — materialização de AggregationRule
por instância espacial.

Uma AggregationRule é lógica; cada escopo concreto em que alvo,
origem e peso existem gera uma AggregationRuleInstance, executada no
seu próprio escopo. Fixtures genéricas (IDs VAR9xxxx, fora de qualquer
faixa produtiva).
"""

from datetime import date
from pathlib import Path

import pytest

from app.domain.forecast.aggregation import (
    AggregationRule,
    AggregationRuleInstance,
    AggregationRuleInstanceRegistry,
    AggregationRuleRegistry,
)
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    AggregationScopeMismatchError,
    VariableNotFoundError,
)
from app.engine.scope_resolver import ScopeResolver
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)
from app.repositories.seed_loader import SeedLoader


SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]


def _definition(variable_id, frequency, scope_type, scope_value):
    return VariableDefinition(
        variable_id, f"v_{variable_id}", "-", "-", "calculada",
        frequency, scope_type, scope_value, "test", "ativo",
    )


def _rule(rule_id, source, target, target_frequency, kind="AVERAGE", weight=None):
    return AggregationRule(
        aggregation_rule_id=rule_id,
        source_variable_id=source,
        source_frequency="diário",
        target_variable_id=target,
        target_frequency=target_frequency,
        aggregation_type=kind,
        weight_variable_id=weight,
    )


def _registry(*definitions):
    registry = VariableDefinitionRegistry()
    for definition in definitions:
        registry.add(definition)
    return registry


def _materialize(registry, *rules):
    rule_registry = AggregationRuleRegistry()
    for rule in rules:
        rule_registry.add(rule)
    return SeedLoader(SEED_ROOT).load_aggregation_rule_instances(
        variable_definition_registry=registry,
        rule_registry=rule_registry,
    )


def test_line_range_rule_materializes_one_instance_per_line_and_frequency():
    registry = _registry(
        _definition("VAR90101", "diário", "linha", "L1_L7"),
        _definition("VAR90102", "mensal", "linha", "L1_L7"),
        _definition("VAR90103", "anual", "linha", "L1_L7"),
    )

    instances = _materialize(
        registry,
        _rule("AGG90101", "VAR90101", "VAR90102", "mensal"),
        _rule("AGG90102", "VAR90101", "VAR90103", "anual"),
    )

    assert len(instances) == 14
    for rule_id in ("AGG90101", "AGG90102"):
        materialized = instances.for_rule(rule_id)
        assert [i.scope_value for i in materialized] == LINES
        assert {i.scope_type for i in materialized} == {"linha"}
        assert [i.aggregation_rule_instance_id for i in materialized] == [
            f"{rule_id}@{line}" for line in LINES
        ]


def test_per_line_sources_with_shared_target_bind_each_rule_to_its_line():
    registry = _registry(
        *[
            _definition(f"VAR9020{n}", "diário", "linha", f"L{n}")
            for n in range(1, 8)
        ],
        _definition("VAR90210", "mensal", "linha", "L1_L7"),
    )

    instances = _materialize(
        registry,
        *[
            _rule(f"AGG9020{n}", f"VAR9020{n}", "VAR90210", "mensal")
            for n in range(1, 8)
        ],
    )

    assert len(instances) == 7
    for n in range(1, 8):
        (instance,) = instances.for_rule(f"AGG9020{n}")
        assert (instance.scope_type, instance.scope_value) == ("linha", f"L{n}")


def test_group_and_plant_rules_stay_single_instance():
    registry = _registry(
        _definition("VAR90301", "diário", "linha_grupo", "L1_L3"),
        _definition("VAR90302", "mensal", "linha_grupo", "L1_L3"),
        _definition("VAR90303", "diário", "planta", "PLANTA"),
        _definition("VAR90304", "mensal", "planta", "PLANTA"),
    )

    instances = _materialize(
        registry,
        _rule("AGG90301", "VAR90301", "VAR90302", "mensal"),
        _rule("AGG90302", "VAR90303", "VAR90304", "mensal", kind="SUM"),
    )

    assert [
        (i.aggregation_rule_instance_id, i.scope_type, i.scope_value)
        for i in instances
    ] == [
        ("AGG90301@L1_L3", "linha_grupo", "L1_L3"),
        ("AGG90302@PLANTA", "planta", "PLANTA"),
    ]


def test_weight_restricts_instances_to_scopes_where_it_exists():
    registry = _registry(
        _definition("VAR90401", "diário", "linha", "L1_L7"),
        _definition("VAR90402", "diário", "linha", "L1_L3"),
        _definition("VAR90403", "mensal", "linha", "L1_L7"),
    )

    instances = _materialize(
        registry,
        _rule(
            "AGG90401", "VAR90401", "VAR90403", "mensal",
            kind="WEIGHTED_AVERAGE", weight="VAR90402",
        ),
    )

    assert [i.scope_value for i in instances] == ["L1", "L2", "L3"]


def test_rule_without_any_applicable_scope_is_an_explicit_error():
    registry = _registry(
        _definition("VAR90501", "diário", "linha_grupo", "L1_L3"),
        _definition("VAR90502", "mensal", "linha_grupo", "L4_L5"),
    )

    with pytest.raises(AggregationScopeMismatchError, match="AGG90501"):
        _materialize(
            registry, _rule("AGG90501", "VAR90501", "VAR90502", "mensal")
        )


def test_rule_referencing_unknown_variable_fails():
    registry = _registry(_definition("VAR90601", "mensal", "linha", "L1"))

    with pytest.raises(KeyError):
        _materialize(
            registry, _rule("AGG90601", "VAR90699", "VAR90601", "mensal")
        )


def test_instance_registry_rejects_duplicates():
    rule = _rule("AGG90701", "VAR90701", "VAR90702", "mensal")
    registry = AggregationRuleInstanceRegistry()
    registry.add(AggregationRuleInstance.create(rule, "linha", "L1"))

    with pytest.raises(ValueError):
        registry.add(AggregationRuleInstance.create(rule, "linha", "L1"))


def test_resolver_scope_intersection_is_order_of_target():
    resolver = ScopeResolver()
    rule = _rule("AGG90801", "VAR90801", "VAR90802", "mensal")

    instances = resolver.resolve_aggregation_rule(
        rule,
        target_definition=_definition("VAR90802", "mensal", "linha", "L1_L7"),
        source_definition=_definition("VAR90801", "diário", "linha", "L4_L5"),
    )

    assert [i.scope_value for i in instances] == ["L4", "L5"]


# ------------------------------------------------------------
# Execução: cada instância lê e grava apenas o seu escopo.
# ------------------------------------------------------------


def _fill_daily(context, variable_id, scope_type, scope_value, values):
    for day, value in enumerate(values, start=1):
        context.set_variable_value(
            variable_id, value, scope_type, scope_value,
            period_id=f"2026-03-{day:02d}",
        )


def test_line_instances_aggregate_independently():
    registry = _registry(
        _definition("VAR90901", "diário", "linha", "L1_L7"),
        _definition("VAR90902", "mensal", "linha", "L1_L7"),
    )
    instances = _materialize(
        registry, _rule("AGG90901", "VAR90901", "VAR90902", "mensal")
    )

    context = CalculationContext()
    for n, line in enumerate(LINES, start=1):
        _fill_daily(context, "VAR90901", "linha", line, [n, 3 * n])

    orchestrator = TemporalForecastOrchestrator()
    run_date = date(2026, 3, 2)

    results = {
        instance.scope_value: orchestrator.run_aggregation_instance(
            instance, context, run_date
        )
        for instance in instances
    }

    for n, line in enumerate(LINES, start=1):
        forecast_value = results[line]
        assert forecast_value.value == pytest.approx(2 * n)
        assert (forecast_value.scope_type, forecast_value.scope_value) == (
            "linha", line,
        )
        assert forecast_value.period_id == "2026-03"


def test_group_instances_do_not_leak_between_groups():
    registry = _registry(
        _definition("VAR91001", "diário", "linha_grupo", "L1_L3"),
        _definition("VAR91002", "diário", "linha_grupo", "L4_L5"),
        _definition("VAR91003", "mensal", "linha_grupo", "L1_L3"),
        _definition("VAR91004", "mensal", "linha_grupo", "L4_L5"),
    )
    instances = _materialize(
        registry,
        _rule("AGG91001", "VAR91001", "VAR91003", "mensal", kind="SUM"),
        _rule("AGG91002", "VAR91002", "VAR91004", "mensal", kind="SUM"),
    )

    context = CalculationContext()
    _fill_daily(context, "VAR91001", "linha_grupo", "L1_L3", [1.0, 2.0])
    _fill_daily(context, "VAR91002", "linha_grupo", "L4_L5", [10.0, 20.0])

    orchestrator = TemporalForecastOrchestrator()
    run_date = date(2026, 3, 2)

    values = {
        i.aggregation_rule_instance_id: orchestrator.run_aggregation_instance(
            i, context, run_date
        ).value
        for i in instances
    }

    assert values == {"AGG91001@L1_L3": 3.0, "AGG91002@L4_L5": 30.0}


def test_instance_missing_its_own_source_does_not_borrow_another_scope():
    registry = _registry(
        _definition("VAR91101", "diário", "linha", "L1_L7"),
        _definition("VAR91102", "mensal", "linha", "L1_L7"),
    )
    instances = _materialize(
        registry, _rule("AGG91101", "VAR91101", "VAR91102", "mensal")
    )

    context = CalculationContext()
    _fill_daily(context, "VAR91101", "linha", "L1", [5.0, 5.0])

    orchestrator = TemporalForecastOrchestrator()
    run_date = date(2026, 3, 2)

    assert orchestrator.run_aggregation_instance(
        instances.get("AGG91101@L1"), context, run_date
    ).value == 5.0

    with pytest.raises(VariableNotFoundError):
        orchestrator.run_aggregation_instance(
            instances.get("AGG91101@L2"), context, run_date
        )


# ------------------------------------------------------------
# Seeds reais: toda regra materializa ao menos uma instância.
# ------------------------------------------------------------


def test_real_seeds_materialize_every_rule():
    loader = SeedLoader(SEED_ROOT)
    rules = loader.load_aggregation_rules()
    instances = loader.load_aggregation_rule_instances()

    assert len(rules) > 0
    materialized_rule_ids = {i.rule.aggregation_rule_id for i in instances}
    assert materialized_rule_ids == {r.aggregation_rule_id for r in rules}
    assert len(instances) >= len(rules)
