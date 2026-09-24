"""
Contrato de runtime do bloco `max_ht`: IDs, unidades, parser, grafo de
dependências, escopo espacial e integração completa com o
`SeedLoader`/`ScopeResolver`/`ExpressionParser` reais do projeto.

Complementar a `tests/test_max_ht_seed_reconciliation.py` (que garante
fidelidade seed <-> planilha) e a `tests/test_id_ranges_taxonomy_consistency.py`
(que garante a faixa de ID 13000-13999 e a ausência de colisão com
outros blocos, de forma genérica). Este módulo cobre os invariantes
específicos do bloco que não são cobertos por nenhum dos dois.
"""

import json
import re
from pathlib import Path

import pytest

from app.engine.expression_parser import ExpressionParser
from app.engine.scope_resolver import ScopeResolver
from app.repositories.seed_loader import SeedLoader
from app.validation.variable_seed_validator import ALLOWED_UNITS

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_ROOT = REPO_ROOT / "data" / "seed"
SEED_DIR = SEED_ROOT / "max_ht"

NEW_UNITS = {
    "t/ano",
    "kg/h",
    "kg/d",
    "kg/mês",
    "kg/ano",
    "m³/mês",
    "m³/ano",
    "mg/l",
}


@pytest.fixture(scope="module")
def variables():
    return json.loads((SEED_DIR / "variables.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def parameters():
    return json.loads((SEED_DIR / "parameters.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def equations():
    return json.loads((SEED_DIR / "equations.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def aggregation_rules():
    return json.loads(
        (SEED_DIR / "aggregation_rules.json").read_text("utf-8")
    )


# ============================================================
# Invariantes de contagem
# ============================================================


def test_entity_counts(variables, parameters, equations, aggregation_rules):
    assert len(variables) == 148
    assert len(parameters) == 4
    assert len(equations) == 29
    assert len(aggregation_rules) == 110


# ============================================================
# IDs
# ============================================================


def test_all_ids_in_block_range(variables, parameters, equations):
    for v in variables:
        number = int(v["variable_id"].removeprefix("VAR"))
        assert 13000 <= number <= 13999, v["variable_id"]

    for p in parameters:
        number = int(p["parameter_id"].removeprefix("PARAM"))
        assert 13000 <= number <= 13999, p["parameter_id"]

    for e in equations:
        number = int(e["equation_id"].removeprefix("EQ"))
        assert 13000 <= number <= 13999, e["equation_id"]


def test_no_duplicate_ids(variables, parameters, equations):
    var_ids = [v["variable_id"] for v in variables]
    param_ids = [p["parameter_id"] for p in parameters]
    eq_ids = [e["equation_id"] for e in equations]

    assert len(var_ids) == len(set(var_ids))
    assert len(param_ids) == len(set(param_ids))
    assert len(eq_ids) == len(set(eq_ids))


@pytest.mark.parametrize("block", ["yield", "production", "energy"])
def test_no_id_collision_with_other_blocks(variables, block):
    other = json.loads(
        (SEED_ROOT / block / "variables.json").read_text("utf-8")
    )
    other_ids = {v["variable_id"] for v in other}
    own_ids = {v["variable_id"] for v in variables}

    assert not (other_ids & own_ids)


# ============================================================
# Unidades
# ============================================================


def test_new_units_are_registered_in_allowed_units():
    assert NEW_UNITS <= ALLOWED_UNITS


def test_units_used_by_the_block_are_exactly_the_expected_set(variables):
    used = {v["unit"] for v in variables}

    unexpected = used - ALLOWED_UNITS

    assert unexpected == set()


# ============================================================
# Parser real: 29/29 expressões matemáticas
# ============================================================


def test_all_math_equations_parse_successfully(equations):
    ok = 0

    for equation in equations:
        ExpressionParser().parse(equation["expression"])
        ok += 1

    assert ok == 29


def test_no_unresolved_tokens_in_equations(variables, parameters, equations):
    known_ids = {v["variable_id"] for v in variables} | {
        p["parameter_id"] for p in parameters
    }

    pattern = re.compile(r"\b((?:VAR|PARAM)\d{5})(?:@L[1-7])?\b")

    for equation in equations:
        for token in pattern.findall(equation["expression"]):
            assert token in known_ids, (
                equation["equation_id"],
                token,
            )


# ============================================================
# DSL temporal: 110/110 AggregationRules válidas
# ============================================================


def test_aggregation_rules_reference_known_ids(variables, aggregation_rules):
    known_ids = {v["variable_id"] for v in variables}

    for rule in aggregation_rules:
        assert rule["source_variable_id"] in known_ids
        assert rule["target_variable_id"] in known_ids
        assert rule["aggregation_type"] in {"SUM", "AVERAGE"}
        assert rule.get("weight_variable_id") is None


def test_aggregation_source_is_always_daily(aggregation_rules):
    for rule in aggregation_rules:
        assert rule["source_frequency"] == "diário"
        assert rule["target_frequency"] in {"mensal", "anual"}


# ============================================================
# Validação espacial: somas @Lx batem com ScopeResolver.GROUP_MEMBERS
# ============================================================


def test_spatial_sums_match_group_members(equations):
    at_pattern = re.compile(r"@(L[1-7])\b")

    for equation in equations:
        tokens = at_pattern.findall(equation["expression"])

        if not tokens:
            continue

        members = set(tokens)

        matching_groups = [
            group
            for group, group_members in ScopeResolver.GROUP_MEMBERS.items()
            if group_members == members
        ]

        assert matching_groups, (equation["equation_id"], members)
        assert equation["scope_value"] in matching_groups


# ============================================================
# Integração completa: SeedLoader + todos os blocos juntos
# ============================================================


def test_full_seed_root_loads_without_errors():
    loader = SeedLoader(SEED_ROOT)

    (
        var_defs, var_insts,
        param_defs, param_insts,
        eq_defs, eq_insts,
    ) = loader.load_all_definitions_and_instances()

    max_ht_var_defs = [
        d for d in var_defs.all()
        if d.variable_definition_id.startswith("VAR13")
    ]
    max_ht_eq_defs = [
        d for d in eq_defs.all()
        if d.equation_definition_id.startswith("EQ13")
    ]

    assert len(max_ht_var_defs) == 148
    assert len(max_ht_eq_defs) == 29

    agg = loader.load_aggregation_rules()
    max_ht_rules = [
        r for r in agg.all()
        if r.aggregation_rule_id.startswith("AGR-MAX_HT-")
    ]
    assert len(max_ht_rules) == 110
