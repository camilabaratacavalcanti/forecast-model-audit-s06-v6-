"""
Validação runtime da cadeia completa do bloco `energy`.

As 23 equações diárias são executadas de uma só vez pelo
`ForecastEngine` real, a partir das EquationDefinitions REAIS do seed:

    SeedLoader (real)
        -> EquationDefinitionRegistry (subconjunto com os
           EquationDefinition reais, não recriados)
        -> ForecastEngine.calculate_from_definition_registry
               -> ScopeResolver real (materialização das instâncias)
               -> DependencyGraph / DependencyResolver reais
                  (ordem topológica derivada das referências REAIS
                  extraídas das expressões)
               -> EquationEngine / ExpressionEvaluator reais
        -> resultados

O teste popula apenas as ENTRADAS do bloco (as variáveis
`entrada`/`entrada_externa` e os Parameters). Nenhum valor calculado é
escrito à mão no CalculationContext: `producao_planta_t_h`,
`energia_digestao`, `energia_bayer` etc. só podem existir por execução
real das equações.

Os valores esperados são recalculados aqui, em Python puro, a partir
das mesmas entradas e das fórmulas documentadas no seed -- nunca
reaproveitando o retorno do ExpressionEvaluator.

Entradas de outros blocos
-------------------------
`temperatura_lp` (fonte "bloco temperature_lp") e
`evaporado_total_evaporacao` (fonte "bloco area_04_13") são populadas
com valores sintéticos: esses blocos ainda não existem em
`data/seed/`, e o bloco energy os declara como entradas próprias, com
IDs próprios. O teste, portanto, exercita o contrato de consumo
(a cadeia calcula corretamente a partir desses valores), não um
acoplamento de IDs entre blocos -- que hoje não existe e que este
teste não simula com mocks.

Não altera seeds, não altera código de produção.
"""

from datetime import date
from pathlib import Path

import pytest

from app.domain.equations.registry import EquationDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.engine.time_period_resolver import TimePeriodResolver
from app.repositories.seed_loader import SeedLoader

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

GROUPS = {
    "L1_L3": ["L1", "L2", "L3"],
    "L4_L5": ["L4", "L5"],
    "L6_L7": ["L6", "L7"],
}

# Fator de conversão vapor -> energia, literal nas expressões
# EQ18009 e EQ18018.
GJ_PER_TONNE = 2.455609

# Constantes literais de EQ18005 (vazao_vapor_digestao).
LTH_FACTOR = 1.27
LTH_DENSITY = 0.85157
DIGESTION_DIVISOR = 482

# Divisor de EQ18010 (economicidade_evaporacao).
ECONOMICITY_DIVISOR = 80


# Entradas por linha. Valores distintos em toda parte: nenhuma linha
# compartilha nenhum número com outra, de modo que uma resolução de
# escopo errada não pode produzir o resultado certo por coincidência.
LINE_INPUTS = {
    "L1": dict(
        producao=25200.0, lth=910.0, temperatura_lp=76.0,
        ref_inferior=41.0, ref_superior=52.0,
        temperatura_he6=151.0, economicidade_ref=6.1,
        evaporado=141.0,
    ),
    "L2": dict(
        producao=25440.0, lth=920.0, temperatura_lp=68.0,
        ref_inferior=42.0, ref_superior=53.0,
        temperatura_he6=152.0, economicidade_ref=6.2,
        evaporado=142.0,
    ),
    "L3": dict(
        producao=25680.0, lth=930.0, temperatura_lp=77.0,
        ref_inferior=43.0, ref_superior=54.0,
        temperatura_he6=153.0, economicidade_ref=6.3,
        evaporado=143.0,
    ),
    "L4": dict(
        producao=25920.0, lth=940.0, temperatura_lp=69.0,
        ref_inferior=44.0, ref_superior=55.0,
        temperatura_he6=154.0, economicidade_ref=6.4,
        evaporado=144.0,
    ),
    "L5": dict(
        producao=26160.0, lth=950.0, temperatura_lp=78.0,
        ref_inferior=45.0, ref_superior=56.0,
        temperatura_he6=155.0, economicidade_ref=6.5,
        evaporado=145.0,
    ),
    "L6": dict(
        producao=26400.0, lth=960.0, temperatura_lp=70.0,
        ref_inferior=46.0, ref_superior=57.0,
        temperatura_he6=156.0, economicidade_ref=6.6,
        evaporado=146.0,
    ),
    "L7": dict(
        producao=26640.0, lth=970.0, temperatura_lp=79.0,
        ref_inferior=47.0, ref_superior=58.0,
        temperatura_he6=157.0, economicidade_ref=6.7,
        evaporado=147.0,
    ),
}

