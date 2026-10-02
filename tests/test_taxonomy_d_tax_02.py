"""
D-TAX-02 — crosswalk histórico normativo dos três blocos de custo e guarda das
projeções físicas da taxonomia canônica (dívida TD-TAX-01).

TAX-02-01..08 provam que os três pareamentos são explícitos (CONFIRMED, com
evidência de repositório), que as faixas estão registradas, que a taxonomia
continua com 29 blocos, que os nomes históricos não são operacionais e que o
crosswalk não alterou nenhum ID ou faixa. Os testes negativos provam que o guard
rejeita cada tipo de divergência (bloco some/aparece, nome, faixa, ordem, par
ausente/alterado, status implícito, inferência).
"""

from __future__ import annotations

import ast
import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MIGRATION = REPO / "audit" / "stage3_4" / "taxonomy_migration"
sys.path.append(str(MIGRATION))

import d_tax_02_inventory as inventory  # noqa: E402
import taxonomy_guard as guard  # noqa: E402

from app.validation.equation_seed_validator import EQUATION_ID_RANGES  # noqa: E402
from app.validation.parameter_seed_validator import PARAMETER_ID_RANGES  # noqa: E402
from app.validation.variable_seed_validator import VARIABLE_ID_RANGES  # noqa: E402
from tools.workbook_seed.taxonomy import BLOCK_TAXONOMY, OFFICIAL_BLOCKS  # noqa: E402

D_TAX_01_COMMIT = "d8b5d55810c55a06cfc54e8a2a25ac9f796f08b7"   # HEAD antes de D-TAX-02
D_TAX_02_COMMIT = "d2847ab36933668bf4a1299b3ffe058827a82037"   # fechamento da D-TAX-02 (Stage 4C, H)
EXPECTED = {
    "custo_budget": ("budget_cost", [32000, 32999]),
    "custo_forecast_bdgt": ("budget_forecast_cost", [33000, 33999]),
    "custo_forecast_real": ("actual_forecast_cost", [34000, 34999]),
}
REGISTRIES = {"variable": VARIABLE_ID_RANGES, "parameter": PARAMETER_ID_RANGES, "equation": EQUATION_ID_RANGES}
DECISION_DOC = REPO / "audit" / "stage3_4" / "STAGE_3_4_TAXONOMY_D_TAX_02.md"
DECISIONS_CSV = MIGRATION / "contract_decisions.csv"


