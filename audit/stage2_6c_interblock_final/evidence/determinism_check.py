"""
Etapa 2.6C — verificação de determinismo do builder e do livro de IDs.

    python audit/stage2_6c_interblock_final/evidence/determinism_check.py

1. `python -m tools.workbook_seed` duas vezes consecutivas no próprio
   repositório: SHA-256 de todo arquivo de data/seed e data/id_ledger
   antes, depois da 1a e depois da 2a execução (devem ser idênticos).
2. Builds isolados em diretórios temporários, em subprocessos, com
   PYTHONHASHSEED diferentes e ordem de carga direta e invertida.

Grava evidence/determinism_check.txt.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def digests(*roots):
    out = {}
    for root in roots:
        for p in sorted(root.rglob("*.json")):
            out[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def aggregate(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


lines = ["# Etapa 2.6C — determinismo", ""]
roots = (REPO / "data" / "seed", REPO / "data" / "id_ledger")
before = digests(*roots)
runs = []
for i in (1, 2):
    completed = subprocess.run(
        [sys.executable, "-m", "tools.workbook_seed"], cwd=REPO, capture_output=True, text=True,
    )
    runs.append((completed.returncode, digests(*roots), completed.stdout.strip().splitlines()[-1]))

lines.append("## 1. python -m tools.workbook_seed, duas execuções consecutivas no repositório")
lines.append(f"arquivos verificados: {len(before)} (data/seed + data/id_ledger)")
lines.append(f"agregado antes        : {aggregate(before)}")
for i, (code, d, last) in enumerate(runs, start=1):
    lines.append(f"agregado execução {i}   : {aggregate(d)} (exit={code}; {last})")
identical_repo = before == runs[0][1] == runs[1][1]
lines.append(f"byte a byte idênticos: {identical_repo}")
lines.append("")

snippet = """
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {repo!r})
from tools.workbook_seed.blocks import BLOCKS, build_all, write_id_ledger, write_interblock_seed, write_seeds
order = list(BLOCKS)
if {reverse!r}:
    order.reverse()
out = Path({out!r})
result = build_all(order=order)
for block, built in result.blocks.items():
    write_seeds(built, out / "seed" / block)
    write_id_ledger(built, out / "id_ledger")
write_interblock_seed(result, out / "seed")
print(json.dumps({{str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(out.rglob("*.json"))}}, sort_keys=True))
"""
lines.append("## 2. builds isolados (subprocesso, diretório temporário)")
results = {}
with tempfile.TemporaryDirectory() as tmp:
    for label, seed, reverse in (
        ("ordem direta, PYTHONHASHSEED=0", 0, False),
        ("ordem direta, PYTHONHASHSEED=0 (repetição)", 0, False),
        ("ordem direta, PYTHONHASHSEED=987654321", 987654321, False),
        ("ordem invertida, PYTHONHASHSEED=12345", 12345, True),
    ):
        out = Path(tmp) / str(len(results))
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        text = subprocess.check_output(
            [sys.executable, "-c", snippet.format(repo=str(REPO), out=str(out), reverse=reverse)],
            cwd=REPO, env=env,
        )
        results[label] = json.loads(text)
        lines.append(f"{label:45s} arquivos={len(results[label])} agregado={aggregate(results[label])}")
committed = {
    name: before[("data/seed/" if name.startswith("seed/") else "data/id_ledger/") + name.split("/", 1)[1]]
    for name in next(iter(results.values()))
}
identical_isolated = all(r == committed for r in results.values())
lines.append(f"agregado dos arquivos versionados equivalentes: {aggregate(committed)}")
lines.append(f"todos idênticos entre si e aos versionados: {identical_isolated}")
lines.append("")
lines.append("## 3. SHA-256 por arquivo (versionados)")
lines += [f"{v}  {k}" for k, v in sorted(before.items())]
lines.append("")
lines.append(f"RESULTADO: {'DETERMINISTIC' if identical_repo and identical_isolated else 'NON_DETERMINISTIC'}")
(HERE / "determinism_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[:16]))
sys.exit(0 if identical_repo and identical_isolated else 1)
