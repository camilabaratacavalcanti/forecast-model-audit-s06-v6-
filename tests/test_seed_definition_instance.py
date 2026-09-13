"""
Valida o fluxo Seed → Definition → Instance da plataforma de Forecast.

Os testes deste módulo verificam a materialização das definições e instâncias
de Variable, Parameter e Equation a partir dos seeds reais, além de garantir
que seeds inválidos sejam rejeitados pelo SeedLoader.
"""

from pathlib import Path

import pytest

from app.domain.equations.models import EquationInstance
from app.domain.parameters.models import ParameterInstance
from app.domain.variables.models import VariableDefinition
from app.domain.variables.models import VariableInstance
from app.engine.scope_resolver import ScopeResolver
from app.repositories.seed_loader import SeedLoader


SEED_ROOT = Path("data/seed")


def test_load_variable_definitions():
    loader = SeedLoader(SEED_ROOT)

    registry = loader.load_variable_definitions()

    definitions = registry.all()

    assert definitions

    assert all(
        isinstance(definition, VariableDefinition)
        for definition in definitions
    )


def test_variable_definition_identity():
    loader = SeedLoader(SEED_ROOT)

    registry = loader.load_variable_definitions()

    definitions = registry.all()

    assert definitions

    definition = definitions[0]

    assert definition.variable_definition_id
    assert definition.variable_name
    assert definition.description
    assert definition.unit
    assert definition.frequency
    assert definition.scope_type
    assert definition.scope_value
    assert definition.source_reference
    assert definition.status


def test_variable_definition_to_instances():
    loader = SeedLoader(SEED_ROOT)
    resolver = ScopeResolver()

    registry = loader.load_variable_definitions()

    definitions = registry.all()

    definition = next(
        definition
        for definition in definitions
        if definition.scope_type == "linha_grupo"
        and definition.scope_value == "L1_L3"
    )

    instances = resolver.resolve_variable(
        definition
    )

    assert len(instances) == 1

    instance = instances[0]

    assert (
        instance.variable_definition_id
        == definition.variable_definition_id
    )

    assert instance.scope_type == "linha_grupo"
    assert instance.scope_value == "L1_L3"

    assert (
        instance.variable_instance_id
        == f"{definition.variable_definition_id}@L1_L3"
    )


def test_parameter_seed_is_rejected(tmp_path):
    seed_root = tmp_path / "seed"
    production_root = seed_root / "production"

    production_root.mkdir(parents=True)

    parameter_seed = production_root / "parameters.json"

    parameter_seed.write_text(
        "{ invalid json }",
        encoding="utf-8",
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Parameter seed validation failed",
    ):
        loader.load_parameter_definitions()


def test_definition_preserves_seed_identity():
    loader = SeedLoader(SEED_ROOT)

    registry = loader.load_variable_definitions()

    definition = registry.all()[0]

    assert definition.variable_definition_id
    assert definition.variable_name
    assert definition.description
    assert definition.unit
    assert definition.frequency
    assert definition.source_reference
    assert definition.status


def test_load_variable_instances_from_seed():
    loader = SeedLoader(SEED_ROOT)

    definition_registry = (
        loader.load_variable_definitions()
    )

    instance_registry = (
        loader.load_variable_instances(
            definition_registry=definition_registry
        )
    )

    instances = instance_registry.all()

    assert instances

    assert all(
        isinstance(instance, VariableInstance)
        for instance in instances
    )


def test_load_parameter_instances_from_seed():
    loader = SeedLoader(SEED_ROOT)

    definition_registry = (
        loader.load_parameter_definitions()
    )

    instance_registry = (
        loader.load_parameter_instances(
            definition_registry=definition_registry
        )
    )

    instances = instance_registry.all()

    assert instances

    assert all(
        isinstance(instance, ParameterInstance)
        for instance in instances
    )


def test_load_equation_instances_from_seed():
    loader = SeedLoader(SEED_ROOT)

    definition_registry = (
        loader.load_equation_definitions()
    )

    instance_registry = (
        loader.load_equation_instances(
            definition_registry=definition_registry
        )
    )

    instances = instance_registry.all()

    assert instances

    assert all(
        isinstance(instance, EquationInstance)
        for instance in instances
    )


def test_load_all_definitions_and_instances():
    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions,
        variable_instances,
        parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loader.load_all_definitions_and_instances()

    assert variable_definitions.all()
    assert variable_instances.all()

    assert parameter_definitions.all()
    assert parameter_instances.all()

    assert equation_definitions.all()
    assert equation_instances.all()


def test_all_instances_reference_existing_definitions():
    loader = SeedLoader(SEED_ROOT)

    (
        variable_definitions,
        variable_instances,
        parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loader.load_all_definitions_and_instances()

    variable_definition_ids = {
        definition.variable_definition_id
        for definition in variable_definitions.all()
    }

    assert all(
        instance.variable_definition_id
        in variable_definition_ids
        for instance in variable_instances.all()
    )

    parameter_definition_keys = {
        (
            definition.parameter_definition_id,
            definition.version,
        )
        for definition in parameter_definitions.all()
    }

    assert all(
        (
            instance.parameter_definition_id,
            instance.version,
        )
        in parameter_definition_keys
        for instance in parameter_instances.all()
    )

    equation_definition_keys = {
        (
            definition.equation_definition_id,
            definition.version,
        )
        for definition in equation_definitions.all()
    }

    assert all(
        (
            instance.equation_definition_id,
            instance.version,
        )
        in equation_definition_keys
        for instance in equation_instances.all()
    )
