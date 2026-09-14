"""
Objetivo (FASE 3A pós-code-review — Parte C):
    Provar que ExpressionEvaluator, DependencyGraph,
    DependencyResolver, EquationEngine e ForecastEngine aplicam
    EXATAMENTE a mesma semântica de resolução de referências:

        - uma referência sem escopo explícito é resolvida no escopo
          da EquationInstance em execução;
        - uma referência explicitamente escopada (ex.: "VAR@L2")
          NUNCA é reinterpretada, mesmo que a instance em execução
          seja outra linha.

    Cada cenário é validado tanto em componentes isolados quanto
    através do fluxo real e completo (SeedLoader-like: Definition ->
    Instance -> DependencyGraph -> DependencyResolver -> EquationEngine
    -> ForecastEngine), sem mocks.
"""

import pytest

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.domain.equations.registry import EquationDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver
from app.engine.equation_engine import EquationEngine
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.engine.forecast_engine import ForecastEngine


# ============================================================
# C.1 — referência explícita em outra linha
# ============================================================


def test_c1_explicit_reference_in_another_line_expression_evaluator():
    context = CalculationContext()
    context.set_variable_value("VAR10001", 20, "linha", "L2")
    context.set_variable_value("VAR10001", 30, "linha", "L3")
    context.set_variable_value("VAR10001", 100, "linha", "L5")

    parser = ExpressionParser()
    tree = parser.parse("VAR10001@L2 + VAR10001@L3")

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L5",
    )

    assert evaluator.evaluate(tree) == 50


