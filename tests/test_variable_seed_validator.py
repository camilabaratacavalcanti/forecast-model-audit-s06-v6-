import json

import pytest

from app.validation.variable_seed_validator import (
    validate_enum_values,
    validate_field_types,
    validate_non_empty_values,
    validate_scope_consistency,
    validate_scope_values,
    validate_seed,
    validate_variable_id_ranges,
    validate_variable_ids,
    validate_variable_signatures,
)


def make_variable(**overrides):
    """
    Cria uma variável válida para os testes.

    Cada teste pode sobrescrever apenas o campo
    que deseja tornar inválido.
    """
    variable = {
        "variable_id": "VAR11001",
        "variable_name": "test_variable",
        "description": "Test variable",
        "unit": "t",
        "variable_type": "entrada",
        "frequency": "mensal",
        "scope_type": "linha_grupo",
        "scope_value": "L1_L3",
        "source_reference": "TestSheet!A1",
        "status": "ativo",
        "_block": "yield",
    }

    variable.update(overrides)

    return variable


# ============================================================
# validate_field_types
# ============================================================


def test_validate_field_types_accepts_valid_variable():
    variable = make_variable()

    errors = validate_field_types([variable])

    assert errors == []


def test_validate_field_types_rejects_non_string_variable_name():
    variable = make_variable(
        variable_name=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "variable_name" in errors[0]
    assert "expected string" in errors[0]


def test_validate_field_types_rejects_non_string_description():
    variable = make_variable(
        description=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "description" in errors[0]


def test_validate_field_types_rejects_non_string_unit():
    variable = make_variable(
        unit=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "unit" in errors[0]


def test_validate_field_types_rejects_non_string_source_reference():
    variable = make_variable(
        source_reference=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "source_reference" in errors[0]


def test_validate_field_types_allows_null_scope():
    variable = make_variable(
        scope_type=None,
        scope_value=None,
    )

    errors = validate_field_types([variable])

    assert errors == []


def test_validate_field_types_rejects_non_string_scope_type():
    variable = make_variable(
        scope_type=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "scope_type" in errors[0]


def test_validate_field_types_rejects_non_string_scope_value():
    variable = make_variable(
        scope_value=123
    )

    errors = validate_field_types([variable])

    assert len(errors) == 1
    assert "scope_value" in errors[0]


# ============================================================
# validate_non_empty_values
# ============================================================


@pytest.mark.parametrize(
    "field",
    [
        "variable_id",
        "variable_name",
        "description",
        "unit",
        "source_reference",
    ],
)
def test_validate_non_empty_values_rejects_empty_string(
    field,
):
    variable = make_variable(
        **{field: ""}
    )

    errors = validate_non_empty_values([variable])

    assert len(errors) == 1
    assert field in errors[0]


@pytest.mark.parametrize(
    "field",
    [
        "variable_id",
        "variable_name",
        "description",
        "unit",
        "source_reference",
    ],
)
def test_validate_non_empty_values_rejects_whitespace(
    field,
):
    variable = make_variable(
        **{field: "   "}
    )

    errors = validate_non_empty_values([variable])

    assert len(errors) == 1
    assert field in errors[0]


# ============================================================
# validate_enum_values
# ============================================================


def test_validate_enum_values_accepts_valid_values():
    variable = make_variable()

    errors = validate_enum_values([variable])

    assert errors == []


def test_validate_enum_values_rejects_invalid_variable_type():
    variable = make_variable(
        variable_type="entrada_interna"
    )

    errors = validate_enum_values([variable])

    assert len(errors) == 1
    assert "variable_type" in errors[0]
    assert "entrada_interna" in errors[0]


def test_validate_enum_values_rejects_invalid_frequency():
    variable = make_variable(
        frequency="semanal"
    )

    errors = validate_enum_values([variable])

    assert len(errors) == 1
    assert "frequency" in errors[0]
    assert "semanal" in errors[0]


def test_validate_enum_values_rejects_invalid_scope_type():
    variable = make_variable(
        scope_type="equipamento"
    )

    errors = validate_enum_values([variable])

    assert len(errors) == 1
    assert "scope_type" in errors[0]
    assert "equipamento" in errors[0]


def test_validate_enum_values_rejects_invalid_status():
    variable = make_variable(
        status="DELETED"
    )

    errors = validate_enum_values([variable])

    assert len(errors) == 1
    assert "status" in errors[0]
    assert "DELETED" in errors[0]


def test_validate_enum_values_allows_null_scope_type():
    variable = make_variable(
        scope_type=None,
        scope_value=None,
    )

    errors = validate_enum_values([variable])

    assert errors == []


def test_validate_enum_values_accepts_valid_unit():
    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "t",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": None,
            "scope_value": None,
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert errors == []


def test_validate_enum_values_rejects_invalid_unit():
    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "ton",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": None,
            "scope_value": None,
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert len(errors) == 1
    assert "Invalid value 'ton'" in errors[0]
    assert "'unit'" in errors[0]


def test_validate_enum_values_accepts_valid_scope_value_line():
    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "t",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": "linha",
            "scope_value": "L1",
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert errors == []


def test_validate_enum_values_accepts_valid_scope_value_line_group():
    variables = [
        {
            "variable_id": "VAR11002",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "t",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": "linha_grupo",
            "scope_value": "L1_L3",
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert errors == []


def test_validate_enum_values_rejects_invalid_scope_value():
    variables = [
        {
            "variable_id": "VAR11003",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "t",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": "linha_grupo",
            "scope_value": "L1_3",
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert len(errors) == 1
    assert "Invalid value 'L1_3'" in errors[0]
    assert "'scope_value'" in errors[0]


def test_validate_enum_values_accepts_null_scope():
    variables = [
        {
            "variable_id": "VAR11004",
            "variable_name": "hydrate_production",
            "description": "Produção de Hidrato",
            "unit": "t",
            "variable_type": "calculado",
            "frequency": "mensal",
            "scope_type": None,
            "scope_value": None,
            "source_reference": "NovoOficial!D152:O152",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert errors == []


def test_validate_enum_values_accepts_external_input_variable_type():
    variable = make_variable(
        variable_type="entrada_externa"
    )

    errors = validate_enum_values([variable])

    assert errors == []


def test_validate_enum_values_accepts_valid_scope_value_all_lines():
    variable = make_variable(
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    errors = validate_enum_values([variable])

    assert errors == []


def test_validate_scope_values_accepts_all_lines_scope():
    variable = make_variable(
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    errors = validate_scope_values([variable])

    assert errors == []


def test_validate_enum_values_accepts_dimensionless_unit():
    variable = make_variable(
        unit="-"
    )

    errors = validate_enum_values([variable])

    assert errors == []


def test_validate_enum_values_accepts_specific_surface_area_unit():
    variable = make_variable(
        unit="m²/kg"
    )

    errors = validate_enum_values([variable])

    assert errors == []


# ============================================================
# validate_scope_consistency
# ============================================================


def test_validate_scope_consistency_allows_both_null():
    variable = make_variable(
        scope_type=None,
        scope_value=None,
    )

    errors = validate_scope_consistency([variable])

    assert errors == []


def test_validate_scope_consistency_allows_both_filled():
    variable = make_variable(
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    errors = validate_scope_consistency([variable])

    assert errors == []


def test_validate_scope_consistency_rejects_type_without_value():
    variable = make_variable(
        scope_type="linha_grupo",
        scope_value=None,
    )

    errors = validate_scope_consistency([variable])

    assert len(errors) == 1
    assert "scope_type and scope_value" in errors[0]


def test_validate_scope_consistency_rejects_value_without_type():
    variable = make_variable(
        scope_type=None,
        scope_value="L1_L3",
    )

    errors = validate_scope_consistency([variable])

    assert len(errors) == 1
    assert "scope_type and scope_value" in errors[0]


# ============================================================
# validate_scope_values
# ============================================================


def test_validate_scope_values_accepts_valid_scope():
    variable = make_variable()

    errors = validate_scope_values([variable])

    assert errors == []


def test_validate_scope_values_rejects_empty_scope_type():
    variable = make_variable(
        scope_type=""
    )

    errors = validate_scope_values([variable])

    assert len(errors) == 1
    assert "scope_type" in errors[0]


def test_validate_scope_values_rejects_whitespace_scope_type():
    variable = make_variable(
        scope_type="   "
    )

    errors = validate_scope_values([variable])

    assert len(errors) == 1
    assert "scope_type" in errors[0]


def test_validate_scope_values_rejects_empty_scope_value():
    variable = make_variable(
        scope_value=""
    )

    errors = validate_scope_values([variable])

    assert len(errors) == 1
    assert "scope_value" in errors[0]


def test_validate_scope_values_rejects_whitespace_scope_value():
    variable = make_variable(
        scope_value="   "
    )

    errors = validate_scope_values([variable])

    assert len(errors) == 1
    assert "scope_value" in errors[0]


# ============================================================
# validate_variable_id_ranges
# ============================================================


def test_validate_variable_id_ranges_accepts_valid_yield_id():
    variable = make_variable(
        variable_id="VAR11001"
    )

    errors = validate_variable_id_ranges([variable])

    assert errors == []


def test_validate_variable_id_ranges_rejects_wrong_yield_range():
    variable = make_variable(
        variable_id="VAR12001"
    )

    errors = validate_variable_id_ranges([variable])

    assert len(errors) == 1
    assert "out of range" in errors[0]


def test_validate_variable_id_ranges_rejects_invalid_prefix():
    variable = make_variable(
        variable_id="ABC11001"
    )

    errors = validate_variable_id_ranges([variable])

    assert len(errors) == 1
    assert "VAR followed by digits" in errors[0]


def test_validate_variable_id_ranges_rejects_non_numeric_suffix():
    variable = make_variable(
        variable_id="VAR11ABC"
    )

    errors = validate_variable_id_ranges([variable])

    assert len(errors) == 1
    assert "VAR followed by digits" in errors[0]


# ============================================================
# validate_variable_ids
# ============================================================


def test_validate_variable_ids_accepts_unique_ids():
    variables = [
        make_variable(variable_id="VAR11001"),
        make_variable(variable_id="VAR11002"),
    ]

    errors = validate_variable_ids(variables)

    assert errors == []


def test_validate_variable_ids_rejects_duplicate_ids():
    variables = [
        make_variable(variable_id="VAR11001"),
        make_variable(variable_id="VAR11001"),
    ]

    errors = validate_variable_ids(variables)

    assert len(errors) == 1
    assert "Duplicate variable_id" in errors[0]
    assert "VAR11001" in errors[0]


# ============================================================
# validate_variable_signatures
# ============================================================


def test_validate_variable_signatures_accepts_different_variables():
    variables = [
        make_variable(
            variable_id="VAR11001",
            variable_name="yield_a",
        ),
        make_variable(
            variable_id="VAR11002",
            variable_name="yield_b",
        ),
    ]

    warnings = validate_variable_signatures(variables)

    assert warnings == []


def test_validate_variable_signatures_warns_possible_duplicate():
    variables = [
        make_variable(
            variable_id="VAR11001",
        ),
        make_variable(
            variable_id="VAR11002",
        ),
    ]

    warnings = validate_variable_signatures(variables)

    assert len(warnings) == 1
    assert "Possible duplicate variable" in warnings[0]


# ============================================================
# validate_seed
# ============================================================


def test_validate_seed_accepts_valid_seed(tmp_path):
    seed_path = tmp_path / "seed"
    yield_path = seed_path / "yield"

    yield_path.mkdir(parents=True)

    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "yield_test",
            "description": "Test yield",
            "unit": "%",
            "variable_type": "entrada",
            "frequency": "mensal",
            "scope_type": "linha_grupo",
            "scope_value": "L1_L3",
            "source_reference": "Yield!A1",
            "status": "ativo",
        }
    ]

    variables_file = yield_path / "variables.json"

    variables_file.write_text(
        json.dumps(variables),
        encoding="utf-8",
    )

    result = validate_seed(seed_path)

    assert result["is_valid"] is True
    assert result["errors"] == []


def test_validate_seed_rejects_invalid_enum(tmp_path):
    seed_path = tmp_path / "seed"
    yield_path = seed_path / "yield"

    yield_path.mkdir(parents=True)

    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "yield_test",
            "description": "Test yield",
            "unit": "%",
            "variable_type": "wrong_type",
            "frequency": "mensal",
            "scope_type": "linha_grupo",
            "scope_value": "L1_L3",
            "source_reference": "Yield!A1",
            "status": "ativo",
        }
    ]

    variables_file = yield_path / "variables.json"

    variables_file.write_text(
        json.dumps(variables),
        encoding="utf-8",
    )

    result = validate_seed(seed_path)

    assert result["is_valid"] is False
    assert any(
        "variable_type" in error
        for error in result["errors"]
    )


def test_validate_seed_rejects_empty_required_value(tmp_path):
    seed_path = tmp_path / "seed"
    yield_path = seed_path / "yield"

    yield_path.mkdir(parents=True)

    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "",
            "description": "Test yield",
            "unit": "%",
            "variable_type": "entrada",
            "frequency": "mensal",
            "scope_type": "linha_grupo",
            "scope_value": "L1_L3",
            "source_reference": "Yield!A1",
            "status": "ativo",
        }
    ]

    variables_file = yield_path / "variables.json"

    variables_file.write_text(
        json.dumps(variables),
        encoding="utf-8",
    )

    result = validate_seed(seed_path)

    assert result["is_valid"] is False
    assert any(
        "variable_name" in error
        for error in result["errors"]
    )


def test_validate_seed_rejects_nonexistent_path(
    tmp_path,
):
    seed_path = tmp_path / "does_not_exist"

    result = validate_seed(seed_path)

    assert result["is_valid"] is False
    assert len(result["errors"]) == 1
    assert "does not exist" in result["errors"][0]


# ============================================================
# VARIABLE_ID_RANGES -- contrato da taxonomia oficial de blocos
# ============================================================
#
# Protege a taxonomia oficial de 29 blocos (10000-38999), sem
# depender de nenhuma seed real: valida a estrutura do proprio
# catalogo. "hydrate" e "costs" nao existem mais como blocos de
# ID; "max_ht" ocupa a faixa antes usada por "hydrate";
# "budget_vs_forecast" ocupa 37000-37999; "shared" foi realocado
# para 38000-38999.


from app.validation.variable_seed_validator import (
    VARIABLE_ID_RANGES,
)


def test_variable_id_ranges_has_exactly_29_blocks():
    assert len(VARIABLE_ID_RANGES) == 29


def test_variable_id_ranges_matches_official_taxonomy():
    assert VARIABLE_ID_RANGES == {
        "maintenance": (10000, 10999),
        "yield": (11000, 11999),
        "production": (12000, 12999),
        "max_ht": (13000, 13999),
        "alumina": (14000, 14999),
        "temperature_lp": (15000, 15999),
        "area_41": (16000, 16999),
        "area_04_13": (17000, 17999),
        "energy": (18000, 18999),
        "boilers": (19000, 19999),
        "volume": (20000, 20999),
        "soda": (21000, 21999),
        "residue_factor": (22000, 22999),
        "condensate_flow": (23000, 23999),
        "forecast_volume": (24000, 24999),
        "full_volume_target": (25000, 25999),
        "empty_space_target_control": (26000, 26999),
        "lime": (27000, 27999),
        "hydrated_flocculant": (28000, 28999),
        "sludge_flocculant": (29000, 29999),
        "monthly_ppt_assumptions": (30000, 30999),
        "acid": (31000, 31999),
        "budget_cost": (32000, 32999),
        "budget_forecast_cost": (33000, 33999),
        "actual_forecast_cost": (34000, 34999),
        "budget": (35000, 35999),
        "forecast": (36000, 36999),
        "budget_vs_forecast": (37000, 37999),
        "shared": (38000, 38999),
    }


def test_variable_id_ranges_hydrate_and_costs_no_longer_exist():
    assert "hydrate" not in VARIABLE_ID_RANGES
    assert "costs" not in VARIABLE_ID_RANGES


def test_variable_id_ranges_max_ht_occupies_former_hydrate_range():
    assert VARIABLE_ID_RANGES["max_ht"] == (13000, 13999)


def test_variable_id_ranges_budget_vs_forecast_occupies_former_shared_range():
    assert VARIABLE_ID_RANGES["budget_vs_forecast"] == (37000, 37999)


def test_variable_id_ranges_shared_is_the_last_block():
    names = list(VARIABLE_ID_RANGES)
    assert names[-1] == "shared"
    assert VARIABLE_ID_RANGES["shared"] == (38000, 38999)


def test_variable_id_ranges_first_block_starts_at_10000():
    first_name = next(iter(VARIABLE_ID_RANGES))
    assert VARIABLE_ID_RANGES[first_name][0] == 10000


def test_variable_id_ranges_last_block_ends_at_38999():
    last_name = list(VARIABLE_ID_RANGES)[-1]
    assert VARIABLE_ID_RANGES[last_name][1] == 38999


def test_variable_id_ranges_every_block_has_exactly_1000_ids():
    for name, (minimum, maximum) in VARIABLE_ID_RANGES.items():
        assert maximum - minimum + 1 == 1000, name


def test_variable_id_ranges_no_overlap_between_any_two_blocks():
    intervals = sorted(VARIABLE_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min > previous_max


def test_variable_id_ranges_are_contiguous_with_no_gaps():
    intervals = sorted(VARIABLE_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min == previous_max + 1


def test_variable_id_ranges_names_have_no_duplicates():
    names = list(VARIABLE_ID_RANGES)
    assert len(names) == len(set(names))


# ============================================================
# Padronizacao de unidades de taxa de massa (t/h, t/d, t/mes)
# ============================================================


@pytest.mark.parametrize("unit", ["t/h", "t/d", "t/mês"])
def test_validate_enum_values_accepts_mass_rate_units(unit):
    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "producao_taxa",
            "description": "Taxa de producao de teste.",
            "unit": unit,
            "variable_type": "calculado",
            "frequency": "diário",
            "scope_type": "linha",
            "scope_value": "L1_L7",
            "source_reference": "teste",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert errors == []


@pytest.mark.parametrize(
    "unit",
    [
        "ton/h",
        "ton/d",
        "ton/dia",
        "ton/mês",
        "ton/month",
        "t/hour",
        "t/day",
        "t/month",
        "t/m",
    ],
)
def test_validate_enum_values_rejects_non_standard_mass_rate_variants(
    unit,
):
    variables = [
        {
            "variable_id": "VAR11001",
            "variable_name": "producao_taxa",
            "description": "Taxa de producao de teste.",
            "unit": unit,
            "variable_type": "calculado",
            "frequency": "diário",
            "scope_type": "linha",
            "scope_value": "L1_L7",
            "source_reference": "teste",
            "status": "ativo",
        }
    ]

    errors = validate_enum_values(variables)

    assert len(errors) == 1
    assert "'unit'" in errors[0]
