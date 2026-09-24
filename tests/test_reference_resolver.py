"""
A019 — resolução de referências por nome + frequência + escopo.

Fixtures genéricas (nomes x/y/p, IDs VAR9xxxx fora de qualquer faixa
produtiva): o contrato é da plataforma, não de um bloco.
"""

import pytest

from app.engine.reference_resolver import (
    ReferenceNotFoundError,
    ReferenceResolutionError,
    build_name_index,
    resolve_reference,
    translate_expression,
)


def _entity(entity_id, name, frequency, scope_type, scope_value, kind="variable", **extra):
    return {
        "entity_id": entity_id,
        "name": name,
        "kind": kind,
        "frequency": frequency,
        "scope_type": scope_type,
        "scope_value": scope_value,
        **extra,
    }


@pytest.fixture
def per_group_index():
    """Mesmo nome + mesma frequência, uma definição por grupo."""

    return build_name_index(
        [
            _entity("VAR90001", "x", "diário", "linha_grupo", "L1_L3"),
            _entity("VAR90002", "x", "diário", "linha_grupo", "L4_L5"),
            _entity("VAR90003", "x", "diário", "linha_grupo", "L6_L7"),
            _entity("VAR90004", "x", "mensal", "linha_grupo", "L1_L3"),
        ]
    )


@pytest.mark.parametrize(
    "consumer_scope,expected",
    [
        (("linha_grupo", "L1_L3"), "VAR90001"),
        (("linha_grupo", "L4_L5"), "VAR90002"),
        (("linha_grupo", "L6_L7"), "VAR90003"),
        (("linha", "L1"), "VAR90001"),
        (("linha", "L2"), "VAR90001"),
        (("linha", "L5"), "VAR90002"),
        (("linha", "L7"), "VAR90003"),
    ],
)
def test_implicit_reference_binds_by_consumer_scope(
    per_group_index, consumer_scope, expected
):
    assert (
        resolve_reference(
            "x", per_group_index, "diário", consumer_scope=consumer_scope
        )
        == expected
    )


def test_frequency_still_filters_before_scope(per_group_index):
    assert (
        resolve_reference(
            "x", per_group_index, "mensal", consumer_scope=("linha", "L4")
        )
        == "VAR90004"
    )


def test_per_line_definitions_bind_to_same_line():
    index = build_name_index(
        [
            _entity("VAR90011", "y", "diário", "linha", "L1"),
            _entity("VAR90012", "y", "diário", "linha", "L2"),
        ]
    )

    assert resolve_reference("y", index, "diário", consumer_scope=("linha", "L1")) == "VAR90011"
    assert resolve_reference("y", index, "diário", consumer_scope=("linha", "L2")) == "VAR90012"


def test_consumer_spanning_several_bindings_is_an_explicit_error(per_group_index):
    """
    Uma definição linha/L1_L7 materializa 7 instâncias; cada uma
    enxergaria um grupo diferente. Uma expressão grava um único ID,
    então isso é ambiguidade estrutural — nunca escolha silenciosa.
    """

    with pytest.raises(ReferenceResolutionError, match="definições diferentes"):
        resolve_reference(
            "x", per_group_index, "diário", consumer_scope=("linha", "L1_L7")
        )


@pytest.mark.parametrize(
    "scope,expected",
    [("L1_L3", "VAR90001"), ("L4_L5", "VAR90002"), ("L6_L7", "VAR90003")],
)
def test_explicit_group_scope_is_part_of_identity(per_group_index, scope, expected):
    assert (
        resolve_reference(
            "x",
            per_group_index,
            "diário",
            consumer_scope=("linha", "L1_L7"),
            explicit_scope_value=scope,
        )
        == expected
    )


def test_explicit_scope_without_matching_definition_is_an_error(per_group_index):
    with pytest.raises(ReferenceResolutionError, match="nenhuma definição"):
        resolve_reference(
            "x", per_group_index, "diário", explicit_scope_value="L1_L7"
        )


def test_explicit_line_scope_matches_line_expansion():
    index = build_name_index(
        [_entity("VAR90021", "z", "diário", "linha", "L1_L7")]
    )

    assert (
        resolve_reference("z", index, "diário", explicit_scope_value="L4")
        == "VAR90021"
    )


def test_missing_scope_keeps_ambiguity_explicit(per_group_index):
    with pytest.raises(ReferenceResolutionError, match="ambígua"):
        resolve_reference("x", per_group_index, "diário")


def test_same_scope_duplicates_are_ambiguous_without_tie_breaker():
    index = build_name_index(
        [
            _entity("VAR90031", "w", "mensal", "linha_grupo", "L1_L7", dsl=("SUM",)),
            _entity("VAR90032", "w", "mensal", "linha_grupo", "L1_L7", dsl=("AVERAGE",)),
        ]
    )

    with pytest.raises(ReferenceResolutionError):
        resolve_reference("w", index, "mensal", consumer_scope=("linha_grupo", "L1_L7"))

    chosen = resolve_reference(
        "w",
        index,
        "mensal",
        consumer_scope=("linha_grupo", "L1_L7"),
        tie_breaker=lambda pool: next(c for c in pool if c["dsl"][0] == "SUM"),
    )

    assert chosen == "VAR90031"


def test_unknown_name_is_not_found():
    with pytest.raises(ReferenceNotFoundError):
        resolve_reference("nope", {}, "diário")

    with pytest.raises(KeyError):
        resolve_reference("nope", {}, "diário")


def test_parameters_are_also_scope_aware():
    index = build_name_index(
        [
            _entity("PARAM90001", "p", None, "linha_grupo", "L1_L3", kind="parameter"),
            _entity("PARAM90002", "p", None, "linha_grupo", "L4_L5", kind="parameter"),
        ]
    )

    assert (
        resolve_reference("p", index, "diário", consumer_scope=("linha", "L4"))
        == "PARAM90002"
    )


def test_monthly_input_resolves_for_daily_consumer():
    index = build_name_index(
        [_entity("VAR90041", "m", "mensal", "linha_grupo", "L1_L3")]
    )

    assert (
        resolve_reference("m", index, "diário", consumer_scope=("linha_grupo", "L1_L3"))
        == "VAR90041"
    )


def test_translate_preserves_and_uses_explicit_scope(per_group_index):
    translated = translate_expression(
        "x@L1_L3 + x@L4_L5 + x@L6_L7",
        per_group_index,
        "diário",
        consumer_scope=("linha_grupo", "L1_L7"),
    )

    assert translated == "VAR90001@L1_L3 + VAR90002@L4_L5 + VAR90003@L6_L7"


def test_translate_binds_implicit_reference_per_consumer(per_group_index):
    assert (
        translate_expression(
            "x * 2", per_group_index, "diário", consumer_scope=("linha", "L5")
        )
        == "VAR90002 * 2"
    )


def test_translate_preserves_text_constants(per_group_index):
    assert (
        translate_expression(
            '"x" if x > 0 else \'x  F\'',
            per_group_index,
            "diário",
            consumer_scope=("linha", "L5"),
        )
        == '"x" if VAR90002 > 0 else \'x  F\''
    )