def test_c1_explicit_reference_in_another_line_equation_engine():
    definition = EquationDefinition(
        equation_definition_id="EQ_C1",
        target_variable_id="VAR_C1",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001@L2 + VAR10001@L3",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    context = CalculationContext()
    context.set_variable_value("VAR10001", 20, "linha", "L2")
    context.set_variable_value("VAR10001", 30, "linha", "L3")
    context.set_variable_value("VAR10001", 100, "linha", "L5")

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 50
    assert result != 200  # não pode ler VAR10001@L5 duas vezes


# ============================================================
# C.2 — referência implícita na linha corrente
# ============================================================


def test_c2_implicit_reference_in_current_line_expression_evaluator():
    context = CalculationContext()
    context.set_variable_value("VAR10001", 20, "linha", "L5")
    context.set_variable_value("VAR10001", 100, "linha", "L2")

    parser = ExpressionParser()
    tree = parser.parse("VAR10001 + 10")

    evaluator = ExpressionEvaluator(
        context,
        default_scope_type="linha",
        default_scope_value="L5",
    )

    assert evaluator.evaluate(tree) == 30


def test_c2_implicit_reference_in_current_line_equation_engine():
    definition = EquationDefinition(
        equation_definition_id="EQ_C2",
        target_variable_id="VAR_C2",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001 + 10",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    context = CalculationContext()
    context.set_variable_value("VAR10001", 20, "linha", "L5")
    context.set_variable_value("VAR10001", 100, "linha", "L2")

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 30


# ============================================================
# C.3 — mistura explícita + implícita
# ============================================================


def test_c3_mixed_explicit_and_implicit_references():
    definition = EquationDefinition(
        equation_definition_id="EQ_C3",
        target_variable_id="VAR_C3",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001@L2 + VAR10002 + VAR10003",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    context = CalculationContext()
    context.set_variable_value("VAR10001", 20, "linha", "L2")
    context.set_variable_value("VAR10002", 30, "linha", "L5")
    context.set_variable_value("VAR10003", 40, "linha", "L5")

    # Nenhum valor definido para VAR10001@L5 nem VAR10002@L2 /
    # VAR10003@L2: se a referência explícita @L2 fosse contextualizada
    # indevidamente para L5, ou a implícita fosse mal resolvida, o
    # cálculo levantaria VariableNotFoundError em vez de 90.

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == 90


# ============================================================
# C.4 — DependencyGraph no mesmo cenário, através do fluxo real
#        completo (ForecastEngine.calculate_from_definition_registry)
# ============================================================


def test_c4_full_stack_preserves_explicit_and_implicit_semantics():
    """
    Fluxo real e completo: EquationDefinitionRegistry ->
    materialização em EquationInstance -> DependencyGraph ->
    DependencyResolver -> EquationEngine, via
    ForecastEngine.calculate_from_definition_registry — sem mocks.

    EQ_PRODUCER é materializada em L2, L3 e L5 (produz VAR_PRODUCER
    em cada linha). EQ_CONSUMER, materializada apenas em L5,
    referencia explicitamente VAR_PRODUCER@L2 e VAR_PRODUCER@L3 (não
    L5) e implicitamente PARAM/VAR extras da própria linha L5.
    """

    registry = EquationDefinitionRegistry()

    producer = EquationDefinition(
        equation_definition_id="EQ_PRODUCER",
        target_variable_id="VAR10010",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="VAR10001 * 2",
        source_reference="TEST",
        status="PUBLISHED",
    )

    consumer = EquationDefinition(
        equation_definition_id="EQ_CONSUMER",
        target_variable_id="VAR10011",
        version=1,
        scope_type="linha",
        scope_value="L5",
        expression="VAR10010@L2 + VAR10010@L3 + VAR10002",
        source_reference="TEST",
        status="PUBLISHED",
    )

    registry.add(producer)
    registry.add(consumer)

    context = CalculationContext()

    # A definição do produtor é scope linha/L1_L7: materializa em
    # TODAS as 7 linhas, mesmo que só L2/L3/L5 importem para este
    # cenário. Valores irrelevantes são atribuídos às demais linhas
    # apenas para que o cálculo delas não falhe por falta de dado.
    for line in ("L1", "L4", "L6", "L7"):
        context.set_variable_value("VAR10001", 0, "linha", line)

    context.set_variable_value("VAR10001", 5, "linha", "L2")   # producer L2 -> 10
    context.set_variable_value("VAR10001", 7, "linha", "L3")   # producer L3 -> 14
    context.set_variable_value("VAR10001", 999, "linha", "L5")  # producer L5 -> 1998 (não deve ser usado)
    context.set_variable_value("VAR10002", 6, "linha", "L5")

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert results["EQ_PRODUCER@v1@L2"] == 10
    assert results["EQ_PRODUCER@v1@L3"] == 14
    assert results["EQ_PRODUCER@v1@L5"] == 1998
    assert results["EQ_CONSUMER@v1@L5"] == 10 + 14 + 6

    # Prova direta no DependencyGraph, reconstruído com os mesmos
    # componentes reais usados pelo ForecastEngine.
    graph = DependencyGraph()
    extractor = DependencyExtractor()

    definitions_by_id_and_version = {
        (d.equation_definition_id, d.version): d
        for d in registry.all()
    }

    all_instances = []
    for definition in registry.all():
        all_instances.extend(
            engine.materialize_equation(definition)
        )

    variable_producers = engine._build_instance_variable_producers(
        all_instances
    )

    for instance in all_instances:
        definition = definitions_by_id_and_version[
            (instance.equation_definition_id, instance.version)
        ]
        graph.add_instance(
            instance=instance,
            definition=definition,
            variable_producers=variable_producers,
            extractor=extractor,
        )

    consumer_dependencies = graph.get_dependencies(
        "EQ_CONSUMER@linha:L5"
    )

    assert consumer_dependencies == {
        "EQ_PRODUCER@linha:L2",
        "EQ_PRODUCER@linha:L3",
    }

    assert "EQ_PRODUCER@linha:L5" not in consumer_dependencies

    # DependencyResolver: o produtor de L2 e o de L3 devem vir antes
    # do consumidor de L5 na ordem de execução — a mesma ordem já
    # usada implicitamente por calculate_from_definition_registry.
    resolver = DependencyResolver()
    execution_order = resolver.resolve(graph)

    assert execution_order.index(
        "EQ_PRODUCER@linha:L2"
    ) < execution_order.index("EQ_CONSUMER@linha:L5")

    assert execution_order.index(
        "EQ_PRODUCER@linha:L3"
    ) < execution_order.index("EQ_CONSUMER@linha:L5")


# ============================================================
# C.5 — n_ppt para L1...L7 (tanque_base - tanque)
# ============================================================


@pytest.mark.parametrize(
    "line,tanque_base_value,tanque_value,expected",
    [
        ("L1", 14, 5, 9),
        ("L2", 14, 6, 8),
        ("L3", 16, 7, 9),
        ("L4", 18, 8, 10),
        ("L5", 18, 5, 13),
        ("L6", 18, 10, 8),
        ("L7", 18, 11, 7),
    ],
)
def test_c5_n_ppt_tanque_base_minus_tanque_all_lines(
    line,
    tanque_base_value,
    tanque_value,
    expected,
):
    definition = EquationDefinition(
        equation_definition_id="EQ11004",
        target_variable_id="VAR11012",
        version=1,
        scope_type="linha",
        scope_value="L1_L7",
        expression="PARAM11003 - VAR11239",
        source_reference="TEST",
        status="PUBLISHED",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value=line,
    )

    context = CalculationContext()

    context.set_parameter_value(
        "PARAM11003", tanque_base_value, "linha", line,
    )
    context.set_variable_value(
        "VAR11239", tanque_value, "linha", line,
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    assert result == expected


def test_c5_n_ppt_full_stack_all_lines():
    """
    Mesmo cenário C.5, mas através do ForecastEngine real
    (Definition -> 7 Instances -> DependencyGraph -> EquationEngine),
    para as 7 linhas simultaneamente, sem duplicar a expressão.
    """

    registry = EquationDefinitionRegistry()

    registry.add(
        EquationDefinition(
            equation_definition_id="EQ11004",
            target_variable_id="VAR11012",
            version=1,
            scope_type="linha",
            scope_value="L1_L7",
            expression="PARAM11003 - VAR11239",
            source_reference="TEST",
            status="PUBLISHED",
        )
    )

    tanque_base_by_line = {
        "L1": 14, "L2": 14, "L3": 16,
        "L4": 18, "L5": 18, "L6": 18, "L7": 18,
    }
    tanque_by_line = {
        "L1": 5, "L2": 6, "L3": 7,
        "L4": 8, "L5": 5, "L6": 10, "L7": 11,
    }

    context = CalculationContext()

    for line in tanque_base_by_line:
        context.set_parameter_value(
            "PARAM11003", tanque_base_by_line[line], "linha", line,
        )
        context.set_variable_value(
            "VAR11239", tanque_by_line[line], "linha", line,
        )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert len(results) == 7

    for line in tanque_base_by_line:
        expected = (
            tanque_base_by_line[line] - tanque_by_line[line]
        )
        assert results[f"EQ11004@v1@{line}"] == expected

        assert context.get_variable_value(
            variable_id="VAR11012",
            scope_type="linha",
            scope_value=line,
        ) == expected
