"""
Etapa 3.3B — auditoria independente da propagação causal de estado e da
identidade temporal (fechamento: D33B-01..04).

    python audit/stage3_3b_state_propagation/evidence/analysis_stage3_3b.py [--no-write]

Não importa nada de app/ nem de tools/ e não replica a implementação.
As expectativas vêm de:

    * seeds (`data/seed/*/equations.json`, `variables.json`,
      `aggregation_rules.json`) e do artefato canônico
      `interblock_links.json`;
    * contrato: D1 (literal é estado só para a variável alvo que o
      declara), D2/§13 (resultado com estado não tem valor), D3/§16 + R1
      (estado alcança os descendentes CAUSAIS), fechamento 3.3B:
        D33B-01  estados diferentes -> MULTI_STATE_COMBINATION_UNDEFINED
        D33B-02  mesmo estado, details diferentes -> MULTI_DETAIL_COMPOSITION_UNDEFINED
        D33B-03  detail sem state -> DETAIL_WITHOUT_STATE
        causal   só dependências EXECUTADAS (semântica de Python: a DSL
                 dos seeds é sintaxe Python — IF avalia só o ramo
                 escolhido; and/or com curto-circuito)
        D33B-04  (variável, instância, período, janela efetiva): run_dates
                 diferentes coexistem; reexecução igual é idempotente;
                 resultado diferente na mesma identidade é conflito
    * agregação (Etapa 3.3C, Policy B): o alvo compõe os estados da origem
      (antes: fronteira STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C);
    * topologia da Etapa 3.2 (`plan_evidence.csv`).

As dependências executadas são derivadas aqui com o módulo `ast` do
Python sobre o TEXTO dos seeds e com os valores OBSERVADOS das
dependências sem estado (para decidir as condições); a simulação percorre
os passos do plano na ordem observada (a topologia é validada à parte).
O runtime é observado como caixa-preta por `runtime_probe.py`.
"""

from __future__ import annotations

import ast
import csv
import itertools
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEED = REPO / "data" / "seed"
WRITE = "--no-write" not in sys.argv[1:]
BASELINE = "eee88d6c9045f040270bc0d7c99d958485db9fff"  # HEAD antes de toda a Etapa 3.3B
RUN_DATE = "2026-09-01"
DAYS = ["2026-09-01", "2026-09-02", "2026-09-03"]
PERIOD = {"diário": "2026-09-01", "mensal": "2026-09", "anual": "2026"}
LINES = [f"L{i}" for i in range(1, 8)]
STATES = {"NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"}  # contrato D2
NAR, INVALID, VFAIL = "NO_APPLICABLE_RULE", "INVALID_INPUT", "VALIDATION_FAILED"
MATH_LIKE = {"ValueError", "ArithmeticError", "ZeroDivisionError", "LookupError", "KeyError",
             "VariableNotFoundError", "EvaluationError"}

counters = Counter()
problems: list[str] = []
evidence_rows: list[dict] = []


def fail(counter, message):
    counters[counter] += 1
    problems.append(f"[{counter}] {message}")


# ------------------------------------------------------------------
# seeds
# ------------------------------------------------------------------
payload = json.loads((SEED / "interblock_links.json").read_text(encoding="utf-8"))
BLOCKS = list(payload["workbooks"])
variables, equations, rules = {}, [], []
for block in BLOCKS:
    for v in json.loads((SEED / block / "variables.json").read_text(encoding="utf-8")):
        variables[v["variable_id"]] = v
    equations += json.loads((SEED / block / "equations.json").read_text(encoding="utf-8"))
    path = SEED / block / "aggregation_rules.json"
    if path.exists():
        rules += json.loads(path.read_text(encoding="utf-8"))
equation_by_id = {e["equation_id"]: e for e in equations}
links = payload["links"]
link_by_consumer = {l["consumer_definition"]: l for l in links}
eq_targets = {e["target_variable_id"] for e in equations}
computed_vars = eq_targets | set(link_by_consumer) | {r["target_variable_id"] for r in rules}


