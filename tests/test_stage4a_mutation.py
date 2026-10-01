"""
Stage 4A.3b — mutação e controles do area_41 (REAL_DERIVED_TEST_RESULT).

Provam que os auditores da 4A detectam 100% das mutações de evidência (com controles
positivos aceitos), que os mutantes de código/seed foram todos detectados em cópias
temporárias (evidência versionada) e que a árvore de trabalho nunca foi tocada.
Os mutantes de código não são reexecutados aqui (custo ~10 min); a execução viva
cobre as mutações de evidência.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MUTATION = REPO / "audit" / "stage4a" / "mutation"
EVIDENCE = MUTATION / "evidence"
sys.path[:0] = [str(REPO / "audit" / "stage4a"), str(REPO / "audit" / "stage4a" / "integrated"), str(MUTATION)]

import code_mutants_4a  # noqa: E402

MINIMUM = {"CM4A-01": "and/or", "CM4A-02": "\"F\"", "CM4A-03": "ln", "CM4A-04": "/2", "CM4A-05": "@L5",
           "CM4A-06": "VAR16007"}


def read_csv(name):
    return list(csv.DictReader((EVIDENCE / name).open(encoding="utf-8")))


@pytest.fixture(scope="module")
def live():
    completed = subprocess.run([sys.executable, str(MUTATION / "run_mutation_4a.py"), "--no-write",
                                "--skip-code-mutants"], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_evidence_mutations_are_all_detected_with_positive_controls(live):
    code, summary, stderr = live
    assert code == 0, (summary["problems"], stderr[-1500:])
    assert summary["evidence_mutations"]["detected"] == summary["evidence_mutations"]["defined"] >= 25
    assert summary["positive_controls"]["accepted"] == summary["positive_controls"]["total"] >= 8
    assert summary["git_status_app_data_tools"]["empty"] is True


def test_committed_evidence_mutation_results():
    rows = read_csv("mutation_results.csv")
    assert len(rows) >= 25 and all(r["detected"] == "TRUE" for r in rows)
    contracts = {r["contract"] for r in rows}
    for needed in ("alvos", "nós", "transferências", "estado", "temporal", "reexecução", "determinismo",
                   "não-regressão", "proveniência", "contrato de resultado"):
        assert any(c.startswith(needed) for c in contracts), needed
    controls = read_csv("positive_controls.csv")
    assert controls and all(c["result"] == "ACCEPT" for c in controls)


def test_committed_code_mutants_all_detected_in_temporary_copies():
    summary = json.loads((EVIDENCE / "mutation_summary.json").read_text(encoding="utf-8"))
    assert summary["result"] == "PASS" and summary["label"] == "REAL_DERIVED_TEST_RESULT"
    cm = summary["code_mutants"]
    assert cm["surviving"] == 0 and cm["surviving_ids"] == [] and cm["detected"] == cm["introduced"] >= 11
    assert cm["positive_control"]["result"] == "ACCEPT"
    assert cm["repository_untouched"] is True and cm["expected_detectors_missed"] == {}
    assert summary["detection_rate"] == "100.0%"
    rows = {r["mutant_id"]: r for r in read_csv("code_mutation_results.csv")}
    for mutant_id in MINIMUM:
        assert rows[mutant_id]["detected"] == "TRUE" and rows[mutant_id]["result"] == "PASS"


def test_minimum_mutant_set_is_defined_and_applies_to_unique_snippets():
    defined = {m[0]: m for m in code_mutants_4a.CODE_MUTANTS}
    assert set(MINIMUM) <= set(defined)
    for mutant_id, (_id, _desc, relative, old, _new, expected) in defined.items():
        assert expected and set(expected) <= {"ORACLE", "INTEGRATED_4A", "CONTRACT_4A", "TESTS"}
        if callable(old):
            continue
        data = (REPO / relative).read_bytes()
        snippet = old.encode()
        if b"\r\n" in data:
            snippet = snippet.replace(b"\n", b"\r\n")
        assert data.count(snippet) == 1, mutant_id


def test_mutants_never_touch_the_working_tree():
    out = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    assert out == ""
