"""
Contrato estrutural do bloco `energy`.

Valida, contra os Registries REAIS carregados por `SeedLoader`, que os
seeds gerados a partir do workbook v2 respeitam:

    - as contagens declaradas (57 entidades = 53 Variables + 4
      Parameters; 25 Equations; 11 AggregationRules — energy v9,
      Stage 5A: + `retirada_total_condensado_area13` e a equação de
      `evaporado_total_evaporacao`);
    - a faixa de IDs reservada ao bloco (18000-18999), sem colisão com
      qualquer outro bloco;
    - unidades, frequências, variable_types e escopos permitidos,
      incluindo a unidade `GJ/t` introduzida por este bloco;
    - a materialização de Definitions em Instances pelo ScopeResolver
      real (nenhum escopo é expandido "na mão" pelo teste);
    - o parsing das 24 expressões pelo ExpressionParser real e a
      extração de dependências pelo DependencyExtractor real,
      incluindo as referências espaciais explícitas `@Lx`;
    - os DOIS ramos da condicional de EQ18003 (delta_t_regenerativo).

Não altera seeds nem código de produção.
"""

from pathlib import Path

import pytest

from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.repositories.seed_loader import SeedLoader
from app.validation import parameter_seed_validator
from app.validation import variable_seed_validator

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

ENERGY_RANGE = (18000, 18999)

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]


def _numeric_suffix(entity_id):
    return int("".join(ch for ch in entity_id if ch.isdigit()))


def _is_energy(entity_id):
    low, high = ENERGY_RANGE

    return low <= _numeric_suffix(entity_id) <= high


@pytest.fixture(scope="module")
def loaded_seed():
    return SeedLoader(SEED_ROOT).load_all_definitions_and_instances()


@pytest.fixture(scope="module")
def energy(loaded_seed):
    (
        var_defs, var_instances,
        param_defs, param_instances,
        eq_defs, eq_instances,
    ) = loaded_seed

    rules = SeedLoader(SEED_ROOT).load_aggregation_rules()

    return {
        "var_defs": [
            d for d in var_defs.all()
            if _is_energy(d.variable_definition_id)
        ],
        "var_instances": [
            i for i in var_instances.all()
            if _is_energy(i.variable_definition_id)
        ],
        "param_defs": [
            d for d in param_defs.all()
            if _is_energy(d.parameter_definition_id)
        ],
        "param_instances": [
            i for i in param_instances.all()
            if _is_energy(i.parameter_definition_id)
        ],
        "eq_defs": [
            d for d in eq_defs.all()
            if _is_energy(d.equation_definition_id)
        ],
        "eq_instances": [
            i for i in eq_instances.all()
            if _is_energy(i.equation_definition_id)
        ],
        "rules": [
            r for r in rules.all()
            if r.aggregation_rule_id.startswith("AGR-ENERGY-")
        ],
    }


# ============================================================
# Contagens
# ============================================================


def test_entity_counts_match_the_workbook(energy):
    """
    57 linhas de dados da aba `energy` -> 53 Variables + 4 Parameters.
    A aba `Planilha1` é auxiliar e não gera nenhuma entidade.
    Stage 5A (energy v9): 52 -> 53 variáveis (+ `retirada_total_condensado_area13`).
    """

    assert len(energy["var_defs"]) == 53
    assert len(energy["param_defs"]) == 4
    assert len(energy["var_defs"]) + len(energy["param_defs"]) == 57


def test_equation_and_aggregation_counts(energy):
    # Stage 5A (energy v9): 24 -> 25 equações (`evaporado_total_evaporacao` passa a calculada).
    assert len(energy["eq_defs"]) == 25
    assert len(energy["rules"]) == 11


# ============================================================
# IDs
# ============================================================


