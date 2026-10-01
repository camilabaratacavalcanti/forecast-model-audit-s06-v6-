"""
Stage 4B.4 — fechamento (REAL_DERIVED_TEST_RESULT).

Provam a reconciliação independente (python -I, sem app/), a superfície de produção e as
stages anteriores intactas, a adição append-only à lista mestre e o conteúdo obrigatório do
fechamento (gate de 16 critérios, E1–E5, ciclos, limitações, comandos).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4b"
BASELINE = "0a924e66cfd0774a13e46a332b460b770283a554"
PENDING = "audit/stage3_4/PLATFORM_PENDING_ITEMS.md"


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def test_independent_reconciliation_passes_without_app():
    completed = subprocess.run([sys.executable, "-I", str(STAGE / "closure" / "reconcile_4b.py"), "--no-write"],
                               cwd=REPO, capture_output=True, text=True)
    out = json.loads(completed.stdout)
    assert completed.returncode == 0, out["problems"]
    committed = json.loads((STAGE / "closure" / "closure_reconciliation_4b.json").read_text(encoding="utf-8"))
    assert committed["result"] == "PASS" and committed["imports_app_or_tools"] == []
    assert committed["passed"] == committed["total"] == out["total"] >= 40


def test_production_surface_and_previous_stages_untouched():
    assert git("diff", "--stat", BASELINE, "--", "app", "data", "tools") == ""
    changed = [p for p in git("diff", "--name-only", BASELINE).split()
               if not p.startswith(("audit/stage4b/", "tests/test_stage4b_"))]
    assert changed == [PENDING]
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "audit/stage3_4", "audit/stage4a")
    assert untracked == ""


def test_pending_items_dated_addition_is_append_only():
    old = git("show", f"{BASELINE}:{PENDING}")
    text = (REPO / PENDING).read_text(encoding="utf-8")
    assert text.startswith(old)
    addition = text[len(old):]
    assert "Adição datada" in addition and "Stage 4B" in addition
    for token in ("cobertura anual", "virada de ano", "ciclos", "lacunas", "ano fiscal"):
        assert token in addition, token


def test_final_closure_document_and_gate():
    text = (STAGE / "STAGE_4B_FINAL_CLOSURE.md").read_text(encoding="utf-8")
    assert "FINAL_STAGE_4B_GATE = PASS" in text or ("FINAL_STAGE_4B_GATE = READY_FOR_DECISION" in text and "F4B-06" in text)
    for token in ("REAL_DERIVED_TEST_RESULT", "E1", "E2", "E3", "E4", "E5", "T1", "T2", "T3", "792",
                  "ACÍCLICO", "EXPLICIT_FAILURE", "não correção de negócio", "first_round_analysis.json",
                  "reconcile_4b.py", "run_temporal_4b.py", "F4B-01", "F4B-02"):
        assert token in text, token
    for criterion in range(1, 17):
        assert f"| {criterion} |" in text