# `temperatura_lp_referencia` = 72 °C (valor real do seed). As
# temperaturas acima ficam deliberadamente dos DOIS lados desse limite:
# L1, L3, L5 e L7 acima (ramo inferior) e L2, L4, L6 abaixo (ramo
# superior), para que ambos os ramos de EQ18003 sejam exercitados na
# mesma execução.

CONSUMO_VAPOR_OUTROS = 33.0

DAILY_EQUATION_IDS = [
    f"EQ180{n:02d}" for n in range(1, 25) if n != 20
]


@pytest.fixture(scope="module")
def loaded_seed():
    return SeedLoader(SEED_ROOT).load_all_definitions_and_instances()


@pytest.fixture(scope="module")
def seed_parameters(loaded_seed):
    """Valores REAIS dos Parameters do seed, nunca inventados."""

    _vd, _vi, _pd, param_instances, _ed, _ei = loaded_seed

    values = {}

    for instance in param_instances.all():
        if not instance.parameter_definition_id.startswith("PARAM18"):
            continue

        values[
            (
                instance.parameter_definition_id,
                instance.scope_type,
                instance.scope_value,
            )
        ] = instance.value

    return values


def _subset_registry(eq_defs, equation_ids):
    subset = EquationDefinitionRegistry()

    for equation_id in equation_ids:
        subset.add(eq_defs.get(equation_id))

    return subset


# Entradas de linha do bloco: (variable_id, chave em LINE_INPUTS).
LINE_INPUT_VARIABLES = (
    ("VAR18001", "producao"),
    ("VAR18008", "lth"),
    ("VAR18012", "temperatura_lp"),
    ("VAR18015", "ref_inferior"),
    ("VAR18016", "ref_superior"),
    ("VAR18018", "temperatura_he6"),
    ("VAR18029", "economicidade_ref"),
    ("VAR18031", "evaporado"),
)


def _populate_inputs(ctx, seed_parameters, line_inputs=None, skip=()):
    """
    Popula APENAS as entradas do bloco. `skip` permite omitir
    deliberadamente uma entrada, para provar que sua ausência é um
    erro explícito e não um zero silencioso.
    """

    line_inputs = line_inputs or LINE_INPUTS

    for line in LINES:
        inputs = line_inputs[line]

        for variable_id, key in LINE_INPUT_VARIABLES:
            if variable_id in skip:
                continue

            ctx.set_variable_value(
                variable_id, inputs[key], "linha", line,
            )

        for parameter_id in (
            "PARAM18001", "PARAM18002", "PARAM18003",
        ):
            if parameter_id in skip:
                continue

            ctx.set_parameter_value(
                parameter_id,
                seed_parameters[(parameter_id, "linha", line)],
                "linha",
                line,
            )

    if "VAR18046" not in skip:
        ctx.set_variable_value(
            "VAR18046", CONSUMO_VAPOR_OUTROS, "linha_grupo", "L1_L7",
        )


