"""
D-TAX-01 — snapshot semântico do repositório (antes/depois da migração taxonômica).

    python audit/stage3_4/taxonomy_migration/snapshot.py <saída.json>

Captura tudo o que a migração NÃO pode mudar, e o que ela muda (os nomes):
  * taxonomia de blocos (tools) e a cópia no seed interbloco;
  * as três faixas de ID (VAR/PARAM/EQ) em ordem;
  * sha256 de todo arquivo de `data/seed/<bloco>/` e `data/id_ledger/`;
  * IDs de variáveis, parâmetros, equações e regras por bloco; expressões das equações;
  * vínculos interbloco (links, pending, rejected) sem a seção `taxonomy`;
  * cardinalidades do planner e do plano integrado; hash do grafo REAL_DERIVED;
  * execução real de 32 datas: identidades temporais e o fingerprint de resultados
    (mesmo algoritmo do RUN_A da 3.4C).
Somente leitura. Todo resultado de execução é REAL_DERIVED_TEST_RESULT.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO), str(REPO / "audit" / "stage3_4" / "integrated")]

import checks  # noqa: E402
import fixture  # noqa: E402
import run_integrated as integ  # noqa: E402

from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.interblock_orchestrator import InterblockExecutionOrchestrator  # noqa: E402
from app.validation.equation_seed_validator import EQUATION_ID_RANGES  # noqa: E402
from app.validation.parameter_seed_validator import PARAMETER_ID_RANGES  # noqa: E402
from app.validation.variable_seed_validator import VARIABLE_ID_RANGES  # noqa: E402
from tools.workbook_seed.taxonomy import BLOCK_TAXONOMY  # noqa: E402

SEED = REPO / "data" / "seed"
BLOCKS4 = ("yield", "production", "energy", "max_ht")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    snap: dict = {"label": fixture.LABEL}
    links_payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
    snap["taxonomy"] = {
        "block_taxonomy": list(BLOCK_TAXONOMY),
        "seed_official_blocks": links_payload["taxonomy"]["official_blocks"],
        "seed_loaded_blocks": links_payload["taxonomy"]["loaded_blocks"],
        "seed_decision": links_payload["taxonomy"].get("decision"),
    }
    snap["ranges"] = {name: [[k, lo, hi] for k, (lo, hi) in registry.items()]
                      for name, registry in (("variable", VARIABLE_ID_RANGES), ("parameter", PARAMETER_ID_RANGES),
                                             ("equation", EQUATION_ID_RANGES))}
    snap["files_sha256"] = {str(p.relative_to(REPO)): sha(p.read_bytes())
                            for root in (SEED, REPO / "data" / "id_ledger", REPO / "data" / "workbooks")
                            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "interblock_links.json"}
    ids, formulas = {}, {}
    for block_dir in sorted(p for p in SEED.iterdir() if p.is_dir()):
        block = block_dir.name
        load = lambda name: json.loads((block_dir / f"{name}.json").read_text(encoding="utf-8"))  # noqa: E731
        ids[block] = {"variables": [r["variable_id"] for r in load("variables")],
                      "parameters": [r["parameter_id"] for r in load("parameters")],
                      "equations": [r["equation_id"] for r in load("equations")],
                      "aggregation_rules": [r["aggregation_rule_id"] for r in load("aggregation_rules")]}
        formulas[block] = {r["equation_id"]: r.get("expression") for r in load("equations")}
    snap["ids"], snap["formulas_sha256"] = ids, sha(json.dumps(formulas, sort_keys=True).encode())
    semantic = {k: v for k, v in links_payload.items() if k != "taxonomy"}
    snap["interblock"] = {
        "semantic_sha256": sha(json.dumps(semantic, sort_keys=True, ensure_ascii=False).encode()),
        "links": sorted([lk["consumer_block"], lk["consumer_definition"], lk["source_block"], lk["source_definition"],
                         lk.get("validation_status"), lk.get("resolution_status")] for lk in links_payload["links"]),
        "pending": sorted([p["consumer_block"], p["consumer_definition"], p["source_block"], p["resolution_status"],
                           p["validation_status"]] for p in links_payload["pending"]),
        "rejected": len(links_payload.get("rejected", [])),
    }
    official = InterblockExecutionOrchestrator.from_seed_root(SEED)
    o = fixture.build("A")
    plan = integ.integrated_plan(o)
    engine = ForecastEngine()
    eq4 = [d for d in o.catalog.equation_definitions.all() if o.catalog.block_of.get(d.equation_definition_id) in BLOCKS4]
    agg4 = [i for i in o.catalog.aggregation_rule_instances.all()
            if o.catalog.block_of.get(i.rule.aggregation_rule_id) in BLOCKS4]
    snap["cardinalities"] = {
        "official_targets": len(official.targets_of_blocks(BLOCKS4 + ("area_41",))),
        "integrated_targets": len(plan.targets), "planner_nodes": len(plan.steps),
        "nodes_by_kind": dict(sorted(Counter(s.kind for s in plan.steps).items())),
        "equation_definitions": len(eq4), "equation_instances": sum(len(engine.materialize_equation(d)) for d in eq4),
        "aggregation_rules": len({i.rule.aggregation_rule_id for i in agg4}), "aggregation_instances": len(agg4),
        "pending_official": len(official.catalog.links.pending()), "pending_fixture": len(o.catalog.links.pending()),
        "plan_order_sha256": sha(json.dumps([s.key for s in plan.steps]).encode()),
    }
    snap["fixture_graph_hash"] = fixture.graph_hash(o)
    context = integ.fresh_context(o)
    snapshot_jan = None
    for day in integ.DAYS:
        if day == integ.FEB1:
            snapshot_jan = {k: v for k, v in integ.store_of(context).items() if k[3] == "2026-01"}
        integ.execute_day(o, plan, context, day)
    counts, problems = checks.check_temporal(integ.store_of(context), snapshot_jan, [d.isoformat() for d in integ.DAYS],
                                             integ.derived_variables(plan))
    fp = integ.fingerprint("A")
    snap["execution"] = {"dates": len(integ.DAYS), "temporal": counts, "temporal_problems": problems,
                         "results_sha256": fp["results_sha256"], "store_sha256": fp["store_sha256"]}
    Path(sys.argv[1]).write_text(json.dumps(snap, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: snap[k] for k in ("cardinalities", "execution", "fixture_graph_hash")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
