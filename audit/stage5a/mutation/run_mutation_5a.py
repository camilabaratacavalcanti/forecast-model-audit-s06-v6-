"""
Stage 5A.4 — mutação dos contratos da 5A (D-5A-1, D-5A-2, D-5A-3, D-5A-4).

    python audit/stage5a/mutation/run_mutation_5a.py [--write] [--only ID[,ID...]]

Mesmo método da 4C.4 (`audit/stage4c/mutation/run_mutation_4c.py`): cada mutante roda num CLONE TEMPORÁRIO
(`git clone --shared` do HEAD + árvore atual de audit/ e tests/, `rehearse_5a.build_tree`); o mutante é
DETECTADO quando todos os testes esperados falham. O controle positivo (clone sem mutação) roda o mesmo
conjunto e precisa passar. `git status --porcelain -- app data tools` do repositório é registrado antes e
depois e precisa ficar vazio. Com `--write` grava `mutation_results.csv` e `mutation_summary.json` aqui.

Mutantes exigidos pelo prompt da 5A:
    EQ-01/02  EQ renumerado / EQ aposentado reutilizado (S)
    LED-01    livro de equações ignorado (volta à numeração posicional)
    SUM-01    builder aceita SUM de origem /h silenciosamente
    RT-01     runtime aceita integration_factor 24
    UNIT-*    unidade nova removida do enum (uma por unidade; + validador de parâmetros)
    SPEC-01   sha256 do BlockSpec diverge do workbook
    VAR-01    VAR aposentado reaparece com o ID antigo
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "audit" / "stage4c" / "rehearsal"))

import rehearse_5a as tree  # noqa: E402  (build_tree / clean_env do ensaio 4C)

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


def replace_everywhere(root: Path, relatives, old: str, new: str) -> None:
    """Troca consistente (como faria um builder com defeito): seeds e livro juntos."""
    total = 0
    for relative in relatives:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        total += text.count(f'"{old}"')
        path.write_text(text.replace(f'"{old}"', f'"{new}"'), encoding="utf-8")
    assert total > 0, (old, relatives)


# ------------------------------------------------------------------ mutantes
def eq_renumber(root):
    # EQ18001 -> EQ18099 nos seeds e no livro do energy: mesma identidade, ID novo.
    replace_everywhere(root, ["data/seed/energy/equations.json", "data/id_ledger/energy.json"], "EQ18001", "EQ18099")


def eq_reuse_retired(root):
    # EQ13030 (alimentacao_evap_total, identidade nova da v13) passa a usar EQ13001, aposentado na 5A.
    replace_everywhere(root, ["data/seed/max_ht/equations.json"], "EQ13030", "EQ13001")
    path = root / "data/id_ledger/max_ht.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload["equations"]:
        if entry["equation_id"] == "EQ13030":
            entry["equation_id"] = "EQ13001"
    payload["retired_equations"] = [r for r in payload["retired_equations"] if r["equation_id"] != "EQ13001"]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ledger_ignored(root):
    edit(root, "tools/workbook_seed/seeds.py",
         "    ledger = model.id_ledger.equations if model.id_ledger is not None else None\n",
         "    ledger = None  # mutante: livro de equações ignorado\n")


def builder_accepts_hourly_sum(root):
    edit(root, "tools/workbook_seed/seeds.py", "                if factor != 1:\n",
         "                if False:  # mutante: SUM /h aceita em silêncio\n")


def runtime_accepts_24(root):
    edit(root, "app/domain/forecast/aggregation.py", "        if self.integration_factor != 1:\n",
         "        if self.integration_factor not in (1, 24):\n")


def unit_removed(unit, relative="app/validation/variable_seed_validator.py"):
    def apply(root):
        edit(root, relative, f'    "{unit}",\n', "")
    return apply


def block_spec_sha(root):
    edit(root, "tools/workbook_seed/blocks.py", "731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2",
         "731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de3")


def retired_var_reappears(root):
    # alimentacao_evap@L1 (VAR13117, nova na v13) volta a usar VAR13001, aposentado na 5A (D-5A-3).
    seeds = [f"data/seed/max_ht/{n}.json" for n in ("manifest", "variables", "equations", "aggregation_rules")]
    replace_everywhere(root, seeds + ["data/seed/interblock_links.json"], "VAR13117", "VAR13001")
    path = root / "data/id_ledger/max_ht.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        if entry["entity_id"] == "VAR13117":
            entry["entity_id"] = "VAR13001"
    payload["retired"] = [r for r in payload["retired"] if r["entity_id"] != "VAR13001"]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


T = "tests/"
LED = T + "test_stage5a_equation_ledger.py::"
SUM = T + "test_stage5a_sum_daily_origin.py::"
UNITS = ("kWh/tv", "tv/MWh", "tv/t carvão", "GJ/d", "m³/d")


def node_id(unit: str) -> str:
    """ID de parametrização como o pytest o escreve (não ASCII escapado: `carv\\xe3o`, `m\\xb3/d`)."""
    return unit.encode("unicode_escape").decode("ascii")
MUTANTS = [
    # id, classe, descrição, aplicar(clone), testes-alvo que precisam falhar
    ("EQ-01", "S", "EQ renumerado (EQ18001 -> EQ18099, seeds e livro do energy)", eq_renumber,
     [LED + "test_equation_ids_are_never_renumbered_retired_or_reused_since_b0[energy]"]),
    ("EQ-02", "S", "EQ aposentado reutilizado (EQ13001 numa identidade nova do max_ht)", eq_reuse_retired,
     [LED + "test_equation_ids_are_never_renumbered_retired_or_reused_since_b0[max_ht]"]),
    ("LED-01", "D-5A-4", "livro de equações ignorado: numeração posicional", ledger_ignored,
     [LED + "test_ledger_payload_reproduces_the_versioned_ledger[energy]",
      LED + "test_ledger_payload_reproduces_the_versioned_ledger[max_ht]"]),
    ("SUM-01", "D-5A-2", "builder aceita SUM de origem /h (fator 24) em silêncio", builder_accepts_hourly_sum,
     [SUM + "test_builder_rejects_sum_of_an_hourly_origin_and_names_the_ag_variable"]),
    ("RT-01", "D-5A-2", "runtime aceita integration_factor 24", runtime_accepts_24,
     [SUM + "test_runtime_refuses_integration_factor_other_than_one[24.0-SUM]",
      SUM + "test_runtime_refuses_integration_factor_other_than_one[24-SUM]",
      T + "test_aggregation_dimensions.py::test_sum_applies_integration_factor"]),
    *[(f"UNIT-0{i}", "D-5A-1", f"unidade {u!r} removida do enum de variáveis", unit_removed(u),
       [LED + f"test_new_units_are_allowed_for_variables_and_parameters[{node_id(u)}]"])
      for i, u in enumerate(UNITS, start=1)],
    ("UNIT-06", "D-5A-1", "unidade 'GJ/d' removida do enum de parâmetros",
     unit_removed("GJ/d", "app/validation/parameter_seed_validator.py"),
     [LED + "test_new_units_are_allowed_for_variables_and_parameters[GJ/d]"]),
    ("SPEC-01", "BlockSpec", "sha256 do BlockSpec do energy diverge do workbook v9", block_spec_sha,
     [T + "test_stage2_4_workbook_contract.py::test_t24_14_source_reference_is_the_workbook_actually_read[energy]"]),
    ("VAR-01", "S", "VAR aposentado reaparece com o ID antigo (VAR13001 em alimentacao_evap)", retired_var_reappears,
     [T + "test_stage2_6b_interblock_closure.py::test_no_historical_id_was_renumbered",
      T + "test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines[a126e02]",
      T + "test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines[eceffd4]"]),
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
    with tempfile.TemporaryDirectory(prefix="stage5a_mut_") as tmp:
        control_root = fresh_tree(Path(tmp) / "control")
        targets = sorted({t for m in selected for t in m[4]})
        control = run_tests(control_root, targets)
        for mutant_id, cls, description, apply, expected in selected:
            with tempfile.TemporaryDirectory(prefix=f"stage5a_{mutant_id}_") as mtmp:
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
    summary = {"stage": "5A.4", "mutants": len(rows), "detected": detected,
               "missed": [r["mutant_id"] for r in rows if r["detected"] != "TRUE"],
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
