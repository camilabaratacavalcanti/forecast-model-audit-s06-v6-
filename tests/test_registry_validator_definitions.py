"""
Objetivo:
    Validar a checagem de compatibilidade de escopo entre uma
    EquationDefinition e a VariableDefinition alvo, e a validação
    de referências de variáveis/parâmetros na expressão contra os
    Definition Registries (aprovado na FASE 3A, item 5).
"""

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.parameters.models import ParameterDefinition
from app.domain.parameters.registry import ParameterDefinitionRegistry
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.exceptions import (
    EquationTargetScopeMismatchError,
    ParameterReferenceNotFoundError,
    TargetVariableNotFoundError,
    VariableReferenceNotFoundError,
)
from app.engine.registry_validator import RegistryIntegrityValidator


def make_variable_definition(
    variable_definition_id="VAR11001",
    scope_type="linha",
    scope_value="L1_L7",
):
    return VariableDefinition(
        variable_definition_id=variable_definition_id,
        variable_name="yield",
        description="Yield",
        unit="g/l",
        variable_type="calculado",
        frequency="diário",
        scope_type=scope_type,
        scope_value=scope_value,
        source_reference="test",
        status="ativo",
    )


def make_equation_definition(
    target_variable_id="VAR11001",
    scope_type="linha",
    scope_value="L1_L7",
    expression="VAR10002 * 2",
):
    return EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id=target_variable_id,
        version=1,
        scope_type=scope_type,
        scope_value=scope_value,
        expression=expression,
        source_reference="test",
        status="PUBLISHED",
    )


def test_validate_definition_accepts_matching_scope():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())
    variable_registry.add(
        make_variable_definition(variable_definition_id="VAR10002")
    )

    equation_definition = make_equation_definition()

    validator.validate_definition(
        definition=equation_definition,
        variable_definition_registry=variable_registry,
    )


def test_validate_definition_rejects_scope_mismatch():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        make_variable_definition(
            scope_type="linha_grupo",
            scope_value="L1_L3",
        )
    )
    variable_registry.add(
        make_variable_definition(variable_definition_id="VAR10002")
    )

    equation_definition = make_equation_definition(
        scope_type="linha",
        scope_value="L1_L7",
    )

    with pytest.raises(EquationTargetScopeMismatchError):
        validator.validate_definition(
            definition=equation_definition,
            variable_definition_registry=variable_registry,
        )


def test_validate_definition_rejects_missing_target_variable():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()

    equation_definition = make_equation_definition(
        target_variable_id="VAR99999",
    )

    with pytest.raises(TargetVariableNotFoundError):
        validator.validate_definition(
            definition=equation_definition,
            variable_definition_registry=variable_registry,
        )


def test_validate_definition_rejects_missing_variable_reference():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())

    equation_definition = make_equation_definition(
        expression="VAR99999 * 2",
    )

    with pytest.raises(VariableReferenceNotFoundError):
        validator.validate_definition(
            definition=equation_definition,
            variable_definition_registry=variable_registry,
        )


def test_validate_definition_accepts_scoped_reference_by_base_id():
    """
    Uma referência explicitamente escopada (ex.: "VAR10002@L1")
    deve ser validada pelo seu ID base, sem exigir que a
    VariableDefinitionRegistry tenha uma entrada por escopo
    concreto.
    """

    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())
    variable_registry.add(
        make_variable_definition(variable_definition_id="VAR10002")
    )

    equation_definition = make_equation_definition(
        expression="VAR10002@L1 + VAR10002@L2",
    )

    validator.validate_definition(
        definition=equation_definition,
        variable_definition_registry=variable_registry,
    )


def test_validate_definition_accepts_parameter_reference_with_multiple_scopes():
    """
    Parâmetros como "tanque_base" podem ter várias
    ParameterDefinitions (uma por linha) sob o mesmo
    parameter_definition_id. A referência da equação deve ser
    aceita mesmo quando a busca por ID puro é ambígua.
    """

    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())

    parameter_registry = ParameterDefinitionRegistry()

    for scope_value, value in (
        ("L1", 14),
        ("L2", 14),
    ):
        parameter_registry.add(
            ParameterDefinition(
                parameter_definition_id="PARAM11003",
                parameter_name="tanque_base",
                description="Tanque base",
                unit="-",
                value=value,
                version=1,
                scope_type="linha",
                scope_value=scope_value,
                source_reference="test",
                status="ativo",
            )
        )

    equation_definition = make_equation_definition(
        expression="PARAM11003 * 2",
    )

    validator.validate_definition(
        definition=equation_definition,
        variable_definition_registry=variable_registry,
        parameter_definition_registry=parameter_registry,
    )


def test_validate_definition_rejects_missing_parameter_reference():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())

    parameter_registry = ParameterDefinitionRegistry()

    equation_definition = make_equation_definition(
        expression="PARAM99999 * 2",
    )

    with pytest.raises(ParameterReferenceNotFoundError):
        validator.validate_definition(
            definition=equation_definition,
            variable_definition_registry=variable_registry,
            parameter_definition_registry=parameter_registry,
        )


def test_validate_definition_registry_iterates_all_definitions():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(make_variable_definition())
    variable_registry.add(
        make_variable_definition(variable_definition_id="VAR10002")
    )

    equation_registry = EquationDefinitionRegistry()
    equation_registry.add(make_equation_definition())

    validator.validate_definition_registry(
        equation_definition_registry=equation_registry,
        variable_definition_registry=variable_registry,
    )
