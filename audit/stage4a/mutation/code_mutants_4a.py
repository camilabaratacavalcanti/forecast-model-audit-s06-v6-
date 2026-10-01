"""
Stage 4A.3b — MUTANTES DE CÓDIGO e de SEED do area_41 (método da 3.4D, estendido).

Cada mutante é uma substituição textual ÚNICA (ou uma edição JSON) aplicada SOMENTE a uma
cópia temporária: `git clone --shared` do HEAD + a árvore atual de `audit/stage4a` e dos testes
4A, dentro de `tempfile.TemporaryDirectory` (apagada ao fim). A árvore de trabalho nunca é
tocada: `git status --porcelain -- app data tools` é registrado antes e depois.

Detectores 4A, reais e sem conhecimento do mutante (rodam na árvore mutada, `python -I`):
  * ORACLE        — `oracle/run_oracle.py --no-write` (fidelidade ao workbook: o workbook não muda);
  * INTEGRATED_4A — `integrated/run_integrated_4a.py --no-write` (universo, estados, não-regressão,
                    regressão contra a evidência 4A versionada);
  * CONTRACT_4A   — `derive_4a.py --no-write` (cardinalidades, árvore de hes x texto literal, F, escopos,
                    expectativas congeladas, sha256 dos vínculos);
  * TESTS         — testes existentes de engine/seeds/contrato que tocam o area_41 (`pytest -x`, informativo).

Controle positivo (CM4A-00): a mesma árvore SEM mutação precisa passar em todos os detectores.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
EQ = "data/seed/area_41/equations.json"
AGG = "data/seed/area_41/aggregation_rules.json"
EVA = "app/engine/expression_evaluator.py"
STP = "app/domain/state_propagation.py"
LINKS = "data/seed/interblock_links.json"
DETECTORS_4A = ("ORACLE", "INTEGRATED_4A", "CONTRACT_4A")
TESTS = ("tests/test_stage2_4_workbook_contract.py", "tests/test_stage3_3b_state_propagation.py",
         "tests/test_stage3_2_execution_orchestration.py", "tests/test_stage2_6b_interblock_closure.py",
         "tests/test_taxonomy_migration_d_tax_01.py")


def remove_link_var16007(root: Path) -> None:
    path = root / LINKS
    payload = json.loads(path.read_text(encoding="utf-8"))
    before = len(payload["links"])
    payload["links"] = [link for link in payload["links"] if link["consumer_definition"] != "VAR16007"]
    if len(payload["links"]) != before - 1:
        raise RuntimeError("vínculo VAR16007 não encontrado")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# (id, descrição, arquivo, trecho original | função, trecho mutado, detectores 4A esperados)
CODE_MUTANTS = [
    ("CM4A-01", "condicional L4_L5 (EQ16011): `or` do ramo LC invertido para `and`", EQ,
     'if VAR16021@L4 == \\"LC\\" or VAR16021@L5 == \\"LC\\"',
     'if VAR16021@L4 == \\"LC\\" and VAR16021@L5 == \\"LC\\"', ("ORACLE", "CONTRACT_4A")),
    ("CM4A-02", "ramo \"F\" de EQ16011 trocado por 0 (o NO_APPLICABLE_RULE some)", EQ,
     'VAR16021@L5 == \\"1 By pass e LC\\" else \\"F\\"', 'VAR16021@L5 == \\"1 By pass e LC\\" else 0',
     ("ORACLE", "INTEGRATED_4A", "CONTRACT_4A")),
    ("CM4A-03", "engine: base do ln trocada (math.log -> math.log10)", EVA,
     "return math.log(value)", "return math.log10(value)", ("ORACLE", "INTEGRATED_4A")),
    ("CM4A-04", "EQ16006 (lth_grupo L6_L7): `/2` -> `/3`", EQ,
     "( VAR16007@L6 + VAR16007@L7 ) /2", "( VAR16007@L6 + VAR16007@L7 ) /3", ("ORACLE", "INTEGRATED_4A")),
    ("CM4A-05", "EQ16005 (lth_grupo L4_L5): `@L5` -> `@L4`", EQ,
     "( VAR16007@L4 + VAR16007@L5 ) / 2", "( VAR16007@L4 + VAR16007@L4 ) / 2", ("ORACLE", "INTEGRATED_4A")),
    ("CM4A-06", "vínculo yield.VAR11031 -> area_41.VAR16007 removido", LINKS, remove_link_var16007, None,
     ("INTEGRATED_4A", "CONTRACT_4A")),
    ("CM4A-07", "EQ16011 ramo `1 By pass`: desconto_retirada_41d (VAR16024) -> 41c (VAR16022)", EQ,
     "- VAR16024 )", "- VAR16022 )", ("ORACLE", "CONTRACT_4A")),
    ("CM4A-08", "EQ16012 ramo LC: constante `/ 24` -> `/ 23`", EQ,
     '/ 2 ) * 10 ) / 24 ) if VAR16021@L6 == \\"LC\\"', '/ 2 ) * 10 ) / 23 ) if VAR16021@L6 == \\"LC\\"',
     ("ORACLE", "CONTRACT_4A")),
    ("CM4A-09", "engine: tradução do literal declarado desligada (\"F\" fica como texto no valor)", STP,
     "            if value == declared_state.literal:\n", "            if False:\n",
     ("ORACLE", "INTEGRATED_4A", "CONTRACT_4A")),
    ("CM4A-10", "regra mensal de retirada_condensado_linha: AVERAGE -> SUM", AGG,
     '"target_variable_id": "VAR16032",\n    "target_frequency": "mensal",\n    "aggregation_type": "AVERAGE"',
     '"target_variable_id": "VAR16032",\n    "target_frequency": "mensal",\n    "aggregation_type": "SUM"',
     ("ORACLE", "INTEGRATED_4A")),
    ("CM4A-11", "EQ16013 (retirada_condensado_linha) com escopo L2 em vez de L1 (escopo da equação)", EQ,
     '"scope_value": "L1",\n    "expression": "( VAR16018@L1_L3 * VAR16007@L1 )',
     '"scope_value": "L2",\n    "expression": "( VAR16018@L1_L3 * VAR16007@L1 )', ("INTEGRATED_4A", "CONTRACT_4A")),
]


def patch(root: Path, relative: str, old, new) -> None:
    if callable(old):
        old(root)
        return
    path = root / relative
    data = path.read_bytes()
    crlf = b"\r\n" in data
    old_b, new_b = old.encode(), new.encode()
    if crlf:
        old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
    if data.count(old_b) != 1:
        raise RuntimeError(f"trecho do mutante não é único em {relative}: {data.count(old_b)}")
    path.write_bytes(data.replace(old_b, new_b))


def build_tree(root: Path) -> None:
    """Clone local de HEAD (`--shared`, só lê os objetos) + árvore atual de audit/stage4a e testes 4A."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                          check=True).stdout.strip()
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(root)], check=True)
    subprocess.run(["git", "checkout", "-q", head], cwd=root, check=True)
    shutil.rmtree(root / "audit" / "stage4a", ignore_errors=True)
    shutil.copytree(STAGE, root / "audit" / "stage4a", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for test in sorted((REPO / "tests").glob("test_stage4a_*.py")):
        shutil.copy2(test, root / "tests" / test.name)


def clean_env(seed: str = "0") -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}
    env["PYTHONHASHSEED"] = seed
    return env