def _expected(seed_parameters, line_inputs=None):
    """
    Recalcula a cadeia inteira em Python puro, a partir das entradas e
    das fórmulas documentadas no seed. Não usa ExpressionEvaluator,
    ExpressionParser, CalculationContext nem ForecastEngine.
    """

    line_inputs = line_inputs or LINE_INPUTS

    referencia = seed_parameters[("PARAM18001", "linha", "L1")]
    ajuste_regenerativo = seed_parameters[
        ("PARAM18002", "linha", "L1")
    ]
    ajuste_vapor_vivo = seed_parameters[("PARAM18003", "linha", "L1")]

    per_line = {}

    for line in LINES:
        inputs = line_inputs[line]

        producao_t_h = inputs["producao"] / 24

        if inputs["temperatura_lp"] > referencia:
            delta_t_regenerativo = (
                inputs["ref_inferior"] + ajuste_regenerativo
            )
        else:
            delta_t_regenerativo = (
                inputs["ref_superior"] + ajuste_regenerativo
            )

        delta_util = (
            inputs["temperatura_he6"]
            - (inputs["temperatura_lp"] + delta_t_regenerativo)
        )

        delta_t_vapor_vivo = delta_util + ajuste_vapor_vivo

        vazao_vapor_digestao = (
            inputs["lth"] * LTH_FACTOR * LTH_DENSITY * delta_util
        ) / DIGESTION_DIVISOR

        especifico_vapor_digestao = (
            vazao_vapor_digestao / producao_t_h
        )

        economicidade_evaporacao = (
            inputs["economicidade_ref"] / ECONOMICITY_DIVISOR
        ) * inputs["temperatura_lp"]

        consumo_vapor_evaporadores = (
            inputs["evaporado"] / economicidade_evaporacao
        )

        per_line[line] = {
            "VAR18002": producao_t_h,
            "VAR18017": delta_t_regenerativo,
            "VAR18019": delta_t_vapor_vivo,
            "VAR18020": vazao_vapor_digestao,
            "VAR18024": especifico_vapor_digestao,
            "VAR18030": economicidade_evaporacao,
            "VAR18032": consumo_vapor_evaporadores,
            "VAR18034": (
                consumo_vapor_evaporadores / producao_t_h
            ),
        }

    producao_planta_t_h = sum(
        per_line[line]["VAR18002"] for line in LINES
    )
    vazao_total = sum(per_line[line]["VAR18020"] for line in LINES)
    consumo_evaporadores_total = sum(
        per_line[line]["VAR18032"] for line in LINES
    )

    especifico_digestao_medio = sum(
        per_line[line]["VAR18002"] * per_line[line]["VAR18024"]
        for line in LINES
    ) / producao_planta_t_h

    energia_digestao = especifico_digestao_medio * GJ_PER_TONNE

    especifico_evaporacao_total = (
        consumo_evaporadores_total / producao_planta_t_h
    )

    energia_evaporacao = especifico_evaporacao_total * GJ_PER_TONNE

    consumo_total_vapor = vazao_total + consumo_evaporadores_total

    demanda_bayer = consumo_total_vapor + CONSUMO_VAPOR_OUTROS

    group = {
        "VAR18003": producao_planta_t_h,
        "VAR18022": vazao_total,
        "VAR18025": especifico_digestao_medio,
        "VAR18027": energia_digestao,
        "VAR18033": consumo_evaporadores_total,
        "VAR18038": especifico_evaporacao_total,
        "VAR18040": energia_evaporacao,
        "VAR18042": energia_digestao + energia_evaporacao,
        "VAR18045": consumo_total_vapor,
        "VAR18047": CONSUMO_VAPOR_OUTROS / producao_planta_t_h,
        "VAR18049": demanda_bayer,
        "VAR18050": demanda_bayer / producao_planta_t_h,
    }

    subgroups = {}

    for group_value, members in GROUPS.items():
        subgroups[group_value] = sum(
            per_line[line]["VAR18032"] for line in members
        ) / sum(
            per_line[line]["VAR18002"] for line in members
        )

    return per_line, group, subgroups


def _run(loaded_seed, ctx):
    _vd, _vi, _pd, _pi, eq_defs, _ei = loaded_seed

    subset = _subset_registry(eq_defs, DAILY_EQUATION_IDS)

    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=subset,
        calculation_context=ctx,
    )

    return ctx


@pytest.fixture
def executed(loaded_seed, seed_parameters):
    ctx = CalculationContext()

    _populate_inputs(ctx, seed_parameters)

    return _run(loaded_seed, ctx)


def _read(ctx, variable_id, scope_type, scope_value):
    return ctx.get_variable_value(
        variable_id, scope_type=scope_type, scope_value=scope_value,
    )


# ============================================================
# Cadeia diária completa
# ============================================================


def test_the_23_daily_equations_all_execute(
    loaded_seed, seed_parameters,
):
    _vd, _vi, _pd, _pi, eq_defs, _ei = loaded_seed

    ctx = CalculationContext()
    _populate_inputs(ctx, seed_parameters)

    subset = _subset_registry(eq_defs, DAILY_EQUATION_IDS)

    results = ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=subset,
        calculation_context=ctx,
    )

    # 16 equações de linha_grupo (1 instância cada) e 7 de linha
    # (7 instâncias cada) -- a contagem é conferida a partir das
    # Definitions reais, não fixada à mão.
    expected_instances = 0

    for equation_id in DAILY_EQUATION_IDS:
        definition = eq_defs.get(equation_id)
        expected_instances += (
            7 if definition.scope_type == "linha" else 1
        )

    assert len(results) == expected_instances


