"""
Objetivo (FASE 3A — Parte D):
    Validar o seed real do bloco Yield fim a fim, através dos
    componentes reais da plataforma — sem mocks:

        SeedLoader real
        -> Definition Registries reais
        -> Instance Registries reais (ScopeResolver real)
        -> RegistryIntegrityValidator real (integridade + escopo)
        -> DependencyGraph real
        -> ForecastEngine/EquationEngine reais

    Cobre especificamente:
    - tanque_base@L1..L7 e tanque@L1..L7 corretamente materializados;
    - n_ppt@L1..L7 resolvendo a referência contextual
      "tanque_base - tanque" sem duplicar a definição por linha;
    - nenhuma equação DRAFT no caminho normal de execução;
    - a fórmula oficial de Ratio_spent usando o coeficiente 0.0007.
"""

from pathlib import Path

import pytest

from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine
from app.engine.registry_validator import RegistryIntegrityValidator
from app.repositories.seed_loader import SeedLoader
from app.validation import equation_seed_validator as esv
from app.validation import parameter_seed_validator as psv
from app.validation import variable_seed_validator as vsv

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

# Valores de entrada usados para exercitar o Engine real ponta a
# ponta. Não representam nenhuma referência de negócio específica —
# servem apenas para comprovar que o fluxo calcula corretamente.
INPUT_DAILY_VALUES = {
    "lth": 500.0,
    "oee": 0.9,
    "ltp_lth": 1.1,
    "ltp_a_c": 1.5,
    "sl_solids": 140.0,
    "ssa_sf": 3.0,
    "ssa_sg": 1.5,
    "eoc_temp": 74.0,
    "eoc_solids": 250.0,
    "tanque": 12.0,
    "ltp_tc": 273.0,
}

INPUT_ANNUAL_VALUES = {
    "lth_base": 500.0,
    "oee_base": 0.9,
    "ltp_lth_base": 1.1,
    "ltp_a_c_base": 1.5,
    "sl_solids_base": 140.0,
    "ratio_spent_base": 0.5,
    "ssa_sf_base": 3.0,
    "ssa_sg_base": 1.5,
    "n_ppt_base": 10.0,
    "eoc_temp_base": 74.0,
    "eoc_solids_base": 250.0,
}

TANQUE_BASE_BY_LINE = {
    "L1": 14,
    "L2": 14,
    "L3": 16,
    "L4": 18,
    "L5": 18,
    "L6": 18,
    "L7": 18,
}


@pytest.fixture(scope="module")
def loaded_seed():
    loader = SeedLoader(SEED_ROOT)
    return loader.load_all_definitions_and_instances()


# ============================================================
# 1. Validators reais sobre o seed real
# ============================================================


def test_real_yield_seed_passes_all_structural_validators():
    variable_result = vsv.validate_seed(SEED_ROOT)
    assert variable_result["errors"] == []

    parameter_errors, _parameter_warnings = psv.validate_seed(
        SEED_ROOT
    )
    assert parameter_errors == []

    equation_errors, _equation_warnings = esv.validate_seed(
        SEED_ROOT
    )
    assert equation_errors == []


def test_real_yield_equations_pass_expression_syntax_validation():
    equations, loading_errors = esv.load_equations_from_seed(
        SEED_ROOT
    )
    assert loading_errors == []

    syntax_errors = esv.validate_expression_syntax(equations)
    assert syntax_errors == []


# ============================================================
# 2. SeedLoader real -> Definition/Instance Registries reais
# ============================================================


