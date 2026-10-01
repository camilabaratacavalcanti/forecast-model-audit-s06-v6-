"""
Stage 4B.3b — MUTANTES DE CÓDIGO temporais (método das 3.4D/4A, estendido).

Cada mutante é uma substituição textual ÚNICA em `app/engine/*` aplicada SOMENTE numa cópia
temporária (`git clone --shared` do HEAD + árvore atual de audit/stage4a e audit/stage4b, em
`tempfile.TemporaryDirectory`). A árvore de trabalho nunca é tocada (`git status -- app data tools`
registrado antes e depois).

Detectores 4B, reais e sem conhecimento do mutante (rodam na árvore mutada):
  * TEMPORAL_T2 — `temporal/run_temporal_4b.py --range T2 --no-write` (2028, bissexto: janelas por data,
                  snapshots, MOVING_AVERAGE, reexecução, determinismo);
  * TURN_E1_E5  — `derive_4b.py --no-write` (virada 2026->2027 com contexto de um ano, E2–E5, colisões);
  * ORACLE_T    — `oracle/run_oracle_4b.py --no-write --ranges T2` (aritmética de agregação + calendário,
                  incluindo a execução curta com estado).
Controle positivo (CM4B-00): a árvore sem mutação passa nos três.
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
TPR = "app/engine/time_period_resolver.py"
AGG = "app/engine/temporal_aggregation_service.py"
CTX = "app/engine/calculation_context.py"
DETECTORS = ("TEMPORAL_T2", "TURN_E1_E5", "ORACLE_T")

# (id, descrição, arquivo, trecho original, trecho mutado, detectores esperados)
CODE_MUTANTS = [
    ("CM4B-01", "YTD começa no dia errado (2 de janeiro)", TPR,
     "            year_start = date(run_date.year, 1, 1)\n",
     "            year_start = date(run_date.year, 1, 2) if run_date.day > 1 or run_date.month > 1 else run_date\n",
     ("TEMPORAL_T2", "ORACLE_T")),
    ("CM4B-02", "janela mensal com off-by-one no último dia (exclui run_date)", TPR,
     '                frequency="mensal",\n                start_date=month_start,\n                end_date=run_date,\n',
     '                frequency="mensal",\n                start_date=month_start,\n'
     '                end_date=run_date - timedelta(days=1) if run_date.day > 1 else run_date,\n',
     ("TEMPORAL_T2", "ORACLE_T")),
    ("CM4B-03", "period_id anual derivado com o mês (AAAA-MM)", TPR,
     '                period_id=f"{run_date.year:04d}",\n',
     '                period_id=f"{run_date.year:04d}-{run_date.month:02d}",\n',
     ("TEMPORAL_T2", "TURN_E1_E5", "ORACLE_T")),
    ("CM4B-04", "bissexto ignorado: 29/fev pulado na enumeração dos sub-períodos", AGG,
     "            current_date += timedelta(days=1)\n\n        return period_ids\n",
     "            current_date += timedelta(days=1)\n"
     "            if (current_date.month, current_date.day) == (2, 29):\n"
     "                current_date += timedelta(days=1)\n\n        return period_ids\n",
     ("TEMPORAL_T2", "ORACLE_T")),
    ("CM4B-05", "MOVING_AVERAGE sem reinício mensal (janela desde 1º de janeiro)", AGG,
     '            month_window = self.time_period_resolver.effective_window(\n                frequency="mensal",\n',
     '            month_window = self.time_period_resolver.effective_window(\n                frequency="anual",\n',
     ("TEMPORAL_T2", "ORACLE_T")),
    ("CM4B-06", "snapshot do ano anterior sobrescrito na virada (em 1º/jan o anual grava no ano anterior)", TPR,
     '                period_id=f"{run_date.year:04d}",\n',
     '                period_id=f"{(run_date - timedelta(days=1)).year:04d}" if (run_date.month, run_date.day) == (1, 1) '
     'and run_date.year > 2026 else f"{run_date.year:04d}",\n',
     ("TURN_E1_E5",)),
    ("CM4B-07", "carry-over silencioso: entrada anual ausente lida do ano anterior", CTX,
     "        if base in self._scoped_results:\n            return base\n",
     "        if base in self._scoped_results:\n            return base\n\n"
     "        if period_id and len(period_id) == 4:\n"
     "            previous = CalculationKey(variable_id, scope_type, scope_value, f\"{int(period_id) - 1:04d}\")\n"
     "            if previous in self._scoped_results:\n                return previous\n",
     ("TURN_E1_E5",)),
    ("CM4B-08", "perda de estado na agregação anual (estado descartado, valor 0)", AGG,
     "        result = compose_aggregated_result(\n            rule.target_variable_id, sources + weights, aggregate_values\n        )\n",
     "        result = compose_aggregated_result(\n            rule.target_variable_id, sources + weights, aggregate_values\n        )\n"
     "        if rule.target_frequency == \"anual\" and result.state is not None:\n"
     "            result = type(result)(value=0.0)\n",
     ("ORACLE_T",)),
]


def patch(root: Path, relative: str, old: str, new: str) -> None:
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
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                          check=True).stdout.strip()
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(root)], check=True)
    subprocess.run(["git", "checkout", "-q", head], cwd=root, check=True)
    for name in ("stage4a", "stage4b"):
        shutil.rmtree(root / "audit" / name, ignore_errors=True)
        shutil.copytree(REPO / "audit" / name, root / "audit" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "stage4b_*"))


def clean_env(seed: str = "0") -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}
    env["PYTHONHASHSEED"] = seed
    return env


def run_script(root: Path, *args: str) -> list[str]:
    done = subprocess.run([sys.executable, "-I", *[str(root / args[0]), *args[1:]]], cwd=root,
                          capture_output=True, text=True, env=clean_env())
    if done.returncode == 0:
        return []
    try:
        problems = json.loads(done.stdout).get("problems") or ["result FAIL"]
    except (json.JSONDecodeError, AttributeError):
        problems = [f"CRASHED {(done.stderr.strip().splitlines() or ['?'])[-1][:200]}"]
    return [str(p)[:220] for p in problems]


def evaluate_mutant(mutant) -> dict:
    mutant_id, description, relative, old, new, expected = mutant
    with tempfile.TemporaryDirectory(prefix=f"stage4b_{mutant_id}_") as tmp:
        root = Path(tmp) / "tree"
        build_tree(root)
        if relative is not None:
            patch(root, relative, old, new)
        found = {"TEMPORAL_T2": run_script(root, "audit/stage4b/temporal/run_temporal_4b.py", "--range", "T2", "--no-write"),
                 "TURN_E1_E5": run_script(root, "audit/stage4b/derive_4b.py", "--no-write"),
                 "ORACLE_T": run_script(root, "audit/stage4b/oracle/run_oracle_4b.py", "--no-write", "--ranges", "T2")}
    detected_by = sorted(k for k, v in found.items() if v)
    missing = sorted(set(expected) - set(detected_by))
    return {"mutant_id": mutant_id, "description": description, "file": relative,
            "expected_detectors": "|".join(expected), "detected_by": "|".join(detected_by),
            "detected": "TRUE" if detected_by else "FALSE", "missing_expected_detectors": "|".join(missing),
            "result": "PASS" if detected_by and not missing else "FAIL",
            "evidence": " || ".join(f"{k}: {v[0][:160]}" for k, v in sorted(found.items()) if v)[:700]}


def run_all(workers: int = 3) -> tuple[dict, list[dict]]:
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    control = ("CM4B-00", "controle positivo: árvore sem mutação", None, None, None, ())
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
               "positive_control": control_row, "repository_untouched": before == after == "",
               "by_detector": {d: sum(d in r["detected_by"].split("|") for r in rows) for d in DETECTORS}}
    return summary, rows
