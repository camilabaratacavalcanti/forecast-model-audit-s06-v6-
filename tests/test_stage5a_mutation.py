"""
Stage 5A.4 — evidência de mutação dos contratos da 5A (`audit/stage5a/mutation/`).

A execução completa (13 mutantes em clones temporários) é `python audit/stage5a/mutation/run_mutation_5a.py`.
Aqui, sem reexecutar: o resumo versionado é PASS com 100%, controle positivo aceito e `app/ data/ tools/`
intactos; os 7 mutantes exigidos pelo prompt da 5A estão na tabela; e todo teste-alvo existe (coleta).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "audit" / "stage5a" / "mutation"
sys.path.insert(0, str(HERE))

import run_mutation_5a as harness  # noqa: E402

REQUIRED = {"EQ-01", "EQ-02", "LED-01", "SUM-01", "RT-01", "SPEC-01", "VAR-01"}   # + UNIT-01..06


def test_committed_mutation_summary_is_a_full_pass():
    summary = json.loads((HERE / "mutation_summary.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((HERE / "mutation_results.csv").open(encoding="utf-8")))
    assert summary["result"] == "PASS" and summary["missed"] == [] and summary["detection_rate"] == "100.0%"
    assert summary["positive_control"]["result"] == "ACCEPT"
    assert summary["git_status_app_data_tools"]["empty"] is True
    assert {r["mutant_id"] for r in rows} == {m[0] for m in harness.MUTANTS}
    assert all(r["detected"] == "TRUE" and r["apply_error"] == "" for r in rows)


def test_every_required_mutant_is_in_the_table():
    ids = {m[0] for m in harness.MUTANTS}
    assert REQUIRED <= ids
    assert {f"UNIT-0{i}" for i in range(1, 7)} <= ids


def test_every_target_test_exists():
    targets = sorted({t for m in harness.MUTANTS for t in m[4]})
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *targets],
                          cwd=REPO, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