def test_all_ids_are_inside_the_energy_range_and_unique(energy):
    variable_ids = [
        d.variable_definition_id for d in energy["var_defs"]
    ]
    parameter_ids = [
        d.parameter_definition_id for d in energy["param_defs"]
    ]
    equation_ids = [
        d.equation_definition_id for d in energy["eq_defs"]
    ]

    # Stage 5A: com o livro de IDs (2.6B/D-5A-4) a variável nova recebe o número seguinte ao maior
    # emitido (VAR18053) e fica na posição da sua linha no workbook; a lista de variáveis deixa de
    # ser crescente, mas continua única e contígua, sem buraco nem renumeração. As equações saem em
    # ordem crescente de EQ (DR-5A-1).
    assert len(variable_ids) == len(set(variable_ids))
    assert sorted(variable_ids) == [f"VAR180{n:02d}" for n in range(1, 54)]
    assert variable_ids[-1] == "VAR18052" and "VAR18053" in variable_ids
    assert parameter_ids == sorted(set(parameter_ids))
    assert equation_ids == sorted(set(equation_ids))

    assert variable_ids[0] == "VAR18001"
    assert parameter_ids == [f"PARAM1800{n}" for n in range(1, 5)]
    assert equation_ids == [f"EQ180{n:02d}" for n in range(1, 26)]

    for entity_id in variable_ids + parameter_ids + equation_ids:
        assert _is_energy(entity_id), entity_id


def test_energy_ids_do_not_collide_with_other_blocks(loaded_seed):
    """
    Os ids do bloco energy não podem existir em nenhum outro bloco: a
    verificação é feita sobre o Registry COMPLETO (todos os blocos
    carregados juntos), não sobre o seed do energy isolado.
    """

    var_defs, _vi, param_defs, _pi, eq_defs, _ei = loaded_seed

    all_variable_ids = [
        d.variable_definition_id for d in var_defs.all()
    ]
    all_parameter_keys = [
        (d.parameter_definition_id, d.scope_type, d.scope_value)
        for d in param_defs.all()
    ]
    all_equation_keys = [
        (d.equation_definition_id, d.scope_type, d.scope_value)
        for d in eq_defs.all()
    ]

    # VariableDefinitionRegistry indexa só por id; os outros dois
    # indexam por (id, version, scope) -- um mesmo PARAM12001 existe
    # legitimamente uma vez por linha no bloco production. Por isso a
    # unicidade é verificada na chave real de cada Registry.
    assert len(all_variable_ids) == len(set(all_variable_ids))
    assert len(all_parameter_keys) == len(set(all_parameter_keys))
    assert len(all_equation_keys) == len(set(all_equation_keys))

    assert sum(1 for i in all_variable_ids if _is_energy(i)) == 53      # 5A: 52 -> 53
    assert sum(
        1 for i, _t, _v in all_parameter_keys if _is_energy(i)
    ) == 4
    assert sum(
        1 for i, _t, _v in all_equation_keys if _is_energy(i)
    ) == 25                                                             # 5A: 24 -> 25


# ============================================================
# Unidades
# ============================================================


def test_units_are_exactly_the_seven_units_of_the_workbook(energy):
    units = {d.unit for d in energy["var_defs"]}
    units |= {d.unit for d in energy["param_defs"]}

    # energy v5 (workbook aprovado) grafa a produção em "t/d" (v2: "tpd").
    assert units == {"-", "t/h", "°C", "GJ/t", "g/l", "m³/h", "t/d"}


def test_every_energy_unit_is_allowed_by_both_validators(energy):
    """
    Pós-condição exigida pela auditoria: o conjunto de unidades usadas
    pelo bloco menos ALLOWED_UNITS deve ser vazio, nos DOIS validators.
    """

    units = {d.unit for d in energy["var_defs"]}
    units |= {d.unit for d in energy["param_defs"]}

    assert units - variable_seed_validator.ALLOWED_UNITS == set()
    assert units - parameter_seed_validator.ALLOWED_UNITS == set()


def test_gj_per_tonne_is_used_by_exactly_the_seven_energy_variables(
    energy,
):
    gj = [
        d.variable_name
        for d in energy["var_defs"]
        if d.unit == "GJ/t"
    ]

    assert sorted(gj) == [
        "energia_bayer",
        "energia_bayer",
        "energia_digestao",
        "energia_digestao",
        "energia_evaporacao",
        "energia_evaporacao",
        "energia_media_frct",
    ]


# ============================================================
# Frequências, variable_type, escopos
# ============================================================


def test_variable_frequency_distribution(energy):
    counts = {}

    for definition in energy["var_defs"]:
        counts[definition.frequency] = (
            counts.get(definition.frequency, 0) + 1
        )

    # 5A (energy v9): diário 33 -> 34 (`retirada_total_condensado_area13`).
    assert counts == {"diário": 34, "mensal": 18, "anual": 1}


