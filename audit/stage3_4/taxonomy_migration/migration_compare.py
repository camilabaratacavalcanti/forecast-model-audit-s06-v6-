"""
D-TAX-01 — reconciliação antes/depois (somente leitura).

    python audit/stage3_4/taxonomy_migration/migration_compare.py [--no-write]

Gera o snapshot atual (snapshot.py) e compara com `evidence/before_snapshot.json`
(tirado em 547b920, antes da migração). Aceita SOMENTE estas diferenças:
  * taxonomia: D26-01 (28) -> D-TAX-01 (29, ordem canônica); rótulo da decisão;
  * faixas: o nome da faixa 30000–30999 (monthly_ppt_assumptions -> thickener_flocculant).
Toda outra seção (arquivos de seed, IDs, fórmulas, vínculos, pendências,
cardinalidades, execução de 32 datas, hash do grafo) tem de ser idêntica.
Grava `evidence/after_snapshot.json` e `evidence/migration_reconciliation.json`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import taxonomy_guard as guard  # noqa: E402

EVIDENCE = HERE / "evidence"
OLD, NEW = guard.OLD_NAME, guard.NEW_NAME
INVARIANT_SECTIONS = ("files_sha256", "ids", "formulas_sha256", "interblock", "cardinalities", "execution",
                      "fixture_graph_hash", "label")


def main() -> int:
    write = "--no-write" not in sys.argv[1:]
    after_path = EVIDENCE / "after_snapshot.json" if write else EVIDENCE / ".after_snapshot.tmp.json"
    subprocess.run([sys.executable, str(HERE / "snapshot.py"), str(after_path)], check=True, capture_output=True)
    before = json.loads((EVIDENCE / "before_snapshot.json").read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    if not write:
        after_path.unlink()
    problems = [f"SEÇÃO ALTERADA: {section}" for section in INVARIANT_SECTIONS if before[section] != after[section]]
    expected_ranges = {kind: [[NEW if n == OLD else n, lo, hi] for n, lo, hi in rows]
                       for kind, rows in before["ranges"].items()}
    if after["ranges"] != expected_ranges:
        problems.append("FAIXAS: diferença além do rename da faixa 30000-30999")
    tax = after["taxonomy"]
    if tuple(tax["block_taxonomy"]) != guard.CANONICAL_NAMES or tuple(tax["seed_official_blocks"]) != guard.CANONICAL_NAMES:
        problems.append("TAXONOMIA: != registro canônico D-TAX-01")
    if tax["seed_decision"] != guard.DECISION or tax["seed_loaded_blocks"] != before["taxonomy"]["seed_loaded_blocks"]:
        problems.append("TAXONOMIA: rótulo ou blocos carregados divergentes")
    if tuple(before["taxonomy"]["block_taxonomy"]) != guard.D26_01:
        problems.append("BASE: taxonomia anterior não é D26-01")
    for kind in ("variable", "parameter", "equation"):
        if [row[0] for row in after["ranges"][kind]] != tax["block_taxonomy"]:
            problems.append(f"FONTES DIVERGENTES: {kind} ranges != BLOCK_TAXONOMY")
    report = {
        "decision": guard.DECISION,
        "before": {"taxonomy_count": len(before["taxonomy"]["block_taxonomy"]),
                   "seed_taxonomy_count": len(before["taxonomy"]["seed_official_blocks"]),
                   "range_counts": {k: len(v) for k, v in before["ranges"].items()},
                   "seed_decision": before["taxonomy"]["seed_decision"]},
        "after": {"taxonomy_count": len(tax["block_taxonomy"]), "seed_taxonomy_count": len(tax["seed_official_blocks"]),
                  "range_counts": {k: len(v) for k, v in after["ranges"].items()}, "seed_decision": tax["seed_decision"]},
        "renamed_range": {"old": OLD, "new": NEW, "range": [30000, 30999]},
        "invariant_sections_identical": {section: before[section] == after[section] for section in INVARIANT_SECTIONS},
        "cardinalities": after["cardinalities"], "execution": after["execution"],
        "fixture_graph_hash": after["fixture_graph_hash"],
        "pending_links": len(after["interblock"]["pending"]), "links": len(after["interblock"]["links"]),
        "problems": problems, "result": "PASS" if not problems else "FAIL",
    }
    if write:
        (EVIDENCE / "migration_reconciliation.json").write_text(
            json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