def expand(scope_type, scope_value):
    if scope_type == "linha" and "_" in str(scope_value):
        a, b = scope_value.split("_")
        return [(scope_type, l) for l in LINES[LINES.index(a): LINES.index(b) + 1]]
    return [(scope_type, scope_value)]


REF = re.compile(r"\b(VAR\d+)(?:@(L\d(?:_L\d)?))?")
PYREF = re.compile(r"^(VAR\d+)(?:__(L\d(?:_L\d)?))?$")


def resolve(ref, at, inst):
    """Instância referenciada (mesma regra textual: @escopo explícito,
    senão a instância da equação, senão a única instância da variável)."""
    if at:
        return (ref, "linha" if re.fullmatch(r"L\d", at) else "linha_grupo", at)
    own = expand(variables[ref]["scope_type"], variables[ref]["scope_value"])
    if inst in own:
        return (ref, *inst)
    if len(own) == 1:
        return (ref, *own[0])
    return None


# ------------------------------------------------------------------
# 1. evidência do literal "F" (D1 + R1)
# ------------------------------------------------------------------
declared = {vid: {d["literal"]: d["state"] for d in v.get("declared_result_states") or []}
            for vid, v in variables.items() if v.get("declared_result_states")}
literal_equations = []
for e in equations:
    for literal in sorted(set(re.findall(r'"([^"]*)"', e["expression"]))):
        target = e["target_variable_id"]
        if any(literal in (variables.get(ref, {}).get("allowed_values") or [])
               for ref, _ in REF.findall(e["expression"])):
            continue
        literal_equations.append((e["equation_id"], target, literal, declared.get(target, {}).get(literal)))
for eid, target, literal, state in literal_equations:
    if state is None:
        fail("mapeamento F", f"{eid}: literal {literal!r} sem declaração em {target} (STATE_LITERAL_MAPPING_UNRESOLVED)")
    elif state not in STATES:
        fail("mapeamento F", f"{eid}: estado {state} fora da taxonomia")
mapping_proven = bool(literal_equations) and all(s in STATES for *_x, s in literal_equations)


# ------------------------------------------------------------------
# 2. dependências executadas (ast do Python sobre o texto do seed)
# ------------------------------------------------------------------
def python_tree(expression):
    return ast.parse(REF.sub(lambda m: m.group(1) + (f"__{m.group(2)}" if m.group(2) else ""), expression),
                     mode="eval").body


NAMES = {"ln": math.log}


class Undecidable(Exception):
    pass


def executed(node, inst, stated, observed):
    """
    Referências executadas por `node`, na ordem de Python. Uma referência
    com estado lida numa condição torna a decisão impossível: nada além
    dela é executado (Undecidable carrega o que foi executado até ali).
    """
    if isinstance(node, ast.Name):
        m = PYREF.match(node.id)
        if not m:
            return []
        key = resolve(m.group(1), m.group(2), inst)
        return [key] if key else []
    if isinstance(node, ast.IfExp):
        cond = executed(node.test, inst, stated, observed)
        if any(k in stated for k in cond):
            raise Undecidable(cond)
        branch = node.body if evaluate(node.test, inst, observed) else node.orelse
        return cond + executed(branch, inst, stated, observed)
    if isinstance(node, ast.BoolOp):
        done = []
        for operand in node.values:
            refs = executed(operand, inst, stated, observed)
            done += refs
            if any(k in stated for k in refs):
                raise Undecidable(done)
            truth = bool(evaluate(operand, inst, observed))
            if isinstance(node.op, ast.And) and not truth or isinstance(node.op, ast.Or) and truth:
                break
        return done
    if isinstance(node, ast.Compare):
        done = executed(node.left, inst, stated, observed)
        for comparator in node.comparators:
            done += executed(comparator, inst, stated, observed)
            if any(k in stated for k in done):
                raise Undecidable(done)
        return done
    refs = []
    for child in ast.iter_child_nodes(node):
        refs += executed(child, inst, stated, observed)
    return refs


def evaluate(node, inst, observed):
    names = dict(NAMES)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and PYREF.match(sub.id):
            m = PYREF.match(sub.id)
            names[sub.id] = observed[resolve(m.group(1), m.group(2), inst)]
    return eval(compile(ast.Expression(node), "<seed>", "eval"), {"__builtins__": {}}, names)  # noqa: S307


