import pytest

from app.engine.dependency_extractor import (
    DependencyExtractor,
    ExpressionDependencies,
)


@pytest.fixture
def extractor():
    return DependencyExtractor()


# ============================================================
# TESTE 1 — SOMENTE VARIÁVEL
# ============================================================


def test_extract_single_variable(extractor):
    result = extractor.extract(
        "VAR11005",
    )

    assert isinstance(
        result,
        ExpressionDependencies,
    )

    assert result.variables == frozenset({"VAR11005"})
    assert result.parameters == frozenset()


# ============================================================
# TESTE 2 — SOMENTE PARÂMETRO
# ============================================================


def test_extract_single_parameter(extractor):
    result = extractor.extract(
        "PARAM12001",
    )

    assert result.variables == frozenset()
    assert result.parameters == frozenset({"PARAM12001"})


# ============================================================
# TESTE 3 — VARIÁVEL + PARÂMETRO
# ============================================================


def test_extract_variable_and_parameter(extractor):
    result = extractor.extract(
        "VAR11005 * PARAM12001",
    )

    assert result.variables == frozenset(
        {"VAR11005"},
    )

    assert result.parameters == frozenset(
        {"PARAM12001"},
    )


# ============================================================
# TESTE 4 — MÚLTIPLAS VARIÁVEIS
# ============================================================


def test_extract_multiple_variables(extractor):
    result = extractor.extract(
        "VAR11005 + VAR12001",
    )

    assert result.variables == frozenset(
        {
            "VAR11005",
            "VAR12001",
        },
    )

    assert result.parameters == frozenset()


# ============================================================
# TESTE 5 — EXPRESSÃO COMPLEXA
# ============================================================


def test_extract_complex_expression(extractor):
    result = extractor.extract(
        "(VAR11005 + VAR12001) * PARAM12001",
    )

    assert result.variables == frozenset(
        {
            "VAR11005",
            "VAR12001",
        },
    )

    assert result.parameters == frozenset(
        {"PARAM12001"},
    )


# ============================================================
# TESTE 6 — DEPENDÊNCIA REPETIDA
# ============================================================


def test_extract_duplicate_dependencies(extractor):
    result = extractor.extract(
        "VAR11005 * PARAM12001 + VAR11005",
    )

    assert result.variables == frozenset(
        {"VAR11005"},
    )

    assert result.parameters == frozenset(
        {"PARAM12001"},
    )


# ============================================================
# TESTE 7 — EXPRESSÃO SEM DEPENDÊNCIAS
# ============================================================


def test_extract_expression_without_dependencies(extractor):
    result = extractor.extract(
        "100 + 50",
    )

    assert result.variables == frozenset()
    assert result.parameters == frozenset()


# ============================================================
# TESTE 8 — EXPRESSÃO INVÁLIDA
# ============================================================


def test_extract_invalid_expression_raises_error(extractor):
    with pytest.raises(Exception):
        extractor.extract(
            "VAR11005 *",
        )


# ============================================================
# TESTE 9 — VARIÁVEL COM ESCOPO
# ============================================================


def test_extract_scoped_variable(extractor):
    result = extractor.extract(
        "VAR11005@L4",
    )

    assert result.variables == frozenset(
        {"VAR11005@L4"},
    )

    assert result.parameters == frozenset()


# ============================================================
# TESTE 10 — PARÂMETRO COM ESCOPO
# ============================================================


def test_extract_scoped_parameter(extractor):
    result = extractor.extract(
        "PARAM12001@L4",
    )

    assert result.variables == frozenset()

    assert result.parameters == frozenset(
        {"PARAM12001@L4"},
    )


# ============================================================
# TESTE 11 — MÚLTIPLAS VARIÁVEIS COM ESCOPO
# ============================================================


def test_extract_multiple_scoped_variables(extractor):
    result = extractor.extract(
        "(VAR11005@L4 + VAR11005@L5) / 2",
    )

    assert result.variables == frozenset(
        {
            "VAR11005@L4",
            "VAR11005@L5",
        },
    )

    assert result.parameters == frozenset()


# ============================================================
# TESTE 12 — VARIÁVEL E PARÂMETRO COM ESCOPO
# ============================================================


def test_extract_scoped_variable_and_parameter(extractor):
    result = extractor.extract(
        "VAR11005@L4 * PARAM12001@L4",
    )

    assert result.variables == frozenset(
        {"VAR11005@L4"},
    )

    assert result.parameters == frozenset(
        {"PARAM12001@L4"},
    )


# ============================================================
# TESTE 13 — DEPENDÊNCIA ESCOPADA REPETIDA
# ============================================================


def test_extract_duplicate_scoped_dependencies(extractor):
    result = extractor.extract(
        "VAR11005@L4 * VAR11005@L4",
    )

    assert result.variables == frozenset(
        {"VAR11005@L4"},
    )

    assert result.parameters == frozenset()


# ============================================================
# TESTE 14 — DEPENDÊNCIAS EM EXPRESSÃO CONDICIONAL (BD-07)
# ============================================================


def test_extract_dependencies_from_all_if_expression_branches(
    extractor,
):
    """
    Uma expressão `X if cond else Y` tem dependências nos três
    ramos (teste, verdadeiro, falso) -- todas devem ser
    extraídas, mesmo que cada ramo referencie variáveis distintas.
    """

    result = extractor.extract(
        "VAR12001@L1 * PARAM12001@L1 if VAR12001@L1 > VAR12002 "
        "else VAR12002",
    )

    assert result.variables == frozenset(
        {"VAR12001@L1", "VAR12002"},
    )

    assert result.parameters == frozenset(
        {"PARAM12001@L1"},
    )
