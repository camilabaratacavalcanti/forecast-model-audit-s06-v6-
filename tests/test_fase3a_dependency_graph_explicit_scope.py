"""
Objetivo (FASE 3A — correção final do DependencyGraph):
    Provar que DependencyGraph.add_instance() nunca altera o escopo
    de uma referência explicitamente escopada, mesmo quando o
    producer registrado em variable_producers ainda não é um
    node_id totalmente qualificado (não contém "@").

    Antes desta correção, _scope_dependency_id (então embutido
    diretamente em add_instance) usava instance.scope_type/
    scope_value para qualificar QUALQUER producer sem "@" — inclusive
    quando a referência que o originou era explícita (ex.:
    "VAR10001@L2" em uma instance L5), produzindo
    "<producer>@linha:L5" em vez de "<producer>@linha:L2".

    Estes testes usam variable_producers com valores propositalmente
    NÃO qualificados (sem "@"), justamente o cenário em que o bug
    se manifestava — o fluxo real via ForecastEngine já usa
    producers totalmente qualificados (por isso o bug nunca afetou
    o cálculo real do Yield), mas a API pública de add_instance()
    não pode depender dessa convenção do chamador para estar
    correta.
"""

from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph


def make_definition(
    scope_type="linha",
    scope_value="L5",
    expression="VAR10001@L2",
):
    return EquationDefinition(
        equation_definition_id="EQ_CONSUMER",
        target_variable_id="VAR_C",
        version=1,
        scope_type=scope_type,
        scope_value=scope_value,
        expression=expression,
        source_reference="TEST",
        status="PUBLISHED",
    )


# ============================================================
# Teste 1 — referência explícita simples
# ============================================================


def test_1_explicit_simple_reference_uses_l2_producer_not_l5():
    definition = make_definition(expression="VAR10001@L2")

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            # Propositalmente SEM "@scope_type:scope_value" — o
            # cenário em que o bug se manifestava.
            "VAR10001@L2": "EQ_PRODUCER_L2",
            "VAR10001@L5": "EQ_PRODUCER_L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies("EQ_CONSUMER@linha:L5")

    assert dependencies == {"EQ_PRODUCER_L2@linha:L2"}
    assert "EQ_PRODUCER_L2@linha:L5" not in dependencies
    assert "EQ_PRODUCER_L5@linha:L5" not in dependencies


# ============================================================
# Teste 2 — duas referências explicitamente escopadas
#            (o teste arquitetural mais importante)
# ============================================================


def test_2_two_explicit_references_never_collapse_to_instance_scope():
    definition = make_definition(
        expression="VAR10001@L2 + VAR10001@L3",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR10001@L2": "EQ_PRODUCER_L2",
            "VAR10001@L3": "EQ_PRODUCER_L3",
            "VAR10001@L5": "EQ_PRODUCER_L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies("EQ_CONSUMER@linha:L5")

    assert dependencies == {
        "EQ_PRODUCER_L2@linha:L2",
        "EQ_PRODUCER_L3@linha:L3",
    }

    assert "EQ_PRODUCER_L2@linha:L5" not in dependencies
    assert "EQ_PRODUCER_L3@linha:L5" not in dependencies
    assert "EQ_PRODUCER_L5@linha:L5" not in dependencies


# ============================================================
# Teste 3 — referência implícita continua contextual
# ============================================================


def test_3_implicit_reference_still_uses_instance_scope():
    definition = make_definition(expression="VAR10001")

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR10001@L2": "EQ_PRODUCER_L2",
            "VAR10001@L5": "EQ_PRODUCER_L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies("EQ_CONSUMER@linha:L5")

    assert dependencies == {"EQ_PRODUCER_L5@linha:L5"}
    assert "EQ_PRODUCER_L2@linha:L2" not in dependencies


# ============================================================
# Teste 4 — expressão mista (explícita + implícita)
# ============================================================


def test_4_mixed_explicit_and_implicit_in_same_expression():
    definition = make_definition(
        expression="VAR10001@L2 + VAR10002",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR10001@L2": "EQ_PRODUCER_VAR10001_L2",
            "VAR10002@L5": "EQ_PRODUCER_VAR10002_L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies("EQ_CONSUMER@linha:L5")

    assert dependencies == {
        "EQ_PRODUCER_VAR10001_L2@linha:L2",
        "EQ_PRODUCER_VAR10002_L5@linha:L5",
    }


# ============================================================
# Teste 5 — parâmetros (não apenas VAR)
# ============================================================


def test_5_explicit_parameter_reference_is_also_preserved():
    definition = make_definition(expression="PARAM10001@L2")

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "PARAM10001@L2": "EQ_PRODUCER_PARAM_L2",
            "PARAM10001@L5": "EQ_PRODUCER_PARAM_L5",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies("EQ_CONSUMER@linha:L5")

    assert dependencies == {"EQ_PRODUCER_PARAM_L2@linha:L2"}
    assert "EQ_PRODUCER_PARAM_L5@linha:L5" not in dependencies


# ============================================================
# Teste 6 — linha_grupo continua funcionando
# ============================================================


def test_6_linha_grupo_aggregation_still_works():
    definition = EquationDefinition(
        equation_definition_id="EQ_GROUP",
        target_variable_id="VAR_GROUP",
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

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR10001@L1": "EQ_PRODUCER_L1",
            "VAR10001@L2": "EQ_PRODUCER_L2",
            "VAR10001@L3": "EQ_PRODUCER_L3",
        },
        extractor=DependencyExtractor(),
    )

    dependencies = graph.get_dependencies(
        "EQ_GROUP@linha_grupo:L1_L3"
    )

    assert dependencies == {
        "EQ_PRODUCER_L1@linha:L1",
        "EQ_PRODUCER_L2@linha:L2",
        "EQ_PRODUCER_L3@linha:L3",
    }


# ============================================================
# Teste 7 — estrutura do nó de dependência (não só o resultado)
# ============================================================


def test_7_dependency_node_structure_never_encodes_instance_scope():
    definition = make_definition(
        expression="VAR10001@L2 + VAR10001@L3",
    )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha",
        scope_value="L5",
    )

    graph = DependencyGraph()

    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers={
            "VAR10001@L2": "EQ_PRODUCER_L2",
            "VAR10001@L3": "EQ_PRODUCER_L3",
        },
        extractor=DependencyExtractor(),
    )

    all_nodes = graph.get_equations()

    # Os nós criados para os produtores devem existir qualificados
    # por L2 e L3 — nunca por L5 (o escopo da instance consumidora).
    assert "EQ_PRODUCER_L2@linha:L2" in all_nodes
    assert "EQ_PRODUCER_L3@linha:L3" in all_nodes

    assert "EQ_PRODUCER_L2@linha:L5" not in all_nodes
    assert "EQ_PRODUCER_L3@linha:L5" not in all_nodes
    assert "linha:L5" not in "".join(
        node
        for node in all_nodes
        if node.startswith("EQ_PRODUCER")
    )
