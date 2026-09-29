"""
Etapa 3.3C — auditoria independente da agregação consciente de Result.

    python audit/stage3_3c_state_aware_aggregation/evidence/analysis_stage3_3c.py [--no-write]

Não importa app/ nem tools/. O runtime é observado por `runtime_probe.py`
(subprocesso, API pública: TemporalAggregationService.aggregate e o
orquestrador). O oráculo abaixo é escrito a partir do TEXTO do contrato,
sem reutilizar a implementação:

    Policy B   present = {state de cada componente com state}
               len(present) == 0 -> sem state/detail
               len(present) == 1 -> state propagado; details desse state:
                    1 valor (inclusive None) -> detail propagado
                    >1 (None x texto conta)  -> MULTI_DETAIL_COMPOSITION_UNDEFINED
               len(present) > 1  -> MULTI_STATE_COMBINATION_UNDEFINED
               componentes = série de origem + pesos (WEIGHTED_AVERAGE)
    valor      aritmética contratual do agregador sobre todos os valores;
               componente sem value (só existe com state) -> value None
    erros      janela vazia EmptyAggregationWindowError; "F"
               AggregationFailureError; texto NonNumericAggregationError;
               pesos somando 0 ZeroWeightSumError; composição antes da
               matemática; detail sem state DETAIL_WITHOUT_STATE
    interbloco consumidor == resultado agregado na MESMA identidade
               (período + janela); reexecução igual idempotente; Result
               diferente na mesma identidade -> conflito sem sobrescrita
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WRITE = "--no-write" not in sys.argv[1:]
S1, S2 = "NO_APPLICABLE_RULE", "INVALID_INPUT"
DAYS = ["2026-09-01", "2026-09-02", "2026-09-03"]
RUN = "2026-09-03"
WEIGHTS = [[1.0, None, None], [2.0, None, None], [3.0, None, None]]
AGGREGATORS = {  # nome: (tipo, integration_factor)
    "AVERAGE": ("AVERAGE", 1), "SUM": ("SUM", 1), "SUM_X24": ("SUM", 24.0),
    "WEIGHTED_AVERAGE": ("WEIGHTED_AVERAGE", 1), "MOVING_AVERAGE": ("MOVING_AVERAGE", 1),
}
ALPHABET = [
    (10.0, None, None), (20.0, None, None), (30.0, S1, None), (40.0, S1, "a"), (50.0, S1, "b"),
    (60.0, S2, None), (None, S1, None), (None, S1, "a"), (None, S2, "b"),
]

counters = Counter()
problems: list[str] = []
rows: list[dict] = []


def fail(counter, message):
    counters[counter] += 1
    problems.append(f"[{counter}] {message}")


# ------------------------------------------------------------------
# oráculo
# ------------------------------------------------------------------
def oracle_semantics(components):
    present = defaultdict(set)
    for _value, state, detail in components:
        if state is not None:
            present[state].add(detail)
    if len(present) > 1:
        return ("ERR", "MULTI_STATE_COMBINATION_UNDEFINED")
    if not present:
        return (None, None)
    (state, details), = present.items()
    if len(details) > 1:
        return ("ERR", "MULTI_DETAIL_COMPOSITION_UNDEFINED")
    return (state, next(iter(details)))


def oracle_value(name, values, weights):
    kind, factor = AGGREGATORS[name]
    if any(v is None for v in values + weights):
        return None
    if kind == "SUM":
        return math.fsum(v * factor for v in values)
    if kind == "WEIGHTED_AVERAGE":
        return math.fsum(v * w for v, w in zip(values, weights)) / math.fsum(weights)
    return math.fsum(values) / len(values)


def oracle(name, sources, weights):
    components = sources + (weights if AGGREGATORS[name][0] == "WEIGHTED_AVERAGE" else [])
    semantics = oracle_semantics(components)
    if semantics[0] == "ERR":
        return list(semantics)
    value = oracle_value(name, [c[0] for c in sources],
                         [c[0] for c in weights] if AGGREGATORS[name][0] == "WEIGHTED_AVERAGE" else [])
    return ["OK", value, *semantics]


# ------------------------------------------------------------------
# comandos
# ------------------------------------------------------------------
commands, expectations = [], {}


def add(cid, name, sources, weights=None, expected=None, **extra):
    kind, factor = AGGREGATORS[name]
    command = {"kind": "aggregate", "id": cid, "type": kind, "integration_factor": factor,
               "days": DAYS, "run_date": RUN, "sources": [list(c) for c in sources],
               "weights": [list(w) for w in (weights or WEIGHTS)] if kind == "WEIGHTED_AVERAGE" else None,
               **extra}
    commands.append(command)
    expectations[cid] = (name, sources, weights or WEIGHTS,
                         expected if expected is not None else oracle(name, list(sources), list(weights or WEIGHTS)))


for name in AGGREGATORS:
    for triple in itertools.product(range(len(ALPHABET)), repeat=3):
        add(f"SWEEP|{name}|{triple}", name, [ALPHABET[i] for i in triple])
    # janela vazia (explícita, depois de run_date)
    add(f"EMPTY|{name}", name, [], expected=["ERR", "EmptyAggregationWindowError"],
        window=["2026-10-01", "2026-10-31"])
    # erros matemáticos existentes e precedência da composição
    add(f"F|{name}", name, [("F", None, None), (20.0, None, None), (30.0, None, None)],
        expected=["ERR", "AggregationFailureError"])
    add(f"TEXT|{name}", name, [("LC", None, None), (20.0, None, None), (30.0, None, None)],
        expected=["ERR", "NonNumericAggregationError"])
    add(f"F_CONFLICT|{name}", name, [("F", S1, None), (20.0, S2, None), (30.0, None, None)],
        expected=["ERR", "MULTI_STATE_COMBINATION_UNDEFINED"])
    add(f"DETAIL_WITHOUT_STATE|{name}", name, [(10.0, None, "x"), (20.0, None, None), (30.0, None, None)],
        expected=["ERR", "DETAIL_WITHOUT_STATE"])
# pesos como componentes
for i, weight_case in enumerate([
    [(1.0, None, None), (2.0, S1, "p"), (3.0, None, None)],
    [(1.0, S2, None), (2.0, None, None), (3.0, None, None)],
    [(1.0, S1, "p"), (2.0, S1, "q"), (3.0, None, None)],
    [(None, S1, None), (2.0, None, None), (3.0, None, None)],
]):
    for j, sources in enumerate([[(10.0, None, None)] * 3, [(10.0, S1, "p"), (20.0, None, None), (30.0, None, None)]]):
        add(f"WEIGHTS|{i}|{j}", "WEIGHTED_AVERAGE", sources, weight_case)
add("ZERO_WEIGHTS", "WEIGHTED_AVERAGE", [(10.0, None, None)] * 3, [(0.0, None, None)] * 3,
    expected=["ERR", "ZeroWeightSumError"])

CHAINS = {
    "C1_WINDOWS_PERIODS_RERUN": [
        {"run_date": "2026-09-01", "sources": {"2026-09-01": [100.0, S1, "lth"]}},
        {"run_date": "2026-09-02", "sources": {"2026-09-02": [200.0, None, None]}},
        {"run_date": "2026-09-01"},
        {"run_date": "2026-10-01", "sources": {"2026-10-01": [50.0, S2, None]}},
    ],
    "C2_CONFLICT_SAME_IDENTITY": [
        {"run_date": "2026-09-01", "sources": {"2026-09-01": [100.0, S1, "a"]}},
        {"run_date": "2026-09-01", "sources": {"2026-09-01": [100.0, S1, "b"]}},
    ],
    "C3_MULTI_STATE_IN_WINDOW": [
        {"run_date": "2026-09-02", "sources": {"2026-09-01": [100.0, S1, None], "2026-09-02": [200.0, S2, None]}},
    ],
    "C4_VALUELESS_COMPONENT": [
        {"run_date": "2026-09-02", "sources": {"2026-09-01": [None, S1, "h"], "2026-09-02": [200.0, None, None]}},
    ],
}
for cid, steps in CHAINS.items():
    commands.append({"kind": "chain", "id": cid, "target": "VAR18010", "steps": steps})


def probe(seed):
    completed = subprocess.run(
        [sys.executable, str(HERE / "runtime_probe.py")], input=json.dumps(commands),
        capture_output=True, text=True, cwd=REPO, env={**os.environ, "PYTHONHASHSEED": seed},
    )
    if completed.returncode != 0:
        fail("sonda", completed.stderr[-1500:])
        return {}, ""
    return json.loads(completed.stdout), completed.stdout


observed, raw_a = probe("0")
_b, raw_b = probe("4242")
digests = {seed: hashlib.sha256(raw.encode()).hexdigest() for seed, raw in (("0", raw_a), ("4242", raw_b))}
deterministic = raw_a == raw_b and raw_a != ""
if not deterministic:
    fail("determinismo", f"sonda difere entre hash seeds: {digests}")


# ------------------------------------------------------------------
# comparação: agregações isoladas
# ------------------------------------------------------------------
def same(expected, got):
    if expected[0] == "ERR" or got[0] == "ERR":
        return expected[:2] == got[:2]
    ev, gv = expected[1], got[1]
    value_ok = (ev is None and gv is None) or (
        ev is not None and gv is not None and math.isclose(ev, gv, rel_tol=1e-9, abs_tol=1e-12))
    consistent = got[1:4] == got[4:7]            # ForecastValue == seu Result canônico
    return value_ok and expected[2:4] == got[2:4] and consistent


by_multiset = defaultdict(set)
for cid, (name, sources, weights, expected) in expectations.items():
    got = observed.get(cid)
    ok = got is not None and same(expected, got)
    if got and got[0] == "ERR" and set(got[2]) & {"ValueError", "TypeError", "ArithmeticError", "ZeroDivisionError"} \
            and got[1].startswith("MULTI_"):
        fail("erro mascarado", f"{cid}: {got}")
        ok = False
    if not ok:
        fail("divergência", f"{cid}: esperado {expected}, obtido {got}")
    if cid.startswith("SWEEP|") and got:
        # Ordem: estado/detail/erro nunca dependem da ordem. O valor também
        # não, exceto na WEIGHTED_AVERAGE, onde cada valor está pareado ao
        # peso do SEU dia (os pesos aqui são fixos por dia) — lá só a
        # semântica é comparada entre permutações.
        key = (name, tuple(sorted(map(repr, sources))))
        weighted = AGGREGATORS[name][0] == "WEIGHTED_AVERAGE"
        value = None if weighted or got[0] != "OK" else (round(got[1], 9) if isinstance(got[1], float) else got[1])
        by_multiset[key].add(json.dumps([got[0], value, *got[2:4]] if got[0] == "OK" else got[:2]))
    rows.append({"case": cid, "operation": AGGREGATORS[name][0] + (f" x{AGGREGATORS[name][1]}" if AGGREGATORS[name][1] != 1 else ""),
                 "inputs": json.dumps(sources), "weights": json.dumps(weights) if AGGREGATORS[name][0] == "WEIGHTED_AVERAGE" else "",
                 "expected": json.dumps(expected), "actual": json.dumps(got[:4] if got else None),
                 "result": "PASS" if ok else "FAIL"})
order_groups = 0
for key, outcomes in by_multiset.items():
    order_groups += 1
    if len(outcomes) != 1:
        fail("ordem", f"{key}: resultados diferentes por permutação {outcomes}")


# ------------------------------------------------------------------
# comparação: cadeia real (interbloco + temporal + reexecução)
# ------------------------------------------------------------------
def chain_expectations(steps, instances):
    """Oráculo passo a passo: fontes acumuladas por dia; janela até run_date."""
    sources, expected = {}, {}
    for step in steps:
        for day, series in step.get("sources", {}).items():
            sources[day] = series
        run = step["run_date"]
        period = run[:7]
        window = [d for d in sorted(sources) if d[:7] == period and d <= run]
        for k, (st, sv) in enumerate(instances):
            comps = [[None if sources[d][0] is None else sources[d][0] + k, sources[d][1], sources[d][2]]
                     for d in window]
            semantics = oracle_semantics(comps)
            if semantics[0] == "ERR":
                expected[(run, st, sv)] = ["ERR", semantics[1]]
            else:
                values = [c[0] for c in comps]
                value = None if any(v is None for v in values) else math.fsum(values) / len(values)
                expected[(run, st, sv)] = ["OK", value, *semantics]
    return expected


chain_summary = {}
for cid, steps in CHAINS.items():
    got = observed.get(cid)
    if not got:
        fail("divergência", f"{cid}: sem observação")
        continue
    if got["rule"][1] != "AVERAGE" or got["rule"][4] != "mensal":
        fail("oráculo", f"{cid}: regra real mudou {got['rule']}")
    instances = [tuple(i) for i in got["instances"]]
    store = {(r[0], r[1], r[2], r[3], r[4]): r[5:8] for r in got["context"]}
    codes = [run["code"] for run in got["runs"]]
    chain_summary[cid] = codes
    target, consumer = got["rule"][3], got["link"][1]
    link_instances = [tuple(i) for i in got["link"][2]]
    if cid == "C2_CONFLICT_SAME_IDENTITY":
        if codes != [None, "INTERBLOCK_CONSUMER_VALUE_CONFLICT"]:
            fail("sobrescrita", f"{cid}: {codes}")
        for st, sv in link_instances:
            kept = store.get((consumer, st, sv, "2026-09", "2026-09-01"))
            if kept is None or kept[2] != "a":
                fail("sobrescrita", f"{cid}: consumidor {st}/{sv} = {kept}")
        rows.append({"case": cid, "operation": "chain", "inputs": json.dumps(steps), "weights": "",
                     "expected": json.dumps([None, "INTERBLOCK_CONSUMER_VALUE_CONFLICT"]),
                     "actual": json.dumps(codes), "result": "PASS" if not counters["sobrescrita"] else "FAIL"})
        continue
    expected = chain_expectations(steps, instances)
    for index, step in enumerate(steps):
        run = step["run_date"]
        for st, sv in link_instances:
            want = expected[(run, st, sv)]
            if want[0] == "ERR":
                ok = codes[index] == want[1]
                actual = [codes[index]]
            else:
                producer = store.get((target, st, sv, run[:7], run))
                received = store.get((consumer, st, sv, run[:7], run))
                ok = (codes[index] is None and producer == received and received is not None
                      and same(want, ["OK", *received, *received]))
                actual = received
            if not ok:
                fail("interbloco/temporal", f"{cid} passo {index} {st}/{sv}: esperado {want}, obtido {actual}")
            rows.append({"case": f"{cid}#{index}", "operation": "AVERAGE -> TRANSFER", "inputs": json.dumps(step),
                         "weights": "", "expected": json.dumps(want), "actual": json.dumps(actual),
                         "result": "PASS" if ok else "FAIL"})
    if cid == "C1_WINDOWS_PERIODS_RERUN":
        if {t[4] for t in got["runs"][2]["transfers"]} != {"UNCHANGED"}:
            fail("idempotência", f"reexecução de 09-01: {got['runs'][2]['transfers']}")
        windows = sorted({k[4] for k in store if k[0] == consumer and k[3] == "2026-09"})
        if windows != ["2026-09-01", "2026-09-02"]:
            fail("interbloco/temporal", f"janelas de setembro {windows}")
        if not [k for k in store if k[0] == consumer and k[3] == "2026-10"]:
            fail("interbloco/temporal", "período de outubro ausente")


# ------------------------------------------------------------------
# estático (texto/AST, sem importar)
# ------------------------------------------------------------------
service = (REPO / "app/engine/temporal_aggregation_service.py").read_text(encoding="utf-8")
if "compose_aggregated_result" not in service or "require_plain_for_aggregation" in service:
    fail("estático", "serviço não usa a composição central")
values_src = (REPO / "app/domain/values.py").read_text(encoding="utf-8")
for forbidden in ("BLOCKED_BY_UPSTREAM_ERROR", "TECHNICAL_ERROR", "MIXED_STATE", "PARTIAL_STATE", "UNKNOWN_STATE"):
    if forbidden in values_src:
        fail("estados inventados", forbidden)
propagation = (REPO / "app/domain/state_propagation.py").read_text(encoding="utf-8").lower()
if "priority =" in propagation or "state_priority" in propagation:
    fail("prioridade", "prioridade de estados no código")
git = subprocess.run(["git", "diff", "--name-only", "4faf5f1", "HEAD"], capture_output=True, text=True, cwd=REPO)
changed = git.stdout.split() if git.returncode == 0 else []
dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO)
changed += [line[3:] for line in dirty.stdout.splitlines()] if dirty.returncode == 0 else []
protected = ("data/", "tools/", "app/domain/values.py", "app/domain/interblock/", "app/engine/time_period_resolver.py",
             "app/engine/calculation_context.py", "app/domain/forecast/aggregation.py")
touched = sorted({p for p in changed if p.startswith(protected)})
if touched:
    fail("artefatos protegidos", f"alterados desde 4faf5f1: {touched}")


summary = {
    "cases": len(expectations), "chains": chain_summary, "order_groups": order_groups,
    "rows": len(rows), "deterministic": deterministic, "probe_sha256": digests,
    "protected_touched": touched, "problems": dict(counters),
}
if WRITE:
    (HERE / "analysis_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
                                                encoding="utf-8")
    with (HERE / "aggregation_evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (HERE / "determinism_check.txt").write_text(
        "".join(f"probe PYTHONHASHSEED={seed} sha256={d}\n" for seed, d in digests.items())
        + f"byte-identical: {deterministic}\n", encoding="utf-8")

print(json.dumps({k: summary[k] for k in ("cases", "chains", "order_groups", "rows", "deterministic", "problems")},
                 indent=1, default=str))
for problem in problems[:40]:
    print(problem)
print("AUDIT:", "PASS" if not problems else "FAIL", f"({len(rows)} linhas)")
sys.exit(1 if problems else 0)
