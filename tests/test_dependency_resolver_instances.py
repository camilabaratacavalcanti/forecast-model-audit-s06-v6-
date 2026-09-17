"""
Objetivo:
    Validar a resolução da ordem de execução de EquationInstances
    contextualizadas, garantindo que as dependências de cada escopo
    sejam respeitadas sem mistura entre instâncias.
"""

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver


def test_dependency_resolver_orders_equation_instances_by_dependency():
    producer_definition = EquationDefinition(
        equation_definition_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="100",
        source_reference="TEST",
        status="PUBLISHED",
    )

    consumer_definition = EquationDefinition(
        equation_definition_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR11001@L4",
        source_reference="TEST",
        status="PUBLISHED",
    )

    producer_instance = EquationInstance.create(
        definition=producer_definition,
        scope_type="linha",
        scope_value="L4",
    )

    consumer_instance = EquationInstance.create(
        definition=consumer_definition,
        scope_type="linha",
        scope_value="L4",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=producer_instance,
        definition=producer_definition,
        variable_producers={},
        extractor=DependencyExtractor(),
    )

    graph.add_instance(
        instance=consumer_instance,
        definition=consumer_definition,
        variable_producers={
            "VAR11001@L4": "EQ11001@v1@L4",
        },
        extractor=DependencyExtractor(),
    )

    resolver = DependencyResolver()

    execution_order = resolver.resolve(graph)

    assert execution_order.index(
        "EQ11001@v1@L4"
    ) < execution_order.index(
        "EQ11002@linha:L4"
    )


def test_dependency_resolver_preserves_instance_isolation():
    """
    A expressão usa uma referência SEM escopo explícito
    ("VAR11001") — a forma correta de expressar "o produtor desta
    mesma linha" em uma Definition materializada por linha.
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

    resolver = DependencyResolver()

    execution_order = resolver.resolve(graph)

    assert execution_order.index(
        "EQ11001@v1@L4"
    ) < execution_order.index(
        "EQ11002@linha:L4"
    )

    assert execution_order.index(
        "EQ11001@v1@L5"
    ) < execution_order.index(
        "EQ11002@linha:L5"
    )
