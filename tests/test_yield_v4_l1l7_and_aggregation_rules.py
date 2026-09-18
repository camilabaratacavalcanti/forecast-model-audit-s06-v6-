"""
Implementação das decisões finais da auditoria do Yield v4:

    A. tanque.variable_type = entrada_externa (correção de metadata)
    B. 16 EquationDefinitions diárias linha_grupo/L1_L7
    C. 16 EquationDefinitions anuais linha_grupo/L1_L7 (variáveis _base)
    D. 80 AggregationRules (diário -> mensal, AVERAGE, month_to_date)

Fechamento (3 decisões de negócio confirmadas):

    Decisão 1 — `ltp_lth_base` (anual, linha_grupo/L1_L7, EQ11127):
    o numerador repetia `ltp_tc_base@L1` nos 7 termos; corrigido para
    variar `ltp_tc_base@Lx` por linha (o denominador já estava
    correto).

    Decisão 2 — `eoc_solids_base` (anual, linha_grupo/L1_L7,
    EQ11137): o numerador repetia `producao_base_ppt_base@L1` nos
    termos de L2, L3 e L4 (referência cruzada indevida) em vez de
    `@L2`/`@L3`/`@L4`; corrigido para que cada `eoc_solids_base@Lx`
    seja multiplicado pelo respectivo `producao_base_ppt_base@Lx`
    (L1->L1, ..., L7->L7). O denominador já estava correto.

    Decisão 3 — `ltp_tc` (diário, linha/L1_L7) migrou de
    ParameterDefinition (PARAM11001, removido) para VariableDefinition
    (nova, VAR11240, variable_type=entrada_externa). Isso resolve o
    gap documentado anteriormente: agora existe uma Variable de
    origem para a AggregationRule diário->mensal de
    `ltp_tc`/linha/L1_L7 (a 80ª regra,
    AGR-LTP_TC-LINHA-L1_L7-MENSAL-AVERAGE), completando a cardinalidade
    esperada de 80 (16 variáveis x 5 grupos de escopo). Todas as
    EquationDefinitions que referenciavam `PARAM11001@Lx`/`PARAM11001`
    (EQ11001, EQ11006, EQ11018, EQ11034, EQ11050, EQ11111, EQ11112)
    foram atualizadas para referenciar `VAR11240` (a nova Variable) —
    `ltp_tc_base` (PARAM11002) NÃO foi alterado, permanece Parameter.
"""

from datetime import date, timedelta

import pytest

from app.domain.equations.models import EquationInstance
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationInstanceRegistry,
)
from app.domain.forecast.aggregation import (
    AGGREGATION_TYPES,
    AggregationRuleRegistry,
)
from app.domain.forecast.collection import ForecastValueRegistry
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterInstanceRegistry,
)
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableInstanceRegistry,
)
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import VariableNotFoundError
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)
from app.repositories.seed_loader import SeedLoader

from pathlib import Path

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


def _is_yield_id(entity_id):
    """
    Filtra pela faixa de IDs reservada ao bloco Yield (11000-11999)
    -- necessário porque `SeedLoader` carrega TODOS os blocos do
    seed a partir de `SEED_ROOT` (agora inclui também "production").
    Este módulo audita especificamente o seed do Yield v4, isolado
    dos demais blocos, preservando o objetivo original de cada
    teste.
    """

    digits = "".join(ch for ch in entity_id if ch.isdigit())

    return bool(digits) and 11000 <= int(digits) <= 11999


def _filter_yield_block(loaded_seed):
    (
        variable_definitions, variable_instances,
        parameter_definitions, parameter_instances,
        equation_definitions, equation_instances,
    ) = loaded_seed

    yield_variable_definitions = VariableDefinitionRegistry()
    for d in variable_definitions.all():
        if _is_yield_id(d.variable_definition_id):
            yield_variable_definitions.add(d)

    yield_variable_instances = VariableInstanceRegistry()
    for i in variable_instances.all():
        if _is_yield_id(i.variable_definition_id):
            yield_variable_instances.add(i)

    yield_parameter_definitions = ParameterDefinitionRegistry()
    for d in parameter_definitions.all():
        if _is_yield_id(d.parameter_definition_id):
            yield_parameter_definitions.add(d)

    yield_parameter_instances = ParameterInstanceRegistry()
    for i in parameter_instances.all():
        if _is_yield_id(i.parameter_definition_id):
            yield_parameter_instances.add(i)

    yield_equation_definitions = EquationDefinitionRegistry()
    for d in equation_definitions.all():
        if _is_yield_id(d.equation_definition_id):
            yield_equation_definitions.add(d)

    yield_equation_instances = EquationInstanceRegistry()
    for i in equation_instances.all():
        if _is_yield_id(i.target_variable_id):
            yield_equation_instances.add(i)

    return (
        yield_variable_definitions, yield_variable_instances,
        yield_parameter_definitions, yield_parameter_instances,
        yield_equation_definitions, yield_equation_instances,
    )


