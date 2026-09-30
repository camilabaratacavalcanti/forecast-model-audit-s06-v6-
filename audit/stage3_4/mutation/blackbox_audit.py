"""
Stage 3.4D — auditoria BLACK-BOX independente (contrato 3.4A §19).

    python -I audit/stage3_4/mutation/blackbox_audit.py [--no-write]

Não importa `app/` nem os harnesses: lê somente os artefatos versionados
das Stages 3.4B, 3.4C e 3.4D (CSV/JSON) e os confronta com um oráculo
ESCRITO a partir do contrato 3.4A (§13–§19) e dos prompts de cada etapa.
Termina verificando que nenhum módulo `app.*` foi carregado.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
S34 = HERE.parent

# ------------------------------------------------------------ oráculo escrito do contrato
ORACLE = {
    "official_targets": 446, "area_41_excluded": 25, "integrated_targets": 421, "planner_nodes": 427,
    "nodes_by_kind": {"EQUATION": 218, "AGGREGATION": 197, "TRANSFER": 12},
    "equation_instances": 392, "aggregation_instances": 395,
    "aggregation_types": {"AVERAGE": 342, "SUM": 42, "WEIGHTED_AVERAGE": 9, "MOVING_AVERAGE": 2},
    "differential_vectors": 3, "differential_dates": 2, "differential_cases": 4722,
    "dates": 32, "start": "2026-01-01", "end": "2026-02-01", "transfers": 12, "events_per_day": 847,
    "official_blocks": {"yield", "production", "energy", "max_ht"}, "pending_official": 16,
    "label": "REAL_DERIVED_TEST_RESULT", "coverage_class": "YEAR_TO_DATE_PARTIAL_COVERAGE",
}
REQUIRED_MUTATIONS = {  # prompt 3.4D §6 (IDs estáveis)
    "MUT-T01", "MUT-T02", "MUT-N01", "MUT-N02", "MUT-N03", "MUT-TX01", "MUT-TX02", "MUT-TX03", "MUT-TX04",
    "MUT-S01", "MUT-S02", "MUT-S03", "MUT-S04", "MUT-A01", "MUT-A02", "MUT-A03", "MUT-TM01", "MUT-TM02",
    "MUT-R01", "MUT-R02", "MUT-D01", "MUT-D02", "MUT-D03", "MUT-D04", "MUT-D05", "MUT-P01", "MUT-P02",
}
REQUIRED_CONTRACTS = {f"M{i}" for i in range(1, 11)}
REQUIRED_CODE_MUTANT_TOPICS = ("AVERAGE", "SUM", "integration_factor", "WEIGHTED_AVERAGE", "MOVING_AVERAGE",
                               "window_end", "janela efetiva", "instância errada", "produtor errado",
                               "descarte", "escolha de estado", "composição de detail", "seleção de ramo IF",
                               "ordenação", "determinismo")


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def audit(root: Path = S34, check_imports: bool = True) -> dict:
    """
    `root` = diretório audit/stage3_4 (o real, ou uma cópia mutada nos testes).
    `check_imports`: exige que nenhum `app.*` esteja carregado — válido no processo isolado
    (`python -I blackbox_audit.py`); desligado quando chamado de dentro de outra suíte.
    """
    diff, integ, mutation = root / "differential" / "evidence", root / "integrated" / "evidence", root / "mutation"
    findings: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            findings.append(message)

    # ---------------- 3.4B diferencial
    cases = rows(diff / "differential_cases.csv")
    keys = [(r["block"], r["operation_type"], r["instance_id"], r["input_vector"], r["run_date"]) for r in cases]
    require(len(keys) == len(set(keys)) == ORACLE["differential_cases"], "3.4B: casos duplicados ou fora de 4722")
    require({r["comparison"] for r in cases} == {"MATCH"}, "3.4B: caso diferente de MATCH")
    per_op = Counter(r["operation_type"] for r in cases)
    runs = ORACLE["differential_vectors"] * ORACLE["differential_dates"]
    require(per_op == Counter({"EQUATION": ORACLE["equation_instances"] * runs,
                               "AGGREGATION": ORACLE["aggregation_instances"] * runs}), f"3.4B: {per_op}")
    types = Counter(r["aggregation_type"] for r in cases if r["operation_type"] == "AGGREGATION")
    require({k: v // runs for k, v in types.items()} == ORACLE["aggregation_types"], f"3.4B tipos: {types}")
    require({r["block"] for r in cases} == ORACLE["official_blocks"], "3.4B: blocos")
    diff_summary = json.loads((diff / "differential_summary.json").read_text(encoding="utf-8"))
    require(diff_summary["result"] == "PASS" and diff_summary["differences"] == 0, "3.4B: summary não PASS")

    # ---------------- 3.4C integrado
    s = json.loads((integ / "integrated_summary.json").read_text(encoding="utf-8"))
    u = s["universe"]
    for field in ("official_targets", "area_41_excluded", "integrated_targets", "planner_nodes", "nodes_by_kind"):
        require(u[field] == ORACLE[field], f"3.4C universo {field}: {u[field]}")
    require(len({u["official_targets"], u["integrated_targets"], u["planner_nodes"]}) == 3, "3.4C: 446 != 421 != 427")
    require(u["official_targets"] - u["area_41_excluded"] == u["integrated_targets"], "3.4C: 446 - 25 != 421")
    require(s["label"] == ORACLE["label"] and s["result"] == "PASS" and s["problems"] == [], "3.4C: summary")
    require(s["temporal"]["coverage_class"] == ORACLE["coverage_class"], "3.4C: classe YTD")
    require("FULL_YEAR" not in json.dumps(s), "3.4C: FULL_YEAR declarado")
    require(s["fixture"]["pending_in_fixture"] == 0 and s["fixture"]["pending_official"] == ORACLE["pending_official"],
            "3.4C: pendências do fixture/oficial")
    det = s["determinism"]
    require(len({det[k]["results_sha256"] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")}) == 1,
            "3.4C: fingerprints divergentes")
    require(len({det[k]["store_sha256"] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B", "REEXECUTION")}) == 1,
            "3.4C: store divergente")
    require({det["HASH_SEED_A"]["hash_seed"], det["HASH_SEED_B"]["hash_seed"]} == {"0", "4242"}, "3.4C: seeds")
    for day, r in s["reexecution"].items():
        require(r["same_store"] and r["new_keys"] == 0 and r["stated_results"] == 0 and r["first_run_events_equal"]
                and r["transfer_statuses"] == {"UNCHANGED": 60}, f"3.4C: reexecução {day}")
    targets = rows(integ / "targets.csv")
    require(len(targets) == len({r["target"] for r in targets}) == ORACLE["integrated_targets"], "3.4C: targets.csv")
    require({r["block"] for r in targets} == ORACLE["official_blocks"], "3.4C: area_41 nos alvos")
    require({r["execution_status"] for r in targets} == {"EXECUTED"}, "3.4C: alvo não executado")
    nodes = rows(integ / "nodes.csv")
    require(len(nodes) == len({r["node"] for r in nodes}) == ORACLE["planner_nodes"], "3.4C: nodes.csv")
    require(Counter(r["kind"] for r in nodes) == Counter(ORACLE["nodes_by_kind"]), "3.4C: tipos de nó")
    require({r["dates_executed"] for r in nodes} == {str(ORACLE["dates"])}, "3.4C: nó sem 32 datas")
    transfers = rows(integ / "transfers.csv")
    require(len(transfers) == ORACLE["transfers"], "3.4C: transfers.csv")
    require(all(r["executed_events"] == r["verified_events"] == str(ORACLE["dates"] * int(r["instances"]))
                for r in transfers), "3.4C: transferência não verificada")
    coverage = rows(integ / "temporal_coverage.csv")
    start = date.fromisoformat(ORACLE["start"])
    expected_days = [(start + timedelta(days=n)).isoformat() for n in range(ORACLE["dates"])]
    require([r["date"] for r in coverage] == expected_days and expected_days[-1] == ORACLE["end"],
            "3.4C: sequência temporal")
    require({(r["targets"], r["nodes"], r["events"], r["errors"]) for r in coverage}
            == {("421", "427", str(ORACLE["events_per_day"]), "0")}, "3.4C: cobertura por data")
    require(ORACLE["events_per_day"] == ORACLE["equation_instances"] + ORACLE["aggregation_instances"]
            + sum(int(r["instances"]) for r in transfers), "3.4C: 847 != 392 + 395 + 60")

    # ---------------- 3.4D mutação
    m = json.loads((mutation / "mutation_summary.json").read_text(encoding="utf-8"))
    matrix = rows(mutation / "mutation_matrix.csv")
    results = rows(mutation / "mutation_results.csv")
    ids = [r["mutation_id"] for r in matrix]
    require(len(ids) == len(set(ids)) and ids == [r["mutation_id"] for r in results], "3.4D: IDs da matriz")
    require(REQUIRED_MUTATIONS <= set(ids), f"3.4D: mutações obrigatórias ausentes {REQUIRED_MUTATIONS - set(ids)}")
    require({r["contract"] for r in matrix} == REQUIRED_CONTRACTS, "3.4D: contratos M1..M10")
    require(all(r["detected"] == "TRUE" and r["result"] == "PASS" and r["expected_detection"] in
                r["actual_detection"].split("|") for r in results), "3.4D: mutação não detectada")
    require({r["production_code_touched"] for r in matrix} == {"NO"}, "3.4D: código de produção tocado")
    require(m["mutations_defined"] == m["mutations_executed"] == m["mutations_detected"] == len(results)
            and m["mutations_missed"] == 0 and m["detection_rate"] == "100.0%", "3.4D: contagem")
    controls = rows(mutation / "positive_controls.csv")
    require(controls and {c["result"] for c in controls} == {"ACCEPT"}, "3.4D: controle positivo rejeitado")
    code = m["code_mutants"]
    require(isinstance(code, dict), "3.4D: mutantes de código não executados")
    if isinstance(code, dict):
        require(code["surviving"] == 0 and code["introduced"] == code["detected"] > 0, "3.4D: mutante sobrevivente")
        require(code["positive_control"]["result"] == "ACCEPT" and code["repository_untouched"], "3.4D: controle/código")
        code_rows = rows(mutation / "code_mutation_results.csv")
        require(all(r["detected"] == "TRUE" and "TESTS" in r["detected_by"] for r in code_rows),
                "3.4D: mutante não morto pelos testes")
        require(all("INTEGRATED" in r["detected_by"] or "DIFFERENTIAL" in r["detected_by"] for r in code_rows),
                "3.4D: mutante não detectado pela auditoria")
        topics = " ".join(r["contract"] for r in code_rows)
        require(all(t in topics for t in REQUIRED_CODE_MUTANT_TOPICS),
                f"3.4D: tópicos §19 sem mutante {[t for t in REQUIRED_CODE_MUTANT_TOPICS if t not in topics]}")
    require(m["fixture"]["official_pending_links"] == ORACLE["pending_official"]
            and m["fixture"]["persisted_links_equal_baseline"], "3.4D: vínculos oficiais")
    require(m["protected_artifacts"]["result"] == "NO PRODUCTION CHANGES", "3.4D: artefatos protegidos")

    loaded_app = sorted(name for name in sys.modules if name == "app" or name.startswith("app."))
    if check_imports:
        require(not loaded_app, f"black-box importou app: {loaded_app[:3]}")
    return {"oracle": "written from STAGE_3_4A_DECISION_CONTRACT §13–§19 and stage prompts",
            "imports_app": bool(loaded_app), "artifacts_checked": 12,
            "findings": findings, "result": "PASS" if not findings else "FAIL"}


def main() -> int:
    report = audit()
    if "--no-write" not in sys.argv[1:]:
        (HERE / "blackbox_audit.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
                                                  + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
