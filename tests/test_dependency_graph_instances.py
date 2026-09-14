"""
Objetivo:
    Validar a construção do DependencyGraph a partir de
    EquationDefinition e EquationInstance, preservando o
    contexto espacial da instância e a expressão matemática
    pertencente à definição.
"""

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph


def test_dependency_graph_accepts_equation_instance_with_definition():
    definition = EquationDefinition(
        equation_definition_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11001@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L4",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR11001@L4": "EQ11001@v1@L4",
        },
        extractor=DependencyExtractor(),
    )

    assert (
        "EQ11002@linha:L4"
        in graph.get_equations()
    )


def test_dependency_graph_preserves_instance_scope():
    definition = EquationDefinition(
        equation_definition_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11001@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L4",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR11001@L4": "EQ11001@v1@L4",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies(
        "EQ11002@linha:L4"
    )

    assert dependencies == {
        "EQ11001@v1@L4"
    }


def test_dependency_graph_does_not_mix_line_instances():
    """
    A expressão usa uma referência SEM escopo explícito
    ("VAR11001"): essa é a forma correta de expressar "o produtor
    desta mesma linha" em uma Definition materializada por linha, e
    deve ser contextualizada por instance sem misturar L4 e L5. Uma
    referência explícita (ex.: "VAR11001@L4") NÃO deve ser
    reinterpretada — ver
    test_dependency_graph_never_rewrites_explicit_scoped_reference.
    """

    definition = EquationDefinition(
        equation_definition_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11001",
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

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance_l4,
        definition=definition,
        variable_producers={
            "VAR11001@L4": "EQ11001@v1@L4",
            "VAR11001@L5": "EQ11001@v1@L5",
        },
        extractor=DependencyExtractor(),
    )

    graph.add_instance(
        instance=instance_l5,
        definition=definition,
        variable_producers={
            "VAR11001@L4": "EQ11001@v1@L4",
            "VAR11001@L5": "EQ11001@v1@L5",
        },
        extractor=DependencyExtractor(),
    )

    assert graph.get_dependencies(
        "EQ11002@linha:L4"
    ) == {
        "EQ11001@v1@L4"
    }

    assert graph.get_dependencies(
        "EQ11002@linha:L5"
    ) == {
        "EQ11001@v1@L5"
    }


def test_dependency_graph_never_rewrites_explicit_scoped_reference():
    """
    Cenário C.4 do contrato aprovado: para uma equação materializada
    em L5 (scope_type "linha"), cuja expressão referencia
    explicitamente L2 e L3, o grafo NÃO pode gerar uma dependência
    "VAR10001@L5" — deve preservar exatamente "VAR10001@L2" e
    "VAR10001@L3", mesmo essa instance sendo, ela própria, L5.
    """

    definition = EquationDefinition(
        equation_definition_id="EQ_A",
        target_variable_id="VAR_A",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001@L2 + VAR10001@L3",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance_l5 = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance_l5,
        definition=definition,
        variable_producers={
            "VAR10001@L2": "EQ_PROD@v1@L2",
            "VAR10001@L3": "EQ_PROD@v1@L3",
            "VAR10001@L5": "EQ_PROD@v1@L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies(
        "EQ_A@linha:L5"
    )

    assert dependencies == {
        "EQ_PROD@v1@L2",
        "EQ_PROD@v1@L3",
    }

    assert "EQ_PROD@v1@L5" not in dependencies
