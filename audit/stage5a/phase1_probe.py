"""
Stage 5A.1 — sonda do contrato (sem mudar produção; não importa app/).

    python audit/stage5a/phase1_probe.py --energy <energy_v9.xlsx> --maxht <MaxHT_v13.xlsx> [--write]

Num CLONE TEMPORÁRIO do HEAD (o repositório não é tocado) monta os seeds com os dois workbooks novos e o
código ATUAL (numeração posicional de EQ) e compara com os seeds B0 (HEAD):
  1. F5A-01: EQ cujo (alvo, escopo) mudou — sem livro de equações;
  2. simulação INDEPENDENTE do livro de equações (D-5A-4): identidade = identidade da variável alvo
     (kind, name, frequency, scope_type, scope_value) + scope_value da instância; conhecidos mantêm o ID,
     novos recebem o próximo acima do maior emitido, ausentes são aposentados;
  3. inventário das regras SUM com integration_factor != 1 (B0 e clone);
  4. expectativas do B1 (contagens, IDs novos/aposentados, vínculos).
Saída: JSON em stdout; com --write grava `audit/stage5a/evidence/phase1_probe.json`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "audit" / "stage4c" / "rehearsal"))

import rehearse_5a as tree  # noqa: E402  (build_tree, add_units, update_block_spec, sha256)

BLOCKS = ("yield", "production", "energy", "max_ht", "area_41")
ID_BASE = {"area_41": 16000, "energy": 18000, "max_ht": 13000, "production": 12000, "yield": 11000}


def load(root: Path, block: str, name: str):
    return json.loads((root / "data" / "seed" / block / f"{name}.json").read_text(encoding="utf-8"))


def identities(root: Path, block: str) -> dict:
    """entity_id -> identidade (kind, name, frequency, scope_type, scope_value) pelo manifesto."""
    return {e["entity_id"]: (e["kind"], e["name"], e["frequency"], e["scope_type"], e["scope_value"])
            for e in load(root, block, "manifest")["entities"]}


def eq_key(eq: dict, ids: dict) -> tuple:
    return (*ids[eq["target_variable_id"]], eq["scope_value"])


def simulate_ledger(old: list[dict], old_ids: dict, new: list[dict], new_ids: dict, base: int) -> dict:
    book = {eq_key(e, old_ids): e["equation_id"] for e in old}
    highest = max([int(e["equation_id"][2:]) for e in old] + [base])
    assigned, created = {}, []
    for e in new:                                    # ordem do workbook (= ordem do seed)
        key = eq_key(e, new_ids)
        if key in book:
            assigned[key] = book[key]
        else:
            highest += 1
            assigned[key] = f"EQ{highest}"
            created.append((f"EQ{highest}", key))
    retired = sorted((eid, key) for key, eid in book.items() if key not in assigned)
    kept_same_target = sum(1 for key, eid in assigned.items() if book.get(key) == eid)
    return {"kept": kept_same_target, "new": [[i, list(k)] for i, k in created],
            "retired": [[i, list(k)] for i, k in retired],
            "renumbered": [],                        # por construção: chave conhecida => mesmo ID
            "expression_changed_same_id": sorted(
                book[eq_key(e, new_ids)] for e in new if eq_key(e, new_ids) in book
                and next(o for o in old if o["equation_id"] == book[eq_key(e, new_ids)])["expression"] != e["expression"])}


def compare(head: Path, clone: Path) -> dict:
    out = {"blocks": {}}
    for block in BLOCKS:
        old_eq, new_eq = load(head, block, "equations"), load(clone, block, "equations")
        old_ids, new_ids = identities(head, block), identities(clone, block)
        old_map = {e["equation_id"]: eq_key(e, old_ids) for e in old_eq}
        new_map = {e["equation_id"]: eq_key(e, new_ids) for e in new_eq}
        moved = sorted(i for i in set(old_map) & set(new_map) if old_map[i] != new_map[i])
        old_vars = {e["variable_id"] for e in load(head, block, "variables")}
        new_vars = {e["variable_id"] for e in load(clone, block, "variables")}
        ledger = json.loads((clone / "data" / "id_ledger" / f"{block}.json").read_text(encoding="utf-8"))
        old_rules = {r["aggregation_rule_id"]: r for r in load(head, block, "aggregation_rules")}
        new_rules = {r["aggregation_rule_id"]: r for r in load(clone, block, "aggregation_rules")}
        out["blocks"][block] = {
            "variables": [len(old_vars), len(new_vars)], "variables_new": sorted(new_vars - old_vars),
            "variables_removed": sorted(old_vars - new_vars),
            "retired_in_ledger": sorted(r["entity_id"] for r in ledger["retired"]),
            "parameters": [len(load(head, block, "parameters")), len(load(clone, block, "parameters"))],
            "equations": [len(old_eq), len(new_eq)],
            "aggregation_rules": [len(old_rules), len(new_rules)],
            "rules_new": sorted(set(new_rules) - set(old_rules)), "rules_removed": sorted(set(old_rules) - set(new_rules)),
            "F5A_01_positional_eq_with_other_target": moved,
            "F5A_01_count": len(moved),
            "ledger_simulation": simulate_ledger(old_eq, old_ids, new_eq, new_ids, ID_BASE[block]),
            "sum_factor_not_1_B0": sorted(i for i, r in old_rules.items()
                                          if r["aggregation_type"] == "SUM" and r.get("integration_factor") != 1),
            "sum_factor_not_1_new": sorted(i for i, r in new_rules.items()
                                           if r["aggregation_type"] == "SUM" and r.get("integration_factor") != 1),
            "sum_rules_B0": sum(1 for r in old_rules.values() if r["aggregation_type"] == "SUM"),
        }
    for label, root in (("B0", head), ("new", clone)):
        links = json.loads((root / "data/seed/interblock_links.json").read_text(encoding="utf-8"))
        out[f"links_{label}"] = {"valid": len(links["links"]), "pending": len(links["pending"]),
                                 "rejected": len(links["rejected"]),
                                 "pending_set": sorted(f"{p['consumer_block']}.{p['consumer_definition']}<-{p['source_block']}"
                                                       for p in links["pending"])}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--energy", required=True)
    parser.add_argument("--maxht", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="stage5a_probe_") as tmp:
        root = Path(tmp) / "tree"
        tree.build_tree(root)
        wb = root / "data" / "workbooks"
        for block, src, version, name in (
                ("energy", args.energy, "v9", "descritivo_das_variáveis_energy_v9.xlsx"),
                ("max_ht", args.maxht, "v13", "descritivo_das_variáveis_MaxHT_v13.xlsx")):
            shutil.copy2(src, wb / name)
            tree.update_block_spec(root, block, version, name, tree.sha256(wb / name))
        tree.add_units(root)
        done = subprocess.run([sys.executable, "-m", "tools.workbook_seed"], cwd=root, capture_output=True,
                              text=True, env=tree.clean_env())
        out = {"workbook_seed_rc": done.returncode, "workbook_seed": done.stdout.strip().splitlines()[-6:],
               **compare(REPO, root)}
    out["F5A_01_total"] = {b: v["F5A_01_count"] for b, v in out["blocks"].items()}
    if args.write:
        (HERE / "evidence").mkdir(exist_ok=True)
        (HERE / "evidence" / "phase1_probe.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                                            encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
