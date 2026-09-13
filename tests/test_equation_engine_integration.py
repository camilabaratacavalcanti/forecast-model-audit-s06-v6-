"""
Testa o fluxo mais próximo do uso real, integrando os componentes do
Engine em conjunto.
"""


from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.models import Parameter
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.models import Variable
from app.domain.variables.registry import VariableRegistry

from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine


def test_equation_engine_integrates_with_registries():

    variable_registry = VariableRegistry()

    variable_registry.add(
        Variable(
            variable_id="VAR12001",
            variable_name="production_total",
            description="Produção total",
            unit="t",
            variable_type="entrada",
            frequency="mensal",
            scope_type="linha",
            scope_value="L1",
            source_reference="NovoOficial!D152:O152",
            status="ativo",
        )
    )

    variable_registry.add(
        Variable(
            variable_id="VAR12002",
            variable_name="production_adjusted",
            description="Produção ajustada",
            unit="t",
            variable_type="calculado",
            frequency="mensal",
            scope_type="linha",
            scope_value="L1",
            source_reference="NovoOficial!D153:O153",
            status="ativo",
        )
    )

    parameter_registry = ParameterRegistry()

    parameter_registry.add(
        Parameter(
            parameter_id="PARAM12001",
            parameter_name="yield_factor",
            description="Fator de ajuste",
            unit="%",
            value=0.80,
            version=1,
            scope_type="linha",
            scope_value="L1",
            source_reference="NovoOficial!D154",
            status="ativo",
        )
    )

    equation_registry = EquationRegistry()

    equation_registry.add(
        Equation(
            equation_id="EQ12001",
            target_variable_id="VAR12002",
            version=1,
            scope_type="linha",
            scope_value="L1",
            expression="VAR12001 * PARAM12001",
            source_reference="NovoOficial!D153:O153",
            status="PUBLISHED",
        )
    )

    equation = equation_registry.get(
        "EQ12001",
        1,
    )

    parameter = parameter_registry.get(
        "PARAM12001"
    )

    context = CalculationContext(
        variables={
            "VAR12001": 1500.0,
        },
        parameters={
            parameter.parameter_id: parameter.value,
        },
    )

    engine = EquationEngine()

    result = engine.calculate(
        equation,
        context,
    )

    assert result == 1200.0
