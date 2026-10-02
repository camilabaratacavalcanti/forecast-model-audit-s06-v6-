"""
Stage 4C.2 — prova de que cada harness R, com o novo parâmetro `--baseline-dir`, reproduz B0 bit a bit.

    python audit/stage4c/b0_reproduction.py [--write]

Regenera TODOS os conjuntos R (mesma sequência do `rebaseline.py`) num diretório TEMPORÁRIO e compara
cada arquivo com o arquivo histórico registrado em B0:
    * BIT_A_BIT       sha256 idêntico;
    * EQUIVALENTE     só diferem campos de TEMPO DE EXECUÇÃO medido (DR-4C-7): chaves com "seconds" ou
                      "performance" no JSON e a coluna `seconds` dos CSV de desempenho; todo o resto do
                      conteúdo canônico é idêntico;
    * DIVERGENTE      qualquer outra diferença (falha).
Nada é escrito no repositório, exceto `audit/stage4c/evidence/b0_reproduction.json` com `--write`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "audit" / "baselines"))

import baseline_paths as bp  # noqa: E402
import baseline_registry as reg  # noqa: E402
import rebaseline  # noqa: E402

TIMING = ("seconds", "performance")


def strip_timing(obj):
    if isinstance(obj, dict):
        return {k: strip_timing(v) for k, v in obj.items() if not any(t in k for t in TIMING)}
    if isinstance(obj, list):
        return [strip_timing(v) for v in obj]
    return obj


def canonical_without_timing(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.dumps(strip_timing(json.loads(text)), sort_keys=True)
    if path.suffix == ".csv":
        rows = list(csv.DictReader(io.StringIO(text)))
        return json.dumps([{k: v for k, v in r.items() if k != "seconds"} for r in rows], sort_keys=True)
    return text


def main() -> int:
    b0 = reg.entry(reg.load(), "B0")
    report = {"label": "Stage 4C.2 — reprodução B0", "steps": [], "files": [], "problems": []}
    with tempfile.TemporaryDirectory(prefix="stage4c_b0_") as tmp:
        target = Path(tmp) / "B0-repro"
        for label, args, isolated in rebaseline.GENERATION:
            step = rebaseline.run_step(label, args, isolated, target)
            report["steps"].append({k: step[k] for k in ("label", "command", "returncode")})
            if step["returncode"] != 0:
                report["problems"].append(f"HARNESS_FAILED {label}: {step['problems'][:3]} {step['stderr_tail'][-300:]}")
        for set_name in bp.R_SETS:
            for logical, meta in b0["conjuntos"][set_name]["arquivos"].items():
                new = target / set_name / logical
                old = REPO / meta["caminho"]
                row = {"set": set_name, "file": logical, "historical": meta["caminho"],
                       "sha256_b0": meta["sha256"],
                       "sha256_regenerated": hashlib.sha256(new.read_bytes()).hexdigest() if new.exists() else None}
                if row["sha256_regenerated"] == meta["sha256"]:
                    row["result"] = "BIT_A_BIT"
                elif new.exists() and canonical_without_timing(new) == canonical_without_timing(old):
                    row["result"] = "EQUIVALENTE (só tempo de execução)"
                else:
                    row["result"] = "DIVERGENTE"
                    report["problems"].append(f"DIVERGENTE {set_name}/{logical}")
                report["files"].append(row)
    report["summary"] = {r: sum(1 for f in report["files"] if f["result"].startswith(r))
                         for r in ("BIT_A_BIT", "EQUIVALENTE", "DIVERGENTE")}
    report["result"] = "PASS" if not report["problems"] else "FAIL"
    if "--write" in sys.argv[1:]:
        out = HERE / "evidence"
        out.mkdir(exist_ok=True)
        (out / "b0_reproduction.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("summary", "problems", "result")}, indent=1, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
