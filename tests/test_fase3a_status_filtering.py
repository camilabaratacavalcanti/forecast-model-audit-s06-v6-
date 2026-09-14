"""
Objetivo (FASE 3A pós-code-review — Parte E):
    Revisar completamente o tratamento de status nos três métodos
    públicos de cálculo do ForecastEngine:

        calculate()                        — BAIXO NÍVEL
        calculate_from_registry()          — ALTO NÍVEL (legado)
        calculate_from_definition_registry() — ALTO NÍVEL (novo fluxo)

    Os dois métodos de alto nível devem filtrar por status elegível
    (ver EquationSelector.ACTIVE_STATUSES) e nunca executar uma
    equação DRAFT/PENDING/REJECTED. calculate() é, deliberadamente,
    um primitivo de baixo nível que executa exatamente o que recebe,
    sem filtrar — está documentado como tal em
    ForecastEngine.calculate().
"""

import pytest

from app.domain.equations.models import (
    Equation,
    EquationDefinition,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationRegistry,
)
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine


def make_variable(variable_id: str) -> Variable:
    return Variable(
        variable_id=variable_id,
        variable_name=f"Variable {variable_id}",
        description="Test variable",
        unit="unit",
        variable_type="input",
        frequency="monthly",
        scope_type=None,
        scope_value=None,
        source_reference="test",
        status="ACTIVE",
    )


def make_parameter(parameter_id: str) -> Parameter:
    return Parameter(
        parameter_id=parameter_id,
        parameter_name=f"Parameter {parameter_id}",
        description="Test parameter",
        unit="unit",
        value=1.0,
        version=1,
        scope_type=None,
        scope_value=None,
        source_reference="test",
        status="ACTIVE",
    )


def make_equation(
    equation_id: str,
    target_variable_id: str,
    expression: str,
    status: str,
) -> Equation:
    return Equation(
        equation_id=equation_id,
        target_variable_id=target_variable_id,
        version=1,
        scope_type="linha",
        scope_value="L1",
        expression=expression,
        source_reference="test",
        status=status,
    )


# ============================================================
# calculate_from_registry() — ALTO NÍVEL, caminho legado
# ============================================================


def test_calculate_from_registry_does_not_execute_draft_equation():
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            "EQ11001",
            "VAR11005",
            "VAR10001 * PARAM11001",
            status="DRAFT",
        )
    )

    variable_registry = VariableRegistry()
    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR11005"))

    parameter_registry = ParameterRegistry()
    parameter_registry.add(make_parameter("PARAM11001"))

    context = CalculationContext()
    context.set_variable("VAR10001", 100)
    context.set_parameter("PARAM11001", 0.8)

    engine = ForecastEngine()

    results = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert results == {}

    with pytest.raises(Exception):
        context.get_variable("VAR11005")


def test_calculate_from_registry_executes_eligible_equation():
    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            "EQ11001",
            "VAR11005",
            "VAR10001 * PARAM11001",
            status="PUBLISHED",
        )
    )

    variable_registry = VariableRegistry()
    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR11005"))

    parameter_registry = ParameterRegistry()
    parameter_registry.add(make_parameter("PARAM11001"))

    context = CalculationContext()
    context.set_variable("VAR10001", 100)
    context.set_parameter("PARAM11001", 0.8)

    engine = ForecastEngine()

    results = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert results == {"EQ11001": 80.0}
    assert context.get_variable("VAR11005") == 80.0


def test_calculate_from_registry_executes_published_ignores_rejected():
    """
    Duas equações, mesma variável alvo não pode ser usada (dispararia
    DuplicateVariableProducerError) — usa alvos distintos para provar
    que apenas a elegível roda.
    """

    equation_registry = EquationRegistry()

    equation_registry.add(
        make_equation(
            "EQ11001",
            "VAR11005",
            "VAR10001 * PARAM11001",
            status="PUBLISHED",
        )
    )

    equation_registry.add(
        make_equation(
            "EQ11002",
            "VAR11006",
            "VAR10001 + PARAM11001",
            status="REJECTED",
        )
    )

    variable_registry = VariableRegistry()
    variable_registry.add(make_variable("VAR10001"))
    variable_registry.add(make_variable("VAR11005"))
    variable_registry.add(make_variable("VAR11006"))

    parameter_registry = ParameterRegistry()
    parameter_registry.add(make_parameter("PARAM11001"))

    context = CalculationContext()
    context.set_variable("VAR10001", 100)
    context.set_parameter("PARAM11001", 0.8)

    engine = ForecastEngine()

    results = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert results == {"EQ11001": 80.0}
    assert "EQ11002" not in results

    with pytest.raises(Exception):
        context.get_variable("VAR11006")


# ============================================================
# calculate_from_definition_registry() — ALTO NÍVEL, novo fluxo
# (comportamento já coberto em test_fase3a_engine_contracts.py;
# reafirmado aqui para reunir os três métodos em um só lugar)
# ============================================================


def test_calculate_from_definition_registry_does_not_execute_draft():
    registry = EquationDefinitionRegistry()

    registry.add(
        EquationDefinition(
            equation_definition_id="EQ11001",
            target_variable_id="VAR11001",
            version=1,
            scope_type="linha",
            scope_value="L1",
            expression="1",
            source_reference="test",
            status="DRAFT",
        )
    )

    engine = ForecastEngine()
    context = CalculationContext()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert results == {}


# ============================================================
# calculate() — BAIXO NÍVEL: não filtra, executa o que recebe
# ============================================================


def test_calculate_low_level_executes_whatever_it_is_given():
    """
    calculate() é documentado como primitivo de baixo nível: recebe
    a lista já selecionada e não filtra por status. Passar uma
    equação DRAFT diretamente aqui a executa — isso é esperado e
    deliberado, diferente dos métodos de alto nível.
    """

    draft_equation = make_equation(
        "EQ11001",
        "VAR11005",
        "VAR10001 * PARAM11001",
        status="DRAFT",
    )

    context = CalculationContext()
    context.set_variable("VAR10001", 100)
    context.set_parameter("PARAM11001", 0.8)

    engine = ForecastEngine()

    results = engine.calculate(
        equations=[draft_equation],
        variable_producers={"VAR11005": "EQ11001"},
        calculation_context=context,
    )

    assert results == {"EQ11001": 80.0}
    assert context.get_variable("VAR11005") == 80.0
