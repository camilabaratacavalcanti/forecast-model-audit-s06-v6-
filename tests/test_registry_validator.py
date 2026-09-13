import pytest

from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry
from app.engine.exceptions import (
    ParameterReferenceNotFoundError,
    TargetVariableNotFoundError,
    VariableReferenceNotFoundError,
)
from app.engine.registry_validator import RegistryIntegrityValidator


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
def validator():
    return RegistryIntegrityValidator()


# ============================================================
# TESTE 1 — EQUAÇÃO VÁLIDA
# ============================================================


def test_validate_equation_accepts_valid_references(
    validator,
    variable_registry,
    parameter_registry,
):
    equation = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    validator.validate_equation(
        equation=equation,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
    )


# ============================================================
# TESTE 2 — VARIÁVEL DA EXPRESSÃO INEXISTENTE
# ============================================================


def test_validate_equation_rejects_missing_variable_reference(
    validator,
    variable_registry,
    parameter_registry,
):
    equation = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR99999 * PARAM11001",
    )

    with pytest.raises(VariableReferenceNotFoundError):
        validator.validate_equation(
            equation=equation,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
        )


# ============================================================
# TESTE 3 — PARÂMETRO DA EXPRESSÃO INEXISTENTE
# ============================================================


def test_validate_equation_rejects_missing_parameter_reference(
    validator,
    variable_registry,
    parameter_registry,
):
    equation = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM99999",
    )

    with pytest.raises(ParameterReferenceNotFoundError):
        validator.validate_equation(
            equation=equation,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
        )


# ============================================================
# TESTE 4 — VARIÁVEL ALVO INEXISTENTE
# ============================================================


def test_validate_equation_rejects_missing_target_variable(
    validator,
    variable_registry,
    parameter_registry,
):
    equation = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR99999",
        expression="VAR10001 * PARAM11001",
    )

    with pytest.raises(TargetVariableNotFoundError):
        validator.validate_equation(
            equation=equation,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
        )


# ============================================================
# TESTE 5 — VÁRIAS REFERÊNCIAS VÁLIDAS
# ============================================================


def test_validate_equation_accepts_multiple_valid_references(
    validator,
    variable_registry,
    parameter_registry,
):
    equation = make_equation(
        equation_id="EQ12003",
        target_variable_id="VAR12003",
        expression="VAR12001 + VAR11005 + PARAM12001 + PARAM12002",
    )

    validator.validate_equation(
        equation=equation,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
    )


# ============================================================
# TESTE 6 — VALIDAR TODO O EQUATION REGISTRY
# ============================================================


def test_validate_registry_accepts_all_valid_equations(
    validator,
    variable_registry,
    parameter_registry,
):
    equation_registry = EquationRegistry()

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

    equation_registry.add(
        make_equation(
            equation_id="EQ12003",
            target_variable_id="VAR12003",
            expression="VAR12001 + PARAM12002",
        )
    )

    validator.validate_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
    )


# ============================================================
# TESTE 7 — REGISTRY COM EQUAÇÃO INVÁLIDA
# ============================================================


def test_validate_registry_rejects_invalid_equation(
    validator,
    variable_registry,
    parameter_registry,
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
        validator.validate_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
        )