@pytest.mark.parametrize("line", LINES)
def test_per_line_results(executed, seed_parameters, line):
    per_line, _group, _subgroups = _expected(seed_parameters)

    for variable_id, expected_value in per_line[line].items():
        actual = _read(executed, variable_id, "linha", line)

        assert actual == pytest.approx(expected_value, rel=1e-12), (
            f"{variable_id}@{line}"
        )


def test_plant_group_results(executed, seed_parameters):
    _per_line, group, _subgroups = _expected(seed_parameters)

    for variable_id, expected_value in group.items():
        actual = _read(
            executed, variable_id, "linha_grupo", "L1_L7",
        )

        assert actual == pytest.approx(expected_value, rel=1e-12), (
            variable_id
        )


@pytest.mark.parametrize(
    "variable_id,group_value",
    [
        ("VAR18035", "L1_L3"),
        ("VAR18036", "L4_L5"),
        ("VAR18037", "L6_L7"),
    ],
)
def test_subgroup_specific_evaporation(
    executed, seed_parameters, variable_id, group_value,
):
    _per_line, _group, subgroups = _expected(seed_parameters)

    actual = _read(
        executed, variable_id, "linha_grupo", group_value,
    )

    assert actual == pytest.approx(
        subgroups[group_value], rel=1e-12,
    )


def test_both_branches_of_the_conditional_are_exercised(
    executed, seed_parameters,
):
    """
    Com temperatura_lp dos dois lados de temperatura_lp_referencia
    (72 °C), a mesma execução produz delta_t_regenerativo pelo ramo
    inferior em L1/L3/L5/L7 e pelo superior em L2/L4/L6.
    """

    referencia = seed_parameters[("PARAM18001", "linha", "L1")]
    ajuste = seed_parameters[("PARAM18002", "linha", "L1")]

    above = []
    below = []

    for line in LINES:
        inputs = LINE_INPUTS[line]
        actual = _read(executed, "VAR18017", "linha", line)

        if inputs["temperatura_lp"] > referencia:
            above.append(line)
            assert actual == pytest.approx(
                inputs["ref_inferior"] + ajuste,
            )
        else:
            below.append(line)
            assert actual == pytest.approx(
                inputs["ref_superior"] + ajuste,
            )

    assert above == ["L1", "L3", "L5", "L7"]
    assert below == ["L2", "L4", "L6"]


def test_energia_bayer_equals_digestion_plus_evaporation(executed):
    """
    Relação estrutural entre três resultados que só existem por
    execução real -- independente dos números do cenário.
    """

    digestao = _read(executed, "VAR18027", "linha_grupo", "L1_L7")
    evaporacao = _read(executed, "VAR18040", "linha_grupo", "L1_L7")
    bayer = _read(executed, "VAR18042", "linha_grupo", "L1_L7")

    assert bayer == pytest.approx(digestao + evaporacao, rel=1e-12)


def test_no_calculated_variable_was_seeded_by_hand(
    loaded_seed, seed_parameters,
):
    """
    Antes de rodar o engine, nenhuma variável `calculado` do bloco
    existe no contexto: os resultados só podem vir da execução.
    """

    from app.engine.exceptions import VariableNotFoundError

    ctx = CalculationContext()
    _populate_inputs(ctx, seed_parameters)

    for variable_id in (
        "VAR18003", "VAR18027", "VAR18040", "VAR18042", "VAR18050",
    ):
        with pytest.raises(VariableNotFoundError):
            ctx.get_variable_value(
                variable_id,
                scope_type="linha_grupo",
                scope_value="L1_L7",
            )

    _run(loaded_seed, ctx)

    for variable_id in (
        "VAR18003", "VAR18027", "VAR18040", "VAR18042", "VAR18050",
    ):
        assert ctx.get_variable_value(
            variable_id,
            scope_type="linha_grupo",
            scope_value="L1_L7",
        ) is not None


# ============================================================
# Causalidade / perturbação
# ============================================================