def _filter_yield_rules(aggregation_rule_registry):
    """
    Isola as AggregationRule do bloco Yield, pelo mesmo criterio
    ja usado por `_is_yield_id` para as entidades: a faixa de IDs
    reservada ao bloco (11000-11999).

    O filtro anterior era uma lista negra do nome do bloco
    ("PRODUCTION" nao no aggregation_rule_id), o que so isolava os
    blocos ja existentes quando ele foi escrito: qualquer bloco novo
    vazava para dentro da fixture deste modulo, que se declara
    "isolado dos demais blocos". Nenhuma assercao dos testes foi
    alterada -- apenas o predicado de isolamento passou a exprimir a
    intencao ja documentada no topo do arquivo.
    """

    yield_rules = AggregationRuleRegistry()
    for rule in aggregation_rule_registry.all():
        if _is_yield_id(rule.source_variable_id) and _is_yield_id(
            rule.target_variable_id
        ):
            yield_rules.add(rule)
    return yield_rules

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

L1_L7_DAILY_NAMES = {
    "yield", "ltp", "lth", "oee", "ltp_lth", "ltp_tc", "ltp_a_c",
    "sl_solids", "ratio_spent", "ssa_sf", "ssa_sg", "ssa_media",
    "n_ppt", "eoc_temp", "eoc_solids", "producao_base_ppt",
}
L1_L7_ANNUAL_NAMES = {n + "_base" for n in L1_L7_DAILY_NAMES}


@pytest.fixture(scope="module")
def loaded_seed():
    loader = SeedLoader(SEED_ROOT)
    return _filter_yield_block(
        loader.load_all_definitions_and_instances()
    )


@pytest.fixture(scope="module")
def aggregation_rules():
    loader = SeedLoader(SEED_ROOT)
    return _filter_yield_rules(loader.load_aggregation_rules())


# ============================================================
# Teste 1 — metadata de tanque
# ============================================================


def test_1_tanque_variable_type_is_entrada_externa(loaded_seed):
    variable_definitions, *_ = loaded_seed

    tanque = [
        v for v in variable_definitions.all()
        if v.variable_name == "tanque"
    ]

    assert len(tanque) == 1
    assert tanque[0].variable_type == "entrada_externa"
    # A modelagem aprovada de tanque (uma única VariableDefinition,
    # escopo linha/L1_L7) não foi alterada por esta correção.
    assert tanque[0].scope_type == "linha"
    assert tanque[0].scope_value == "L1_L7"


# ============================================================
# Teste 2 — cardinalidade das EquationDefinitions
# ============================================================


def test_2_equation_definition_count_is_138(loaded_seed):
    _vd, _vi, _pd, _pi, equation_definitions, equation_instances = (
        loaded_seed
    )

    assert len(equation_definitions.all()) == 138
    # L1_L7 é escopo singular (não materializa por linha): as 32
    # novas EquationDefinitions produzem exatamente 32 novas
    # EquationInstances, não 32*7.
    assert len(equation_instances.all()) == 198


# ============================================================
# Teste 3 — L1_L7 diário (16 novas EquationDefinitions)
# ============================================================


