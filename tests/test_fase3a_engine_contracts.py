"""
Objetivo:
    Comprovar os contratos mínimos aprovados na FASE 3A antes da
    implementação do seed do Yield:

    A/B. resolução contextual de referências sem escopo dentro de
         uma EquationInstance scoped ("linha corrente");
    C/D. referências simples vs. explicitamente escopadas;
    E.   equações DRAFT não são executadas pelo caminho normal;
    F.   scopes válidos (L1, L1_L7, área/global) continuam
         funcionando, incluindo o caso antes quebrado;
    G.   ausência de regressão nos contratos de escopo existentes
         (cobertura adicional; a suíte completa é a prova final).
"""

import pytest

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.domain.equations.registry import EquationDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.forecast_engine import ForecastEngine
from app.engine.scope_resolver import ScopeResolver


# ============================================================
# A/B — n_ppt@L1 e n_ppt@L7 resolvem "tanque_base - tanque"
#        no escopo da própria instance
# ============================================================


@pytest.mark.parametrize(
    "scope_value,tanque_base_value,tanque_value,expected",
    [
        ("L1", 14, 5, 9),
        ("L7", 18, 11, 7),
    ],
)
def test_n_ppt_resolves_bare_references_in_instance_scope(
    scope_value,
    tanque_base_value,
    tanque_value,
    expected,
):
    definition = EquationDefinition(
        equation_definition_id="EQ11099",
        target_variable_id="VAR11012",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="PARAM11003 - VAR11090",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value=scope_value,
    )

    context = CalculationContext()

    context.set_parameter_value(
        parameter_id="PARAM11003",
        value=tanque_base_value,
        scope_type="linha",
        scope_value=scope_value,
    )

    context.set_variable_value(
        variable_id="VAR11090",
        value=tanque_value,
        scope_type="linha",
        scope_value=scope_value,
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == expected


# ============================================================
# C — referência simples "x" em equação scoped L3 resolve x@L3
#      quando existe definição/valor compatível naquele escopo
# ============================================================


def test_bare_reference_resolves_in_current_instance_scope():
    definition = EquationDefinition(
        equation_definition_id="EQ11098",
        target_variable_id="VAR11099",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001 * 2",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L3",
    )

    context = CalculationContext()

    context.set_variable_value(
        variable_id="VAR10001",
        value=21,
        scope_type="linha",
        scope_value="L3",
    )

    # Um valor "de outra linha" não deve ser usado por engano.
    context.set_variable_value(
        variable_id="VAR10001",
        value=999,
        scope_type="linha",
        scope_value="L4",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 42


def test_bare_reference_falls_back_to_legacy_when_no_scoped_value():
    """
    Quando não existe valor escopado compatível, a referência sem
    escopo continua caindo para a API legada (não-escopada),
    preservando o comportamento anterior (compatibilidade
    retroativa com equações/valores legados).
    """

    definition = EquationDefinition(
        equation_definition_id="EQ11097",
        target_variable_id="VAR11096",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001 * 3",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L3",
    )

    context = CalculationContext(
        variables={"VAR10001": 10},
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 30


# ============================================================
# D — referência explícita x@L2 continua significando x@L2
#
# Isso é exercitado pelas equações de agregação de linha_grupo
# (ex.: ratio_spent@L1_L3 = média ponderada de ratio_spent@L1,
# @L2 e @L3): a EquationInstance é "linha_grupo" (não "linha"), e
# cada @Lx explícito na expressão deve continuar apontando
# exatamente para aquela linha, nunca para o escopo da própria
# instance. O contrato pré-existente de "linha" (materialização de
# um template por linha, onde @Lx no corpo da Definition sempre
# significa "esta mesma linha materializada") permanece inalterado
# — é o que os testes já existentes de EquationEngine/DependencyGraph
# cobrem (ex.: test_equation_engine_uses_instance_scope).
# ============================================================


def test_explicit_scoped_reference_is_not_affected_by_context():
    definition = EquationDefinition(
        equation_definition_id="EQ11096",
        target_variable_id="VAR11095",
        version=1,
        scope_type="linha_grupo",
        scope_value="L1_L3",
        expression="VAR10001@L1 + VAR10001@L2 + VAR10001@L3",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    context = CalculationContext()

    context.set_variable_value(
        variable_id="VAR10001",
        value=10,
        scope_type="linha",
        scope_value="L1",
    )

    context.set_variable_value(
        variable_id="VAR10001",
        value=20,
        scope_type="linha",
        scope_value="L2",
    )

    context.set_variable_value(
        variable_id="VAR10001",
        value=30,
        scope_type="linha",
        scope_value="L3",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 60


# ============================================================
# E — equação DRAFT não é executada pelo caminho normal
# ============================================================


def test_draft_equation_is_not_executed_by_definition_registry_flow():
    registry = EquationDefinitionRegistry()

    draft_definition = EquationDefinition(
        equation_definition_id="EQ11095",
        target_variable_id="VAR11094",
        version=1,
        scope_type="linha",
        scope_value="L1",
        expression="1",
        source_reference="TEST",
        status="DRAFT",
    )

    registry.add(draft_definition)

    engine = ForecastEngine()

    context = CalculationContext()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert results == {}

    with pytest.raises(Exception):
        context.get_variable_value(
            variable_id="VAR11094",
            scope_type="linha",
            scope_value="L1",
        )


def test_published_equation_alongside_draft_is_still_executed():
    registry = EquationDefinitionRegistry()

    registry.add(
        EquationDefinition(
            equation_definition_id="EQ11095",
            target_variable_id="VAR11094",
            version=1,
            scope_type="linha",
            scope_value="L1",
            expression="1",
            source_reference="TEST",
            status="DRAFT",
        )
    )

    registry.add(
        EquationDefinition(
            equation_definition_id="EQ11093",
            target_variable_id="VAR11092",
            version=1,
            scope_type="linha",
            scope_value="L1",
            expression="2",
            source_reference="TEST",
            status="PUBLISHED",
        )
    )

    engine = ForecastEngine()

    context = CalculationContext()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert results == {
        "EQ11093@v1@L1": 2,
    }


# ============================================================
# F — scopes válidos continuam funcionando, incluindo o caso
#      antes quebrado (área/global com scope_value=None)
# ============================================================


@pytest.mark.parametrize(
    "scope_type,scope_value,expected",
    [
        ("linha", "L1", [("linha", "L1")]),
        (
            "linha",
            "L1_L7",
            [
                ("linha", "L1"),
                ("linha", "L2"),
                ("linha", "L3"),
                ("linha", "L4"),
                ("linha", "L5"),
                ("linha", "L6"),
                ("linha", "L7"),
            ],
        ),
        ("linha_grupo", "L1_L3", [("linha_grupo", "L1_L3")]),
        ("planta", "PLANTA", [("planta", "PLANTA")]),
        ("área", None, [("área", None)]),
        ("global", None, [("global", None)]),
    ],
)
def test_scope_resolver_handles_all_valid_scope_types(
    scope_type,
    scope_value,
    expected,
):
    resolver = ScopeResolver()

    result = resolver.resolve_scopes(
        scope_type=scope_type,
        scope_value=scope_value,
    )

    assert result == expected


def test_scope_resolver_still_requires_scope_value_for_line_scopes():
    resolver = ScopeResolver()

    with pytest.raises(
        ValueError,
        match="scope_value is required",
    ):
        resolver.resolve_scopes(
            scope_type="linha",
            scope_value=None,
        )
