"""
Objetivo:
    Validar o fluxo integrado de execução de EquationDefinition
    materializada em EquationInstances pelo ForecastEngine,
    incluindo construção do grafo, resolução das dependências
    e armazenamento dos resultados no CalculationContext.
"""

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine


def make_definition(
    equation_definition_id,
    target_variable_id,
    expression,
):
    return EquationDefinition(
        equation_definition_id=equation_definition_id,
        target_variable_id=target_variable_id,
        version=1,
        scope_type="linha",
        scope_value="L4_L5",
        expression=expression,
        source_reference="TEST",
        status="PUBLISHED",
    )


def test_forecast_engine_executes_definition_instances_by_scope():
    registry = EquationDefinitionRegistry()

    definition = make_definition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        expression="VAR10001@L4 + PARAM10001@L4",
    )

    registry.add(definition)

    context = CalculationContext()

    context.set_variable_value(
        variable_id="VAR10001",
        value=100,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_parameter_value(
        parameter_id="PARAM10001",
        value=10,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_variable_value(
        variable_id="VAR10001",
        value=200,
        scope_type="linha",
        scope_value="L5",
    )

    context.set_parameter_value(
        parameter_id="PARAM10001",
        value=20,
        scope_type="linha",
        scope_value="L5",
    )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert results == {
        "EQ11001@v1@L4": 110,
        "EQ11001@v1@L5": 220,
    }

    assert context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L4",
    ) == 110

    assert context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L5",
    ) == 220


def test_forecast_engine_resolves_dependencies_between_instances():
    registry = EquationDefinitionRegistry()

    producer = make_definition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        expression="VAR10001@L4 * PARAM10001@L4",
    )

    consumer = make_definition(
        equation_definition_id="EQ11002",
        target_variable_id="VAR11002",
        expression="VAR11001@L4 + PARAM10002@L4",
    )

    registry.add(producer)
    registry.add(consumer)

    context = CalculationContext()

    # ------------------------------------------------------------------
    # Inputs da instância L4
    # ------------------------------------------------------------------

    context.set_variable_value(
        variable_id="VAR10001",
        value=100,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_parameter_value(
        parameter_id="PARAM10001",
        value=0.80,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_parameter_value(
        parameter_id="PARAM10002",
        value=20,
        scope_type="linha",
        scope_value="L4",
    )

    # ------------------------------------------------------------------
    # Inputs da instância L5
    # ------------------------------------------------------------------

    context.set_variable_value(
        variable_id="VAR10001",
        value=200,
        scope_type="linha",
        scope_value="L5",
    )

    context.set_parameter_value(
        parameter_id="PARAM10001",
        value=0.90,
        scope_type="linha",
        scope_value="L5",
    )

    context.set_parameter_value(
        parameter_id="PARAM10002",
        value=30,
        scope_type="linha",
        scope_value="L5",
    )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    # ------------------------------------------------------------------
    # Resultados L4
    # ------------------------------------------------------------------

    assert results["EQ11001@v1@L4"] == 80
    assert results["EQ11002@v1@L4"] == 100

    assert context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L4",
    ) == 80

    assert context.get_variable_value(
        variable_id="VAR11002",
        scope_type="linha",
        scope_value="L4",
    ) == 100

    # ------------------------------------------------------------------
    # Resultados L5
    # ------------------------------------------------------------------

    assert results["EQ11001@v1@L5"] == 180
    assert results["EQ11002@v1@L5"] == 210

    assert context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L5",
    ) == 180

    assert context.get_variable_value(
        variable_id="VAR11002",
        scope_type="linha",
        scope_value="L5",
    ) == 210
