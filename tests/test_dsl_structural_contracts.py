"""
Correções estruturais da DSL (Fases C–G):

    C  referência espacial explícita a grupo (VAR@L1_L3)
    D  ln() por allowlist fechada
    E  valores categóricos (texto) tipados
    F  constantes de texto e and/or
    G  contrato da falha condicional "F"

Fixtures genéricas: IDs VAR9xxxx/PARAM9xxxx/EQ9xxxx, fora de qualquer
faixa produtiva.
"""

import ast
import math
from datetime import date

import pytest

from app.domain.equations.models import EquationDefinition
from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import AggregationRule
from app.domain.values import CONDITIONAL_FAILURE
from app.domain.variables.models import Variable, VariableDefinition
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import (
    AggregationFailureError,
    CalculationValueError,
    ConditionalFailureError,
    EquationEvaluationError,
    ExpressionTypeError,
    MathDomainError,
    NonNumericAggregationError,
    UnsafeExpressionError,
    VariableNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser
from app.engine.forecast_engine import ForecastEngine
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.validation import variable_seed_validator


@pytest.fixture
def parser():
    return ExpressionParser()


def _evaluate(expression, context, scope=(None, None), period_id=None):
    tree = ExpressionParser().parse(expression)
    return ExpressionEvaluator(
        context,
        default_scope_type=scope[0],
        default_scope_value=scope[1],
        default_period_id=period_id,
    ).evaluate(tree)


def _variable_definition(variable_id, scope_type, scope_value, value_type="numeric"):
    return VariableDefinition(
        variable_id, f"v_{variable_id}", "-", "-", "calculada",
        "diário", scope_type, scope_value, "test", "ativo",
        value_type,
    )


# ============================================================
# Fase C — @grupo
# ============================================================


@pytest.mark.parametrize("group", ["L1_L3", "L4_L5", "L6_L7", "L1_L7"])
def test_parser_accepts_explicit_group_reference(parser, group):
    tree = parser.parse(f"VAR90001@{group} * 2")

    assert tree.body.left.id == f"VAR90001__{group}"


def test_group_reference_is_not_a_matmul_operator(parser):
    tree = parser.parse("VAR90001@L1_L3 + PARAM90001@L4_L5")

    assert not any(isinstance(n, ast.MatMult) for n in ast.walk(tree))


@pytest.mark.parametrize(
    "expression",
    [
        "VAR90001@L1_L2",       # grupo inexistente no ScopeResolver
        "VAR90001@L3_L1",
        "VAR90001@L8",
        "VAR90001@PLANTA",
        "VAR90001 @ VAR90002",  # MatMult
        "VAR90001@",
        "VAR90001@@L1_L3",
    ],
)
def test_parser_rejects_invalid_scope_references(parser, expression):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(expression)


def test_extractor_returns_group_references_in_domain_form():
    dependencies = DependencyExtractor().extract(
        "VAR90001@L1_L3 + VAR90001@L4_L5 + PARAM90001@L6_L7 + VAR90002@L2"
    )

    assert dependencies.variables == frozenset(
        {"VAR90001@L1_L3", "VAR90001@L4_L5", "VAR90002@L2"}
    )
    assert dependencies.parameters == frozenset({"PARAM90001@L6_L7"})


def test_evaluator_resolves_group_reference_in_group_scope():
    context = CalculationContext()
    context.set_variable_value("VAR90001", 10.0, "linha_grupo", "L1_L3")
    context.set_variable_value("VAR90001", 20.0, "linha_grupo", "L4_L5")
    context.set_parameter_value("PARAM90001", 3.0, "linha_grupo", "L6_L7")

    assert _evaluate(
        "VAR90001@L1_L3 + VAR90001@L4_L5 + PARAM90001@L6_L7",
        context,
        scope=("planta", "PLANTA"),
    ) == 33.0


def test_group_reference_never_projects_to_another_scope():
    """Explícito é exato: sem valor no grupo, não usa linha nem planta."""

    context = CalculationContext()
    context.set_variable_value("VAR90001", 1.0, "linha", "L1")
    context.set_variable_value("VAR90001", 2.0, "planta", "PLANTA")

    with pytest.raises(VariableNotFoundError):
        _evaluate("VAR90001@L1_L3", context, scope=("linha", "L1"))


def test_group_reference_keeps_period_fallback():
    context = CalculationContext()
    context.set_variable_value(
        "VAR90001", 7.0, "linha_grupo", "L1_L3", period_id="2026-03"
    )

    assert _evaluate(
        "VAR90001@L1_L3", context, period_id="2026-03-05"
    ) == 7.0


def test_line_reference_still_resolves_as_line():
    context = CalculationContext()
    context.set_variable_value("VAR90001", 4.0, "linha", "L4")

    assert _evaluate("VAR90001@L4", context) == 4.0


def test_engine_orders_group_producers_before_explicit_consumer():
    """
    Uma equação de grupo por grupo (IDs distintos, como a A019 os
    resolve); uma equação de planta, registrada primeiro, consome as
    três pelo grupo explícito. O grafo precisa ordenar os produtores
    antes do consumidor (chave VAR@grupo).
    """

    registry = EquationDefinitionRegistry()
    registry.add(
        EquationDefinition(
            "EQ90013", "VAR90013", 1, "planta", "PLANTA",
            "VAR90010@L1_L3 + VAR90011@L4_L5 + VAR90012@L6_L7",
            "test", "PUBLISHED",
        )
    )
    for n, group in enumerate(["L1_L3", "L4_L5", "L6_L7"]):
        registry.add(
            EquationDefinition(
                f"EQ9001{n}", f"VAR9001{n}", 1, "linha_grupo", group,
                "PARAM90010 * 2", "test", "PUBLISHED",
            )
        )

    context = CalculationContext()
    context.set_parameter_value("PARAM90010", 1.0, "linha_grupo", "L1_L3")
    context.set_parameter_value("PARAM90010", 2.0, "linha_grupo", "L4_L5")
    context.set_parameter_value("PARAM90010", 3.0, "linha_grupo", "L6_L7")

    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=registry,
        calculation_context=context,
    )

    assert context.get_variable_value(
        "VAR90013", "planta", "PLANTA"
    ) == 12.0


