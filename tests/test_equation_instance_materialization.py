"""
Objetivo:
    Validar a materialização de EquationDefinition em EquationInstance,
    incluindo expansão de escopos de linha, preservação da definição
    original e geração determinística dos identificadores das instâncias.
"""


from app.domain.equations.models import EquationDefinition
from app.engine.scope_resolver import ScopeResolver


def test_materialize_line_range_into_equation_instances():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11002@L1 + PARAM11001",
        source_reference="TEST",
        status="PUBLISHED",
    )

    resolver = ScopeResolver()

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 7

    assert [instance.scope_value for instance in instances] == [
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
    ]


def test_materialized_instances_preserve_definition_identity():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=3,
        scope_type="linha",
        scope_value="L1_L3",
        expression="VAR11002@L1",
        source_reference="TEST",
        status="PUBLISHED",
    )

    resolver = ScopeResolver()

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 3

    for instance in instances:
        assert instance.equation_definition_id == "EQ11001"
        assert instance.version == 3
        assert instance.target_variable_id == "VAR11001"


def test_materialized_instance_ids_are_deterministic():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L3",
        expression="VAR11002@L1",
        source_reference="TEST",
        status="PUBLISHED",
    )

    resolver = ScopeResolver()

    instances = resolver.resolve_equation(definition)

    assert [instance.equation_instance_id for instance in instances] == [
        "EQ11001@v1@L1",
        "EQ11001@v1@L2",
        "EQ11001@v1@L3",
    ]


def test_single_scope_definition_creates_single_instance():
    definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11002@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    resolver = ScopeResolver()

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 1

    assert instances[0].scope_type == "linha"
    assert instances[0].scope_value == "L4"
    assert instances[0].equation_instance_id == "EQ11001@v1@L4"
