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


# ============================================================
# Suporte a expressões condicionais (IfExp) — BD-07
# ============================================================


def test_if_expression_true_branch(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 100.0,
            "VAR12002": 50.0,
        }
    )

    result = evaluate(
        "VAR12001 if VAR12001 >= VAR12002 else VAR12002",
        context,
        parser,
    )

    assert result == 100.0


def test_if_expression_false_branch(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 10.0,
            "VAR12002": 50.0,
        }
    )

    result = evaluate(
        "VAR12001 if VAR12001 >= VAR12002 else VAR12002",
        context,
        parser,
    )

    assert result == 50.0


def test_if_expression_with_composite_branches(parser):
    context = CalculationContext(
        variables={
            "VAR12001": 20.0,
            "VAR12002": 3.0,
        }
    )

    result = evaluate(
        "VAR12001 * VAR12002 if VAR12001 > 10 else VAR12001 / VAR12002",
        context,
        parser,
    )

    assert result == 60.0

    context_false = CalculationContext(
        variables={
            "VAR12001": 6.0,
            "VAR12002": 3.0,
        }
    )

    result_false = evaluate(
        "VAR12001 * VAR12002 if VAR12001 > 10 else VAR12001 / VAR12002",
        context_false,
        parser,
    )

    assert result_false == 2.0


@pytest.mark.parametrize(
    "operator_symbol, left, right, expected_true",
    [
        (">", 10.0, 5.0, True),
        (">=", 5.0, 5.0, True),
        ("<", 3.0, 5.0, True),
        ("<=", 5.0, 5.0, True),
        ("==", 5.0, 5.0, True),
        ("!=", 5.0, 4.0, True),
    ],
)
def test_if_expression_relational_operators(
    parser, operator_symbol, left, right, expected_true,
):
    context = CalculationContext(
        variables={
            "VAR12001": left,
            "VAR12002": right,
        }
    )

    result = evaluate(
        f"1 if VAR12001 {operator_symbol} VAR12002 else 0",
        context,
        parser,
    )

    assert result == (1 if expected_true else 0)


def test_lth_equation_if_expression_matches_production_workbook(
    parser,
):
    """
    Regressão dedicada à equação real de `lth` (Production, BD-07):
    o piso (lth_meta) é aplicado somente quando o valor calculado
    fica abaixo dele -- sem simplificar a regra condicional.
    """

    context = CalculationContext(
        variables={
            "VAR12099": 900.0,
        },
        parameters={
            "PARAM12001": 1050.0,
        },
    )

    result = evaluate(
        "VAR12099 if VAR12099 >= PARAM12001 else PARAM12001",
        context,
        parser,
    )

    assert result == 1050.0

    context_above_floor = CalculationContext(
        variables={
            "VAR12099": 1200.0,
        },
        parameters={
            "PARAM12001": 1050.0,
        },
    )

    result_above_floor = evaluate(
        "VAR12099 if VAR12099 >= PARAM12001 else PARAM12001",
        context_above_floor,
        parser,
    )

    assert result_above_floor == 1200.0


# ============================================================
# Resolução temporal diário -> mensal (BD-02)
# ============================================================


def test_daily_equation_consumes_monthly_variable_via_containing_month():
    """
    `fator_ajuste_lth` (mensal) armazenado sob period_id="2026-09"
    deve ser resolvido por uma equação cujo period_id corrente é
    diário ("2026-09-14"), sem transformar a variável em diária.
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR12099",
        1.05,
        scope_type="linha",
        scope_value="L1",
        period_id="2026-09",
    )

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L1",
        default_period_id="2026-09-14",
    )

    tree = ExpressionParser().parse("VAR12099")

    assert evaluator.evaluate(tree) == 1.05


def test_daily_equation_prefers_exact_daily_value_over_month():
    """
    Quando existe um valor diário exato, ele tem prioridade sobre o
    fallback mensal (o fallback só age quando o valor exato não foi
    encontrado).
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR12099",
        1.05,
        scope_type="linha",
        scope_value="L1",
        period_id="2026-09",
    )
    context.set_variable_value(
        "VAR12099",
        9.99,
        scope_type="linha",
        scope_value="L1",
        period_id="2026-09-14",
    )

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L1",
        default_period_id="2026-09-14",
    )

    tree = ExpressionParser().parse("VAR12099")

    assert evaluator.evaluate(tree) == 9.99


def test_monthly_fallback_does_not_apply_to_monthly_consumer():
    """
    O fallback mensal só deriva um mês a partir de um period_id
    DIÁRIO (10 caracteres). Um consumidor já mensal (period_id
    "YYYY-MM") não deve tentar um "mês contendo o mês", e sim cair
    direto no fallback anual/sem período -- comportamento
    inalterado por esta decisão.
    """

    context = CalculationContext()

    context.set_variable_value(
        "VAR12099",
        7.0,
        scope_type="linha",
        scope_value="L1",
        period_id=None,
    )

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L1",
        default_period_id="2026-09",
    )

    tree = ExpressionParser().parse("VAR12099")

    assert evaluator.evaluate(tree) == 7.0


def test_monthly_fallback_raises_when_month_value_is_missing():
    from app.engine.exceptions import VariableNotFoundError

    context = CalculationContext()

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L1",
        default_period_id="2026-09-14",
    )

    tree = ExpressionParser().parse("VAR12099")

    with pytest.raises(VariableNotFoundError):
        evaluator.evaluate(tree)