def simulate(steps, overrides, observed):
    """
    Estados esperados por nó (variável, scope_type, scope_value) seguindo os
    passos do plano. Devolve (código esperado, {nó: set((state, detail))}, nós
    executados, arestas causais usadas).
    """
    stated = {}
    for var, st, sv, _period, _value, state, detail in overrides:
        if state is not None:
            stated[(var, st, sv)] = {(state, detail)}
    done, used = set(), []
    for key in steps:
        kind, node_id = key.split(":", 1)
        if kind == "EQUATION":
            e = equation_by_id[node_id]
            tree = python_tree(e["expression"])
            for inst in expand(e["scope_type"], e["scope_value"]):
                node = (e["target_variable_id"], *inst)
                try:
                    refs = executed(tree, inst, stated, observed)
                except Undecidable as partial:
                    refs = partial.args[0]
                incoming = set().union(*[stated[r] for r in refs if r in stated])
                used.append((node, sorted({r for r in refs if r in stated})))
                done.add(node)
                if incoming:
                    if len({s for s, _d in incoming}) > 1:
                        return "MULTI_STATE_COMBINATION_UNDEFINED", stated, done, used
                    if len(incoming) > 1:
                        return "MULTI_DETAIL_COMPOSITION_UNDEFINED", stated, done, used
                    stated[node] = incoming
                elif e["target_variable_id"] in declared:
                    value = evaluate(tree, inst, observed)
                    if isinstance(value, str) and value in declared[e["target_variable_id"]]:
                        stated[node] = {(declared[e["target_variable_id"]][value], None)}
        elif kind == "TRANSFER":
            l = link_by_consumer[node_id]
            for i in l["instances"]:
                source = (l["source_definition"], i["scope_type"], i["scope_value"])
                node = (node_id, i["scope_type"], i["scope_value"])
                done.add(node)
                if source in stated:
                    stated[node] = stated[source]
        elif kind == "AGGREGATION":
            # LEGACY_TEST_EXPECTATION (Etapa 3.3C): a fronteira
            # STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C foi substituída pela
            # Policy B — o alvo de cada instância compõe os estados das
            # instâncias de origem da janela (aqui um único dia): estados
            # diferentes / details diferentes são erro, senão propaga.
            rule = next(r for r in rules if r["aggregation_rule_id"] == node_id)
            source_var = variables[rule["source_variable_id"]]
            for inst in expand(source_var["scope_type"], source_var["scope_value"]):
                node = (rule["target_variable_id"], *inst)
                done.add(node)
                incoming = stated.get((rule["source_variable_id"], *inst), set())
                if len({st for st, _d in incoming}) > 1:
                    return "MULTI_STATE_COMBINATION_UNDEFINED", stated, done, used
                if len(incoming) > 1:
                    return "MULTI_DETAIL_COMPOSITION_UNDEFINED", stated, done, used
                if incoming:
                    stated[node] = incoming
    return None, stated, done, used


# ------------------------------------------------------------------
# 3. cenários de estado (uma data)
# ------------------------------------------------------------------
f_equation = equation_by_id["EQ16011"]
hes = "VAR16021"
options = variables[hes]["allowed_values"]
f_tree = python_tree(f_equation["expression"])


def eval_hes(pair):
    names = dict(NAMES, **{n.id: 1.0 for n in ast.walk(f_tree) if isinstance(n, ast.Name) and PYREF.match(n.id)})
    names.update({f"{hes}__L4": pair[0], f"{hes}__L5": pair[1]})
    return eval(compile(ast.Expression(f_tree), "<seed>", "eval"), {"__builtins__": {}}, names)  # noqa: S307


pairs = list(itertools.product(options, options))
f_pair = next(p for p in pairs if eval_hes(p) == "F")
control_pair = next(p for p in pairs if eval_hes(p) != "F")
cat = lambda pair: {f"{hes}@L4": pair[0], f"{hes}@L5": pair[1]}  # noqa: E731

