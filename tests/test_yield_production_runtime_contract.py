"""
Validação runtime dos 8 pontos de contato reais Yield -> Production:

    EQ12003 (yield_lth_total, linha_grupo/L1_L7)
    EQ12006 (pick_up L1)
    EQ12007 (pick_up L2)
    EQ12008 (pick_up L3)
    EQ12009 (pick_up L4)
    EQ12010 (pick_up L5)
    EQ12011 (pick_up L6)
    EQ12012 (pick_up L7)

Todos referenciam VAR11001 ("yield", produzido por EQ11001 do bloco
Yield) via sintaxe explícita `@Lx`.

Contrato provado por cada teste (não apenas por chamada isolada):

    SeedLoader (real)
        -> EquationDefinitionRegistry (subconjunto: só os IDs sob
           teste, mas objetos EquationDefinition REAIS do seed)
        -> ForecastEngine.calculate_from_definition_registry
               -> materialize_equation (ScopeResolver real)
               -> DependencyGraph.add_instance (real, a partir das
                  referências REAIS extraídas da expressão)
               -> DependencyResolver.resolve (ordem topológica real)
               -> EquationEngine.calculate_instance (real,
                  ExpressionEvaluator real)
               -> calculation_context.set_variable_value (o MESMO
                  CalculationContext usado tanto por Yield quanto
                  por Production)
        -> resultado

Em nenhum teste desta suíte o código injeta manualmente um valor de
VAR11001 ("yield") no CalculationContext: esse valor só pode chegar
lá através da própria execução de EQ11001 pelo ForecastEngine. Os
valores "expected" de Production são recalculados de forma
independente (a partir dos inputs brutos e da fórmula documentada no
seed), nunca reaproveitando o retorno do ExpressionEvaluator.

Não altera seeds, não altera código de produção.
"""

from pathlib import Path

import pytest

from app.domain.equations.registry import EquationDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver
from app.engine.forecast_engine import ForecastEngine
from app.repositories.seed_loader import SeedLoader

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


@pytest.fixture(scope="module")
def loaded_seed():
    loader = SeedLoader(SEED_ROOT)
    return loader.load_all_definitions_and_instances()


@pytest.fixture(scope="module")
def registries(loaded_seed):
    (
        var_defs, var_instances,
        param_defs, param_instances,
        eq_defs, eq_instances,
    ) = loaded_seed
    return {
        "var_defs": var_defs,
        "var_instances": var_instances,
        "param_defs": param_defs,
        "param_instances": param_instances,
        "eq_defs": eq_defs,
        "eq_instances": eq_instances,
    }


def _subset_registry(eq_defs, equation_ids):
    """
    Constrói um EquationDefinitionRegistry contendo SOMENTE os
    EquationDefinition reais (do seed carregado) cujos ids estão em
    `equation_ids`. Os objetos em si não são recriados/alterados.
    """

    subset = EquationDefinitionRegistry()

    for equation_id in equation_ids:
        subset.add(eq_defs.get(equation_id))

    return subset


def _real_param_value(param_instances, parameter_definition_id, scope_value):
    """
    Lê o valor REAL já carregado do seed para um Parameter em um
    scope_value específico de linha -- nunca inventa um valor.
    """

    for instance in param_instances.all():
        if (
            instance.parameter_definition_id == parameter_definition_id
            and instance.scope_type == "linha"
            and instance.scope_value == scope_value
        ):
            return instance.value

    raise AssertionError(
        f"Nenhuma ParameterInstance real encontrada para "
        f"{parameter_definition_id}/linha/{scope_value}"
    )


def _expected_yield(VAR11006, VAR11008, VAR11240, VAR11007):
    """
    Fórmula documentada de EQ11001 (yield), calculada
    independentemente do ExpressionEvaluator:

        (VAR11006 - VAR11008) * VAR11240 - 0.654 * VAR11007
    """

    return (VAR11006 - VAR11008) * VAR11240 - 0.654 * VAR11007


