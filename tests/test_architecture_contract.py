import json

import pytest

from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.equation_selector import EquationSelector
from app.engine.forecast_engine import ForecastEngine
from app.repositories.seed_loader import SeedLoader


# ============================================================
# HELPERS
# ============================================================


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
    variable_name="production_total",
):
    return {
        "variable_id": variable_id,
        "variable_name": variable_name,
        "description": "Produção total",
        "unit": "t",
        "variable_type": "entrada",
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


def make_parameter(
    parameter_id="PARAM12001",
    value=0.80,
    version=1,
):
    return {
        "parameter_id": parameter_id,
        "parameter_name": "test_parameter",
        "description": "Test parameter",
        "unit": "%",
        "value": value,
        "version": version,
        "scope_type": "linha",
        "scope_value": "L1",
        "source_reference": "NovoOficial!D152:O152",
        "status": "ativo",
    }


def make_equation(
    equation_id="EQ12001",
    version=1,
    expression="VAR12001 * PARAM12001",
    status="PUBLISHED",
):
    return {
        "equation_id": equation_id,
        "target_variable_id": "VAR12002",
        "version": version,
        "scope_type": "linha",
        "scope_value": "L1",
        "expression": expression,
        "source_reference": "NovoOficial!D153:O153",
        "status": status,
    }


def create_complete_seed(
    seed_root,
):
    production_path = seed_root / "production"

    production_path.mkdir(
        parents=True
    )

    write_json(
        production_path / "variables.json",
        [
            make_variable(),
            make_target_variable(),
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


# ============================================================
# 1. CONTRACT — DOMAIN OBJECTS
# ============================================================


def test_domain_objects_contract():
    variable = Variable(
        **make_variable()
    )

    parameter = Parameter(
        **make_parameter()
    )

    equation = Equation(
        **make_equation()
    )

    assert variable.variable_id == "VAR12001"
    assert parameter.parameter_id == "PARAM12001"
    assert equation.equation_id == "EQ12001"

    assert equation.scope_type == "linha"
    assert equation.scope_value == "L1"


# ============================================================
# 2. CONTRACT — REGISTRIES
# ============================================================


def test_registries_contract():
    variable_registry = VariableRegistry()
    parameter_registry = ParameterRegistry()
    equation_registry = EquationRegistry()

    variable = Variable(
        **make_variable()
    )

    parameter = Parameter(
        **make_parameter()
    )

    equation = Equation(
        **make_equation()
    )

    variable_registry.add(
        variable
    )

    parameter_registry.add(
        parameter
    )

    equation_registry.add(
        equation
    )

    assert variable_registry.get(
        "VAR12001"
    ) is variable

    assert parameter_registry.get(
        "PARAM12001"
    ) is parameter

    assert equation_registry.get(
        "EQ12001",
        1,
    ) is equation


# ============================================================
# 3. CONTRACT — SEED → REGISTRY
# ============================================================


def test_seed_to_registry_contract(
    tmp_path,
):
    seed_root = tmp_path / "seed"

    create_complete_seed(
        seed_root
    )

    loader = SeedLoader(
        seed_root
    )

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

    assert isinstance(
        variable_registry.get(
            "VAR12001"
        ),
        Variable,
    )

    assert isinstance(
        parameter_registry.get(
            "PARAM12001"
        ),
        Parameter,
    )

    assert isinstance(
        equation_registry.get(
            "EQ12001",
            1,
        ),
        Equation,
    )


# ============================================================
# 4. CONTRACT — EQUATION SELECTOR
# ============================================================


def test_equation_selector_contract():
    registry = EquationRegistry()

    equation_v1 = Equation(
        **make_equation(
            version=1,
            status="PUBLISHED",
        )
    )

    equation_v2 = Equation(
        **make_equation(
            version=2,
            expression=(
                "VAR12001 * PARAM12001 * 1.05"
            ),
            status="PUBLISHED",
        )
    )

    registry.add(
        equation_v1
    )

    registry.add(
        equation_v2
    )

    selector = EquationSelector(
        registry
    )

    selected = selector.select(
        equation_id="EQ12001",
        scope_type="linha",
        scope_value="L1",
    )

    assert selected.equation_id == (
        "EQ12001"
    )

    assert selected.version == 2

    assert selected.scope_type == (
        "linha"
    )

    assert selected.scope_value == (
        "L1"
    )


# ============================================================
# 5. CONTRACT — CALCULATION CONTEXT
# ============================================================


def test_calculation_context_contract():
    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    assert context.get_variable(
        "VAR12001"
    ) == 1500.0

    assert context.get_parameter(
        "PARAM12001"
    ) == 0.80


# ============================================================
# 6. CONTRACT — EQUATION ENGINE
# ============================================================


def test_equation_engine_contract():
    equation = Equation(
        **make_equation()
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 1200.0


# ============================================================
# 7. CONTRACT — FORECAST ENGINE
# ============================================================


def test_forecast_engine_contract(
    tmp_path,
):
    seed_root = tmp_path / "seed"

    create_complete_seed(
        seed_root
    )

    loader = SeedLoader(
        seed_root
    )

    (
        variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    engine = ForecastEngine()

    result = engine.calculate_from_registry(
        equation_registry=equation_registry,
        variable_registry=variable_registry,
        parameter_registry=parameter_registry,
        calculation_context=context,
    )

    assert result["EQ12001"] == 1200.0


# ============================================================
# 8. CONTRACT — FULL ARCHITECTURE FLOW
# ============================================================


def test_full_architecture_contract(
    tmp_path,
):
    seed_root = tmp_path / "seed"

    create_complete_seed(
        seed_root
    )

    # --------------------------------------------------------
    # Seed → Registry
    # --------------------------------------------------------

    loader = SeedLoader(
        seed_root
    )

    (
        variable_registry,
        parameter_registry,
        equation_registry,
    ) = loader.load_all()

    # --------------------------------------------------------
    # Registry → EquationSelector
    # --------------------------------------------------------

    selector = EquationSelector(
        equation_registry
    )

    equation = selector.select(
        equation_id="EQ12001",
        scope_type="linha",
        scope_value="L1",
    )

    # --------------------------------------------------------
    # CalculationContext
    # --------------------------------------------------------

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            "PARAM12001": 0.80,
        },
    )

    # --------------------------------------------------------
    # EquationEngine
    # --------------------------------------------------------

    equation_engine = EquationEngine()

    direct_result = equation_engine.calculate(
        equation,
        context,
    )

    assert direct_result == 1200.0

    # --------------------------------------------------------
    # ForecastEngine
    # --------------------------------------------------------

    forecast_engine = ForecastEngine()

    forecast_result = (
        forecast_engine.calculate_from_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
            calculation_context=context,
        )
    )

    assert forecast_result[
        "EQ12001"
    ] == 1200.0

    assert context.get_variable(
        "VAR12002"
    ) == 1200.0

# ============================================================
# 9. CONTRACT — SCOPE TYPES
# ============================================================


@pytest.mark.parametrize(
    "scope_type,scope_value",
    [
        ("linha", "L1"),
        ("linha_grupo", "L1_L3"),
        ("área", None),
        ("planta", None),
        ("global", None),
    ],
)
def test_scope_type_contract(
    scope_type,
    scope_value,
):
    equation_data = make_equation()

    equation_data[
        "scope_type"
    ] = scope_type

    equation_data[
        "scope_value"
    ] = scope_value

    equation = Equation(
        **equation_data
    )

    assert equation.scope_type == (
        scope_type
    )

    assert equation.scope_value == (
        scope_value
    )
