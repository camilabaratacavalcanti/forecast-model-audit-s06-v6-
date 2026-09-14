"""
Objetivo (FASE 3A pós-code-review — Partes D e F):
    Provar, de ponta a ponta, o contrato de scope definitivamente
    aprovado:

        linha / L1                 -> válido
        linha / L7                 -> válido
        linha_grupo / L1_L7        -> válido
        área / None                -> válido (não é erro)
        global / None               -> válido (não é erro)
        combinações inválidas       -> continuam rejeitadas

    Cobre ScopeResolver, os três seed validators
    (Variable/Parameter/Equation), a materialização em Instance
    (Definition -> Instance, sem crash) e a validação de
    compatibilidade Definition -> Target Scope
    (RegistryIntegrityValidator), reutilizando o componente já
    existente em vez de duplicar lógica de escopo.
"""

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.parameters.models import ParameterDefinition
from app.domain.parameters.registry import ParameterDefinitionRegistry
from app.domain.variables.models import VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.exceptions import EquationTargetScopeMismatchError
from app.engine.registry_validator import RegistryIntegrityValidator
from app.engine.scope_resolver import ScopeResolver
from app.validation import equation_seed_validator as esv
from app.validation import parameter_seed_validator as psv
from app.validation import variable_seed_validator as vsv


VALID_SCOPE_COMBINATIONS = [
    ("linha", "L1"),
    ("linha", "L7"),
    ("linha_grupo", "L1_L7"),
    ("área", None),
    ("global", None),
]

INVALID_SCOPE_COMBINATIONS = [
    ("linha", None),
    ("linha", "L8"),
    ("linha", "L1_L3"),
    ("linha_grupo", "L1"),
    ("linha_grupo", None),
    ("área", "L1"),
    ("global", "L1"),
    ("planta", "L1"),
]

# ScopeResolver é um resolvedor genérico de faixas de linha, mais
# permissivo do que os seed validators quanto ao "shape" de
# scope_value: "linha"/"L1_L3" resolve normalmente para [L1, L2, L3]
# (qualquer subintervalo de 1 a 7 é uma faixa de linha válida), ainda
# que o ENUM restrito dos seed validators só aceite L1..L7 e L1_L7
# para "linha" (L1_L3 é reservado para "linha_grupo" na convenção de
# negócio). Por isso o ScopeResolver usa sua própria lista de
# combinações inválidas, sem essa exceção estrutural.
SCOPE_RESOLVER_INVALID_COMBINATIONS = [
    combo
    for combo in INVALID_SCOPE_COMBINATIONS
    if combo != ("linha", "L1_L3")
]


# ============================================================
# D — ScopeResolver
# ============================================================


@pytest.mark.parametrize("scope_type,scope_value", VALID_SCOPE_COMBINATIONS)
def test_scope_resolver_accepts_valid_combination(scope_type, scope_value):
    resolver = ScopeResolver()

    result = resolver.resolve_scopes(
        scope_type=scope_type,
        scope_value=scope_value,
    )

    assert len(result) >= 1
    assert all(scope_type == pair[0] for pair in result)


@pytest.mark.parametrize(
    "scope_type,scope_value", SCOPE_RESOLVER_INVALID_COMBINATIONS
)
def test_scope_resolver_rejects_invalid_combination(scope_type, scope_value):
    resolver = ScopeResolver()

    with pytest.raises(ValueError):
        resolver.resolve_scopes(
            scope_type=scope_type,
            scope_value=scope_value,
        )


def test_scope_resolver_treats_linha_l1_l3_as_a_valid_subrange():
    """
    Documenta explicitamente a permissividade intencional do
    ScopeResolver: diferente dos seed validators (cujo enum restrito
    reserva L1_L3/L4_L5/L6_L7 para "linha_grupo"), o ScopeResolver
    resolve qualquer subintervalo de linha bem formado para
    scope_type="linha", incluindo "L1_L3".
    """

    resolver = ScopeResolver()

    result = resolver.resolve_scopes(
        scope_type="linha",
        scope_value="L1_L3",
    )

    assert result == [
        ("linha", "L1"),
        ("linha", "L2"),
        ("linha", "L3"),
    ]


# ============================================================
# D — Definition -> Instance (materialização real, sem crash)
# ============================================================


def test_variable_definition_area_materializes_to_single_instance():
    resolver = ScopeResolver()

    definition = VariableDefinition(
        variable_definition_id="VARX",
        variable_name="x",
        description="x",
        unit="-",
        variable_type="entrada",
        frequency="diário",
        scope_type="área",
        scope_value=None,
        source_reference="test",
        status="ativo",
    )

    instances = resolver.resolve_variable(definition)

    assert len(instances) == 1
    assert instances[0].scope_type == "área"
    assert instances[0].scope_value is None


