import pytest

from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver
from app.engine.exceptions import DependencyCycleError
from app.domain.equations.models import Equation


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


# ============================================================
# TESTE 1 — EQUAÇÃO ÚNICA
# ============================================================


def test_resolve_single_equation():
    equation = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005",
    )

    graph = build_graph(
        equations=[equation],
        variable_producers={
            "VAR12001": "EQ12001",
        },
    )

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ12001",
    )


# ============================================================
# TESTE 2 — DUAS EQUAÇÕES EM CADEIA
# ============================================================


def test_resolve_two_equation_chain():
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

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001",
        "EQ12001",
    )


# ============================================================
# TESTE 3 — CADEIA DE TRÊS EQUAÇÕES
# ============================================================


def test_resolve_three_equation_chain():
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
            "VAR11005": "EQ11001",
            "VAR12001": "EQ12001",
            "VAR12003": "EQ12003",
        },
    )

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001",
        "EQ12001",
        "EQ12003",
    )


# ============================================================
# TESTE 4 — DUAS EQUAÇÕES INDEPENDENTES
# ============================================================


def test_resolve_independent_equations_deterministically():
    equation_1 = make_equation(
        equation_id="EQ11002",
        target_variable_id="VAR11006",
        expression="VAR10002",
    )

    equation_2 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR11006": "EQ11002",
        },
    )

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001",
        "EQ11002",
    )


# ============================================================
# TESTE 5 — DEPENDÊNCIAS EM RAMIFICAÇÃO
# ============================================================


def test_resolve_branching_dependencies():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001",
    )

    equation_2 = make_equation(
        equation_id="EQ11002",
        target_variable_id="VAR11006",
        expression="VAR10002",
    )

    equation_3 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 + VAR11006",
    )

    graph = build_graph(
        equations=[
            equation_1,
            equation_2,
            equation_3,
        ],
        variable_producers={
            "VAR11005": "EQ11001",
            "VAR11006": "EQ11002",
            "VAR12001": "EQ12001",
        },
    )

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001",
        "EQ11002",
        "EQ12001",
    )


# ============================================================
# TESTE 6 — CICLO DE DEPENDÊNCIAS
# ============================================================


def test_resolve_detects_dependency_cycle():
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

    with pytest.raises(DependencyCycleError):
        resolver.resolve(graph)


def test_resolver_handles_contextualized_dependency_chain():
    graph = DependencyGraph()

    graph._dependencies = {
        "EQ11003@linha:L4": {
            "EQ11002@linha:L4",
        },
        "EQ11002@linha:L4": {
            "EQ11001@linha:L4",
        },
        "EQ11001@linha:L4": set(),
    }

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001@linha:L4",
        "EQ11002@linha:L4",
        "EQ11003@linha:L4",
    )


def test_resolver_keeps_line_dependencies_independent():
    graph = DependencyGraph()

    graph._dependencies = {
        "EQ11002@linha:L4": {
            "EQ11001@linha:L4",
        },
        "EQ11001@linha:L4": set(),
        "EQ11002@linha:L5": {
            "EQ11001@linha:L5",
        },
        "EQ11001@linha:L5": set(),
    }

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001@linha:L4",
        "EQ11001@linha:L5",
        "EQ11002@linha:L4",
        "EQ11002@linha:L5",
    )


def test_resolver_detects_contextualized_cycle():
    graph = DependencyGraph()

    graph._dependencies = {
        "EQ11001@linha:L4": {
            "EQ11003@linha:L4",
        },
        "EQ11002@linha:L4": {
            "EQ11001@linha:L4",
        },
        "EQ11003@linha:L4": {
            "EQ11002@linha:L4",
        },
    }

    resolver = DependencyResolver()

    with pytest.raises(DependencyCycleError) as exc_info:
        resolver.resolve(graph)

    assert exc_info.value.cycle == (
        "EQ11001@linha:L4",
        "EQ11003@linha:L4",
        "EQ11002@linha:L4",
        "EQ11001@linha:L4",
    )


def test_resolver_detects_cycle_without_confusing_other_scope():
    graph = DependencyGraph()

    graph._dependencies = {
        "EQ11001@linha:L4": {
            "EQ11002@linha:L4",
        },
        "EQ11002@linha:L4": {
            "EQ11001@linha:L4",
        },
        "EQ11003@linha:L5": {
            "EQ11004@linha:L5",
        },
        "EQ11004@linha:L5": set(),
    }

    resolver = DependencyResolver()

    with pytest.raises(DependencyCycleError) as exc_info:
        resolver.resolve(graph)

    assert all(
        "@linha:L4" in equation_id
        for equation_id in exc_info.value.cycle
    )


def test_graph_and_resolver_work_with_scoped_equations():
    extractor = DependencyExtractor()
    graph = DependencyGraph()

    equation_1 = Equation(
        equation_id="EQ11001",
        target_variable_id="VAR11001",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR10001",
        source_reference="TEST",
        status="APPROVED",
    )

    equation_2 = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11001@L4 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    equation_3 = Equation(
        equation_id="EQ11003",
        target_variable_id="VAR11003",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11002@L4 + 10",
        source_reference="TEST",
        status="APPROVED",
    )

    variable_producers = {
        "VAR11001@L4": "EQ11001@linha:L4",
        "VAR11002@L4": "EQ11002@linha:L4",
        "VAR11003@L4": "EQ11003@linha:L4",
    }

    graph.add_equation(
        equation_1,
        variable_producers,
        extractor,
    )

    graph.add_equation(
        equation_2,
        variable_producers,
        extractor,
    )

    graph.add_equation(
        equation_3,
        variable_producers,
        extractor,
    )

    resolver = DependencyResolver()

    result = resolver.resolve(graph)

    assert result == (
        "EQ11001@linha:L4",
        "EQ11002@linha:L4",
        "EQ11003@linha:L4",
    )