def run_script(root: Path, relative: str) -> list[str]:
    done = subprocess.run([sys.executable, "-I", str(root / relative), "--no-write"], cwd=root,
                          capture_output=True, text=True, env=clean_env())
    if done.returncode == 0:
        return []
    try:
        problems = json.loads(done.stdout).get("problems") or ["result FAIL"]
    except (json.JSONDecodeError, AttributeError):
        problems = [f"CRASHED {(done.stderr.strip().splitlines() or ['?'])[-1][:200]}"]
    return [str(p)[:220] for p in problems]


def run_tests(root: Path) -> list[str]:
    done = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS],
                          cwd=root, capture_output=True, text=True, env=clean_env())
    if done.returncode == 0:
        return []
    failed = [line for line in done.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    return [f"TESTS_FAILED {(failed or done.stdout.splitlines()[-1:])[0][:200]}"]


def evaluate_mutant(mutant) -> dict:
    mutant_id, description, relative, old, new, expected = mutant
    with tempfile.TemporaryDirectory(prefix=f"stage4a_{mutant_id}_") as tmp:
        root = Path(tmp) / "tree"
        build_tree(root)
        if relative is not None:
            patch(root, relative, old, new)
        found = {"ORACLE": run_script(root, "audit/stage4a/oracle/run_oracle.py"),
                 "INTEGRATED_4A": run_script(root, "audit/stage4a/integrated/run_integrated_4a.py"),
                 "CONTRACT_4A": run_script(root, "audit/stage4a/derive_4a.py"),
                 "TESTS": run_tests(root)}
    detected_by = sorted(k for k, v in found.items() if v)
    detected_4a = sorted(set(detected_by) & set(DETECTORS_4A))
    missing = sorted(set(expected) - set(detected_by))
    return {"mutant_id": mutant_id, "description": description, "file": relative,
            "expected_detectors": "|".join(expected), "detected_by": "|".join(detected_by),
            "detected": "TRUE" if detected_4a else "FALSE", "missing_expected_detectors": "|".join(missing),
            "result": "PASS" if detected_4a and not missing else "FAIL",
            "evidence": " || ".join(f"{k}: {v[0][:160]}" for k, v in sorted(found.items()) if v)[:700]}


def run_all(workers: int = 4) -> tuple[dict, list[dict]]:
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    control = ("CM4A-00", "controle positivo: árvore sem mutação", None, None, None, ())
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(evaluate_mutant, [control, *CODE_MUTANTS]))
    after = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout
    control_row, rows = results[0], results[1:]
    control_row["result"] = "ACCEPT" if not control_row["detected_by"] else "REJECT"
    killed = sum(r["detected"] == "TRUE" for r in rows)
    summary = {"introduced": len(rows), "detected": killed, "surviving": len(rows) - killed,
               "surviving_ids": [r["mutant_id"] for r in rows if r["detected"] != "TRUE"],
               "expected_detectors_missed": {r["mutant_id"]: r["missing_expected_detectors"] for r in rows
                                             if r["missing_expected_detectors"]},
               "positive_control": control_row,
               "git_status_app_data_tools_before": before, "git_status_app_data_tools_after": after,
               "repository_untouched": before == after == "",
               "by_detector": {d: sum(d in r["detected_by"].split("|") for r in rows)
                               for d in (*DETECTORS_4A, "TESTS")}}
    return summary, rows
