"""
Etapa 3.1 — auditoria independente do runtime interbloco.

    python audit/stage3_1_interblock_runtime/evidence/analysis_stage3_1.py [--no-write]

Não importa nada de app/ nem de tools/. Lê apenas artefatos:

    data/seed/interblock_links.json         (contrato canônico)
    data/seed/<bloco>/variables.json        (definições locais)
    data/seed/<bloco>/manifest.json         (source_block por entidade)

1. Reconstrói de forma independente TODOS os vínculos a partir dos
   manifestos (entidades com `source_block`) e das definições do bloco
   produtor (mesmo nome, frequência, tipo de escopo, instâncias
   cobertas) e compara com a seção `links`/`pending` do artefato.
2. Observa o runtime como caixa-preta (`runtime_probe.py` em
   subprocesso): grava um número ÚNICO em cada chave
   (variável, instância, período) de todas as variáveis não
   consumidoras dos cinco blocos — incluindo iscas em outros períodos
   (mensal/anual/sem período) — executa a transferência e decodifica,
   pelo número recebido, qual chave o runtime leu para cada consumidor.
   O esperado é exatamente: produtor raiz da cadeia, mesma instância,
   mesmo período. Qualquer outra chave (outro bloco, outra instância,
   outra frequência, isca, valor local) é divergência.
3. Sonda os 16 vínculos pendentes: todos devem falhar com
   INTERBLOCK_SOURCE_NOT_LOADED.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
SEED = REPO / "data" / "seed"
WRITE = "--no-write" not in sys.argv[1:]
LINES = [f"L{i}" for i in range(1, 8)]
PERIODS = {"diário": "2026-09-14", "mensal": "2026-09", "anual": "2026"}
DECOYS = [None, "2026-09-14", "2026-09", "2026", "2026-09-13", "2025"]
failures: list[str] = []


def check(condition, message):
    if not condition:
        failures.append(message)


def instances(scope_type, scope_value):
    if scope_type == "linha" and "_" in str(scope_value):
        a, b = scope_value.split("_")
        return [(scope_type, l) for l in LINES[LINES.index(a): LINES.index(b) + 1]]
    return [(scope_type, scope_value)]


payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
blocks = sorted(payload["workbooks"])
variables = {b: json.loads((SEED / b / "variables.json").read_text(encoding="utf-8")) for b in blocks}
manifests = {b: json.loads((SEED / b / "manifest.json").read_text(encoding="utf-8")) for b in blocks}
by_id = {v["variable_id"]: (b, v) for b in blocks for v in variables[b]}


# ------------------------------------------------------------------
# 1. reconstrução independente dos vínculos
# ------------------------------------------------------------------
expected_links, expected_pending = {}, {}
for block in blocks:
    for entity in manifests[block]["entities"]:
        source = entity.get("source_block")
        if source is None:
            continue
        consumer = entity["entity_id"]
        consumer_instances = instances(entity["scope_type"], entity["scope_value"])
        if source not in blocks:
            expected_pending[consumer] = (block, source)
            continue
        candidates = [
            v for v in variables[source]
            if (v["variable_name"], v["frequency"], v["scope_type"])
            == (entity["name"], entity["frequency"], entity["scope_type"])
            and set(consumer_instances) <= set(instances(v["scope_type"], v["scope_value"]))
        ]
        check(len(candidates) == 1, f"{block}.{entity['name']}: {len(candidates)} produtores independentes")
        if candidates:
            p = candidates[0]
            c = by_id[consumer][1]
            check(c["unit"] == p["unit"], f"{consumer}: unidade {c['unit']} x {p['unit']}")
            expected_links[consumer] = {
                "consumer_block": block, "consumer_name": entity["name"],
                "source_block": source, "source_definition": p["variable_id"],
                "frequency": entity["frequency"], "instances": consumer_instances,
                "unit": p["unit"],
            }

seed_links = {r["consumer_definition"]: r for r in payload["links"]}
seed_pending = {r["consumer_definition"]: r for r in payload["pending"]}
check(set(seed_links) == set(expected_links), "consumidores de links divergentes")
check(set(seed_pending) == set(expected_pending), "consumidores de pending divergentes")
for consumer, e in expected_links.items():
    r = seed_links.get(consumer)
    if r is None:
        continue
    check((r["source_block"], r["source_definition"]) == (e["source_block"], e["source_definition"]),
          f"{consumer}: produtor {r['source_block']}.{r['source_definition']} != esperado")
    check([(i["scope_type"], i["scope_value"]) for i in r["instances"]] == e["instances"],
          f"{consumer}: instâncias divergentes")
    check(r["consumer_frequency"] == r["source_frequency"] == e["frequency"], f"{consumer}: frequência")
for consumer, (block, source) in expected_pending.items():
    r = seed_pending.get(consumer)
    check(r is not None and r["source_block"] == source and r["source_definition"] is None,
          f"{consumer}: pendência divergente")
check(payload["rejected"] == [], "artefato com vínculos rejeitados")


def root_of(consumer):
    link = expected_links[consumer]
    chain = [consumer]
    while link["source_definition"] in expected_links:
        chain.append(link["source_definition"])
        link = expected_links[link["source_definition"]]
    chain.append(link["source_definition"])
    return link["source_definition"], chain


# ------------------------------------------------------------------
# 2. runtime como caixa-preta
# ------------------------------------------------------------------
consumers = set(expected_links) | set(expected_pending)
values, key_of = [], {}
number = 0
for block in blocks:
    for v in variables[block]:
        if v["variable_id"] in consumers or v["value_type"] != "numerico":
            continue
        for scope_type, scope_value in instances(v["scope_type"], v["scope_value"]):
            for period in DECOYS:
                number += 1
                value = float(number)
                values.append([v["variable_id"], scope_type, scope_value, period, value])
                key_of[value] = (v["variable_id"], scope_type, scope_value, period)

pending_probes = []
for consumer in sorted(expected_pending):
    d = by_id[consumer][1]
    scope_type, scope_value = instances(d["scope_type"], d["scope_value"])[0]
    pending_probes.append([consumer, scope_type, scope_value, PERIODS[d["frequency"]]])

probe = subprocess.run(
    [sys.executable, str(HERE / "runtime_probe.py")],
    input=json.dumps({"values": values, "periods": PERIODS, "pending_probes": pending_probes}),
    capture_output=True, text=True, cwd=REPO,
)
check(probe.returncode == 0, f"sonda falhou: {probe.stderr[-2000:]}")
observed = json.loads(probe.stdout) if probe.returncode == 0 else {"received": [], "pending": []}

rows = []
received = {}
for consumer, scope_type, scope_value, period, value in observed["received"]:
    received[(consumer, scope_type, scope_value)] = (period, value)

for consumer in sorted(expected_links):
    e = expected_links[consumer]
    root, chain = root_of(consumer)
    period = PERIODS[e["frequency"]]
    for scope_type, scope_value in e["instances"]:
        got = received.get((consumer, scope_type, scope_value))
        consumed = key_of.get(got[1]) if got else None
        expected_key = (root, scope_type, scope_value, period)
        ok = got is not None and got[0] == period and consumed == expected_key
        check(ok, f"{consumer} {scope_type}/{scope_value}: consumiu {consumed}, esperado {expected_key}")
        consumer_block, c = by_id[consumer]
        root_block, rdef = by_id[root]
        rows.append({
            "consumer_block": consumer_block,
            "consumer_definition": consumer,
            "consumer_name": c["variable_name"],
            "instance": f"{scope_type}/{scope_value}",
            "frequency": e["frequency"],
            "period_id": period,
            "declared_source": f"{e['source_block']}.{e['source_definition']}",
            "chain": " <- ".join(f"{by_id[x][0]}.{x}" for x in chain),
            "expected_root_producer": f"{root_block}.{root}",
            "expected_key": f"{root}|{scope_type}/{scope_value}|{period}",
            "consumed_key": "|".join(
                [consumed[0], f"{consumed[1]}/{consumed[2]}", str(consumed[3])]
            ) if consumed else "",
            "received_value": got[1] if got else "",
            "consumer_unit": c["unit"],
            "producer_unit": rdef["unit"],
            "result": "MATCH" if ok else "DIVERGENCE",
        })

check(len(observed["received"]) == sum(len(e["instances"]) for e in expected_links.values()),
      "número de transferências divergente")

pending_rows = []
for consumer, code in observed["pending"]:
    check(code == "INTERBLOCK_SOURCE_NOT_LOADED", f"{consumer}: pendência sem erro explícito ({code})")
    block, source = expected_pending[consumer]
    pending_rows.append({"consumer_block": block, "consumer_definition": consumer,
                         "consumer_name": by_id[consumer][1]["variable_name"],
                         "source_block": source, "runtime_result": code})

if WRITE:
    for path, data in ((HERE / "runtime_link_evidence.csv", rows),
                       (HERE / "runtime_pending_evidence.csv", pending_rows)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)

summary = {
    "links_reconstructed": len(expected_links),
    "pending_reconstructed": len(expected_pending),
    "instance_transfers_checked": len(rows),
    "matches": sum(r["result"] == "MATCH" for r in rows),
    "decoy_keys_written": len(values),
    "pending_probed": dict(Counter(code for _c, code in observed["pending"])),
    "chains": sorted({r["chain"] for r in rows if r["chain"].count("<-") > 1}),
    "divergences": failures,
}
if WRITE:
    (HERE / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(1 if failures else 0)