def test_variable_type_distribution(energy):
    counts = {}

    for definition in energy["var_defs"]:
        counts[definition.variable_type] = (
            counts.get(definition.variable_type, 0) + 1
        )

    # 5A (energy v9): `evaporado_total_evaporacao` entrada_externa -> calculado (35 -> 36);
    # `retirada_total_condensado_area13` é a nova entrada_externa (6 -> 6).
    assert counts == {
        "calculado": 36,
        "entrada": 11,
        "entrada_externa": 6,
    }


def test_scope_distribution(energy):
    counts = {}

    for definition in energy["var_defs"]:
        key = (definition.scope_type, definition.scope_value)
        counts[key] = counts.get(key, 0) + 1

    # 5A (energy v9): linha/L1_L7 20 -> 21 (`retirada_total_condensado_area13`).
    assert counts == {
        ("linha", "L1_L7"): 21,
        ("linha_grupo", "L1_L7"): 29,
        ("linha_grupo", "L1_L3"): 1,
        ("linha_grupo", "L4_L5"): 1,
        ("linha_grupo", "L6_L7"): 1,
    }


def test_parameter_scopes(energy):
    scopes = {
        d.parameter_name: (d.scope_type, d.scope_value)
        for d in energy["param_defs"]
    }

    assert scopes == {
        "temperatura_lp_referencia": ("linha", "L1_L7"),
        "fator_ajuste_delta_t_reg": ("linha", "L1_L7"),
        "fator_ajuste_delta_t_vapor_vivo": ("linha", "L1_L7"),
        "delta_t_vapor_vivo_maximo": ("linha_grupo", "L1_L7"),
    }


def test_lth_meta_stays_a_variable(energy):
    """
    `lth_meta` é Variable anual em linha/L1_L7, com fonte no bloco
    production -- nunca um Parameter. O
    `VariableDefinitionRegistry` indexa apenas por
    `variable_definition_id`, então conviver com o `lth_meta` de outro
    bloco é suportado.
    """

    matches = [
        d for d in energy["var_defs"]
        if d.variable_name == "lth_meta"
    ]

    assert len(matches) == 1

    definition = matches[0]

    assert definition.frequency == "anual"
    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"
    assert definition.unit == "-"
    assert definition.variable_type == "entrada"


def test_especifico_vapor_evaporacao_keeps_its_four_scopes(energy):
    scopes = sorted(
        (d.scope_type, d.scope_value)
        for d in energy["var_defs"]
        if d.variable_name == "especifico_vapor_evaporacao"
    )

    assert scopes == [
        ("linha", "L1_L7"),
        ("linha_grupo", "L1_L3"),
        ("linha_grupo", "L4_L5"),
        ("linha_grupo", "L6_L7"),
    ]


# ============================================================
# Instances (ScopeResolver real)
# ============================================================


def test_variable_instances_are_materialized_by_the_real_resolver(
    energy,
):
    """
    21 Definitions em linha/L1_L7 -> 7 instâncias cada = 147;
    32 Definitions em linha_grupo -> 1 instância cada = 32.
    Total 179 (5A: 172 -> 179, + `retirada_total_condensado_area13` em
    linha/L1_L7). O teste não expande escopo nenhum: apenas confere o que
    o ScopeResolver real produziu.
    """

    assert len(energy["var_instances"]) == 179

    by_definition = {}

    for instance in energy["var_instances"]:
        by_definition.setdefault(
            instance.variable_definition_id, []
        ).append(instance)

    for definition in energy["var_defs"]:
        instances = by_definition[definition.variable_definition_id]

        if definition.scope_type == "linha":
            assert sorted(i.scope_value for i in instances) == LINES
        else:
            assert len(instances) == 1
            assert instances[0].scope_value == definition.scope_value


def test_parameter_instances_are_materialized(energy):
    """
    3 Parameters em linha/L1_L7 -> 7 instâncias cada = 21;
    1 Parameter em linha_grupo/L1_L7 -> 1 instância. Total 22.
    """

    assert len(energy["param_instances"]) == 22