YIELD_INPUTS = {
    # valores distintivos por linha (nenhum padrão repetido), para
    # que seja impossível confundir o valor de uma linha com o de
    # outra caso o mecanismo resolvesse o scope errado.
    "L1": dict(VAR11006=101.0, VAR11008=5.1, VAR11240=201.0, VAR11007=3.1),
    "L2": dict(VAR11006=112.0, VAR11008=5.2, VAR11240=202.0, VAR11007=3.2),
    "L3": dict(VAR11006=123.0, VAR11008=5.3, VAR11240=203.0, VAR11007=3.3),
    "L4": dict(VAR11006=134.0, VAR11008=5.4, VAR11240=204.0, VAR11007=3.4),
    "L5": dict(VAR11006=145.0, VAR11008=5.5, VAR11240=205.0, VAR11007=3.5),
    "L6": dict(VAR11006=156.0, VAR11008=5.6, VAR11240=206.0, VAR11007=3.6),
    "L7": dict(VAR11006=167.0, VAR11008=5.7, VAR11240=207.0, VAR11007=3.7),
}

# "lth" (VAR12016) é entrada independente da Production (não deriva
# de Yield -- confirmado no workbook Yield, onde "lth" é ele mesmo
# listado como "entrada"). Valores sintéticos distintivos.
LTH_INPUTS = {
    "L1": 900.0, "L2": 910.0, "L3": 920.0, "L4": 930.0,
    "L5": 940.0, "L6": 950.0, "L7": 960.0,
}


ALL_LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]


def _populate_yield_inputs(ctx, lines=ALL_LINES):
    """
    EQ11001 tem scope de Definition `linha/L1_L7`: o ScopeResolver
    sempre materializa as 7 EquationInstances (L1..L7), mesmo quando
    o teste só precisa do resultado de um subconjunto de linhas para
    validar uma equação Production específica. Por isso os inputs de
    TODAS as 7 linhas devem estar presentes no contexto sempre que
    EQ11001 fizer parte do subset registry -- caso contrário a
    própria instância Yield de uma linha não usada falha por falta
    de input, antes mesmo de chegar à equação Production sob teste.
    """

    for line in lines:
        for var_id, value in YIELD_INPUTS[line].items():
            ctx.set_variable_value(var_id, value, "linha", line)


def _run_engine(eq_defs, equation_ids, ctx):
    subset = _subset_registry(eq_defs, equation_ids)
    engine = ForecastEngine()
    return engine.calculate_from_definition_registry(
        equation_definition_registry=subset,
        calculation_context=ctx,
    )


# ============================================================
# Estrutura (A): Definition / Instance / referências / scopes
# ============================================================


@pytest.mark.parametrize(
    "equation_id,expected_target,expected_scope_type,expected_scope_value",
    [
        ("EQ12003", "VAR12021", "linha_grupo", "L1_L7"),
        ("EQ12006", "VAR12029", "linha", "L1"),
        ("EQ12007", "VAR12030", "linha", "L2"),
        ("EQ12008", "VAR12031", "linha", "L3"),
        ("EQ12009", "VAR12032", "linha", "L4"),
        ("EQ12010", "VAR12033", "linha", "L5"),
        ("EQ12011", "VAR12034", "linha", "L6"),
        ("EQ12012", "VAR12035", "linha", "L7"),
    ],
)
def test_structure_definition_and_instance(
    registries, equation_id, expected_target,
    expected_scope_type, expected_scope_value,
):
    eq_defs = registries["eq_defs"]
    eq_instances = registries["eq_instances"]

    definition = eq_defs.get(equation_id)
    assert definition is not None, f"{equation_id}: Definition ausente"
    assert definition.target_variable_id == expected_target
    assert definition.scope_type == expected_scope_type
    assert definition.scope_value == expected_scope_value
    assert "VAR11001@" in definition.expression

    matching_instances = [
        i for i in eq_instances.all()
        if i.equation_definition_id == equation_id
    ]
    assert len(matching_instances) == 1, (
        f"{equation_id}: esperada exatamente 1 EquationInstance, "
        f"encontradas {len(matching_instances)}"
    )
    assert matching_instances[0].scope_type == expected_scope_type
    assert matching_instances[0].scope_value == expected_scope_value