# IF causal real: a entrada lida em UM ÚNICO ramo de EQ16011
def if_chain(node):
    """Cadeia a if c0 else b if c1 else ... -> [(teste, ramo), ..., (None, último)]."""
    chain = []
    while isinstance(node, ast.IfExp):
        chain.append((node.test, node.body))
        node = node.orelse
    return chain + [(None, node)]


chain = if_chain(f_tree)
branch_refs = {i: {n.id for n in ast.walk(branch) if isinstance(n, ast.Name) and PYREF.match(n.id)}
               for i, (_test, branch) in enumerate(chain)}


def branch_taken(pair):
    names = {f"{hes}__L4": pair[0], f"{hes}__L5": pair[1]}
    for i, (test, _branch) in enumerate(chain):
        if test is None or eval(compile(ast.Expression(test), "<seed>", "eval"), {"__builtins__": {}}, names):  # noqa: S307
            return i


only_one_branch = sorted(
    ref for ref in set().union(*branch_refs.values())
    if sum(ref in refs for refs in branch_refs.values()) == 1
    and PYREF.match(ref).group(1) not in computed_vars
)
if_ref = only_one_branch[0]
if_var = PYREF.match(if_ref).group(1)
if_branch = next(i for i, refs in branch_refs.items() if if_ref in refs)
active_pair = next(p for p in pairs if branch_taken(p) == if_branch)
if branch_taken(control_pair) == if_branch:
    fail("IF causal", "par de controle executa o ramo da variável escolhida")
if_scope = variables[if_var]


def override(var, st, sv, state, detail=None, value=None):
    return [var, st, sv, PERIOD[variables[var]["frequency"]], value, state, detail]


def first_input_ancestor(variable):
    frontier, seen = [variable], set()
    while frontier:
        current = frontier.pop(0)
        for e in sorted((x for x in equations if x["target_variable_id"] == current), key=lambda x: x["equation_id"]):
            for ref, _ in REF.findall(e["expression"]):
                if ref not in variables or ref in seen:
                    continue
                seen.add(ref)
                if ref not in computed_vars and variables[ref].get("value_type") != "categorico":
                    return ref
                if ref in eq_targets:
                    frontier.append(ref)
    return None


agg_rule = next(r for r in rules if r["target_variable_id"] == "VAR12002")
agg_input = first_input_ancestor(agg_rule["source_variable_id"])
agg_overrides = [override(agg_input, st, sv, VFAIL)
                 for st, sv in expand(variables[agg_input]["scope_type"], variables[agg_input]["scope_value"])]
if_override = override(if_var, if_scope["scope_type"], if_scope["scope_value"], INVALID, "ramo")

SCENARIOS = {
    "S1_A41_F": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=cat(f_pair),
                     overrides=[], scalar_reads=[["VAR16025", "linha_grupo", "L4_L5", PERIOD["diário"]]]),
    "S2_A41_CONTROL": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=cat(control_pair),
                           overrides=[]),
    "S3_LTH_META": dict(mode="derived", targets=["VAR16008", "VAR13039"], categorical={},
                        overrides=[override("VAR12066", "linha", "L2", INVALID, "meta")]),
    "S4_MULTI_STATE": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=cat(f_pair),
                           overrides=[override("VAR16017", "linha", "L1", INVALID)]),
    "S5_MULTI_DETAIL": dict(mode="derived", targets=["VAR16008"], categorical={},
                            overrides=[override("VAR12066", "linha", "L1", INVALID, "a"),
                                       override("VAR12066", "linha", "L2", INVALID, "b")]),
    "S6_SAME_DETAIL": dict(mode="derived", targets=["VAR16008"], categorical={},
                           overrides=[override("VAR12066", "linha", "L1", INVALID, "igual"),
                                      override("VAR12066", "linha", "L2", INVALID, "igual")]),
    "S7_AGGREGATION_3_3C": dict(mode="derived", targets=["VAR12002"], categorical={}, overrides=agg_overrides),
    "S8_OFFICIAL_ENERGY": dict(mode="official", targets=["VAR18011"], categorical={},
                               overrides=[override("VAR12066", "linha", "L3", VFAIL)]),
    "S9_IF_INACTIVE_BRANCH": dict(mode="derived", targets=["VAR16031", "VAR16034"],
                                  categorical=cat(control_pair), overrides=[if_override]),
    "S10_IF_ACTIVE_BRANCH": dict(mode="derived", targets=["VAR16031", "VAR16034"],
                                 categorical=cat(active_pair), overrides=[if_override]),
    "S11_IF_TWO_STATES_ONE_BRANCH": dict(mode="derived", targets=["VAR16031", "VAR16034"],
                                         categorical=cat(control_pair),
                                         overrides=[if_override,
                                                    override("VAR16017", "linha", "L1", VFAIL)]),
}

