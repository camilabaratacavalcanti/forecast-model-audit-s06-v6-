import json

import pytest

from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.registry import VariableRegistry
from app.repositories.seed_loader import SeedLoader
from app.domain.equations.models import Equation
from app.domain.parameters.models import Parameter
from app.domain.variables.models import Variable


def write_json(
    file_path,
    data,
):
    file_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def make_variable(
    variable_id="VAR12001",
):
    return {
        "variable_id": variable_id,
        "variable_name": "production_total",
        "description": "Produção total",
        "unit": "t",
        "variable_type": "entrada",
        "frequency": "mensal",
        "scope_type": "linha",
        "scope_value": "L1",
        "source_reference": "NovoOficial!D152:O152",
        "status": "ativo",
    }


def make_parameter(
    parameter_id="PARAM12001",
):
    return {
        "parameter_id": parameter_id,
        "parameter_name": "yield_factor",
        "description": "Fator de ajuste",
        "unit": "%",
        "value": 0.80,
        "version": 1,
        "scope_type": "linha",
        "scope_value": "L1",
        "source_reference": "NovoOficial!D154",
        "status": "ativo",
    }


def make_equation(
    equation_id="EQ12001",
):
    return {
        "equation_id": equation_id,
        "target_variable_id": "VAR12002",
        "version": 1,
        "scope_type": "linha",
        "scope_value": "L1",
        "expression": "VAR12001 * PARAM12001",
        "source_reference": "NovoOficial!D153:O153",
        "status": "PUBLISHED",
    }


# ============================================================
# load_variables
# ============================================================


def test_load_variables_returns_variable_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_variables()

    assert isinstance(
        registry,
        VariableRegistry,
    )

    assert len(registry.all()) == 1

    variable = registry.get(
        "VAR12001"
    )

    assert variable.variable_name == (
        "production_total"
    )