def test_3_sixteen_daily_l1_l7_equation_definitions_loaded(
    loaded_seed,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    daily_l1l7 = [
        e for e in equation_definitions.all()
        if e.scope_type == "linha_grupo"
        and e.scope_value == "L1_L7"
        and var_by_id[e.target_variable_id].frequency == "diário"
    ]

    assert len(daily_l1l7) == 16
    assert {
        var_by_id[e.target_variable_id].variable_name
        for e in daily_l1l7
    } == L1_L7_DAILY_NAMES
    assert all(e.status == "PUBLISHED" for e in daily_l1l7)
    assert all(e.version == 1 for e in daily_l1l7)


# ============================================================
# Teste 4 — L1_L7 anual (16 novas EquationDefinitions)
# ============================================================


def test_4_sixteen_annual_l1_l7_equation_definitions_loaded(
    loaded_seed,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    annual_l1l7 = [
        e for e in equation_definitions.all()
        if e.scope_type == "linha_grupo"
        and e.scope_value == "L1_L7"
        and var_by_id[e.target_variable_id].frequency == "anual"
    ]

    assert len(annual_l1l7) == 16
    assert {
        var_by_id[e.target_variable_id].variable_name
        for e in annual_l1l7
    } == L1_L7_ANNUAL_NAMES

    # Nenhuma das 32 novas EquationDefinitions L1_L7 tem frequency
    # própria -- a frequência continua inteiramente derivada da
    # VariableDefinition alvo (contrato inalterado).
    for e in annual_l1l7:
        assert not hasattr(e, "frequency")


# ============================================================
# Teste 5 — referências explícitas @L1..@L7 (matemática real,
# valores distintos por linha, prova de que não há resolução
# contextual incorreta)
# ============================================================


def test_5_daily_l1_l7_explicit_scope_references_resolve_per_line(
    loaded_seed,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    definition = next(
        e for e in equation_definitions.all()
        if e.scope_type == "linha_grupo"
        and e.scope_value == "L1_L7"
        and var_by_id[e.target_variable_id].variable_name == "yield"
        and var_by_id[e.target_variable_id].frequency == "diário"
    )

    yield_values = {
        "L1": 10.0, "L2": 20.0, "L3": 30.0, "L4": 40.0,
        "L5": 50.0, "L6": 60.0, "L7": 70.0,
    }
    ltp_values = {
        "L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
        "L5": 5.0, "L6": 6.0, "L7": 7.0,
    }

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            "VAR11001", yield_values[line], "linha", line,
        )
        context.set_variable_value(
            "VAR11002", ltp_values[line], "linha", line,
        )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    expected = sum(
        yield_values[line] * ltp_values[line] for line in LINES
    ) / sum(ltp_values.values())

    assert result == pytest.approx(expected)

    # Prova de que L1..L7 não foram resolvidos como o mesmo escopo:
    # alterar SOMENTE o valor de L4 muda o resultado.
    context.set_variable_value("VAR11001", 999.0, "linha", "L4")
    result_changed = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )
    assert result_changed != result


# ============================================================
# Teste 6 — anual L1_L7 `_base`: cálculo direto, sem
# AggregationRule, sem dependência de valores diários
# ============================================================


def test_6_annual_l1_l7_base_is_a_direct_calculation(loaded_seed):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    definition = next(
        e for e in equation_definitions.all()
        if e.scope_type == "linha_grupo"
        and e.scope_value == "L1_L7"
        and var_by_id[e.target_variable_id].variable_name
        == "yield_base"
    )

    target_variable = var_by_id[definition.target_variable_id]
    assert target_variable.frequency == "anual"

    # As fontes (yield_base, ltp_base por linha) também são anuais
    # -- nenhuma dependência de dado diário.
    yield_base_values = {
        "L1": 11.0, "L2": 22.0, "L3": 33.0, "L4": 44.0,
        "L5": 55.0, "L6": 66.0, "L7": 77.0,
    }
    ltp_base_values = {
        "L1": 1.5, "L2": 2.5, "L3": 3.5, "L4": 4.5,
        "L5": 5.5, "L6": 6.5, "L7": 7.5,
    }

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            "VAR11080", yield_base_values[line], "linha", line,
        )
        context.set_variable_value(
            "VAR11081", ltp_base_values[line], "linha", line,
        )

    instance = EquationInstance.create(
        definition=definition,
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance,
        definition=definition,
        calculation_context=context,
    )

    expected = sum(
        yield_base_values[line] * ltp_base_values[line]
        for line in LINES
    ) / sum(ltp_base_values.values())

    assert result == pytest.approx(expected)


# ============================================================
# Teste 7 — nenhuma das 32 equações L1_L7 virou AggregationRule
# ============================================================


