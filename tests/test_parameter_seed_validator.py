import json

import pytest

from pathlib import Path

from app.validation.parameter_seed_validator import (
    PARAMETER_ID_RANGES,
    build_parameter_signature,
    validate_enum_values,
    validate_field_types,
    validate_non_empty_values,
    validate_parameter_id_ranges,
    validate_parameter_ids,
    validate_parameter_signatures,
    validate_required_fields,
    validate_scope_consistency,
    validate_scope_values,
    validate_seed,
    validate_seed_path,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def valid_parameter():
    return {
        "parameter_id": "PARAM12001",
        "parameter_name": "minimum_operating_rate",
        "description": "Taxa mínima de operação",
        "unit": "%",
        "value": 85.0,
        "scope_type": "linha_grupo",
        "scope_value": "L1_L3",
        "source_reference": "NovoOficial!D180:O180",
        "status": "ativo",
    }


@pytest.fixture
def production_seed_path(tmp_path):
    seed_path = tmp_path / "data" / "seed" / "production"
    seed_path.mkdir(parents=True)

    return seed_path


# ============================================================
# REQUIRED FIELDS
# ============================================================

def test_validate_required_fields_accepts_valid_parameter(
    valid_parameter,
    tmp_path,
):
    errors = validate_required_fields(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


def test_validate_required_fields_detects_missing_field(
    valid_parameter,
    tmp_path,
):
    del valid_parameter["parameter_name"]

    errors = validate_required_fields(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert len(errors) == 1
    assert "parameter_name" in errors[0]


# ============================================================
# FIELD TYPES
# ============================================================

def test_validate_field_types_accepts_valid_parameter(
    valid_parameter,
    tmp_path,
):
    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("parameter_id", 12001),
        ("parameter_name", 123),
        ("description", 123),
        ("unit", 123),
        ("source_reference", 123),
        ("status", 123),
    ],
)
def test_validate_field_types_rejects_invalid_string_fields(
    valid_parameter,
    tmp_path,
    field,
    invalid_value,
):
    valid_parameter[field] = invalid_value

    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any(field in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "scope_type",
        "scope_value",
    ],
)
def test_validate_field_types_accepts_null_optional_scope_fields(
    valid_parameter,
    tmp_path,
    field,
):
    valid_parameter[field] = None

    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("scope_type", 123),
        ("scope_value", 123),
    ],
)
def test_validate_field_types_rejects_invalid_optional_scope_fields(
    valid_parameter,
    tmp_path,
    field,
    invalid_value,
):
    valid_parameter[field] = invalid_value

    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any(field in error for error in errors)


# ============================================================
# VALUE TYPE
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        100,
        -10,
        85.0,
        0.5,
        -1.25,
    ],
)
def test_validate_field_types_accepts_numeric_values(
    valid_parameter,
    tmp_path,
    value,
):
    valid_parameter["value"] = value

    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "85",
        "0.85",
        None,
        [],
        {},
    ],
)
def test_validate_field_types_rejects_non_numeric_values(
    valid_parameter,
    tmp_path,
    value,
):
    valid_parameter["value"] = value

    errors = validate_field_types(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any("value" in error for error in errors)


# ============================================================
# NON-EMPTY VALUES
# ============================================================

@pytest.mark.parametrize(
    "field",
    [
        "parameter_id",
        "parameter_name",
        "description",
        "unit",
        "source_reference",
    ],
)
def test_validate_non_empty_values_rejects_empty_strings(
    valid_parameter,
    tmp_path,
    field,
):
    valid_parameter[field] = ""

    errors = validate_non_empty_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any(field in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "parameter_id",
        "parameter_name",
        "description",
        "unit",
        "source_reference",
    ],
)
def test_validate_non_empty_values_rejects_whitespace_only_strings(
    valid_parameter,
    tmp_path,
    field,
):
    valid_parameter[field] = "   "

    errors = validate_non_empty_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any(field in error for error in errors)


def test_validate_non_empty_values_accepts_zero_as_value(
    valid_parameter,
    tmp_path,
):
    valid_parameter["value"] = 0

    errors = validate_non_empty_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


# ============================================================
# ENUM VALUES
# ============================================================

