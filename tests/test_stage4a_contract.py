"""
Stage 4A.1 — contrato do area_41 no universo integrado (REAL_DERIVED_TEST_RESULT).

Provam que as cardinalidades do contrato 4A foram derivadas pelo planner/engine
E confirmadas por recálculo independente (processo `python -I` que não importa
app/tools), que o plano oficial e os 16 PENDING_LOAD continuam intactos, que a
árvore de decisão de `hes` do engine é a do texto literal do workbook e que o
literal "F" vira estado (nunca texto no valor). Nenhum teste altera app/, data/ ou tools/.

Stage 4C: recálculo independente, derivação e plano oficial são classe R (expectativas e plan_evidence
do registro `current`; em B0 os literais 446/458/62/896 são provados no teste do registro). O fato
"vínculos inalterados durante a 4A" é H (`d2847ab` x `0a924e6`).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import hashlib

import openpyxl
import pytest

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4a"
sys.path.insert(0, str(STAGE))

import common  # noqa: E402
import independent_count as independent  # noqa: E402

sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_registry as reg  # noqa: E402

EXPECTATIONS = reg.load_json("stage4a_contract", "contract_expectations.json")      # classe R
IND = EXPECTATIONS["independent"]
LINKS = "data/seed/interblock_links.json"
BASELINE_4A, CLOSURE_4A = "d2847ab36933668bf4a1299b3ffe058827a82037", "0a924e66cfd0774a13e46a332b460b770283a554"
NAR = "NO_APPLICABLE_RULE"
F_COMBINATIONS = {("Normal", "1 By pass e LC"), ("1 By pass e LC", "Normal")}


@pytest.fixture(scope="module")
def independent_run():
    completed = subprocess.run([sys.executable, "-I", str(STAGE / "independent_count.py"), "--check",
                                *reg.harness_args()], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout)


@pytest.fixture(scope="module")
def derived_run():
    completed = subprocess.run([sys.executable, str(STAGE / "derive_4a.py"), "--no-write", *reg.harness_args()],
                               cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_independent_recount_matches_contract_without_importing_app(independent_run):
    code, out = independent_run
    assert code == 0, out["problems"]
    assert out["imports_app_or_tools"] == []
    u5 = out["universe_5"]
    # B0: (446, 458, 62, 896), {238, 207, 13}, 25, 427 — provados no teste do registro
    assert (u5["targets"], u5["nodes"], u5["required_inputs"], u5["events_per_date"]) == (
        IND["universe_5.targets"], IND["universe_5.nodes"], IND["universe_5.required_inputs"],
        IND["universe_5.events_per_date"])
    assert u5["nodes_by_kind"] == IND["universe_5.nodes_by_kind"]
    assert u5["targets_by_block"]["area_41"] == EXPECTATIONS["integrated"]["area_41_targets"]
    assert out["universe_4"]["nodes"] == IND["universe_4.nodes"] and out["universe_area_41_only"]["nodes"] == 33


def test_nodes_are_the_union_not_the_sum(independent_run):
    _code, out = independent_run
    union = out["union"]
    assert union["shared"] == IND["union.shared"]                      # B0: [EQ12012, TRANSFER:VAR11031]
    assert union["union"] == union["nodes_4"] + union["nodes_area_41_only"] - len(union["shared"]) == \
        IND["universe_5.nodes"]
    assert union["union_equals_5"] is True
    assert out["link_VAR16007_used_in_5"] is True and out["link_VAR16007_used_in_4"] is False


def test_derivation_agrees_with_independent_recount_and_frozen_expectations(derived_run):
    code, out, stderr = derived_run
    assert code == 0, (out["problems"], stderr[-1500:])
    assert out["independent"]["fields_compared"] >= 40
    assert out["union"]["plan4_relative_order_preserved_in_5"] is True


def test_official_plan_pending_links_and_links_sha_are_unchanged(derived_run):
    _code, out, _ = derived_run
    plan = out["official_plan"]
    assert plan["identical_to_plan_evidence"] is True and plan["differences"] == []
    assert plan["area_41"] == IND["official_plan.area_41"]           # B0: {OK: 3, INTERBLOCK_SOURCE_NOT_LOADED: 22}
    assert plan["area_41_pending_blocks"] == ["maintenance"]
    assert plan["pending_links"] == IND["official_plan.pending_links"] == 16
    assert plan["pending_by_source_block"] == {"alumina": 1, "area_04_13": 1, "forecast": 2, "maintenance": 9,
                                               "temperature_lp": 3}
    assert plan["interblock_links_sha256"] == EXPECTATIONS["integrated"]["interblock_links_sha256"]   # R
    links = {commit: subprocess.run(["git", "show", f"{commit}:{LINKS}"], cwd=REPO, capture_output=True,
                                    check=True).stdout for commit in (BASELINE_4A, CLOSURE_4A)}
    assert plan["interblock_links_sha256_at_baseline"] == hashlib.sha256(links[BASELINE_4A]).hexdigest() == \
        hashlib.sha256(links[CLOSURE_4A]).hexdigest()                  # H: vínculos inalterados durante a 4A


def test_official_plan_comparator_detects_a_changed_evidence_row(tmp_path, monkeypatch):
    rows = list(csv.DictReader(independent.PLAN_EVIDENCE.open(encoding="utf-8")))
    victim = next(r for r in rows if r["target"] == "VAR16004")
    victim["observed"] = "INTERBLOCK_SOURCE_NOT_LOADED"
    copy = tmp_path / "plan_evidence.csv"
    with copy.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(independent, "PLAN_EVIDENCE", copy)
    differences = independent.official_plan(independent.catalog())["differences_vs_plan_evidence"]
    assert len(differences) == 1 and differences[0].startswith("VAR16004")


def test_hes_decision_tree_engine_equals_literal_workbook_in_all_50_combinations(derived_run):
    _code, out, _ = derived_run
    assert out["hes"]["combinations"] == 50 and out["hes"]["agree"] == 50
    rows = list(csv.DictReader((STAGE / "evidence" / "hes_decision_matrix.csv").open(encoding="utf-8")))
    for group in ("L4_L5", "L6_L7"):
        f = {(r["hes_first"], r["hes_second"]) for r in rows if r["group"] == group and r["workbook_branch"] == "F"}
        assert f == F_COMBINATIONS                                       # "F" só em 2/25 por grupo
    bypass = {r["group"]: r["workbook_branch"] for r in rows
              if (r["hes_first"], r["hes_second"]) == ("1 By pass", "1 By pass")}
    assert bypass == {"L4_L5": "1 By pass[41d]", "L6_L7": "1 By pass[41c]"}   # 41d só em L4_L5


def test_precedence_follows_branch_order_when_lines_differ():
    rows = {(r["group"], r["hes_first"], r["hes_second"]): r["branch"] for r in independent.hes_matrix()}
    for group in ("L4_L5", "L6_L7"):
        assert rows[(group, "LC", "Overhaul/Parada")] == "LC"
        assert rows[(group, "Overhaul/Parada", "1 By pass")] == "Overhaul/Parada"
        assert rows[(group, "1 By pass e LC", "LC")] == "LC"
        assert rows[(group, "1 By pass e LC", "Overhaul/Parada")] == "Overhaul/Parada"


def test_f_literal_is_a_state_never_text_in_a_numeric_value(derived_run):
    _code, out, _ = derived_run
    f = out["f_literal"]
    assert f["value_is_text"] is False
    # contrato 3.3B (D1/R1): value None, state NO_APPLICABLE_RULE, detail None (finding F4A-01)
    assert f["engine_results"] == [["NoneType", "None", NAR, "None"]]
    for label, case in f["propagation"].items():
        group = "L4_L5" if label.startswith("L4_L5") else "L6_L7"
        lines = ("L4", "L5") if group == "L4_L5" else ("L6", "L7")
        source = "VAR16025" if group == "L4_L5" else "VAR16028"
        assert case["error"] is None
        assert set(case["stated"]) == {f"{source}@{group}", f"VAR16031@{lines[0]}", f"VAR16031@{lines[1]}",
                                       "VAR16034@L1_L7"}
        assert all(v == [None, NAR, None] for v in case["stated"].values())


def test_f_literal_on_both_groups_through_the_engine():
    universe = common.Universe("A")
    for group, (eq, target, lines, operands) in {
            "L4_L5": ("EQ16011", "VAR16025", ("L4", "L5"), ("VAR16005", "VAR16015", "VAR16022", "VAR16024")),
            "L6_L7": ("EQ16012", "VAR16028", ("L6", "L7"), ("VAR16006", "VAR16016", "VAR16023"))}.items():
        for combo in F_COMBINATIONS:
            inputs = {(v, "linha_grupo", group): 3.0 for v in operands}
            inputs.update({("VAR16021", "linha", line): h for line, h in zip(lines, combo)})
            results, error = common.engine_area_41(universe.orchestrator, inputs, only={eq})
            result = results[(target, "linha_grupo", group)]
            assert error is None
            assert (result.value, result.state, result.detail) == (None, NAR, None)


def test_scopes_and_suffixes_verified_in_the_parser(derived_run):
    _code, out, _ = derived_run
    audit = json.loads((STAGE / "evidence" / "contract_audit.json").read_text(encoding="utf-8"))
    scopes = audit["scopes"]
    assert scopes["parse_errors"] == [] and scopes["equation_vs_target_scope_mismatches"] == []
    assert all(c["covered_once"] for c in scopes["target_instance_coverage"].values())
    assert scopes["suffix_scope_type"]["L4_L5"] == "linha_grupo" and scopes["suffix_scope_type"]["L7"] == "linha"
    assert scopes["suffix_scope_type"]["L8"].startswith("REJEITADO")
    assert scopes["target_instance_coverage"]["VAR16031"] == {"instances": 7, "covered_once": True}


def test_area_41_aggregation_rules_and_ytd_partial():
    audit = json.loads((STAGE / "evidence" / "contract_audit.json").read_text(encoding="utf-8"))
    rules = audit["aggregations"]
    assert len(rules) == 10 and {r["type"] for r in rules} == {"AVERAGE"}
    assert {r["target_frequency"] for r in rules} == {"mensal", "anual"}
    linha = [r for r in rules if "RETIRADA_CONDENSADO_LINHA-LINHA-L1_L7" in r["rule"]]
    assert len(linha) == 2 and all(len(r["instances"]) == 7 for r in linha)
    probe = audit["ytd_probe"]
    assert probe["windows_of_annual_identity"] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert float(probe["annual_2026_window_2026-01-03"][1]) == pytest.approx(probe["mean_of_3"], rel=1e-12)


def test_obs_register_is_read_from_the_workbook_and_fully_classified():
    sheet = openpyxl.load_workbook(independent.WORKBOOK, read_only=True)["A41"]
    raw = [row[17] for row in sheet.iter_rows(min_row=3, values_only=True) if row[17]]
    register = list(csv.DictReader((STAGE / "evidence" / "obs_register.csv").open(encoding="utf-8")))
    assert [r["obs"] for r in register] == raw and len(raw) == 26
    assert {r["classification"] for r in register} <= {"REQUIRES_FOLLOWUP", "DOCUMENTATION_ONLY"}
    assert any("41c/41d" in r["obs"] for r in register if r["name"] == "retirada_condensado_grupo")


def test_input_protocol_keeps_every_3_4c_input_index():
    universe = common.Universe("A")
    assert all(universe.index[v] == i for i, v in enumerate(universe.plan4.required_inputs))
    new = [v for v in universe.plan.required_inputs if v in universe.area_41_entities]
    assert sorted(universe.index[v] for v in new) == list(range(51, 62))
    naive = {v: i for i, v in enumerate(universe.plan.required_inputs)}
    assert any(naive[v] != universe.index[v] for v in universe.plan4.required_inputs)   # por isso DR-4A-5


def test_contract_document_records_decisions_findings_and_obs():
    text = (STAGE / "STAGE_4A_DECISION_CONTRACT.md").read_text(encoding="utf-8")
    for token in ("DR-4A-1", "DR-4A-2", "DR-4A-3", "DR-4A-4", "DR-4A-5", "DR-4A-6", "DR-4A-7",
                  "F4A-01", "PROPOSED_ACCEPTED_BY_DEFAULT", "REAL_DERIVED_TEST_RESULT",
                  "INDEPENDENT_NUMERIC_ORACLE = PARTIAL"):
        assert token in text
    assert "UNRESOLVED`: **nenhuma**" in text and "`BLOCKER` técnico: **nenhum**" in text
