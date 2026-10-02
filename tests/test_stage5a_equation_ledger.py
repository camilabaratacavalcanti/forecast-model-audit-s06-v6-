"""
Stage 5A — livro de IDs de equação (D-5A-4), unidades novas (D-5A-1).

Provam:
    * todo EQ dos seeds está no livro do bloco com a identidade (variável alvo + escopo da instância);
    * invariantes S estendidos a EQ, ao vivo contra B0 (`e262e03`): mesma identidade => mesmo ID;
      identidade que saiu => EQ em `retired_equations`; EQ novo => número nunca emitido nem aposentado;
    * o build é determinístico com o livro e, sem a seção de equações, reproduz a numeração sequencial;
    * o livro rejeita EQ duplicado e EQ ativo e aposentado ao mesmo tempo;
    * as 5 unidades da D-5A-1 são aceitas pelos validadores de variáveis e de parâmetros.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess

import pytest

from app.validation import parameter_seed_validator, variable_seed_validator
from tools.workbook_seed.blocks import BLOCKS, ID_LEDGER_ROOT, REPO_ROOT, SEED_ROOT, build_block
from tools.workbook_seed.canonical import build_canonical_model
from tools.workbook_seed.id_ledger import (
    EQUATION_KEY_FIELDS,
    KEY_FIELDS,
    IdLedger,
    IdLedgerError,
    equation_key,
    ledger_payload,
    load_ledger,
)
from tools.workbook_seed.reader import read_workbook
from tools.workbook_seed.seeds import build_equations

B0 = "e262e03"           # main com 4B + 4C (current = B0); referência dos invariantes S de EQ
NEW_UNITS = ("kWh/tv", "tv/MWh", "tv/t carvão", "GJ/d", "m³/d")


def seed(block, name, commit=None):
    if commit is None:
        return json.loads((SEED_ROOT / block / f"{name}.json").read_text(encoding="utf-8"))
    raw = subprocess.check_output(["git", "show", f"{commit}:data/seed/{block}/{name}.json"], cwd=REPO_ROOT)
    return json.loads(raw)


def equation_identities(block, commit=None):
    """equation_id -> identidade da equação, pelos seeds e pelo manifesto do commit."""
    entities = {e["entity_id"]: tuple(e[f] for f in KEY_FIELDS) for e in seed(block, "manifest", commit)["entities"]}
    return {e["equation_id"]: equation_key(entities[e["target_variable_id"]], e["scope_value"])
            for e in seed(block, "equations", commit)}


# ------------------------------------------------------------ livro x seeds

@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_every_seed_equation_is_in_the_ledger_with_its_identity(block):
    ledger = load_ledger(ID_LEDGER_ROOT / f"{block}.json")
    assert ledger.equations is not None, "livro sem a seção de equações"
    current = equation_identities(block)
    assert {equation_id: key for key, equation_id in ledger.equations.items()} == current
    ids = [e["equation_id"] for e in seed(block, "equations")]
    assert ids == sorted(ids, key=lambda i: int(i[2:]))                 # DR-5A-1: ordem crescente de EQ


@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_equation_ids_are_never_renumbered_retired_or_reused_since_b0(block):
    before, after = equation_identities(block, B0), equation_identities(block)
    ledger = load_ledger(ID_LEDGER_ROOT / f"{block}.json")
    retired = {r["equation_id"]: equation_key(tuple(r[f] for f in KEY_FIELDS), r["equation_scope_value"])
               for r in ledger.retired_equations}
    by_key_before = {key: equation_id for equation_id, key in before.items()}
    for equation_id, key in after.items():
        if key in by_key_before:
            assert by_key_before[key] == equation_id, (block, key, "EQ renumerado")
        else:
            assert equation_id not in before and equation_id not in retired, (block, equation_id, "EQ reutilizado")
    current_keys = set(after.values())
    for equation_id, key in before.items():
        if key not in current_keys:
            assert retired.get(equation_id) == key, (block, equation_id, "saiu sem aposentar")


@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_ledger_payload_reproduces_the_versioned_ledger(block):
    built = build_block(block)
    assert ledger_payload(built.model, built.id_ledger) == json.loads(
        (ID_LEDGER_ROOT / f"{block}.json").read_text(encoding="utf-8"))


def test_without_the_equation_section_numbering_is_sequential():
    spec = BLOCKS["energy"]
    workbook = read_workbook(spec.workbook_path, spec.sheet)
    ledger = load_ledger(ID_LEDGER_ROOT / "energy.json")
    legacy = dataclasses.replace(ledger, equations=None, retired_equations=())
    model = build_canonical_model("energy", workbook, spec.id_base, legacy)
    equations, _ = build_equations(model, spec.id_base)
    assert [e["equation_id"] for e in equations] == [f"EQ{spec.id_base + i}" for i in range(1, len(equations) + 1)]


def test_new_equation_identity_gets_the_number_after_the_highest_issued():
    spec = BLOCKS["energy"]
    workbook = read_workbook(spec.workbook_path, spec.sheet)
    ledger = load_ledger(ID_LEDGER_ROOT / "energy.json")
    victim_key, victim_id = next(iter(ledger.equations.items()))
    highest = ledger.highest_equation()
    shrunk = dataclasses.replace(
        ledger,
        equations={k: v for k, v in ledger.equations.items() if k != victim_key},
        retired_equations=({"equation_id": f"EQ{highest + 5}", **dict(zip(EQUATION_KEY_FIELDS, ("variable", "x", "diário",
                                                                                                 "linha", "L1", "L1"))),
                            "retired_in": "teste"},),
    )
    model = build_canonical_model("energy", workbook, spec.id_base, shrunk)
    equations, _ = build_equations(model, spec.id_base)
    assigned = dict(model.equation_assignments)
    assert assigned[victim_key] == f"EQ{highest + 6}"                    # acima do maior emitido (aposentado incluso)
    assert all(assigned[k] == v for k, v in shrunk.equations.items())   # nenhum outro muda
    assert victim_id not in {e["equation_id"] for e in equations}


def test_ledger_rejects_duplicated_or_active_and_retired_equation_ids():
    key = equation_key(("variable", "a", "diário", "linha", "L1", ), "L1")
    other = equation_key(("variable", "b", "diário", "linha", "L1"), "L1")
    with pytest.raises(IdLedgerError):
        IdLedger(block="x", equations={key: "EQ18001", other: "EQ18001"})
    with pytest.raises(IdLedgerError):
        IdLedger(block="x", equations={key: "EQ18001"},
                 retired_equations=({"equation_id": "EQ18001", **dict(zip(EQUATION_KEY_FIELDS, other)),
                                     "retired_in": "t"},))
    with pytest.raises(IdLedgerError):
        IdLedger(block="x", equations={key: "VAR18001"})


# ------------------------------------------------------------ D-5A-1

@pytest.mark.parametrize("unit", NEW_UNITS)
def test_new_units_are_allowed_for_variables_and_parameters(unit):
    assert unit in variable_seed_validator.ALLOWED_UNITS
    assert unit in parameter_seed_validator.ALLOWED_UNITS