def test_validate_enum_values_accepts_valid_parameter(
    valid_parameter,
    tmp_path,
):
    errors = validate_enum_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("status", "invalid"),
        ("unit", "invalid_unit"),
        ("scope_type", "invalid_scope"),
        ("scope_value", "invalid_scope_value"),
    ],
)
def test_validate_enum_values_rejects_invalid_values(
    valid_parameter,
    tmp_path,
    field,
    invalid_value,
):
    valid_parameter[field] = invalid_value

    errors = validate_enum_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert any(field in error for error in errors)


def test_validate_enum_values_accepts_null_scope_fields(
    valid_parameter,
    tmp_path,
):
    valid_parameter["scope_type"] = None
    valid_parameter["scope_value"] = None

    errors = validate_enum_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


# ============================================================
# SCOPE CONSISTENCY
# ============================================================

def test_validate_scope_consistency_accepts_both_values(
    valid_parameter,
    tmp_path,
):
    errors = validate_scope_consistency(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


def test_validate_scope_consistency_accepts_both_null(
    valid_parameter,
    tmp_path,
):
    valid_parameter["scope_type"] = None
    valid_parameter["scope_value"] = None

    errors = validate_scope_consistency(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "scope_type,scope_value",
    [
        ("linha", None),
        (None, "L1"),
        ("linha_grupo", None),
        (None, "L1_L3"),
    ],
)
def test_validate_scope_consistency_rejects_partial_scope(
    valid_parameter,
    tmp_path,
    scope_type,
    scope_value,
):
    valid_parameter["scope_type"] = scope_type
    valid_parameter["scope_value"] = scope_value

    errors = validate_scope_consistency(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert len(errors) == 1
    assert "scope_type" in errors[0]
    assert "scope_value" in errors[0]


# ============================================================
# SCOPE VALUES
# ============================================================

@pytest.mark.parametrize(
    "scope_value",
    [
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
        "L1_L7",
    ],
)
def test_validate_scope_values_accepts_line_values(
    valid_parameter,
    tmp_path,
    scope_value,
):
    valid_parameter["scope_type"] = "linha"
    valid_parameter["scope_value"] = scope_value

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "scope_value",
    [
        "L1_L3",
        "L4_L5",
        "L6_L7",
        "L1_L7",
    ],
)
def test_validate_scope_values_accepts_line_group_values(
    valid_parameter,
    tmp_path,
    scope_value,
):
    valid_parameter["scope_type"] = "linha_grupo"
    valid_parameter["scope_value"] = scope_value

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


@pytest.mark.parametrize(
    "scope_type",
    [
        "área",
        "global",
    ],
)
def test_validate_scope_values_accepts_null_value_for_non_line_scope(
    valid_parameter,
    tmp_path,
    scope_type,
):
    valid_parameter["scope_type"] = scope_type
    valid_parameter["scope_value"] = None

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


def test_validate_scope_values_rejects_null_value_for_planta_scope(
    valid_parameter,
    tmp_path,
):
    """
    Contrato de `planta` (corrigido): diferente de "área"/"global",
    `scope_value=None` NÃO é mais aceito -- o contrato canônico
    exige "PLANTA" explicitamente, consistente com
    `ScopeResolver.PLANT_SCOPE`.
    """

    valid_parameter["scope_type"] = "planta"
    valid_parameter["scope_value"] = None

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors != []


def test_validate_scope_values_accepts_planta_with_planta_value(
    valid_parameter,
    tmp_path,
):
    valid_parameter["scope_type"] = "planta"
    valid_parameter["scope_value"] = "PLANTA"

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert errors == []


def test_validate_scope_values_rejects_invalid_line_value(
    valid_parameter,
    tmp_path,
):
    valid_parameter["scope_type"] = "linha"
    valid_parameter["scope_value"] = "L1_L3"

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert len(errors) == 1
    assert "linha" in errors[0]


def test_validate_scope_values_rejects_invalid_line_group_value(
    valid_parameter,
    tmp_path,
):
    valid_parameter["scope_type"] = "linha_grupo"
    valid_parameter["scope_value"] = "L1"

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert len(errors) == 1
    assert "linha_grupo" in errors[0]


@pytest.mark.parametrize(
    "scope_type",
    [
        "área",
        "planta",
        "global",
    ],
)
def test_validate_scope_values_rejects_line_value_for_non_line_scope(
    valid_parameter,
    tmp_path,
    scope_type,
):
    valid_parameter["scope_type"] = scope_type
    valid_parameter["scope_value"] = "L1"

    errors = validate_scope_values(
        valid_parameter,
        tmp_path / "parameters.json",
    )

    assert len(errors) == 1


def test_validate_scope_values_accepts_l1_l7_for_linha(
    valid_parameter,
):
    parameter = valid_parameter.copy()

    parameter["scope_type"] = "linha"
    parameter["scope_value"] = "L1_L7"

    errors = validate_scope_values(
        parameter,
        Path("data/seed/yield/parameters.json"),
    )

    assert errors == []


# ============================================================
# SEED PATH
# ============================================================

@pytest.mark.parametrize(
    "block",
    [
        "maintenance",
        "yield",
        "production",
        "shared",
    ],
)
def test_validate_seed_path_accepts_valid_blocks(
    tmp_path,
    block,
):
    file_path = (
        tmp_path
        / "data"
        / "seed"
        / block
        / "parameters.json"
    )

    errors = validate_seed_path(file_path)

    assert errors == []


def test_validate_seed_path_rejects_unknown_block(tmp_path):
    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "unknown"
        / "parameters.json"
    )

    errors = validate_seed_path(file_path)

    assert len(errors) == 1


