import pytest

from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    ParameterReferenceNotFoundError,
    TargetVariableNotFoundError,
    VariableNotFoundError,
    VariableReferenceNotFoundError,
)
from app.engine.forecast_engine import ForecastEngine


# ============================================================
# HELPERS
# ============================================================


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


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def variable_registry():
    registry = VariableRegistry()

    registry.add(make_variable("VAR10001"))
    registry.add(make_variable("VAR11005"))
    registry.add(make_variable("VAR12001"))
    registry.add(make_variable("VAR12003"))

    return registry


@pytest.fixture
def parameter_registry():
    registry = ParameterRegistry()

    registry.add(make_parameter("PARAM11001"))
    registry.add(make_parameter("PARAM12001"))
    registry.add(make_parameter("PARAM12002"))

    return registry


@pytest.fixture
def calculation_context():
    context = CalculationContext()

    context.set_variable("VAR10001", 100)

    context.set_parameter("PARAM11001", 0.80)
    context.set_parameter("PARAM12001", 2)
    context.set_parameter("PARAM12002", 10)

    return context


@pytest.fixture
def forecast_engine():
    return ForecastEngine()


# ============================================================
# VALID INTEGRATION
# ============================================================


def test_calculate_from_registry_validates_and_executes(
    forecast_engine,
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR11005",
            expression="VAR10001 * PARAM11001",
        )
    )

    results = forecast_engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=calculation_context,
    )

    assert results == {
        "EQ11001": 80.0,
    }

    assert calculation_context.get_variable("VAR11005") == 80.0


def test_calculate_from_registry_validates_dependency_chain(
    forecast_engine,
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ12003",
            target_variable_id="VAR12003",
            expression="VAR12001 + PARAM12002",
        )
    )

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR11005",
            expression="VAR10001 * PARAM11001",
        )
    )

    equation_registry.add(
        make_equation(
            equation_id="EQ12001",
            target_variable_id="VAR12001",
            expression="VAR11005 * PARAM12001",
        )
    )

    results = forecast_engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=calculation_context,
    )

    assert results == {
        "EQ11001": 80.0,
        "EQ12001": 160.0,
        "EQ12003": 170.0,
    }

    assert calculation_context.get_variable("VAR11005") == 80.0
    assert calculation_context.get_variable("VAR12001") == 160.0
    assert calculation_context.get_variable("VAR12003") == 170.0


# ============================================================
# INVALID VARIABLE REFERENCE
# ============================================================


def test_calculate_from_registry_rejects_missing_variable_reference(
    forecast_engine,
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR11005",
            expression="VAR99999 * PARAM11001",
        )
    )

    with pytest.raises(VariableReferenceNotFoundError):
        forecast_engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=calculation_context,
        )


# ============================================================
# INVALID PARAMETER REFERENCE
# ============================================================


def test_calculate_from_registry_rejects_missing_parameter_reference(
    forecast_engine,
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR11005",
            expression="VAR10001 * PARAM99999",
        )
    )

    with pytest.raises(ParameterReferenceNotFoundError):
        forecast_engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=calculation_context,
        )


# ============================================================
# INVALID TARGET VARIABLE
# ============================================================


def test_calculate_from_registry_rejects_missing_target_variable(
    forecast_engine,
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR99999",
            expression="VAR10001 * PARAM11001",
        )
    )

    with pytest.raises(TargetVariableNotFoundError):
        forecast_engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=calculation_context,
        )


# ============================================================
# VALIDATION MUST OCCUR BEFORE CALCULATION
# ============================================================


def test_registry_validation_happens_before_equation_execution(
    variable_registry,
    parameter_registry,
    calculation_context,
):
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            equation_id="EQ11001",
            target_variable_id="VAR11005",
            expression="VAR99999 * PARAM11001",
        )
    )

    forecast_engine = ForecastEngine()

    with pytest.raises(VariableReferenceNotFoundError):
        forecast_engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=calculation_context,
        )

    with pytest.raises(VariableNotFoundError):
        calculation_context.get_variable("VAR11005")
