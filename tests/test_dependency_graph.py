from app.domain.equations.models import Equation
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph


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


# ============================================================
# TESTE 1 — EQUAÇÃO SEM DEPENDÊNCIA ENTRE EQUAÇÕES
# ============================================================


def test_equation_without_calculated_dependencies():
    equation = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    variable_producers = {
        "VAR12001": "EQ12001",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

    graph.add_equation(
        equation,
        variable_producers,
        extractor,
    )

    assert graph.get_dependencies(
        "EQ12001",
    ) == frozenset()


# ============================================================
# TESTE 2 — UMA DEPENDÊNCIA
# ============================================================


def test_equation_depends_on_another_equation():
    equation_1 = make_equation(
        equation_id="EQ11001",
        target_variable_id="VAR11005",
        expression="VAR10001 * PARAM11001",
    )

    equation_2 = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    variable_producers = {
        "VAR11005": "EQ11001",
        "VAR12001": "EQ12001",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

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

    assert graph.get_dependencies(
        "EQ12001",
    ) == frozenset(
        {"EQ11001"},
    )


# ============================================================
# TESTE 3 — DUAS DEPENDÊNCIAS
# ============================================================


def test_equation_depends_on_multiple_equations():
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

    variable_producers = {
        "VAR11005": "EQ11001",
        "VAR11006": "EQ11002",
        "VAR12001": "EQ12001",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

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

    assert graph.get_dependencies(
        "EQ12001",
    ) == frozenset(
        {
            "EQ11001",
            "EQ11002",
        },
    )


# ============================================================
# TESTE 4 — DEPENDÊNCIA INDIRETA
# ============================================================


def test_dependency_chain_is_represented():
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

    variable_producers = {
        "VAR11005": "EQ11001",
        "VAR12001": "EQ12001",
        "VAR12003": "EQ12003",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

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

    assert graph.get_dependencies(
        "EQ11001",
    ) == frozenset()

    assert graph.get_dependencies(
        "EQ12001",
    ) == frozenset(
        {"EQ11001"},
    )

    assert graph.get_dependencies(
        "EQ12003",
    ) == frozenset(
        {"EQ12001"},
    )


# ============================================================
# TESTE 5 — PARÂMETROS NÃO CRIAM DEPENDÊNCIAS
# ============================================================


def test_parameters_do_not_create_equation_dependencies():
    equation = make_equation(
        equation_id="EQ12001",
        target_variable_id="VAR12001",
        expression="VAR11005 * PARAM12001",
    )

    variable_producers = {
        "VAR12001": "EQ12001",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

    graph.add_equation(
        equation,
        variable_producers,
        extractor,
    )

    assert graph.get_dependencies(
        "EQ12001",
    ) == frozenset()


# ============================================================
# TESTE 6 — EQUAÇÕES SEM DEPENDÊNCIAS TAMBÉM ENTRAM NO GRAFO
# ============================================================


def test_all_added_equations_are_present_in_graph():
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

    variable_producers = {
        "VAR11005": "EQ11001",
        "VAR12001": "EQ12001",
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

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

    assert graph.get_equations() == frozenset(
        {
            "EQ11001",
            "EQ12001",
        },
    )


def test_graph_preserves_line_scope():
    graph = DependencyGraph()

    equation = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11001@L4 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    variable_producers = {
        "VAR11001@L4": "EQ11001",
    }

    graph.add_equation(
        equation,
        variable_producers,
        DependencyExtractor(),
    )

    assert graph.get_dependencies(
        "EQ11002@linha:L4"
    ) == frozenset(
        {"EQ11001@linha:L4"}
    )


def test_graph_separates_same_equation_across_lines():
    graph = DependencyGraph()

    equation_l4 = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L4",
        expression="VAR11001@L4 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    equation_l5 = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type="linha",
        scope_value="L5",
        expression="VAR11001@L5 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    variable_producers = {
        "VAR11001@L4": "EQ11001",
        "VAR11001@L5": "EQ11001",
    }

    extractor = DependencyExtractor()

    graph.add_equation(
        equation_l4,
        variable_producers,
        extractor,
    )

    graph.add_equation(
        equation_l5,
        variable_producers,
        extractor,
    )

    assert graph.get_equations() == frozenset(
        {
            "EQ11002@linha:L4",
            "EQ11001@linha:L4",
            "EQ11002@linha:L5",
            "EQ11001@linha:L5",
        }
    )

    assert graph.get_dependencies(
        "EQ11002@linha:L4"
    ) == frozenset(
        {"EQ11001@linha:L4"}
    )

    assert graph.get_dependencies(
        "EQ11002@linha:L5"
    ) == frozenset(
        {"EQ11001@linha:L5"}
    )


def test_graph_preserves_unscoped_equation_behavior():
    graph = DependencyGraph()

    equation = Equation(
        equation_id="EQ11002",
        target_variable_id="VAR11002",
        version=1,
        scope_type=None,
        scope_value=None,
        expression="VAR11001 * 2",
        source_reference="TEST",
        status="APPROVED",
    )

    variable_producers = {
        "VAR11001": "EQ11001",
    }

    graph.add_equation(
        equation,
        variable_producers,
        DependencyExtractor(),
    )

    assert graph.get_dependencies(
        "EQ11002"
    ) == frozenset(
        {"EQ11001"}
    )