# ------------------------------------------------------------------
# 4. cenários temporais (várias datas no MESMO contexto)
# ------------------------------------------------------------------
monthly_link = next(l for l in sorted(links, key=lambda x: x["consumer_definition"])
                    if l["consumer_frequency"] == "mensal"
                    and l["source_definition"] in {r["target_variable_id"] for r in rules}
                    and len(l["instances"]) == 1 and l["consumer_definition"] == "VAR18010")
annual_link = next(l for l in links if l["consumer_frequency"] == "anual")
TEMPORAL_TARGETS = [monthly_link["consumer_definition"], "VAR16008", annual_link["consumer_definition"]]
ORDER_TARGETS = ["VAR16008", annual_link["consumer_definition"]]   # sem janela mensal (exige dias anteriores)
conflict_override = [override("VAR12066", "linha", "L1", None, None, 999.0)]

SEQUENCES = {
    "T1_FORWARD": dict(targets=TEMPORAL_TARGETS, steps=[{"run_date": d} for d in DAYS]),
    "T2_RERUN_P1": dict(targets=TEMPORAL_TARGETS, steps=[{"run_date": d} for d in (DAYS[0], DAYS[1], DAYS[0])]),
    "T2_REFERENCE": dict(targets=TEMPORAL_TARGETS, steps=[{"run_date": d} for d in DAYS[:2]]),
    "T3_ORDER_FORWARD": dict(targets=ORDER_TARGETS, steps=[{"run_date": d} for d in DAYS]),
    "T3_ORDER_SHUFFLED": dict(targets=ORDER_TARGETS, steps=[{"run_date": d} for d in (DAYS[2], DAYS[0], DAYS[1])]),
    "T4_CONFLICT": dict(targets=ORDER_TARGETS, steps=[{"run_date": DAYS[0]},
                                                       {"run_date": DAYS[0], "overrides": conflict_override}]),
}

