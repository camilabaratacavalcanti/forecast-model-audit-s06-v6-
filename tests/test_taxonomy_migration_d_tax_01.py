"""
D-TAX-01 — canonicalização da taxonomia oficial para 29 blocos e rename
`monthly_ppt_assumptions` -> `thickener_flocculant` (faixa 30000–30999).

TAX-01..TAX-10 provam que o registro canônico é único e de 29 blocos em todas
as fontes normativas e que a migração é exclusivamente nomenclatural: nenhum
ID, fórmula, vínculo, pendência, cardinalidade ou resultado mudou. Os testes
negativos provam que o guard "taxonomy-only" da Stage 3 não aceita nenhuma
outra mudança (não é um bypass dos controles).
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MIGRATION = REPO / "audit" / "stage3_4" / "taxonomy_migration"
sys.path.append(str(MIGRATION))

import taxonomy_guard as guard  # noqa: E402

from app.validation.equation_seed_validator import EQUATION_ID_RANGES  # noqa: E402
from app.validation.parameter_seed_validator import PARAMETER_ID_RANGES  # noqa: E402
from app.validation.variable_seed_validator import VARIABLE_ID_RANGES  # noqa: E402
from tools.workbook_seed.taxonomy import BLOCK_TAXONOMY, OFFICIAL_BLOCKS  # noqa: E402

PRE_MIGRATION = "547b9202f5f17fb57034624d7f4c94b0618854e1"   # HEAD antes de D-TAX-01
RETIRED = "monthly_" + "ppt_assumptions"                     # nome aposentado (montado para não ser ocorrência)
SEED_LINKS = REPO / "data" / "seed" / "interblock_links.json"
REGISTRIES = {"variable": VARIABLE_ID_RANGES, "parameter": PARAMETER_ID_RANGES, "equation": EQUATION_ID_RANGES}


def seed_links() -> dict:
    return json.loads(SEED_LINKS.read_text(encoding="utf-8"))


def base(path: str) -> bytes:
    return subprocess.run(["git", "show", f"{PRE_MIGRATION}:{path}"], cwd=REPO, capture_output=True,
                          check=True).stdout


# ------------------------------------------------------------ TAX-01..TAX-05

def test_tax_01_exactly_29_official_blocks_in_every_normative_source():
    assert len(BLOCK_TAXONOMY) == len(set(BLOCK_TAXONOMY)) == len(OFFICIAL_BLOCKS) == 29
    assert len(seed_links()["taxonomy"]["official_blocks"]) == 29
    assert seed_links()["taxonomy"]["decision"] == "D-TAX-01"
    for registry in REGISTRIES.values():
        assert len(registry) == 29


def test_tax_02_canonical_order_is_exactly_the_owner_order():
    assert BLOCK_TAXONOMY == guard.CANONICAL_NAMES
    assert tuple(seed_links()["taxonomy"]["official_blocks"]) == guard.CANONICAL_NAMES
    for registry in REGISTRIES.values():
        assert tuple(registry) == guard.CANONICAL_NAMES


def test_tax_03_all_ranges_match_exactly():
    expected = {name: (lo, hi) for name, lo, hi in guard.CANONICAL}
    for kind, registry in REGISTRIES.items():
        assert registry == expected, kind
    ordered = [lo for _n, lo, _h in guard.CANONICAL]
    assert ordered == list(range(10000, 39000, 1000))                     # contínuas, 1000 IDs, sem sobreposição
    assert all(hi == lo + 999 for _n, lo, hi in guard.CANONICAL)
    assert "budget_vs_forecast" in OFFICIAL_BLOCKS and VARIABLE_ID_RANGES["budget_vs_forecast"] == (37000, 37999)


def test_tax_04_thickener_flocculant_owns_30000_30999():
    for registry in REGISTRIES.values():
        assert registry["thickener_flocculant"] == (30000, 30999)
        assert RETIRED not in registry
    assert "thickener_flocculant" in OFFICIAL_BLOCKS


def _current_text_files():
    for root in ("app", "tools", "data"):
        for path in (REPO / root).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".xlsx":
                yield path


def test_tax_05_retired_name_absent_from_current_code_data_and_configuration():
    for path in _current_text_files():
        assert RETIRED.encode() not in path.read_bytes(), path
    for workbook in (REPO / "data" / "workbooks").glob("*.xlsx"):          # células das planilhas
        with zipfile.ZipFile(workbook) as archive:
            for name in archive.namelist():
                assert RETIRED.encode() not in archive.read(name), (workbook.name, name)
    # a lista D26-01 (28 nomes em português) não é mais fonte normativa atual
    assert "premissas_ppt_mensal" not in OFFICIAL_BLOCKS
    assert "premissas_ppt_mensal" not in seed_links()["taxonomy"]["official_blocks"]


# ------------------------------------------------------------ TAX-06..TAX-09 (antes x depois, ao vivo)

@pytest.fixture(scope="module")
def snapshots(tmp_path_factory):
    after = tmp_path_factory.mktemp("dtax01") / "after.json"
    subprocess.run([sys.executable, str(MIGRATION / "snapshot.py"), str(after)], cwd=REPO, check=True,
                   capture_output=True)
    before = json.loads((MIGRATION / "evidence" / "before_snapshot.json").read_text(encoding="utf-8"))
    return before, json.loads(after.read_text(encoding="utf-8"))


def test_tax_06_no_id_changed_by_the_rename(snapshots):
    before, after = snapshots
    assert after["ids"] == before["ids"]
    assert after["files_sha256"] == before["files_sha256"]                # todos os seeds de bloco e ledgers
    rename = {RETIRED: "thickener_flocculant"}
    for kind in ("variable", "parameter", "equation"):
        assert after["ranges"][kind] == [[rename.get(n, n), lo, hi] for n, lo, hi in before["ranges"][kind]]


def test_tax_07_no_formula_changed(snapshots):
    before, after = snapshots
    assert after["formulas_sha256"] == before["formulas_sha256"]


def test_tax_08_no_interblock_link_changed_semantically(snapshots):
    before, after = snapshots
    assert after["interblock"] == before["interblock"]                    # links, pending, rejected, resto do JSON
    old, new = json.loads(base("data/seed/interblock_links.json")), seed_links()
    assert {k: v for k, v in old.items() if k != "taxonomy"} == {k: v for k, v in new.items() if k != "taxonomy"}
    assert new["taxonomy"]["loaded_blocks"] == old["taxonomy"]["loaded_blocks"]
    assert {link["source_block"] for link in new["links"] + new["pending"]} <= OFFICIAL_BLOCKS


def test_tax_09_the_16_pending_load_links_are_identical(snapshots):
    before, after = snapshots
    assert after["interblock"]["pending"] == before["interblock"]["pending"]
    assert len(after["interblock"]["pending"]) == 16
    assert {p[3] for p in after["interblock"]["pending"]} == {"PENDING_LOAD"}
    assert {p[2] for p in after["interblock"]["pending"]} == {"maintenance", "temperature_lp", "forecast",
                                                             "area_04_13", "alumina"}


def test_cardinalities_results_and_graph_unchanged(snapshots):
    before, after = snapshots
    assert after["cardinalities"] == before["cardinalities"]
    assert after["cardinalities"]["official_targets"] == 446 and after["cardinalities"]["planner_nodes"] == 427
    assert after["execution"] == before["execution"]                      # 32 datas, 313/313/185, fingerprints
    assert after["fixture_graph_hash"] == before["fixture_graph_hash"]
    for block in ("yield", "production", "energy", "max_ht", "area_41"):  # os 5 blocos carregados
        assert after["ids"][block] == before["ids"][block]


# ------------------------------------------------------------ TAX-10 e guard

def test_tax_10_the_authorized_change_is_detected_as_taxonomic_not_functional():
    verdict = guard.classify_git(PRE_MIGRATION)
    assert verdict["taxonomy_only"] and verdict["problems"] == [], verdict["problems"]
    assert set(verdict["files"]) == set(guard.AUTHORIZED)
    for reference in ("7877551", "f3b6588", "043fe9c"):                  # baselines da Stage 3
        assert guard.protected_status(reference, None, ("data", "tools")) == "AUTHORIZED_TAXONOMY_MIGRATION"


def _real(path: str) -> bytes:
    return (REPO / path).read_bytes()


def _mutated_json(path: str, fn) -> bytes:
    payload = json.loads(_real(path))
    fn(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode()


def _replace(path: str, old: str, new: str) -> bytes:
    data = _real(path)
    assert data.count(old.encode()) >= 1
    return data.replace(old.encode(), new.encode(), 1)


LINKS = "data/seed/interblock_links.json"
VALIDATOR = "app/validation/variable_seed_validator.py"
NEGATIVE = {
    "formula_change": ("data/seed/yield/equations.json",
                       lambda: _mutated_json("data/seed/yield/equations.json",
                                             lambda p: p[0].__setitem__("expression", p[0]["expression"] + " + 0"))),
    "value_change": ("data/seed/production/parameters.json",
                     lambda: _mutated_json("data/seed/production/parameters.json",
                                           lambda p: p[0].__setitem__("value", 12345))),
    "range_change": (VALIDATOR, lambda: _replace(VALIDATOR, '"thickener_flocculant": (30000, 30999)',
                                                 '"thickener_flocculant": (30000, 30998)')),
    "extra_code_in_validator": (VALIDATOR, lambda: _real(VALIDATOR) + b"\r\nALLOWED_VARIABLE_TYPES = set()\r\n"),
    "link_removed": (LINKS, lambda: _mutated_json(LINKS, lambda p: p["links"].pop())),
    "pending_load_altered": (LINKS, lambda: _mutated_json(
        LINKS, lambda p: p["pending"][0].__setitem__("resolution_status", "RESOLVED"))),
    "pending_removed": (LINKS, lambda: _mutated_json(LINKS, lambda p: p["pending"].pop())),
    "taxonomy_cardinality_28": (LINKS, lambda: _mutated_json(
        LINKS, lambda p: p["taxonomy"]["official_blocks"].remove("budget_vs_forecast"))),
    "links_outside_taxonomy_section": (LINKS, lambda: _mutated_json(
        LINKS, lambda p: p["workbooks"]["yield"].__setitem__("sha256", "0" * 64))),
    "taxonomy_order_changed": ("tools/workbook_seed/taxonomy.py", lambda: _replace(
        "tools/workbook_seed/taxonomy.py", '    "maintenance",\n    "yield",\n', '    "yield",\n    "maintenance",\n')),
    "engine_code_change": ("app/engine/temporal_aggregation_service.py", lambda: _replace(
        "app/engine/temporal_aggregation_service.py", "sum(values) / len(values)", "sum(values) / (len(values) + 1)")),
    "seed_variable_removed": ("data/seed/energy/variables.json",
                              lambda: _mutated_json("data/seed/energy/variables.json", lambda p: p.pop())),
}


@pytest.mark.parametrize("case", sorted(NEGATIVE))
def test_guard_rejects_every_non_taxonomic_change(case):
    path, mutate = NEGATIVE[case]
    changes = guard.changes_between(PRE_MIGRATION)                      # a migração real ...
    old = changes[path][0] if path in changes else base(path)
    changes[path] = (old, mutate())                                     # ... + UMA mudança não taxonômica
    verdict = guard.classify(changes)
    assert not verdict["taxonomy_only"]
    assert any(p.startswith("NON_TAXONOMIC_CHANGE") and path in p for p in verdict["problems"]), verdict["problems"]


def test_guard_rejects_created_or_deleted_protected_files():
    assert not guard.classify({"app/engine/new_module.py": (None, b"x = 1\n")})["taxonomy_only"]
    assert not guard.classify({LINKS: (base(LINKS), None)})["taxonomy_only"]


def test_stage3_provenance_still_rejects_masked_pending_links(tmp_path):
    sys.path.insert(0, str(REPO / "audit" / "stage3_4" / "mutation"))
    import provenance
    seed = tmp_path / "seed"
    seed.mkdir()
    baseline = subprocess.run(["git", "show", "043fe9c:data/seed/interblock_links.json"], cwd=REPO,
                              capture_output=True, check=True).stdout
    (seed / "interblock_links.json").write_bytes(_real(LINKS))
    assert provenance.check_provenance(seed, baseline) == []                           # migração autorizada
    (seed / "interblock_links.json").write_bytes(_mutated_json(LINKS, lambda p: p.__setitem__("pending", [])))
    problems = provenance.check_provenance(seed, baseline)
    assert any(p.startswith("PROVENANCE_FAILURE") for p in problems)
    assert any(p.startswith("PENDING_LINKS_ALTERED") for p in problems)
