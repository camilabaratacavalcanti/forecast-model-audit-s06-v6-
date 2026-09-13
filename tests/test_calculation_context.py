"""
Verifica armazenamento, recuperação e comportamento de ausência
de valores no CalculationContext.
"""


import pytest

from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    CalculationValueError,
    ParameterNotFoundError,
    VariableNotFoundError,
)
from app.domain.parameters.models import ParameterInstance
from app.domain.variables.models import VariableInstance


def test_get_variable_value():
    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        }
    )

    assert context.get_variable("VAR12001") == 1500.0


def test_get_parameter_value():
    context = CalculationContext(
        parameters={
            "PARAM12001": 0.85,
        }
    )

    assert context.get_parameter("PARAM12001") == 0.85


def test_missing_variable_raises_error():
    context = CalculationContext()

    with pytest.raises(VariableNotFoundError):
        context.get_variable("VAR12001")


def test_missing_parameter_raises_error():
    context = CalculationContext()

    with pytest.raises(ParameterNotFoundError):
        context.get_parameter("PARAM12001")


def test_set_variable():
    context = CalculationContext()

    context.set_variable(
        "VAR12001",
        100.0,
    )

    assert context.get_variable("VAR12001") == 100.0


def test_set_parameter():
    context = CalculationContext()

    context.set_parameter(
        "PARAM12001",
        0.75,
    )

    assert context.get_parameter("PARAM12001") == 0.75


def test_boolean_variable_value_is_rejected():
    with pytest.raises(CalculationValueError):
        CalculationContext(
            variables={
                "VAR12001": True,
            }
        )


def test_boolean_parameter_value_is_rejected():
    with pytest.raises(CalculationValueError):
        CalculationContext(
            parameters={
                "PARAM12001": False,
            }
        )


def test_non_numeric_variable_value_is_rejected():
    with pytest.raises(CalculationValueError):
        CalculationContext(
            variables={
                "VAR12001": "100",
            }
        )


def test_non_numeric_parameter_value_is_rejected():
    with pytest.raises(CalculationValueError):
        CalculationContext(
            parameters={
                "PARAM12001": "0.85",
            }
        )


def test_context_stores_variable_by_scope_and_period():
    context = CalculationContext()

    context.set_variable_value(
        variable_id="VAR12001",
        value=100.0,
        scope_type="linha",
        scope_value="L1",
        period_id="2026-01",
    )

    assert context.get_variable_value(
        variable_id="VAR12001",
        scope_type="linha",
        scope_value="L1",
        period_id="2026-01",
    ) == 100.0


def test_context_distinguishes_variable_values_by_scope():
    context = CalculationContext()

    context.set_variable_value(
        "VAR12001",
        100.0,
        "linha",
        "L1",
        "2026-01",
    )

    context.set_variable_value(
        "VAR12001",
        200.0,
        "linha",
        "L2",
        "2026-01",
    )

    assert context.get_variable_value(
        "VAR12001",
        "linha",
        "L1",
        "2026-01",
    ) == 100.0

    assert context.get_variable_value(
        "VAR12001",
        "linha",
        "L2",
        "2026-01",
    ) == 200.0


def test_context_distinguishes_variable_values_by_period():
    context = CalculationContext()

    context.set_variable_value(
        "VAR12001",
        100.0,
        "linha",
        "L1",
        "2026-01",
    )

    context.set_variable_value(
        "VAR12001",
        120.0,
        "linha",
        "L1",
        "2026-02",
    )

    assert context.get_variable_value(
        "VAR12001",
        "linha",
        "L1",
        "2026-01",
    ) == 100.0

    assert context.get_variable_value(
        "VAR12001",
        "linha",
        "L1",
        "2026-02",
    ) == 120.0


def test_context_stores_parameter_by_scope_and_period():
    context = CalculationContext()

    context.set_parameter_value(
        parameter_id="PARAM12001",
        value=0.80,
        scope_type="linha",
        scope_value="L1",
        period_id="2026-01",
    )

    assert context.get_parameter_value(
        parameter_id="PARAM12001",
        scope_type="linha",
        scope_value="L1",
        period_id="2026-01",
    ) == 0.80


def test_missing_contextual_variable_raises_error():
    context = CalculationContext()

    with pytest.raises(VariableNotFoundError):
        context.get_variable_value(
            "VAR12001",
            "linha",
            "L1",
            "2026-01",
        )


