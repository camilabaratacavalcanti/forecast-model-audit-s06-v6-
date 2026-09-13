import pytest

from app.domain.equations.models import Equation
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver
from app.engine.exceptions import DependencyCycleError


def make_equation(
    equation_id,
    target_variable_id,
    expression,
):
    return Equation(
        equation_id=equation_id,
        target_variable_id=target_variable_id,
        version=1,
        scope_type="linha",
        scope_value="L1",
        expression=expression,
        source_reference="test",
        status="PUBLISHED",
    )


def build_graph(
    equations,
    variable_producers,
):
    extractor = DependencyExtractor()
    graph = DependencyGraph()

    for equation in equations:
        graph.add_equation(
            equation,
            variable_producers,
            extractor,
        )

    return graph


def test_detects_two_equation_cycle():
    equation_1 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR12002",
    )

    equation_2 = make_equation(
        equation_id="EQ12002",
        target_variable_id="VAR12002",
        expression="VAR12001",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR12001": "EQ12001",
            "VAR12002": "EQ12002",
        },
    )

    resolver = DependencyResolver()

    with pytest.raises(
        DependencyCycleError,
    ) as exc_info:
        resolver.resolve(graph)

    assert exc_info.value.cycle == (
        "EQ12001",
        "EQ12002",
        "EQ12001",
    )


def test_detects_three_equation_cycle():
    equation_1 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR12002",
    )

    equation_2 = make_equation(
        equation_id="EQ12002",
        target_variable_id="VAR12002",
        expression="VAR12003",
    )

    equation_3 = make_equation(
        equation_id="EQ12003",
        target_variable_id="VAR12003",
        expression="VAR12001",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
            equation_3,
        ],
        variable_producers={
            "VAR12001": "EQ12001",
            "VAR12002": "EQ12002",
            "VAR12003": "EQ12003",
        },
    )

    resolver = DependencyResolver()

    with pytest.raises(
        DependencyCycleError,
    ) as exc_info:
        resolver.resolve(graph)

    assert exc_info.value.cycle == (
        "EQ12001",
        "EQ12002",
        "EQ12003",
        "EQ12001",
    )


def test_cycle_error_contains_readable_message():
    equation_1 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR12002",
    )

    equation_2 = make_equation(
        equation_id="EQ12002",
        target_variable_id="VAR12002",
        expression="VAR12001",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR12001": "EQ12001",
            "VAR12002": "EQ12002",
        },
    )

    resolver = DependencyResolver()

    with pytest.raises(
        DependencyCycleError,
    ) as exc_info:
        resolver.resolve(graph)

    assert str(exc_info.value) == (
        "Ciclo de dependências detectado: "
        "EQ12001 → EQ12002 → EQ12001"
    )


def test_detects_cycle_inside_larger_graph():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR12002",
    )

    equation_3 = make_equation(
        equation_id="EQ12002",
        target_variable_id="VAR12002",
        expression="VAR12001",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
            equation_3,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
            "VAR12002": "EQ12002",
        },
    )

    resolver = DependencyResolver()

    with pytest.raises(
        DependencyCycleError,
    ) as exc_info:
        resolver.resolve(graph)

    assert exc_info.value.cycle == (
        "EQ12001",
        "EQ12002",
        "EQ12001",
    )


def test_acyclic_graph_does_not_raise_cycle_error():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
        },
    )

    resolver = DependencyResolver()

    result = resolver.resolve(
        graph,
    )

    assert result == (
        "EQ11001",
        "EQ12001",
    )
