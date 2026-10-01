"""
Stage 4B.3b — mutação e controles temporais (REAL_DERIVED_TEST_RESULT).

Provam que os auditores da 4B detectam 100% das mutações de evidência (controles positivos
aceitos), que os mutantes de código temporais foram todos detectados em cópias temporárias
(evidência versionada) e que a árvore de trabalho nunca foi tocada. Os mutantes de código não
são reexecutados aqui (custo ~20 min).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MUTATION = REPO / "audit" / "stage4b" / "mutation"
EVIDENCE = MUTATION / "evidence"
sys.path.insert(0, str(MUTATION))

import code_mutants_4b  # noqa: E402

REQUIRED = {"CM4B-01": "YTD", "CM4B-02": "off-by-one", "CM4B-03": "period_id anual", "CM4B-04": "bissexto",
            "CM4B-05": "MOVING_AVERAGE", "CM4B-06": "snapshot", "CM4B-07": "carry-over", "CM4B-08": "estado anual"}


def read_csv(name):
    return list(csv.DictReader((EVIDENCE / name).open(encoding="utf-8")))


@pytest.fixture(scope="module")
def live():
    completed = subprocess.run([sys.executable, str(MUTATION / "run_mutation_4b.py"), "--no-write",
                                "--skip-code-mutants"], cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_evidence_mutations_detected_and_controls_accepted(live):
    code, summary, stderr = live
    assert code == 0, (summary["problems"], stderr[-1500:])
    assert summary["evidence_mutations"]["detected"] == summary["evidence_mutations"]["defined"] >= 19
    assert summary["positive_controls"]["accepted"] == summary["positive_controls"]["total"] >= 12
    assert summary["git_status_app_data_tools"]["empty"] is True


def test_committed_evidence_mutations_cover_every_temporal_contract():
    rows = read_csv("mutation_results.csv")
    assert all(r["detected"] == "TRUE" for r in rows)
    contracts = {r["contract"].split(" ")[0] for r in rows}
    for needed in ("identidades", "janelas", "MOVING_AVERAGE", "snapshots", "períodos", "agregação", "estado",
                   "reexecução", "determinismo", "invariante", "cobertura", "proveniência"):
        assert needed in contracts, needed
    assert all(c["result"] == "ACCEPT" for c in read_csv("positive_controls.csv"))


def test_committed_code_mutants_all_detected():
    summary = json.loads((EVIDENCE / "mutation_summary.json").read_text(encoding="utf-8"))
    assert summary["result"] == "PASS" and summary["detection_rate"] == "100.0%"
    cm = summary["code_mutants"]
    assert cm["surviving"] == 0 and cm["detected"] == cm["introduced"] == len(REQUIRED)
    assert cm["positive_control"]["result"] == "ACCEPT" and cm["repository_untouched"] is True
    assert cm["expected_detectors_missed"] == {}
    rows = {r["mutant_id"]: r for r in read_csv("code_mutation_results.csv")}
    assert set(rows) == set(REQUIRED) and all(r["result"] == "PASS" for r in rows.values())


def test_required_mutants_apply_to_unique_snippets():
    defined = {m[0]: m for m in code_mutants_4b.CODE_MUTANTS}
    assert set(defined) == set(REQUIRED)
    for mutant_id, (_id, _d, relative, old, _new, expected) in defined.items():
        data = (REPO / relative).read_bytes()
        snippet = old.encode()
        if b"\r\n" in data:
            snippet = snippet.replace(b"\n", b"\r\n")
        assert data.count(snippet) == 1, mutant_id
        assert expected and set(expected) <= set(code_mutants_4b.DETECTORS)


def test_working_tree_untouched():
    out = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    assert out == ""