# ============================================================
# PARAMETER ID FORMAT AND RANGE
# ============================================================

@pytest.mark.parametrize(
    "parameter_id",
    [
        "PARAM10000",
        "PARAM10500",
        "PARAM10999",
    ],
)
def test_validate_parameter_id_ranges_accepts_maintenance_ids(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "maintenance"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert errors == []


@pytest.mark.parametrize(
    "parameter_id",
    [
        "PARAM11000",
        "PARAM11500",
        "PARAM11999",
    ],
)
def test_validate_parameter_id_ranges_accepts_yield_ids(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "yield"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert errors == []


@pytest.mark.parametrize(
    "parameter_id",
    [
        "PARAM12000",
        "PARAM12500",
        "PARAM12999",
    ],
)
def test_validate_parameter_id_ranges_accepts_production_ids(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "production"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert errors == []


@pytest.mark.parametrize(
    "parameter_id",
    [
        "PARAM37000",
        "PARAM37500",
        "PARAM37999",
    ],
)
def test_validate_parameter_id_ranges_accepts_shared_ids(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "shared"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert errors == []


@pytest.mark.parametrize(
    "parameter_id",
    [
        "PARAM09999",
        "PARAM11000",
        "PARAM11999",
        "PARAM13000",
        "PARAM20000",
    ],
)
def test_validate_parameter_id_ranges_rejects_id_outside_block(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "production"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert len(errors) == 1
    assert "fora da faixa" in errors[0]


@pytest.mark.parametrize(
    "parameter_id",
    [
        "12001",
        "PAR12001",
        "PARAMABC",
        "PARAM12A01",
        "",
    ],
)
def test_validate_parameter_id_ranges_rejects_invalid_id_format(
    valid_parameter,
    tmp_path,
    parameter_id,
):
    valid_parameter["parameter_id"] = parameter_id

    file_path = (
        tmp_path
        / "data"
        / "seed"
        / "production"
        / "parameters.json"
    )

    errors = validate_parameter_id_ranges(
        valid_parameter,
        file_path,
    )

    assert len(errors) == 1


# ============================================================
# PARAMETER IDS DUPLICADOS
# ============================================================

def test_validate_parameter_ids_accepts_unique_ids(
    valid_parameter,
    tmp_path,
):
    parameter_2 = valid_parameter.copy()
    parameter_2["parameter_id"] = "PARAM12002"

    parameters = [
        (
            valid_parameter,
            tmp_path / "production" / "parameters.json",
        ),
        (
            parameter_2,
            tmp_path / "production" / "parameters.json",
        ),
    ]

    errors = validate_parameter_ids(parameters)

    assert errors == []


def test_validate_parameter_ids_detects_duplicate_ids(
    valid_parameter,
    tmp_path,
):
    parameter_2 = valid_parameter.copy()

    parameters = [
        (
            valid_parameter,
            tmp_path / "production" / "parameters.json",
        ),
        (
            parameter_2,
            tmp_path / "production" / "parameters.json",
        ),
    ]

    errors = validate_parameter_ids(parameters)

    assert len(errors) == 1
    assert "duplicado" in errors[0]
    assert "PARAM12001" in errors[0]


# ============================================================
# PARAMETER SIGNATURE
# ============================================================

def test_build_parameter_signature(
    valid_parameter,
):
    signature = build_parameter_signature(valid_parameter)

    assert signature == (
        "minimum_operating_rate",
        "%",
        "linha_grupo",
        "L1_L3",
    )


def test_parameter_signature_ignores_value(
    valid_parameter,
):
    parameter_2 = valid_parameter.copy()

    parameter_2["value"] = 90.0

    signature_1 = build_parameter_signature(valid_parameter)
    signature_2 = build_parameter_signature(parameter_2)

    assert signature_1 == signature_2


def test_validate_parameter_signatures_accepts_different_parameters(
    valid_parameter,
    tmp_path,
):
    parameter_2 = valid_parameter.copy()

    parameter_2["parameter_id"] = "PARAM12002"
    parameter_2["parameter_name"] = "maximum_operating_rate"

    parameters = [
        (
            valid_parameter,
            tmp_path / "production" / "parameters.json",
        ),
        (
            parameter_2,
            tmp_path / "production" / "parameters.json",
        ),
    ]

    warnings = validate_parameter_signatures(parameters)

    assert warnings == []


def test_validate_parameter_signatures_detects_semantic_duplicate(
    valid_parameter,
    tmp_path,
):
    parameter_2 = valid_parameter.copy()

    parameter_2["parameter_id"] = "PARAM12002"
    parameter_2["value"] = 90.0

    parameters = [
        (
            valid_parameter,
            tmp_path / "production" / "parameters.json",
        ),
        (
            parameter_2,
            tmp_path / "production" / "parameters.json",
        ),
    ]

    warnings = validate_parameter_signatures(parameters)

    assert len(warnings) == 1
    assert "semanticamente duplicado" in warnings[0]


# ============================================================
# JSON STRUCTURE / COMPLETE SEED
# ============================================================

def test_validate_seed_accepts_valid_seed(
    production_seed_path,
    valid_parameter,
):
    file_path = production_seed_path / "parameters.json"

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [valid_parameter],
            file,
            ensure_ascii=False,
            indent=2,
        )

    errors, warnings = validate_seed(
        production_seed_path.parent.parent.parent
    )

    assert errors == []
    assert warnings == []


def test_validate_seed_rejects_invalid_parameter(
    production_seed_path,
    valid_parameter,
):
    valid_parameter["value"] = True

    file_path = production_seed_path / "parameters.json"

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [valid_parameter],
            file,
            ensure_ascii=False,
            indent=2,
        )

    errors, warnings = validate_seed(
        production_seed_path.parent.parent.parent
    )

    assert len(errors) >= 1
    assert any("value" in error for error in errors)


def test_validate_seed_detects_duplicate_parameter_ids(
    production_seed_path,
    valid_parameter,
):
    parameter_2 = valid_parameter.copy()

    parameter_2["parameter_name"] = "another_parameter"

    file_path = production_seed_path / "parameters.json"

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [
                valid_parameter,
                parameter_2,
            ],
            file,
            ensure_ascii=False,
            indent=2,
        )

    errors, warnings = validate_seed(
        production_seed_path.parent.parent.parent
    )

    assert any("duplicado" in error for error in errors)


def test_validate_seed_warns_about_semantic_duplicates(
    production_seed_path,
    valid_parameter,
):
    parameter_2 = valid_parameter.copy()

    parameter_2["parameter_id"] = "PARAM12002"
    parameter_2["value"] = 90.0

    file_path = production_seed_path / "parameters.json"

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [
                valid_parameter,
                parameter_2,
            ],
            file,
            ensure_ascii=False,
            indent=2,
        )

    errors, warnings = validate_seed(
        production_seed_path.parent.parent.parent
    )

    assert errors == []
    assert len(warnings) == 1
    assert "semanticamente duplicado" in warnings[0]


def test_validate_seed_rejects_parameter_outside_block(
    production_seed_path,
    valid_parameter,
):
    valid_parameter["parameter_id"] = "PARAM11001"

    file_path = production_seed_path / "parameters.json"

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [valid_parameter],
            file,
            ensure_ascii=False,
            indent=2,
        )

    errors, warnings = validate_seed(
        production_seed_path.parent.parent.parent
    )

    assert any("fora da faixa" in error for error in errors)