def test_load_variables_removes_validator_block_metadata(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_variables()

    variable = registry.get(
        "VAR12001"
    )

    assert not hasattr(
        variable,
        "_block",
    )


def test_load_variables_accepts_existing_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    existing_registry = VariableRegistry()

    loader = SeedLoader(seed_root)

    result = loader.load_variables(
        existing_registry
    )

    assert result is existing_registry
    assert len(result.all()) == 1


def test_load_variables_rejects_invalid_seed(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_variable = make_variable()

    invalid_variable["variable_type"] = (
        "invalid_type"
    )

    write_json(
        production_path / "variables.json",
        [
            invalid_variable,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Variable seed validation failed",
    ):
        loader.load_variables()


# ============================================================
# load_parameters
# ============================================================


def test_load_parameters_returns_parameter_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "parameters.json",
        [
            make_parameter(),
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_parameters()

    assert isinstance(
        registry,
        ParameterRegistry,
    )

    assert len(registry.all()) == 1

    parameter = registry.get(
        "PARAM12001"
    )

    assert parameter.value == 0.80


def test_load_parameters_accepts_existing_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "parameters.json",
        [
            make_parameter(),
        ],
    )

    existing_registry = ParameterRegistry()

    loader = SeedLoader(seed_root)

    result = loader.load_parameters(
        existing_registry
    )

    assert result is existing_registry
    assert len(result.all()) == 1


def test_load_parameters_rejects_invalid_seed(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_parameter = make_parameter()

    invalid_parameter["value"] = "invalid"

    write_json(
        production_path / "parameters.json",
        [
            invalid_parameter,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Parameter seed validation failed",
    ):
        loader.load_parameters()


# ============================================================
# load_equations
# ============================================================


def test_load_equations_returns_equation_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "equations.json",
        [
            make_equation(),
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_equations()

    assert isinstance(
        registry,
        EquationRegistry,
    )

    assert len(registry.all()) == 1

    equation = registry.get(
        "EQ12001",
        1,
    )

    assert equation.expression == (
        "VAR12001 * PARAM12001"
    )


def test_load_equations_accepts_existing_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "equations.json",
        [
            make_equation(),
        ],
    )

    existing_registry = EquationRegistry()

    loader = SeedLoader(seed_root)

    result = loader.load_equations(
        existing_registry
    )

    assert result is existing_registry
    assert len(result.all()) == 1


def test_load_equations_rejects_invalid_seed(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_equation = make_equation()

    invalid_equation["version"] = 0

    write_json(
        production_path / "equations.json",
        [
            invalid_equation,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Equation seed validation failed",
    ):
        loader.load_equations()


# ============================================================
# load_all
# ============================================================


def test_load_all_returns_all_registries(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    write_json(
        production_path / "parameters.json",
        [
            make_parameter(),
        ],
    )

    write_json(
        production_path / "equations.json",
        [
            make_equation(),
        ],
    )

    loader = SeedLoader(seed_root)

    (
        variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    assert isinstance(
        variable_registry,
        VariableRegistry,
    )

    assert isinstance(
        parameter_registry,
        ParameterRegistry,
    )

    assert isinstance(
        equation_registry,
        EquationRegistry,
    )

    assert len(variable_registry.all()) == 1
    assert len(parameter_registry.all()) == 1
    assert len(equation_registry.all()) == 1


def test_load_all_rejects_invalid_variable_seed(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_variable = make_variable()

    invalid_variable["unit"] = (
        "invalid_unit"
    )

    write_json(
        production_path / "variables.json",
        [
            invalid_variable,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Variable seed validation failed",
    ):
        loader.load_all()


# ============================================================
# INTEGRAÇÃO — VARIABLES
# ============================================================


def test_load_variables_json_to_domain_object_to_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    variable_data = make_variable()

    write_json(
        production_path / "variables.json",
        [variable_data],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_variables()

    variable = registry.get(
        "VAR12001"
    )

    assert isinstance(
        variable,
        Variable,
    )

    assert variable.variable_id == (
        variable_data["variable_id"]
    )

    assert variable.variable_name == (
        variable_data["variable_name"]
    )

    assert variable.unit == (
        variable_data["unit"]
    )


def test_load_variables_does_not_register_invalid_variable(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_variable = make_variable()

    invalid_variable["variable_id"] = (
        "VAR99999"
    )

    write_json(
        production_path / "variables.json",
        [invalid_variable],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Variable seed validation failed",
    ):
        loader.load_variables()

    registry = VariableRegistry()

    assert len(registry.all()) == 0


def test_load_variables_multiple_records_preserves_all_records(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    variable_1 = make_variable(
        "VAR12001"
    )

    variable_2 = make_variable(
        "VAR12002"
    )

    variable_2["variable_name"] = (
        "production_secondary"
    )

    write_json(
        production_path / "variables.json",
        [
            variable_1,
            variable_2,
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_variables()

    assert len(registry.all()) == 2

    assert registry.get(
        "VAR12001"
    ).variable_name == "production_total"

    assert registry.get(
        "VAR12002"
    ).variable_name == (
        "production_secondary"
    )


# ============================================================
# INTEGRAÇÃO — PARAMETERS
# ============================================================


def test_load_parameters_json_to_domain_object_to_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    parameter_data = make_parameter()

    write_json(
        production_path / "parameters.json",
        [parameter_data],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_parameters()

    parameter = registry.get(
        "PARAM12001"
    )

    assert isinstance(
        parameter,
        Parameter,
    )

    assert parameter.parameter_id == (
        parameter_data["parameter_id"]
    )

    assert parameter.parameter_name == (
        parameter_data["parameter_name"]
    )

    assert parameter.value == (
        parameter_data["value"]
    )


def test_load_parameters_does_not_register_invalid_parameter(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_parameter = make_parameter()

    invalid_parameter["parameter_id"] = (
        "PARAM99999"
    )

    write_json(
        production_path / "parameters.json",
        [invalid_parameter],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Parameter seed validation failed",
    ):
        loader.load_parameters()

    registry = ParameterRegistry()

    assert len(registry.all()) == 0


def test_load_parameters_multiple_records_preserves_all_records(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    parameter_1 = make_parameter(
        "PARAM12001"
    )

    parameter_2 = make_parameter(
        "PARAM12002"
    )

    parameter_2["parameter_name"] = (
        "secondary_factor"
    )

    write_json(
        production_path / "parameters.json",
        [
            parameter_1,
            parameter_2,
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_parameters()

    assert len(registry.all()) == 2

    assert registry.get(
        "PARAM12001"
    ).parameter_name == "yield_factor"

    assert registry.get(
        "PARAM12002"
    ).parameter_name == (
        "secondary_factor"
    )


# ============================================================
# INTEGRAÇÃO — EQUATIONS
# ============================================================


def test_load_equations_json_to_domain_object_to_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    equation_data = make_equation()

    write_json(
        production_path / "equations.json",
        [equation_data],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_equations()

    equation = registry.get(
        "EQ12001",
        1,
    )

    assert isinstance(
        equation,
        Equation,
    )

    assert equation.equation_id == (
        equation_data["equation_id"]
    )

    assert equation.target_variable_id == (
        equation_data["target_variable_id"]
    )

    assert equation.expression == (
        equation_data["expression"]
    )


def test_load_equations_does_not_register_invalid_equation(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    invalid_equation = make_equation()

    invalid_equation["equation_id"] = (
        "EQ99999"
    )

    write_json(
        production_path / "equations.json",
        [invalid_equation],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Equation seed validation failed",
    ):
        loader.load_equations()

    registry = EquationRegistry()

    assert len(registry.all()) == 0


def test_load_equations_multiple_versions_preserves_all_versions(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    equation_v1 = make_equation(
        "EQ12001"
    )

    equation_v2 = make_equation(
        "EQ12001"
    )

    equation_v2["version"] = 2
    equation_v2["expression"] = (
        "VAR12001 * PARAM12001 * 1.05"
    )

    write_json(
        production_path / "equations.json",
        [
            equation_v1,
            equation_v2,
        ],
    )

    loader = SeedLoader(seed_root)

    registry = loader.load_equations()

    assert len(registry.all()) == 2

    assert registry.get(
        "EQ12001",
        1,
    ).expression == (
        "VAR12001 * PARAM12001"
    )

    assert registry.get(
        "EQ12001",
        2,
    ).expression == (
        "VAR12001 * PARAM12001 * 1.05"
    )


# ============================================================
# INTEGRAÇÃO — LOAD ALL
# ============================================================


def test_load_all_preserves_relationships_between_entities(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(
                "VAR12001"
            ),
            make_variable(
                "VAR12002"
            ),
        ],
    )

    write_json(
        production_path / "parameters.json",
        [
            make_parameter(
                "PARAM12001"
            ),
        ],
    )

    equation = make_equation(
        "EQ12001"
    )

    equation["target_variable_id"] = (
        "VAR12002"
    )

    write_json(
        production_path / "equations.json",
        [equation],
    )

    loader = SeedLoader(seed_root)

    (
        variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    variable = variable_registry.get(
        "VAR12002"
    )

    parameter = parameter_registry.get(
        "PARAM12001"
    )

    equation = equation_registry.get(
        "EQ12001",
        1,
    )

    assert isinstance(
        variable,
        Variable,
    )

    assert isinstance(
        parameter,
        Parameter,
    )

    assert isinstance(
        equation,
        Equation,
    )

    assert equation.target_variable_id == (
        variable.variable_id
    )

    assert "PARAM12001" in (
        equation.expression
    )


def test_load_all_stops_when_parameter_seed_is_invalid(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    invalid_parameter = make_parameter()

    invalid_parameter["value"] = (
        "invalid"
    )

    write_json(
        production_path / "parameters.json",
        [invalid_parameter],
    )

    write_json(
        production_path / "equations.json",
        [
            make_equation(),
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Parameter seed validation failed",
    ):
        loader.load_all()


def test_load_all_stops_when_equation_seed_is_invalid(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
        ],
    )

    write_json(
        production_path / "parameters.json",
        [
            make_parameter(),
        ],
    )

    invalid_equation = make_equation()

    invalid_equation["version"] = 0

    write_json(
        production_path / "equations.json",
        [invalid_equation],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Equation seed validation failed",
    ):
        loader.load_all()


# ============================================================
# Detectar a duplicidade antes de o Registry receber os objetos
# ============================================================


# Para Variable


def test_load_variables_rejects_duplicate_variable_id_before_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    variable_1 = make_variable(
        "VAR12001"
    )

    variable_2 = make_variable(
        "VAR12001"
    )

    variable_2["variable_name"] = (
        "duplicated_variable"
    )

    write_json(
        production_path / "variables.json",
        [
            variable_1,
            variable_2,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Variable seed validation failed",
    ):
        loader.load_variables()


# Para Equation


def test_load_equations_rejects_duplicate_id_and_version_before_registry(
    tmp_path,
):
    seed_root = tmp_path / "seed"
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    equation_1 = make_equation(
        "EQ12001"
    )

    equation_2 = make_equation(
        "EQ12001"
    )

    write_json(
        production_path / "equations.json",
        [
            equation_1,
            equation_2,
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(
        ValueError,
        match="Equation seed validation failed",
    ):
        loader.load_equations()
