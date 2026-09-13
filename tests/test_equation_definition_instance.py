from dataclasses import FrozenInstanceError, fields

import pytest

from app.domain.equations.models import (
    Equation,
    EquationDefinition,
    EquationInstance,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationInstanceRegistry,
)


def make_equation(**overrides):
    data = {
        "equation_id": "yield_daily",
        "target_variable_id": "yield",
        "version": 1,
        "scope_type": "linha",
        "scope_value": "L1_L7",
        "expression": (
            "(ltp_a_c - ratio_spent) * ltp_tc "
            "- 0.654 * sl_solids"
        ),
        "source_reference": "Yield",
        "status": "ativo",
    }

    data.update(overrides)

    return Equation(**data)


def make_definition(**overrides):
    return EquationDefinition.from_equation(
        make_equation(**overrides)
    )


def test_equation_definition_preserves_identity():
    definition = make_definition()

    assert definition.equation_definition_id == "yield_daily"
    assert definition.target_variable_id == "yield"
    assert definition.version == 1


def test_equation_definition_preserves_target_variable():
    definition = make_definition()

    assert definition.target_variable_id == "yield"


def test_equation_definition_preserves_expression():
    definition = make_definition()

    assert (
        definition.expression
        == "(ltp_a_c - ratio_spent) * ltp_tc "
        "- 0.654 * sl_solids"
    )


def test_equation_definition_preserves_metadata():
    definition = make_definition()

    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"
    assert definition.expression == (
        "(ltp_a_c - ratio_spent) * ltp_tc "
        "- 0.654 * sl_solids"
    )
    assert definition.source_reference == "Yield"
    assert definition.status == "ativo"


def test_equation_definition_can_be_created_from_existing_equation():
    equation = make_equation()

    definition = EquationDefinition.from_equation(equation)

    assert definition.equation_definition_id == equation.equation_id
    assert definition.target_variable_id == equation.target_variable_id
    assert definition.version == equation.version
    assert definition.scope_type == equation.scope_type
    assert definition.scope_value == equation.scope_value
    assert definition.expression == equation.expression
    assert definition.source_reference == equation.source_reference
    assert definition.status == equation.status


def test_equation_definition_has_no_frequency():
    field_names = {
        field.name
        for field in fields(EquationDefinition)
    }

    assert "frequency" not in field_names


def test_equation_definition_is_immutable():
    definition = make_definition()

    with pytest.raises(FrozenInstanceError):
        definition.expression = "different_expression"


def test_equation_instance_references_definition():
    definition = make_definition()

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.equation_instance_id == "yield_daily@v1@L1"
    assert instance.equation_definition_id == "yield_daily"
    assert instance.target_variable_id == "yield"
    assert instance.scope_type == "linha"
    assert instance.scope_value == "L1"


def test_equation_instance_does_not_duplicate_expression():
    instance_field_names = {
        field.name
        for field in fields(EquationInstance)
    }

    assert "expression" not in instance_field_names


def test_equation_instance_can_have_multiple_scopes_from_same_definition():
    definition = make_definition()

    instance_l1 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    instance_l2 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L2",
    )

    assert instance_l1.equation_definition_id == "yield_daily"
    assert instance_l2.equation_definition_id == "yield_daily"

    assert instance_l1.equation_instance_id == "yield_daily@v1@L1"
    assert instance_l2.equation_instance_id == "yield_daily@v1@L2"

    assert instance_l1.equation_instance_id != instance_l2.equation_instance_id


def test_group_scope_creates_single_equation_group_instance():
    definition = make_definition(
        equation_id="yield_group_daily",
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    assert instance.equation_instance_id == "yield_group_daily@v1@L1_L3"
    assert instance.equation_definition_id == "yield_group_daily"
    assert instance.version == 1
    assert instance.scope_type == "linha_grupo"
    assert instance.scope_value == "L1_L3"


def test_plant_scope_creates_single_equation_plant_instance():
    definition = make_definition(
        equation_id="yield_plant",
        scope_type="planta",
        scope_value="PLANTA",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="planta",
        scope_value="PLANTA",
    )

    assert instance.equation_instance_id == "yield_plant@v1@PLANTA"
    assert instance.equation_definition_id == "yield_plant"
    assert instance.version == 1
    assert instance.scope_type == "planta"
    assert instance.scope_value == "PLANTA"


def test_equation_instance_requires_scope_type():
    definition = make_definition()

    with pytest.raises(ValueError):
        EquationInstance.create(
            definition=definition,
            scope_type="",
            scope_value="L1",
        )


def test_equation_instance_requires_scope_value():
    definition = make_definition()

    with pytest.raises(ValueError):
        EquationInstance.create(
            definition=definition,
            scope_type="linha",
            scope_value="",
        )


def test_equation_definition_registry_rejects_duplicate_ids():
    registry = EquationDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    with pytest.raises(ValueError):
        registry.add(definition)


def test_equation_definition_registry_returns_definition():
    registry = EquationDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    result = registry.get("yield_daily")

    assert result is definition


def test_equation_definition_registry_returns_all_definitions():
    registry = EquationDefinitionRegistry()

    definition_yield = make_definition(
        equation_id="yield_daily",
    )

    definition_ltp = make_definition(
        equation_id="ltp_daily",
        target_variable_id="ltp",
        expression="lth * ltp_lth",
    )

    registry.add(definition_yield)
    registry.add(definition_ltp)

    definitions = registry.all()

    assert len(definitions) == 2
    assert definition_yield in definitions
    assert definition_ltp in definitions


def test_equation_instance_registry_rejects_duplicate_ids():
    registry = EquationInstanceRegistry()

    definition = make_definition()

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry.add(instance)

    with pytest.raises(ValueError):
        registry.add(instance)


def test_equation_instance_registry_returns_instance():
    registry = EquationInstanceRegistry()

    definition = make_definition()

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry.add(instance)

    result = registry.get("yield_daily@v1@L1")

    assert result is instance


def test_equation_instance_registry_returns_all_instances():
    registry = EquationInstanceRegistry()

    definition = make_definition()

    instance_l1 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    instance_l2 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(instance_l1)
    registry.add(instance_l2)

    instances = registry.all()

    assert len(instances) == 2
    assert instance_l1 in instances
    assert instance_l2 in instances
