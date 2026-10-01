"""
Stage 4A.4 — reconciliação INDEPENDENTE das cardinalidades e comparação formal 3.4C x 4A (protocolo L8).

    python -I audit/stage4a/closure/reconcile_4a.py [--no-write]

Não importa `app/`, `tools/` nem os harnesses: recalcula cada cardinalidade a partir dos
ARQUIVOS de evidência (CSV/JSON) e do recálculo estrutural independente
(`independent_count.py`, também sem app), e confronta com as expectativas do contrato 4A.
Escreve `closure_reconciliation_4a.json` (sem `--no-write`).

L8: compara a evidência versionada da 3.4C (só leitura) com a da 4A:
    mudou     -> apenas a inclusão do area_41 (alvos, nós, transferência, eventos, identidades);
    não mudou -> os 421 alvos (resultado final), os 427 nós (ordem relativa), as 12 transferências,
                 o store dos 4 blocos (hash) e o grafo do fixture.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
S34 = REPO / "audit" / "stage3_4" / "integrated" / "evidence"
S4A = STAGE / "integrated" / "evidence"
EXPECTED = json.loads((STAGE / "contract_expectations.json").read_text(encoding="utf-8"))
BASELINE = "d2847ab36933668bf4a1299b3ffe058827a82037"          # HEAD da Fase 0
PENDING_ITEMS = "audit/stage3_4/PLATFORM_PENDING_ITEMS.md"     # única adição autorizada fora de stage4a (§6.4)


def append_only(relative: str) -> bool:
    """O conteúdo do baseline é prefixo exato do conteúdo atual (adição datada, sem reescrita)."""
    old = subprocess.run(["git", "show", f"{BASELINE}:{relative}"], cwd=REPO, capture_output=True, check=True).stdout
    return (REPO / relative).read_bytes().startswith(old)


def rows_of(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    independent = json.loads(subprocess.run([sys.executable, "-I", str(STAGE / "independent_count.py"), "--check"],
                                            cwd=REPO, capture_output=True, text=True).stdout)
    t34, t4a = rows_of(S34 / "targets.csv"), rows_of(S4A / "targets.csv")
    n34, n4a = rows_of(S34 / "nodes.csv"), rows_of(S4A / "nodes.csv")
    tr34, tr4a = rows_of(S34 / "transfers.csv"), rows_of(S4A / "transfers.csv")
    cov34, cov4a = rows_of(S34 / "temporal_coverage.csv"), rows_of(S4A / "temporal_coverage.csv")
    s34, s4a = load(S34 / "integrated_summary.json"), load(S4A / "integrated_summary.json")
    nonreg = load(S4A / "non_regression_421.json")
    oracle = load(STAGE / "oracle" / "evidence" / "oracle_summary.json")
    mutation = load(STAGE / "mutation" / "evidence" / "mutation_summary.json")
    contract = load(STAGE / "evidence" / "contract_audit.json")
    exp = EXPECTED["integrated"]
    u5 = independent["universe_5"]

    lines = []

    def line(row_id, quantity, expected, recomputed, source):
        lines.append({"id": row_id, "quantity": quantity, "expected": expected, "recomputed": recomputed,
                      "source": source, "result": "PASS" if expected == recomputed else "FAIL"})

    # universo
    line("R01", "alvos integrados", exp["integrated_targets"], len(t4a), "integrated/evidence/targets.csv")
    line("R02", "alvos do area_41", exp["area_41_targets"], sum(r["block"] == "area_41" for r in t4a), "targets.csv")
    line("R03", "alvos por bloco (independente)", u5["targets_by_block"],
         dict(Counter(r["block"] for r in t4a)), "independent_count.py x targets.csv")
    line("R04", "nós do plano", exp["planner_nodes"], len(n4a), "integrated/evidence/nodes.csv")
    line("R05", "nós por tipo", exp["nodes_by_kind"], dict(sorted(Counter(r["kind"] for r in n4a).items())), "nodes.csv")
    line("R06", "nós por tipo (independente)", u5["nodes_by_kind"], dict(sorted(Counter(r["kind"] for r in n4a).items())),
         "independent_count.py x nodes.csv")
    line("R07", "nós = união (427 + 33 − 2)", independent["union"]["union"],
         sum(r["in_stage_3_4c_plan"] == "True" for r in n4a) + independent["union"]["nodes_area_41_only"]
         - len(independent["union"]["shared"]),
         "nodes.csv + independent_count.py")
    line("R08", "transferências (vínculos usados)", len(exp["transfers"]), len(tr4a), "integrated/evidence/transfers.csv")
    line("R09", "transferência VAR16007 executada e verificada", 32 * 7,
         int(next(r for r in tr4a if r["node"] == "TRANSFER:VAR16007")["verified_events"]), "transfers.csv")
    line("R10", "eventos por data (32 datas)", [exp["events_per_date"]] * 32, [int(r["events"]) for r in cov4a],
         "temporal_coverage.csv")
    line("R11", "eventos de transferência por data", [exp["transfer_events_per_date"]] * 32,
         [int(r["transfer_events"]) for r in cov4a], "temporal_coverage.csv")
    line("R12", "entradas livres (independente)", exp["required_inputs"], u5["required_inputs"], "independent_count.py")
    line("R13", "nós executados em 32 datas", exp["planner_nodes"],
         sum(r["dates_executed"] == "32" and r["execution_status"] == "EXECUTED" for r in n4a), "nodes.csv")
    # plano oficial e proveniência
    line("R14", "plano oficial area_41 (OK / bloqueados)", EXPECTED["independent"]["official_plan.area_41"],
         independent["official_plan"]["area_41"], "independent_count.py x plan_evidence.csv")
    line("R15", "plano oficial x plan_evidence.csv (diferenças)", [], independent["official_plan"]["differences_vs_plan_evidence"],
         "independent_count.py")
    line("R16", "PENDING_LOAD oficiais", 16, independent["official_plan"]["pending_links"], "interblock_links.json")
    line("R17", "sha256 de interblock_links.json", exp["interblock_links_sha256"], independent["interblock_links_sha256"],
         "interblock_links.json")
    # não-regressão
    line("R18", "não-regressão: hash do subconjunto == 3.4C", s34["determinism"]["RUN_A"]["store_sha256"],
         nonreg["subset_store_sha256"], "non_regression_421.json x 3.4C integrated_summary.json")
    line("R19", "não-regressão: diferenças em chaves dos 4 blocos", 0, nonreg["differences"], "non_regression_421.json")
    line("R20", "não-regressão: alvos 3.4C com resultado final diferente", 0,
         sum(1 for a, b in zip(sorted(t34, key=lambda r: r["target"]),
                               sorted((r for r in t4a if r["block"] != "area_41"), key=lambda r: r["target"]))
             if (a["target"], a["final_results_2026-02-01"]) != (b["target"], b["final_results_2026-02-01"])),
         "3.4C targets.csv x 4A targets.csv")
    # temporal, reexecução, determinismo
    temporal = s4a["temporal"]
    line("R21", "identidades mensais de janeiro (3.4C + 11)", s34["temporal"]["monthly_jan_identities"] + 11,
         temporal["monthly_jan_identities"], "integrated_summary.json (3.4C x 4A)")
    line("R22", "identidades anuais YTD (3.4C + 11)", s34["temporal"]["annual_ytd_identities"] + 11,
         temporal["annual_ytd_identities"], "integrated_summary.json (3.4C x 4A)")
    line("R23", "janelas 31 (mensal jan) e 32 (anual)", [True, True],
         [temporal["monthly_jan_all_31_windows"], temporal["annual_ytd_all_32_windows"]], "integrated_summary.json")
    line("R24", "reexecução: transferências WRITTEN -> UNCHANGED", [{"UNCHANGED": 67}] * 2,
         [v["transfer_statuses"] for v in s4a["reexecution"].values()], "integrated_summary.json")
    det = s4a["determinism"]
    line("R25", "determinismo: hashes idênticos (4 execuções + reexecução)", 1,
         len({det[k]["results_sha256"] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")})
         * len({det[k]["store_sha256"] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")} | {det["REEXECUTION"]["store_sha256"]}),
         "integrated_summary.json")
    # estado
    state = s4a["state"]
    line("R26", "cenários de estado do area_41 sem problema", 6,
         sum(1 for k, v in state.items() if k.startswith("SA") and isinstance(v, dict) and v.get("problems") == []),
         "integrated_summary.json state")
    line("R27", "composições indefinidas = erro do contrato", 3,
         sum(c["error"] == c["expected"] for c in state["SA6_undefined_compositions"].values()), "integrated_summary.json")
    # oracle
    line("R28", "oracle: equações cobertas", 20, oracle["equations_covered"], "oracle_summary.json")
    line("R29", "oracle: combinações de hes por grupo", [25, 25],
         [oracle["hes_coverage"][g]["combinations"] for g in ("L4_L5", "L6_L7")], "oracle_summary.json")
    line("R30", "oracle: comparações concordantes", oracle["compared"], oracle["agree"], "oracle_summary.json")
    line("R31", "hes: engine x texto literal do workbook", 50, contract["hes"]["agree"], "contract_audit.json")
    # mutação
    line("R32", "mutações de evidência detectadas", mutation["evidence_mutations"]["defined"],
         mutation["evidence_mutations"]["detected"], "mutation_summary.json")
    line("R33", "mutantes de código detectados", mutation["code_mutants"]["introduced"],
         mutation["code_mutants"]["detected"], "mutation_summary.json")
    line("R34", "controles positivos aceitos", mutation["positive_controls"]["total"] + 1,
         mutation["positive_controls"]["accepted"] + (mutation["code_mutants"]["positive_control"]["result"] == "ACCEPT"),
         "mutation_summary.json")

    # L8: 3.4C x 4A
    common_targets = {r["target"] for r in t34}
    l8 = {
        "changed_only_by_area_41": {
            "targets": {"3.4C": len(t34), "4A": len(t4a), "added": sorted({r["target"] for r in t4a} - common_targets)},
            "nodes": {"3.4C": len(n34), "4A": len(n4a),
                      "added_blocks": dict(Counter(r["block"] for r in n4a if r["in_stage_3_4c_plan"] != "True"))},
            "transfers": {"3.4C": len(tr34), "4A": len(tr4a),
                          "added": sorted({r["node"] for r in tr4a} - {r["node"] for r in tr34})},
            "events_per_date": {"3.4C": int(cov34[0]["events"]), "4A": int(cov4a[0]["events"])},
        },
        "unchanged": {
            "targets_final_results_identical": all(
                r["final_results_2026-02-01"] == next(x for x in t4a if x["target"] == r["target"])["final_results_2026-02-01"]
                for r in t34),
            "removed_targets": sorted(common_targets - {r["target"] for r in t4a}),
            "nodes_relative_order_identical": [r["node"] for r in n4a if r["in_stage_3_4c_plan"] == "True"]
            == [r["node"] for r in n34],
            "transfers_identical": all(
                {k: v for k, v in r.items() if k in ("source_block", "source_variable", "target_variable", "instances",
                                                     "executed_events", "verified_events", "value_2026-02-01")}
                == {k: v for k, v in next(x for x in tr4a if x["node"] == r["node"]).items()
                    if k in ("source_block", "source_variable", "target_variable", "instances", "executed_events",
                             "verified_events", "value_2026-02-01")} for r in tr34),
            "store_4_blocks_sha256_identical": nonreg["subset_store_sha256"] == s34["determinism"]["RUN_A"]["store_sha256"],
            "fixture_graph_hash_identical": s4a["fixture"]["graph_hashes"]["A"] == s34["fixture"]["graph_hashes"]["A"],
        },
        "historical_paths_changed_since_baseline": [p for p in subprocess.run(
            ["git", "diff", "--name-only", BASELINE, "--", "audit/stage3_4", "audit/stage3_2_execution_orchestration",
             "audit/stage3_3a_result_contract", "audit/stage3_3b_state_propagation", "audit/stage3_3c_state_aware_aggregation"],
            cwd=REPO, capture_output=True, text=True, check=True).stdout.split() if p != PENDING_ITEMS],
        "pending_items_append_only": append_only(PENDING_ITEMS),
    }
    for name, ok in (("L8-1 alvos da 3.4C idênticos", l8["unchanged"]["targets_final_results_identical"]),
                     ("L8-2 nenhum alvo removido", l8["unchanged"]["removed_targets"] == []),
                     ("L8-3 ordem relativa dos 427 nós", l8["unchanged"]["nodes_relative_order_identical"]),
                     ("L8-4 12 transferências idênticas", l8["unchanged"]["transfers_identical"]),
                     ("L8-5 store dos 4 blocos idêntico", l8["unchanged"]["store_4_blocks_sha256_identical"]),
                     ("L8-7 evidência 3.4C e histórica não sobrescrita (git diff vazio)",
                      l8["historical_paths_changed_since_baseline"] == []),
                     ("L8-8 PLATFORM_PENDING_ITEMS.md alterado só por adição", l8["pending_items_append_only"]),
                     ("L8-6 só area_41 acrescentado", set(l8["changed_only_by_area_41"]["nodes"]["added_blocks"]) == {"area_41"}
                      and all(t.startswith("VAR160") for t in l8["changed_only_by_area_41"]["targets"]["added"]))):
        line(name.split()[0], " ".join(name.split()[1:]), True, ok, "3.4C x 4A evidence")

    imported = sorted(m for m in sys.modules if m == "app" or m.startswith(("app.", "tools")))
    problems = [f"{r['id']} {r['quantity']}: {r['recomputed']!r} != {r['expected']!r}" for r in lines if r["result"] != "PASS"]
    if imported:
        problems.append(f"INDEPENDENCE_FAILURE {imported}")
    if independent["result"] != "PASS":
        problems.append(f"INDEPENDENT_COUNT_FAILURE {independent['problems'][:3]}")
    out = {"label": "REAL_DERIVED_TEST_RESULT", "lines": lines, "l8_comparison": l8,
           "passed": sum(r["result"] == "PASS" for r in lines), "total": len(lines), "imports_app_or_tools": imported,
           "problems": problems, "result": "PASS" if not problems else "FAIL"}
    if "--no-write" not in sys.argv[1:]:
        (HERE / "closure_reconciliation_4a.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                                             encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("passed", "total", "problems", "result")}, indent=1, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