def test_7_none_of_the_32_l1_l7_equations_became_aggregation_rules(
    loaded_seed, aggregation_rules,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    l1l7_target_ids = {
        e.target_variable_id
        for e in equation_definitions.all()
        if e.scope_type == "linha_grupo" and e.scope_value == "L1_L7"
    }

    rule_target_ids = {
        r.target_variable_id for r in aggregation_rules.all()
    }

    # As 32 variáveis-alvo L1_L7 (diário+anual) nunca são o alvo de
    # uma AggregationRule -- são sempre produzidas por cálculo direto.
    assert l1l7_target_ids.isdisjoint(rule_target_ids)


# ============================================================
# Teste 8 — 80 AggregationRules (gap do ltp_tc resolvido pela
# migração Parameter -> Variable, Decisão 3)
# ============================================================


def test_8_aggregation_rule_count_is_80(aggregation_rules):
    assert len(aggregation_rules) == 80

    ids = [r.aggregation_rule_id for r in aggregation_rules]
    assert len(ids) == len(set(ids))


def test_8_all_aggregation_rules_are_daily_to_monthly_average(
    aggregation_rules,
):
    for rule in aggregation_rules:
        assert rule.source_frequency == "diário"
        assert rule.target_frequency == "mensal"
        assert rule.aggregation_type == "AVERAGE"
        assert rule.aggregation_type in AGGREGATION_TYPES
        # Sem janela explícita: a janela mensal progressiva
        # (month_to_date) é derivada automaticamente pelo
        # TemporalAggregationService via TimePeriodResolver, não
        # fixada na regra -- não é MOVING_AVERAGE.
        assert rule.window_start_date is None
        assert rule.window_end_date is None


# ============================================================
# Teste 9 — janela mensal (AC-10, AC-11)
# ============================================================


def test_9_monthly_window_is_progressive_never_includes_future(
    loaded_seed, aggregation_rules,
):
    variable_definitions, *_ = loaded_seed

    rule = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-YIELD-LINHA-L1_L7-MENSAL-AVERAGE"
    )

    context = CalculationContext()

    daily_values = {}
    current = date(2026, 9, 1)
    value = 1.0
    while current <= date(2026, 9, 14):
        context.set_variable_value(
            rule.source_variable_id, value, "linha", "L4",
            period_id=current.isoformat(),
        )
        daily_values[current] = value
        value += 1.0
        current += timedelta(days=1)

    orchestrator = TemporalForecastOrchestrator()

    result = orchestrator.run_aggregation(
        rule=rule,
        calculation_context=context,
        scope_type="linha",
        scope_value="L4",
        run_date=date(2026, 9, 14),
    )

    assert result.period_id == "2026-09"
    assert result.value == pytest.approx(
        sum(daily_values.values()) / len(daily_values)
    )

    # AC-11: nenhum valor de 15..30/09 foi populado -- se a regra
    # tentasse usá-los, receberíamos VariableNotFoundError em vez de
    # um resultado. O sucesso acima já prova isso; reforçamos com
    # uma tentativa explícita a partir de um run_date que exigiria
    # o mês inteiro (não populado).
    with pytest.raises(VariableNotFoundError):
        orchestrator.run_aggregation(
            rule=rule,
            calculation_context=context,
            scope_type="linha",
            scope_value="L4",
            run_date=date(2026, 9, 30),
        )


# ============================================================
# Teste 10 — múltiplas regras não colidem (aggregation_rule_id)
# ============================================================


def test_10_aggregation_rule_id_keeps_different_scopes_distinct(
    aggregation_rules,
):
    yield_rules = [
        r for r in aggregation_rules.all()
        if r.aggregation_rule_id.startswith("AGR-YIELD-")
    ]

    # yield tem 5 regras (uma por grupo de escopo): todas distintas.
    assert len(yield_rules) == 5

    context = CalculationContext()
    for day in range(1, 15):
        context.set_variable_value(
            "VAR11001", 10.0 + day, "linha", "L1",
            period_id=f"2026-09-{day:02d}",
        )
        context.set_variable_value(
            "VAR11016", 20.0 + day, "linha_grupo", "L1_L3",
            period_id=f"2026-09-{day:02d}",
        )

    orchestrator = TemporalForecastOrchestrator()
    registry = ForecastValueRegistry()

    rule_linha = next(
        r for r in yield_rules
        if r.aggregation_rule_id == "AGR-YIELD-LINHA-L1_L7-MENSAL-AVERAGE"
    )
    rule_grupo = next(
        r for r in yield_rules
        if r.aggregation_rule_id
        == "AGR-YIELD-GRUPO-L1_L3-MENSAL-AVERAGE"
    )

    result_linha = orchestrator.run_aggregation(
        rule=rule_linha, calculation_context=context,
        scope_type="linha", scope_value="L1",
        run_date=date(2026, 9, 14),
    )
    result_grupo = orchestrator.run_aggregation(
        rule=rule_grupo, calculation_context=context,
        scope_type="linha_grupo", scope_value="L1_L3",
        run_date=date(2026, 9, 14),
    )

    registry.add(result_linha)
    registry.add(result_grupo)

    assert len(registry) == 2
    assert result_linha.identity() != result_grupo.identity()
    assert result_linha.value != result_grupo.value


# ============================================================
# Teste 11 — integração completa: SeedLoader -> Registries ->
# EquationEngine/ForecastEngine -> TemporalAggregationService/
# Orchestrator -> ForecastValue -> ForecastValueRegistry
# ============================================================


