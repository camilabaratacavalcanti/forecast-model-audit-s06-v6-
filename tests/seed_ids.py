"""
Localiza entidades dos seeds pela identidade contratual
(name + frequency + scope_type + scope_value), nunca por um ID fixo.

Os IDs são atribuídos pelo builder na ordem das linhas do workbook
aprovado; os testes que exercitam o seed real devem sobreviver a uma
regeneração que preserve a identidade.
"""

import json
from functools import lru_cache
from pathlib import Path

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"


@lru_cache(maxsize=None)
def _load(block: str, name: str):
    return json.loads(
        (SEED_ROOT / block / f"{name}.json").read_text(encoding="utf-8")
    )


def _single(matches, description):
    ids = sorted(set(matches))

    if len(ids) != 1:
        raise LookupError(f"{description}: {len(ids)} correspondências {ids}")

    return ids[0]


def variable_id(block, name, frequency, scope_type="linha", scope_value="L1_L7"):
    return _single(
        [
            v["variable_id"]
            for v in _load(block, "variables")
            if v["variable_name"] == name
            and v["frequency"] == frequency
            and v["scope_type"] == scope_type
            and v["scope_value"] == scope_value
        ],
        f"{block}: variável {name} {frequency} {scope_type}/{scope_value}",
    )


def parameter_id(block, name):
    return _single(
        [
            p["parameter_id"]
            for p in _load(block, "parameters")
            if p["parameter_name"] == name
        ],
        f"{block}: parâmetro {name}",
    )


def equation(block, target_variable_id, scope_value=None):
    matches = [
        e
        for e in _load(block, "equations")
        if e["target_variable_id"] == target_variable_id
        and (scope_value is None or e["scope_value"] == scope_value)
    ]

    if len(matches) != 1:
        raise LookupError(
            f"{block}: {len(matches)} equações para {target_variable_id} "
            f"{scope_value or ''}"
        )

    return matches[0]


def aggregation_rule(block, target_variable_id):
    matches = [
        r
        for r in _load(block, "aggregation_rules")
        if r["target_variable_id"] == target_variable_id
    ]

    if len(matches) != 1:
        raise LookupError(
            f"{block}: {len(matches)} regras para {target_variable_id}"
        )

    return matches[0]
