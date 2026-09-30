"""
Stage 3.4D — MUTANTES DE CÓDIGO (contrato 3.4A §19).

Cada mutante é uma substituição textual ÚNICA em um arquivo de `app/`,
aplicada somente a uma cópia temporária (clone local de HEAD + harness atual,
em tempfile.TemporaryDirectory, apagada ao fim). O repositório nunca é
tocado (verificado antes e depois por `git status`/`git diff`).

Detectores, todos reais e sem conhecimento do mutante:
  * TESTS       — suíte existente de testes unitários/contrato na árvore mutada
                  (`pytest -x`, sem os três testes de harness 3.4B/3.4C/3.4D,
                  que são executados abaixo como auditoria);
  * INTEGRATED  — `mutant_probe.py` (auditores da 3.4C, regressão contra a
                  evidência versionada, cenários de estado);
  * DIFFERENTIAL — `run_differential.produce(mutate)` + `evaluate` (3.4B):
                  7877551 x candidate mutado; cobre só o caminho sem estado.

Controle positivo: a mesma árvore SEM mutação precisa passar nos três.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "audit" / "stage3_4" / "differential")]

import run_differential as differential  # noqa: E402

AGG = "app/engine/temporal_aggregation_service.py"
CTX = "app/engine/calculation_context.py"
RES = "app/engine/interblock_resolver.py"
STP = "app/domain/state_propagation.py"
EVA = "app/engine/expression_evaluator.py"
ORC = "app/engine/interblock_orchestrator.py"
IF_OLD = "            if condition:\n                return self._evaluate_node(node.body)\n"

# (id, contrato 3.4A §19, descrição, arquivo, trecho original, trecho mutado, detectores esperados)
CODE_MUTANTS = [
    ("CM-01", "aggregator arithmetic: AVERAGE (e MOVING, mesma aritmética)", "média divide por n+1", AGG,
     "            return sum(values) / len(values)\n", "            return sum(values) / (len(values) + 1)\n",
     ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-02", "aggregator arithmetic: SUM", "SUM descarta o primeiro sub-período", AGG,
     "                    return sum(values)\n", "                    return sum(values[1:])\n",
     ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-03", "aggregator arithmetic: integration_factor", "integration_factor ignorado", AGG,
     "value * rule.integration_factor for value in values", "value for value in values",
     ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-04", "aggregator arithmetic: WEIGHTED_AVERAGE (peso)", "peso ignorado no numerador", AGG,
     "            value * weight\n", "            value * 1.0\n", ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-05", "aggregator window: MOVING_AVERAGE (janela)", "janela móvel reduzida ao último dia", AGG,
     "            return month_window.start_date, month_window.end_date\n",
     "            return month_window.end_date, month_window.end_date\n", ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-06", "window_end", "window_end nunca preenchido (janelas colapsam na identidade do período)", CTX,
     "            return as_of\n", "            return None\n", ("TESTS", "INTEGRATED")),
    ("CM-07", "janela efetiva", "janela efetiva de agregação reduzida ao último dia", AGG,
     "        return target_period.start_date, target_period.end_date\n",
     "        return target_period.end_date, target_period.end_date\n", ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-08", "leitura interbloco: instância errada", "produtor lido sempre na primeira instância do vínculo", RES,
     "                link.source_definition_id,\n                scope_type=scope_type,\n"
     "                scope_value=scope_value,\n",
     "                link.source_definition_id,\n                scope_type=scope_type,\n"
     "                scope_value=link.instances[0][1],\n", ("TESTS", "INTEGRATED")),
    ("CM-09", "leitura interbloco: produtor errado", "produtor lido de outro vínculo", RES,
     "            return self.calculation_context.get_variable_result(\n                link.source_definition_id,\n",
     "            return self.calculation_context.get_variable_result(\n"
     "                sorted(item.source_definition_id for item in self.registry.links())[0],\n",
     ("TESTS", "INTEGRATED")),
    ("CM-10", "propagação de estado: descarte (equação)", "estado herdado das dependências descartado", STP,
     "    return Result(value=None, state=state, detail=detail)\n", "    return None\n", ("TESTS", "INTEGRATED")),
    ("CM-11", "propagação de estado: descarte (agregação)", "Policy B não compõe o estado dos componentes", STP,
     "    composed = compose_states(target_variable_id, components)\n", "    composed = None\n",
     ("TESTS", "INTEGRATED")),
    ("CM-12", "composição de state: escolha de estado", "estados diferentes: escolhe o primeiro em vez do erro", STP,
     "        _raise_multi_state(target_variable_id, present)\n", "        pass\n", ("TESTS", "INTEGRATED")),
    ("CM-13", "composição de detail", "details diferentes: escolhe o primeiro em vez do erro", STP,
     "        _raise_multi_detail(target_variable_id, state, present[state])\n", "        pass\n",
     ("TESTS", "INTEGRATED")),
    ("CM-14", "seleção de ramo IF", "condição do IF invertida", EVA,
     IF_OLD, "            if not condition:\n                return self._evaluate_node(node.body)\n",
     ("TESTS", "INTEGRATED", "DIFFERENTIAL")),
    ("CM-15", "IF: propagação estrutural", "estado do ramo INATIVO propagado (avaliação especulativa)", EVA,
     IF_OLD, "            inactive = self._evaluate_node(node.orelse if condition else node.body)\n"
             "            if isinstance(inactive, StatedOperand):\n                return inactive\n" + IF_OLD,
     ("TESTS", "INTEGRATED")),
    ("CM-16", "ordenação do plano", "fila de prontos LIFO em vez de heap canônico", ORC,
     "            key = heapq.heappop(ready)\n", "            key = ready.pop()\n", ("INTEGRATED",)),
    ("CM-17", "determinismo", "escolha do próximo nó dependente de hash() (PYTHONHASHSEED)", ORC,
     "            key = heapq.heappop(ready)\n",
     "            key = min(ready, key=hash)\n            ready.remove(key)\n            heapq.heapify(ready)\n",
     ("INTEGRATED",)),
]
HARNESS_TESTS = ("tests/test_stage3_4b_differential.py", "tests/test_stage3_4c_integrated.py",
                 "tests/test_stage3_4d_mutation.py")


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
    """
    Clone local de HEAD (`git clone --shared`: lê os objetos do repositório original, nunca
    escreve nele; alguns testes leem o histórico git) + harness atual da Stage 3.4.
    """
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                          check=True).stdout.strip()
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(root)], check=True)
    subprocess.run(["git", "checkout", "-q", head], cwd=root, check=True)
    for name in ("integrated", "differential", "mutation"):
        target = root / "audit" / "stage3_4" / name
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(REPO / "audit" / "stage3_4" / name, target,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "evidence"))
    shutil.copytree(REPO / "audit" / "stage3_4" / "integrated" / "evidence",
                    root / "audit" / "stage3_4" / "integrated" / "evidence")
    for name in HARNESS_TESTS:
        if (REPO / name).exists():
            shutil.copy2(REPO / name, root / name)


def expected_integrated() -> dict:
    summary = json.loads((REPO / "audit/stage3_4/integrated/evidence/integrated_summary.json").read_text(encoding="utf-8"))
    import csv
    order = [r["node"] for r in csv.DictReader((REPO / "audit/stage3_4/integrated/evidence/nodes.csv").open(encoding="utf-8"))]
    return {"results_sha256": summary["determinism"]["RUN_A"]["results_sha256"],
            "plan_order_sha256": hashlib.sha256(json.dumps(order).encode()).hexdigest()}


def clean_env(seed: str = "0") -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}
    env["PYTHONHASHSEED"] = seed
    return env


def run_tests(root: Path) -> list[str]:
    ignore = [f"--ignore={t}" for t in HARNESS_TESTS]
    done = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *ignore],
                          cwd=root, capture_output=True, text=True, env=clean_env())
    if done.returncode == 0:
        return []
    failed = [line for line in done.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    return [f"TESTS_FAILED {(failed or done.stdout.splitlines()[-1:])[0][:200]}"]


def run_integrated_probe(root: Path, expected: dict) -> list[str]:
    problems = []
    outputs = {}
    for seed in ("0", "4242"):
        mode = [] if seed == "0" else ["--regression-only"]
        done = subprocess.run([sys.executable, "-I", str(root / "audit/stage3_4/mutation/mutant_probe.py"),
                               json.dumps(expected), *mode], cwd=root, capture_output=True, text=True,
                              env=clean_env(seed))
        if done.returncode != 0:
            return [f"PROBE_CRASHED seed={seed} {done.stderr.strip().splitlines()[-1][:200]}"]
        outputs[seed] = json.loads(done.stdout)
        if outputs[seed]["modules_outside_tree"]:
            return [f"HARNESS_FAILURE módulos fora da árvore {outputs[seed]['modules_outside_tree'][:2]}"]
        problems += [f"{p} (PYTHONHASHSEED={seed})" for p in outputs[seed]["problems"]]
    return problems


def run_differential(relative: str | None, old: str | None, new: str | None) -> list[str]:
    def mutate(candidate_root):
        if relative is not None:
            patch(candidate_root, relative, old, new)
    try:
        produced = differential.produce(mutate)
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or b"").decode(errors="replace").strip().splitlines()[-1:] if exc.stderr else []
        return [f"DIFFERENTIAL_RUNNER_FAILED {tail}"]
    evaluated = differential.evaluate(produced["reference"], produced["candidate"])
    problems = [p for p in produced["problems"] if "mesmo código" not in p] + evaluated["problems"]
    kinds = sorted({t for _k, types in evaluated["differences"] for t in types})
    return [f"DIFFERENTIAL {kinds} {problems[:2]}"] if problems else []


def evaluate_mutant(mutant, expected) -> dict:
    mutant_id, contract, description, relative, old, new, detectors = mutant
    with tempfile.TemporaryDirectory(prefix=f"stage3_4d_{mutant_id}_") as tmp:
        root = Path(tmp) / "tree"
        build_tree(root)
        if relative is not None:
            patch(root, relative, old, new)
        found = {"TESTS": run_tests(root), "INTEGRATED": run_integrated_probe(root, expected)}
    found["DIFFERENTIAL"] = run_differential(relative, old, new)
    detected_by = sorted(k for k, v in found.items() if v)
    missing = sorted(set(detectors) - set(detected_by))
    return {"mutant_id": mutant_id, "contract": contract, "description": description, "file": relative,
            "expected_detectors": "|".join(detectors), "detected_by": "|".join(detected_by),
            "detected": "TRUE" if not missing else "FALSE", "missing_detectors": "|".join(missing),
            "result": "PASS" if not missing else "FAIL",
            "evidence": " || ".join(f"{k}: {v[0][:160]}" for k, v in sorted(found.items()) if v)[:600]}


def run_all(workers: int = 4) -> tuple[dict, list[dict]]:
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    expected = expected_integrated()
    control = ("CM-00", "controle positivo", "árvore sem mutação", None, None, None, ())
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda m: evaluate_mutant(m, expected), [control, *CODE_MUTANTS]))
    after = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout
    control_row, rows = results[0], results[1:]
    control_row["result"] = "ACCEPT" if not control_row["detected_by"] else "REJECT"
    killed = sum(r["detected"] == "TRUE" for r in rows)
    summary = {"introduced": len(rows), "detected": killed, "surviving": len(rows) - killed,
               "surviving_ids": [r["mutant_id"] for r in rows if r["detected"] != "TRUE"],
               "positive_control": control_row,
               "repository_untouched": before == after == "",
               "by_detector": {d: sum(d in r["detected_by"].split("|") for r in rows)
                               for d in ("TESTS", "INTEGRATED", "DIFFERENTIAL")}}
    return summary, rows
