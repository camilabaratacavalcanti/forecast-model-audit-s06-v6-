"""
Etapa 3.3B — testes de mutação da auditoria black-box.

    python audit/stage3_3b_state_propagation/evidence/mutation_check.py [--no-write]

Para cada mutação: copia `app/`, `data/seed/`, a evidência de planos da
3.2 e os scripts desta auditoria para um diretório temporário, aplica UMA
alteração de uma linha no código do runtime (nunca no repositório real)
e executa `analysis_stage3_3b.py --no-write` na cópia. A auditoria
precisa FALHAR em toda mutação e PASSAR na cópia sem mutação.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WRITE = "--no-write" not in sys.argv[1:]

MUTATIONS = {
    "M0_NONE": None,
    "M1_PICK_ONE_OF_TWO_STATES": (
        "app/domain/state_propagation.py",
        "    if len(states) > 1:", "    if False:"),
    "M2_PICK_ONE_OF_TWO_DETAILS": (
        "app/domain/state_propagation.py",
        "    if len(details) > 1:", "    if False:"),
    # propagação estrutural: todo IF avalia os DOIS ramos e une os estados
    "M3_INACTIVE_BRANCH_PROPAGATES": (
        "app/engine/expression_evaluator.py",
        "            if condition:\n                return self._evaluate_node(node.body)",
        "            both = StatedOperand.merge(self._evaluate_node(node.body), "
        "self._evaluate_node(node.orelse))\n"
        "            if both is not None:\n"
        "                return both\n"
        "            if condition:\n                return self._evaluate_node(node.body)"),
    "M4_NO_TEMPORAL_WINDOW": (
        "app/engine/calculation_context.py",
        '        if as_of.startswith(f"{period_id}-"):', "        if False:"),
    "M5_SILENT_OVERWRITE": (
        "app/engine/interblock_resolver.py",
        "        if existing is not _MISSING and not results_equivalent(existing, value):",
        "        if False:"),
    "M6_DETAIL_WITHOUT_STATE_ALLOWED": (
        "app/domain/results.py",
        "    if detail is not None and state is None:", "    if False:"),
}


def workspace(root: Path) -> None:
    shutil.copytree(REPO / "app", root / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "data" / "seed", root / "data" / "seed")
    plans = root / "audit/stage3_2_execution_orchestration/evidence"
    plans.mkdir(parents=True)
    shutil.copy(REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv", plans)
    evidence = root / "audit/stage3_3b_state_propagation/evidence"
    evidence.mkdir(parents=True)
    for name in ("analysis_stage3_3b.py", "runtime_probe.py"):
        shutil.copy(HERE / name, evidence)


def mutate(root: Path, spec) -> None:
    path, old, new = spec
    file = root / path
    text = open(file, encoding="utf-8", newline="").read()
    if "\r\n" in text:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    if text.count(old) != 1:
        raise SystemExit(f"mutação não aplicável ({text.count(old)}x): {path}: {old!r}")
    open(file, "w", encoding="utf-8", newline="").write(text.replace(old, new))


rows = []
ok = True
for name, spec in MUTATIONS.items():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace(root)
        if spec:
            mutate(root, spec)
        completed = subprocess.run(
            [sys.executable, str(root / "audit/stage3_3b_state_propagation/evidence/analysis_stage3_3b.py"),
             "--no-write"], capture_output=True, text=True, cwd=root,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    detected = completed.returncode != 0
    counters = sorted({line.split("]")[0] + "]" for line in completed.stdout.splitlines() if line.startswith("[")})
    expected = spec is not None
    status = "OK" if detected == expected else "UNEXPECTED"
    ok &= status == "OK"
    rows.append(f"{name}: audit_exit={completed.returncode} detected={detected} "
                f"expected_detection={expected} {status} {' '.join(counters)}")

report = "\n".join(rows) + f"\nMUTATION_CHECK: {'PASS' if ok else 'FAIL'}\n"
print(report, end="")
if WRITE:
    (HERE / "mutation_results.txt").write_text(report, encoding="utf-8")
sys.exit(0 if ok else 1)
