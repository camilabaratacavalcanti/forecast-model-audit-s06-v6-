import json

import pytest

from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import (
    ParameterNotFoundError,
    VariableNotFoundError,
)
from app.repositories.seed_loader import SeedLoader


# ============================================================
# HELPERS
# ============================================================


def write_json(file_path, data):
    file_path.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )


def make_variable(
    variable_id="VAR12001",
    variable_type="entrada",
):
    return {
        "variable_id": variable_id,
        "variable_name": "production_total",
        "description": "Produção total",
        "unit": "t",
        "variable_type": variable_type,
        "frequency": "mensal",
        "scope_type": "linha",
        "scope_value": "L1",
        "source_reference": "NovoOficial!D152:O152",
        "status": "ativo",
    }


def make_target_variable():
    return {
        "variable_id": "VAR12002",
        "variable_name": "production_adjusted",
        "description": "Produção ajustada",
        "unit": "t",
        "variable_type": "calculado",
        "frequency": "mensal",
        "scope_type": "linha",
        "scope_value": "L1",
        "source_reference": "NovoOficial!D153:O153",
        "status": "ativo",
    }


def make_parameter(parameter_id="PARAM12001"):
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
    expression="VAR12001 * PARAM12001",
):
    return {
        "equation_id": equation_id,
        "target_variable_id": "VAR12002",
        "version": 1,
        "scope_type": "linha",
        "scope_value": "L1",
        "expression": expression,
        "source_reference": "NovoOficial!D153:O153",
        "status": "PUBLISHED",
    }


def create_complete_seed(
    seed_root,
    variables=None,
    parameters=None,
    equations=None,
):
    production_path = seed_root / "production"
    production_path.mkdir(parents=True)

    write_json(
        production_path / "variables.json",
        (
            variables
            if variables is not None
            else [
                make_variable(),
                make_target_variable(),
            ]
        ),
    )

    write_json(
        production_path / "parameters.json",
        parameters
        if parameters is not None
        else [make_parameter()],
    )

    write_json(
        production_path / "equations.json",
        equations
        if equations is not None
        else [make_equation()],
    )


# ============================================================
# TESTE 1 — FLUXO COMPLETO
# ============================================================


def test_seed_to_engine_complete_flow(tmp_path):
    seed_root = tmp_path / "seed"

    create_complete_seed(seed_root)

    loader = SeedLoader(seed_root)

    (
        variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    input_variable = variable_registry.get("VAR12001")
    target_variable = variable_registry.get("VAR12002")
    parameter = parameter_registry.get("PARAM12001")
    equation = equation_registry.get("EQ12001", 1)

    assert input_variable.variable_id == "VAR12001"
    assert target_variable.variable_id == "VAR12002"
    assert parameter.parameter_id == "PARAM12001"
    assert equation.equation_id == "EQ12001"

    context = CalculationContext(
        variables={
            input_variable.variable_id: 1500.0,
        },
        parameters={
            parameter.parameter_id: parameter.value,
        },
    )

    assert context.get_variable("VAR12001") == 1500.0
    assert context.get_parameter("PARAM12001") == 0.80

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 1200.0


# ============================================================
# TESTE 2 — EQUAÇÃO CARREGADA DO SEED
# ============================================================


def test_seed_loaded_equation_is_used_by_engine(tmp_path):
    seed_root = tmp_path / "seed"

    create_complete_seed(seed_root)

    loader = SeedLoader(seed_root)

    (
        _variable_registry,
        _parameter_registry,
        equation_registry,
    ) = loader.load_all()

    equation = equation_registry.get(
        "EQ12001",
        1,
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1000.0,
        },
        parameters={
            "PARAM12001": 0.75,
        },
    )

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 750.0


# ============================================================
# TESTE 3 — VARIÁVEL AUSENTE NO CONTEXTO
# ============================================================


def test_seed_to_engine_missing_variable_propagates_error(tmp_path):
    seed_root = tmp_path / "seed"

    create_complete_seed(seed_root)

    loader = SeedLoader(seed_root)

    (
        _variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    equation = equation_registry.get(
        "EQ12001",
        1,
    )

    parameter = parameter_registry.get(
        "PARAM12001",
    )

    context = CalculationContext(
        variables={},
        parameters={
            parameter.parameter_id: parameter.value,
        },
    )

    engine = EquationEngine()

    with pytest.raises(VariableNotFoundError):
        engine.calculate(
            equation,
            context,
        )


# ============================================================
# TESTE 4 — PARÂMETRO AUSENTE NO CONTEXTO
# ============================================================


def test_seed_to_engine_missing_parameter_propagates_error(
    tmp_path,
):
    seed_root = tmp_path / "seed"

    create_complete_seed(seed_root)

    loader = SeedLoader(seed_root)

    (
        _variable_registry,
        _parameter_registry,
        equation_registry,
    ) = loader.load_all()

    equation = equation_registry.get(
        "EQ12001",
        1,
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={},
    )

    engine = EquationEngine()

    with pytest.raises(ParameterNotFoundError):
        engine.calculate(
            equation,
            context,
        )


# ============================================================
# TESTE 5 — SEED INVÁLIDO É REJEITADO ANTES DO ENGINE
# ============================================================


def test_invalid_seed_is_rejected_before_engine(tmp_path):
    seed_root = tmp_path / "seed"

    invalid_variable = make_variable(
        variable_id="VAR99999",
    )

    create_complete_seed(
        seed_root,
        variables=[
            invalid_variable,
            make_target_variable(),
        ],
    )

    loader = SeedLoader(seed_root)

    with pytest.raises(ValueError):
        loader.load_all()


# ============================================================
# TESTE 6 — ALTERAÇÃO DA EQUAÇÃO NO SEED
# ============================================================


def test_seed_equation_calculates_using_context_values(
    tmp_path,
):
    seed_root = tmp_path / "seed"

    equation = make_equation(
        expression="VAR12001 * PARAM12001 + 100",
    )

    create_complete_seed(
        seed_root,
        equations=[equation],
    )

    loader = SeedLoader(seed_root)

    (
        _variable_registry,
        _parameter_registry,
        equation_registry,
    ) = loader.load_all()

    loaded_equation = equation_registry.get(
        "EQ12001",
        1,
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1000.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    engine = EquationEngine()

    result = engine.calculate(
        loaded_equation,
        context,
    )

    assert result == 900.0