def test_perturbing_one_line_propagates_to_the_plant(
    loaded_seed, seed_parameters,
):
    """
    Dobrar a produção de L4 (e nada mais) muda producao_planta_t_h
    exatamente pelo delta esperado, e muda energia_bayer. Um resultado
    "congelado" ou escrito à mão não reagiria.
    """

    _per_line, baseline_group, _sub = _expected(seed_parameters)

    perturbed_inputs = {
        line: dict(values) for line, values in LINE_INPUTS.items()
    }
    perturbed_inputs["L4"]["producao"] = (
        LINE_INPUTS["L4"]["producao"] * 2
    )

    ctx = CalculationContext()
    _populate_inputs(ctx, seed_parameters, perturbed_inputs)
    _run(loaded_seed, ctx)

    _pl, perturbed_group, _sg = _expected(
        seed_parameters, perturbed_inputs,
    )

    actual_plant = _read(ctx, "VAR18003", "linha_grupo", "L1_L7")

    assert actual_plant == pytest.approx(
        perturbed_group["VAR18003"], rel=1e-12,
    )

    expected_delta = LINE_INPUTS["L4"]["producao"] / 24

    assert actual_plant - baseline_group["VAR18003"] == pytest.approx(
        expected_delta, rel=1e-12,
    )

    actual_bayer = _read(ctx, "VAR18042", "linha_grupo", "L1_L7")

    assert actual_bayer == pytest.approx(
        perturbed_group["VAR18042"], rel=1e-12,
    )
    assert actual_bayer != pytest.approx(
        baseline_group["VAR18042"], rel=1e-9,
    )


def test_perturbing_an_unrelated_line_does_not_change_a_subgroup(
    loaded_seed, seed_parameters,
):
    """
    especifico_vapor_evaporacao do grupo L4_L5 depende só de L4 e L5:
    perturbar L1 não pode movê-lo. Prova que o escopo não vaza.
    """

    _pl, _g, baseline_subgroups = _expected(seed_parameters)

    perturbed_inputs = {
        line: dict(values) for line, values in LINE_INPUTS.items()
    }
    perturbed_inputs["L1"]["evaporado"] = (
        LINE_INPUTS["L1"]["evaporado"] * 3
    )

    ctx = CalculationContext()
    _populate_inputs(ctx, seed_parameters, perturbed_inputs)
    _run(loaded_seed, ctx)

    _pl2, _g2, perturbed_subgroups = _expected(
        seed_parameters, perturbed_inputs,
    )

    assert _read(
        ctx, "VAR18036", "linha_grupo", "L4_L5",
    ) == pytest.approx(baseline_subgroups["L4_L5"], rel=1e-12)

    assert perturbed_subgroups["L1_L3"] != pytest.approx(
        baseline_subgroups["L1_L3"], rel=1e-9,
    )

    assert _read(
        ctx, "VAR18035", "linha_grupo", "L1_L3",
    ) == pytest.approx(perturbed_subgroups["L1_L3"], rel=1e-12)


# ============================================================
# Entradas vindas de outros blocos
# ============================================================


def test_cross_block_inputs_are_declared_as_inputs_with_a_source(
    loaded_seed,
):
    """
    As variáveis que o workbook marca como vindas de outro bloco são
    entradas do bloco energy, com ID próprio -- não referências a IDs
    de outro bloco. É o que o teste de runtime acima assume ao
    populá-las com valores sintéticos.
    """

    var_defs, _vi, _pd, _pi, _ed, _ei = loaded_seed

    cross_block = {
        "VAR18001": "producao",
        "VAR18008": "lth",
        "VAR18012": "temperatura_lp",
        "VAR18031": "evaporado_total_evaporacao",
    }

    for variable_id, name in cross_block.items():
        definition = var_defs.get(variable_id)

        assert definition is not None
        assert definition.variable_name == name
        assert definition.variable_type in {
            "entrada", "entrada_externa",
        }


@pytest.mark.parametrize(
    "variable_id,description",
    [
        ("VAR18031", "evaporado_total_evaporacao (bloco area_04_13)"),
        ("VAR18012", "temperatura_lp (bloco temperature_lp)"),
        ("VAR18001", "producao (bloco production)"),
        ("VAR18008", "lth (bloco production)"),
        ("VAR18046", "consumo_vapor_outros (entrada_externa)"),
    ],
)
def test_a_missing_cross_block_input_fails_loudly(
    loaded_seed, seed_parameters, variable_id, description,
):
    """
    A ausência de qualquer entrada externa ao bloco faz a cadeia
    falhar explicitamente -- nunca devolver zero, None ou NaN, nem
    pular a equação em silêncio.

    Cobre as quatro entradas cujo workbook aponta outro bloco como
    fonte, mais `consumo_vapor_outros`, que é entrada externa sem
    bloco de origem declarado.
    """

    from app.engine.exceptions import VariableNotFoundError

    ctx = CalculationContext()
    _populate_inputs(ctx, seed_parameters, skip={variable_id})

    with pytest.raises(VariableNotFoundError):
        _run(loaded_seed, ctx)