# ============================================================
# Grafo (B): dependência Yield -> Production representada
# ============================================================


@pytest.mark.parametrize(
    "equation_id,yield_lines",
    [
        ("EQ12003", ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]),
        ("EQ12006", ["L1", "L2", "L3"]),
        ("EQ12007", ["L1", "L2", "L3"]),
        ("EQ12008", ["L1", "L2", "L3"]),
        ("EQ12009", ["L4", "L5"]),
        ("EQ12010", ["L4", "L5"]),
        ("EQ12011", ["L6", "L7"]),
        ("EQ12012", ["L6", "L7"]),
    ],
)
def test_dependency_graph_edge_and_order(
    registries, equation_id, yield_lines,
):
    eq_defs = registries["eq_defs"]
    eq_instances = registries["eq_instances"]

    yield_def = eq_defs.get("EQ11001")
    prod_def = eq_defs.get(equation_id)

    yield_instances = {
        i.scope_value: i for i in eq_instances.all()
        if i.equation_definition_id == "EQ11001"
    }
    prod_instance = next(
        i for i in eq_instances.all()
        if i.equation_definition_id == equation_id
    )

    variable_producers = {
        f"{yield_def.target_variable_id}@{line}": (
            f"EQ11001@linha:{line}"
        )
        for line in yield_lines
    }

    extractor = DependencyExtractor()
    graph = DependencyGraph()

    for line in yield_lines:
        graph.add_instance(
            instance=yield_instances[line],
            definition=yield_def,
            variable_producers=variable_producers,
            extractor=extractor,
        )

    graph.add_instance(
        instance=prod_instance,
        definition=prod_def,
        variable_producers=variable_producers,
        extractor=extractor,
    )

    prod_node = f"{equation_id}@{prod_instance.scope_type}:{prod_instance.scope_value}"
    yield_nodes = {
        f"EQ11001@{yield_instances[line].scope_type}:{line}"
        for line in yield_lines
    }

    assert prod_node in graph._dependencies
    assert graph._dependencies[prod_node] == yield_nodes, (
        f"{equation_id}: aresta esperada para {yield_nodes}, "
        f"encontrada {graph._dependencies[prod_node]}"
    )

    order = DependencyResolver().resolve(graph)
    prod_index = order.index(prod_node)
    yield_indices = [order.index(n) for n in yield_nodes]

    assert all(i < prod_index for i in yield_indices), (
        f"{equation_id}: ordem topológica não coloca todos os "
        f"produtores Yield antes de Production: order={order}"
    )


# ============================================================
# Runtime + valor (C, D): execução real via ForecastEngine
# ============================================================