def test_equation_instances_are_materialized(energy):
    """
    As 24 EquationDefinitions: as de linha/L1_L7 geram 7 instâncias,
    as de linha_grupo geram 1.
    """

    by_definition = {}

    for instance in energy["eq_instances"]:
        by_definition.setdefault(
            instance.equation_definition_id, []
        ).append(instance)

    expected_total = 0

    for definition in energy["eq_defs"]:
        instances = by_definition[definition.equation_definition_id]

        if definition.scope_type == "linha":
            assert sorted(i.scope_value for i in instances) == LINES
            expected_total += 7
        else:
            assert len(instances) == 1
            expected_total += 1

    assert len(energy["eq_instances"]) == expected_total


def test_every_equation_targets_an_energy_variable_definition(energy):
    variable_ids = {
        d.variable_definition_id for d in energy["var_defs"]
    }

    for definition in energy["eq_defs"]:
        assert definition.target_variable_id in variable_ids, (
            f"{definition.equation_definition_id}: alvo "
            f"{definition.target_variable_id} fora do bloco energy"
        )

    targets = [d.target_variable_id for d in energy["eq_defs"]]

    assert len(targets) == len(set(targets))


# ============================================================
# Expressões: parsing e dependências
# ============================================================


def test_all_24_expressions_parse(energy):
    parser = ExpressionParser()

    for definition in energy["eq_defs"]:
        parser.parse(definition.expression)


def test_all_referenced_ids_exist_in_the_registries(energy, loaded_seed):
    var_defs, _vi, param_defs, _pi, _ed, _ei = loaded_seed

    extractor = DependencyExtractor()

    for definition in energy["eq_defs"]:
        dependencies = extractor.extract(definition.expression)

        for reference in dependencies.variables:
            base = reference.split("@")[0]
            assert var_defs.get(base) is not None, (
                f"{definition.equation_definition_id}: {reference}"
            )

        for reference in dependencies.parameters:
            base = reference.split("@")[0]
            assert any(
                d.parameter_definition_id == base
                for d in param_defs.all()
            ), f"{definition.equation_definition_id}: {reference}"


def test_explicit_scoped_references_are_extracted(energy):
    """
    6 equações usam `@Lx`: as somas por linha (EQ18002, EQ18006,
    EQ18012), a média ponderada de digestão (EQ18008) e os três
    específicos de evaporação por grupo (EQ18014-EQ18016).
    """

    extractor = DependencyExtractor()

    scoped = {}

    for definition in energy["eq_defs"]:
        dependencies = extractor.extract(definition.expression)

        references = sorted(
            r for r in dependencies.variables if "@" in r
        )

        if references:
            scoped[definition.equation_definition_id] = references

    assert sorted(scoped) == [
        "EQ18002", "EQ18006", "EQ18008",
        "EQ18012", "EQ18014", "EQ18015", "EQ18016",
    ]

    assert scoped["EQ18002"] == [f"VAR18002@{line}" for line in LINES]
    assert scoped["EQ18015"] == [
        "VAR18002@L4", "VAR18002@L5",
        "VAR18032@L4", "VAR18032@L5",
    ]


def test_energia_bayer_and_energia_media_frct_bind_by_id_not_name(
    energy,
):
    """
    Regra de vínculo por ID: `energia_bayer` (diário) consome os IDs
    DIÁRIOS; `energia_media_frct` (mensal) consome os IDs MENSAIS de
    energia_digestao/energia_evaporacao. Os nomes são idênticos nos
    dois casos -- só o ID distingue.
    """

    by_id = {
        d.equation_definition_id: d for d in energy["eq_defs"]
    }

    variables = {
        d.variable_definition_id: d for d in energy["var_defs"]
    }

    assert by_id["EQ18019"].expression == "VAR18027 + VAR18040"
    assert by_id["EQ18020"].expression == "VAR18028 + VAR18041"

    assert variables["VAR18027"].variable_name == "energia_digestao"
    assert variables["VAR18027"].frequency == "diário"
    assert variables["VAR18040"].variable_name == "energia_evaporacao"
    assert variables["VAR18040"].frequency == "diário"

    assert variables["VAR18028"].variable_name == "energia_digestao"
    assert variables["VAR18028"].frequency == "mensal"
    assert variables["VAR18041"].variable_name == "energia_evaporacao"
    assert variables["VAR18041"].frequency == "mensal"

    assert variables["VAR18042"].frequency == "diário"
    assert variables["VAR18044"].frequency == "mensal"


