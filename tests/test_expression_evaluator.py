"""
Verifica a execução das ASTs: operações matemáticas, resolução de
variáveis/parâmetros e propagação/tratamento das exceções.
"""

import pytest

from app.engine.calculation_context import CalculationContext
# from app.engine.exceptions import EvaluationError
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.engine.exceptions import VariableNotFoundError
from app.engine.exceptions import (
    DivisionByZeroError,
    EvaluationError,
)


@pytest.fixture
def parser():
    return ExpressionParser()


def evaluate(expression, context, parser):
    tree = parser.parse(expression)

    evaluator = ExpressionEvaluator(context)

    return evaluator.evaluate(tree)


def test_addition(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
            "VAR12002": 50.0,
        }
    )

    result = evaluate(
        "VAR12001 + VAR12002",
        context,
        parser,
    )

    assert result == 150.0


def test_subtraction(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
            "VAR12002": 30.0,
        }
    )

    result = evaluate(
        "VAR12001 - VAR12002",
        context,
        parser,
    )

    assert result == 70.0


def test_multiplication(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        },
        parameters={
            "PARAM12001": 0.8,
        },
    )

    result = evaluate(
        "VAR12001 * PARAM12001",
        context,
        parser,
    )

    assert result == 80.0


def test_division(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        },
        parameters={
            "PARAM12001": 4.0,
        },
    )

    result = evaluate(
        "VAR12001 / PARAM12001",
        context,
        parser,
    )

    assert result == 25.0


def test_parentheses_respect_precedence(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
            "VAR12002": 5.0,
        },
        parameters={
            "PARAM12001": 2.0,
        },
    )

    result = evaluate(
        "(VAR12001 + VAR12002) * PARAM12001",
        context,
        parser,
    )

    assert result == 30.0


def test_operator_precedence(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
            "VAR12002": 5.0,
        }
    )

    result = evaluate(
        "VAR12001 + VAR12002 * 2",
        context,
        parser,
    )

    assert result == 20.0


def test_unary_minus(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
        }
    )

    result = evaluate(
        "-VAR12001",
        context,
        parser,
    )

    assert result == -10.0


def test_constant(parser):
    context = CalculationContext()

    result = evaluate(
        "100",
        context,
        parser,
    )

    assert result == 100


def test_power(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 4.0,
        }
    )

    result = evaluate(
        "VAR12001 ** 2",
        context,
        parser,
    )

    assert result == 16.0


def test_modulo(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
        }
    )

    result = evaluate(
        "VAR12001 % 3",
        context,
        parser,
    )

    assert result == 1.0


def test_missing_variable_propagates_error(parser):
    context = CalculationContext()

    with pytest.raises(VariableNotFoundError):
        evaluate(
            "VAR12001 + 10",
            context,
            parser,
        )


def test_division_by_zero_raises_specific_error(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        },
    )

    with pytest.raises(DivisionByZeroError) as exc_info:
        evaluate(
            "VAR12001 / 0",
            context,
            parser,
        )

    error = exc_info.value

    assert error.operation == "/"
    assert error.left_value == 100.0
    assert error.right_value == 0


def test_division_by_zero_remains_evaluation_error(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
        },
    )

    with pytest.raises(EvaluationError):
        evaluate(
            "VAR12001 / 0",
            context,
            parser,
        )


def test_modulo_by_zero_raises_specific_error(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
        },
    )

    with pytest.raises(DivisionByZeroError) as exc_info:
        evaluate(
            "VAR12001 % 0",
            context,
            parser,
        )

    error = exc_info.value

    assert error.operation == "%"
    assert error.left_value == 10.0
    assert error.right_value == 0


def test_evaluate_scoped_variable():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    evaluator = ExpressionEvaluator(context)

    tree = ExpressionParser().parse(
        "VAR11001@L4"
    )

    result = evaluator.evaluate(tree)

    assert result == 100.0


def test_evaluate_scoped_variable_uses_correct_scope():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_variable_value(
        "VAR11001",
        200.0,
        scope_type="linha",
        scope_value="L5",
    )

    evaluator = ExpressionEvaluator(context)
    parser = ExpressionParser()

    tree_l4 = parser.parse(
        "VAR11001@L4"
    )

    tree_l5 = parser.parse(
        "VAR11001@L5"
    )

    assert evaluator.evaluate(tree_l4) == 100.0
    assert evaluator.evaluate(tree_l5) == 200.0


def test_evaluate_scoped_parameter():
    context = CalculationContext()

    context.set_parameter_value(
        "PARAM11001",
        273.0,
        scope_type="linha",
        scope_value="L4",
    )

    evaluator = ExpressionEvaluator(context)

    tree = ExpressionParser().parse(
        "PARAM11001@L4"
    )

    result = evaluator.evaluate(tree)

    assert result == 273.0


def test_evaluate_scoped_expression():
    context = CalculationContext()

    context.set_variable_value(
        "VAR11001",
        100.0,
        scope_type="linha",
        scope_value="L4",
    )

    context.set_parameter_value(
        "PARAM11001",
        2.0,
        scope_type="linha",
        scope_value="L4",
    )

    evaluator = ExpressionEvaluator(context)

    tree = ExpressionParser().parse(
        "VAR11001@L4 * PARAM11001@L4"
    )

    result = evaluator.evaluate(tree)

    assert result == 200.0
