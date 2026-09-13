import pytest

from app.engine.equation_selector import EquationSelector
from app.domain.equations.models import (
    Equation,
    EquationDefinition,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationRegistry,
)

# ============================================================
# HELPERS
# ============================================================


def make_equation(
    equation_id: str,
    version: int,
    expression: str,
    scope_type: str | None = "linha",
    scope_value: str | None = "L1",
    status: str = "PUBLISHED",
) -> Equation:
    return Equation(
        equation_id=equation_id,
        target_variable_id="VAR11005",
        version=version,
        scope_type=scope_type,
        scope_value=scope_value,
        expression=expression,
        source_reference="test",
        status=status,
    )


# ============================================================
# TESTE 1 — SELEÇÃO DA EQUAÇÃO PUBLISHED
# ============================================================


def test_select_published_equation():
    registry = EquationRegistry()

    equation = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    registry.add(equation)

    selector = EquationSelector(registry)

    result = selector.select("EQ11001")

    assert result == equation


# ============================================================
# TESTE 2 — SELEÇÃO DA MAIOR VERSÃO PUBLISHED
# ============================================================


def test_selects_highest_published_version():
    registry = EquationRegistry()

    equation_v1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    equation_v2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
    )

    registry.add(equation_v1)
    registry.add(equation_v2)

    selector = EquationSelector(registry)

    result = selector.select("EQ11001")

    assert result == equation_v2
    assert result.version == 2


# ============================================================
# TESTE 3 — IGNORA VERSÃO DRAFT
# ============================================================


def test_select_ignores_draft_version():
    registry = EquationRegistry()

    equation_v1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
        status="PUBLISHED",
    )

    equation_v2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
        status="DRAFT",
    )

    registry.add(equation_v1)
    registry.add(equation_v2)

    selector = EquationSelector(registry)

    result = selector.select("EQ11001")

    assert result == equation_v1
    assert result.version == 1


# ============================================================
# TESTE 4 — SELEÇÃO EXPLÍCITA DE VERSÃO
# ============================================================


def test_select_explicit_version():
    registry = EquationRegistry()

    equation_v1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    equation_v2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
    )

    registry.add(equation_v1)
    registry.add(equation_v2)

    selector = EquationSelector(registry)

    result = selector.select(
        equation_id="EQ11001",
        version=1,
    )

    assert result == equation_v1
    assert result.version == 1


# ============================================================
# TESTE 5 — SELEÇÃO POR ESCOPO
# ============================================================


def test_selects_equation_by_scope():
    registry = EquationRegistry()

    equation_l1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
        scope_type="linha",
        scope_value="L1",
    )

    equation_l2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(equation_l1)
    registry.add(equation_l2)

    selector = EquationSelector(registry)

    result = selector.select(
        equation_id="EQ11001",
        scope_type="linha",
        scope_value="L2",
    )

    assert result == equation_l2
    assert result.version == 2
    assert result.scope_type == "linha"
    assert result.scope_value == "L2"


# ============================================================
# TESTE 6 — VERSÃO MAIS ALTA DENTRO DO ESCOPO
# ============================================================


