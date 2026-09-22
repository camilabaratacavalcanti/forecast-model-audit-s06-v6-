import json
from pathlib import Path

import pytest

from app.validation.equation_seed_validator import (
    ALLOWED_SCOPE_TYPES,
    ALLOWED_SCOPE_VALUES,
    ALLOWED_STATUSES,
    EQUATION_ID_RANGES,
    REQUIRED_EQUATION_FIELDS,
    build_equation_signature,
    find_equation_files,
    load_equations_from_seed,
    validate_equation_id_ranges,
    validate_equation_ids,
    validate_equation_signatures,
    validate_enum_values,
    validate_field_types,
    validate_json_structure,
    validate_non_empty_values,
    validate_required_fields,
    validate_scope_consistency,
    validate_seed,
    validate_seed_path,
    validate_versions,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def equation_base():
    """
    Retorna uma equação estruturalmente válida.
    """
    return {
        "equation_id": "EQ12001",
        "target_variable_id": "VAR12001",
        "version": 1,
        "scope_type": "global",
        "scope_value": None,
        "expression": "production * yield",
        "source_reference": "NovoOficial!D152:O152",
        "status": "DRAFT",
    }


@pytest.fixture
def seed_root(tmp_path):
    """
    Cria uma estrutura mínima de seed para os testes.
    """
    seed_root = tmp_path / "data" / "seed"
    seed_root.mkdir(parents=True)

    return seed_root


def write_equations(seed_root, equations, block="production"):
    """
    Escreve um equations.json dentro da estrutura de seed.
    """
    block_dir = seed_root / block
    block_dir.mkdir(parents=True, exist_ok=True)

    file_path = block_dir / "equations.json"

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(
            equations,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return file_path


# ============================================================
# REQUIRED FIELDS
# ============================================================

def test_required_equation_fields():
    """
    Verifica se os campos obrigatórios do Equation Registry
    estão definidos corretamente.
    """
    assert REQUIRED_EQUATION_FIELDS == [
        "equation_id",
        "target_variable_id",
        "version",
        "scope_type",
        "scope_value",
        "expression",
        "source_reference",
        "status",
    ]


def test_validate_required_fields_accepts_valid_equation(
    equation_base,
):
    errors = validate_required_fields(
        [equation_base]
    )

    assert errors == []


def test_validate_required_fields_rejects_missing_field(
    equation_base,
):
    del equation_base["expression"]

    errors = validate_required_fields(
        [equation_base]
    )

    assert len(errors) == 1
    assert "expression" in errors[0]


def test_scope_value_key_is_required_even_when_none(
    equation_base,
):
    del equation_base["scope_value"]

    errors = validate_required_fields(
        [equation_base]
    )

    assert len(errors) == 1
    assert "scope_value" in errors[0]


# ============================================================
# JSON STRUCTURE
# ============================================================

def test_validate_json_structure_accepts_list(
    equation_base,
):
    errors = validate_json_structure(
        [equation_base],
        Path("equations.json"),
    )

    assert errors == []


def test_validate_json_structure_rejects_non_list():
    errors = validate_json_structure(
        {},
        Path("equations.json"),
    )

    assert len(errors) == 1
    assert "lista JSON" in errors[0]


def test_validate_json_structure_rejects_non_dict_item():
    errors = validate_json_structure(
        ["invalid"],
        Path("equations.json"),
    )

    assert len(errors) == 1
    assert "objeto JSON" in errors[0]


# ============================================================
# SEED PATH
# ============================================================

def test_validate_seed_path_accepts_valid_path():
    path = Path(
        "data",
        "seed",
        "production",
        "equations.json",
    )

    errors = validate_seed_path(path)

    assert errors == []


def test_validate_seed_path_rejects_wrong_filename():
    path = Path(
        "data",
        "seed",
        "production",
        "variables.json",
    )

    errors = validate_seed_path(path)

    assert len(errors) == 1
    assert "equations.json" in errors[0]


def test_validate_seed_path_rejects_path_without_seed():
    path = Path(
        "data",
        "production",
        "equations.json",
    )

    errors = validate_seed_path(path)

    assert len(errors) == 1
    assert "data/seed" in errors[0]


# ============================================================
# FIELD TYPES
# ============================================================

def test_validate_field_types_accepts_valid_equation(
    equation_base,
):
    errors = validate_field_types(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "field",
    [
        "equation_id",
        "target_variable_id",
        "scope_type",
        "expression",
        "source_reference",
        "status",
    ],
)
def test_validate_field_types_rejects_non_string_fields(
    equation_base,
    field,
):
    equation_base[field] = 123

    errors = validate_field_types(
        [equation_base]
    )

    assert any(field in error for error in errors)


def test_validate_field_types_accepts_scope_value_none(
    equation_base,
):
    equation_base["scope_value"] = None

    errors = validate_field_types(
        [equation_base]
    )

    assert errors == []


def test_validate_field_types_rejects_invalid_scope_value_type(
    equation_base,
):
    equation_base["scope_value"] = 123

    errors = validate_field_types(
        [equation_base]
    )

    assert any("scope_value" in error for error in errors)


def test_validate_field_types_accepts_integer_version(
    equation_base,
):
    equation_base["version"] = 3

    errors = validate_field_types(
        [equation_base]
    )

    assert errors == []


def test_validate_field_types_rejects_boolean_version(
    equation_base,
):
    equation_base["version"] = True

    errors = validate_field_types(
        [equation_base]
    )

    assert any("version" in error for error in errors)


def test_validate_field_types_rejects_string_version(
    equation_base,
):
    equation_base["version"] = "1"

    errors = validate_field_types(
        [equation_base]
    )

    assert any("version" in error for error in errors)


# ============================================================
# NON-EMPTY VALUES
# ============================================================

@pytest.mark.parametrize(
    "field",
    [
        "equation_id",
        "target_variable_id",
        "expression",
        "source_reference",
    ],
)
def test_validate_non_empty_values_rejects_empty_string(
    equation_base,
    field,
):
    equation_base[field] = "   "

    errors = validate_non_empty_values(
        [equation_base]
    )

    assert any(field in error for error in errors)


def test_validate_non_empty_values_accepts_valid_strings(
    equation_base,
):
    errors = validate_non_empty_values(
        [equation_base]
    )

    assert errors == []


# ============================================================
# ENUM VALUES
# ============================================================

def test_allowed_scope_types():
    assert ALLOWED_SCOPE_TYPES == {
        "linha",
        "linha_grupo",
        "área",
        "planta",
        "global",
    }


def test_allowed_scope_values():
    assert ALLOWED_SCOPE_VALUES == {
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
        "L1_L3",
        "L4_L5",
        "L6_L7",
        "L1_L7",
        "PLANTA",
    }


def test_allowed_statuses():
    assert ALLOWED_STATUSES == {
        "DRAFT",
        "PENDING",
        "APPROVED",
        "PUBLISHED",
        "REJECTED",
    }


@pytest.mark.parametrize(
    "scope_type",
    [
        "linha",
        "linha_grupo",
        "área",
        "planta",
        "global",
    ],
)
def test_validate_enum_values_accepts_scope_type(
    equation_base,
    scope_type,
):
    equation_base["scope_type"] = scope_type

    if scope_type in {
        "área",
        "planta",
        "global",
    }:
        equation_base["scope_value"] = None

    elif scope_type == "linha":
        equation_base["scope_value"] = "L1"

    elif scope_type == "linha_grupo":
        equation_base["scope_value"] = "L1_L3"

    errors = validate_enum_values(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "status",
    [
        "DRAFT",
        "PENDING",
        "APPROVED",
        "PUBLISHED",
        "REJECTED",
    ],
)
def test_validate_enum_values_accepts_status(
    equation_base,
    status,
):
    equation_base["status"] = status

    errors = validate_enum_values(
        [equation_base]
    )

    assert errors == []


def test_validate_enum_values_rejects_invalid_status(
    equation_base,
):
    equation_base["status"] = "ativo"

    errors = validate_enum_values(
        [equation_base]
    )

    assert any("status" in error for error in errors)


def test_validate_enum_values_rejects_invalid_scope_type(
    equation_base,
):
    equation_base["scope_type"] = "invalid_scope"

    errors = validate_enum_values(
        [equation_base]
    )

    assert any("scope_type" in error for error in errors)


def test_validate_enum_values_accepts_scope_value_none(
    equation_base,
):
    equation_base["scope_value"] = None

    errors = validate_enum_values(
        [equation_base]
    )

    assert errors == []


# ============================================================
# SCOPE CONSISTENCY
# ============================================================

def test_scope_global_requires_none(
    equation_base,
):
    equation_base["scope_type"] = "global"
    equation_base["scope_value"] = None

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_scope_global_rejects_value(
    equation_base,
):
    equation_base["scope_type"] = "global"
    equation_base["scope_value"] = "L1"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert len(errors) == 1
    assert "scope_value" in errors[0]


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
    ],
)
def test_scope_line_accepts_valid_line(
    equation_base,
    scope_value,
):
    equation_base["scope_type"] = "linha"
    equation_base["scope_value"] = scope_value

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_scope_line_rejects_line_group(
    equation_base,
):
    equation_base["scope_type"] = "linha"
    equation_base["scope_value"] = "L1_L3"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert len(errors) == 1


