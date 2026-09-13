import pytest

from app.domain.equations.models import (
    EquationDefinition,
)
from app.domain.parameters.models import (
    ParameterDefinition,
)
from app.domain.variables.models import (
    VariableDefinition,
)
from app.engine.scope_resolver import ScopeResolver


@pytest.fixture
def resolver():
    return ScopeResolver()


def make_variable_definition(
    scope_type="linha",
    scope_value="L1_L7",
):
    return VariableDefinition(
        variable_definition_id="yield",
        variable_name="yield",
        description="Yield",
        unit="%",
        variable_type="calculado",
        frequency="diário",
        scope_type=scope_type,
        scope_value=scope_value,
        source_reference="test",
        status="ativo",
    )


def make_parameter_definition(
    scope_type="linha",
    scope_value="L1_L7",
):
    return ParameterDefinition(
        parameter_definition_id="ltp",
        parameter_name="ltp",
        description="LTP",
        unit="t",
        value=1.0,
        version=1,
        scope_type=scope_type,
        scope_value=scope_value,
        source_reference="test",
        status="ativo",
    )


def make_equation_definition(
    scope_type="linha",
    scope_value="L1_L7",
):
    return EquationDefinition(
        equation_definition_id="yield_daily",
        target_variable_id="yield",
        version=1,
        scope_type=scope_type,
        scope_value=scope_value,
        expression="ltp - ratio_spent",
        source_reference="test",
        status="ativo",
    )


def test_resolve_line_range_l1_l7(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha",
        scope_value="L1_L7",
    )

    assert result == [
        ("linha", "L1"),
        ("linha", "L2"),
        ("linha", "L3"),
        ("linha", "L4"),
        ("linha", "L5"),
        ("linha", "L6"),
        ("linha", "L7"),
    ]


def test_resolve_line_range_l1_l3(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha",
        scope_value="L1_L3",
    )

    assert result == [
        ("linha", "L1"),
        ("linha", "L2"),
        ("linha", "L3"),
    ]


def test_resolve_line_group_l1_l3(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    assert result == [
        ("linha_grupo", "L1_L3"),
    ]


def test_resolve_line_group_l4_l5(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha_grupo",
        scope_value="L4_L5",
    )

    assert result == [
        ("linha_grupo", "L4_L5"),
    ]


def test_resolve_line_group_l6_l7(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha_grupo",
        scope_value="L6_L7",
    )

    assert result == [
        ("linha_grupo", "L6_L7"),
    ]


def test_resolve_plant(resolver):
    result = resolver.resolve_scopes(
        scope_type="planta",
        scope_value="PLANTA",
    )

    assert result == [
        ("planta", "PLANTA"),
    ]


def test_resolve_variable_definition_to_seven_instances(
    resolver,
):
    definition = make_variable_definition()

    instances = resolver.resolve_variable(definition)

    assert len(instances) == 7

    assert [
        instance.variable_instance_id
        for instance in instances
    ] == [
        "yield@L1",
        "yield@L2",
        "yield@L3",
        "yield@L4",
        "yield@L5",
        "yield@L6",
        "yield@L7",
    ]


def test_resolve_variable_group_definition(
    resolver,
):
    definition = make_variable_definition(
        scope_type="linha_grupo",
        scope_value="L1_L3",
    )

    instances = resolver.resolve_variable(definition)

    assert len(instances) == 1

    assert instances[0].variable_instance_id == (
        "yield@L1_L3"
    )


def test_resolve_parameter_definition_to_seven_instances(
    resolver,
):
    definition = make_parameter_definition()

    instances = resolver.resolve_parameter(definition)

    assert len(instances) == 7

    assert [
        instance.parameter_instance_id
        for instance in instances
    ] == [
        "ltp@v1@L1",
        "ltp@v1@L2",
        "ltp@v1@L3",
        "ltp@v1@L4",
        "ltp@v1@L5",
        "ltp@v1@L6",
        "ltp@v1@L7",
    ]


def test_parameter_instances_preserve_definition_data(
    resolver,
):
    definition = make_parameter_definition()

    instances = resolver.resolve_parameter(definition)

    assert len(instances) == 7

    for instance in instances:
        assert instance.parameter_definition_id == (
            definition.parameter_definition_id
        )
        assert instance.version == definition.version
        assert instance.value == definition.value
        assert instance.scope_type == "linha"


def test_resolve_equation_definition_to_seven_instances(
    resolver,
):
    definition = make_equation_definition()

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 7

    assert [
        instance.equation_instance_id
        for instance in instances
    ] == [
        "yield_daily@v1@L1",
        "yield_daily@v1@L2",
        "yield_daily@v1@L3",
        "yield_daily@v1@L4",
        "yield_daily@v1@L5",
        "yield_daily@v1@L6",
        "yield_daily@v1@L7",
    ]


def test_equation_instances_preserve_definition_data(
    resolver,
):
    definition = make_equation_definition()

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 7

    for instance in instances:
        assert instance.equation_definition_id == (
            definition.equation_definition_id
        )
        assert instance.target_variable_id == (
            definition.target_variable_id
        )
        assert instance.version == definition.version
        assert instance.scope_type == "linha"


def test_equation_instance_does_not_duplicate_expression(
    resolver,
):
    definition = make_equation_definition(
        scope_type="linha",
        scope_value="L1",
    )

    instances = resolver.resolve_equation(definition)

    assert len(instances) == 1

    instance = instances[0]

    assert not hasattr(instance, "expression")

    assert definition.expression == (
        "ltp - ratio_spent"
    )


def test_missing_scope_type_raises_error(resolver):
    with pytest.raises(
        ValueError,
        match="scope_type is required",
    ):
        resolver.resolve_scopes(
            scope_type=None,
            scope_value="L1",
        )


def test_missing_scope_value_raises_error(resolver):
    with pytest.raises(
        ValueError,
        match="scope_value is required",
    ):
        resolver.resolve_scopes(
            scope_type="linha",
            scope_value=None,
        )


def test_invalid_scope_type_raises_error(resolver):
    with pytest.raises(
        ValueError,
        match="Unsupported scope_type",
    ):
        resolver.resolve_scopes(
            scope_type="inexistente",
            scope_value="L1",
        )


def test_invalid_line_scope_raises_error(resolver):
    with pytest.raises(
        ValueError,
        match="Invalid line range",
    ):
        resolver.resolve_scopes(
            scope_type="linha",
            scope_value="L8",
        )


def test_resolve_line_group_l1_l7(resolver):
    result = resolver.resolve_scopes(
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    assert result == [
        ("linha_grupo", "L1_L7"),
    ]


def test_invalid_plant_scope_raises_error(resolver):
    with pytest.raises(
        ValueError,
        match="Invalid plant scope_value",
    ):
        resolver.resolve_scopes(
            scope_type="planta",
            scope_value="L1",
        )


def test_l1_l7_has_different_behavior_for_line_and_line_group(
    resolver,
):
    line_result = resolver.resolve_scopes(
        scope_type="linha",
        scope_value="L1_L7",
    )

    group_result = resolver.resolve_scopes(
        scope_type="linha_grupo",
        scope_value="L1_L7",
    )

    assert line_result == [
        ("linha", "L1"),
        ("linha", "L2"),
        ("linha", "L3"),
        ("linha", "L4"),
        ("linha", "L5"),
        ("linha", "L6"),
        ("linha", "L7"),
    ]

    assert group_result == [
        ("linha_grupo", "L1_L7"),
    ]