def crosswalk() -> dict:
    return json.loads((REPO / guard.CROSSWALK_JSON).read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


# ------------------------------------------------------------------ TAX-02-01..03

def test_tax_02_01_the_three_cost_pairs_exist_exactly():
    mapping = crosswalk()["historical_to_canonical"]
    assert {h: e["canonical"] for h, e in mapping.items()} == {h: c for h, (c, _r) in EXPECTED.items()}
    assert guard.COST_CROSSWALK == {h: (c, r[0], r[1]) for h, (c, r) in EXPECTED.items()}


def test_tax_02_02_ranges_are_recorded_and_identical():
    for historical, (canonical, rng) in EXPECTED.items():
        entry = crosswalk()["historical_to_canonical"][historical]
        assert entry["historical_range"] == rng
        assert entry["canonical_range"] == rng
        assert entry["same_id_range"] is True
        for registry in REGISTRIES.values():
            assert registry[canonical] == tuple(rng)


def test_tax_02_03_every_pair_has_explicit_status_and_none_is_inferred():
    payload = crosswalk()
    assert payload["inference_by_name_allowed"] is False
    assert payload["historical_names_are_operational"] is False
    for historical, entry in payload["historical_to_canonical"].items():
        assert entry["status"] == "CONFIRMED", historical          # nenhum UNRESOLVED: gate exige 3 confirmados
        assert entry["inferred_only"] is False
        assert "EXPLICIT_RENAME_RECORD" in entry["evidence_class"]
        assert any(f"{historical}->{entry['canonical']}" in ev for ev in entry["repository_evidence"])
        assert entry["semantic_evidence"]


def test_tax_02_03b_rename_record_exists_in_git_history():
    """A evidência citada (1d3276e) existe e registra os três renames com as mesmas faixas."""
    message = git("log", "-1", "--format=%B", "1d3276e")
    assert "MESMOS ranges numericos" in message
    for historical, (canonical, rng) in EXPECTED.items():
        assert f"{historical}->{canonical}" in message
        for name in ("variable", "parameter", "equation"):
            path = f"app/validation/{name}_seed_validator.py"
            before, after = git("show", f"1d3276e^:{path}"), git("show", f"1d3276e:{path}")
            assert f'"{historical}": ({rng[0]}, {rng[1]})' in before
            assert f'"{canonical}": ({rng[0]}, {rng[1]})' in after
            assert f'"{historical}"' not in after


# ------------------------------------------------------------------ TAX-02-04..05

def test_tax_02_04_taxonomy_still_has_29_blocks_in_every_projection():
    projections = guard.physical_projections()
    assert set(projections) == {"VARIABLE_ID_RANGES", "PARAMETER_ID_RANGES", "EQUATION_ID_RANGES",
                                "BLOCK_TAXONOMY", "interblock_links.taxonomy"}
    assert all(len(rows) == 29 for rows in projections.values())
    assert guard.check_current_registry() == []
    assert len(BLOCK_TAXONOMY) == len(OFFICIAL_BLOCKS) == 29


def test_tax_02_05_historical_names_are_not_canonical_anywhere_operational():
    seed = json.loads((REPO / guard.LINKS_JSON).read_text(encoding="utf-8"))
    for historical in EXPECTED:
        assert historical not in guard.CANONICAL_NAMES
        assert historical not in BLOCK_TAXONOMY
        assert historical not in OFFICIAL_BLOCKS
        assert historical not in seed["taxonomy"]["official_blocks"]
        for registry in REGISTRIES.values():
            assert historical not in registry
    pattern = "|".join(EXPECTED)
    hits = subprocess.run(["git", "grep", "-n", "-I", "--untracked", "-E", pattern, "--", "app", "tools", "data"],
                          cwd=REPO, capture_output=True, text=True).stdout
    assert [h for h in hits.splitlines() if "__pycache__" not in h] == []


# ------------------------------------------------------------------ TAX-02-06

def test_tax_02_06_historical_names_only_in_allowed_places():
    rows, summary = inventory.inventory()
    assert summary["problems"] == [], summary["problems"]
    assert summary["historical_in_operational"] == 0
    assert all(r["class"] != "UNCLASSIFIED" for r in rows)
    for row in rows:
        if row["name_kind"] == "historical_name" and row["class"] == "test":
            assert row["file"] in inventory.HISTORICAL_ALLOWED_TESTS


def test_tax_02_06b_inventory_rejects_unclassified_and_operational_occurrences():
    assert inventory.classify("app/new_module.py", "custo_budget") == "operational"
    assert inventory.classify("somewhere/else.md", "custo_budget") is None
    assert inventory.classify("tests/test_other.py", "custo_budget") == "test"
    assert "tests/test_other.py" not in inventory.HISTORICAL_ALLOWED_TESTS
    assert "operational" not in inventory.HISTORICAL_ALLOWED


def test_tax_02_06c_versioned_occurrence_evidence_is_consistent():
    with (MIGRATION / "evidence" / "d_tax_02_occurrences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(r["class"] != "UNCLASSIFIED" for r in rows)
    assert not [r for r in rows if r["name_kind"] == "historical_name" and r["class"] == "operational"]


# ------------------------------------------------------------------ TAX-02-07

def test_tax_02_07_crosswalk_changes_no_id_or_range():
    # Stage 4C (H): a afirmação é do fechamento D-TAX-02 (d8b5d55..d2847ab); a faixa viva == CANONICAL é S.
    changed = set(git("diff", "--name-only", D_TAX_01_COMMIT, D_TAX_02_COMMIT, "--", "app", "tools", "data").split())
    assert changed <= {"app/validation/variable_seed_validator.py", "app/validation/parameter_seed_validator.py"}
    for path in changed:                                         # só comentários: AST idêntico
        before = ast.parse(git("show", f"{D_TAX_01_COMMIT}:{path}"))
        after = ast.parse(git("show", f"{D_TAX_02_COMMIT}:{path}"))
        assert ast.dump(before) == ast.dump(after), path
    assert guard.protected_status(D_TAX_01_COMMIT, D_TAX_02_COMMIT) in ("UNCHANGED", "AUTHORIZED_TAXONOMY_MIGRATION")
    assert [(n, lo, hi) for n, (lo, hi) in VARIABLE_ID_RANGES.items()] == list(guard.CANONICAL)


# ------------------------------------------------------------------ TAX-02-08

def test_tax_02_08_decision_is_registered_and_validated_automatically():
    with DECISIONS_CSV.open(encoding="utf-8") as handle:
        decisions = {row["decision_id"]: row for row in csv.DictReader(handle)}
    assert decisions["D-TAX-01"]["status"] == "APPLIED"
    assert decisions["D-TAX-02"]["status"] == "APPLIED"
    assert decisions["TD-TAX-01"]["status"] == "OPEN"
    for historical, (canonical, _rng) in EXPECTED.items():
        assert f"{historical}->{canonical}" in decisions["D-TAX-02"]["resolution"]
    payload = crosswalk()
    assert payload["decision"] == guard.D_TAX_02 and payload["status"] == "APPLIED"
    assert guard.check_crosswalk(payload) == []
    text = DECISION_DOC.read_text(encoding="utf-8")
    assert "| status | **APPLIED** |" in text
    for historical, (canonical, rng) in EXPECTED.items():
        assert f"| `{historical}` | `{canonical}` | {rng[0]}–{rng[1]} | **CONFIRMED** |" in text


def test_tax_02_arch_app_does_not_import_tools():
    offenders = []
    for path in (REPO / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            offenders += [f"{path}: {n}" for n in names if n == "tools" or n.startswith("tools.")]
    assert offenders == []


# ------------------------------------------------------------------ negativos

def mutate_projection(source: str, change):
    projections = guard.physical_projections()
    projections[source] = change(list(projections[source]))
    return guard.check_projections(projections)


@pytest.mark.parametrize("source", ["VARIABLE_ID_RANGES", "BLOCK_TAXONOMY", "interblock_links.taxonomy"])
@pytest.mark.parametrize("case", ["removed", "added", "renamed", "reordered"])
def test_guard_rejects_projection_divergence(source, case):
    def change(rows):
        if case == "removed":
            return rows[:-1]
        if case == "added":
            return rows + [("extra_block", None, None) if rows[0][1] is None else ("extra_block", 39000, 39999)]
        if case == "renamed":
            i = [r[0] for r in rows].index("budget_cost")
            return rows[:i] + [("custo_budget", *rows[i][1:])] + rows[i + 1:]
        rows[0], rows[1] = rows[1], rows[0]
        return rows
    problems = mutate_projection(source, change)
    assert problems and all(p.startswith("PROJECTION_DIVERGENCE") for p in problems)


@pytest.mark.parametrize("source", ["VARIABLE_ID_RANGES", "PARAMETER_ID_RANGES", "EQUATION_ID_RANGES"])
def test_guard_rejects_range_change(source):
    def change(rows):
        i = [r[0] for r in rows].index("actual_forecast_cost")
        return rows[:i] + [("actual_forecast_cost", 34000, 34998)] + rows[i + 1:]
    assert any("faixa de actual_forecast_cost" in p for p in mutate_projection(source, change))


def _mutated(edit) -> list[str]:
    payload = copy.deepcopy(crosswalk())
    edit(payload)
    return guard.check_crosswalk(payload)


@pytest.mark.parametrize("edit", [
    pytest.param(lambda p: p["historical_to_canonical"].pop("custo_forecast_bdgt"), id="pair-missing"),
    pytest.param(lambda p: p["historical_to_canonical"].update(custo_extra={}), id="pair-extra"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_budget"].update(canonical="budget_forecast_cost"),
                 id="pair-changed"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_budget"].pop("status"), id="status-implicit"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_budget"].update(status="PROBABLE"),
                 id="status-invalid"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_forecast_real"].update(inferred_only=True),
                 id="inferred-only"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_forecast_real"].update(historical_range=[34000, 34500]),
                 id="range-changed"),
    pytest.param(lambda p: p["historical_to_canonical"]["custo_budget"].update(repository_evidence=[]),
                 id="confirmed-without-evidence"),
    pytest.param(lambda p: p.update(inference_by_name_allowed=True), id="inference-allowed"),
    pytest.param(lambda p: p.update(status="PROPOSED"), id="decision-not-applied"),
])
def test_guard_rejects_crosswalk_divergence(edit):
    problems = _mutated(edit)
    assert problems and all(p.startswith("CROSSWALK_DIVERGENCE") for p in problems)