@pytest.mark.parametrize(
    "scope_value",
    [
        "L1_L3",
        "L4_L5",
        "L6_L7",
        "L1_L7",
    ],
)
def test_scope_line_group_accepts_valid_group(
    equation_base,
    scope_value,
):
    equation_base["scope_type"] = "linha_grupo"
    equation_base["scope_value"] = scope_value

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_scope_line_group_rejects_individual_line(
    equation_base,
):
    equation_base["scope_type"] = "linha_grupo"
    equation_base["scope_value"] = "L1"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert len(errors) == 1


def test_validate_scope_values_accepts_area_without_value(
    equation_base,
):
    equation_base["scope_type"] = "área"
    equation_base["scope_value"] = None

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_validate_scope_values_rejects_planta_without_value(
    equation_base,
):
    """
    Contrato de `planta` (corrigido): diferente de "área", o
    `scope_value=None` NÃO é mais aceito -- o contrato canônico
    exige "PLANTA" explicitamente, consistente com
    `ScopeResolver.PLANT_SCOPE`.
    """

    equation_base["scope_type"] = "planta"
    equation_base["scope_value"] = None

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors != []


def test_validate_scope_values_accepts_planta_with_planta_value(
    equation_base,
):
    equation_base["scope_type"] = "planta"
    equation_base["scope_value"] = "PLANTA"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "scope_type",
    [
        "área",
        "planta",
        "global",
    ],
)
def test_validate_scope_values_rejects_specific_value_for_non_line_scope(
    equation_base,
    scope_type,
):
    equation_base["scope_type"] = scope_type
    equation_base["scope_value"] = "L1"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors
    assert "scope_value" in errors[0]


