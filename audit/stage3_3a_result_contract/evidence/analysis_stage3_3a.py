"""
Etapa 3.3A — auditoria independente do contrato value + state + detail.

    python audit/stage3_3a_result_contract/evidence/analysis_stage3_3a.py [--no-write]

Não importa nada de app/ nem de tools/ e não replica a implementação:
as expectativas vêm dos seeds (`data/seed/**`), do artefato canônico
(`interblock_links.json`), da taxonomia de estados documentada no
contrato D2 e das evidências históricas da Etapa 3.2
(`audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv`).
O runtime é observado como caixa-preta por `runtime_probe.py`
(subprocesso).

Verificações: representação, preservação de value/state/detail,
allowed_values, identidade (variável/instância/período/frequência),
transferências sem perda, ausência de atalhos e de iscas, pendências sem
valor fictício, topologia igual à da 3.2, determinismo.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEED = REPO / "data" / "seed"
WRITE = "--no-write" not in sys.argv[1:]
PERIOD = {"diário": "2026-09-01", "mensal": "2026-09", "anual": "2026"}
LINES = [f"L{i}" for i in range(1, 8)]
STATES = ["NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"]  # contrato D2
TRICKY_DETAILS = ["  pontas  ", "a\nb", "ção ÿ €", "", "\t"]

counters = Counter()
problems: list[str] = []
evidence_rows: list[dict] = []


def fail(counter, message):
    counters[counter] += 1
    problems.append(f"[{counter}] {message}")


def instances(scope_type, scope_value):
    if scope_type == "linha" and "_" in str(scope_value):
        a, b = scope_value.split("_")
        return [(scope_type, l) for l in LINES[LINES.index(a): LINES.index(b) + 1]]
    return [(scope_type, scope_value)]


payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
variables = {}
for block in payload["workbooks"]:
    for v in json.loads((SEED / block / "variables.json").read_text(encoding="utf-8")):
        variables[v["variable_id"]] = v
links = {r["consumer_definition"]: r for r in payload["links"]}
pending = {r["consumer_definition"]: r for r in payload["pending"]}

commands = []

# ------------------------------------------------------------------
# A. representação
# ------------------------------------------------------------------
construct_cases = {
    "value_int": ([42], ["OK", [42, "int", None, None]]),
    "value_float": ([4.5], ["OK", [4.5, "float", None, None]]),
    "value_text": (["LC"], ["OK", ["LC", "str", None, None]]),
    "value_F": (["F"], ["OK", ["F", "str", None, None]]),
    **{f"state_{s}": ([1.0, s], ["OK", [1.0, "float", s, None]]) for s in STATES},
    **{f"detail_{i}": ([2.0, "INVALID_INPUT", d], ["OK", [2.0, "float", "INVALID_INPUT", d]])
       for i, d in enumerate(TRICKY_DETAILS)},
    **{f"bad_state_{i}": ([1.0, s], ["ERR", "RESULT_CONTRACT_INVALID"])
       for i, s in enumerate(["OK", "no_applicable_rule", "INVALID_INPUT ", "F", ""])},
    "bad_value_bool": ([True], ["ERR", "RESULT_CONTRACT_INVALID"]),
    "bad_detail_type": ([1.0, None, 5], ["ERR", "RESULT_CONTRACT_INVALID"]),
}
for cid, (args, _expected) in construct_cases.items():
    commands.append({"kind": "construct", "id": f"A:{cid}", "args": args})

# ------------------------------------------------------------------
# B. allowed_values (domínio do valor categórico, contrato 2.4)
# ------------------------------------------------------------------
hes = next(v for v in variables.values() if v.get("allowed_values"))
allowed = hes["allowed_values"]
numeric = next(v for v in variables.values() if v["value_type"] == "numerico")
b_writes, b_expected = [], []
for i, option in enumerate(allowed + ["Parado", "lc", allowed[0] + " ", "F"]):
    line = hes["scope_value"].split("_")[0] if "_" in hes["scope_value"] else hes["scope_value"]
    b_writes.append([hes["variable_id"], hes["scope_type"], line, f"2026-09-{i + 1:02d}", [option]])
    ok = option in allowed or option == "F"
    b_expected.append(["OK"] if ok else ["ERR", "RESULT_VALUE_OUTSIDE_ALLOWED_VALUES"])
b_writes.append([numeric["variable_id"], "linha", "L1", "2026-09-01", [-1e9]])
b_expected.append(["OK"])
commands.append({
    "kind": "context_roundtrip", "id": "B:allowed_values",
    "declare": [hes["variable_id"], numeric["variable_id"]],
    "writes": b_writes, "reads": [w[:4] for w in b_writes],
})

# ------------------------------------------------------------------
# C. identidade: variável / instância / período / frequência
# ------------------------------------------------------------------
daily = next(v for v in variables.values() if v["variable_name"] == "lth" and v["variable_id"].startswith("VAR12") and v["frequency"] == "diário")
monthly = next(v for v in variables.values() if v["variable_name"] == "lth" and v["variable_id"].startswith("VAR12") and v["frequency"] == "mensal")
c_keys = [
    (daily["variable_id"], "linha", "L1", "2026-09-01"),
    (daily["variable_id"], "linha", "L2", "2026-09-01"),
    (daily["variable_id"], "linha", "L1", "2026-09-02"),
    (monthly["variable_id"], "linha", "L1", "2026-09"),
]
c_results = [[10.0 + i, STATES[i % 3], f"id{i}"] for i in range(len(c_keys))]
c_cross = [
    (daily["variable_id"], "linha", "L1", "2026-09"),   # frequência errada
    (monthly["variable_id"], "linha", "L1", "2026-09-01"),
    (daily["variable_id"], "linha", "L3", "2026-09-01"),
]
commands.append({
    "kind": "context_roundtrip", "id": "C:identity",
    "writes": [[*k, r] for k, r in zip(c_keys, c_results)],
    "reads": [list(k) for k in c_keys] + [list(k) for k in c_cross],
})

# ------------------------------------------------------------------
# D. transferência de TODOS os vínculos válidos, com iscas
# ------------------------------------------------------------------
def producer_first(consumers):
    order, seen = [], set()

    def visit(c):
        if c in seen:
            return
        seen.add(c)
        if links[c]["source_definition"] in links:
            visit(links[c]["source_definition"])
        order.append(c)

    for c in sorted(consumers):
        visit(c)
    return order


order = producer_first(links)
writes, transfers, expected = [], [], {}
n = 0
for consumer in order:
    link = links[consumer]
    period = PERIOD[link["consumer_frequency"]]
    for inst in link["instances"]:
        key = (inst["scope_type"], inst["scope_value"])
        producer = link["source_definition"]
        # Um produtor pode alimentar vários consumidores: um único
        # resultado por chave do produtor.
        if producer not in links and (producer, *key, period) not in expected:
            n += 1
            result = [1000.0 + n, STATES[n % 3] if n % 4 else None, f"{producer}|{key[1]}|{n}" if n % 5 else None]
            writes.append([producer, *key, period, result])
            expected[(producer, *key, period)] = result
            # iscas: mesmo produtor em outro período e sem período
            for decoy_period in ("2025-01-01", "2025-01", "2025", None):
                if decoy_period != period:
                    writes.append([producer, *key, decoy_period, [-1.0, "VALIDATION_FAILED", "ISCA"]])
        expected[(consumer, *key, period)] = expected[(producer, *key, period)]
        transfers.append([consumer, *key, period])
commands.append({"kind": "transfer", "id": "D:all_links", "writes": writes, "transfers": transfers})

# atalho: yield.lth já tem resultado próprio diferente do de production.lth;
# area_41.lth deve receber o de yield.lth.
chain_consumer = next(c for c, r in links.items() if r["source_definition"] in links)
middle = links[chain_consumer]["source_definition"]
root = links[middle]["source_definition"]
shortcut_writes, shortcut_transfers = [], []
for inst in links[chain_consumer]["instances"]:
    key = (inst["scope_type"], inst["scope_value"])
    shortcut_writes.append([root, *key, PERIOD["diário"], [1.0, None, "ROOT"]])
    shortcut_writes.append([middle, *key, PERIOD["diário"], [2.0, "INVALID_INPUT", "MIDDLE"]])
    shortcut_transfers.append([chain_consumer, *key, PERIOD["diário"]])
commands.append({"kind": "transfer", "id": "D:shortcut", "writes": shortcut_writes, "transfers": shortcut_transfers})

# pendências: transferência pedida -> erro, nada gravado
commands.append({"kind": "transfer", "id": "D:pending", "writes": [], "transfers": [
    [c, *instances(r["consumer_scope"]["scope_type"], r["consumer_scope"]["scope_value"])[0],
     PERIOD[r["consumer_frequency"]]] for c, r in sorted(pending.items())
]})
commands.append({"kind": "blocked_execution", "id": "E:blocked", "run_date": "2026-09-01",
                 "targets": sorted(pending) + ["VAR16008", "VAR18002", "VAR13039"]})

# ------------------------------------------------------------------
# F. topologia igual à da Etapa 3.2
# ------------------------------------------------------------------
plan_evidence = list(csv.DictReader(open(
    REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv", encoding="utf-8")))
commands.append({"kind": "plans", "id": "F:official", "mode": "official",
                 "targets": [r["target"] for r in plan_evidence]})
commands.append({"kind": "plans", "id": "F:derived", "mode": "real_derived",
                 "targets": ["VAR16008", "VAR18002", "VAR13039"]})


# ------------------------------------------------------------------
# execução da sonda (duas vezes, hash seeds diferentes)
# ------------------------------------------------------------------
def probe(seed):
    completed = subprocess.run(
        [sys.executable, str(HERE / "runtime_probe.py")], input=json.dumps(commands),
        capture_output=True, text=True, cwd=REPO, env={**os.environ, "PYTHONHASHSEED": seed},
    )
    if completed.returncode != 0:
        fail("divergências", f"sonda falhou: {completed.stderr[-1500:]}")
        return {}, ""
    return json.loads(completed.stdout), completed.stdout


observed, raw_a = probe("0")
_again, raw_b = probe("31337")
deterministic = raw_a == raw_b and raw_a != ""
if not deterministic:
    fail("determinismo", "saída da sonda difere entre PYTHONHASHSEED 0 e 31337")

# A
for cid, (_args, exp) in construct_cases.items():
    got = observed.get(f"A:{cid}")
    if got != exp:
        fail("representação", f"{cid}: {got} != {exp}")

# B
b = observed.get("B:allowed_values", {"writes": [], "reads": []})
if b["writes"] != b_expected:
    fail("allowed_values", f"escritas {b['writes']} != {b_expected}")
for write, got_write, got_read in zip(b_writes, b["writes"], b["reads"]):
    if got_write == ["OK"] and got_read[0] != write[4][0]:
        fail("allowed_values", f"valor aceito não preservado: {got_read}")
    if got_write[0] == "ERR" and got_read[0] != "ERR":
        fail("valores fictícios", f"valor rejeitado foi gravado: {write}")

# C
c = observed.get("C:identity", {"reads": []})
for key, result, got in zip(c_keys, c_results, c["reads"]):
    if got != [result[0], "float", result[1], result[2]]:
        fail("identidade", f"{key}: {got} != {result}")
for key, got in zip(c_cross, c["reads"][len(c_keys):]):
    if got != ["ERR", "VariableNotFoundError"]:
        fail("identidade", f"leitura cruzada {key} devolveu {got}")

# D
d = observed.get("D:all_links", {"errors": [], "context": []})
if d["errors"]:
    fail("divergências", f"erros de transferência {d['errors'][:5]}")
context = {(r[0], r[1], r[2], r[3]): [r[4], r[6], r[7]] for r in d["context"]}
for consumer in order:
    link = links[consumer]
    period = PERIOD[link["consumer_frequency"]]
    for inst in link["instances"]:
        key = (consumer, inst["scope_type"], inst["scope_value"], period)
        want = expected[key]
        got = context.get(key)
        status = "OK"
        if got is None:
            fail("transferências com perda", f"{key}: consumidor sem resultado")
            status = "MISSING"
        else:
            if got[0] != want[0]:
                fail("transferências com perda", f"{key}: value {got[0]} != {want[0]}")
                status = "VALUE"
            if got[1] != want[1]:
                fail("transferências com perda", f"{key}: state {got[1]} != {want[1]}")
                status = "STATE"
            if got[2] != want[2]:
                fail("transferências com perda", f"{key}: detail {got[2]!r} != {want[2]!r}")
                status = "DETAIL"
            if got[2] == "ISCA":
                fail("atalhos", f"{key}: leu isca")
        evidence_rows.append({
            "consumer": f"{link['consumer_block']}.{consumer}",
            "source": f"{link['source_block']}.{link['source_definition']}",
            "instance": f"{inst['scope_type']}/{inst['scope_value']}", "period_id": period,
            "expected_value": want[0], "expected_state": want[1], "expected_detail": want[2],
            "received_value": got[0] if got else "", "received_state": got[1] if got else "",
            "received_detail": got[2] if got else "", "result": status,
        })
# nenhum consumidor recebeu algo fora das instâncias/períodos do vínculo
for (entity, st, sv, period), _v in context.items():
    if entity in links:
        link = links[entity]
        if [st, sv] not in [[i["scope_type"], i["scope_value"]] for i in link["instances"]] or period != PERIOD[link["consumer_frequency"]]:
            fail("transferências com perda", f"{entity} gravado fora do vínculo: {st}/{sv} {period}")

s = observed.get("D:shortcut", {"errors": [], "context": []})
s_ctx = {(r[0], r[1], r[2], r[3]): [r[4], r[6], r[7]] for r in s["context"]}
for inst in links[chain_consumer]["instances"]:
    got = s_ctx.get((chain_consumer, inst["scope_type"], inst["scope_value"], PERIOD["diário"]))
    if got != [2.0, "INVALID_INPUT", "MIDDLE"]:
        fail("atalhos", f"{chain_consumer} {inst}: recebeu {got}, esperado o resultado de {middle}")

p = observed.get("D:pending", {"errors": [], "context": []})
if sorted(e[0] for e in p["errors"]) != sorted(pending) or {e[3] for e in p["errors"]} != {"INTERBLOCK_SOURCE_NOT_LOADED"}:
    fail("pendências", f"erros de pendência {p['errors'][:3]}")
if p["context"]:
    fail("valores fictícios", f"pendência gravou {p['context'][:3]}")

# E
for target, (code, written) in observed.get("E:blocked", {}).items():
    if code != "INTERBLOCK_SOURCE_NOT_LOADED" or written != 0:
        fail("valores fictícios", f"execução bloqueada {target}: {code}, {written} resultados")

# F
official_plans = observed.get("F:official", {})
for row in plan_evidence:
    got = official_plans.get(row["target"])
    if got is None:
        fail("topologia", f"{row['target']} sem plano")
        continue
    if got[0] != row["observed"]:
        fail("topologia", f"{row['target']}: {got[0]} != 3.2 {row['observed']}")
    elif got[0] == "OK" and str(len(got[1])) != row["steps"]:
        fail("topologia", f"{row['target']}: {len(got[1])} passos != 3.2 {row['steps']}")
derived = observed.get("F:derived", {})
expected_chains = {
    "VAR16008": ["EQUATION:EQ12012", "TRANSFER:VAR11031", "TRANSFER:VAR16007", "EQUATION:EQ16004"],
    "VAR13039": ["EQUATION:EQ12012", "TRANSFER:VAR13062", "EQUATION:EQ13014"],
}
for target, steps in expected_chains.items():
    if derived.get(target) != ["OK", steps]:
        fail("topologia", f"{target}: {derived.get(target)}")
energy = derived.get("VAR18002", ["?", []])[1]
if len(energy) != 20 or not (
    energy.index("EQUATION:EQ12012") < energy.index("TRANSFER:VAR11031") < energy.index("TRANSFER:VAR12062")
    < energy.index("TRANSFER:VAR18001") < energy.index("EQUATION:EQ18001")
):
    fail("topologia", f"cadeia production->energy alterada: {energy}")

summary = {
    "representation_cases": len(construct_cases),
    "allowed_values_writes": len(b_writes),
    "identity_reads": len(c["reads"]),
    "links_checked": len(links),
    "instance_transfers_checked": len(evidence_rows),
    "decoy_results_written": sum(1 for w in writes if w[4][2] == "ISCA"),
    "pending_checked": len(pending),
    "official_plans_compared_with_stage_3_2": len(plan_evidence),
    "deterministic_across_hash_seeds": deterministic,
    **{name: counters[name] for name in (
        "divergências", "representação", "allowed_values", "identidade",
        "transferências com perda", "atalhos", "pendências", "valores fictícios",
        "topologia", "determinismo",
    )},
    "problems": problems[:50],
}
if WRITE:
    with open(HERE / "result_transfer_evidence.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    (HERE / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
sys.exit(1 if problems else 0)