def test_seed_loader_builds_definition_and_instance_registries(
    loaded_seed,
):
    (
        variable_definitions,
        variable_instances,
        parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loaded_seed

    assert len(variable_definitions.all()) > 0
    assert len(parameter_definitions.all()) > 0
    assert len(equation_definitions.all()) > 0

    assert len(variable_instances.all()) > 0
    assert len(parameter_instances.all()) > 0
    assert len(equation_instances.all()) > 0


def test_tanque_is_a_single_variable_definition_materialized_by_line(
    loaded_seed,
):
    """
    Confirma que NÃO existem tanque_L1, tanque_L2, ... como
    definições conceituais distintas: há apenas UMA
    VariableDefinition "tanque", materializada em 7 instances.
    """

    variable_definitions, variable_instances, *_ = loaded_seed

    tanque_definitions = [
        d
        for d in variable_definitions.all()
        if d.variable_name == "tanque"
    ]

    assert len(tanque_definitions) == 1

    definition = tanque_definitions[0]

    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"

    tanque_instances = [
        i
        for i in variable_instances.all()
        if i.variable_definition_id
        == definition.variable_definition_id
    ]

    assert sorted(
        i.scope_value for i in tanque_instances
    ) == LINES

    # Nenhuma definição legada tanque_L1..tanque_L7 deve existir.
    legacy_names = {
        f"tanque_{line}" for line in LINES
    }

    assert not any(
        d.variable_name in legacy_names
        for d in variable_definitions.all()
    )


def test_tanque_base_is_one_id_materialized_with_distinct_values_per_line(
    loaded_seed,
):
    """
    tanque_base é uma única definição lógica (mesmo
    parameter_definition_id), com uma ParameterDefinition por linha
    e valores distintos, não 7 IDs conceituais diferentes.
    """

    _vd, _vi, parameter_definitions, parameter_instances, *_ = (
        loaded_seed
    )

    tanque_base_definitions = [
        d
        for d in parameter_definitions.all()
        if d.parameter_name == "tanque_base"
    ]

    assert len(tanque_base_definitions) == 7

    ids = {
        d.parameter_definition_id
        for d in tanque_base_definitions
    }

    assert len(ids) == 1, (
        "tanque_base deve compartilhar um único "
        "parameter_definition_id entre as 7 linhas"
    )

    tanque_base_id = ids.pop()

    values_by_line = {
        d.scope_value: d.value
        for d in tanque_base_definitions
    }

    assert values_by_line == TANQUE_BASE_BY_LINE

    tanque_base_instances = [
        i
        for i in parameter_instances.all()
        if i.parameter_definition_id == tanque_base_id
    ]

    assert len(tanque_base_instances) == 7

    for instance in tanque_base_instances:
        assert (
            instance.value
            == TANQUE_BASE_BY_LINE[instance.scope_value]
        )


def test_n_ppt_is_a_single_equation_definition_scoped_linha_l1_l7(
    loaded_seed,
):
    _vd, _vi, _pd, _pi, equation_definitions, equation_instances = (
        loaded_seed
    )

    n_ppt_definitions = [
        d
        for d in equation_definitions.all()
        if d.target_variable_id == "VAR11012"  # n_ppt (diário)
    ]

    assert len(n_ppt_definitions) == 1

    definition = n_ppt_definitions[0]

    assert definition.scope_type == "linha"
    assert definition.scope_value == "L1_L7"
    assert definition.expression == "PARAM11003 - VAR11239"
    assert definition.status == "PUBLISHED"

    n_ppt_instances = [
        i
        for i in equation_instances.all()
        if i.equation_definition_id
        == definition.equation_definition_id
    ]

    assert sorted(
        i.scope_value for i in n_ppt_instances
    ) == LINES


def test_official_ratio_spent_formula_uses_0_0007_coefficient(
    loaded_seed,
):
    _vd, _vi, _pd, _pi, equation_definitions, _ei = loaded_seed

    ratio_spent_daily = [
        d
        for d in equation_definitions.all()
        if d.target_variable_id == "VAR11008"  # ratio_spent (diário)
    ]

    assert len(ratio_spent_daily) == 1

    expression = ratio_spent_daily[0].expression

    assert "0.0007" in expression
    assert "0.001*" not in expression
    assert "+ 0.002*(VAR11090 - VAR11011)" in expression


def test_no_draft_equation_in_real_yield_seed(loaded_seed):
    _vd, _vi, _pd, _pi, equation_definitions, _ei = loaded_seed

    statuses = {
        d.status for d in equation_definitions.all()
    }

    assert "DRAFT" not in statuses


# ============================================================
# 3. Validação de integridade/escopo real (Parte A, item 5)
# ============================================================


def test_registry_validator_accepts_real_yield_definitions(
    loaded_seed,
):
    (
        variable_definitions,
        _vi,
        parameter_definitions,
        _pi,
        equation_definitions,
        _ei,
    ) = loaded_seed

    validator = RegistryIntegrityValidator()

    validator.validate_definition_registry(
        equation_definition_registry=equation_definitions,
        variable_definition_registry=variable_definitions,
        parameter_definition_registry=parameter_definitions,
    )


# ============================================================
# 4. Execução real ponta a ponta (ForecastEngine + EquationEngine)
# ============================================================


def _populate_context_with_inputs(context, variable_definitions):
    definitions_by_name_scope = {}

    for d in variable_definitions.all():
        definitions_by_name_scope.setdefault(d.variable_name, {})[
            (d.frequency, d.scope_type, d.scope_value)
        ] = d

    for name, value in INPUT_DAILY_VALUES.items():
        definition = definitions_by_name_scope[name][
            ("diário", "linha", "L1_L7")
        ]

        for line in LINES:
            context.set_variable_value(
                variable_id=definition.variable_definition_id,
                value=value,
                scope_type="linha",
                scope_value=line,
            )

    for name, value in INPUT_ANNUAL_VALUES.items():
        definition = definitions_by_name_scope[name][
            ("anual", "linha", "L1_L7")
        ]

        for line in LINES:
            context.set_variable_value(
                variable_id=definition.variable_definition_id,
                value=value,
                scope_type="linha",
                scope_value=line,
            )


def test_real_engine_executes_full_yield_seed_without_mocks(
    loaded_seed,
):
    (
        variable_definitions,
        _vi,
        _parameter_definitions,
        parameter_instances,
        equation_definitions,
        equation_instances,
    ) = loaded_seed

    context = CalculationContext()

    _populate_context_with_inputs(context, variable_definitions)

    for instance in parameter_instances.all():
        context.set_parameter_instance_value(
            instance,
            instance.value,
        )

    engine = ForecastEngine()

    results = engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definitions,
        calculation_context=context,
    )

    # Todas as 166 EquationInstances materializadas devem ter sido
    # calculadas (nenhuma DRAFT/ausente).
    assert len(results) == len(equation_instances.all())

    # n_ppt@Lx = tanque_base@Lx - tanque@Lx (tanque = 12.0 em todas
    # as linhas neste teste).
    expected_n_ppt = {
        line: TANQUE_BASE_BY_LINE[line] - 12.0
        for line in LINES
    }

    for line in LINES:
        assert context.get_variable_value(
            variable_id="VAR11012",
            scope_type="linha",
            scope_value=line,
        ) == expected_n_ppt[line]

    # yield@Lx deve ter sido calculado (depende de ratio_spent@Lx,
    # que por sua vez depende de n_ppt@Lx: comprova a ordenação de
    # dependências correta via referências contextuais/sem escopo).
    for line in LINES:
        yield_value = context.get_variable_value(
            variable_id="VAR11001",
            scope_type="linha",
            scope_value=line,
        )
        assert isinstance(yield_value, (int, float))

    # Agregação de linha_grupo (L1_L3) deve ter sido calculada a
    # partir dos valores já calculados por linha.
    yield_l1_l3 = context.get_variable_value(
        variable_id="VAR11016",
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    yield_l1 = context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L1",
    )
    yield_l2 = context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L2",
    )
    yield_l3 = context.get_variable_value(
        variable_id="VAR11001",
        scope_type="linha",
        scope_value="L3",
    )

    # ltp é igual nas 3 linhas neste teste (mesmos inputs lth/ltp_lth
    # em todas as linhas), logo a média ponderada por ltp equivale à
    # média aritmética simples.
    assert yield_l1_l3 == pytest.approx(
        (yield_l1 + yield_l2 + yield_l3) / 3
    )