def test_eq12003_runtime_weighted_by_lth(registries):
    eq_defs = registries["eq_defs"]

    lines = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
    ctx = CalculationContext()
    _populate_yield_inputs(ctx, lines)

    for line in lines:
        ctx.set_variable_value("VAR12016", LTH_INPUTS[line], "linha", line)

    results = _run_engine(eq_defs, ["EQ11001", "EQ12003"], ctx)

    expected_yield = {
        line: _expected_yield(**YIELD_INPUTS[line]) for line in lines
    }

    for line in lines:
        yield_node = f"EQ11001@v1@{line}"
        assert yield_node in results, f"resultado Yield ausente para {line}"
        assert results[yield_node] == pytest.approx(
            expected_yield[line], rel=1e-9,
        ), f"Yield@{line}: engine={results[yield_node]} expected={expected_yield[line]}"

    numerator = sum(
        expected_yield[line] * LTH_INPUTS[line] for line in lines
    )
    denominator = sum(LTH_INPUTS[line] for line in lines)
    expected_prod = numerator / denominator

    prod_node = "EQ12003@v1@L1_L7"
    assert prod_node in results, "resultado Production (EQ12003) ausente"

    actual_prod = results[prod_node]
    diff = abs(actual_prod - expected_prod)

    print(
        "\nEQ12003: yield_input(por linha)=", YIELD_INPUTS,
        "\n  lth_input=", LTH_INPUTS,
        "\n  expected_yield=", expected_yield,
        "\n  expected_production=", expected_prod,
        "\n  actual_production=", actual_prod,
        "\n  diff=", diff,
    )

    assert actual_prod == pytest.approx(expected_prod, rel=1e-9), (
        f"EQ12003: engine={actual_prod} expected={expected_prod} diff={diff}"
    )

    # Causalidade / não-falso-positivo: o único jeito de VAR11001@Lx
    # existir no CalculationContext é a própria execução de EQ11001
    # pelo ForecastEngine -- este teste nunca chama
    # ctx.set_variable_value("VAR11001", ...) diretamente.
    for line in lines:
        stored = ctx.get_variable_value(
            "VAR11001", scope_type="linha", scope_value=line,
        )
        assert stored == pytest.approx(expected_yield[line], rel=1e-9)


PICK_UP_CASES = [
    ("EQ12006", "L1", ["L1", "L2", "L3"]),
    ("EQ12007", "L2", ["L1", "L2", "L3"]),
    ("EQ12008", "L3", ["L1", "L2", "L3"]),
    ("EQ12009", "L4", ["L4", "L5"]),
    ("EQ12010", "L5", ["L4", "L5"]),
    ("EQ12011", "L6", ["L6", "L7"]),
    ("EQ12012", "L7", ["L6", "L7"]),
]


@pytest.mark.parametrize("equation_id,target_line,yield_lines", PICK_UP_CASES)
def test_pick_up_runtime_contract(
    registries, equation_id, target_line, yield_lines,
):
    eq_defs = registries["eq_defs"]
    param_instances = registries["param_instances"]

    ctx = CalculationContext()
    _populate_yield_inputs(ctx)

    pick_up_yield_value = _real_param_value(
        param_instances, "PARAM12002", target_line,
    )
    ctx.set_parameter_value(
        "PARAM12002", pick_up_yield_value, "linha", target_line,
    )

    results = _run_engine(eq_defs, ["EQ11001", equation_id], ctx)

    expected_yield = {
        line: _expected_yield(**YIELD_INPUTS[line]) for line in yield_lines
    }

    for line in yield_lines:
        yield_node = f"EQ11001@v1@{line}"
        assert yield_node in results
        assert results[yield_node] == pytest.approx(
            expected_yield[line], rel=1e-9,
        )

    expected_prod = (
        sum(expected_yield[line] for line in yield_lines) / len(yield_lines)
    ) + pick_up_yield_value

    prod_node = f"{equation_id}@v1@{target_line}"
    assert prod_node in results, f"resultado Production ausente para {equation_id}"

    actual_prod = results[prod_node]
    diff = abs(actual_prod - expected_prod)

    print(
        f"\n{equation_id}@{target_line}: yield_lines={yield_lines}",
        "\n  expected_yield=", expected_yield,
        "\n  pick_up_yield(real seed)=", pick_up_yield_value,
        "\n  expected_production=", expected_prod,
        "\n  actual_production=", actual_prod,
        "\n  diff=", diff,
    )

    assert actual_prod == pytest.approx(expected_prod, rel=1e-9), (
        f"{equation_id}: engine={actual_prod} expected={expected_prod} diff={diff}"
    )


# ============================================================
# Teste de perturbação / causalidade (seção 8)
# ============================================================