# ============================================================
# Cadeia diário -> AggregationRule -> mensal -> EQ18020
# ============================================================
#
# Acrescentado pela auditoria pós-implementação: a Fase 2 validou
# cada elo isoladamente (as equações diárias pelo ForecastEngine, as
# AggregationRules pelo TemporalAggregationService, e o vínculo por ID
# de EQ18020 estaticamente), mas nunca executou a COMPOSIÇÃO dos três.
# Sem este teste, uma quebra que só aparecesse na junção -- por
# exemplo o valor mensal não chegando ao período que EQ18020 lê --
# passaria por todos os outros testes.


CHAIN_MONTH = date(2026, 9, 1)

CHAIN_DAYS = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]

# Fatores (produção, lth, evaporado) aplicados às entradas de cada
# dia. Os três variam de forma INDEPENDENTE de propósito.
#
# Escalar tudo por um fator comum não serviria: `especifico_vapor_*`
# é a razão entre um consumo e a produção, e a produção aparece nos
# dois lados. Com um fator único, `especifico_vapor_evaporacao_total`
# fica invariante (consumo ∝ evaporado ∝ f, produção ∝ f) e os três
# dias produziriam o mesmo valor -- caso em que média ponderada e
# média simples coincidem e o teste deixaria de distinguir
# WEIGHTED_AVERAGE de AVERAGE. As temperaturas ficam fixas, para que
# o ramo da condicional não mude entre os dias.
CHAIN_DAY_FACTORS = [
    (1.0, 1.0, 1.0),
    (1.4, 1.1, 1.6),
    (0.7, 1.3, 0.9),
]


def _scaled_inputs(factors):
    producao_factor, lth_factor, evaporado_factor = factors

    scaled = {}

    for line, values in LINE_INPUTS.items():
        scaled[line] = dict(values)
        scaled[line]["producao"] = values["producao"] * producao_factor
        scaled[line]["lth"] = values["lth"] * lth_factor
        scaled[line]["evaporado"] = (
            values["evaporado"] * evaporado_factor
        )

    return scaled


def _run_dated(loaded_seed, ctx, run_date):
    var_defs, _vi, _pd, _pi, eq_defs, _ei = loaded_seed

    subset = _subset_registry(eq_defs, DAILY_EQUATION_IDS)

    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=subset,
        calculation_context=ctx,
        variable_definition_registry=var_defs,
        run_date=run_date,
    )