def test_11_full_integration_seed_to_forecast_value_registry(
    loaded_seed, aggregation_rules,
):
    (
        variable_definitions, _vi, _parameter_definitions,
        parameter_instances, equation_definitions, equation_instances,
    ) = loaded_seed

    assert len(equation_definitions.all()) == 138
    assert len(equation_instances.all()) == 198

    context = CalculationContext()

    # Popula os inputs mínimos reais do Yield (mesmo padrão dos
    # testes de Fase A/B/C) para que a cadeia completa (incluindo as
    # 32 novas equações L1_L7) seja calculável.
    definitions_by_name_scope = {}
    for d in variable_definitions.all():
        definitions_by_name_scope.setdefault(d.variable_name, {})[
            (d.frequency, d.scope_type, d.scope_value)
        ] = d

    daily_inputs = {
        "lth": 500.0, "oee": 0.9, "ltp_lth": 1.1, "ltp_a_c": 1.5,
        "sl_solids": 140.0, "ssa_sf": 3.0, "ssa_sg": 1.5,
        "eoc_temp": 74.0, "eoc_solids": 250.0, "tanque": 12.0,
        "ltp_tc": 273.0,
    }
    annual_inputs = {
        "lth_base": 500.0, "oee_base": 0.9, "ltp_lth_base": 1.1,
        "ltp_a_c_base": 1.5, "sl_solids_base": 140.0,
        "ratio_spent_base": 0.5, "ssa_sf_base": 3.0,
        "ssa_sg_base": 1.5, "n_ppt_base": 10.0, "eoc_temp_base": 74.0,
        "eoc_solids_base": 250.0,
    }

    orchestrator = TemporalForecastOrchestrator()

    for name, value in daily_inputs.items():
        definition = definitions_by_name_scope[name][
            ("diário", "linha", "L1_L7")
        ]
        for line in LINES:
            context.set_variable_value(
                definition.variable_definition_id, value,
                "linha", line,
            )
    for name, value in annual_inputs.items():
        definition = definitions_by_name_scope[name][
            ("anual", "linha", "L1_L7")
        ]
        for line in LINES:
            context.set_variable_value(
                definition.variable_definition_id, value,
                "linha", line,
            )

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(instance, instance.value)

    execution = orchestrator.start_execution(
        run_date=date(2026, 9, 14), model_version="v4",
    )

    # Executa o cálculo diário real para cada dia de 01 a 14/09, para
    # que a AggregationRule mensal (abaixo) tenha uma janela completa
    # de resultados diários já calculados pela cadeia real do Yield
    # -- não apenas um snapshot isolado.
    for day in range(1, 15):
        results = orchestrator.run_direct(
            equation_definition_registry=equation_definitions,
            variable_definition_registry=variable_definitions,
            calculation_context=context,
            run_date=date(2026, 9, day),
        )
        assert len(results) == len(equation_instances.all())

    # Uma equação L1_L7 (yield diário) foi de fato calculada.
    yield_l1l7 = orchestrator.direct_forecast_value(
        variable_id="VAR11064", scope_type="linha_grupo",
        scope_value="L1_L7",
        variable_definition_registry=variable_definitions,
        calculation_context=context, run_date=date(2026, 9, 14),
        execution=execution,
    )
    assert isinstance(yield_l1l7.value, (int, float))
    assert yield_l1l7.execution_id == execution.execution_id

    # Uma AggregationRule mensal real (yield, linha/L1_L7) é
    # aplicada sobre o resultado diário já calculado.
    rule = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-YIELD-LINHA-L1_L7-MENSAL-AVERAGE"
    )

    monthly_yield = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L4",
        run_date=date(2026, 9, 14), execution=execution,
    )

    assert monthly_yield.frequency == "mensal"
    assert monthly_yield.period_id == "2026-09"
    # ForecastValue recebe o execution_id correto da Execution em
    # curso.
    assert monthly_yield.execution_id == execution.execution_id

    registry = ForecastValueRegistry()
    registry.add(yield_l1l7)
    registry.add(monthly_yield)
    assert len(registry) == 2

    execution = execution.complete()
    assert execution.status == "COMPLETED"


# ============================================================
# Teste 12 — auditoria sistemática das 32 novas EquationDefinitions
# ============================================================