def test_parameter_definition_global_materializes_to_single_instance():
    resolver = ScopeResolver()

    definition = ParameterDefinition(
        parameter_definition_id="PARAMX",
        parameter_name="x",
        description="x",
        unit="-",
        value=1.0,
        version=1,
        scope_type="global",
        scope_value=None,
        source_reference="test",
        status="ativo",
    )

    instances = resolver.resolve_parameter(definition)

    assert len(instances) == 1
    assert instances[0].scope_type == "global"
    assert instances[0].scope_value is None
    assert instances[0].value == 1.0


def test_equation_definition_global_materializes_to_single_instance():
    resolver = ScopeResolver()

    definition = EquationDefinition(
        equation_definition_id="EQX",
        target_variable_id="VARX",
        version=1,
        scope_type="global",
        scope_value=None,
        expression="1",
        source_reference="test",
        status="PUBLISHED",
    )

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 1
    assert instances[0].scope_type == "global"
    assert instances[0].scope_value is None


# ============================================================
# D — Seed validators (Variable / Parameter / Equation)
# ============================================================


def make_variable_dict(scope_type, scope_value):
    return {
        "variable_id": "VAR11200",
        "variable_name": "x",
        "description": "x",
        "unit": "-",
        "variable_type": "entrada",
        "frequency": "diário",
        "scope_type": scope_type,
        "scope_value": scope_value,
        "source_reference": "test",
        "status": "ativo",
        "_block": "yield",
    }


def make_parameter_dict(scope_type, scope_value):
    return {
        "parameter_id": "PARAM11200",
        "parameter_name": "x",
        "description": "x",
        "unit": "-",
        "value": 1.0,
        "version": 1,
        "scope_type": scope_type,
        "scope_value": scope_value,
        "source_reference": "test",
        "status": "ativo",
    }


def make_equation_dict(scope_type, scope_value):
    return {
        "equation_id": "EQ11200",
        "target_variable_id": "VAR11200",
        "version": 1,
        "scope_type": scope_type,
        "scope_value": scope_value,
        "expression": "1",
        "source_reference": "test",
        "status": "PUBLISHED",
    }


@pytest.mark.parametrize("scope_type,scope_value", VALID_SCOPE_COMBINATIONS)
def test_variable_validator_accepts_valid_combination(scope_type, scope_value):
    variable = make_variable_dict(scope_type, scope_value)

    assert vsv.validate_enum_values([variable]) == []
    assert vsv.validate_scope_consistency([variable]) == []
    assert vsv.validate_scope_type_value_combination([variable]) == []


@pytest.mark.parametrize(
    "scope_type,scope_value", INVALID_SCOPE_COMBINATIONS
)
def test_variable_validator_rejects_invalid_combination(scope_type, scope_value):
    variable = make_variable_dict(scope_type, scope_value)

    errors = (
        vsv.validate_enum_values([variable])
        + vsv.validate_scope_consistency([variable])
        + vsv.validate_scope_type_value_combination([variable])
    )

    assert errors != []


@pytest.mark.parametrize("scope_type,scope_value", VALID_SCOPE_COMBINATIONS)
def test_parameter_validator_accepts_valid_combination(scope_type, scope_value):
    parameter = make_parameter_dict(scope_type, scope_value)

    assert (
        psv.validate_enum_values(parameter, "test.json") == []
    )
    assert (
        psv.validate_scope_consistency(parameter, "test.json") == []
    )
    assert (
        psv.validate_scope_values(parameter, "test.json") == []
    )


@pytest.mark.parametrize(
    "scope_type,scope_value", INVALID_SCOPE_COMBINATIONS
)
def test_parameter_validator_rejects_invalid_combination(scope_type, scope_value):
    parameter = make_parameter_dict(scope_type, scope_value)

    errors = (
        psv.validate_enum_values(parameter, "test.json")
        + psv.validate_scope_consistency(parameter, "test.json")
        + psv.validate_scope_values(parameter, "test.json")
    )

    assert errors != []


@pytest.mark.parametrize("scope_type,scope_value", VALID_SCOPE_COMBINATIONS)
def test_equation_validator_accepts_valid_combination(scope_type, scope_value):
    equation = make_equation_dict(scope_type, scope_value)

    assert esv.validate_enum_values([equation]) == []
    assert esv.validate_scope_consistency([equation]) == []


