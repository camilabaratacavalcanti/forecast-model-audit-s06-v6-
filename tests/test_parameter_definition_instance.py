from dataclasses import FrozenInstanceError

import pytest

from app.domain.parameters.models import (
    Parameter,
    ParameterDefinition,
    ParameterInstance,
)
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterInstanceRegistry,
)


def make_parameter(**overrides):
    data = {
        "parameter_id": "ratio_spent_base",
        "parameter_name": "ratio_spent_base",
        "description": "Valor base do ratio spent",
        "unit": "-",
        "value": 1.0,
        "version": 1,
        "scope_type": "linha",
        "scope_value": "L1_L7",
        "source_reference": "Yield",
        "status": "ativo",
    }

    data.update(overrides)

    return Parameter(**data)


def make_definition(**overrides):
    parameter = make_parameter(**overrides)

    return ParameterDefinition.from_parameter(parameter)


def test_parameter_definition_preserves_metadata():
    definition = make_definition()

    assert definition.parameter_definition_id == "ratio_spent_base"
    assert definition.parameter_name == "ratio_spent_base"
    assert definition.description == "Valor base do ratio spent"
    assert definition.unit == "-"
    assert definition.value == 1.0
    assert definition.version == 1
    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"
    assert definition.source_reference == "Yield"
    assert definition.status == "ativo"


def test_parameter_definition_can_be_created_from_existing_parameter():
    parameter = make_parameter()

    definition = ParameterDefinition.from_parameter(parameter)

    assert definition.parameter_definition_id == parameter.parameter_id
    assert definition.parameter_name == parameter.parameter_name
    assert definition.description == parameter.description
    assert definition.unit == parameter.unit
    assert definition.value == parameter.value
    assert definition.version == parameter.version
    assert definition.scope_type == parameter.scope_type
    assert definition.scope_value == parameter.scope_value
    assert definition.source_reference == parameter.source_reference
    assert definition.status == parameter.status


def test_parameter_definition_is_frozen():
    definition = make_definition()

    with pytest.raises(FrozenInstanceError):
        definition.value = 2.0


def test_parameter_definition_has_no_parameter_type():
    definition = make_definition()

    assert not hasattr(definition, "parameter_type")


def test_parameter_instance_can_be_created_from_definition():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.parameter_definition_id == (
        definition.parameter_definition_id
    )
    assert instance.scope_type == "linha"
    assert instance.scope_value == "L1"


def test_parameter_instance_copies_value_from_definition():
    definition = make_definition(value=1.25)

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.value == 1.25


def test_parameter_instance_copies_version_from_definition():
    definition = make_definition(version=3)

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.version == 3


def test_parameter_instance_builds_expected_id():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance.parameter_instance_id == (
        "ratio_spent_base@v1@L1"
    )


def test_parameter_instance_id_changes_with_version():
    definition_v1 = make_definition(version=1)
    definition_v2 = make_definition(version=2)

    instance_v1 = ParameterInstance.create(
        definition=definition_v1,
        scope_type="linha",
        scope_value="L1",
    )

    instance_v2 = ParameterInstance.create(
        definition=definition_v2,
        scope_type="linha",
        scope_value="L1",
    )

    assert instance_v1.parameter_instance_id != (
        instance_v2.parameter_instance_id
    )


def test_parameter_instance_is_frozen():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    with pytest.raises(FrozenInstanceError):
        instance.value = 2.0


def test_parameter_instance_requires_scope_type():
    definition = make_definition()

    with pytest.raises(ValueError):
        ParameterInstance.create(
            definition=definition,
            scope_type="",
            scope_value="L1",
        )


def test_parameter_instance_requires_scope_value():
    definition = make_definition()

    with pytest.raises(ValueError):
        ParameterInstance.create(
            definition=definition,
            scope_type="linha",
            scope_value="",
        )


def test_parameter_definition_registry_accepts_definition():
    registry = ParameterDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    assert registry.all() == [definition]


def test_parameter_definition_registry_returns_definition():
    registry = ParameterDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    result = registry.get("ratio_spent_base")

    assert result == definition


def test_parameter_definition_registry_supports_exact_lookup():
    registry = ParameterDefinitionRegistry()

    definition = make_definition(
        version=2,
        scope_type="linha",
        scope_value="L1_L7",
    )

    registry.add(definition)

    result = registry.get(
        "ratio_spent_base",
        version=2,
        scope_type="linha",
        scope_value="L1_L7",
    )

    assert result == definition


def test_parameter_definition_registry_distinguishes_versions():
    registry = ParameterDefinitionRegistry()

    definition_v1 = make_definition(version=1)
    definition_v2 = make_definition(version=2)

    registry.add(definition_v1)
    registry.add(definition_v2)

    assert registry.get(
        "ratio_spent_base",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
    ) == definition_v1

    assert registry.get(
        "ratio_spent_base",
        version=2,
        scope_type="linha",
        scope_value="L1_L7",
    ) == definition_v2


def test_parameter_definition_registry_distinguishes_scopes():
    registry = ParameterDefinitionRegistry()

    line_definition = make_definition(
        scope_type="linha",
        scope_value="L1_L7",
    )

    group_definition = make_definition(
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    registry.add(line_definition)
    registry.add(group_definition)

    assert registry.get(
        "ratio_spent_base",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
    ) == line_definition

    assert registry.get(
        "ratio_spent_base",
        version=1,
        scope_type="linha_grupo",
        scope_value="L1_L3",
    ) == group_definition


def test_parameter_definition_registry_rejects_duplicate_definition():
    registry = ParameterDefinitionRegistry()

    definition = make_definition()

    registry.add(definition)

    with pytest.raises(ValueError):
        registry.add(definition)


def test_parameter_definition_registry_rejects_ambiguous_lookup():
    registry = ParameterDefinitionRegistry()

    definition_v1 = make_definition(version=1)
    definition_v2 = make_definition(version=2)

    registry.add(definition_v1)
    registry.add(definition_v2)

    with pytest.raises(ValueError):
        registry.get("ratio_spent_base")


def test_parameter_definition_registry_raises_key_error():
    registry = ParameterDefinitionRegistry()

    with pytest.raises(KeyError):
        registry.get(
            "parameter_inexistente",
            version=1,
            scope_type="linha",
            scope_value="L1_L7",
        )


def test_parameter_instance_registry_accepts_instance():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry = ParameterInstanceRegistry()

    registry.add(instance)

    assert registry.all() == [instance]


def test_parameter_instance_registry_returns_instance():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry = ParameterInstanceRegistry()

    registry.add(instance)

    result = registry.get(
        "ratio_spent_base@v1@L1"
    )

    assert result == instance


def test_parameter_instance_registry_rejects_duplicate_instance():
    definition = make_definition()

    instance = ParameterInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L1",
    )

    registry = ParameterInstanceRegistry()

    registry.add(instance)

    with pytest.raises(ValueError):
        registry.add(instance)
