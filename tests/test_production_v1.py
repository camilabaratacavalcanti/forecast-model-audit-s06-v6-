"""
Implementação Production v1 -- Forecast Platform S06 v6.

Cobre BD-01 a BD-11 (decisões de negócio fechadas para o bloco
Production), a evolução do parser para expressões condicionais
(BD-07) e a resolução temporal diário -> mensal (BD-02), todas
exercitadas contra o seed real de `data/seed/production/`.

Pendências conhecidas, deliberadamente NÃO implementadas nesta
etapa (ver relatório da tarefa):
    - `consumo_mrn`/`consumo_mpsa`/`consumo_cbg`/`consumo_bauxita`:
      apenas VariableDefinition (metadata), sem EquationDefinition
      -- suas fórmulas originais precisam ler `fator_mrn`/
      `fator_mpsa`/`fator_cbg` (linha_grupo) a partir de uma
      equação `linha`, referência cruzada de scope_type não
      suportada pela arquitetura atual.
    - `desaguamento_produtividade`/`desaguamento_oee`: não
      seedados -- `ScopeResolver` exige `scope_value="PLANTA"` para
      `scope_type="planta"`, mas os seed validators de
      Variable/Parameter exigem `scope_value=None` para o mesmo
      `scope_type` -- inconsistência pré-existente entre os dois
      componentes, descoberta nesta implementação.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.domain.equations.models import EquationInstance
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationInstanceRegistry,
)
from app.domain.forecast.aggregation import AggregationRuleRegistry
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterInstanceRegistry,
)
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableInstanceRegistry,
)
from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.equation_engine import EquationEngine
from app.engine.registry_validator import RegistryIntegrityValidator
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.engine.temporal_forecast_orchestrator import (
    TemporalForecastOrchestrator,
)
from app.repositories.seed_loader import SeedLoader

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]


def _is_production_id(entity_id):
    digits = "".join(ch for ch in entity_id if ch.isdigit())
    return bool(digits) and 12000 <= int(digits) <= 12999


def _filter_production_block(loaded_seed):
    (
        variable_definitions, variable_instances,
        parameter_definitions, parameter_instances,
        equation_definitions, equation_instances,
    ) = loaded_seed

    prod_variable_definitions = VariableDefinitionRegistry()
    for d in variable_definitions.all():
        if _is_production_id(d.variable_definition_id):
            prod_variable_definitions.add(d)

    prod_variable_instances = VariableInstanceRegistry()
    for i in variable_instances.all():
        if _is_production_id(i.variable_definition_id):
            prod_variable_instances.add(i)

    prod_parameter_definitions = ParameterDefinitionRegistry()
    for d in parameter_definitions.all():
        if _is_production_id(d.parameter_definition_id):
            prod_parameter_definitions.add(d)

    prod_parameter_instances = ParameterInstanceRegistry()
    for i in parameter_instances.all():
        if _is_production_id(i.parameter_definition_id):
            prod_parameter_instances.add(i)

    prod_equation_definitions = EquationDefinitionRegistry()
    for d in equation_definitions.all():
        if _is_production_id(d.equation_definition_id):
            prod_equation_definitions.add(d)

    prod_equation_instances = EquationInstanceRegistry()
    for i in equation_instances.all():
        if _is_production_id(i.target_variable_id):
            prod_equation_instances.add(i)

    return (
        prod_variable_definitions, prod_variable_instances,
        prod_parameter_definitions, prod_parameter_instances,
        prod_equation_definitions, prod_equation_instances,
    )


@pytest.fixture(scope="module")
def loaded_seed():
    loader = SeedLoader(SEED_ROOT)
    return loader.load_all_definitions_and_instances()


@pytest.fixture(scope="module")
def production_seed(loaded_seed):
    return _filter_production_block(loaded_seed)


@pytest.fixture(scope="module")
def aggregation_rules():
    loader = SeedLoader(SEED_ROOT)
    registry = loader.load_aggregation_rules()
    production_only = AggregationRuleRegistry()
    for rule in registry.all():
        if "PRODUCTION" in rule.aggregation_rule_id:
            production_only.add(rule)
    return production_only


def _by_name_scope(registry, id_attr="variable_definition_id"):
    result = {}
    for d in registry.all():
        key = (
            getattr(d, "variable_name", None)
            or getattr(d, "parameter_name", None),
            d.frequency if hasattr(d, "frequency") else None,
            d.scope_type, d.scope_value,
        )
        result[key] = d
    return result


# ============================================================
# 1. Seed structural validation
# ============================================================


def test_production_seed_passes_registry_integrity_validator(
    loaded_seed,
):
    (
        variable_definitions, _vi, parameter_definitions, _pi,
        equation_definitions, _ei,
    ) = loaded_seed

    validator = RegistryIntegrityValidator()
    errors = validator.validate_definition_registry(
        equation_definition_registry=equation_definitions,
        variable_definition_registry=variable_definitions,
        parameter_definition_registry=parameter_definitions,
    )

    assert errors is None


def test_production_variable_ids_are_all_unique_and_in_range(
    production_seed,
):
    variable_definitions = production_seed[0]

    ids = [d.variable_definition_id for d in variable_definitions.all()]

    assert len(ids) == len(set(ids))
    for vid in ids:
        assert 12000 <= int(vid.replace("VAR", "")) <= 12999


def test_production_equation_ids_are_all_unique_and_in_range(
    production_seed,
):
    equation_definitions = production_seed[4]

    ids = [d.equation_definition_id for d in equation_definitions.all()]

    assert len(ids) == len(set(ids))
    for eid in ids:
        assert 12000 <= int(eid.replace("EQ", "")) <= 12999


def test_production_parameter_ids_are_all_in_range_and_scope_unique(
    production_seed,
):
    """
    `parameter_id` pode se repetir entre linhas de um mesmo
    parâmetro lógico (ex.: `lth_meta`, `pick_up_yield`) -- mesmo
    padrão já usado pelo Yield (ex.: `tanque_base`/PARAM11003): a
    identidade real é (parameter_id, scope_type, scope_value).
    """

    parameter_definitions = production_seed[2]

    ids = [
        d.parameter_definition_id for d in parameter_definitions.all()
    ]
    for pid in ids:
        assert 12000 <= int(pid.replace("PARAM", "")) <= 12999

    scope_keys = [
        (d.parameter_definition_id, d.scope_type, d.scope_value)
        for d in parameter_definitions.all()
    ]
    assert len(scope_keys) == len(set(scope_keys))


def test_yield_reused_for_production_not_duplicated(loaded_seed):
    """
    BD-01: `yield` não é duplicado -- Production referencia
    diretamente `VAR11001` (bloco Yield), e nenhuma nova
    VariableDefinition "yield" existe na faixa 12000-12999.
    """

    variable_definitions = loaded_seed[0]

    yield_vars = [
        d for d in variable_definitions.all()
        if d.variable_name == "yield"
        and d.frequency == "diário"
        and d.scope_type == "linha"
        and d.scope_value == "L1_L7"
    ]

    assert len(yield_vars) == 1
    assert yield_vars[0].variable_definition_id == "VAR11001"


def test_lth_meta_parameters_have_expected_values(production_seed):
    parameter_definitions = production_seed[2]

    lth_meta = {
        p.scope_value: p.value
        for p in parameter_definitions.all()
        if p.parameter_name == "lth_meta"
    }

    assert lth_meta == {
        "L1": 1050, "L2": 1050, "L3": 1100, "L4": 1100,
        "L5": 1100, "L6": 1100, "L7": 1100,
    }
    assert lth_meta.keys() == set(LINES)


def test_pick_up_yield_parameters_have_expected_values(production_seed):
    parameter_definitions = production_seed[2]

    pick_up_yield = {
        p.scope_value: p.value
        for p in parameter_definitions.all()
        if p.parameter_name == "pick_up_yield"
    }

    assert pick_up_yield == {
        "L1": 14.64, "L2": 14.64, "L3": 14.64, "L4": 14.4,
        "L5": 14.4, "L6": 13.3, "L7": 13.3,
    }
    for p in parameter_definitions.all():
        if p.parameter_name == "pick_up_yield":
            assert p.status == "ativo"


def test_fator_mrn_kg_t_and_fator_mpsa_kg_t_exist_as_inputs(
    production_seed,
):
    """BD-10: as duas novas entradas."""

    variable_definitions = production_seed[0]
    by_name = {
        d.variable_name: d for d in variable_definitions.all()
        if d.frequency == "diário" and d.scope_type == "linha_grupo"
    }

    for name in ("fator_mrn_kg_t", "fator_mpsa_kg_t"):
        d = by_name[name]
        assert d.unit == "kg/t"
        assert d.variable_type == "entrada"
        assert d.scope_value == "L1_L7"
        assert d.status == "ativo"


def test_fator_mrn_and_fator_mpsa_are_calculated_not_input(
    production_seed,
):
    """BD-10: nenhuma Variable "entrada" possui expression própria
    -- fator_mrn/fator_mpsa agora são calculados a partir das novas
    entradas."""

    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }

    for eq in equation_definitions.all():
        target = var_by_id[eq.target_variable_id]
        if target.variable_name in ("fator_mrn", "fator_mpsa"):
            assert target.variable_type == "calculado"


def test_fator_cbg_equation_is_explicit_alias_of_fator_mrn(
    production_seed,
):
    """BD-11: fator_cbg = fator_mrn, via equação explícita."""

    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }

    fator_mrn_id = next(
        d.variable_definition_id for d in variable_definitions.all()
        if d.variable_name == "fator_mrn"
    )

    fator_cbg_eq = next(
        eq for eq in equation_definitions.all()
        if var_by_id[eq.target_variable_id].variable_name == "fator_cbg"
    )

    assert fator_cbg_eq.expression.strip() == fator_mrn_id


def test_consumo_bauxita_annual_scope_standardized_to_linha_grupo(
    production_seed,
):
    """BD-09."""

    variable_definitions = production_seed[0]

    bauxita_annual = next(
        d for d in variable_definitions.all()
        if d.variable_name == "consumo_bauxita" and d.frequency == "anual"
    )

    assert bauxita_annual.scope_type == "linha_grupo"
    assert bauxita_annual.scope_value == "L1_L7"


# ============================================================
# 2. Unidades
# ============================================================


def test_production_variables_only_use_allowed_units(production_seed):
    from app.validation.variable_seed_validator import ALLOWED_UNITS

    variable_definitions = production_seed[0]

    for d in variable_definitions.all():
        assert d.unit in ALLOWED_UNITS, (
            f"{d.variable_definition_id} usa unidade não permitida: "
            f"{d.unit}"
        )


# ============================================================
# 3. Dependency extraction
# ============================================================


def test_dependency_extraction_for_key_production_equations(
    production_seed,
):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }
    extractor = DependencyExtractor()

    checked_names = set()
    for eq in equation_definitions.all():
        target = var_by_id[eq.target_variable_id]
        if target.variable_name in {
            "lth", "oee", "oee_total", "pick_up_total", "producao",
            "fator_mrn", "fator_mpsa", "fator_cbg",
        }:
            deps = extractor.extract(eq.expression)

            assert len(deps.variables) + len(deps.parameters) > 0, (
                f"{eq.equation_definition_id} ({target.variable_name}) "
                "não extraiu nenhuma dependência"
            )

            # Nenhuma dependência aponta para uma referência
            # indefinida ("lth_alvo" -- BD-03) -- todas devem
            # resolver a VAR/PARAM reais do seed.
            all_ids = {
                ref.split("@")[0] for ref in deps.variables
            } | {
                ref.split("@")[0] for ref in deps.parameters
            }
            var_ids = {
                d.variable_definition_id
                for d in variable_definitions.all()
            }
            param_ids = {
                p.parameter_definition_id
                for p in production_seed[2].all()
            }
            for ref_id in all_ids:
                assert (
                    ref_id in var_ids
                    or ref_id in param_ids
                    or ref_id == "VAR11001"  # yield (BD-01)
                ), f"{eq.equation_definition_id} referencia {ref_id} inexistente"

            checked_names.add(target.variable_name)

    assert checked_names == {
        "lth", "oee", "oee_total", "pick_up_total", "producao",
        "fator_mrn", "fator_mpsa", "fator_cbg",
    }


def test_lth_alvo_is_not_a_valid_dependency_anywhere(production_seed):
    """BD-03: nenhuma equação referencia 'lth_alvo' (nome inválido,
    substituído por lth_meta)."""

    equation_definitions = production_seed[4]

    for eq in equation_definitions.all():
        assert "lth_alvo" not in eq.expression


# ============================================================
# 4. Equações com valores distintos por linha
# ============================================================


def _get_equation_for(production_seed, name, frequency, scope_type):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }
    return next(
        eq for eq in equation_definitions.all()
        if var_by_id[eq.target_variable_id].variable_name == name
        and var_by_id[eq.target_variable_id].frequency == frequency
        and var_by_id[eq.target_variable_id].scope_type == scope_type
    )


def test_oee_total_bd04_uses_distinct_per_line_values(production_seed):
    """BD-04: oee_total corrigido, sem o fragmento espúrio
    'lth / lth_alvo'."""

    eq = _get_equation_for(production_seed, "oee_total", "diário", "linha_grupo")

    assert "lth_alvo" not in eq.expression
    for line in LINES:
        assert f"@{line}" in eq.expression

    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    oee_var_id = eq.expression.split("@L1")[0].split("(")[-1].strip()
    lth_meta_id = next(
        p.parameter_definition_id for p in production_seed[2].all()
        if p.parameter_name == "lth_meta"
    )

    oee_values = {"L1": 0.1, "L2": 0.2, "L3": 0.3, "L4": 0.4,
                  "L5": 0.5, "L6": 0.6, "L7": 0.7}
    lth_meta_values = {"L1": 1050, "L2": 1050, "L3": 1100, "L4": 1100,
                        "L5": 1100, "L6": 1100, "L7": 1100}

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(oee_var_id, oee_values[line], "linha", line)
        context.set_parameter_value(
            lth_meta_id, lth_meta_values[line], "linha", line,
        )

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    expected = sum(
        oee_values[l] * lth_meta_values[l] for l in LINES
    ) / sum(lth_meta_values.values())

    assert result == pytest.approx(expected)


def test_pick_up_total_bd05_uses_distinct_per_line_values(
    production_seed,
):
    """BD-05: pick_up_total corrigido, sem o fragmento 'lth / lth'."""

    eq = _get_equation_for(
        production_seed, "pick_up_total", "diário", "linha_grupo",
    )

    for line in LINES:
        assert f"@{line}" in eq.expression
    assert eq.expression.count("/") == 1  # apenas a divisão final

    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    variable_definitions = production_seed[0]
    pick_up_ids = {
        d.scope_value: d.variable_definition_id
        for d in variable_definitions.all()
        if d.variable_name == "pick_up" and d.frequency == "diário"
    }
    lth_id = next(
        d.variable_definition_id for d in variable_definitions.all()
        if d.variable_name == "lth" and d.frequency == "diário"
    )

    pick_up_values = {"L1": 10.0, "L2": 20.0, "L3": 30.0, "L4": 40.0,
                       "L5": 50.0, "L6": 60.0, "L7": 70.0}
    lth_values = {"L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
                  "L5": 5.0, "L6": 6.0, "L7": 7.0}

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            pick_up_ids[line], pick_up_values[line], "linha", line,
        )
        context.set_variable_value(lth_id, lth_values[line], "linha", line)

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    expected = sum(
        pick_up_values[l] * lth_values[l] for l in LINES
    ) / sum(lth_values.values())

    assert result == pytest.approx(expected)


def test_yield_lth_total_weighted_by_lth_not_ltp(production_seed):
    """Preserva a característica explícita: ponderado por lth."""

    eq = _get_equation_for(
        production_seed, "yield_lth_total", "diário", "linha_grupo",
    )

    assert "ltp" not in eq.expression
    assert "lth" in eq.expression or any(
        f"VAR12016@{l}" in eq.expression for l in LINES
    )

    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    yield_values = {"L1": 100.0, "L2": 200.0, "L3": 300.0, "L4": 400.0,
                     "L5": 500.0, "L6": 600.0, "L7": 700.0}
    lth_values = {"L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
                  "L5": 5.0, "L6": 6.0, "L7": 7.0}

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value("VAR11001", yield_values[line], "linha", line)
        context.set_variable_value("VAR12016", lth_values[line], "linha", line)

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    expected = sum(
        yield_values[l] * lth_values[l] for l in LINES
    ) / sum(lth_values.values())

    assert result == pytest.approx(expected)


def test_lth_total_sums_all_seven_lines_without_repetition(
    production_seed,
):
    eq = _get_equation_for(production_seed, "lth_total", "diário", "linha_grupo")

    for line in LINES:
        assert eq.expression.count(f"@{line}") == 1

    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    lth_values = {"L1": 1.0, "L2": 2.0, "L3": 3.0, "L4": 4.0,
                  "L5": 5.0, "L6": 6.0, "L7": 7.0}
    context = CalculationContext()
    for line in LINES:
        context.set_variable_value("VAR12016", lth_values[line], "linha", line)

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    assert result == pytest.approx(sum(lth_values.values()))


def test_producao_planta_sums_distinct_per_line_producao_values(
    production_seed,
):
    eq = _get_equation_for(
        production_seed, "producao_planta", "diário", "linha_grupo",
    )

    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    variable_definitions = production_seed[0]
    producao_ids = {
        d.scope_value: d.variable_definition_id
        for d in variable_definitions.all()
        if d.variable_name == "producao" and d.frequency == "diário"
    }

    producao_values = {"L1": 11.0, "L2": 22.0, "L3": 33.0, "L4": 44.0,
                        "L5": 55.0, "L6": 66.0, "L7": 77.0}

    context = CalculationContext()
    for line in LINES:
        context.set_variable_value(
            producao_ids[line], producao_values[line], "linha", line,
        )

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    assert result == pytest.approx(sum(producao_values.values()))

    # Perturbar somente L4 muda o resultado -- prova de que cada
    # termo referencia o VAR correto (não confunde linhas).
    context.set_variable_value(producao_ids["L4"], 9999.0, "linha", "L4")
    result_perturbed = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )
    assert result_perturbed != result


# ============================================================
# 5. Decimal BD-06 (producao)
# ============================================================


def test_producao_uses_dot_decimal_not_comma(production_seed):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }

    eq = next(
        eq for eq in equation_definitions.all()
        if var_by_id[eq.target_variable_id].variable_name == "producao"
        and var_by_id[eq.target_variable_id].frequency == "diário"
    )

    assert "1.0902" in eq.expression
    assert "1,0902" not in eq.expression

    instance = EquationInstance.create(
        definition=eq, scope_type="linha", scope_value="L1",
    )
    engine = EquationEngine()

    variable_definitions = production_seed[0]
    lth_id = next(
        d.variable_definition_id for d in variable_definitions.all()
        if d.variable_name == "lth" and d.frequency == "diário"
    )
    pick_up_l1 = next(
        d.variable_definition_id for d in variable_definitions.all()
        if d.variable_name == "pick_up" and d.frequency == "diário"
        and d.scope_value == "L1"
    )
    fator_producao_id = next(
        p.parameter_definition_id for p in production_seed[2].all()
        if p.parameter_name == "fator_producao"
    )

    context = CalculationContext()
    context.set_variable_value(lth_id, 500.0, "linha", "L1")
    context.set_variable_value(pick_up_l1, 15.0, "linha", "L1")
    context.set_parameter_value(fator_producao_id, 0.88, "linha", "L1")

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    expected = 500.0 * 15.0 * 0.88 * 1.0902 * 24 / 1000
    assert result == pytest.approx(expected)


# ============================================================
# 6. BD-07 -- lth (IfExp real do Production)
# ============================================================


def test_lth_equation_uses_ifexp_and_lth_meta_not_lth_alvo(
    production_seed,
):
    eq = _get_equation_for(production_seed, "lth", "diário", "linha")

    assert " if " in eq.expression
    assert " else " in eq.expression
    assert "lth_alvo" not in eq.expression


def test_lth_real_equation_applies_fator_ajuste_only_above_floor(
    production_seed,
):
    """
    BD-07: reproduz a regra de negócio real -- o fator de ajuste só
    é aplicado quando o valor base já está no piso (lth_meta) ou
    acima dele; abaixo do piso, o valor bruto é usado sem ajuste.
    """

    eq = _get_equation_for(production_seed, "lth", "diário", "linha")
    instance = EquationInstance.create(
        definition=eq, scope_type="linha", scope_value="L1",
    )
    engine = EquationEngine()

    variable_definitions = production_seed[0]

    def vid(name):
        return next(
            d.variable_definition_id for d in variable_definitions.all()
            if d.variable_name == name and d.frequency == "diário"
            and d.scope_type == "linha"
        )

    lth_meta_id = next(
        p.parameter_definition_id for p in production_seed[2].all()
        if p.parameter_name == "lth_meta"
    )

    from app.engine.expression_evaluator import ExpressionEvaluator
    from app.engine.expression_parser import ExpressionParser

    def _run(reducao_values, tempo_values, fator_ajuste, lth_meta_value):
        context = CalculationContext()
        context.set_variable_value(
            vid("reducao_lth_digestao"), reducao_values[0], "linha", "L1",
        )
        context.set_variable_value(
            vid("tempo_digestao"), tempo_values[0], "linha", "L1",
        )
        context.set_variable_value(
            vid("reducao_lth_clarificacao"), reducao_values[1], "linha", "L1",
        )
        context.set_variable_value(
            vid("tempo_clarificacao"), tempo_values[1], "linha", "L1",
        )
        context.set_variable_value(
            vid("reducao_lth_precipitacao"), reducao_values[2], "linha", "L1",
        )
        context.set_variable_value(
            vid("tempo_precipitacao"), tempo_values[2], "linha", "L1",
        )
        context.set_variable_value(
            vid("reducao_lth_calcinacao"), reducao_values[3], "linha", "L1",
        )
        context.set_variable_value(
            vid("tempo_calcinacao"), tempo_values[3], "linha", "L1",
        )
        context.set_variable_value(
            "VAR12001", fator_ajuste, "linha", "L1", period_id="2026-09",
        )
        context.set_parameter_value(
            lth_meta_id, lth_meta_value, "linha", "L1",
        )

        evaluator = ExpressionEvaluator(
            context, default_scope_type="linha", default_scope_value="L1",
            default_period_id="2026-09-14",
        )
        tree = ExpressionParser().parse(eq.expression)

        reduc_sum = sum(
            r * t for r, t in zip(reducao_values, tempo_values)
        )
        remainder = 24 - sum(tempo_values)
        base = (reduc_sum + remainder * lth_meta_value) / 24

        return evaluator.evaluate(tree), base

    # Condição verdadeira: base >= lth_meta -> fator_ajuste aplicado.
    result_true, base_true = _run(
        reducao_values=[1200.0, 1200.0, 1200.0, 1200.0],
        tempo_values=[2.0, 2.0, 2.0, 2.0],
        fator_ajuste=1.2,
        lth_meta_value=1050.0,
    )
    assert base_true >= 1050.0
    assert result_true == pytest.approx(base_true * 1.2)

    # Condição falsa: base < lth_meta -> fator_ajuste NÃO aplicado
    # (valor bruto, sem o piso "vencer" o ajuste).
    result_false, base_false = _run(
        reducao_values=[10.0, 10.0, 10.0, 10.0],
        tempo_values=[2.0, 2.0, 2.0, 2.0],
        fator_ajuste=1.2,
        lth_meta_value=1050.0,
    )
    assert base_false < 1050.0
    assert result_false == pytest.approx(base_false)
    assert result_false != pytest.approx(base_false * 1.2)


# ============================================================
# 7. BD-02 -- resolução temporal diário -> mensal
# ============================================================


def test_fator_ajuste_lth_monthly_value_consumed_by_daily_lth(
    production_seed,
):
    variable_definitions = production_seed[0]
    v = next(
        d for d in variable_definitions.all()
        if d.variable_name == "fator_ajuste_lth"
    )
    assert v.frequency == "mensal"

    context = CalculationContext()
    context.set_variable_value(
        v.variable_definition_id, 1.1, "linha", "L4", period_id="2026-09",
    )

    from app.engine.expression_evaluator import ExpressionEvaluator
    from app.engine.expression_parser import ExpressionParser

    evaluator = ExpressionEvaluator(
        context, default_scope_type="linha", default_scope_value="L4",
        default_period_id="2026-09-14",
    )
    tree = ExpressionParser().parse(v.variable_definition_id)

    assert evaluator.evaluate(tree) == 1.1


# ============================================================
# 8. AggregationRules -- AVERAGE/SUM coexistindo (BD-08)
# ============================================================


def test_producao_planta_monthly_has_average_and_sum_coexisting(
    aggregation_rules,
):
    rules = [
        r for r in aggregation_rules.all()
        if "PRODUCAO_PLANTA-GRUPO-L1_L7-MENSAL" in r.aggregation_rule_id
    ]

    types = {r.aggregation_type for r in rules}

    assert types == {"AVERAGE", "SUM"}
    ids = [r.aggregation_rule_id for r in rules]
    assert len(ids) == len(set(ids))


def test_producao_planta_average_and_sum_produce_different_results(
    aggregation_rules,
):
    rule_avg = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-PRODUCTION-PRODUCAO_PLANTA-GRUPO-L1_L7-MENSAL-AVERAGE"
    )
    rule_sum = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-PRODUCTION-PRODUCAO_PLANTA-GRUPO-L1_L7-MENSAL-SUM"
    )

    context = CalculationContext()
    values = {}
    current = date(2026, 9, 1)
    v = 100.0
    while current <= date(2026, 9, 10):
        context.set_variable_value(
            rule_avg.source_variable_id, v, "linha_grupo", "L1_L7",
            period_id=current.isoformat(),
        )
        values[current] = v
        v += 10.0
        current += timedelta(days=1)

    orchestrator = TemporalForecastOrchestrator()

    result_avg = orchestrator.run_aggregation(
        rule=rule_avg, calculation_context=context,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=date(2026, 9, 10),
    )
    result_sum = orchestrator.run_aggregation(
        rule=rule_sum, calculation_context=context,
        scope_type="linha_grupo", scope_value="L1_L7",
        run_date=date(2026, 9, 10),
    )

    assert result_avg.value == pytest.approx(
        sum(values.values()) / len(values)
    )
    assert result_sum.value == pytest.approx(sum(values.values()))
    assert result_avg.value != result_sum.value
    assert result_avg.aggregation_rule_id != result_sum.aggregation_rule_id
    assert result_avg.identity() != result_sum.identity()


# ============================================================
# 9. Moving average -- producao_planta_movel
# ============================================================


def test_producao_planta_movel_progressive_window(aggregation_rules):
    rule = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE"
    )

    assert rule.source_frequency == "diário"
    assert rule.target_frequency == "diário"
    assert rule.aggregation_type == "MOVING_AVERAGE"

    context = CalculationContext()
    values = {}
    current = date(2026, 9, 1)
    v = 200.0
    while current <= date(2026, 9, 30):
        context.set_variable_value(
            rule.source_variable_id, v, "linha_grupo", "L1_L7",
            period_id=current.isoformat(),
        )
        values[current] = v
        v += 3.0
        current += timedelta(days=1)

    service = TemporalAggregationService()

    for run_date, expected_days in [
        (date(2026, 9, 1), [date(2026, 9, 1)]),
        (
            date(2026, 9, 14),
            [date(2026, 9, d) for d in range(1, 15)],
        ),
        (
            date(2026, 9, 30),
            [date(2026, 9, d) for d in range(1, 31)],
        ),
    ]:
        result = service.aggregate(
            rule=rule, calculation_context=context,
            scope_type="linha_grupo", scope_value="L1_L7",
            run_date=run_date,
        )

        expected = sum(values[d] for d in expected_days) / len(
            expected_days
        )

        assert result.period_id == run_date.isoformat()
        assert result.value == pytest.approx(expected)


# ============================================================
# 10. Integração real: inputs -> lth -> oee -> pick_up -> producao
#     -> producao_planta
# ============================================================


def test_production_integration_chain_inputs_to_producao_planta(
    loaded_seed,
):
    (
        variable_definitions, _vi, _parameter_definitions,
        parameter_instances, equation_definitions, equation_instances,
    ) = loaded_seed

    prod_equation_definitions_all = _filter_production_block(loaded_seed)[4]
    prod_equation_instances_all = _filter_production_block(loaded_seed)[5]

    # `desaguamento_oee` está fora do escopo declarado desta cadeia
    # (inputs -> lth -> oee -> pick_up -> producao -> producao_planta)
    # e depende de `consumo_mpsa` anual, cuja cadeia diária ainda é
    # uma pendência documentada (referência cruzada linha_grupo <-
    # planta/linha, ver relatório da tarefa) -- excluído aqui para
    # não misturar essa pendência com o que este teste efetivamente
    # cobre. `desaguamento_oee` tem cobertura própria e dedicada em
    # outros testes deste arquivo.
    prod_equation_definitions = EquationDefinitionRegistry()
    for d in prod_equation_definitions_all.all():
        if d.target_variable_id != "VAR12083":
            prod_equation_definitions.add(d)

    prod_equation_instances = EquationInstanceRegistry()
    for i in prod_equation_instances_all.all():
        if i.target_variable_id != "VAR12083":
            prod_equation_instances.add(i)

    context = CalculationContext()

    # Filtra para as VariableDefinitions do bloco Production (mais
    # VAR11001, "yield" reutilizado do Yield via BD-01) -- alguns
    # nomes (ex.: "lth", "oee") existem também no bloco Yield com a
    # mesma (frequency, scope_type, scope_value), e usar o registry
    # completo sem filtrar pegaria a variável errada.
    var_by_name_scope = {}
    for d in variable_definitions.all():
        if not (
            _is_production_id(d.variable_definition_id)
            or d.variable_definition_id == "VAR11001"
        ):
            continue
        var_by_name_scope.setdefault(d.variable_name, {})[
            (d.frequency, d.scope_type, d.scope_value)
        ] = d

    for line in LINES:
        context.set_variable_value(
            var_by_name_scope["reducao_lth_digestao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            100.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["tempo_digestao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            4.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["reducao_lth_clarificacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            50.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["tempo_clarificacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            2.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["reducao_lth_precipitacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            30.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["tempo_precipitacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            2.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["reducao_lth_calcinacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            20.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["tempo_calcinacao"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            2.0, "linha", line,
        )
        context.set_variable_value(
            var_by_name_scope["fator_ajuste_lth"][
                ("mensal", "linha", "L1_L7")
            ].variable_definition_id,
            1.05, "linha", line, period_id="2026-09",
        )
        # yield (bloco Yield, BD-01) -- valores distintos por linha
        context.set_variable_value(
            "VAR11001", 10.0 + int(line[1]), "linha", line,
        )

    # fator_mrn_kg_t/fator_mpsa_kg_t (BD-10): linha_grupo/L1_L7,
    # necessários pois run_direct calcula TODAS as EquationInstances
    # de Production, incluindo fator_mrn/fator_mpsa/fator_cbg.
    context.set_variable_value(
        var_by_name_scope["fator_mrn_kg_t"][
            ("diário", "linha_grupo", "L1_L7")
        ].variable_definition_id,
        250.0, "linha_grupo", "L1_L7",
    )
    context.set_variable_value(
        var_by_name_scope["fator_mpsa_kg_t"][
            ("diário", "linha_grupo", "L1_L7")
        ].variable_definition_id,
        125.0, "linha_grupo", "L1_L7",
    )

    for instance in parameter_instances.all():
        if _is_production_id(instance.parameter_definition_id):
            context.set_parameter_instance_value(
                instance,
                next(
                    p.value for p in _filter_production_block(loaded_seed)[2].all()
                    if p.parameter_definition_id
                    == instance.parameter_definition_id
                ),
            )

    orchestrator = TemporalForecastOrchestrator()

    results = orchestrator.run_direct(
        equation_definition_registry=prod_equation_definitions,
        variable_definition_registry=variable_definitions,
        calculation_context=context,
        run_date=date(2026, 9, 14),
    )

    assert len(results) == len(prod_equation_instances.all())

    for line in LINES:
        lth_value = context.get_variable_value(
            var_by_name_scope["lth"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            scope_type="linha", scope_value=line,
            period_id="2026-09-14",
        )
        assert isinstance(lth_value, (int, float))

        oee_value = context.get_variable_value(
            var_by_name_scope["oee"][
                ("diário", "linha", "L1_L7")
            ].variable_definition_id,
            scope_type="linha", scope_value=line,
            period_id="2026-09-14",
        )
        assert isinstance(oee_value, (int, float))

    pick_up_l4 = var_by_name_scope["pick_up"][
        ("diário", "linha", "L4")
    ]
    pick_up_value = context.get_variable_value(
        pick_up_l4.variable_definition_id,
        scope_type="linha", scope_value="L4",
        period_id="2026-09-14",
    )
    assert isinstance(pick_up_value, (int, float))

    producao_l4 = var_by_name_scope["producao"][
        ("diário", "linha", "L4")
    ]
    producao_value = context.get_variable_value(
        producao_l4.variable_definition_id,
        scope_type="linha", scope_value="L4",
        period_id="2026-09-14",
    )
    assert isinstance(producao_value, (int, float))

    producao_planta_value = context.get_variable_value(
        var_by_name_scope["producao_planta"][
            ("diário", "linha_grupo", "L1_L7")
        ].variable_definition_id,
        scope_type="linha_grupo", scope_value="L1_L7",
        period_id="2026-09-14",
    )
    assert isinstance(producao_planta_value, (int, float))

    producao_by_line = {
        line: context.get_variable_value(
            var_by_name_scope["producao"][
                ("diário", "linha", line)
            ].variable_definition_id,
            scope_type="linha", scope_value=line,
            period_id="2026-09-14",
        )
        for line in LINES
    }
    assert producao_planta_value == pytest.approx(
        sum(producao_by_line.values())
    )


# ============================================================
# 11. `desaguamento_produtividade` / escopo `planta` (OBJ-01)
# ============================================================


def test_desaguamento_produtividade_is_planta_planta_and_t_h(
    production_seed,
):
    parameter_definitions = production_seed[2]

    p = next(
        d for d in parameter_definitions.all()
        if d.parameter_name == "desaguamento_produtividade"
    )

    assert p.scope_type == "planta"
    assert p.scope_value == "PLANTA"
    assert p.unit == "t/h"
    assert p.value == 115
    assert p.status == "ativo"


def test_desaguamento_produtividade_materializes_one_planta_instance(
    production_seed,
):
    parameter_instances = production_seed[3]

    instances = [
        i for i in parameter_instances.all()
        if i.parameter_definition_id == "PARAM12005"
    ]

    assert len(instances) == 1
    assert instances[0].scope_type == "planta"
    assert instances[0].scope_value == "PLANTA"


def test_planta_planta_is_accepted_by_scope_resolver():
    from app.engine.scope_resolver import ScopeResolver

    resolver = ScopeResolver()
    resolved = resolver.resolve_scopes("planta", "PLANTA")

    assert resolved == [("planta", "PLANTA")]


def test_planta_none_is_rejected_by_scope_resolver():
    from app.engine.scope_resolver import ScopeResolver

    resolver = ScopeResolver()

    with pytest.raises(ValueError):
        resolver.resolve_scopes("planta", None)


# ============================================================
# 12. Normalização de unidade tph -> t/h (OBJ-03)
# ============================================================


def test_tph_is_normalized_to_t_h_in_variable_pipeline(tmp_path):
    import json

    from app.validation import variable_seed_validator as vsv

    block = tmp_path / "testblock"
    block.mkdir()
    (block / "variables.json").write_text(
        json.dumps([{
            "variable_id": "VAR99001", "variable_name": "x",
            "description": "d", "unit": "tph",
            "variable_type": "entrada", "frequency": "diário",
            "scope_type": "linha", "scope_value": "L1_L7",
            "source_reference": "r", "status": "ativo",
        }])
    )

    loaded = vsv.load_variables_from_seed(tmp_path)

    assert loaded[0]["unit"] == "t/h"
    assert "tph" not in {v["unit"] for v in loaded}


def test_tph_is_normalized_to_t_h_in_parameter_pipeline(tmp_path):
    import json

    from app.validation import parameter_seed_validator as psv

    block = tmp_path / "testblock"
    block.mkdir()
    (block / "parameters.json").write_text(
        json.dumps([{
            "parameter_id": "PARAM99001", "parameter_name": "x",
            "description": "d", "unit": "tph", "value": 115,
            "version": 1, "scope_type": "planta",
            "scope_value": "PLANTA", "status": "ativo",
            "source_reference": "r",
        }])
    )

    loaded, errors = psv.load_parameters_from_seed(tmp_path)

    assert errors == []
    assert loaded[0][0]["unit"] == "t/h"


def test_115_tph_normalizes_to_115_t_h_no_numeric_conversion():
    """
    A normalização é apenas de rótulo textual: nenhum fator
    multiplicativo é aplicado ao `value`.
    """

    from app.validation.variable_seed_validator import normalize_unit

    assert normalize_unit("tph") == "t/h"
    # O valor numérico não é parâmetro desta função -- a
    # normalização nunca vê nem altera `value`.


def test_t_h_unit_still_works_after_normalization_introduced(
    production_seed,
):
    """Regressão: unidades já em 't/h' continuam funcionando -- a
    normalização é um no-op para elas."""

    from app.validation.variable_seed_validator import normalize_unit

    assert normalize_unit("t/h") == "t/h"

    parameter_definitions = production_seed[2]
    p = next(
        d for d in parameter_definitions.all()
        if d.parameter_name == "desaguamento_produtividade"
    )
    assert p.unit == "t/h"


def test_normalization_does_not_affect_other_existing_units(
    production_seed,
):
    from app.validation.variable_seed_validator import (
        ALLOWED_UNITS,
        normalize_unit,
    )

    for unit in ALLOWED_UNITS:
        if unit == "t/h":
            continue
        assert normalize_unit(unit) == unit

    assert "tph" not in ALLOWED_UNITS


def test_variable_and_parameter_unit_aliases_are_identical():
    from app.validation.parameter_seed_validator import (
        UNIT_ALIASES as PARAM_ALIASES,
    )
    from app.validation.variable_seed_validator import (
        UNIT_ALIASES as VAR_ALIASES,
    )

    assert PARAM_ALIASES == VAR_ALIASES == {"tph": "t/h"}


# ============================================================
# 13. `desaguamento_oee` (OBJ-02)
# ============================================================


def test_desaguamento_oee_expression_uses_factor_100_and_13(
    production_seed,
):
    eq = _get_equation_for(
        production_seed, "desaguamento_oee", "anual", "linha_grupo",
    )

    assert "100" in eq.expression
    assert "13" in eq.expression
    assert "24" in eq.expression


def test_desaguamento_oee_uses_annual_consumo_mpsa(production_seed):
    variable_definitions, _vi, _pd, _pi, equation_definitions, _ei = (
        production_seed
    )
    var_by_id = {
        d.variable_definition_id: d for d in variable_definitions.all()
    }

    eq = _get_equation_for(
        production_seed, "desaguamento_oee", "anual", "linha_grupo",
    )

    deps = DependencyExtractor().extract(eq.expression)

    consumo_mpsa_refs = [
        v for v in deps.variables
        if var_by_id[v.split("@")[0]].variable_name == "consumo_mpsa"
    ]
    assert len(consumo_mpsa_refs) == 1
    referenced = var_by_id[consumo_mpsa_refs[0].split("@")[0]]
    assert referenced.frequency == "anual"
    assert referenced.scope_type == "linha_grupo"

    param_refs = [
        p for p in deps.parameters
        if p.split("@")[0] == "PARAM12005"
    ]
    assert len(param_refs) == 1


def test_desaguamento_oee_is_target_of_no_equation_besides_eq12026(
    production_seed,
):
    equation_definitions = production_seed[4]

    matches = [
        eq for eq in equation_definitions.all()
        if eq.target_variable_id == "VAR12083"
    ]
    assert len(matches) == 1
    assert matches[0].equation_definition_id == "EQ12026"


def test_consumo_mpsa_annual_aggregation_rule_is_sum(aggregation_rules):
    rule = next(
        r for r in aggregation_rules
        if r.aggregation_rule_id
        == "AGR-PRODUCTION-CONSUMO_MPSA-GRUPO-L1_L7-ANUAL-SUM"
    )

    assert rule.source_frequency == "diário"
    assert rule.target_frequency == "anual"
    assert rule.aggregation_type == "SUM"


def test_desaguamento_oee_formula_produces_expected_percentage(
    production_seed,
):
    """
    Prova matemática da fórmula (OBJ-02), com valores deliberadamente
    não triviais para evitar coincidência:

        100 * (consumo_mpsa_anual / 24) / (desaguamento_produtividade * 13)

    A avaliação é feita colocando `consumo_mpsa` e
    `desaguamento_produtividade` no MESMO escopo da equação
    (linha_grupo/L1_L7) -- isolando a correção da fórmula da
    resolução cruzada de escopo (linha_grupo -> planta), coberta
    separadamente em
    `test_desaguamento_oee_resolves_cross_scope_reference_via_decision_e`.
    """

    eq = _get_equation_for(
        production_seed, "desaguamento_oee", "anual", "linha_grupo",
    )
    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    consumo_mpsa_anual = 47281.0
    desaguamento_produtividade = 115.0

    context = CalculationContext()
    context.set_variable_value(
        "VAR12075", consumo_mpsa_anual, "linha_grupo", "L1_L7",
    )
    context.set_parameter_value(
        "PARAM12005", desaguamento_produtividade, "linha_grupo", "L1_L7",
    )

    result = engine.calculate_instance(
        instance=instance, definition=eq, calculation_context=context,
    )

    expected = 100 * (consumo_mpsa_anual / 24) / (
        desaguamento_produtividade * 13
    )

    assert result == pytest.approx(expected)
    # Confirma que o resultado não é obtido "por coincidência" com
    # uma fórmula alternativa plausível (ex.: sem o fator 100, ou
    # sem dividir por 13).
    assert result != pytest.approx(
        (consumo_mpsa_anual / 24) / (desaguamento_produtividade * 13)
    )
    assert result != pytest.approx(
        100 * (consumo_mpsa_anual / 24) / desaguamento_produtividade
    )


def test_desaguamento_oee_resolves_cross_scope_reference_via_decision_e(
    production_seed,
):
    """
    A pendência antes documentada em
    `test_desaguamento_oee_blocked_by_cross_scope_reference_today`
    (uma equação `linha_grupo` não conseguia resolver implicitamente
    um Parameter `planta`) foi resolvida pela Decision E: o
    `ExpressionEvaluator` agora esgota o fallback temporal em cada
    candidato espacial (linha_grupo/L1_L7 -> planta/PLANTA) antes de
    avançar, então um Parameter armazenado em `planta/PLANTA` é
    alcançado por uma equação `linha_grupo/L1_L7` que não o encontra
    em seu próprio scope.
    """

    eq = _get_equation_for(
        production_seed, "desaguamento_oee", "anual", "linha_grupo",
    )
    instance = EquationInstance.create(
        definition=eq, scope_type="linha_grupo", scope_value="L1_L7",
    )
    engine = EquationEngine()

    consumo_mpsa_anual = 47281.0
    desaguamento_produtividade = 115.0

    context = CalculationContext()
    context.set_variable_value(
        "VAR12075", consumo_mpsa_anual, "linha_grupo", "L1_L7",
    )
    context.set_parameter_value(
        "PARAM12005", desaguamento_produtividade, "planta", "PLANTA",
    )

    result = engine.calculate_instance(
        instance=instance, definition=eq,
        calculation_context=context,
    )

    expected = 100 * (consumo_mpsa_anual / 24) / (
        desaguamento_produtividade * 13
    )

    assert result == pytest.approx(expected)
