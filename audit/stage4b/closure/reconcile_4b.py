"""
Stage 4B.4 — reconciliação INDEPENDENTE das expectativas temporais (REAL_DERIVED_TEST_RESULT).

    python -I audit/stage4b/closure/reconcile_4b.py [--no-write]

Não importa `app/`, `tools/` nem os harnesses: recalcula cada expectativa só com `datetime`/`calendar`
(`independent_calendar.py`) e lê os ARQUIVOS de evidência da 4B (CSV/JSON), confrontando linha a linha.
Escreve `closure_reconciliation_4b.json` (sem `--no-write`).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
sys.path.insert(0, str(STAGE))

import independent_calendar as cal  # noqa: E402  (puro)

TEMPORAL = STAGE / "temporal" / "evidence"
BASELINE = "0a924e66cfd0774a13e46a332b460b770283a554"
PENDING_ITEMS = "audit/stage3_4/PLATFORM_PENDING_ITEMS.md"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows_of(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def main() -> int:
    lines = []

    def line(row_id, quantity, expected, recomputed, source):
        lines.append({"id": row_id, "quantity": quantity, "expected": expected, "recomputed": recomputed,
                      "source": source, "result": "PASS" if expected == recomputed else "FAIL"})

    for label in ("T1", "T2", "T3"):
        days = cal.days(*cal.RANGES[label])
        summary = load(TEMPORAL / label / "temporal_summary.json")
        ids = rows_of(TEMPORAL / label / "identities_by_date.csv")
        cov = rows_of(TEMPORAL / label / "temporal_coverage.csv")
        line(f"{label}-01", "datas executadas", len(days), len(cov), "temporal_coverage.csv")
        line(f"{label}-02", "datas na ordem do calendário", [d.isoformat() for d in days], [r["date"] for r in cov],
             "temporal_coverage.csv")
        line(f"{label}-03", "janelas mensais por data = dia do mês", [cal.expected_windows(d)["monthly"] for d in days],
             [int(r["monthly_windows_each"]) for r in ids], "identities_by_date.csv")
        line(f"{label}-04", "janelas anuais por data = dia do ano", [cal.expected_windows(d)["annual"] for d in days],
             [int(r["annual_windows_each"]) for r in ids], "identities_by_date.csv")
        line(f"{label}-05", "crescimento do store = previsto", 0,
             sum(r["new_keys"] != r["expected_new_keys"] for r in ids), "identities_by_date.csv")
        line(f"{label}-06", "alvos/nós/eventos/transferências por data", {"446|458|896|67"},
             {f"{r['targets']}|{r['nodes']}|{r['events']}|{r['transfer_events']}" for r in cov}, "temporal_coverage.csv")
        line(f"{label}-07", "fins de mês", [d.isoformat() for d in days if cal.expected_windows(d)["month_end"]],
             summary["month_ends"], "temporal_summary.json")
        snaps = load(TEMPORAL / label / "period_snapshots.json")
        line(f"{label}-08", "períodos encerrados inalterados", len(snaps), sum(v["unchanged"] for v in snaps.values()),
             "period_snapshots.json")
        line(f"{label}-09", "resultado do harness", "PASS", summary["result"], "temporal_summary.json")
        line(f"{label}-10", "razão de desempenho <= 3,0", True, summary["performance"]["ratio_last_over_first"] <= 3.0,
             "temporal_summary.json")
    t1 = {r["date"]: r for r in rows_of(TEMPORAL / "T1" / "identities_by_date.csv")}
    t3 = {r["date"]: r for r in rows_of(TEMPORAL / "T3" / "identities_by_date.csv")}
    line("V-01", "365 janelas anuais em 2026-12-31 (T1)", "365", t1["2026-12-31"]["annual_windows_each"], "T1")
    line("V-02", "2027 nasce com 1 janela (T1)", "1", t1["2027-01-01"]["annual_windows_each"], "T1")
    line("V-03", "365 janelas em 2027-12-31 e 60 em 2028-02-29 (T3)", ["365", "60", "29"],
         [t3["2027-12-31"]["annual_windows_each"], t3["2028-02-29"]["annual_windows_each"],
          t3["2028-02-29"]["monthly_windows_each"]], "T3")
    line("V-04", "snapshot de 2026 inalterado (T1)", True, load(TEMPORAL / "T1" / "period_snapshots.json")["2026"]["unchanged"],
         "T1 period_snapshots.json")
    for label in ("T1", "T3"):
        prefix = load(TEMPORAL / label / "temporal_summary.json")["prefix_invariant"]
        line(f"P-{label}", f"invariante de prefixo ({label}) x 4A", [0, prefix["reference_4a_store_sha256"]],
             [prefix["differences"], prefix["prefix_subset_sha256"]], "temporal_summary.json")
    a4 = load(REPO / "audit/stage4a/integrated/evidence/integrated_summary.json")["determinism"]["RUN_A"]["store_sha256"]
    line("P-4A", "referência do prefixo = store_sha256 versionado da 4A", a4,
         load(TEMPORAL / "T1" / "temporal_summary.json")["prefix_invariant"]["reference_4a_store_sha256"], "4A")
    for label, configs in (("T1", {"RUN_A", "RUN_B"}), ("T2", {"RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B"})):
        det = load(TEMPORAL / label / "temporal_summary.json")["determinism"]
        line(f"D-{label}", f"determinismo {label}: configurações e hash único", [sorted(configs), 1, 1],
             [sorted(det), len({r["results_sha256"] for r in det.values()}), len({r["store_sha256"] for r in det.values()})],
             "temporal_summary.json")
    reex = load(TEMPORAL / "T1" / "reexecution.json")
    line("R-01", "reexecução T1 (02-28, 12-31, 01-01): store igual e UNCHANGED", [True] * 3,
         [reex[d]["same_store"] and reex[d]["transfer_statuses"] == {"UNCHANGED": 67} for d in
          ("2026-02-28", "2026-12-31", "2027-01-01")], "T1 reexecution.json")
    line("R-02", "conflito de entrada a montante", "INTERBLOCK_CONSUMER_VALUE_CONFLICT",
         reex["conflict_on_changed_upstream_input"]["error"], "T1 reexecution.json")
    line("R-03", "E3 na virada: falha explícita", "VariableNotFoundError", reex["missing_new_year_input"]["error"]["type"],
         "T1 reexecution.json")
    state = load(TEMPORAL / "T1" / "state_scenarios.json")
    line("S-01", "estado ao longo do ano / entre anos", [[], True], [state["problems"], state["l4_l5_2026_keys_identical_to_clean"]],
         "T1 state_scenarios.json")
    oracle = load(STAGE / "oracle" / "evidence" / "oracle_temporal_summary.json")
    line("O-01", "oracle: agregações recalculadas (T1 + T2)", 417 * 396 + 417 * 62,
         oracle["by_range"]["T1"]["compared"] + oracle["by_range"]["T2"]["compared"], "oracle_temporal_summary.json")
    line("O-02", "oracle: concordância e bit a bit", [oracle["compared"]] * 2, [oracle["agree"], oracle["bitwise_equal"]],
         "oracle_temporal_summary.json")
    mutation = load(STAGE / "mutation" / "evidence" / "mutation_summary.json")
    line("M-01", "mutações de evidência detectadas", mutation["evidence_mutations"]["defined"],
         mutation["evidence_mutations"]["detected"], "mutation_summary.json")
    line("M-02", "mutantes de código detectados", mutation["code_mutants"]["introduced"], mutation["code_mutants"]["detected"],
         "mutation_summary.json")
    line("M-03", "controles positivos", mutation["positive_controls"]["total"] + 1,
         mutation["positive_controls"]["accepted"] + (mutation["code_mutants"]["positive_control"]["result"] == "ACCEPT"),
         "mutation_summary.json")
    independent = json.loads(subprocess.run([sys.executable, "-I", str(STAGE / "independent_calendar.py"), "--check"],
                                            cwd=REPO, capture_output=True, text=True).stdout)
    line("C-01", "ciclos no nível de instância / variável", [[], []],
         [independent["cycles"]["instance_cycles"], independent["cycles"]["variable_cycles"]], "independent_calendar.py")
    line("C-02", "ciclo entre blocos", [["production", "yield"]], independent["cycles"]["block_cycles"], "independent_calendar.py")
    changed = subprocess.run(["git", "diff", "--name-only", BASELINE], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.split()
    line("G-01", "fora de audit/stage4b e tests/test_stage4b_* só a adição datada da lista mestre", [],
         [p for p in changed if not p.startswith(("audit/stage4b/", "tests/test_stage4b_")) and p != PENDING_ITEMS],
         "git diff")
    old = subprocess.run(["git", "show", f"{BASELINE}:{PENDING_ITEMS}"], cwd=REPO, capture_output=True, check=True).stdout
    line("G-02", "lista mestre alterada só por adição", True, (REPO / PENDING_ITEMS).read_bytes().startswith(old), "git show")
    imported = sorted(m for m in sys.modules if m == "app" or m.startswith(("app.", "tools")))
    problems = [f"{r['id']} {r['quantity']}: {str(r['recomputed'])[:120]} != {str(r['expected'])[:120]}"
                for r in lines if r["result"] != "PASS"]
    if imported:
        problems.append(f"INDEPENDENCE_FAILURE {imported}")
    out = {"label": "REAL_DERIVED_TEST_RESULT", "lines": lines, "passed": sum(r["result"] == "PASS" for r in lines),
           "total": len(lines), "imports_app_or_tools": imported, "problems": problems,
           "result": "PASS" if not problems else "FAIL"}
    if "--no-write" not in sys.argv[1:]:
        (HERE / "closure_reconciliation_4b.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str)
                                                             + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("passed", "total", "problems", "result")}, indent=1, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