def test_perturbation_propagates_only_to_dependent_production_equations(
    registries,
):
    """
    Altera SOMENTE o input de Yield para L1 e confirma:

      1. o resultado Yield@L1 muda de acordo com a fórmula;
      2. EQ12006 (depende de L1,L2,L3) muda de acordo;
      3. EQ12009 (depende de L4,L5 -- NÃO de L1) permanece
         inalterado, provando que a propagação é precisa e não um
         efeito colateral genérico.
    """

    eq_defs = registries["eq_defs"]
    param_instances = registries["param_instances"]

    pick_up_l1 = _real_param_value(param_instances, "PARAM12002", "L1")
    pick_up_l4 = _real_param_value(param_instances, "PARAM12002", "L4")

    def run_scenario(var11006_l1):
        ctx = CalculationContext()
        _populate_yield_inputs(ctx)
        # overriding apenas o input bruto de L1 (nunca o resultado)
        overrides = dict(YIELD_INPUTS["L1"])
        overrides["VAR11006"] = var11006_l1
        ctx.set_variable_value("VAR11006", var11006_l1, "linha", "L1")
        ctx.set_parameter_value("PARAM12002", pick_up_l1, "linha", "L1")
        ctx.set_parameter_value("PARAM12002", pick_up_l4, "linha", "L4")

        results = _run_engine(
            eq_defs, ["EQ11001", "EQ12006", "EQ12009"], ctx,
        )
        return results, overrides

    results_1, overrides_1 = run_scenario(101.0)
    results_2, overrides_2 = run_scenario(999.0)

    yield_l1_1 = results_1["EQ11001@v1@L1"]
    yield_l1_2 = results_2["EQ11001@v1@L1"]

    expected_yield_l1_1 = _expected_yield(**overrides_1)
    expected_yield_l1_2 = _expected_yield(**overrides_2)

    assert yield_l1_1 == pytest.approx(expected_yield_l1_1, rel=1e-9)
    assert yield_l1_2 == pytest.approx(expected_yield_l1_2, rel=1e-9)
    assert yield_l1_1 != pytest.approx(yield_l1_2, rel=1e-6), (
        "Perturbação não alterou o resultado Yield@L1 -- teste inválido"
    )

    pick_up_l1_1 = results_1["EQ12006@v1@L1"]
    pick_up_l1_2 = results_2["EQ12006@v1@L1"]

    expected_pick_up_1 = (
        expected_yield_l1_1
        + _expected_yield(**YIELD_INPUTS["L2"])
        + _expected_yield(**YIELD_INPUTS["L3"])
    ) / 3 + pick_up_l1
    expected_pick_up_2 = (
        expected_yield_l1_2
        + _expected_yield(**YIELD_INPUTS["L2"])
        + _expected_yield(**YIELD_INPUTS["L3"])
    ) / 3 + pick_up_l1

    assert pick_up_l1_1 == pytest.approx(expected_pick_up_1, rel=1e-9)
    assert pick_up_l1_2 == pytest.approx(expected_pick_up_2, rel=1e-9)
    assert pick_up_l1_1 != pytest.approx(pick_up_l1_2, rel=1e-6), (
        "EQ12006 não reagiu à mudança de Yield@L1 -- causalidade não provada"
    )

    # Controle negativo: EQ12009 (L4/L5) não depende de L1, deve ser
    # idêntico nos dois cenários.
    pick_up_l4_1 = results_1["EQ12009@v1@L4"]
    pick_up_l4_2 = results_2["EQ12009@v1@L4"]

    assert pick_up_l4_1 == pytest.approx(pick_up_l4_2, rel=1e-12), (
        "EQ12009 (independente de L1) mudou entre os cenários -- "
        "propagação incorreta/vazamento de escopo"
    )

    print(
        "\nPerturbação: Yield@L1 mudou de", yield_l1_1, "para", yield_l1_2,
        "\n  EQ12006@L1 mudou de", pick_up_l1_1, "para", pick_up_l1_2,
        "(causalidade confirmada)",
        "\n  EQ12009@L4 permaneceu", pick_up_l4_1, "==", pick_up_l4_2,
        "(controle negativo confirmado)",
    )
