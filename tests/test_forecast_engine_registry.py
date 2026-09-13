import pytest

from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    DependencyCycleError,
    DuplicateVariableProducerError,
)
from app.engine.forecast_engine import ForecastEngine


# ============================================================
# HELPERS
# ============================================================


def make_equation(
    equation_id: str,
    target_variable_id: str,
    expression: str,
) -> Equation:
    return Equation(
        equation_id=equation_id,
        target_variable_id=target_variable_id,
        version=1,
        scope_type="linha",
        scope_value="L1",
        expression=expression,
        source_reference="test",
        status="PUBLISHED",
    )


def make_variable(variable_id: str) -> Variable:
    return Variable(
        variable_id=variable_id,
        variable_name=f"Variable {variable_id}",
        description="Test variable",
        unit="unit",
        variable_type="input",
        frequency="monthly",
        scope_type=None,
        scope_value=None,
        source_reference="test",
        status="ACTIVE",
    )


def make_parameter(parameter_id: str) -> Parameter:
    return Parameter(
        parameter_id=parameter_id,
        parameter_name=f"Parameter {parameter_id}",
        description="Test parameter",
        unit="unit",
        value=1.0,
        version=1,
        scope_type=None,
        scope_value=None,
        source_reference="test",
        status="ACTIVE",
    )


# ============================================================
# TESTE 1 — EXECUÇÃO DE UMA EQUAÇÃO A PARTIR DO REGISTRY
# ============================================================


def test_forecast_engine_calculates_equation_from_registry():
    equation_registry = EquationRegistry()

    equation = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_registry.add(equation)

    variable_registry = VariableRegistry()

    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR11005"))

    parameter_registry = ParameterRegistry()

    parameter_registry.add(make_parameter("PARAM11001"))

    context = CalculationContext()

    context.set_variable("VAR10001", 100)
    context.set_parameter("PARAM11001", 0.8)

    engine = ForecastEngine()

    results = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert results == {
        "EQ11001": 80
    }

    assert context.get_variable("VAR11005") == 80


# ============================================================
# TESTE 2 — CADEIA DE DEPENDÊNCIAS A PARTIR DO REGISTRY
# ============================================================


def test_forecast_engine_resolves_dependency_chain_from_registry():
    equation_registry = EquationRegistry()

    # Inseridas propositalmente fora da ordem de execução.

    equation_3 = make_equation(
        equation_id="EQ12003",
        target_variable_id="VAR12003",
        expression="VAR12001 + PARAM12002",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_registry.add(equation_3)
    equation_registry.add(equation_2)
    equation_registry.add(equation_1)

    variable_registry = VariableRegistry()

    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR11005"))
    variable_registry.add(make_variable("VAR12001"))
    variable_registry.add(make_variable("VAR12003"))

    parameter_registry = ParameterRegistry()

    parameter_registry.add(make_parameter("PARAM11001"))
    parameter_registry.add(make_parameter("PARAM12001"))
    parameter_registry.add(make_parameter("PARAM12002"))

    context = CalculationContext()

    context.set_variable("VAR10001", 100)

    context.set_parameter("PARAM11001", 0.8)
    context.set_parameter("PARAM12001", 2)
    context.set_parameter("PARAM12002", 10)

    engine = ForecastEngine()

    results = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert results == {
        "EQ11001": 80,
        "EQ12001": 160,
        "EQ12003": 170,
    }

    assert context.get_variable("VAR11005") == 80
    assert context.get_variable("VAR12001") == 160
    assert context.get_variable("VAR12003") == 170


# ============================================================
# TESTE 3 — DUAS EQUAÇÕES PRODUZINDO A MESMA VARIÁVEL
# ============================================================


def test_forecast_engine_rejects_duplicate_variable_producers():
    equation_registry = EquationRegistry()

    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_2 = make_equation(
        equation_id="EQ11002",
        target_variable_id="VAR11005",
        expression="VAR10002 * PARAM11002",
    )

    equation_registry.add(equation_1)
    equation_registry.add(equation_2)

    variable_registry = VariableRegistry()

    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR10002"))
    variable_registry.add(make_variable("VAR11005"))

    parameter_registry = ParameterRegistry()

    parameter_registry.add(make_parameter("PARAM11001"))
    parameter_registry.add(make_parameter("PARAM11002"))

    context = CalculationContext()

    engine = ForecastEngine()

    with pytest.raises(DuplicateVariableProducerError):
        engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=context,
        )


# ============================================================
# TESTE 4 — CICLO DE DEPENDÊNCIAS A PARTIR DO REGISTRY
# ============================================================


def test_forecast_engine_rejects_dependency_cycle_from_registry():
    equation_registry = EquationRegistry()

    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11001",
        expression="VAR11002 + 1",
    )

    equation_2 = make_equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        expression="VAR11001 + 1",
    )

    equation_registry.add(equation_1)
    equation_registry.add(equation_2)

    variable_registry = VariableRegistry()

    variable_registry.add(make_variable("VAR11001"))
    variable_registry.add(make_variable("VAR11002"))

    parameter_registry = ParameterRegistry()

    context = CalculationContext()

    engine = ForecastEngine()

    with pytest.raises(DependencyCycleError):
        engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=context,
        )
