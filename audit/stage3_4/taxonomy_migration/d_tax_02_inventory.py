"""
D-TAX-02 — inventário classificado das ocorrências dos nomes dos blocos de custo.

    python audit/stage3_4/taxonomy_migration/d_tax_02_inventory.py [--no-write]

Toda ocorrência (arquivos versionados + novos ainda não versionados) dos três
nomes históricos e dos três canônicos recebe uma classe:
operational | normative | historical | test | evidence.

Falha se:
  * alguma ocorrência fica sem classe;
  * um nome histórico aparece fora dos locais permitidos (crosswalk/decisão D-TAX-02,
    evidência e documentação históricas, testes específicos de crosswalk) — em
    particular em app/, tools/ ou data/.
Grava `evidence/d_tax_02_occurrences.csv`.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HISTORICAL = ("custo_budget", "custo_forecast_bdgt", "custo_forecast_real")
CANONICAL = ("budget_cost", "budget_forecast_cost", "actual_forecast_cost")

# (prefixo do caminho, classe) — o primeiro que casar vence.
RULES = (
    ("app/", "operational"), ("tools/", "operational"), ("data/", "operational"),
    ("audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json", "normative"),
    ("audit/stage3_4/taxonomy_migration/contract_decisions.csv", "normative"),
    ("audit/stage3_4/taxonomy_migration/taxonomy_guard.py", "normative"),
    ("audit/stage3_4/taxonomy_migration/d_tax_02_inventory.py", "normative"),
    ("audit/stage3_4/STAGE_3_4_TAXONOMY_D_TAX_02.md", "normative"),
    ("audit/stage3_4/TECH_DEBT_TAXONOMY_DUPLICATION.md", "normative"),
    ("audit/stage3_4/PLATFORM_PENDING_ITEMS.md", "normative"),
    ("audit/stage3_4/taxonomy_migration/evidence/", "evidence"),
    ("audit/stage2_6c_interblock_final/evidence/analysis_stage2_6c.py", "LIVE_ORACLE"),
    ("audit/stage2_6", "historical"),
    ("audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md", "historical"),
    ("audit/stage3_4/STAGE_3_FINAL_CLOSURE.md", "historical"),
    ("tests/", "test"),
)
# Nome histórico só é permitido aqui (TAX-02-06).
HISTORICAL_ALLOWED = ("normative", "historical", "evidence", "LIVE_ORACLE")
HISTORICAL_ALLOWED_TESTS = ("tests/test_taxonomy_d_tax_02.py", "tests/test_stage2_6b_interblock_closure.py")
OUTPUT = "audit/stage3_4/taxonomy_migration/evidence/d_tax_02_occurrences.csv"   # a própria saída não é ocorrência


def occurrences() -> list[tuple[str, int, str]]:
    names = HISTORICAL + CANONICAL
    pattern = "|".join(names)
    out = subprocess.run(["git", "grep", "-n", "-I", "--untracked", "-E", pattern], cwd=REPO,
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        path, number, text = line.split(":", 2)
        if "__pycache__" in path or path == OUTPUT:
            continue
        for name in names:
            if name in text:
                rows.append((path, int(number), name))
    return rows


def classify(path: str, name: str) -> str | None:
    for prefix, cls in RULES:
        if path.startswith(prefix):
            if cls == "LIVE_ORACLE":                 # análise 2.6C executada ao vivo pelo test_17
                return "normative" if name in CANONICAL else "historical"
            return cls
    return None


def inventory() -> tuple[list[dict], dict]:
    """Ocorrências classificadas e o resumo (problems vazio == PASS)."""
    rows, problems = [], []
    for path, number, name in occurrences():
        cls = classify(path, name)
        kind = "historical_name" if name in HISTORICAL else "canonical_name"
        rows.append({"file": path, "line": number, "name": name, "name_kind": kind, "class": cls or "UNCLASSIFIED"})
        if cls is None:
            problems.append(f"UNCLASSIFIED {path}:{number} {name}")
        elif kind == "historical_name":
            allowed = cls in HISTORICAL_ALLOWED or (cls == "test" and path in HISTORICAL_ALLOWED_TESTS)
            if not allowed:
                problems.append(f"HISTORICAL_NAME_NOT_ALLOWED {path}:{number} {name} ({cls})")
    summary = {"occurrences": len(rows), "by_class": dict(sorted(Counter(r["class"] for r in rows).items())),
               "by_name": dict(sorted(Counter(r["name"] for r in rows).items())),
               "historical_in_operational": sum(1 for r in rows if r["name_kind"] == "historical_name"
                                                and r["class"] == "operational"),
               "problems": problems, "result": "PASS" if not problems else "FAIL"}
    return rows, summary


def main() -> int:
    rows, summary = inventory()
    problems = summary["problems"]
    if "--no-write" not in sys.argv[1:]:
        with (REPO / OUTPUT).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: (r["file"], r["line"], r["name"])))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