def test_validate_seed_warns_when_no_parameter_files(
    tmp_path,
):
    seed_root = tmp_path / "data" / "seed"
    seed_root.mkdir(parents=True)

    errors, warnings = validate_seed(seed_root)

    assert errors == []
    assert len(warnings) == 1
    assert "parameters.json" in warnings[0]


# ============================================================
# PARAMETER_ID_RANGES -- contrato da taxonomia oficial de blocos
# ============================================================
#
# Protege a taxonomia oficial de 28 blocos (10000-37999), sem
# depender de nenhuma seed real: valida a estrutura do proprio
# catalogo. Identica, bloco a bloco, a VARIABLE_ID_RANGES.
# "hydrate" e "costs" nao existem mais como blocos de ID;
# "max_ht" ocupa a faixa antes usada por "hydrate"; "shared"
# foi realocado para 37000-37999.


def test_parameter_id_ranges_has_exactly_28_blocks():
    assert len(PARAMETER_ID_RANGES) == 28


def test_parameter_id_ranges_matches_official_taxonomy():
    assert PARAMETER_ID_RANGES == {
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
        "fator_residuo": (22000, 22999),
        "vazao_condensado": (23000, 23999),
        "forecast_volume": (24000, 24999),
        "meta_volume_cheio": (25000, 25999),
        "controle_espaco_vazio_meta": (26000, 26999),
        "lime_dia": (27000, 27999),
        "floculante_hidrato_2026": (28000, 28999),
        "floculante_lama_dia": (29000, 29999),
        "premissas_ppt_mensal": (30000, 30999),
        "acido": (31000, 31999),
        "custo_budget": (32000, 32999),
        "custo_forecast_bdgt": (33000, 33999),
        "custo_forecast_real": (34000, 34999),
        "budget": (35000, 35999),
        "forecast": (36000, 36999),
        "shared": (37000, 37999),
    }