def test_selects_highest_version_within_scope():
    registry = EquationRegistry()

    equation_l1_v1 = make_equation(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
        scope_type="linha",
        scope_value="L1",
    )

    equation_l1_v2 = make_equation(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
        scope_type="linha",
        scope_value="L1",
    )

    equation_l2_v3 = make_equation(
        equation_id="EQ11001",
        version=3,
        expression="VAR10001 * PARAM11003",
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(equation_l1_v1)
    registry.add(equation_l1_v2)
    registry.add(equation_l2_v3)

    selector = EquationSelector(registry)

    result = selector.select(
        equation_id="EQ11001",
        scope_type="linha",
        scope_value="L1",
    )

    assert result == equation_l1_v2
    assert result.version == 2


# ============================================================
# TESTE 7 — EQUAÇÃO INEXISTENTE
# ============================================================


def test_select_rejects_unknown_equation():
    registry = EquationRegistry()

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select("EQ99999")


# ============================================================
# TESTE 8 — VERSÃO INEXISTENTE
# ============================================================


def test_select_rejects_unknown_version():
    registry = EquationRegistry()

    registry.add(
        make_equation(
            equation_id="EQ11001",
            version=1,
            expression="VAR10001 * PARAM11001",
        )
    )

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select(
            equation_id="EQ11001",
            version=99,
        )


# ============================================================
# TESTE 9 — ESCOPO INEXISTENTE
# ============================================================


def test_select_rejects_unknown_scope():
    registry = EquationRegistry()

    registry.add(
        make_equation(
            equation_id="EQ11001",
            version=1,
            expression="VAR10001 * PARAM11001",
            scope_type="linha",
            scope_value="L1",
        )
    )

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select(
            equation_id="EQ11001",
            scope_type="linha",
            scope_value="L99",
        )


# ============================================================
# TESTE 10 — EQUAÇÃO DRAFT NÃO PODE SER SELECIONADA
# ============================================================


def test_select_rejects_only_draft_equation():
    registry = EquationRegistry()

    registry.add(
        make_equation(
            equation_id="EQ11001",
            version=1,
            expression="VAR10001 * PARAM11001",
            status="DRAFT",
        )
    )

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select("EQ11001")


# ============================================================
# EQUATION DEFINITION SELECTOR
# ============================================================


def make_equation_definition(
    equation_id: str,
    version: int,
    expression: str,
    scope_type: str | None = "linha",
    scope_value: str | None = "L1",
    status: str = "ativo",
):
    equation = Equation(
        equation_id=equation_id,
        target_variable_id="VAR11005",
        version=version,
        scope_type=scope_type,
        scope_value=scope_value,
        expression=expression,
        source_reference="test",
        status=status,
    )

    return EquationDefinition.from_equation(
        equation
    )


def test_selects_equation_definition():

    registry = EquationDefinitionRegistry()

    definition = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    registry.add(definition)

    selector = EquationSelector(registry)

    result = selector.select_definition(
        equation_definition_id="EQ11001",
        version=1,
        scope_type="linha",
        scope_value="L1",
    )

    assert result is definition


def test_selects_highest_definition_version():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    definition_v1 = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001 * PARAM11001",
    )

    definition_v2 = make_equation_definition(
        equation_id="EQ11001",
        version=2,
        expression="VAR10001 * PARAM11002",
    )

    registry.add(definition_v1)
    registry.add(definition_v2)

    selector = EquationSelector(registry)

    result = selector.select_definition(
        equation_definition_id="EQ11001",
        scope_type="linha",
        scope_value="L1",
    )

    assert result is definition_v2
    assert result.version == 2


def test_selects_definition_by_scope():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    definition_l1 = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001",
        scope_type="linha",
        scope_value="L1",
    )

    definition_l2 = make_equation_definition(
        equation_id="EQ11001",
        version=2,
        expression="VAR10002",
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(definition_l1)
    registry.add(definition_l2)

    selector = EquationSelector(registry)

    result = selector.select_definition(
        equation_definition_id="EQ11001",
        scope_type="linha",
        scope_value="L2",
    )

    assert result is definition_l2
    assert result.version == 2


def test_selects_explicit_definition_version():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    definition_v1 = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001",
    )

    definition_v2 = make_equation_definition(
        equation_id="EQ11001",
        version=2,
        expression="VAR10002",
    )

    registry.add(definition_v1)
    registry.add(definition_v2)

    selector = EquationSelector(registry)

    result = selector.select_definition(
        equation_definition_id="EQ11001",
        version=1,
    )

    assert result is definition_v1
    assert result.version == 1


def test_rejects_ambiguous_definition():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    definition_l1 = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001",
        scope_type="linha",
        scope_value="L1",
    )

    definition_l2 = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10002",
        scope_type="linha",
        scope_value="L2",
    )

    registry.add(definition_l1)
    registry.add(definition_l2)

    selector = EquationSelector(registry)

    with pytest.raises(
        ValueError,
        match="EquationDefinition ambígua",
    ):
        selector.select_definition(
            equation_definition_id="EQ11001",
            version=1,
        )


def test_rejects_inactive_definition():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    definition = make_equation_definition(
        equation_id="EQ11001",
        version=1,
        expression="VAR10001",
        status="DRAFT",
    )

    registry.add(definition)

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select_definition(
            equation_definition_id="EQ11001",
            version=1,
        )


def test_rejects_unknown_definition():
    from app.domain.equations.registry import (
        EquationDefinitionRegistry,
    )

    registry = EquationDefinitionRegistry()

    selector = EquationSelector(registry)

    with pytest.raises(ValueError):
        selector.select_definition(
            equation_definition_id="EQ99999",
        )
