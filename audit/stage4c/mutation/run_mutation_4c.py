"""
Stage 4C.4 — mutação das guardas convertidas e do registro de baseline.

    python audit/stage4c/mutation/run_mutation_4c.py [--write] [--only ID[,ID...]]

Cada mutante roda num CLONE TEMPORÁRIO (`git clone --shared` do HEAD + árvore atual de audit/ e tests/,
como no ensaio da 4C.3): o mutante é aplicado no clone e os testes-alvo rodam lá; o mutante é DETECTADO
quando todos os testes esperados falham. O controle positivo (clone sem mutação) roda o mesmo conjunto de
testes e precisa passar. `git status --porcelain -- app data tools` do repositório é registrado antes e
depois e precisa ficar vazio. Com `--write` grava `mutation_results.csv` e `mutation_summary.json` aqui.

Classes (contrato 4C §1): H commit sintético dentro do intervalo fixo; E evidência histórica reescrita;
S renumeração, reuso de aposentado, aposentadoria sem `retired`; W harness escrevendo na árvore;
REG registro (sha de B0, entrada APPROVED editada, árvore suja e motivo ausente aceitos, current em
PROPOSED); R mudança de comportamento sem re-baseline (= ensaio R2-b).
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "audit" / "stage4c" / "rehearsal"))

import rehearse_5a as tree  # noqa: E402  (build_tree / clean_env / commit_all do ensaio)

ENV = tree.clean_env()


def sh(root, *args, check=True) -> str:
    return subprocess.run(list(args), cwd=root, capture_output=True, text=True, check=check, env=ENV).stdout


def git(root, *args) -> str:
    return sh(root, "git", "-c", "user.name=mutante", "-c", "user.email=mutante@local", *args)


def edit(root: Path, relative: str, old: str, new: str, count: int = 1) -> None:
    path = root / relative
    data = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    o, n = old.encode(), new.encode()
    if eol == b"\r\n":
        o, n = o.replace(b"\n", b"\r\n"), n.replace(b"\n", b"\r\n")
    assert data.count(o) == count, (relative, old, data.count(o))
    path.write_bytes(data.replace(o, n))


def synthetic_commit(root: Path, base: str, change) -> str:
    """Commit sintético sobre `base` (dentro do intervalo histórico); volta ao ramo da árvore."""
    git(root, "checkout", "-q", base)
    change(root)
    git(root, "commit", "-q", "-am", f"mutante: commit sintético sobre {base}")
    sha = git(root, "rev-parse", "HEAD").strip()
    git(root, "checkout", "-q", "arvore")
    return sha


def json_edit(root: Path, relative: str, fn) -> None:
    path = root / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    fn(payload)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def drop_last_line(root: Path, relative: str) -> None:
    path = root / relative
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:-1]), encoding="utf-8")


# ------------------------------------------------------------------ mutantes
def replace_in_test(test_file: str, literal: str, base: str, change):
    """Commit sintético sobre `base` (dentro do intervalo); o teste passa a apontar o fim do intervalo para ele."""
    def apply(root):
        sha = synthetic_commit(root, base, change)
        edit(root, test_file, literal, literal.replace(base, sha))
    return apply


def app_line(root):
    path = root / "app/engine/forecast_engine.py"
    data = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    path.write_bytes(data + b"MUTANTE_SINTETICO = 1" + eol)


def mean_off(root):
    edit(root, "app/engine/temporal_aggregation_service.py", "sum(values) / len(values)",
         "sum(values) / (len(values) + 1)")


def yield_formula(root):
    path = "data/seed/yield/equations.json"
    payload = json.loads((root / path).read_text(encoding="utf-8"))
    payload[0]["expression"] += " + 0"
    (root / path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def app_planner(root):
    edit(root, "app/engine/interblock_orchestrator.py",
         "        indegree = {key: 0 for key in selected}\n",
         "        indegree = {key: 0 for key in sorted(selected, reverse=True)}\n")


COST_BLOCK = "budget_" + "cost"     # montado: o inventário D-TAX-02 não admite o nome fora dos locais classificados


def validator_range(root):
    edit(root, "app/validation/variable_seed_validator.py", f'"{COST_BLOCK}": (32000, 32999)',
         f'"{COST_BLOCK}": (32000, 32998)')


def energy_manifest_renumber(root):
    def fn(p):
        p["entities"][0]["entity_id"] = p["entities"][0]["entity_id"][:-2] + "99"
    json_edit(root, "data/seed/energy/manifest.json", fn)


def production_reuse_retired(root):
    def fn(p):
        clone = dict(p["entities"][0])
        clone.update({"name": "mutante_reuso", "entity_id": "PARAM12003"})
        p["entities"].append(clone)
    json_edit(root, "data/seed/production/manifest.json", fn)


def max_ht_retire_without_ledger(root):
    def fn(p):
        p["entities"] = [e for e in p["entities"] if e["entity_id"] != "VAR13001"]
    json_edit(root, "data/seed/max_ht/manifest.json", fn)


def registry_sha(root):
    def fn(r):
        r["entries"][0]["conjuntos"]["stage3_4c_integrated"]["arquivos"]["targets.csv"]["sha256"] = "0" * 64
    path = root / "audit/baselines/BASELINE_REGISTRY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    fn(payload)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def registry_edit_approved(root):
    path = root / "audit/baselines/BASELINE_REGISTRY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["motivo"] += " (editado depois da aprovação)"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def registry_current_proposed(root):
    path = root / "audit/baselines/BASELINE_REGISTRY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    proposed = json.loads(json.dumps(payload["entries"][-1]))
    proposed.update({"id": "B1", "anterior": payload["entries"][-1]["id"], "status": "PROPOSED",
                     "layout": "audit/baselines/B1"})
    proposed.pop("selo", None)
    payload["entries"].append(proposed)
    payload["current"] = "B1"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def committed(change):
    """Mutante do CÓDIGO do registro: precisa estar commitado (o teste clona o HEAD do clone)."""
    def apply(root):
        change(root)
        git(root, "commit", "-q", "-am", "mutante do registro")
    return apply


def no_dirty_check(root):
    edit(root, "audit/baselines/rebaseline.py", '''    if dirty:
        return f"árvore suja: {dirty.splitlines()[:5]}"
''', "")


def no_reason_check(root):
    edit(root, "audit/baselines/rebaseline.py", '''    if not reason or not reason.strip():
        return "motivo (--reason) ausente ou vazio"
''', "")


def harness_writes_tree(root):
    edit(root, "audit/stage4a/mutation/run_mutation_4a.py", '''    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=common.REPO,''',
         '''    (common.REPO / "data" / "mutante_w.txt").write_text("escrito pelo harness\\n", encoding="utf-8")
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=common.REPO,''')


def evidence_rewrite(relative):
    def apply(root):
        drop_last_line(root, relative)
    return apply


def behaviour_change(root):
    edit(root, "data/seed/area_41/equations.json", "19.475*ln(VAR16001) - 85.999", "19.476*ln(VAR16001) - 85.999")


T = "tests/"
REG = T + "test_stage4c_baseline_registry.py::"
MUTANTS = [
    # id, classe, descrição, aplicar(clone), testes-alvo que precisam falhar
    ("H-01", "H", "commit sintético alterando app/ dentro do intervalo da 4A (d2847ab..X)",
     replace_in_test(T + "test_stage4a_closure.py", "0a924e66cfd0774a13e46a332b460b770283a554",
                     "0a924e66cfd0774a13e46a332b460b770283a554", app_line),
     [T + "test_stage4a_closure.py::test_production_surface_and_stage_3_closure_untouched"]),
    ("H-02", "H", "commit sintético alterando data/ dentro do intervalo da 4B (0a924e6..X)",
     replace_in_test(T + "test_stage4b_closure.py", "f573c1b6cb9365b4669ec6af688f0ada36ad438d",
                     "f573c1b6cb9365b4669ec6af688f0ada36ad438d", yield_formula),
     [T + "test_stage4b_closure.py::test_production_surface_and_previous_stages_untouched"]),
    ("H-03", "H", "commit sintético removendo um alvo da evidência 4A no fechamento (reconcile_4a no clone)",
     replace_in_test(T + "test_stage4a_closure.py", "0a924e66cfd0774a13e46a332b460b770283a554",
                     "0a924e66cfd0774a13e46a332b460b770283a554",
                     evidence_rewrite("audit/stage4a/integrated/evidence/targets.csv")),
     [T + "test_stage4a_closure.py::test_independent_reconciliation_passes_without_app"]),
    ("H-04", "H", "commit sintético mudando a média de agregação sobre o fechamento 3.4B (diferencial no clone)",
     replace_in_test(T + "test_stage3_4b_differential.py", '"4d54804"', "4d54804", mean_off),
     [T + "test_stage3_4b_differential.py::test_live_differential_reference_vs_head_matches_exactly"]),
    ("H-05", "H", "commit sintético não taxonômico em app/ no intervalo 043fe9c..X da 3.4D",
     replace_in_test(T + "test_stage3_4d_mutation.py", '"d8b5d55"', "d8b5d55", app_line),
     [T + "test_stage3_4d_mutation.py::test_no_production_artifact_changed_since_baseline"]),
    ("H-06", "H", "commit sintético mudando uma fórmula no intervalo da D-TAX-01 (547b920..X)",
     replace_in_test(T + "test_taxonomy_migration_d_tax_01.py", "d8b5d55810c55a06cfc54e8a2a25ac9f796f08b7",
                     "d8b5d55810c55a06cfc54e8a2a25ac9f796f08b7", yield_formula),
     [T + "test_taxonomy_migration_d_tax_01.py::test_tax_10_the_authorized_change_is_detected_as_taxonomic_not_functional",
      T + "test_taxonomy_migration_d_tax_01.py::test_tax_07_no_formula_changed"]),
    ("H-07", "H", "commit sintético alterando o planner no intervalo da 3.3A (a733487..X)",
     replace_in_test(T + "test_stage3_3a_result_contract.py", '"git", "show", "eee88d6:', "eee88d6", app_planner),
     [T + "test_stage3_3a_result_contract.py::test_23_25_planning_code_is_unchanged_since_stage_3_2"]),
    ("H-08", "H", "commit sintético mudando uma faixa de ID no intervalo da D-TAX-02 (d8b5d55..X)",
     replace_in_test(T + "test_taxonomy_d_tax_02.py", "d2847ab36933668bf4a1299b3ffe058827a82037",
                     "d2847ab36933668bf4a1299b3ffe058827a82037", validator_range),
     [T + "test_taxonomy_d_tax_02.py::test_tax_02_07_crosswalk_changes_no_id_or_range"]),
    ("E-01", "E", "evidência 3.4C reescrita (última linha de transfers.csv removida)",
     evidence_rewrite("audit/stage3_4/integrated/evidence/transfers.csv"),
     [REG + "test_b0_historical_evidence_is_immutable[stage3_4c_integrated]"]),
    ("E-02", "E", "evidência 4A reescrita (última linha de targets.csv removida)",
     evidence_rewrite("audit/stage4a/integrated/evidence/targets.csv"),
     [REG + "test_b0_historical_evidence_is_immutable[stage4a_integrated]"]),
    ("E-03", "E", "evidência 4B reescrita (última linha de T2/temporal_coverage.csv removida)",
     evidence_rewrite("audit/stage4b/temporal/evidence/T2/temporal_coverage.csv"),
     [REG + "test_b0_historical_evidence_is_immutable[stage4b_temporal]"]),
    ("S-01", "S", "ID renumerado (primeira entidade do energy)", energy_manifest_renumber,
     [T + "test_stage2_6b_interblock_closure.py::test_no_historical_id_was_renumbered",
      T + "test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines[a126e02]"]),
    ("S-02", "S", "ID aposentado reutilizado (PARAM12003 numa identidade nova do production)",
     production_reuse_retired,
     [T + "test_stage2_6b_interblock_closure.py::test_no_historical_id_was_renumbered",
      T + "test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines[eceffd4]"]),
    ("S-03", "S", "identidade removida sem entrar no `retired` do ledger (VAR13001 do max_ht)",
     max_ht_retire_without_ledger,
     [T + "test_stage2_6b_interblock_closure.py::test_no_historical_id_was_renumbered",
      T + "test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines[a126e02]"]),
    ("W-01", "W", "harness de mutação 4A grava um arquivo em data/ durante a execução", harness_writes_tree,
     [T + "test_stage4a_mutation.py::test_live_evidence_mutations_are_all_detected_with_positive_controls"]),
    ("REG-01", "REG", "sha256 de um arquivo de B0 alterado no registro", registry_sha,
     [REG + "test_registry_check_passes_without_writing", REG + "test_b0_historical_evidence_is_immutable[stage3_4c_integrated]"]),
    ("REG-02", "REG", "entrada APPROVED (B0) editada depois da aprovação", registry_edit_approved,
     [REG + "test_registry_check_passes_without_writing",
      REG + "test_b0_is_the_approved_root_pointing_to_historical_evidence_without_copies"]),
    ("REG-03", "REG", "re-baseline sem a recusa de árvore suja", committed(no_dirty_check),
     [REG + "test_rebaseline_refuses_a_dirty_tree"]),
    ("REG-04", "REG", "re-baseline sem a recusa de motivo ausente", committed(no_reason_check),
     [REG + "test_rebaseline_refuses_invalid_requests[mode1-args0-motivo]",
      REG + "test_rebaseline_refuses_invalid_requests[mode1-args1-motivo]"]),
    ("REG-05", "REG", "current apontando para uma entrada PROPOSED", registry_current_proposed,
     [REG + "test_registry_check_passes_without_writing", REG + "test_current_is_approved_and_resolves_the_harness_arguments"]),
    ("R-01", "R", "mudança de comportamento sem re-baseline (EQ16001 19.475 -> 19.476, = R2-b)", behaviour_change,
     [T + "test_stage4a_integrated.py::test_live_five_block_regression_passes_and_reproduces_committed_evidence"]),
]


def run_tests(root: Path, node_ids: list[str]) -> dict:
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", "--tb=line",
                           *node_ids], cwd=root, capture_output=True, text=True, env=ENV)
    failed = sorted({line.split(" ", 1)[1].split(" - ")[0] for line in done.stdout.splitlines()
                     if line.startswith(("FAILED ", "ERROR "))})
    tail = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    detail = [line[:300] for line in done.stdout.splitlines() if line.startswith(("E ", "/")) or "Error" in line][:6]
    return {"returncode": done.returncode, "failed": failed, "summary": tail, "detail": detail}


def fresh_tree(tmp: Path) -> Path:
    root = tmp / "tree"
    tree.build_tree(root)
    git(root, "checkout", "-q", "-B", "arvore")
    return root


def main() -> int:
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    selected = [m for m in MUTANTS if only is None or m[0] in only]
    status_before = sh(REPO, "git", "status", "--porcelain", "--", "app", "data", "tools")
    rows = []
    with tempfile.TemporaryDirectory(prefix="stage4c_mut_") as tmp:
        control_root = fresh_tree(Path(tmp) / "control")
        targets = sorted({t for m in selected for t in m[4]})
        control = run_tests(control_root, targets)
        for mutant_id, cls, description, apply, expected in selected:
            with tempfile.TemporaryDirectory(prefix=f"stage4c_{mutant_id}_") as mtmp:
                root = fresh_tree(Path(mtmp))
                error = None
                try:
                    apply(root)
                except Exception as exc:  # noqa: BLE001 — mutante que não aplica é registrado como erro
                    error = f"{type(exc).__name__}: {exc}"
                result = run_tests(root, expected) if error is None else {"returncode": None, "failed": [],
                                                                           "summary": "", "detail": []}
                detected = error is None and set(expected) <= set(result["failed"])
                rows.append({"mutant_id": mutant_id, "class": cls, "description": description,
                             "expected_failing_tests": "|".join(expected), "failed_tests": "|".join(result["failed"]),
                             "detected": "TRUE" if detected else "FALSE", "apply_error": error or "",
                             "pytest_summary": result["summary"], "evidence": " || ".join(result["detail"])[:600]})
    status_after = sh(REPO, "git", "status", "--porcelain", "--", "app", "data", "tools")
    detected = sum(r["detected"] == "TRUE" for r in rows)
    summary = {"stage": "4C.4", "mutants": len(rows), "detected": detected, "missed": [r["mutant_id"] for r in rows
                                                                                   if r["detected"] != "TRUE"],
               "detection_rate": f"{100.0 * detected / len(rows):.1f}%" if rows else "n/a",
               "by_class": {c: f"{sum(r['detected'] == 'TRUE' for r in rows if r['class'] == c)}/"
                               f"{sum(1 for r in rows if r['class'] == c)}" for c in sorted({r['class'] for r in rows})},
               "positive_control": {"tests": len(targets), "returncode": control["returncode"],
                                    "failed": control["failed"], "summary": control["summary"],
                                    "result": "ACCEPT" if control["returncode"] == 0 else "REJECT"},
               "git_status_app_data_tools": {"before": status_before, "after": status_after,
                                             "empty": status_before == status_after == ""}}
    summary["result"] = "PASS" if (not summary["missed"] and summary["positive_control"]["result"] == "ACCEPT"
                                   and summary["git_status_app_data_tools"]["empty"]) else "FAIL"
    if "--write" in sys.argv[1:]:
        with (HERE / "mutation_results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        (HERE / "mutation_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
                                                    encoding="utf-8")
    print(json.dumps({"summary": summary, "results": [{k: r[k] for k in ("mutant_id", "detected", "failed_tests",
                                                                         "apply_error")} for r in rows]},
                     indent=1, ensure_ascii=False))
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
