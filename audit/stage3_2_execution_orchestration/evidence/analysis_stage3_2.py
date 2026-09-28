"""
Etapa 3.2 — auditoria independente da execução coordenada interbloco.

    python audit/stage3_2_execution_orchestration/evidence/analysis_stage3_2.py [--no-write]

Não importa nada de app/ nem de tools/. Lê os seeds diretamente,
reconstrói o grafo de execução em nível de definição (equações,
agregações, transferências canônicas), calcula para cada alvo o fecho
esperado, os bloqueios por vínculo pendente e as restrições de ordem, e
compara com o orquestrador observado como caixa-preta (`runtime_probe.py`
em subprocesso).

Contadores (esperado: todos 0):
    divergências               plano/estado/fecho diferente do esperado
    transferências fora do contrato
    atalhos                    transferência lendo outro produtor que o declarado
    execuções fora da ordem    nó executado antes de um predecessor
    valores fictícios          valor gravado em execução bloqueada, ou
                               consumidor com valor diferente do produtor
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
SEED = REPO / "data" / "seed"
WRITE = "--no-write" not in sys.argv[1:]
RUN_DATE = "2026-09-01"
PERIOD = {"diário": "2026-09-01", "mensal": "2026-09", "anual": "2026"}
LINES = [f"L{i}" for i in range(1, 8)]
ACTIVE = {"PUBLISHED", "ACTIVE", "APPROVED"}

counters = Counter()
problems: list[str] = []


def fail(counter, message):
    counters[counter] += 1
    problems.append(f"[{counter}] {message}")


def instances(scope_type, scope_value):
    if scope_type == "linha" and "_" in str(scope_value):
        a, b = scope_value.split("_")
        return [(scope_type, l) for l in LINES[LINES.index(a): LINES.index(b) + 1]]
    return [(scope_type, scope_value)]


# ------------------------------------------------------------------
# 1. grafo independente
# ------------------------------------------------------------------
payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
blocks = sorted(payload["workbooks"])
variables, block_of = {}, {}
nodes, deps, producers = {}, {}, defaultdict(set)
for block in blocks:
    for v in json.loads((SEED / block / "variables.json").read_text(encoding="utf-8")):
        variables[v["variable_id"]] = v
        block_of[v["variable_id"]] = block
    for e in json.loads((SEED / block / "equations.json").read_text(encoding="utf-8")):
        if e["status"] not in ACTIVE:
            continue
        key = f"EQUATION:{e['equation_id']}"
        nodes[key] = (block, e["target_variable_id"])
        deps[key] = set(re.findall(r"\b(VAR\d+)", e["expression"]))
    for r in json.loads((SEED / block / "aggregation_rules.json").read_text(encoding="utf-8")):
        key = f"AGGREGATION:{r['aggregation_rule_id']}"
        nodes[key] = (block, r["target_variable_id"])
        deps[key] = {r["source_variable_id"]} | ({r["weight_variable_id"]} if r.get("weight_variable_id") else set())
links = {r["consumer_definition"]: r for r in payload["links"]}
pending = {r["consumer_definition"]: r for r in payload["pending"]}
for consumer, r in links.items():
    key = f"TRANSFER:{consumer}"
    nodes[key] = (r["consumer_block"], consumer)
    deps[key] = {r["source_definition"]}
for key, (_block, target) in nodes.items():
    producers[target].add(key)
for consumer in links:
    if producers[consumer] != {f"TRANSFER:{consumer}"}:
        fail("divergências", f"{consumer}: produtores {sorted(producers[consumer])}")


def closure(targets, pending_as_input):
    selected, needed_inputs, blockers = set(), set(), set()
    stack, seen = list(targets), set()
    while stack:
        var = stack.pop()
        if var in seen:
            continue
        seen.add(var)
        if var in pending and not pending_as_input:
            blockers.add(pending[var]["source_block"])
            continue
        owners = producers.get(var)
        if not owners:
            needed_inputs.add(var)
            continue
        for key in owners:
            if key not in selected:
                selected.add(key)
                stack.extend(deps[key])
    return selected, needed_inputs, blockers


def upstream(key, selected):
    return {p for var in deps[key] for p in producers.get(var, ()) if p in selected and p != key}


def check_order(steps, label):
    position = {k: i for i, k in enumerate(steps)}
    for key in steps:
        for up in upstream(key, set(steps)):
            if position[up] > position[key]:
                fail("execuções fora da ordem", f"{label}: {up} depois de {key}")


# ------------------------------------------------------------------
# 2. probes
# ------------------------------------------------------------------
def probe(request, hash_seed="0"):
    request = {"run_date": RUN_DATE, **request}
    completed = subprocess.run(
        [sys.executable, str(HERE / "runtime_probe.py")], input=json.dumps(request),
        capture_output=True, text=True, cwd=REPO, env={**os.environ, "PYTHONHASHSEED": hash_seed},
    )
    if completed.returncode != 0:
        fail("divergências", f"sonda falhou: {completed.stderr[-1500:]}")
        return {"plans": {}, "executions": [], "blocked": {}}, ""
    return json.loads(completed.stdout), completed.stdout


def input_values(needed):
    values, n = [], 0
    for var in sorted(needed):
        v = variables[var]
        for scope_type, scope_value in instances(v["scope_type"], v["scope_value"]):
            n += 1
            value = v["allowed_values"][0] if v["value_type"] == "categorico" else 1.0 + 0.0001 * n
            values.append([var, scope_type, scope_value, PERIOD[v["frequency"]], value])
    return values


all_targets = sorted({target for (_b, target) in nodes.values()})

# 2a. OFICIAL: planos de todos os alvos
official, _ = probe({"mode": "official", "plan_targets": all_targets})
plan_rows = []
for target in all_targets:
    selected, needed, blockers = closure([target], pending_as_input=False)
    got = official["plans"].get(target, {})
    expected_status = "INTERBLOCK_SOURCE_NOT_LOADED" if blockers else "OK"
    if got.get("status") != expected_status:
        fail("divergências", f"{target}: estado {got.get('status')} esperado {expected_status}")
    elif blockers and got.get("source_block") not in blockers:
        fail("divergências", f"{target}: bloco pendente {got.get('source_block')} não está em {sorted(blockers)}")
    elif not blockers:
        if set(got["steps"]) != selected:
            fail("divergências", f"{target}: fecho {len(got['steps'])} x esperado {len(selected)}")
        if set(got["inputs"]) != needed:
            fail("divergências", f"{target}: entradas divergentes")
        check_order(got["steps"], f"oficial {target}")
    plan_rows.append({
        "target": target, "block": block_of.get(target, ""), "expected": expected_status,
        "observed": got.get("status"), "pending_blocks": ";".join(sorted(blockers)),
        "steps": len(selected) if not blockers else "",
    })

# 2b. OFICIAL: execuções bloqueadas não gravam nada
blocked_targets = sorted(set(pending) | {"VAR16008", "VAR18002", "VAR13039"})
official_blocked, _ = probe({"mode": "official", "blocked_executions": blocked_targets})
for target in blocked_targets:
    got = official_blocked["blocked"].get(target, {})
    if got.get("code") != "INTERBLOCK_SOURCE_NOT_LOADED":
        fail("divergências", f"execução bloqueada {target}: {got}")
    if got.get("written", 1) != 0:
        fail("valores fictícios", f"{target}: {got.get('written')} chaves gravadas em execução bloqueada")

# 2c. execuções: oficial (lth_meta) + real_derived (cadeias reais, 13 consumidores)
executions_official = [["VAR18011"]]
executions_derived = [["VAR16008"], ["VAR18002"], ["VAR13039"]] + [[c] for c in sorted(links)]


def run_executions(mode, target_sets, hash_seed="0"):
    requests = []
    for targets in target_sets:
        _sel, needed, _bl = closure(targets, pending_as_input=(mode == "real_derived"))
        requests.append({"targets": targets, "inputs": input_values(needed)})
    return probe({"mode": mode, "executions": requests}, hash_seed)


transfer_rows = []


def audit_executions(result, mode):
    for execution in result["executions"]:
        targets = execution["targets"]
        selected, _needed, _bl = closure(targets, pending_as_input=(mode == "real_derived"))
        if set(execution["steps"]) != selected:
            fail("divergências", f"{mode} {targets}: passos divergentes")
        check_order(execution["steps"], f"{mode} {targets}")
        context = {(k[0], k[1], k[2], k[3]): k[4] for k in execution["context"]}
        linked_written = defaultdict(set)
        for (step, kind, node, block, variable, st, sv, period, value, status, src_block, src_var) in execution["events"]:
            if kind != "TRANSFER":
                if variable in links:
                    fail("transferências fora do contrato", f"{variable} gravada por {kind}:{node}")
                continue
            link = links.get(node)
            if link is None:
                fail("transferências fora do contrato", f"transferência sem vínculo canônico {node}")
                continue
            if (src_block, src_var) != (link["source_block"], link["source_definition"]):
                fail("atalhos", f"{node} leu {src_block}.{src_var}, declarado {link['source_block']}.{link['source_definition']}")
            if [st, sv] not in [[i["scope_type"], i["scope_value"]] for i in link["instances"]]:
                fail("transferências fora do contrato", f"{node}: instância {st}/{sv}")
            if period != PERIOD[link["consumer_frequency"]]:
                fail("transferências fora do contrato", f"{node}: período {period}")
            producer_value = context.get((link["source_definition"], st, sv, period))
            consumer_value = context.get((node, st, sv, period))
            if producer_value is None or consumer_value != producer_value or value != producer_value:
                fail("valores fictícios", f"{node} {st}/{sv}: consumidor {consumer_value} x produtor {producer_value}")
            linked_written[node].add((st, sv))
            transfer_rows.append({
                "mode": mode, "targets": ";".join(targets), "step": step,
                "consumer": f"{block}.{node}", "instance": f"{st}/{sv}", "period_id": period,
                "declared_source": f"{link['source_block']}.{link['source_definition']}",
                "read_source": f"{src_block}.{src_var}", "value": value,
                "producer_value_in_context": producer_value, "status": status,
                "result": "OK" if (src_block, src_var) == (link["source_block"], link["source_definition"])
                and consumer_value == producer_value else "DIVERGENCE",
            })
        for node in (k.split(":", 1)[1] for k in execution["steps"] if k.startswith("TRANSFER:")):
            expected = {(i["scope_type"], i["scope_value"]) for i in links[node]["instances"]}
            if linked_written[node] != expected:
                fail("divergências", f"{node}: instâncias transferidas {sorted(linked_written[node])}")


official_exec, _ = run_executions("official", executions_official)
audit_executions(official_exec, "official")
derived_exec, derived_raw = run_executions("real_derived", executions_derived)
audit_executions(derived_exec, "real_derived")

# Cadeia obrigatória: ordem exata e ausência de atalho.
chain = next(e for e in derived_exec["executions"] if e["targets"] == ["VAR16008"])
if chain["steps"] != ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"]:
    fail("execuções fora da ordem", f"cadeia production->yield->area_41: {chain['steps']}")

# 3. determinismo: mesma sonda com outro PYTHONHASHSEED
_again, derived_raw_2 = run_executions("real_derived", executions_derived, hash_seed="424242")
deterministic = hashlib.sha256(derived_raw.encode()).hexdigest() == hashlib.sha256(derived_raw_2.encode()).hexdigest()
if not deterministic:
    fail("divergências", "resultado difere entre PYTHONHASHSEED 0 e 424242")

summary = {
    "targets_planned": len(all_targets),
    "targets_executable_official": sum(1 for r in plan_rows if r["expected"] == "OK"),
    "targets_blocked_official": sum(1 for r in plan_rows if r["expected"] != "OK"),
    "blocked_by_block": dict(Counter(b for r in plan_rows for b in r["pending_blocks"].split(";") if b)),
    "blocked_executions_checked": len(blocked_targets),
    "executions_checked": {"official": len(executions_official), "real_derived": len(executions_derived)},
    "transfer_events_checked": len(transfer_rows),
    "deterministic_across_hash_seeds": deterministic,
    "divergências": counters["divergências"],
    "transferências fora do contrato": counters["transferências fora do contrato"],
    "atalhos": counters["atalhos"],
    "execuções fora da ordem": counters["execuções fora da ordem"],
    "valores fictícios": counters["valores fictícios"],
    "problems": problems[:50],
}
if WRITE:
    for path, rows in ((HERE / "plan_evidence.csv", plan_rows), (HERE / "transfer_evidence.csv", transfer_rows)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (HERE / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(1 if problems else 0)