# ============================================================
# EQ18003 — os DOIS ramos da condicional
# ============================================================


def _evaluate_delta_t_regenerativo(
    expression, temperatura_lp, referencia, inferior, superior, ajuste,
):
    ctx = CalculationContext()

    ctx.set_variable_value("VAR18012", temperatura_lp, "linha", "L1")
    ctx.set_variable_value("VAR18015", inferior, "linha", "L1")
    ctx.set_variable_value("VAR18016", superior, "linha", "L1")
    ctx.set_parameter_value("PARAM18001", referencia, "linha", "L1")
    ctx.set_parameter_value("PARAM18002", ajuste, "linha", "L1")

    evaluator = ExpressionEvaluator(
        calculation_context=ctx,
        default_scope_type="linha",
        default_scope_value="L1",
    )

    return evaluator.evaluate(ExpressionParser().parse(expression))


def test_eq18003_true_branch(energy):
    """
    temperatura_lp > temperatura_lp_referencia -> ramo do LIMITE
    INFERIOR. Os valores dos dois ramos são deliberadamente distintos
    para que o ramo errado nunca produza o mesmo número.
    """

    expression = next(
        d.expression for d in energy["eq_defs"]
        if d.equation_definition_id == "EQ18003"
    )

    result = _evaluate_delta_t_regenerativo(
        expression,
        temperatura_lp=80.0,
        referencia=72.0,
        inferior=40.0,
        superior=51.0,
        ajuste=1.5,
    )

    assert result == pytest.approx(41.5)


def test_eq18003_false_branch(energy):
    """
    temperatura_lp <= temperatura_lp_referencia -> ramo do LIMITE
    SUPERIOR.
    """

    expression = next(
        d.expression for d in energy["eq_defs"]
        if d.equation_definition_id == "EQ18003"
    )

    result = _evaluate_delta_t_regenerativo(
        expression,
        temperatura_lp=60.0,
        referencia=72.0,
        inferior=40.0,
        superior=51.0,
        ajuste=1.5,
    )

    assert result == pytest.approx(52.5)


def test_eq18003_boundary_is_not_strictly_greater(energy):
    """
    Na igualdade (temperatura_lp == referencia) a condição `>` é
    falsa: o ramo SUPERIOR vence. O teste fixa a semântica da
    fronteira, que uma troca acidental de `>` por `>=` quebraria.
    """

    expression = next(
        d.expression for d in energy["eq_defs"]
        if d.equation_definition_id == "EQ18003"
    )

    result = _evaluate_delta_t_regenerativo(
        expression,
        temperatura_lp=72.0,
        referencia=72.0,
        inferior=40.0,
        superior=51.0,
        ajuste=1.5,
    )

    assert result == pytest.approx(52.5)


def test_evaporado_total_evaporacao_is_the_condensate_withdrawal_over_its_specific_volume(energy):
    """
    Stage 5A (energy v9): `evaporado_total_evaporacao` (VAR18031) deixa de ser entrada vinda do
    area_04_13 e passa a calculada = `retirada_total_condensado_area13` / 1 (volume específico do
    condensado). A entrada nova (VAR18053, m³/h) é a que vem do area_04_13.
    """

    variables = {d.variable_definition_id: d for d in energy["var_defs"]}
    target, source = variables["VAR18031"], variables["VAR18053"]

    assert (target.variable_name, target.variable_type) == ("evaporado_total_evaporacao", "calculado")
    assert (source.variable_name, source.variable_type, source.unit, source.frequency) == (
        "retirada_total_condensado_area13", "entrada_externa", "m³/h", "diário")
    assert (source.scope_type, source.scope_value) == ("linha", "L1_L7")

    equations = [d for d in energy["eq_defs"] if d.target_variable_id == "VAR18031"]
    assert [(d.equation_definition_id, d.expression) for d in equations] == [("EQ18025", "VAR18053 / 1")]

    context = CalculationContext()
    context.set_variable_value("VAR18053", 123.5, "linha", "L3")
    evaluator = ExpressionEvaluator(
        calculation_context=context, default_scope_type="linha", default_scope_value="L3",
    )
    assert evaluator.evaluate(ExpressionParser().parse(equations[0].expression)) == 123.5