# ============================================================
# Fase D — ln()
# ============================================================


def test_ln_of_one_is_zero():
    assert _evaluate("ln(1)", CalculationContext()) == 0.0


def test_ln_of_e_is_one():
    context = CalculationContext({"VAR90020": math.e})

    assert _evaluate("ln(VAR90020)", context) == pytest.approx(1.0)


def test_ln_composes_with_arithmetic():
    context = CalculationContext({"VAR90020": 100.0})

    assert _evaluate("2 * ln(VAR90020) / ln(10)", context) == pytest.approx(4.0)


@pytest.mark.parametrize("value", [0, 0.0, -1, -0.5])
def test_ln_outside_domain_is_explicit_error(value):
    context = CalculationContext({"VAR90020": value})

    with pytest.raises(MathDomainError):
        _evaluate("ln(VAR90020)", context)


def test_ln_of_text_literal_is_rejected_by_parser(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse('ln("texto")')


def test_ln_of_categorical_value_is_type_error():
    context = CalculationContext(categorical_variable_ids={"VAR90021"})
    context.set_variable("VAR90021", "texto")

    with pytest.raises(ExpressionTypeError):
        _evaluate("ln(VAR90021)", context)


def test_ln_of_conditional_failure_is_failure():
    context = CalculationContext({"VAR90020": CONDITIONAL_FAILURE})

    with pytest.raises(ConditionalFailureError):
        _evaluate("ln(VAR90020)", context)


@pytest.mark.parametrize(
    "expression",
    [
        "foo(VAR90001)",
        "abs(VAR90001)",
        "log(VAR90001)",
        "exp(VAR90001)",
        "os.system('ls')",
        "__import__('os')",
        "eval('1')",
        "exec('1')",
        "open('x')",
        "math.log(VAR90001)",
        "ln.__class__",
        "VAR90001.real",
        "ln(VAR90001).real",
        "ln",
        "ln(VAR90001, 10)",
        "ln()",
        "ln(x=VAR90001)",
        "ln(*VAR90001)",
        "[ln][0](VAR90001)",
        "VAR90001(1)",
        "(lambda x: x)(1)",
        "getattr(VAR90001, 'real')",
    ],
)
def test_function_allowlist_is_closed(parser, expression):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(expression)


def test_ln_argument_is_a_dependency_but_ln_is_not():
    dependencies = DependencyExtractor().extract("ln(VAR90001@L1_L3)")

    assert dependencies.variables == frozenset({"VAR90001@L1_L3"})
    assert dependencies.parameters == frozenset()


# ============================================================
# Fase E — valores categóricos
# ============================================================


def test_categorical_variable_accepts_text():
    context = CalculationContext(categorical_variable_ids={"VAR90030"})
    context.set_variable_value("VAR90030", "ABERTO", "linha", "L1")

    assert context.get_variable_value("VAR90030", "linha", "L1") == "ABERTO"


def test_numeric_variable_still_rejects_text():
    context = CalculationContext()

    with pytest.raises(CalculationValueError):
        context.set_variable_value("VAR90031", "ABERTO", "linha", "L1")

    with pytest.raises(CalculationValueError):
        CalculationContext({"VAR90031": "100"})


def test_categorical_variable_rejects_empty_text_and_bool():
    context = CalculationContext(categorical_variable_ids={"VAR90030"})

    with pytest.raises(CalculationValueError):
        context.set_variable("VAR90030", "  ")

    with pytest.raises(CalculationValueError):
        context.set_variable("VAR90030", True)


def test_parameters_remain_numeric_only():
    context = CalculationContext(categorical_variable_ids={"PARAM90030"})

    with pytest.raises(CalculationValueError):
        context.set_parameter("PARAM90030", "ABERTO")

    with pytest.raises(CalculationValueError):
        CalculationContext(parameters={"PARAM90030": "F"})


def test_value_type_is_declared_on_definition():
    assert _variable_definition("VAR90032", "linha", "L1").value_type == "numeric"

    definition = _variable_definition("VAR90032", "linha", "L1", "categorical")
    assert definition.is_categorical

    with pytest.raises(ValueError):
        _variable_definition("VAR90032", "linha", "L1", "texto")


def test_value_type_defaults_to_numeric_in_legacy_model():
    variable = Variable(
        "VAR90033", "v", "-", "-", "calculada", "diário",
        "linha", "L1", "test", "ativo",
    )

    assert VariableDefinition.from_variable(variable).value_type == "numeric"


def test_seed_validator_checks_value_type_enum():
    base = {
        "variable_id": "VAR90034", "_block": "test",
        "variable_type": "calculado", "frequency": "diário",
        "status": "ativo", "unit": "-", "scope_type": "linha",
        "scope_value": "L1",
    }

    assert variable_seed_validator.validate_enum_values([base]) == []
    assert variable_seed_validator.validate_enum_values(
        [{**base, "value_type": "categorical"}]
    ) == []
    assert variable_seed_validator.validate_enum_values(
        [{**base, "value_type": "texto"}]
    )


def test_engine_declares_categorical_variables_from_definitions():
    variables = VariableDefinitionRegistry()
    variables.add(_variable_definition("VAR90035", "linha", "L1", "categorical"))
    variables.add(_variable_definition("VAR90036", "linha", "L1"))

    equations = EquationDefinitionRegistry()
    equations.add(
        EquationDefinition(
            "EQ90035", "VAR90035", 1, "linha", "L1",
            '"ALTO" if VAR90036 > 10 else "BAIXO"', "test", "PUBLISHED",
        )
    )

    context = CalculationContext()
    context.set_variable_value("VAR90036", 11.0, "linha", "L1")

    ForecastEngine().calculate_from_definition_registry(
        equation_definition_registry=equations,
        calculation_context=context,
        variable_definition_registry=variables,
    )

    assert context.get_variable_value("VAR90035", "linha", "L1") == "ALTO"


def test_text_result_into_numeric_variable_is_rejected():
    variables = VariableDefinitionRegistry()
    variables.add(_variable_definition("VAR90037", "linha", "L1"))

    equations = EquationDefinitionRegistry()
    equations.add(
        EquationDefinition(
            "EQ90037", "VAR90037", 1, "linha", "L1",
            '"ALTO"', "test", "PUBLISHED",
        )
    )

    with pytest.raises(CalculationValueError):
        ForecastEngine().calculate_from_definition_registry(
            equation_definition_registry=equations,
            calculation_context=CalculationContext(),
            variable_definition_registry=variables,
        )


def test_categorical_values_are_not_aggregated():
    context = CalculationContext(categorical_variable_ids={"VAR90038"})
    context.set_variable_value("VAR90038", "A", "linha", "L1", "2026-03-01")

    rule = AggregationRule(
        "AGG90038", "VAR90038", "diário", "VAR90039", "mensal", "SUM"
    )

    with pytest.raises(NonNumericAggregationError):
        TemporalAggregationService().aggregate(
            rule, context, "linha", "L1", date(2026, 3, 1)
        )


# ============================================================
# Fase F — constantes de texto e and/or
# ============================================================


@pytest.fixture
def text_context():
    context = CalculationContext(
        {"VAR90040": 5.0, "VAR90041": 0.0},
        categorical_variable_ids={"VAR90042"},
    )
    context.set_variable("VAR90042", "ABERTO")
    return context


def test_text_equality(text_context):
    assert _evaluate('1 if VAR90042 == "ABERTO" else 2', text_context) == 1
    assert _evaluate('1 if VAR90042 != "ABERTO" else 2', text_context) == 2
    assert _evaluate('1 if "X" == "X" else 2', text_context) == 1


def test_text_constant_as_result(text_context):
    assert _evaluate('"OK" if VAR90040 > 1 else "NOK"', text_context) == "OK"
    assert _evaluate('"OK"', text_context) == "OK"


@pytest.mark.parametrize(
    "expression",
    [
        'VAR90040 + "1"',
        '"1" * 2',
        '-"1"',
        'VAR90040 if "A" else 1',
        'VAR90040 if VAR90040 > 0 and "A" else 1',
        'VAR90040 + "a" if VAR90040 > 0 else 1',
        "VAR90040 + 'a\\nb'",
        '"a\\"b"',
        '"' + "x" * 65 + '"',
        "b'bytes'",
        "f'{VAR90040}'",
        "None",
        "True",
        "...",
        "[1, 2]",
        "{'a': 1}",
        "VAR90040 in (1, 2)",
        "VAR90040 is 1",
        "not VAR90040",
    ],
)
def test_text_constants_and_other_literals_are_controlled(parser, expression):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(expression)


@pytest.mark.parametrize(
    "expression",
    [
        '1 if VAR90042 > "A" else 2',   # ordenação de texto
        '1 if VAR90042 == 1 else 2',    # texto x número
        '1 if VAR90040 == "5" else 2',  # número x texto
        '1 if VAR90042 else 2',         # texto como condição
        'VAR90042 + 1',                 # aritmética com texto
        '-VAR90042',
        "VAR90040 > 1",                 # resultado final booleano
    ],
)
def test_type_rules_are_explicit_errors(text_context, expression):
    with pytest.raises(ExpressionTypeError):
        _evaluate(expression, text_context)


def test_and_or_truth_table(text_context):
    cases = {
        "VAR90040 > 1 and VAR90041 == 0": 1,
        "VAR90040 > 1 and VAR90041 > 0": 2,
        "VAR90040 < 1 or VAR90041 == 0": 1,
        "VAR90040 < 1 or VAR90041 > 0": 2,
        'VAR90040 > 1 and VAR90042 == "ABERTO"': 1,
    }

    for condition, expected in cases.items():
        assert _evaluate(f"1 if {condition} else 2", text_context) == expected


def test_and_binds_tighter_than_or(text_context):
    # True or (False and False) -> True ; (True or False) and False -> False
    assert _evaluate(
        "1 if VAR90040 > 1 or VAR90041 > 0 and VAR90041 > 1 else 2",
        text_context,
    ) == 1
    assert _evaluate(
        "1 if (VAR90040 > 1 or VAR90041 > 0) and VAR90041 > 1 else 2",
        text_context,
    ) == 2


def test_and_or_short_circuit(text_context):
    # VAR99999 não existe: só seria lido se o curto-circuito falhasse.
    assert _evaluate(
        "1 if VAR90041 > 0 and VAR99999 > 0 else 2", text_context
    ) == 2
    assert _evaluate(
        "1 if VAR90040 > 0 or VAR99999 > 0 else 2", text_context
    ) == 1

    with pytest.raises(VariableNotFoundError):
        _evaluate("1 if VAR90040 > 0 and VAR99999 > 0 else 2", text_context)


def test_numeric_if_condition_keeps_legacy_semantics(text_context):
    assert _evaluate("1 if VAR90040 else 2", text_context) == 1
    assert _evaluate("1 if VAR90041 else 2", text_context) == 2


# ============================================================
# Fase G — falha condicional "F"
# ============================================================


@pytest.fixture
def failure_context():
    return CalculationContext(
        {"VAR90050": CONDITIONAL_FAILURE, "VAR90051": 3.0}
    )


def test_if_routine_can_produce_failure(failure_context):
    assert _evaluate(
        'VAR90051 if VAR90051 > 10 else "F"', failure_context
    ) == CONDITIONAL_FAILURE


def test_failure_passes_through_unchanged(failure_context):
    assert _evaluate("VAR90050", failure_context) == "F"
    assert _evaluate(
        "VAR90050 if VAR90051 > 0 else 0", failure_context
    ) == "F"


def test_failure_can_be_detected_explicitly(failure_context):
    assert _evaluate(
        '0 if VAR90050 == "F" else VAR90050', failure_context
    ) == 0
    assert _evaluate(
        '1 if VAR90050 != "F" else 0', failure_context
    ) == 0


def test_failure_check_on_numeric_value_is_well_defined(failure_context):
    # Um número nunca é a falha: `== "F"` é falso, sem erro de tipo.
    assert _evaluate('1 if VAR90051 != "F" else 0', failure_context) == 1
    assert _evaluate('1 if VAR90051 == "F" else 0', failure_context) == 0


def test_comparing_number_with_other_text_is_type_error(failure_context):
    with pytest.raises(ExpressionTypeError):
        _evaluate('1 if VAR90051 != "G" else 0', failure_context)


@pytest.mark.parametrize(
    "expression",
    [
        "VAR90050 + 1",
        "VAR90050 * 0",
        "-VAR90050",
        "ln(VAR90050)",
        "1 if VAR90050 > 0 else 2",
        "1 if VAR90050 == 0 else 2",
        "1 if VAR90050 else 2",
        "1 if VAR90051 > 0 and VAR90050 > 0 else 2",
    ],
)
def test_consuming_failure_is_explicit_failure(failure_context, expression):
    with pytest.raises(ConditionalFailureError):
        _evaluate(expression, failure_context)


def test_categorical_failure_is_not_silently_different():
    context = CalculationContext(categorical_variable_ids={"VAR90062"})
    context.set_variable("VAR90062", "F")

    with pytest.raises(ConditionalFailureError):
        _evaluate('1 if VAR90062 == "ABERTO" else 2', context)

    assert _evaluate('1 if VAR90062 == "F" else 2', context) == 1


def test_failure_is_stored_for_any_variable_without_conversion():
    context = CalculationContext()
    context.set_variable_value("VAR90052", "F", "linha", "L1", "2026-03-01")

    assert context.get_variable_value(
        "VAR90052", "linha", "L1", "2026-03-01"
    ) == "F"


def test_equation_engine_wraps_failure_with_equation_context():
    definition = EquationDefinition(
        "EQ90053", "VAR90053", 1, "linha", "L1",
        "VAR90050 * 2", "test", "PUBLISHED",
    )
    context = CalculationContext()
    context.set_variable_value("VAR90050", "F", "linha", "L1")

    from app.engine.scope_resolver import ScopeResolver

    (instance,) = ScopeResolver().resolve_equation(definition)

    with pytest.raises(EquationEvaluationError) as error:
        EquationEngine().calculate_instance(instance, definition, context)

    assert isinstance(error.value.original_error, ConditionalFailureError)


def test_failure_propagates_through_forecast_engine_as_value():
    """Uma equação cujo IF falha grava "F"; a consumidora falha."""

    equations = EquationDefinitionRegistry()
    equations.add(
        EquationDefinition(
            "EQ90054", "VAR90054", 1, "linha", "L1",
            'VAR90056 if VAR90056 > 0 else "F"', "test", "PUBLISHED",
        )
    )
    equations.add(
        EquationDefinition(
            "EQ90055", "VAR90055", 1, "linha", "L1",
            "VAR90054 + 1", "test", "PUBLISHED",
        )
    )

    context = CalculationContext()
    context.set_variable_value("VAR90056", -1.0, "linha", "L1")

    with pytest.raises(EquationEvaluationError) as error:
        ForecastEngine().calculate_from_definition_registry(
            equation_definition_registry=equations,
            calculation_context=context,
        )

    assert isinstance(error.value.original_error, ConditionalFailureError)
    assert context.get_variable_value("VAR90054", "linha", "L1") == "F"


@pytest.mark.parametrize("kind", ["SUM", "AVERAGE", "MOVING_AVERAGE"])
def test_aggregation_preserves_failure_explicitly(kind):
    context = CalculationContext()
    context.set_variable_value("VAR90057", 1.0, "linha", "L1", "2026-03-01")
    context.set_variable_value("VAR90057", "F", "linha", "L1", "2026-03-02")
    context.set_variable_value("VAR90057", 3.0, "linha", "L1", "2026-03-03")

    rule = AggregationRule(
        "AGG90057", "VAR90057", "diário", "VAR90058", "mensal", kind
    )

    with pytest.raises(AggregationFailureError) as error:
        TemporalAggregationService().aggregate(
            rule, context, "linha", "L1", date(2026, 3, 3)
        )

    assert error.value.failed_period_ids == ["2026-03-02"]


def test_weighted_average_with_failed_weight_fails():
    context = CalculationContext()
    for day, (value, weight) in enumerate([(1.0, 1.0), (2.0, "F")], start=1):
        period_id = f"2026-03-{day:02d}"
        context.set_variable_value("VAR90059", value, "linha", "L1", period_id)
        context.set_variable_value("VAR90060", weight, "linha", "L1", period_id)

    rule = AggregationRule(
        "AGG90059", "VAR90059", "diário", "VAR90061", "mensal",
        "WEIGHTED_AVERAGE", weight_variable_id="VAR90060",
    )

    with pytest.raises(AggregationFailureError):
        TemporalAggregationService().aggregate(
            rule, context, "linha", "L1", date(2026, 3, 2)
        )
