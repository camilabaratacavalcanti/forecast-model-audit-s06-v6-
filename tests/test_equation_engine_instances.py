"""
Objetivo:
    Validar a execução de EquationInstance utilizando a expressão
    pertencente à EquationDefinition e o contexto espacial da
    instância, sem duplicar a expressão matemática na Instance.
"""

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine


def test_equation_engine_calculates_equation_instance():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001@L4 * PARAM10001@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L4",
    )

    context = CalculationContext()

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

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 80


def test_equation_engine_uses_instance_scope():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001@L4 + PARAM10001@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance_l4 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L4",
    )

    instance_l5 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

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

    engine = EquationEngine()

    result_l4 = engine.calculate_instance(
        instance=instance_l4,
        definition=definition,
        calculation_context=context,
    )

    result_l5 = engine.calculate_instance(
        instance=instance_l5,
        definition=definition,
        calculation_context=context,
    )

    assert result_l4 == 110
    assert result_l5 == 220