plan_evidence = list(csv.DictReader(
    (REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv").open(encoding="utf-8")))

commands = [{"kind": "run", "id": sid, "run_date": RUN_DATE, **spec} for sid, spec in SCENARIOS.items()]
commands += [{"kind": "sequence", "id": sid, "mode": "derived", **spec} for sid, spec in SEQUENCES.items()]
commands.append({"kind": "construct", "id": "D33B03_DETAIL_WITHOUT_STATE", "args": [1.0, None, "texto"]})
commands.append({"kind": "construct", "id": "D33B03_STATE_WITH_DETAIL", "args": [None, INVALID, "texto"]})
commands.append({"kind": "construct", "id": "D33B03_STATE_ONLY", "args": [None, INVALID, None]})
commands.append({"kind": "plans", "id": "PLANS", "targets": [r["target"] for r in plan_evidence]})


def probe(seed):
    completed = subprocess.run(
        [sys.executable, str(HERE / "runtime_probe.py")], input=json.dumps(commands),
        capture_output=True, text=True, cwd=REPO, env={**os.environ, "PYTHONHASHSEED": seed},
    )
    if completed.returncode != 0:
        fail("divergências", f"sonda falhou: {completed.stderr[-1500:]}")
        return {}, ""
    return json.loads(completed.stdout), completed.stdout


observed_all, raw_a = probe("0")
_again, raw_b = probe("4242")
deterministic = raw_a == raw_b and raw_a != ""
if not deterministic:
    fail("determinismo", "saída da sonda difere entre PYTHONHASHSEED 0 e 4242")


# ------------------------------------------------------------------
# 5. estados: expectativa x observado
# ------------------------------------------------------------------
summary_scenarios = {}
for sid, spec in SCENARIOS.items():
    got = observed_all.get(sid)
    if got is None:
        fail("divergências", f"{sid}: sem observação")
        continue
    context = {(r[0], r[1], r[2]): (r[5], r[6], r[7]) for r in got["context"]}
    values = {k: v[0] for k, v in context.items()}
    want_code, stated, done, used = simulate(got["steps"], spec["overrides"], values)
    if got["code"] != want_code:
        fail("códigos", f"{sid}: código {got['code']} != {want_code}")
    if got["code"] and MATH_LIKE & set(got.get("error_bases", [])):
        fail("erros mascarados", f"{sid}: {got['code']} herda de {got['error_bases']}")
    overrides = {(o[0], o[1], o[2]) for o in spec["overrides"]}
    counted = Counter()
    for node in sorted(done):
        if node not in context:
            if want_code is None:
                fail("divergências", f"{sid}: {node} não gravado")
            continue
        value, state, detail = context[node]
        sds = stated.get(node, set())
        if len(sds) == 1:
            (want_state, want_detail), = sds
            ok = (value, state, detail) == (None, want_state, want_detail)
            counted["herdado"] += 1
            if not ok:
                fail("propagação", f"{sid}: {node} = {(value, state, detail)} != {(None, want_state, want_detail)}")
        else:
            ok = state is None and detail is None and value is not None
            counted["isolado"] += 1
            if not ok:
                fail("isolamento", f"{sid}: {node} fora do fecho causal recebeu {(value, state, detail)}")
        if value == "F":
            fail("literal F", f"{sid}: {node} gravou 'F' bruto")
        evidence_rows.append({
            "scenario": sid, "variable": node[0], "instance": f"{node[1]}/{node[2]}",
            "expected_state": "|".join(sorted(f"{s}:{d}" for s, d in sds)),
            "received_value": value, "received_state": state or "", "received_detail": detail or "",
            "result": "OK" if ok else "DIVERGENT",
        })
    for node, (_v, state, _d) in context.items():
        if state is not None and node not in stated and node not in overrides:
            fail("isolamento", f"{sid}: estado espúrio em {node}")
    for read in got.get("scalar_reads", []):
        if read != ["ERR", "STATEFUL_RESULT_ON_SCALAR_API"]:
            fail("API escalar", f"{sid}: leitura escalar de estado devolveu {read}")
    summary_scenarios[sid] = {"code": got["code"], "expected_code": want_code, "steps": len(got["steps"]),
                              **counted}

# prova de que S9/S10/S11 exercitam de fato o ramo (inativo x ativo)
s9 = observed_all.get("S9_IF_INACTIVE_BRANCH", {}).get("context", [])
s10 = observed_all.get("S10_IF_ACTIVE_BRANCH", {}).get("context", [])
producer_s9 = next((r for r in s9 if r[0] == "VAR16025"), None)
producer_s10 = next((r for r in s10 if r[0] == "VAR16025"), None)
if not producer_s9 or producer_s9[6] is not None:
    fail("IF causal", f"ramo inativo propagou estado: {producer_s9}")
if not producer_s10 or producer_s10[6] != INVALID:
    fail("IF causal", f"ramo ativo não propagou estado: {producer_s10}")


# ------------------------------------------------------------------
# 6. D33B-03
# ------------------------------------------------------------------
construct_expect = {
    "D33B03_DETAIL_WITHOUT_STATE": (["ERR", "DETAIL_WITHOUT_STATE"], ["ERR", "DETAIL_WITHOUT_STATE"], 0),
    "D33B03_STATE_WITH_DETAIL": (["OK", [None, INVALID, "texto"]], ["OK"], 1),
    "D33B03_STATE_ONLY": (["OK", [None, INVALID, None]], ["OK"], 1),
}
for cid, (want_construct, want_write, stored) in construct_expect.items():
    got = observed_all.get(cid, {})
    if got.get("construct") != want_construct or got.get("write") != want_write or len(got.get("context", [])) != stored:
        fail("detail sem state", f"{cid}: {got}")


# ------------------------------------------------------------------
# 7. identidade temporal (D33B-04)
# ------------------------------------------------------------------
def by_identity(dump):
    return {(r[0], r[1], r[2], r[3], r[4]): (r[5], r[6], r[7]) for r in dump}


def producer_result(store, link, st, sv, period, window):
    source = link["source_definition"]
    return store.get((source, st, sv, period, window), store.get((source, st, sv, period, None)))


def check_transfers(sid, store, days):
    for consumer, link in link_by_consumer.items():
        keys = [k for k in store if k[0] == consumer]
        if not keys:
            continue
        frequency = link["consumer_frequency"]
        for key in keys:
            _c, st, sv, period, window = key
            want = producer_result(store, link, st, sv, period, window)
            if want != store[key]:
                fail("identidade temporal", f"{sid}: {key} = {store[key]} != produtor {want}")
            if frequency == "diário" and (window is not None or period not in days):
                fail("identidade temporal", f"{sid}: diário com janela/período inesperado {key}")
            evidence_rows.append({
                "scenario": sid, "variable": consumer, "instance": f"{st}/{sv}",
                "expected_state": f"period={period} window={window}", "received_value": store[key][0],
                "received_state": store[key][1] or "", "received_detail": store[key][2] or "",
                "result": "OK" if want == store[key] else "DIVERGENT",
            })
        if frequency != "diário":
            windows = {k[4] for k in keys}
            if windows != set(days):
                fail("identidade temporal", f"{sid}: {consumer} janelas {sorted(map(str, windows))} != {days}")
        else:
            if {k[3] for k in keys} != set(days):
                fail("identidade temporal", f"{sid}: {consumer} períodos {sorted({k[3] for k in keys})} != {days}")


temporal_summary = {}
for sid, spec in SEQUENCES.items():
    got = observed_all.get(sid)
    if got is None:
        fail("divergências", f"{sid}: sem observação")
        continue
    temporal_summary[sid] = [run["code"] for run in got["runs"]]
    if sid == "T4_CONFLICT":
        continue
    if any(run["code"] for run in got["runs"]):
        fail("identidade temporal", f"{sid}: erro inesperado {[run['code'] for run in got['runs']]} (D32-02?)")
        continue
    check_transfers(sid, by_identity(got["context"]), sorted({s["run_date"] for s in spec["steps"]}))

t1 = observed_all.get("T1_FORWARD")
if t1:
    monthly = [v for k, v in by_identity(t1["context"]).items() if k[0] == monthly_link["consumer_definition"]]
    if len({v[0] for v in monthly}) < 2:
        fail("identidade temporal", f"janelas mensais sem valores distintos: {monthly}")
rerun, reference = observed_all.get("T2_RERUN_P1"), observed_all.get("T2_REFERENCE")
if rerun and reference:
    if by_identity(rerun["context"]) != by_identity(reference["context"]):
        fail("idempotência", "P1 -> P2 -> P1 alterou o contexto em relação a P1 -> P2")
    statuses = {t[4] for t in rerun["runs"][2]["transfers"]}
    if statuses != {"UNCHANGED"}:
        fail("idempotência", f"reexecução de P1: transferências {statuses}")
forward, shuffled = observed_all.get("T3_ORDER_FORWARD"), observed_all.get("T3_ORDER_SHUFFLED")
if forward and shuffled and by_identity(forward["context"]) != by_identity(shuffled["context"]):
    fail("ordem de períodos", "P3 -> P1 -> P2 difere de P1 -> P2 -> P3")
conflict = observed_all.get("T4_CONFLICT")
if conflict:
    codes = [run["code"] for run in conflict["runs"]]
    if codes != [None, "INTERBLOCK_CONSUMER_VALUE_CONFLICT"]:
        fail("sobrescrita", f"conflito real na mesma identidade: {codes}")
    store = by_identity(conflict["context"])
    consumer = [k for k in store if k[0] == "VAR11031" and k[2] == "L1"]
    producer_now = store.get(("VAR12031", "linha", "L1", DAYS[0], None))
    if not consumer or store[consumer[0]] == producer_now:
        fail("sobrescrita", f"consumidor sobrescrito em silêncio: {[store[k] for k in consumer]} / {producer_now}")

# topologia (3.2) preservada
official_plans = observed_all.get("PLANS", {})
for row in plan_evidence:
    got = official_plans.get(row["target"])
    if got is None or got[0] != row["observed"] or (got[0] == "OK" and str(len(got[1])) != row["steps"]):
        fail("topologia", f"{row['target']}: {got} != 3.2 {row['observed']}/{row['steps']}")


# ------------------------------------------------------------------
# 8. verificações estáticas (texto/AST, sem importar)
# ------------------------------------------------------------------
f_holders = sorted(
    str(p.relative_to(REPO)) for p in (REPO / "app").rglob("*.py")
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
    if isinstance(n, ast.Constant) and n.value == "F"
)
if f_holders != ["app/domain/values.py"]:
    fail("literal F", f"constante 'F' espalhada em {f_holders}")
values_src = (REPO / "app/domain/values.py").read_text(encoding="utf-8")
for forbidden in ("BLOCKED_BY_UPSTREAM_ERROR", "TECHNICAL_ERROR", '"OK"'):
    if forbidden in values_src:
        fail("estados inventados", f"{forbidden} na taxonomia")
propagation_src = (REPO / "app/domain/state_propagation.py").read_text(encoding="utf-8")
imports = {n.module for n in ast.walk(ast.parse(propagation_src)) if isinstance(n, ast.ImportFrom)}
if not imports <= {"__future__", "app.domain.results"}:
    fail("centralização", f"state_propagation importa {imports}")
git = subprocess.run(["git", "diff", "--name-only", BASELINE, "HEAD"], capture_output=True, text=True, cwd=REPO)
changed = git.stdout.split() if git.returncode == 0 else []
protected = ("data/", "tools/", "app/domain/interblock/", "app/domain/values.py",
             "app/engine/temporal_aggregation_service.py", "app/engine/time_period_resolver.py")
touched = [p for p in changed if p.startswith(protected)]
if touched:
    fail("artefatos protegidos", f"alterados desde {BASELINE[:7]}: {touched}")


# ------------------------------------------------------------------
# 9. saída
# ------------------------------------------------------------------
summary = {
    "baseline": BASELINE,
    "literal_mapping": {
        "equations_with_state_literal": [list(x) for x in literal_equations],
        "declared_result_states": declared,
        "mapping_proven_per_variable": mapping_proven,
    },
    "f_pair": f_pair, "control_pair": control_pair,
    "if_causal": {"variable": if_var, "branch_index": if_branch, "active_pair": active_pair},
    "aggregation_scenario": {"rule": agg_rule["aggregation_rule_id"], "stated_input": agg_input},
    "temporal": {"targets": TEMPORAL_TARGETS, "order_targets": ORDER_TARGETS, "runs": temporal_summary},
    "scenarios": summary_scenarios,
    "evidence_rows": len(evidence_rows),
    "static": {"f_constant_holders": f_holders, "propagation_imports": sorted(imports),
               "changed_since_baseline": changed, "protected_touched": touched},
    "deterministic": deterministic,
    "problems": dict(counters),
}

if WRITE:
    (HERE / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    with (HERE / "propagation_evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    (HERE / "determinism_check.txt").write_text(
        f"probe PYTHONHASHSEED=0 sha-equal PYTHONHASHSEED=4242: {deterministic}\n"
        f"bytes: {len(raw_a)}\n", encoding="utf-8")

print(json.dumps({k: summary[k] for k in ("scenarios", "temporal", "deterministic", "problems")},
                 ensure_ascii=False, indent=1, default=str))
for problem in problems:
    print(problem)
print("AUDIT:", "PASS" if not problems else "FAIL", f"({len(evidence_rows)} linhas de evidência)")
sys.exit(1 if problems else 0)
