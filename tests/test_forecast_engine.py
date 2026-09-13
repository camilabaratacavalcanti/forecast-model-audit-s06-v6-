import pytest

from app.engine.exceptions import DependencyCycleError

from app.domain.equations.models import Equation
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine


def make_equation(
    equation_id,
    target_variable_id,
    expression,
):
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


def test_forecast_engine_calculates_single_equation():
    equation = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    context = CalculationContext(
        variables={
            "VAR11005": 100,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    engine = ForecastEngine()

    results = engine.calculate(
        equations=[equation],
        variable_producers={
            "VAR12001": "EQ12001",
        },
        calculation_context=context,
    )

    assert results == {
        "EQ12001": 80,
    }

    assert context.get_variable(
        "VAR12001",
    ) == 80


def test_forecast_engine_calculates_equations_in_dependency_order():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    equation_3 = make_equation(
        equation_id="EQ12003",
        target_variable_id="VAR12003",
        expression="VAR12001 + PARAM12002",
    )

    context = CalculationContext(
        variables={
            "VAR10001": 100,
        },
        parameters={
            "PARAM11001": 0.80,
            "PARAM12001": 2,
            "PARAM12002": 10,
        },
    )

    engine = ForecastEngine()

    results = engine.calculate(
        equations=[
            equation_3,
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
            "VAR12003": "EQ12003",
        },
        calculation_context=context,
    )

    assert results == {
        "EQ11001": 80,
        "EQ12001": 160,
        "EQ12003": 170,
    }

    assert context.get_variable(
        "VAR11005",
    ) == 80

    assert context.get_variable(
        "VAR12001",
    ) == 160

    assert context.get_variable(
        "VAR12003",
    ) == 170


def test_forecast_engine_calculates_branching_dependencies():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_2 = make_equation(
        equation_id="EQ11002",
        target_variable_id="VAR11006",
        expression="VAR10002 * PARAM11002",
    )

    equation_3 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 + VAR11006",
    )

    context = CalculationContext(
        variables={
            "VAR10001": 100,
            "VAR10002": 50,
        },
        parameters={
            "PARAM11001": 0.80,
            "PARAM11002": 2,
        },
    )

    engine = ForecastEngine()

    results = engine.calculate(
        equations=[
            equation_3,
            equation_2,
            equation_1,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR11006": "EQ11002",
            "VAR12001": "EQ12001",
        },
        calculation_context=context,
    )

    assert results == {
        "EQ11001": 80,
        "EQ11002": 100,
        "EQ12001": 180,
    }

    assert context.get_variable(
        "VAR12001",
    ) == 180


def test_forecast_engine_does_not_depend_on_input_equation_order():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 + 10",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * 2",
    )

    context = CalculationContext(
        variables={
            "VAR10001": 100,
        },
        parameters={},
    )

    engine = ForecastEngine()

    results = engine.calculate(
        equations=[
            equation_2,
            equation_1,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
        },
        calculation_context=context,
    )

    assert results == {
        "EQ11001": 110,
        "EQ12001": 220,
    }


def test_forecast_engine_rejects_dependency_cycle():
    equation_1 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR12002",
    )

    equation_2 = make_equation(
        equation_id="EQ12002",
        target_variable_id="VAR12002",
        expression="VAR12001",
    )

    context = CalculationContext(
        variables={},
        parameters={},
    )

    engine = ForecastEngine()

    with pytest.raises(
        DependencyCycleError,
    ):
        engine.calculate(
            equations=[
                equation_1,
                equation_2,
            ],
            variable_producers={
                "VAR12001": "EQ12001",
                "VAR12002": "EQ12002",
            },
            calculation_context=context,
        )


def test_forecast_engine_stores_intermediate_results_in_context():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 + 10",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 + 20",
    )

    context = CalculationContext(
        variables={
            "VAR10001": 100,
        },
        parameters={},
    )

    engine = ForecastEngine()

    engine.calculate(
        equations=[
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
        },
        calculation_context=context,
    )

    assert context.get_variable(
        "VAR11005",
    ) == 110

    assert context.get_variable(
        "VAR12001",
    ) == 130