@pytest.mark.parametrize(
    "scope_type,scope_value", INVALID_SCOPE_COMBINATIONS
)
def test_equation_validator_rejects_invalid_combination(scope_type, scope_value):
    equation = make_equation_dict(scope_type, scope_value)

    errors = (
        esv.validate_enum_values([equation])
        + esv.validate_scope_consistency([equation])
    )

    assert errors != []


# ============================================================
# F — Definition -> Target Scope (RegistryIntegrityValidator)
# ============================================================


def test_f1_linha_to_linha_is_valid():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            "linha", "L1", "test", "ativo",
        )
    )

    equation = EquationDefinition(
        "EQ11200", "VAR11200", 1, "linha", "L1", "1", "test",
        "PUBLISHED",
    )

    validator.validate_definition(
        definition=equation,
        variable_definition_registry=variable_registry,
    )


def test_f2_linha_l1_l7_to_compatible_definition_is_valid():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            "linha", "L1_L7", "test", "ativo",
        )
    )

    equation = EquationDefinition(
        "EQ11200", "VAR11200", 1, "linha", "L1_L7", "1", "test",
        "PUBLISHED",
    )

    validator.validate_definition(
        definition=equation,
        variable_definition_registry=variable_registry,
    )


def test_f3_incompatible_scope_is_rejected():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            "linha_grupo", "L1_L3", "test", "ativo",
        )
    )

    equation = EquationDefinition(
        "EQ11200", "VAR11200", 1, "linha", "L1_L7", "1", "test",
        "PUBLISHED",
    )

    with pytest.raises(EquationTargetScopeMismatchError):
        validator.validate_definition(
            definition=equation,
            variable_definition_registry=variable_registry,
        )


def test_f4_missing_target_is_rejected():
    from app.engine.exceptions import TargetVariableNotFoundError

    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()

    equation = EquationDefinition(
        "EQ11200", "VAR99999", 1, "linha", "L1", "1", "test",
        "PUBLISHED",
    )

    with pytest.raises(TargetVariableNotFoundError):
        validator.validate_definition(
            definition=equation,
            variable_definition_registry=variable_registry,
        )


@pytest.mark.parametrize("scope_type", ["área", "global"])
def test_f5_scopeless_target_scope_is_respected(scope_type):
    """
    Uma equação declarada em escopo área/global só é compatível com
    uma variável alvo também declarada em área/global (com
    scope_value=None em ambos) — a comparação de escopo continua
    funcionando com None de ambos os lados, sem exigir nenhum valor
    artificial no lugar de None.
    """

    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            scope_type, None, "test", "ativo",
        )
    )

    equation = EquationDefinition(
        "EQ11200", "VAR11200", 1, scope_type, None, "1", "test",
        "PUBLISHED",
    )

    validator.validate_definition(
        definition=equation,
        variable_definition_registry=variable_registry,
    )


def test_f5_scopeless_mismatch_between_area_and_global_is_rejected():
    validator = RegistryIntegrityValidator()

    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            "área", None, "test", "ativo",
        )
    )

    equation = EquationDefinition(
        "EQ11200", "VAR11200", 1, "global", None, "1", "test",
        "PUBLISHED",
    )

    with pytest.raises(EquationTargetScopeMismatchError):
        validator.validate_definition(
            definition=equation,
            variable_definition_registry=variable_registry,
        )


# ============================================================
# F — Integração real: Definition Registries reais, sem mocks
# ============================================================


def test_f_integration_validate_definition_registry_real_flow():
    variable_registry = VariableDefinitionRegistry()
    variable_registry.add(
        VariableDefinition(
            "VAR11200", "x", "x", "-", "calculado", "diário",
            "linha", "L1_L7", "test", "ativo",
        )
    )
    variable_registry.add(
        VariableDefinition(
            "VAR11201", "y", "y", "-", "calculado", "diário",
            "área", None, "test", "ativo",
        )
    )

    parameter_registry = ParameterDefinitionRegistry()
    parameter_registry.add(
        ParameterDefinition(
            "PARAM11200", "p", "p", "-", 1.0, 1,
            "global", None, "test", "ativo",
        )
    )

    equation_registry = EquationDefinitionRegistry()
    equation_registry.add(
        EquationDefinition(
            "EQ11200", "VAR11200", 1, "linha", "L1_L7",
            "PARAM11200 * 2", "test", "PUBLISHED",
        )
    )
    equation_registry.add(
        EquationDefinition(
            "EQ11201", "VAR11201", 1, "área", None,
            "PARAM11200 + 1", "test", "PUBLISHED",
        )
    )

    validator = RegistryIntegrityValidator()

    validator.validate_definition_registry(
        equation_definition_registry=equation_registry,
        variable_definition_registry=variable_registry,
        parameter_definition_registry=parameter_registry,
    )
