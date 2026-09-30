"""
Stage 3.4D — Mutation & Audit Closure.

Validam, sem alterar app/, data/, tools/ ou seeds:
    * a matriz de mutações de EVIDÊNCIA roda ao vivo sobre a evidência real
      (3.4B diferencial, 3.4C integrado) e 100% das mutações são detectadas
      pelos auditores reais; controles positivos continuam aceitos; o
      resultado ao vivo reproduz a evidência versionada;
    * um MUTANTE DE CÓDIGO roda ao vivo numa cópia temporária de HEAD e é
      morto pelos testes existentes e pela auditoria integrada;
    * a evidência versionada dos 17 mutantes de código (0 sobreviventes);
    * a auditoria black-box (sem importar app/) aceita a evidência correta e
      rejeita cópias corrompidas;
    * os gaps dos auditores da 3.4C no baseline estão registrados e fechados.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MUTATION = REPO / "audit" / "stage3_4" / "mutation"
sys.path.insert(0, str(MUTATION))

import blackbox_audit  # noqa: E402

BASELINE = "043fe9c36d9d02664db8be7dd29c0fd7014c73f8"


def read_csv(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ------------------------------------------------------------ mutações de evidência (ao vivo)

@pytest.fixture(scope="module")
def live():
    done = subprocess.run([sys.executable, str(MUTATION / "run_mutation.py"), "--no-write", "--skip-code-mutants"],
                          cwd=REPO, capture_output=True, text=True)
    return done.returncode, json.loads(done.stdout), done.stderr


def test_live_evidence_mutations_are_all_detected(live):
    code, out, stderr = live
    assert code == 0, stderr[-2000:]
    s = out["summary"]
    assert s["mutations_defined"] == s["mutations_executed"] == s["mutations_detected"] == len(out["results"])
    assert s["mutations_missed"] == 0 and s["detection_rate"] == "100.0%"
    assert s["positive_controls"]["rejected_unexpectedly"] == [] and s["positive_controls"]["accepted"] >= 10
    assert s["fixture"]["official_pending_links"] == 16
    assert s["fixture"]["persisted_links_status"] in ("EQUAL_TO_BASELINE", "AUTHORIZED_TAXONOMY_MIGRATION")
    assert s["protected_artifacts"]["result"] in ("NO PRODUCTION CHANGES", "AUTHORIZED TAXONOMY MIGRATION (D-TAX-01)")
    assert s["synthetic_only_mutations"] == 0


def test_live_run_reproduces_committed_mutation_results(live):
    _code, out, _ = live
    committed = read_csv(MUTATION / "mutation_results.csv")
    assert [(r["mutation_id"], r["expected_detection"], r["actual_detection"], r["result"]) for r in committed] == \
        [(r["mutation_id"], r["expected_detection"], r["actual_detection"], r["result"]) for r in out["results"]]


# ------------------------------------------------------------ evidência versionada

def test_committed_mutation_matrix_is_formal_and_complete():
    matrix = read_csv(MUTATION / "mutation_matrix.csv")
    results = read_csv(MUTATION / "mutation_results.csv")
    ids = [r["mutation_id"] for r in matrix]
    assert len(ids) == len(set(ids)) == len(results) and ids == [r["mutation_id"] for r in results]
    assert blackbox_audit.REQUIRED_MUTATIONS <= set(ids)
    assert {r["contract"] for r in matrix} == {f"M{i}" for i in range(1, 11)}
    assert {r["production_code_touched"] for r in matrix} == {"NO"}
    for field in ("mutation_description", "mutation_point", "artifact", "field", "expected_detection",
                  "detection_mechanism", "real_path"):
        assert all(r[field] for r in matrix), field
    for r in results:
        assert r["detected"] == "TRUE" and r["result"] == "PASS" and r["rejected"] == "TRUE"
        assert r["expected_detection"] in r["actual_detection"].split("|")
        assert r["before"] != r["after"]                                       # mutação localizada e efetiva


def test_committed_code_mutants_have_no_survivors():
    summary = json.loads((MUTATION / "mutation_summary.json").read_text(encoding="utf-8"))
    code = summary["code_mutants"]
    assert code["introduced"] == code["detected"] == 17 and code["surviving"] == 0
    assert code["positive_control"]["result"] == "ACCEPT" and code["positive_control"]["detected_by"] == ""
    assert code["repository_untouched"]
    rows = read_csv(MUTATION / "code_mutation_results.csv")
    assert len(rows) == 17
    for r in rows:
        detected = set(r["detected_by"].split("|"))
        assert r["result"] == "PASS" and set(r["expected_detectors"].split("|")) <= detected
        assert "TESTS" in detected and detected & {"INTEGRATED", "DIFFERENTIAL"}


def test_live_code_mutant_is_killed_in_a_temporary_copy():
    import code_mutants
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    mutant = next(m for m in code_mutants.CODE_MUTANTS if m[0] == "CM-13")
    row = code_mutants.evaluate_mutant(mutant, code_mutants.expected_integrated())
    after = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout
    assert before == after                                  # a execução do mutante não toca o repositório
    assert row["result"] == "PASS" and {"TESTS", "INTEGRATED"} <= set(row["detected_by"].split("|"))
    assert "MULTI_DETAIL_COMPOSITION_UNDEFINED" in row["evidence"]


# ------------------------------------------------------------ auditoria black-box

def test_blackbox_audit_passes_without_importing_app():
    done = subprocess.run([sys.executable, "-I", str(MUTATION / "blackbox_audit.py"), "--no-write"],
                          cwd=REPO, capture_output=True, text=True)
    report = json.loads(done.stdout)
    assert done.returncode == 0 and report["result"] == "PASS" and report["findings"] == []
    assert report["imports_app"] is False


def corrupted_copy(tmp_path):
    root = tmp_path / "stage3_4"
    for name in ("differential/evidence", "integrated/evidence"):
        shutil.copytree(REPO / "audit" / "stage3_4" / name, root / name)
    (root / "mutation").mkdir()
    for path in MUTATION.glob("*.csv"):
        shutil.copy2(path, root / "mutation" / path.name)
    shutil.copy2(MUTATION / "mutation_summary.json", root / "mutation" / "mutation_summary.json")
    return root


def rewrite(path, fn):
    text = path.read_text(encoding="utf-8")
    new = fn(text)
    assert new != text
    path.write_text(new, encoding="utf-8")


@pytest.mark.parametrize("artifact, corrupt, expected", [
    ("differential/evidence/differential_cases.csv", lambda t: t.replace(",MATCH\n", ",VALUE_DIFFERENCE\n", 1),
     "3.4B: caso diferente de MATCH"),
    ("integrated/evidence/targets.csv", lambda t: "\n".join(t.splitlines()[:-1]) + "\n", "3.4C: targets.csv"),
    ("integrated/evidence/transfers.csv", lambda t: t.replace(",224,224,", ",224,223,", 1),
     "3.4C: transferência não verificada"),
    ("integrated/evidence/integrated_summary.json",
     lambda t: t.replace('"label": "REAL_DERIVED_TEST_RESULT"', '"label": "OPERATIONAL"'), "3.4C: summary"),
    ("mutation/mutation_results.csv", lambda t: t.replace(",TRUE,TRUE,", ",FALSE,TRUE,", 1),
     "3.4D: mutação não detectada"),
    ("mutation/code_mutation_results.csv", lambda t: t.replace("|TESTS,TRUE", ",TRUE", 1), "3.4D: mutante não morto pelos testes"),
])
def test_blackbox_audit_rejects_corrupted_evidence(tmp_path, artifact, corrupt, expected):
    root = corrupted_copy(tmp_path)
    assert blackbox_audit.audit(root, check_imports=False)["result"] == "PASS"                   # controle positivo da cópia
    rewrite(root / artifact, corrupt)
    report = blackbox_audit.audit(root, check_imports=False)
    assert report["result"] == "FAIL" and any(f.startswith(expected) for f in report["findings"])


# ------------------------------------------------------------ gaps do baseline e integridade

def test_baseline_gaps_are_recorded_and_closed():
    probe = json.loads((MUTATION / "baseline_gap_probe.json").read_text(encoding="utf-8"))
    assert probe["baseline"] == BASELINE and probe["control_sc1_original_problems"] == []
    assert {k: v["detected_by_original_auditor"] for k, v in probe["probes"].items()} == {
        "G1_state_reach_unnamed_date": False, "G2_value_with_state": False,
        "G3_duplicated_transfer_interblock_check": False, "G4_transfer_wrong_target_interblock_check": False,
        "G5_monthly_identity_without_window": False}
    closed_by = {r["mutation_id"]: r for r in read_csv(MUTATION / "mutation_results.csv")}
    for mutation_id in ("MUT-S01", "MUT-A05", "MUT-TX05", "MUT-TX06", "MUT-TM04"):
        assert closed_by[mutation_id]["detected"] == "TRUE"


def test_no_production_artifact_changed_since_baseline():
    # D-TAX-01: app/data/tools iguais ao baseline, ou diferentes SOMENTE pela migração
    # taxonômica autorizada, provada arquivo a arquivo (qualquer outra mudança falha).
    sys.path.append(str(REPO / "audit" / "stage3_4" / "taxonomy_migration"))
    import taxonomy_guard as guard
    verdict = guard.classify_git(BASELINE)
    assert verdict["unchanged"] or verdict["taxonomy_only"], verdict["problems"]