def test_daily_to_monthly_chain_feeds_eq18020(
    loaded_seed, seed_parameters,
):
    """
    Executa a composição completa, sem escrever à mão nenhum valor
    calculado:

        23 equações diárias (ForecastEngine real, um dia por vez)
            -> energia_digestao / energia_evaporacao DIÁRIOS
        AggregationRule WEIGHTED_AVERAGE (serviço real)
            -> energia_digestao / energia_evaporacao MENSAIS
        EQ18020 (ForecastEngine real, escopo mensal)
            -> energia_media_frct

    O esperado é recalculado aqui: a média ponderada mensal é
    Σ(vₓ·wₓ)/Σ(wₓ) sobre os valores DIÁRIOS que a própria cadeia
    produziu em cada dia, e o resultado final é a soma das duas
    parcelas mensais. Nada disso reaproveita o retorno do
    TemporalAggregationService nem do ForecastEngine.
    """

    var_defs, _vi, _pd, _pi, eq_defs, _ei = loaded_seed

    ctx = CalculationContext()

    daily_digestao = []
    daily_evaporacao = []
    daily_planta = []

    for day, factors in zip(CHAIN_DAYS, CHAIN_DAY_FACTORS):
        inputs = _scaled_inputs(factors)

        _populate_inputs(ctx, seed_parameters, inputs)

        _run_dated(loaded_seed, ctx, day)

        _per_line, group, _sub = _expected(seed_parameters, inputs)

        daily_digestao.append(group["VAR18027"])
        daily_evaporacao.append(group["VAR18040"])
        daily_planta.append(group["VAR18003"])

        # A cadeia diária tem de bater dia a dia, no período do dia.
        for variable_id, expected_value in (
            ("VAR18027", group["VAR18027"]),
            ("VAR18040", group["VAR18040"]),
            ("VAR18003", group["VAR18003"]),
        ):
            assert ctx.get_variable_value(
                variable_id,
                scope_type="linha_grupo",
                scope_value="L1_L7",
                period_id=day.isoformat(),
            ) == pytest.approx(expected_value, rel=1e-12)

    # Os três dias têm de ser realmente diferentes, senão a média
    # ponderada não discriminaria nada.
    assert len(set(daily_planta)) == 3
    assert len(set(daily_digestao)) == 3
    assert len(set(daily_evaporacao)) == 3

    rules = {
        rule.target_variable_id: rule
        for rule in SeedLoader(SEED_ROOT).load_aggregation_rules().all()
        if rule.aggregation_rule_id.startswith("AGR-ENERGY-")
    }

    service = TemporalAggregationService()

    run_date = CHAIN_DAYS[-1]

    monthly = {}

    for target_variable_id, daily_values in (
        ("VAR18028", daily_digestao),
        ("VAR18041", daily_evaporacao),
    ):
        rule = rules[target_variable_id]

        assert rule.aggregation_type == "WEIGHTED_AVERAGE"
        assert rule.weight_variable_id == "VAR18003"

        result = service.aggregate(
            rule=rule,
            calculation_context=ctx,
            scope_type="linha_grupo",
            scope_value="L1_L7",
            run_date=run_date,
        )

        expected_monthly = sum(
            value * weight
            for value, weight in zip(daily_values, daily_planta)
        ) / sum(daily_planta)

        # A média ponderada tem de diferir da simples, senão o teste
        # não distinguiria WEIGHTED_AVERAGE de AVERAGE.
        simple = sum(daily_values) / len(daily_values)
        assert expected_monthly != pytest.approx(simple, rel=1e-9)

        assert result.value == pytest.approx(
            expected_monthly, rel=1e-12,
        )

        monthly[target_variable_id] = result.value

    monthly_period_id = (
        TimePeriodResolver()
        .effective_window(frequency="mensal", run_date=run_date)
        .period_id
    )

    # O serviço de agregação não escreve de volta no contexto: o
    # valor mensal só chega ao período mensal por esta escrita
    # explícita, que é o papel do orquestrador na plataforma.
    for variable_id, value in monthly.items():
        ctx.set_variable_value(
            variable_id, value, "linha_grupo", "L1_L7",
            period_id=monthly_period_id,
        )

    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=_subset_registry(
            eq_defs, ["EQ18020"],
        ),
        calculation_context=ctx,
        variable_definition_registry=var_defs,
        run_date=run_date,
    )

    expected_frct = (
        monthly["VAR18028"] + monthly["VAR18041"]
    )

    assert ctx.get_variable_value(
        "VAR18044",
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id=monthly_period_id,
    ) == pytest.approx(expected_frct, rel=1e-12)


def test_eq18020_cannot_be_satisfied_by_daily_values_alone(
    loaded_seed, seed_parameters,
):
    """
    Se a etapa de agregação não acontecer, EQ18020 não pode
    silenciosamente cair nos valores DIÁRIOS de energia_digestao /
    energia_evaporacao: o período mensal não existe e a execução
    falha alto.

    É o contra-teste do anterior -- sem ele, um EQ18020 que lesse os
    valores diários passaria pela cadeia acima sem ninguém perceber.
    """

    var_defs, _vi, _pd, _pi, eq_defs, _ei = loaded_seed

    ctx = CalculationContext()

    _populate_inputs(ctx, seed_parameters)

    _run_dated(loaded_seed, ctx, CHAIN_DAYS[-1])

    # Os diários existem; os mensais (VAR18028/VAR18041), não.
    assert ctx.get_variable_value(
        "VAR18027",
        scope_type="linha_grupo",
        scope_value="L1_L7",
        period_id=CHAIN_DAYS[-1].isoformat(),
    ) is not None

    from app.engine.exceptions import VariableNotFoundError

    with pytest.raises(VariableNotFoundError):
        ForecastEngine().calculate_from_definition_registry(
            equation_definition_registry=_subset_registry(
                eq_defs, ["EQ18020"],
            ),
            calculation_context=ctx,
            variable_definition_registry=var_defs,
            run_date=CHAIN_DAYS[-1],
        )
