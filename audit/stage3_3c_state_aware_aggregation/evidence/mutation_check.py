"""
Etapa 3.3C — testes de mutação da agregação consciente de Result.

    python audit/stage3_3c_state_aware_aggregation/evidence/mutation_check.py [--no-write]

Cada mutante é aplicado a uma CÓPIA (diretório temporário) de `app/`,
`data/seed/`, dos testes da 3.3C (e do módulo da 3.2 que eles importam)
e dos scripts desta auditoria — nunca ao repositório. Em cada cópia
rodam (a) `tests/test_stage3_3c_state_aware_aggregation.py` e (b) a
auditoria black-box. Um mutante é DETECTADO se (a) ou (b) falha; a
tabela registra os dois. A cópia sem mutação (M0) precisa passar em
ambos.
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
SP = "app/domain/state_propagation.py"
SERVICE = "app/engine/temporal_aggregation_service.py"
ORCH = "app/engine/interblock_orchestrator.py"

MUTATIONS = {
    "M0_NONE": [],
    # 1. descartar state
    "M1_DROP_STATE": [(SP, "    return Result(value=value, state=state, detail=detail)",
                       "    return Result(value=value)")],
    "M1b_SERVICE_DROPS_STATE": [(SERVICE, "            state=result.state,\n            detail=result.detail,\n", "")],
    "M1c_ORCHESTRATOR_WRITES_ONLY_VALUE": [(ORCH, "value.variable_id, value.result, value.scope_type",
                                            "value.variable_id, value.value, value.scope_type")],
    # 2. primeiro state
    "M2_FIRST_STATE_WINS": [(SP, "        _raise_multi_state(target_variable_id, present)", "        pass")],
    # 3. último state
    "M3_LAST_STATE_WINS": [(SP, "        _raise_multi_state(target_variable_id, present)",
                            "        states = states[-1:]")],
    # 4. primeiro detail
    "M4_FIRST_DETAIL_WINS": [(SP, "        _raise_multi_detail(target_variable_id, state, present[state])",
                              "        pass")],
    # 5. ignorar conflito de detail (descarta o detail em conflito)
    "M5_IGNORE_DETAIL_CONFLICT": [(SP, "        _raise_multi_detail(target_variable_id, state, present[state])",
                                   "        details = [None]")],
    # 6. None como state
    "M6_NONE_IS_A_STATE": [(SP, "        if result.state is not None:", "        if True:")],
    # 7. dependência de ordem (conflito só quando primeiro e último diferem)
    "M7_ORDER_DEPENDENT": [(SP, "    if len(states) > 1:",
                            "    if len(states) > 1 and components[0][1].state != components[-1][1].state:")],
    # 8. descartar detail
    "M8_DROP_DETAIL": [(SP, "    return Result(value=value, state=state, detail=detail)",
                        "    return Result(value=value, state=state)")],
    # 9. semântica x matemática inconsistentes
    "M9a_SEMANTICS_WITHOUT_WEIGHTS": [(SERVICE, "rule.target_variable_id, sources + weights, aggregate_values",
                                       "rule.target_variable_id, sources, aggregate_values")],
    "M9b_SEMANTICS_ON_LAST_DAY_ONLY": [(SERVICE, "rule.target_variable_id, sources + weights, aggregate_values",
                                        "rule.target_variable_id, sources[-1:] + weights, aggregate_values")],
    "M9c_MATH_IGNORES_VALUELESS": [(SP, "    if any(result.value is None for _key, result in components):",
                                    "    if False:")],
}


def workspace(root: Path) -> None:
    shutil.copytree(REPO / "app", root / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "data" / "seed", root / "data" / "seed")
    (root / "tests").mkdir()
    for name in ("test_stage3_3c_state_aware_aggregation.py", "test_stage3_2_execution_orchestration.py"):
        shutil.copy(REPO / "tests" / name, root / "tests")
    evidence = root / "audit/stage3_3c_state_aware_aggregation/evidence"
    evidence.mkdir(parents=True)
    for name in ("analysis_stage3_3c.py", "runtime_probe.py"):
        shutil.copy(HERE / name, evidence)


def mutate(root: Path, edits) -> None:
    for path, old, new in edits:
        file = root / path
        text = open(file, encoding="utf-8", newline="").read()
        if "\r\n" in text:
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        if text.count(old) != 1:
            raise SystemExit(f"mutação não aplicável ({text.count(old)}x): {path}: {old!r}")
        open(file, "w", encoding="utf-8", newline="").write(text.replace(old, new))


env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
rows, introduced, detected, survived = [], 0, 0, []
baseline_ok = True
for name, edits in MUTATIONS.items():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace(root)
        mutate(root, edits)
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "no:randomly",
             "tests/test_stage3_3c_state_aware_aggregation.py"],
            capture_output=True, text=True, cwd=root, env=env)
        audit = subprocess.run(
            [sys.executable, "audit/stage3_3c_state_aware_aggregation/evidence/analysis_stage3_3c.py", "--no-write"],
            capture_output=True, text=True, cwd=root, env=env)
    tests_fail, audit_fail = tests.returncode != 0, audit.returncode != 0
    counters = sorted({line.split("]")[0] + "]" for line in audit.stdout.splitlines() if line.startswith("[")})
    if not edits:
        baseline_ok = not tests_fail and not audit_fail
        status = "OK" if baseline_ok else "BASELINE_FAILED"
    else:
        introduced += 1
        caught = tests_fail and audit_fail
        detected += caught
        if not caught:
            survived.append(name)
        status = "DETECTED" if caught else "SURVIVED"
    rows.append(f"{name}: tests_fail={tests_fail} audit_fail={audit_fail} {status} {' '.join(counters)}")

ok = baseline_ok and not survived
report = "\n".join(rows) + (
    f"\nmutations introduced: {introduced}\nmutations detected: {detected}\n"
    f"mutations survived: {len(survived)} {survived}\nMUTATION_CHECK: {'PASS' if ok else 'FAIL'}\n")
print(report, end="")
if WRITE:
    (HERE / "mutation_results.txt").write_text(report, encoding="utf-8")
sys.exit(0 if ok else 1)