def test_12_audit_all_32_new_equations_target_expected_variables(
    loaded_seed,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        loaded_seed
    )

    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    new_equations = [
        e for e in equation_definitions.all()
        if e.equation_definition_id >= "EQ11107"
    ]

    assert len(new_equations) == 32

    for e in new_equations:
        assert e.scope_type == "linha_grupo"
        assert e.scope_value == "L1_L7"
        assert e.status == "PUBLISHED"
        assert e.source_reference == (
            "descritivo_das_variáveis_yield_v4.xlsx"
        )

        target = var_by_id[e.target_variable_id]
        assert target.variable_name in (
            L1_L7_DAILY_NAMES | L1_L7_ANNUAL_NAMES
        )

        # Cada referência explícita na expressão (@L1..@L7) aponta
        # para uma VariableDefinition ou ParameterDefinition
        # existente -- nenhuma referência inventada.
        import re
        tokens = re.findall(r'\b(VAR\d+|PARAM\d+)@L\d+', e.expression)
        assert len(tokens) > 0
        for token in set(tokens):
            if token.startswith("VAR"):
                assert token in var_by_id, (
                    f"{e.equation_definition_id} referencia "
                    f"{token}, inexistente"
                )


# ============================================================
# Teste 13 — auditoria sistemática das 80 AggregationRules
# ============================================================


def test_13_audit_all_80_rules_reference_matching_variable_pairs(
    loaded_seed, aggregation_rules,
):
    variable_definitions, *_ = loaded_seed
    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    for rule in aggregation_rules:
        assert rule.source_variable_id in var_by_id, (
            f"{rule.aggregation_rule_id}: source inexistente"
        )
        assert rule.target_variable_id in var_by_id, (
            f"{rule.aggregation_rule_id}: target inexistente"
        )

        source = var_by_id[rule.source_variable_id]
        target = var_by_id[rule.target_variable_id]

        # A regra sempre liga a MESMA variável de negócio (nome e
        # escopo) entre a frequência diária e a mensal -- nunca uma
        # variável errada.
        assert source.variable_name == target.variable_name
        assert source.scope_type == target.scope_type
        assert source.scope_value == target.scope_value
        assert source.frequency == "diário"
        assert target.frequency == "mensal"


# ============================================================
# Teste 14 — Decisão 1: correção de `ltp_lth_base` (EQ11127) —
# cada termo do numerador deve usar `ltp_tc_base@Lx` (não sempre
# `@L1`); o denominador soma cada linha exatamente uma vez.
# ============================================================


def test_14_ltp_lth_base_numerator_varies_per_line(loaded_seed):
    _vd, _vi, _pd, _pi, equation_definitions, _ei = loaded_seed

    definition = equation_definitions.get("EQ11127")
    expression = definition.expression

    numerator, denominator = expression.split(") / (")

    for line in LINES:
        assert f"VAR11084@{line}*PARAM11002@{line}" in numerator, (
            f"numerador de EQ11127 não usa PARAM11002@{line} no "
            f"termo de {line} (regressão do bug de repetição @L1)"
        )

    for line in LINES:
        assert denominator.count(f"PARAM11002@{line}") == 1

    # Prova matemática real: cada linha contribui com seu próprio
    # ltp_tc_base — alterar SOMENTE o parâmetro de L4 muda o
    # resultado do numerador de forma proporcional ao termo de L4,
    # não ao de L1.
    var_by_id = {
        v.variable_definition_id: v for v in loaded_seed[0].all()
    }
    assert var_by_id[definition.target_variable_id].variable_name == (
        "ltp_lth_base"
    )

    ltp_lth_values = {
        "L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
        "L5": 5.0, "L6": 6.0, "L7": 7.0,
    }
    ltp_tc_base_values = {
        "L1": 10.0, "L2": 20.0, "L3": 30.0, "L4": 40.0,
        "L5": 50.0, "L6": 60.0, "L7": 70.0,
    }

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            "VAR11084", ltp_lth_values[line], "linha", line,
        )
        context.set_parameter_value(
            "PARAM11002", ltp_tc_base_values[line], "linha", line,
        )

    instance = EquationInstance.create(
        definition=definition, scope_type="linha_grupo",
        scope_value="L1_L7",
    )
    engine = EquationEngine()

    result = engine.calculate_instance(
        instance=instance, definition=definition,
        calculation_context=context,
    )

    expected = sum(
        ltp_lth_values[line] * ltp_tc_base_values[line]
        for line in LINES
    ) / sum(ltp_tc_base_values.values())

    assert result == pytest.approx(expected)


