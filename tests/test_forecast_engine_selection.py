"""
Objetivo:
    Validar a integração entre ForecastEngine e EquationSelector,
    garantindo que a seleção de equações seja delegada ao componente
    responsável por versão, status e escopo.
"""

import pytest

from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.engine.equation_selector import EquationSelector
from app.engine.forecast_engine import ForecastEngine


def make_equation(
    equation_id: str,
    version: int,
    expression: str,
    scope_type: str | None = "linha",
    scope_value: str | None = "L1",
    status: str = "PUBLISHED",
) -> Equation:
    return Equation(
        equation_id=equation_id,
        target_variable_id="VAR11005",
        version=version,
        scope_type=scope_type,
        scope_value=scope_value,
        expression=expression,
        source_reference="test",
        status=status,
    )


def test_forecast_engine_delegates_equation_selection():
    registry = EquationRegistry()

    equation = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    registry.add(equation)

    selector = EquationSelector(registry)

    engine = ForecastEngine(
        equation_selector=selector,
    )

    result = engine.select_equation(
        equation_id="EQ11001",
    )

    assert result == equation


def test_forecast_engine_selects_highest_published_version():
    registry = EquationRegistry()

    equation_v1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    equation_v2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
    )

    registry.add(equation_v1)
    registry.add(equation_v2)

    selector = EquationSelector(registry)

    engine = ForecastEngine(
        equation_selector=selector,
    )

    result = engine.select_equation(
        equation_id="EQ11001",
    )

    assert result == equation_v2
    assert result.version == 2


def test_forecast_engine_selects_equation_by_scope():
    """
    Valida que o ForecastEngine encaminha corretamente os parâmetros
    de escopo ao EquationSelector.
    """

    registry = EquationRegistry()

    equation_l1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
        scope_type="linha",
        scope_value="L1",
    )

    equation_l2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(equation_l1)
    registry.add(equation_l2)

    selector = EquationSelector(registry)

    engine = ForecastEngine(
        equation_selector=selector,
    )

    result = engine.select_equation(
        equation_id="EQ11001",
        scope_type="linha",
        scope_value="L2",
    )

    assert result == equation_l2
    assert result.scope_type == "linha"
    assert result.scope_value == "L2"


def test_forecast_engine_propagates_unknown_equation_error():
    registry = EquationRegistry()

    selector = EquationSelector(registry)

    engine = ForecastEngine(
        equation_selector=selector,
    )

    with pytest.raises(ValueError):
        engine.select_equation(
            equation_id="EQ99999",
        )