# ============================================================
# CONSISTÊNCIA DE ESCOPO — L1_L7
# ============================================================

def test_validate_scope_consistency_accepts_l1_l7_for_linha(
    equation_base,
):
    equation_base["scope_type"] = "linha"
    equation_base["scope_value"] = "L1_L7"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_validate_scope_consistency_accepts_l1_l7_for_linha_grupo(
    equation_base,
):
    equation_base["scope_type"] = "linha_grupo"
    equation_base["scope_value"] = "L1_L7"

    errors = validate_scope_consistency(
        [equation_base]
    )

    assert errors == []


def test_validate_seed_accepts_l1_l7_for_linha(
    seed_root,
    equation_base,
):
    equation_base["scope_type"] = "linha"
    equation_base["scope_value"] = "L1_L7"

    write_equations(
        seed_root,
        [equation_base],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert errors == []
    assert warnings == []


def test_validate_seed_accepts_l1_l7_for_linha_grupo(
    seed_root,
    equation_base,
):
    equation_base["scope_type"] = "linha_grupo"
    equation_base["scope_value"] = "L1_L7"

    write_equations(
        seed_root,
        [equation_base],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert errors == []
    assert warnings == []


# ============================================================
# VERSION
# ============================================================

@pytest.mark.parametrize(
    "version",
    [
        1,
        2,
        3,
        10,
    ],
)
def test_validate_versions_accepts_valid_versions(
    equation_base,
    version,
):
    equation_base["version"] = version

    errors = validate_versions(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "version",
    [
        0,
        -1,
    ],
)
def test_validate_versions_rejects_invalid_versions(
    equation_base,
    version,
):
    equation_base["version"] = version

    errors = validate_versions(
        [equation_base]
    )

    assert len(errors) == 1
    assert "version" in errors[0]


def test_validate_versions_rejects_boolean_version(
    equation_base,
):
    equation_base["version"] = True

    errors = validate_versions(
        [equation_base]
    )

    assert len(errors) == 1
    assert "bool" in errors[0]


# ============================================================
# EQUATION ID RANGES
# ============================================================

def test_equation_id_ranges_are_defined():
    assert EQUATION_ID_RANGES == {
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


@pytest.mark.parametrize(
    "equation_id",
    [
        "EQ10000",
        "EQ11000",
        "EQ12000",
        "EQ13000",
        "EQ14000",
        "EQ15000",
        "EQ16000",
        "EQ17000",
        "EQ18000",
        "EQ19000",
        "EQ20000",
        "EQ21000",
        "EQ22000",
        "EQ23000",
    ],
)
def test_validate_equation_id_ranges_accepts_valid_ids(
    equation_base,
    equation_id,
):
    equation_base["equation_id"] = equation_id

    errors = validate_equation_id_ranges(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "equation_id",
    [
        "EQ10999",
        "EQ11999",
        "EQ12999",
        "EQ13999",
        "EQ14999",
        "EQ15999",
        "EQ16999",
        "EQ17999",
        "EQ18999",
        "EQ19999",
        "EQ20999",
        "EQ21999",
        "EQ22999",
        "EQ23999",
    ],
)
def test_validate_equation_id_ranges_accepts_upper_boundaries(
    equation_base,
    equation_id,
):
    equation_base["equation_id"] = equation_id

    errors = validate_equation_id_ranges(
        [equation_base]
    )

    assert errors == []


@pytest.mark.parametrize(
    "equation_id",
    [
        "EQ09999",
        "EQ109999",
        "EQ38000",
        "EQ99999",
    ],
)
def test_validate_equation_id_ranges_rejects_ids_outside_ranges(
    equation_base,
    equation_id,
):
    equation_base["equation_id"] = equation_id

    errors = validate_equation_id_ranges(
        [equation_base]
    )

    assert len(errors) == 1
    assert "faixa reservada" in errors[0]


@pytest.mark.parametrize(
    "equation_id",
    [
        "12001",
        "EQABC",
        "EQ12A01",
        "E12001",
    ],
)
def test_validate_equation_id_ranges_rejects_invalid_format(
    equation_base,
    equation_id,
):
    equation_base["equation_id"] = equation_id

    errors = validate_equation_id_ranges(
        [equation_base]
    )

    assert len(errors) == 1


# ============================================================
# DUPLICIDADE DE EQUATION_ID + VERSION
# ============================================================

def test_validate_equation_ids_accepts_unique_equations(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"

    errors = validate_equation_ids(
        [
            equation_base,
            second_equation,
        ]
    )

    assert errors == []


def test_validate_equation_ids_rejects_duplicate_id_and_version(
    equation_base,
):
    second_equation = equation_base.copy()

    errors = validate_equation_ids(
        [
            equation_base,
            second_equation,
        ]
    )

    assert len(errors) == 1
    assert "combinação duplicada" in errors[0]


def test_validate_equation_ids_accepts_same_id_different_versions(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["version"] = 2

    errors = validate_equation_ids(
        [
            equation_base,
            second_equation,
        ]
    )

    assert errors == []


# ============================================================
# ASSINATURA SEMÂNTICA
# ============================================================

def test_build_equation_signature(
    equation_base,
):
    signature = build_equation_signature(
        equation_base
    )

    assert signature == (
        "VAR12001",
        "global",
        None,
        "production * yield",
    )


def test_semantic_signature_excludes_equation_id_and_version(
    equation_base,
):
    first = equation_base.copy()

    second = equation_base.copy()
    second["equation_id"] = "EQ12099"
    second["version"] = 7

    assert (
        build_equation_signature(first)
        == build_equation_signature(second)
    )


def test_validate_equation_signatures_returns_warning_for_duplicate(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"

    warnings = validate_equation_signatures(
        [
            equation_base,
            second_equation,
        ]
    )

    assert len(warnings) == 1
    assert "mesma assinatura semântica" in warnings[0]


def test_validate_equation_signatures_allows_different_expressions(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"
    second_equation["expression"] = "production + yield"

    warnings = validate_equation_signatures(
        [
            equation_base,
            second_equation,
        ]
    )

    assert warnings == []


def test_validate_equation_signatures_allows_different_scope(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"
    second_equation["scope_type"] = "linha"
    second_equation["scope_value"] = "L1"

    warnings = validate_equation_signatures(
        [
            equation_base,
            second_equation,
        ]
    )

    assert warnings == []


def test_validate_equation_signatures_allows_different_target_variable(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"
    second_equation["target_variable_id"] = "VAR12002"

    warnings = validate_equation_signatures(
        [
            equation_base,
            second_equation,
        ]
    )

    assert warnings == []


def test_validate_equation_signatures_same_equation_different_versions(
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["version"] = 2

    warnings = validate_equation_signatures(
        [
            equation_base,
            second_equation,
        ]
    )

    assert len(warnings) == 1


# ============================================================
# SEED COMPLETO
# ============================================================

def test_load_equations_from_seed(
    seed_root,
    equation_base,
):
    write_equations(
        seed_root,
        [equation_base],
    )

    equations, errors = load_equations_from_seed(
        seed_root
    )

    assert errors == []
    assert len(equations) == 1
    assert equations[0]["equation_id"] == "EQ12001"


def test_find_equation_files(
    seed_root,
    equation_base,
):
    write_equations(
        seed_root,
        [equation_base],
    )

    files = find_equation_files(
        seed_root
    )

    assert len(files) == 1
    assert files[0].name == "equations.json"


def test_validate_seed_accepts_valid_seed(
    seed_root,
    equation_base,
):
    write_equations(
        seed_root,
        [equation_base],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert errors == []
    assert warnings == []


def test_validate_seed_rejects_missing_scope_value(
    seed_root,
    equation_base,
):
    del equation_base["scope_value"]

    write_equations(
        seed_root,
        [equation_base],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert any(
        "scope_value" in error
        for error in errors
    )


def test_validate_seed_rejects_empty_expression(
    seed_root,
    equation_base,
):
    equation_base["expression"] = ""

    write_equations(
        seed_root,
        [equation_base],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert any(
        "expression" in error
        for error in errors
    )


def test_validate_seed_returns_warning_for_semantic_duplicate(
    seed_root,
    equation_base,
):
    second_equation = equation_base.copy()
    second_equation["equation_id"] = "EQ12002"

    write_equations(
        seed_root,
        [
            equation_base,
            second_equation,
        ],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert errors == []
    assert len(warnings) == 1
    assert "mesma assinatura semântica" in warnings[0]


def test_validate_seed_rejects_duplicate_id_and_version(
    seed_root,
    equation_base,
):
    second_equation = equation_base.copy()

    write_equations(
        seed_root,
        [
            equation_base,
            second_equation,
        ],
    )

    errors, warnings = validate_seed(
        seed_root
    )

    assert any(
        "combinação duplicada" in error
        for error in errors
    )


# ============================================================
# EQUATION_ID_RANGES -- contrato da taxonomia oficial de blocos
# ============================================================
#
# Protege a taxonomia oficial de 28 blocos (10000-37999), sem
# depender de nenhuma seed real: valida a estrutura do proprio
# catalogo. Identica, bloco a bloco, a VARIABLE_ID_RANGES e a
# PARAMETER_ID_RANGES. "hydrate" e "costs" nao existem mais como
# blocos de ID; "max_ht" ocupa a faixa antes usada por "hydrate";
# "shared" foi realocado para 37000-37999.
#
# (O teste `test_equation_id_ranges_are_defined`, acima, ja
# confere a igualdade byte-a-byte com a taxonomia oficial; os
# testes abaixo protegem a ESTRUTURA do catalogo -- contagem,
# contiguidade, ausencia de sobreposicao -- que a igualdade nao
# comunica isoladamente.)


def test_equation_id_ranges_has_exactly_28_blocks():
    assert len(EQUATION_ID_RANGES) == 28


def test_equation_id_ranges_hydrate_and_costs_no_longer_exist():
    assert "hydrate" not in EQUATION_ID_RANGES
    assert "costs" not in EQUATION_ID_RANGES


def test_equation_id_ranges_max_ht_occupies_former_hydrate_range():
    assert EQUATION_ID_RANGES["max_ht"] == (13000, 13999)


def test_equation_id_ranges_shared_is_the_last_block():
    names = list(EQUATION_ID_RANGES)
    assert names[-1] == "shared"
    assert EQUATION_ID_RANGES["shared"] == (37000, 37999)


def test_equation_id_ranges_first_block_starts_at_10000():
    first_name = next(iter(EQUATION_ID_RANGES))
    assert EQUATION_ID_RANGES[first_name][0] == 10000


def test_equation_id_ranges_last_block_ends_at_37999():
    last_name = list(EQUATION_ID_RANGES)[-1]
    assert EQUATION_ID_RANGES[last_name][1] == 37999


def test_equation_id_ranges_every_block_has_exactly_1000_ids():
    for name, (minimum, maximum) in EQUATION_ID_RANGES.items():
        assert maximum - minimum + 1 == 1000, name


def test_equation_id_ranges_no_overlap_between_any_two_blocks():
    intervals = sorted(EQUATION_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min > previous_max


def test_equation_id_ranges_are_contiguous_with_no_gaps():
    intervals = sorted(EQUATION_ID_RANGES.values())

    for (_, previous_max), (next_min, _) in zip(
        intervals, intervals[1:]
    ):
        assert next_min == previous_max + 1


def test_equation_id_ranges_names_have_no_duplicates():
    names = list(EQUATION_ID_RANGES)
    assert len(names) == len(set(names))