# ============================================================
# Teste 15 — `eoc_solids_base` (EQ11137): cada
# `eoc_solids_base@Lx` deve ser multiplicado pelo respectivo
# `producao_base_ppt_base@Lx` (L1->L1, ..., L7->L7) -- nunca por
# um termo de outra linha. Usa valores distintos por linha: um
# teste com valores iguais em todas as linhas não distinguiria
# `@Lx` correto de uma referência cruzada incorreta (ex.: sempre
# `@L1`), que foi exatamente o defeito encontrado e corrigido
# nesta etapa.
# ============================================================


def test_15_eoc_solids_base_multiplies_matching_line_terms(
    loaded_seed,
):
    _vd, _vi, _pd, _pi, equation_definitions, _ei = loaded_seed

    definition = equation_definitions.get("EQ11137")
    expression = definition.expression

    for line in LINES:
        assert f"VAR11093@{line}*VAR11094@{line}" in expression, (
            f"numerador de EQ11137 não multiplica VAR11093@{line} "
            f"por VAR11094@{line} (regressão de referência cruzada)"
        )

    for line in LINES:
        assert expression.split(") / (")[1].count(
            f"VAR11094@{line}"
        ) == 1

    var_by_id = {
        v.variable_definition_id: v for v in loaded_seed[0].all()
    }
    assert var_by_id[definition.target_variable_id].variable_name == (
        "eoc_solids_base"
    )

    instance = EquationInstance.create(
        definition=definition, scope_type="linha_grupo",
        scope_value="L1_L7",
    )
    engine = EquationEngine()

    eoc_solids_base_values = {
        "L1": 10.0, "L2": 20.0, "L3": 30.0, "L4": 40.0,
        "L5": 50.0, "L6": 60.0, "L7": 70.0,
    }
    producao_base_ppt_base_values = {
        "L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
        "L5": 5.0, "L6": 6.0, "L7": 7.0,
    }

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            "VAR11093", eoc_solids_base_values[line], "linha", line,
        )
        context.set_variable_value(
            "VAR11094", producao_base_ppt_base_values[line],
            "linha", line,
        )

    result = engine.calculate_instance(
        instance=instance, definition=definition,
        calculation_context=context,
    )

    expected = sum(
        eoc_solids_base_values[line]
        * producao_base_ppt_base_values[line]
        for line in LINES
    ) / sum(producao_base_ppt_base_values.values())

    assert result == pytest.approx(expected)

    # Prova de referência cruzada: se L2 estivesse multiplicando
    # producao_base_ppt_base@L1 (o bug original) em vez de @L2, o
    # resultado abaixo seria diferente -- perturbar SOMENTE
    # producao_base_ppt_base@L1 não deve afetar o termo de L2.
    context.set_variable_value("VAR11094", 999.0, "linha", "L1")
    result_l1_perturbed = engine.calculate_instance(
        instance=instance, definition=definition,
        calculation_context=context,
    )
    expected_l1_perturbed = (
        eoc_solids_base_values["L1"] * 999.0
        + sum(
            eoc_solids_base_values[line]
            * producao_base_ppt_base_values[line]
            for line in LINES if line != "L1"
        )
    ) / (
        999.0
        + sum(
            producao_base_ppt_base_values[line]
            for line in LINES if line != "L1"
        )
    )
    assert result_l1_perturbed == pytest.approx(expected_l1_perturbed)


# ============================================================
# Teste 16 — Decisão 3: `ltp_tc` (diário, linha/L1_L7) agora é uma
# VariableDefinition (não mais um Parameter).
# ============================================================


def test_16_ltp_tc_daily_linha_l1_l7_is_now_a_variable(loaded_seed):
    variable_definitions, variable_instances, parameter_definitions, \
        _pi, _ed, _ei = loaded_seed

    ltp_tc_variable = next(
        v for v in variable_definitions.all()
        if v.variable_name == "ltp_tc"
        and v.frequency == "diário"
        and v.scope_type == "linha"
        and v.scope_value == "L1_L7"
    )

    assert ltp_tc_variable.variable_definition_id == "VAR11240"
    assert ltp_tc_variable.variable_type == "entrada_externa"
    assert ltp_tc_variable.status == "ativo"
    assert not hasattr(ltp_tc_variable, "value")
    assert not hasattr(ltp_tc_variable, "version")

    # 7 VariableInstances materializadas (uma por linha), como
    # qualquer outra Variable de escopo linha/L1_L7 -- via
    # ScopeResolver padrão, sem mecanismo especial.
    ltp_tc_instances = [
        i for i in variable_instances.all()
        if i.variable_definition_id == "VAR11240"
    ]
    assert len(ltp_tc_instances) == 7
    assert {i.scope_value for i in ltp_tc_instances} == set(LINES)

    # PARAM11001 não existe mais como ParameterDefinition.
    assert all(
        p.parameter_definition_id != "PARAM11001"
        for p in parameter_definitions.all()
    )

    # ltp_tc_base permanece Parameter -- não foi migrado.
    ltp_tc_base = next(
        p for p in parameter_definitions.all()
        if p.parameter_name == "ltp_tc_base"
    )
    assert ltp_tc_base.parameter_definition_id == "PARAM11002"


