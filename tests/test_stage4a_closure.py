"""
Stage 4A.4 — fechamento (REAL_DERIVED_TEST_RESULT).

Provam a reconciliação independente das cardinalidades (sem importar app/), o protocolo
L8 (3.4C preservada e comparada; só o area_41 mudou), a superfície de produção e a
Stage 3 intactas, a adição append-only à lista mestre de pendências e o conteúdo
obrigatório do fechamento (gate, limitações do oracle, gancho do Excel).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4a"
BASELINE = "d2847ab36933668bf4a1299b3ffe058827a82037"


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def test_independent_reconciliation_passes_without_app():
    completed = subprocess.run([sys.executable, "-I", str(STAGE / "closure" / "reconcile_4a.py"), "--no-write"],
                               cwd=REPO, capture_output=True, text=True)
    out = json.loads(completed.stdout)
    assert completed.returncode == 0, out["problems"]
    assert out["passed"] == out["total"] >= 42
    committed = json.loads((STAGE / "closure" / "closure_reconciliation_4a.json").read_text(encoding="utf-8"))
    assert committed["result"] == "PASS" and committed["imports_app_or_tools"] == []
    assert committed["passed"] == committed["total"] == out["total"]


def test_l8_comparison_only_area_41_changed():
    l8 = json.loads((STAGE / "closure" / "closure_reconciliation_4a.json").read_text(encoding="utf-8"))["l8_comparison"]
    changed, unchanged = l8["changed_only_by_area_41"], l8["unchanged"]
    assert (changed["targets"]["3.4C"], changed["targets"]["4A"]) == (421, 446)
    assert all(t.startswith("VAR160") for t in changed["targets"]["added"]) and len(changed["targets"]["added"]) == 25
    assert changed["nodes"]["added_blocks"] == {"area_41": 31}
    assert changed["transfers"]["added"] == ["TRANSFER:VAR16007"]
    assert all(unchanged[k] is True for k in ("targets_final_results_identical", "nodes_relative_order_identical",
                                               "transfers_identical", "store_4_blocks_sha256_identical",
                                               "fixture_graph_hash_identical"))
    assert unchanged["removed_targets"] == []
    assert l8["historical_paths_changed_since_baseline"] == [] and l8["pending_items_append_only"] is True
    report = (STAGE / "closure" / "evidence_regeneration_report.md").read_text(encoding="utf-8")
    assert "L8 (3.4C x 4A): PASS" in report


def test_production_surface_and_stage_3_closure_untouched():
    assert git("diff", "--stat", BASELINE, "--", "app", "data", "tools") == ""
    assert git("diff", "--stat", BASELINE, "--", "audit/stage3_4/STAGE_3_FINAL_CLOSURE.md") == ""
    changed = [p for p in git("diff", "--name-only", BASELINE).split() if not p.startswith(("audit/stage4a/", "tests/test_stage4a_"))]
    assert changed == ["audit/stage3_4/PLATFORM_PENDING_ITEMS.md"]


def test_pending_items_dated_addition_keeps_f01_f02_open_and_f03_partial():
    text = (REPO / "audit" / "stage3_4" / "PLATFORM_PENDING_ITEMS.md").read_text(encoding="utf-8")
    old = git("show", f"{BASELINE}:audit/stage3_4/PLATFORM_PENDING_ITEMS.md")
    assert text.startswith(old)                                         # append-only
    addition = text[len(old):]
    assert "Adição datada — 2026-10-01: Stage 4A" in addition
    assert "F-01" in addition and "16 vínculos `PENDING_LOAD`" in addition and "continua aberto" in addition
    assert "F-02" in addition and "**parcialmente atendido**" in addition and "D-TAX-02" in addition


def test_excel_hook_defines_extract_format_without_values():
    hook = (STAGE / "oracle" / "EXCEL_COMPARISON_HOOK.md").read_text(encoding="utf-8")
    assert "variavel,variable_id,scope_type,scope_value,frequencia,data,periodo,valor,estado,celula_origem" in hook
    assert "nenhum valor foi inventado" in hook and "Forecast A41" in hook


def test_final_closure_document_and_gate():
    text = (STAGE / "STAGE_4A_FINAL_CLOSURE.md").read_text(encoding="utf-8")
    assert "FINAL_STAGE_4A_GATE = PASS" in text
    for token in ("REAL_DERIVED_TEST_RESULT", "INDEPENDENT_NUMERIC_ORACLE = PARTIAL",
                  "não correção de negócio", "compartilha com o engine a leitura do workbook",
                  "F4A-01", "N1", "N8", "OBS", "L10", "reconcile_4a.py", "run_integrated_4a.py"):
        assert token in text, token
    for criterion in range(1, 13):
        assert f"| {criterion} |" in text
