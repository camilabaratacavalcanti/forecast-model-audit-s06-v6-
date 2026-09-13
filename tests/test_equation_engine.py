"""
Testa o EquationEngine como unidade, verificando a integração entre parser,
contexto e evaluator.
"""


import pytest

from app.domain.equations.models import Equation

from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import (
    EquationEvaluationError,
    InvalidExpressionError,
    UnsafeExpressionError,
)


@pytest.fixture
def engine():
    return EquationEngine()


def create_equation(expression):
    return Equation(
        equation_id="EQ12001",
        target_variable_id="VAR12003",
        version=1,
        scope_type="linha",
        scope_value="L1",
        expression=expression,
        source_reference="NovoOficial!D152:O152",
        status="PUBLISHED",
    )


def test_engine_calculates_equation(engine):
    equation = create_equation(
        "VAR12001 * PARAM12001"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 1200.0


def test_engine_calculates_complex_expression(engine):
    equation = create_equation(
        "(VAR12001 + VAR12002) * PARAM12001"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1000.0,
            "VAR12002": 500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 1200.0


def test_engine_accepts_constant_expression(engine):
    equation = create_equation(
        "100"
    )

    context = CalculationContext()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 100


def test_engine_rejects_invalid_expression(engine):
    equation = create_equation(
        "VAR12001 +"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        }
    )

    with pytest.raises(InvalidExpressionError):
        engine.calculate(
            equation,
            context,
        )


def test_engine_rejects_unsafe_expression(engine):
    equation = create_equation(
        "__import__('os')"
    )

    context = CalculationContext()

    with pytest.raises(UnsafeExpressionError):
        engine.calculate(
            equation,
            context,
        )


def test_engine_wraps_division_by_zero_with_equation_context(engine):
    equation = create_equation(
        "VAR12001 / 0"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        }
    )

    with pytest.raises(EquationEvaluationError) as exc_info:
        engine.calculate(
            equation,
            context,
        )

    error = exc_info.value

    assert error.equation_id == "EQ12001"
    assert error.target_variable_id == "VAR12003"
    assert error.expression == "VAR12001 / 0"


def test_engine_preserves_original_evaluation_error(engine):
    equation = create_equation(
        "VAR12001 / 0"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        }
    )

    with pytest.raises(EquationEvaluationError) as exc_info:
        engine.calculate(
            equation,
            context,
        )

    error = exc_info.value

    assert error.original_error.operation == "/"
    assert error.original_error.left_value == 100.0
    assert error.original_error.right_value == 0


def test_engine_evaluation_error_contains_useful_message(engine):
    equation = create_equation(
        "VAR12001 / 0"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        }
    )

    with pytest.raises(EquationEvaluationError) as exc_info:
        engine.calculate(
            equation,
            context,
        )

    message = str(exc_info.value)

    assert "EQ12001" in message
    assert "VAR12003" in message
    assert "VAR12001 / 0" in message


def test_engine_evaluates_scoped_variable():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    equation = Equation(
        equation_id="EQ11001",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11001@L4 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 200.0


def test_engine_evaluates_correct_scoped_value():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_variable_value(
        "VAR11001",
        150.0,
        scope_type="linha",
        scope_value="L5",
    )

    equation_l4 = Equation(
        equation_id="EQ11001",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11001@L4 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    equation_l5 = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L5",
        expression="VAR11001@L5 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    engine = EquationEngine()

    assert engine.calculate(
        equation_l4,
        context,
    ) == 200.0

    assert engine.calculate(
        equation_l5,
        context,
    ) == 300.0


def test_engine_evaluates_scoped_expression():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_variable_value(
        "VAR11002",
        50.0,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_parameter_value(
        "PARAM11001",
        2.0,
        scope_type="linha",
        scope_value="L4",
    )

    equation = Equation(
        equation_id="EQ11003",
        target_variable_id="VAR11003",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression=(
            "(VAR11001@L4 + VAR11002@L4)"
            " * PARAM11001@L4"
        ),
        source_reference="TEST",
        status="APPROVED",
    )

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 300.0
