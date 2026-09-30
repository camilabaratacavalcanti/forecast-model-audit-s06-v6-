"""
Stage 3.4E — reconciliação final da Stage 3 (Consolidation / Final Stage-3 Closure).

    python audit/stage3_4/closure/reconcile.py [--no-write]

Recalcula cada cardinalidade crítica a partir do CÓDIGO (catálogo, planner,
engine, fixture REAL_DERIVED, uma sequência real de 32 datas) e confronta com
a EVIDÊNCIA versionada da 3.4B, 3.4C e 3.4D e com o contrato 3.4A. Não aceita
número de relatório: cada linha da matriz tem origem observada.

Verifica também a superfície de produção protegida (git contra 7877551,
f3b6588 e o baseline 8095011; bytes do registro oficial de vínculos).

Somente leitura; grava apenas `closure_reconciliation.json` neste diretório.
Todo resultado de execução é REAL_DERIVED_TEST_RESULT.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
S34 = HERE.parent
REPO = S34.parents[1]
sys.path[:0] = [str(REPO), str(S34 / "integrated")]

import checks  # noqa: E402
import fixture  # noqa: E402
import run_integrated as integ  # noqa: E402

from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.interblock_orchestrator import InterblockExecutionOrchestrator  # noqa: E402
from app.repositories.seed_loader import SeedLoader  # noqa: E402

BLOCKS = ("yield", "production", "energy", "max_ht")
REFERENCE, CONTRACT_BASELINE, BASELINE_34E = "7877551", "f3b6588", "80950117eb9881fe635e695dd221bdf0c6147ee5"
GRAPH_HASH = "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff"


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def git_bytes(*args) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True).stdout


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def seed_json(block: str, name: str) -> list:
    return json.loads((REPO / "data" / "seed" / block / f"{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    observed: dict = {}

    # ---------------- planejamento (código + plan_evidence.csv)
    official = InterblockExecutionOrchestrator.from_seed_root(REPO / "data" / "seed")
    plan_rows = rows(REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv")
    official_targets = official.targets_of_blocks(BLOCKS + ("area_41",))
    o = fixture.build("A")
    integrated = o.targets_of_blocks(BLOCKS)
    excluded = sorted(set(official_targets) - set(integrated))
    block_of_row = {r["target"]: r["block"] for r in plan_rows}
    observed["planning"] = {
        "plan_evidence_rows": len(plan_rows),
        "official_targets_from_planner": len(official_targets),
        "plan_evidence_equals_planner": sorted(r["target"] for r in plan_rows) == official_targets,
        "official_ok_blocked": dict(Counter("OK" if r["observed"] == "OK" else "BLOCKED" for r in plan_rows)),
        "integrated_targets": len(integrated),
        "excluded": len(excluded),
        "excluded_blocks": sorted({block_of_row[t] for t in excluded}),
        "integrated_subset_of_official": set(integrated) <= set(official_targets),
    }

    # ---------------- planner
    plan = integ.integrated_plan(o)
    kinds = Counter(s.kind for s in plan.steps)
    by_block = {}
    for block in BLOCKS:
        steps = [s for s in plan.steps if s.block == block]
        c = Counter(s.kind for s in steps)
        by_block[block] = {"targets": sum(1 for t in integrated if o.catalog.block_of.get(t) == block),
                           "EQUATION": c["EQUATION"], "AGGREGATION": c["AGGREGATION"], "TRANSFER": c["TRANSFER"],
                           "nodes": len(steps)}
    producers = Counter(v for s in plan.steps for v in s.produces)
    multi = {v: n for v, n in producers.items() if n > 1}
    observed["planner"] = {"nodes": len(plan.steps), "by_kind": dict(kinds), "by_block": by_block,
                           "pending_blockers": len(plan.pending_blockers),
                           "variables_with_multiple_nodes": multi,
                           "nodes_minus_targets": len(plan.steps) - len(integrated),
                           "graph_hash": fixture.graph_hash(o)}

    # ---------------- equações e agregações (seeds + engine)
    loader = SeedLoader(REPO / "data" / "seed")
    variables = loader.load_variable_definitions()
    engine = ForecastEngine()
    eq_block = {r["equation_id"]: b for b in BLOCKS for r in seed_json(b, "equations")}
    agg_block = {r["aggregation_rule_id"]: b for b in BLOCKS + ("area_41",) for r in seed_json(b, "aggregation_rules")}
    definitions = [d for d in loader.load_equation_definitions().all() if d.equation_definition_id in eq_block]
    instances = loader.load_aggregation_rule_instances(variable_definition_registry=variables).all()
    agg4 = [i for i in instances if agg_block.get(i.rule.aggregation_rule_id) in BLOCKS]
    agg5 = [i for i in instances if i.rule.aggregation_rule_id in agg_block]
    rules4 = {i.rule.aggregation_rule_id for i in agg4}
    observed["equations"] = {"definitions": len(definitions),
                             "instances": sum(len(engine.materialize_equation(d)) for d in definitions),
                             "distinct_target_variables": len({d.target_variable_id for d in definitions}),
                             "VAR12041_definitions": sum(1 for d in definitions if d.target_variable_id == "VAR12041")}
    observed["aggregations"] = {
        "rules": len(rules4), "instances_4_blocks": len(agg4), "instances_with_area_41": len(agg5),
        "historical_834_equals_417x2": len(agg5) * 2 == 834,
        "types": dict(Counter(i.rule.aggregation_type for i in agg4)),
        "annual_rules": len({i.rule.aggregation_rule_id for i in agg4 if i.rule.target_frequency == "anual"}),
        "annual_rules_by_block": dict(Counter(agg_block[r] for r in {i.rule.aggregation_rule_id for i in agg4
                                                                     if i.rule.target_frequency == "anual"})),
    }

    # ---------------- vínculos
    links = official.catalog.links
    payload = json.loads((REPO / "data/seed/interblock_links.json").read_text(encoding="utf-8"))
    observed["links"] = {
        "loaded_links": len(links.links()),
        "transfer_nodes_integrated": kinds["TRANSFER"],
        "excluded_link": sorted(f"{link.source_block}.{link.source_definition_id} -> {link.consumer_block}."
                                f"{link.consumer_definition_id}" for link in links.links()
                                if link.consumer_block not in BLOCKS),
        "pending_official": len(links.pending()),
        "pending_persisted_status": dict(Counter(p["resolution_status"] for p in payload["pending"])),
        "pending_fixture": len(o.catalog.links.pending()),
    }

    # ---------------- execução real de 32 datas (temporal, transfers)
    context = integ.fresh_context(o)
    traces, snapshot = {}, None
    for day in integ.DAYS:
        if day == integ.FEB1:
            snapshot = {k: v for k, v in integ.store_of(context).items() if k[3] == "2026-01"}
        traces[day] = integ.execute_day(o, plan, context, day)
    store = integ.store_of(context)
    counts, temporal_problems = checks.check_temporal(store, snapshot, [d.isoformat() for d in integ.DAYS],
                                                      integ.derived_variables(plan))
    windows = {}
    for k in store:
        if k[0] in integ.derived_variables(plan):
            windows.setdefault(k[:4], set()).add(k[4])
    observed["temporal"] = {
        "dates": len(integ.DAYS), "first": integ.DAYS[0].isoformat(), "last": integ.DAYS[-1].isoformat(),
        "transfer_events": sum(len(t.of_kind("TRANSFER")) for t in traces.values()),
        "events_per_day": sorted({len(t.events) for t in traces.values()}),
        "monthly_identities_jan": counts["monthly_jan"], "monthly_identities_feb": counts["monthly_feb"],
        "annual_identities": counts["annual"],
        "windows_per_monthly_jan_identity": sorted({len(w) for (e, st, sv, p), w in windows.items() if p == "2026-01"}),
        "windows_per_annual_identity": sorted({len(w) for (e, st, sv, p), w in windows.items() if len(p) == 4}),
        "temporal_problems": temporal_problems,
    }

    # ---------------- evidência 3.4B / 3.4C / 3.4D
    diff_rows = rows(S34 / "differential/evidence/differential_cases.csv")
    diff_summary = json.loads((S34 / "differential/evidence/differential_summary.json").read_text(encoding="utf-8"))
    observed["stage_3_4B"] = {
        "cases": len(diff_rows), "unique_keys": len({(r["block"], r["operation_type"], r["instance_id"],
                                                     r["input_vector"], r["run_date"]) for r in diff_rows}),
        "comparison": dict(Counter(r["comparison"] for r in diff_rows)),
        "by_operation": dict(Counter(r["operation_type"] for r in diff_rows)),
        "vectors": sorted({r["input_vector"] for r in diff_rows}), "dates": sorted({r["run_date"] for r in diff_rows}),
        "reference_commit": diff_summary["reference_commit"], "candidate_commit": diff_summary["candidate_commit"],
        "difference_types": diff_summary["difference_types"], "result": diff_summary["result"],
        "oracle_type": diff_summary["oracle_type"],
        "aggregation_types": diff_summary["aggregation_types"],
    }
    s34c = json.loads((S34 / "integrated/evidence/integrated_summary.json").read_text(encoding="utf-8"))
    transfers = rows(S34 / "integrated/evidence/transfers.csv")
    observed["stage_3_4C"] = {
        "result": s34c["result"], "targets_executed": s34c["targets_executed"],
        "nodes_executed": s34c["nodes_executed"], "transfers": len(transfers),
        "transfer_events_verified": sum(int(r["verified_events"]) for r in transfers),
        "transfer_events_executed": sum(int(r["executed_events"]) for r in transfers),
        "dates": s34c["temporal"]["dates"], "coverage_class": s34c["temporal"]["coverage_class"],
        "reexecution": {d: {"first": r["first_run_transfer_statuses"], "re": r["transfer_statuses"],
                            "same_store": r["same_store"], "new_keys": r["new_keys"]}
                        for d, r in s34c["reexecution"].items()},
        "fingerprints": {k: s34c["determinism"][k]["results_sha256"]
                         for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")},
        "store_fingerprints": {k: s34c["determinism"][k]["store_sha256"]
                               for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B", "REEXECUTION")},
        "hash_seeds": sorted({s34c["determinism"][k]["hash_seed"] for k in ("HASH_SEED_A", "HASH_SEED_B")}),
        "graph_hashes": s34c["fixture"]["graph_hashes"],
        "state": {k: v.get("problems", []) for k, v in s34c["state"].items() if isinstance(v, dict) and "problems" in v},
        "sc2": {k: s34c["state"]["SC2_EQ18003"][k] for k in ("active_branch_L1", "inactive_branch_L2")},
        "sc4": s34c["state"]["SC4_composition_contracts"],
        "by_block": s34c["by_block"],
        "evidence_unchanged_since_043fe9c": git("diff", "--stat", "043fe9c", "--", "audit/stage3_4/integrated/evidence") == "",
    }
    m = json.loads((S34 / "mutation/mutation_summary.json").read_text(encoding="utf-8"))
    results = rows(S34 / "mutation/mutation_results.csv")
    code = rows(S34 / "mutation/code_mutation_results.csv")
    controls = rows(S34 / "mutation/positive_controls.csv")
    probe = json.loads((S34 / "mutation/baseline_gap_probe.json").read_text(encoding="utf-8"))
    observed["stage_3_4D"] = {
        "evidence_mutations": len(results),
        "evidence_detected": sum(r["detected"] == "TRUE" for r in results),
        "by_contract": dict(sorted(Counter(r["contract"] for r in results).items(), key=lambda kv: int(kv[0][1:]))),
        "code_mutants": len(code), "code_mutant_ids": [r["mutant_id"] for r in code],
        "code_detected": sum(r["detected"] == "TRUE" for r in code),
        "code_killed_by": dict(Counter(d for r in code for d in r["detected_by"].split("|"))),
        "evidence_positive_controls": dict(Counter(c["result"] for c in controls)),
        "code_positive_control": m["code_mutants"]["positive_control"]["mutant_id"] + ":"
        + m["code_mutants"]["positive_control"]["result"],
        "code_repository_untouched": m["code_mutants"]["repository_untouched"],
        "gap_probe": {k: v["detected_by_original_auditor"] for k, v in probe["probes"].items()},
        "gap_probe_baseline": probe["baseline"],
        "blackbox": json.loads((S34 / "mutation/blackbox_audit.json").read_text(encoding="utf-8"))["result"],
    }

    # ---------------- superfície protegida
    links_now = (REPO / "data/seed/interblock_links.json").read_bytes()
    observed["protected"] = {
        "diff_vs_reference_data_tools": git("diff", "--stat", REFERENCE, "--", "data", "tools"),
        "diff_vs_3_4A_baseline_app_data_tools": git("diff", "--stat", CONTRACT_BASELINE, "--", "app", "data", "tools"),
        "diff_vs_3_4E_baseline_app_data_tools": git("diff", "--stat", BASELINE_34E, "--", "app", "data", "tools"),
        "working_tree_app_data_tools": git("status", "--porcelain", "--", "app", "data", "tools"),
        "changed_since_3_4A_outside_stage3_4": [line for line in git("diff", "--name-only", CONTRACT_BASELINE,
                                                                     BASELINE_34E).splitlines()
                                                if not line.startswith(("audit/stage3_4/", "tests/test_stage3_4"))],
        "interblock_links_sha256": hashlib.sha256(links_now).hexdigest(),
        "interblock_links_equal_7877551": links_now == git_bytes("show", f"{REFERENCE}:data/seed/interblock_links.json"),
        "interblock_links_equal_f3b6588": links_now == git_bytes("show",
                                                                  f"{CONTRACT_BASELINE}:data/seed/interblock_links.json"),
        "workbooks_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                             for p in sorted((REPO / "data/workbooks").iterdir())},
    }

    # ---------------- matriz final (esperado do contrato x observado)
    p, pl, eq, ag, lk, tm = (observed[k] for k in ("planning", "planner", "equations", "aggregations", "links", "temporal"))
    b, c, d = observed["stage_3_4B"], observed["stage_3_4C"], observed["stage_3_4D"]
    matrix = [
        ("Planning targets", 446, p["official_targets_from_planner"], "planner + plan_evidence.csv"),
        ("Integrated targets", 421, p["integrated_targets"], "targets_of_blocks(4 blocos)"),
        ("Area_41 excluded (only area_41)", 25, p["excluded"] if p["excluded_blocks"] == ["area_41"] else -1,
         "446 − 421, blocos dos excluídos"),
        ("Planner nodes", 427, pl["nodes"], "plan(421).steps"),
        ("Equation nodes", 218, pl["by_kind"].get("EQUATION"), "plan steps"),
        ("Aggregation nodes", 197, pl["by_kind"].get("AGGREGATION"), "plan steps"),
        ("Transfer nodes", 12, pl["by_kind"].get("TRANSFER"), "plan steps"),
        ("VAR12041 equation definitions (427 − 421)", 7, pl["variables_with_multiple_nodes"].get("VAR12041"),
         "nós que produzem VAR12041"),
        ("VAR12041 equation definitions (seeds)", 7, eq["VAR12041_definitions"], "equations.json"),
        ("Equation definitions", 218, eq["definitions"], "equations.json (4 blocos)"),
        ("Equation target variables", 212, eq["distinct_target_variables"], "218 − 6 (VAR12041)"),
        ("Equation instances", 392, eq["instances"], "ForecastEngine.materialize_equation"),
        ("Aggregation rules", 197, ag["rules"], "SeedLoader aggregation instances"),
        ("Aggregation instances", 395, ag["instances_4_blocks"], "SeedLoader aggregation instances"),
        ("Aggregation incl. area_41", 417, ag["instances_with_area_41"], "SeedLoader (5 blocos)"),
        ("Historical 834 = 417 × 2 execution cases", True, ag["historical_834_equals_417x2"], "cálculo"),
        ("Transfers (transfers.csv)", 12, c["transfers"], "transfers.csv; = TRANSFER nodes"),
        ("Transfer events (32 datas)", 1920, tm["transfer_events"], "execução real + transfers.csv"),
        ("Transfer events verified (3.4C evidence)", 1920, c["transfer_events_verified"], "transfers.csv"),
        ("Execution dates", 32, tm["dates"], f"{tm['first']} → {tm['last']}"),
        ("Pending links (official, PENDING_LOAD)", 16,
         lk["pending_official"] if lk["pending_persisted_status"] == {"PENDING_LOAD": 16} else -1,
         "registry oficial + interblock_links.json"),
        ("Annual rules", 48, ag["annual_rules"], "target_frequency = anual"),
        ("Monthly identities (jan / feb)", "313/313", f"{tm['monthly_identities_jan']}/{tm['monthly_identities_feb']}",
         "check_temporal"),
        ("Windows per January monthly identity", [31], tm["windows_per_monthly_jan_identity"], "store real"),
        ("Annual identities", 185, tm["annual_identities"], "check_temporal"),
        ("Windows per annual identity (YTD)", [32], tm["windows_per_annual_identity"], "store real"),
        ("Differential cases (3.4B)", 4722, b["comparison"].get("MATCH"), "differential_cases.csv"),
        ("Mutation evidence", 58, d["evidence_detected"], "mutation_results.csv"),
        ("Code mutants", 17, d["code_detected"], "code_mutation_results.csv"),
        ("Mutation detection", "100%",
         f"{100 * (d['evidence_detected'] + d['code_detected']) / (d['evidence_mutations'] + d['code_mutants']):.0f}%",
         "75 / 75"),
        ("Positive controls", 14, d["evidence_positive_controls"].get("ACCEPT", 0)
         + (d["code_positive_control"].endswith("ACCEPT")), "positive_controls.csv + CM-00"),
    ]
    table = [{"area": a, "expected": e, "observed": ob, "evidence": ev, "status": "PASS" if e == ob else "FAIL"}
             for a, e, ob, ev in matrix]
    problems = [f"{r['area']}: esperado {r['expected']} observado {r['observed']}" for r in table if r["status"] != "PASS"]
    pr = observed["protected"]
    for field in ("diff_vs_reference_data_tools", "diff_vs_3_4A_baseline_app_data_tools",
                  "diff_vs_3_4E_baseline_app_data_tools", "working_tree_app_data_tools"):
        if pr[field]:
            problems.append(f"PROTECTED_SURFACE_CHANGED {field}")
    if pr["changed_since_3_4A_outside_stage3_4"]:
        problems.append(f"ALTERAÇÃO FORA DA STAGE 3.4 desde f3b6588: {pr['changed_since_3_4A_outside_stage3_4'][:3]}")
    if not (pr["interblock_links_equal_7877551"] and pr["interblock_links_equal_f3b6588"]):
        problems.append("REGISTRY_CHANGED interblock_links.json")
    if pl["graph_hash"] != GRAPH_HASH or observed["planning"]["excluded_blocks"] != ["area_41"]:
        problems.append("FIXTURE/PLANNING divergente")
    if tm["temporal_problems"] or tm["events_per_day"] != [847]:
        problems.append("TEMPORAL divergente")
    if (b["result"], b["difference_types"], b["unique_keys"]) != ("PASS", {}, 4722):
        problems.append("3.4B divergente")
    if not c["evidence_unchanged_since_043fe9c"] or c["result"] != "PASS":
        problems.append("3.4C evidência alterada")
    if d["blackbox"] != "PASS" or not d["code_repository_untouched"]:
        problems.append("3.4D black-box / repositório")
    report = {"label": fixture.LABEL, "matrix": table, "observed": observed, "problems": problems,
              "result": "PASS" if not problems else "FAIL"}
    if "--no-write" not in sys.argv[1:]:
        (HERE / "closure_reconciliation.json").write_text(
            json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"matrix": table, "problems": problems, "result": report["result"]}, indent=1,
                     ensure_ascii=False, default=str))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