def test_missing_contextual_parameter_raises_error():
    context = CalculationContext()

    with pytest.raises(ParameterNotFoundError):
        context.get_parameter_value(
            "PARAM12001",
            "linha",
            "L1",
            "2026-01",
        )


def test_contextual_boolean_variable_is_rejected():
    context = CalculationContext()

    with pytest.raises(CalculationValueError):
        context.set_variable_value(
            "VAR12001",
            True,
            "linha",
            "L1",
            "2026-01",
        )


def test_contextual_non_numeric_parameter_is_rejected():
    context = CalculationContext()

    with pytest.raises(CalculationValueError):
        context.set_parameter_value(
            "PARAM12001",
            "0.80",
            "linha",
            "L1",
            "2026-01",
        )


def test_context_stores_variable_instance_value():
    instance = VariableInstance(
        variable_instance_id="VAR12001@L1",
        variable_definition_id="VAR12001",
        scope_type="linha",
        scope_value="L1",
    )

    context = CalculationContext()

    context.set_variable_instance_value(
        instance,
        100.0,
        period_id="2026-01",
    )

    assert context.get_variable_instance_value(
        instance,
        period_id="2026-01",
    ) == 100.0


def test_context_distinguishes_variable_instances_by_scope():
    instance_l1 = VariableInstance(
        variable_instance_id="VAR12001@L1",
        variable_definition_id="VAR12001",
        scope_type="linha",
        scope_value="L1",
    )

    instance_l2 = VariableInstance(
        variable_instance_id="VAR12001@L2",
        variable_definition_id="VAR12001",
        scope_type="linha",
        scope_value="L2",
    )

    context = CalculationContext()

    context.set_variable_instance_value(
        instance_l1,
        100.0,
        period_id="2026-01",
    )

    context.set_variable_instance_value(
        instance_l2,
        200.0,
        period_id="2026-01",
    )

    assert context.get_variable_instance_value(
        instance_l1,
        period_id="2026-01",
    ) == 100.0

    assert context.get_variable_instance_value(
        instance_l2,
        period_id="2026-01",
    ) == 200.0


def test_context_stores_parameter_instance_value():
    instance = ParameterInstance(
        parameter_instance_id="PARAM12001@L1",
        parameter_definition_id="PARAM12001",
        version=1,
        scope_type="linha",
        scope_value="L1",
        value=0.80,
    )

    context = CalculationContext()

    context.set_parameter_instance_value(
        instance,
        0.80,
        period_id="2026-01",
    )

    assert context.get_parameter_instance_value(
        instance,
        period_id="2026-01",
    ) == 0.80


def test_context_missing_variable_instance_raises_error():
    instance = VariableInstance(
        variable_instance_id="VAR12001@L1",
        variable_definition_id="VAR12001",
        scope_type="linha",
        scope_value="L1",
    )

    context = CalculationContext()

    with pytest.raises(VariableNotFoundError):
        context.get_variable_instance_value(
            instance,
            period_id="2026-01",
        )


def test_context_missing_parameter_instance_raises_error():
    instance = ParameterInstance(
        parameter_instance_id="PARAM12001@L1",
        parameter_definition_id="PARAM12001",
        version=1,
        scope_type="linha",
        scope_value="L1",
        value=0.80,
    )

    context = CalculationContext()

    with pytest.raises(ParameterNotFoundError):
        context.get_parameter_instance_value(
            instance,
            period_id="2026-01",
        )


def test_context_variable_instance_rejects_boolean():
    instance = VariableInstance(
        variable_instance_id="VAR12001@L1",
        variable_definition_id="VAR12001",
        scope_type="linha",
        scope_value="L1",
    )

    context = CalculationContext()

    with pytest.raises(CalculationValueError):
        context.set_variable_instance_value(
            instance,
            True,
            period_id="2026-01",
        )


def test_context_parameter_instance_rejects_non_numeric():
    instance = ParameterInstance(
        parameter_instance_id="PARAM12001@L1",
        parameter_definition_id="PARAM12001",
        version=1,
        scope_type="linha",
        scope_value="L1",
        value=0.80,
    )

    context = CalculationContext()

    with pytest.raises(CalculationValueError):
        context.set_parameter_instance_value(
            instance,
            "0.80",
            period_id="2026-01",
        )
