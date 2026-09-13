from dataclasses import FrozenInstanceError

import pytest

from app.domain.variables.models import (
    Variable,
    VariableDefinition,
    VariableInstance,
)
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableInstanceRegistry,
)


def make_variable(**overrides):
    data = {
        "variable_id": "yield",
        "variable_name": "yield",
        "description": "Yield da linha",
        "unit": "g/l",
        "variable_type": "calculado",
        "frequency": "diário",
        "scope_type": "linha",
        "scope_value": "L1_L7",
        "source_reference": "Yield",
        "status": "ativo",
    }

    data.update(overrides)
    return Variable(**data)


def make_definition(**overrides):
    return VariableDefinition.from_variable(
        make_variable(**overrides)
    )


def test_variable_definition_preserves_identity():
    definition = make_definition()

    assert definition.variable_definition_id == "yield"
    assert definition.variable_name == "yield"


def test_variable_definition_preserves_metadata():
    definition = make_definition()

    assert definition.description == "Yield da linha"
    assert definition.unit == "g/l"
    assert definition.variable_type == "calculado"
    assert definition.frequency == "diário"
    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"
    assert definition.source_reference == "Yield"
    assert definition.status == "ativo"


def test_variable_definition_can_be_created_from_existing_variable():
    variable = make_variable()

    definition = VariableDefinition.from_variable(variable)

    assert definition.variable_definition_id == variable.variable_id
    assert definition.variable_name == variable.variable_name
    assert definition.description == variable.description
    assert definition.unit == variable.unit
    assert definition.variable_type == variable.variable_type
    assert definition.frequency == variable.frequency
    assert definition.scope_type == variable.scope_type
    assert definition.scope_value == variable.scope_value
    assert definition.source_reference == variable.source_reference
    assert definition.status == variable.status


def test_variable_definition_is_immutable():
    definition = make_definition()

    with pytest.raises(FrozenInstanceError):
        definition.variable_name = "new_name"


def test_variable_instance_references_definition():
    definition = make_definition()

    instance = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.variable_instance_id == "yield@L1"
    assert instance.variable_definition_id == "yield"
    assert instance.scope_type == "linha"
    assert instance.scope_value == "L1"


def test_variable_instance_can_have_multiple_scopes_from_same_definition():
    definition = make_definition()

    instance_l1 = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    instance_l2 = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L2",
    )

    assert instance_l1.variable_definition_id == "yield"
    assert instance_l2.variable_definition_id == "yield"

    assert instance_l1.variable_instance_id == "yield@L1"
    assert instance_l2.variable_instance_id == "yield@L2"

    assert instance_l1.variable_instance_id != instance_l2.variable_instance_id


def test_group_scope_creates_single_group_instance():
    definition = make_definition(
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    instance = VariableInstance.create(
        definition=definition,
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    assert instance.variable_instance_id == "yield@L1_L3"
    assert instance.variable_definition_id == "yield"
    assert instance.scope_type == "linha_grupo"
    assert instance.scope_value == "L1_L3"


def test_plant_scope_creates_single_plant_instance():
    definition = make_definition(
        scope_type="planta",
        scope_value="PLANTA",
    )

    instance = VariableInstance.create(
        definition=definition,
        scope_type="planta",
        scope_value="PLANTA",
    )

    assert instance.variable_instance_id == "yield@PLANTA"
    assert instance.variable_definition_id == "yield"
    assert instance.scope_type == "planta"
    assert instance.scope_value == "PLANTA"


def test_variable_instance_requires_scope_type():
    definition = make_definition()

    with pytest.raises(ValueError):
        VariableInstance.create(
            definition=definition,
            scope_type="",
            scope_value="L1",
        )


def test_variable_instance_requires_scope_value():
    definition = make_definition()

    with pytest.raises(ValueError):
        VariableInstance.create(
            definition=definition,
            scope_type="linha",
            scope_value="",
        )


def test_variable_definition_registry_rejects_duplicate_ids():
    registry = VariableDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    with pytest.raises(ValueError):
        registry.add(definition)


def test_variable_definition_registry_returns_definition():
    registry = VariableDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    result = registry.get("yield")

    assert result is definition


def test_variable_definition_registry_returns_all_definitions():
    registry = VariableDefinitionRegistry()

    definition_yield = make_definition(
        variable_id="yield",
        variable_name="yield",
    )

    definition_ltp = make_definition(
        variable_id="ltp",
        variable_name="ltp",
        unit="m³/h",
    )

    registry.add(definition_yield)
    registry.add(definition_ltp)

    definitions = registry.all()

    assert len(definitions) == 2
    assert definition_yield in definitions
    assert definition_ltp in definitions


def test_variable_instance_registry_rejects_duplicate_ids():
    registry = VariableInstanceRegistry()

    definition = make_definition()

    instance = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry.add(instance)

    with pytest.raises(ValueError):
        registry.add(instance)


def test_variable_instance_registry_returns_instance():
    registry = VariableInstanceRegistry()

    definition = make_definition()

    instance = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry.add(instance)

    result = registry.get("yield@L1")

    assert result is instance


def test_variable_instance_registry_returns_all_instances():
    registry = VariableInstanceRegistry()

    definition = make_definition()

    instance_l1 = VariableInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    instance_l2 = VariableInstance.create(
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