def test_parameter_id_ranges_hydrate_and_costs_no_longer_exist():
    assert "hydrate" not in PARAMETER_ID_RANGES
    assert "costs" not in PARAMETER_ID_RANGES


def test_parameter_id_ranges_max_ht_occupies_former_hydrate_range():
    assert PARAMETER_ID_RANGES["max_ht"] == (13000, 13999)


def test_parameter_id_ranges_shared_is_the_last_block():
    names = list(PARAMETER_ID_RANGES)
    assert names[-1] == "shared"
    assert PARAMETER_ID_RANGES["shared"] == (37000, 37999)


def test_parameter_id_ranges_first_block_starts_at_10000():
    first_name = next(iter(PARAMETER_ID_RANGES))
    assert PARAMETER_ID_RANGES[first_name][0] == 10000


def test_parameter_id_ranges_last_block_ends_at_37999():
    last_name = list(PARAMETER_ID_RANGES)[-1]
    assert PARAMETER_ID_RANGES[last_name][1] == 37999


def test_parameter_id_ranges_every_block_has_exactly_1000_ids():
    for name, (minimum, maximum) in PARAMETER_ID_RANGES.items():
        assert maximum - minimum + 1 == 1000, name


def test_parameter_id_ranges_no_overlap_between_any_two_blocks():
    intervals = sorted(PARAMETER_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min > previous_max


def test_parameter_id_ranges_are_contiguous_with_no_gaps():
    intervals = sorted(PARAMETER_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min == previous_max + 1


def test_parameter_id_ranges_names_have_no_duplicates():
    names = list(PARAMETER_ID_RANGES)
    assert len(names) == len(set(names))
