"""
Objetivo:
    Validar a integração entre ForecastEngine e ScopeResolver para
    materialização de EquationDefinition em EquationInstance,
    garantindo que o ForecastEngine apenas orquestre o processo.
"""

from app.domain.equations.models import EquationDefinition
from app.engine.forecast_engine import ForecastEngine
from app.engine.scope_resolver import ScopeResolver


def test_forecast_engine_materializes_line_range():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11002@L1 + PARAM11001",
        source_reference="TEST",
        status="PUBLISHED",
    )

    engine = ForecastEngine(
        scope_resolver=ScopeResolver(),
    )

    instances = engine.materialize_equation(definition)

    assert len(instances) == 7

    assert [instance.scope_value for instance in instances] == [
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
    ]


def test_forecast_engine_materialization_preserves_definition_id():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=2,
        scope_type="linha",
        scope_value="L4_L5",
        expression="VAR11002@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    engine = ForecastEngine(
        scope_resolver=ScopeResolver(),
    )

    instances = engine.materialize_equation(definition)

    assert len(instances) == 2

    assert all(
        instance.equation_definition_id == "EQ11001"
        for instance in instances
    )

    assert all(
        instance.version == 2
        for instance in instances
    )


def test_forecast_engine_materializes_single_scope():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11002@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    engine = ForecastEngine(
        scope_resolver=ScopeResolver(),
    )

    instances = engine.materialize_equation(definition)

    assert len(instances) == 1
    assert instances[0].scope_value == "L4"