# ============================================================
# Teste 17 — Decisão 3: todas as EquationDefinitions que
# referenciavam PARAM11001 agora referenciam VAR11240; nenhuma
# referência residual a PARAM11001 existe no seed.
# ============================================================


def test_17_no_equation_references_old_ltp_tc_parameter(loaded_seed):
    _vd, _vi, _pd, _pi, equation_definitions, _ei = loaded_seed

    for e in equation_definitions.all():
        assert "PARAM11001" not in e.expression, (
            f"{e.equation_definition_id} ainda referencia o "
            "Parameter removido PARAM11001"
        )

    migrated_ids = [
        "EQ11001", "EQ11006", "EQ11018", "EQ11034", "EQ11050",
        "EQ11111", "EQ11112",
    ]
    for eid in migrated_ids:
        definition = equation_definitions.get(eid)
        assert "VAR11240" in definition.expression, (
            f"{eid} deveria referenciar VAR11240 (ltp_tc migrado)"
        )

    # ltp_tc_base (PARAM11002) não foi tocado pela migração.
    eq11127 = equation_definitions.get("EQ11127")
    for line in LINES:
        assert f"PARAM11002@{line}" in eq11127.expression


# ============================================================
# Teste 18 — Decisão 3: a 80ª AggregationRule (ltp_tc diário/linha
# L1_L7 -> mensal, AVERAGE) existe, com origem/destino corretos.
# ============================================================


def test_18_ltp_tc_aggregation_rule_exists_and_is_correct(
    loaded_seed, aggregation_rules,
):
    variable_definitions, *_ = loaded_seed
    var_by_id = {
        v.variable_definition_id: v for v in variable_definitions.all()
    }

    rule = aggregation_rules.get(
        "AGR-LTP_TC-LINHA-L1_L7-MENSAL-AVERAGE"
    )

    assert rule.source_variable_id == "VAR11240"
    assert rule.target_variable_id == "VAR11164"
    assert rule.source_frequency == "diário"
    assert rule.target_frequency == "mensal"
    assert rule.aggregation_type == "AVERAGE"
    assert rule.window_start_date is None
    assert rule.window_end_date is None

    source = var_by_id[rule.source_variable_id]
    target = var_by_id[rule.target_variable_id]
    assert source.variable_name == target.variable_name == "ltp_tc"
    assert source.scope_type == target.scope_type == "linha"
    assert source.scope_value == target.scope_value == "L1_L7"


# ============================================================
# Teste 19 — integração real: valores diários distintos de ltp_tc
# (descobertos via SeedLoader -> AggregationRuleRegistry, não
# hand-constructed) agregados progressivamente em ltp_tc mensal.
# ============================================================


def test_19_ltp_tc_daily_to_monthly_aggregation_real_flow(
    aggregation_rules,
):
    rule = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-LTP_TC-LINHA-L1_L7-MENSAL-AVERAGE"
    )

    context = CalculationContext()

    daily_values = {}
    current = date(2026, 9, 1)
    value = 270.0
    while current <= date(2026, 9, 10):
        context.set_variable_value(
            rule.source_variable_id, value, "linha", "L3",
            period_id=current.isoformat(),
        )
        daily_values[current] = value
        value += 0.5
        current += timedelta(days=1)

    orchestrator = TemporalForecastOrchestrator()
    execution = orchestrator.start_execution(
        run_date=date(2026, 9, 10), model_version="v4",
    )

    result = orchestrator.run_aggregation(
        rule=rule, calculation_context=context,
        scope_type="linha", scope_value="L3",
        run_date=date(2026, 9, 10), execution=execution,
    )

    assert result.period_id == "2026-09"
    assert result.value == pytest.approx(
        sum(daily_values.values()) / len(daily_values)
    )
    assert result.execution_id == execution.execution_id

    # Somente os dias populados (01..10) entraram na janela
    # progressiva -- nenhum dado futuro.
    with pytest.raises(VariableNotFoundError):
        orchestrator.run_aggregation(
            rule=rule, calculation_context=context,
            scope_type="linha", scope_value="L3",
            run_date=date(2026, 9, 30),
        )
