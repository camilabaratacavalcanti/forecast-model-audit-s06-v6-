"""
Stage 4A.3a — oracle de fidelidade ao workbook A41 v9 (REAL_DERIVED_TEST_RESULT).

O oracle (`audit/stage4a/oracle/oracle_a41.py`) é Python puro, reescrito do texto do
workbook, sem importar app/. Os testes provam: 20/20 equações e as 25 combinações de
`hes` por grupo concordam com o engine (tolerância DR-4A-7); a guarda do texto detecta
um workbook divergente; e o confronto DETECTA um desvio (o oracle não é vacuamente verde).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STAGE = REPO / "audit" / "stage4a"
ORACLE = STAGE / "oracle"
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(ORACLE))

import common  # noqa: E402
import oracle_a41 as oracle  # noqa: E402
import run_oracle  # noqa: E402

F_COMBINATIONS = sorted([["Normal", "1 By pass e LC"], ["1 By pass e LC", "Normal"]])


@pytest.fixture(scope="module")
def live():
    completed = subprocess.run([sys.executable, str(ORACLE / "run_oracle.py"), "--no-write"],
                               cwd=REPO, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout), completed.stderr


def test_live_oracle_agrees_with_engine_on_20_equations_and_25_hes_combinations(live):
    code, summary, stderr = live
    assert code == 0, (summary["problems"][:5], stderr[-1500:])
    assert summary["result"] == "PASS" and summary["equations_covered"] == 20
    assert summary["agree"] == summary["compared"] > 4000
    for group in ("L4_L5", "L6_L7"):
        assert summary["hes_coverage"][group]["combinations"] == 25
        assert sorted(summary["hes_coverage"][group]["no_applicable_rule"]) == F_COMBINATIONS
    modes = summary["by_mode"]
    for mode in ("equation", "chain", "integrated_daily", "integrated_aggregation", "integrated_aggregation_with_F"):
        assert modes[mode]["compared"] > 0 and modes[mode]["agree"] == modes[mode]["compared"]


def test_committed_oracle_summary_declares_tolerance_and_limitations():
    summary = json.loads((ORACLE / "evidence" / "oracle_summary.json").read_text(encoding="utf-8"))
    assert summary["label"] == "REAL_DERIVED_TEST_RESULT" and summary["result"] == "PASS"
    assert summary["oracle"] == "INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)"
    assert summary["tolerance"]["rel_tol"] == 1e-12 and summary["tolerance"]["abs_tol"] == 1e-12
    assert any("não correção de negócio" in x for x in summary["limitations"])
    assert any("leitura do workbook" in x for x in summary["limitations"])
    assert summary["workbook_text_guard"] == "PASS"
    per_equation = summary["per_equation"]
    assert sorted(per_equation) == [f"EQ{16000 + i}" for i in range(1, 21)]
    assert all(e["agree"] == e["cases"] for e in per_equation.values())
    for eq in ("EQ16001", "EQ16002", "EQ16003", "EQ16007", "EQ16008", "EQ16009"):
        assert per_equation[eq]["failure"] >= 3                      # ln fora do domínio previsto e observado
    for eq in ("EQ16013", "EQ16016", "EQ16019"):
        assert per_equation[eq]["failure"] >= 2                      # divisão por zero prevista e observada
    assert per_equation["EQ16011"]["state"] == per_equation["EQ16012"]["state"] == 6   # 2 combinações x 3 casos
    assert summary["aggregation_windows_compared"] == {"anual": 352, "mensal": 352}


def test_oracle_module_is_pure_python_without_app():
    assert run_oracle.oracle_is_pure() == []
    probe = ("import sys; sys.path.insert(0, %r); import oracle_a41; "
             "print(sorted(m for m in sys.modules if m == 'app' or m.startswith(('app.', 'tools'))))" % str(ORACLE))
    out = subprocess.run([sys.executable, "-I", "-c", probe], cwd=REPO, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_workbook_text_guard_detects_a_divergent_transcription(monkeypatch):
    assert oracle.check_workbook_text() == []
    key = ("lth_grupo", "L6_L7")
    monkeypatch.setitem(oracle.WORKBOOK_TEXT, key, "( lth@L6 + lth@L7 ) /3")
    problems = oracle.check_workbook_text()
    assert len(problems) == 1 and "ORACLE_STALE" in problems[0] and "L6_L7" in problems[0]


def test_oracle_literal_branches_precedence_and_41d_only_in_l4_l5():
    ltp, lth = 3.0, 2.0
    base = 100 - ((ltp - lth) * 2)
    g45, g67 = oracle.retirada_condensado_grupo_l4_l5, oracle.retirada_condensado_grupo_l6_l7
    assert g45(ltp, lth, "1 By pass", "Normal", 3.0, 5.0) == base - 5.0          # 41d
    assert g67(ltp, lth, "1 By pass", "Normal", 3.0) == base - 3.0               # 41c
    assert g45(ltp, lth, "LC", "Overhaul/Parada", 3.0, 5.0) == g45(ltp, lth, "LC", "LC", 3.0, 5.0)
    assert g45(ltp, lth, "Overhaul/Parada", "1 By pass", 3.0, 5.0) == 50 - ((ltp - lth) * 2)
    assert g45(ltp, lth, "Normal", "1 By pass e LC", 3.0, 5.0) == "F"
    assert oracle.declared("F") == oracle.Stated("NO_APPLICABLE_RULE")


def test_negative_oracle_detects_a_deviating_engine_behaviour(monkeypatch):
    """Se o comportamento divergir (aqui: o oracle trocado para 41c no ramo 1 By pass de L4_L5), o confronto falha."""
    original = oracle.retirada_condensado_grupo_l4_l5

    def deviated(ltp, lth, a, b, d41c, d41d):
        return original(ltp, lth, a, b, d41c, d41c)
    monkeypatch.setattr(oracle, "retirada_condensado_grupo_l4_l5", deviated)
    universe = common.Universe("A")
    ids = run_oracle.identity_map(universe.orchestrator)
    _rows, problems = run_oracle.run_equation_grid(universe.orchestrator, ids, random.Random(4242))
    assert problems and all("EQ16011" in p for p in problems)


def test_negative_oracle_detects_a_wrong_failure_prediction(monkeypatch):
    original = oracle.ln

    def lenient_ln(x, where):
        return original(abs(x) or 1.0, where)
    monkeypatch.setattr(oracle, "ln", lenient_ln)
    universe = common.Universe("A")
    ids = run_oracle.identity_map(universe.orchestrator)
    _rows, problems = run_oracle.run_equation_grid(universe.orchestrator, ids, random.Random(4242))
    assert any("EQ16001" in p and "LN_DOMAIN" in p for p in problems)
