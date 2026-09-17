import pytest

from app.engine.exceptions import AmbiguousSpatialPrecedenceError
from app.engine.scope_resolver import ScopeResolver
from app.engine.spatial_candidate_resolver import (
    get_spatial_candidates,
)


# ============================================================
# Decision C — Projection
# ============================================================


def test_c_t01_planta_can_generate_candidate_for_a_line():
    """C-T01: planta/PLANTA pode gerar candidato para uma linha
    específica (via linha/L4 -> ... -> planta/PLANTA)."""

    candidates = get_spatial_candidates("linha", "L4")

    assert ("planta", "PLANTA") in candidates


def test_c_t02_planta_projects_to_group():
    """C-T02: planta/PLANTA -> linha_grupo/L1_L7."""

    candidates = get_spatial_candidates("linha_grupo", "L1_L7")

    assert candidates == [
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_c_t03_group_projects_to_line():
    """C-T03: linha_grupo/L1_L7 -> linha/L4 (L4 encontra L1_L7 como
    candidato ao subir na hierarquia)."""

    candidates = get_spatial_candidates("linha", "L4")

    assert ("linha_grupo", "L1_L7") in candidates


def test_c_t04_inverse_projection_is_forbidden():
    """C-T04: linha/L4 não projeta para linha_grupo/L4_L5 nem para
    planta/PLANTA como se fossem escopos MAIS ESPECÍFICOS do que
    linha/L4 — a direção da projeção é sempre para cima na
    hierarquia (linha -> grupo -> planta), nunca o inverso.

    Como consumidor de linha_grupo/L4_L5, linha/L4 não deve aparecer
    como candidato: um grupo não se expande implicitamente em linhas.
    """

    candidates = get_spatial_candidates("linha_grupo", "L4_L5")

    assert ("linha", "L4") not in candidates
    assert ("linha", "L5") not in candidates


def test_c_t05_group_does_not_expand_into_lines():
    """C-T05: linha_grupo/L1_L3 não produz implicitamente
    linha/L1, linha/L2, linha/L3 como candidatos."""

    candidates = get_spatial_candidates("linha_grupo", "L1_L3")

    assert ("linha", "L1") not in candidates
    assert ("linha", "L2") not in candidates
    assert ("linha", "L3") not in candidates

    assert candidates == [
        ("linha_grupo", "L1_L3"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_c_t06_plant_consumer_has_only_itself_as_candidate():
    """C-T06: planta/PLANTA possui somente ela própria como
    candidato."""

    candidates = get_spatial_candidates("planta", "PLANTA")

    assert candidates == [("planta", "PLANTA")]


def test_c_t07_no_aggregation_only_scopes_are_returned():
    """C-T07: o resolver retorna apenas tuplas (scope_type,
    scope_value) — nunca um valor numérico agregado. A camada não
    tem acesso a nenhum valor (não recebe, não importa e não
    consulta CalculationContext/Registry)."""

    candidates = get_spatial_candidates("linha_grupo", "L1_L3")

    for candidate in candidates:
        assert isinstance(candidate, tuple)
        assert len(candidate) == 2
        assert isinstance(candidate[0], str)
        assert isinstance(candidate[1], str)

    import app.engine.spatial_candidate_resolver as module

    assert not hasattr(module, "CalculationContext")
    assert not hasattr(module, "VariableInstanceRegistry")
    assert not hasattr(module, "ParameterInstanceRegistry")


# ============================================================
# Decision D — Precedence
# ============================================================


def test_d_t01_line_exact_precedes_groups():
    """D-T01: linha/L4 vem antes de qualquer grupo."""

    candidates = get_spatial_candidates("linha", "L4")

    assert candidates[0] == ("linha", "L4")


def test_d_t02_specific_group_precedes_broad_group():
    """D-T02: linha_grupo/L4_L5 vem antes de linha_grupo/L1_L7."""

    candidates = get_spatial_candidates("linha", "L4")

    specific_index = candidates.index(("linha_grupo", "L4_L5"))
    broad_index = candidates.index(("linha_grupo", "L1_L7"))

    assert specific_index < broad_index


def test_d_t03_group_inclusion_defines_precedence():
    """D-T03: a precedência é definida por members(G1) ⊂ members(G2),
    e não pelo número de membros. Cenário controlado com um grupo
    injetado de tamanho maior mas que NÃO é superset do consumidor
    não deve aparecer antes de um grupo que efetivamente o contém."""

    custom_group_members = {
        "L4_L5": frozenset({"L4", "L5"}),
        "L1_L7": frozenset(
            {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}
        ),
        "OUTRO_MAIOR_MAS_NAO_SUPERSET": frozenset(
            {"L1", "L2", "L3", "L6", "L7"}
        ),
    }

    candidates = get_spatial_candidates(
        "linha",
        "L4",
        group_members=custom_group_members,
    )

    assert candidates == [
        ("linha", "L4"),
        ("linha_grupo", "L4_L5"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_d_t04_l1_precedence():
    """D-T04: linha/L1, linha_grupo/L1_L3, linha_grupo/L1_L7,
    planta/PLANTA, nesta ordem."""

    candidates = get_spatial_candidates("linha", "L1")

    assert candidates == [
        ("linha", "L1"),
        ("linha_grupo", "L1_L3"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_d_t05_l6_and_l7_precedence():
    """D-T05: linha/L6 e linha/L7 seguem
    linha/Lx, linha_grupo/L6_L7, linha_grupo/L1_L7, planta/PLANTA."""

    candidates_l6 = get_spatial_candidates("linha", "L6")

    assert candidates_l6 == [
        ("linha", "L6"),
        ("linha_grupo", "L6_L7"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]

    candidates_l7 = get_spatial_candidates("linha", "L7")

    assert candidates_l7 == [
        ("linha", "L7"),
        ("linha_grupo", "L6_L7"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_d_t06_group_consumer_precedence():
    """D-T06: linha_grupo/L1_L3, linha_grupo/L1_L7, planta/PLANTA."""

    candidates = get_spatial_candidates("linha_grupo", "L1_L3")

    assert candidates == [
        ("linha_grupo", "L1_L3"),
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]


def test_d_t07_incomparable_groups_raise_explicit_ambiguity():
    """D-T07: grupos incomparáveis (nem G1 ⊂ G2, nem G2 ⊂ G1) não são
    silenciosamente escolhidos — o comportamento é uma exceção
    explícita, e o resultado não depende de ordem de inserção."""

    g1_first = {
        "G1": frozenset({"L1", "L2", "L3"}),
        "G2": frozenset({"L2", "L3", "L4"}),
    }

    g2_first = {
        "G2": frozenset({"L2", "L3", "L4"}),
        "G1": frozenset({"L1", "L2", "L3"}),
    }

    with pytest.raises(AmbiguousSpatialPrecedenceError):
        get_spatial_candidates(
            "linha",
            "L2",
            group_members=g1_first,
        )

    with pytest.raises(AmbiguousSpatialPrecedenceError):
        get_spatial_candidates(
            "linha",
            "L2",
            group_members=g2_first,
        )


def test_d_t08_deterministic_result():
    """D-T08: a mesma resolução, executada repetidamente, produz
    resultado idêntico."""

    results = [
        get_spatial_candidates("linha", "L4")
        for _ in range(5)
    ]

    assert all(result == results[0] for result in results)


def test_d_t09_plant_last_for_line_consumer():
    """D-T09: para uma linha, planta/PLANTA fica depois dos
    candidatos de linha/grupo."""

    candidates = get_spatial_candidates("linha", "L4")

    assert candidates[-1] == ("planta", "PLANTA")


# ============================================================
# Contrato de pureza / isolamento arquitetural
# ============================================================


def test_default_group_members_is_scope_resolver_source_of_truth():
    """O componente usa ScopeResolver.GROUP_MEMBERS por padrão —
    não duplica a composição dos grupos."""

    candidates = get_spatial_candidates("linha_grupo", "L1_L7")

    assert candidates == [
        ("linha_grupo", "L1_L7"),
        ("planta", "PLANTA"),
    ]

    assert ScopeResolver.GROUP_MEMBERS["L1_L7"] == frozenset(
        {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}
    )


def test_invalid_scope_type_raises_error():
    with pytest.raises(
        ValueError,
        match="Unsupported scope_type",
    ):
        get_spatial_candidates("área", None)


def test_invalid_line_scope_value_raises_error():
    with pytest.raises(ValueError, match="Invalid line scope_value"):
        get_spatial_candidates("linha", "L8")


def test_invalid_group_scope_value_raises_error():
    with pytest.raises(ValueError, match="Unknown line group"):
        get_spatial_candidates("linha_grupo", "L4_L6")


def test_invalid_plant_scope_value_raises_error():
    with pytest.raises(ValueError, match="Invalid plant scope_value"):
        get_spatial_candidates("planta", "GLOBAL")
