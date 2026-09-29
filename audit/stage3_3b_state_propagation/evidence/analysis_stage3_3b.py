"""
Etapa 3.3B — auditoria independente da propagação causal de estado.

    python audit/stage3_3b_state_propagation/evidence/analysis_stage3_3b.py [--no-write]

Não importa nada de app/ nem de tools/ e não replica a política
implementada. As expectativas vêm de:

    * seeds (`data/seed/*/equations.json`, `variables.json`,
      `aggregation_rules.json`) e do artefato canônico
      `interblock_links.json`;
    * contrato documentado: D1 (literal é estado só para a variável alvo
      que o declara em `declared_result_states`), D2/§13 (resultado com
      estado não tem valor), D3/§16 + R1 (o estado alcança exatamente os
      descendentes pelo grafo de dependências; o resto não é afetado);
    * decisões registradas como NÃO definidas pelo contrato (estados
      diferentes, details diferentes numa mesma equação) -> erro
      explícito, nunca uma escolha;
    * fronteira da 3.3C (agregação sobre estado) -> erro explícito;
    * topologia da Etapa 3.2 (`plan_evidence.csv`).

O grafo de dependências é reconstruído aqui a partir do TEXTO das
expressões (referências VARnnnnn[@escopo]); o ramo "F" de EQ16011 é
decidido avaliando a expressão do seed com a semântica do próprio
Python (a sintaxe dos seeds é Python), não com o evaluator do app.
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
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEED = REPO / "data" / "seed"
WRITE = "--no-write" not in sys.argv[1:]
BASELINE = "eee88d6c9045f040270bc0d7c99d958485db9fff"  # HEAD real no início da 3.3B
RUN_DATE = "2026-09-01"
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
    for e in json.loads((SEED / block / "equations.json").read_text(encoding="utf-8")):
        equations.append(e)
    path = SEED / block / "aggregation_rules.json"
    if path.exists():
        rules += json.loads(path.read_text(encoding="utf-8"))
links = payload["links"]
eq_targets = {e["target_variable_id"] for e in equations}
consumers = {l["consumer_definition"] for l in links}
computed_vars = eq_targets | consumers | {r["target_variable_id"] for r in rules}


def expand(scope_type, scope_value):
    if scope_type == "linha" and "_" in str(scope_value):
        a, b = scope_value.split("_")
        return [(scope_type, l) for l in LINES[LINES.index(a): LINES.index(b) + 1]]
    return [(scope_type, scope_value)]


REF = re.compile(r"\b(VAR\d+)(?:@(L\d(?:_L\d)?))?")


# ------------------------------------------------------------------
# 1. evidência do literal "F" (D1 + R1)
# ------------------------------------------------------------------
declared = {vid: {d["literal"]: d["state"] for d in v.get("declared_result_states") or []}
            for vid, v in variables.items() if v.get("declared_result_states")}
literal_equations = []
for e in equations:
    for literal in sorted(set(re.findall(r'"([^"]*)"', e["expression"]))):
        target = e["target_variable_id"]
        is_categorical_comparison = any(
            literal in (variables.get(ref, {}).get("allowed_values") or [])
            for ref, _ in REF.findall(e["expression"])
        )
        if is_categorical_comparison:
            continue
        literal_equations.append((e["equation_id"], target, literal, declared.get(target, {}).get(literal)))
for eid, target, literal, state in literal_equations:
    if state is None:
        fail("mapeamento F", f"{eid}: literal {literal!r} sem declaração em {target} (STATE_LITERAL_MAPPING_UNRESOLVED)")
    elif state not in STATES:
        fail("mapeamento F", f"{eid}: estado {state} fora da taxonomia")
mapping_proven = bool(literal_equations) and all(s in STATES for *_x, s in literal_equations)


# ------------------------------------------------------------------
# 2. grafo de instâncias (texto das expressões + vínculos)
# ------------------------------------------------------------------
edges = defaultdict(set)          # dependência -> dependente
unresolved = []                   # (equação, instância, referência)
for e in equations:
    for inst in expand(e["scope_type"], e["scope_value"]):
        node = (e["target_variable_id"], *inst)
        for ref, at in REF.findall(e["expression"]):
            if ref not in variables:
                continue
            if at:
                dep = (ref, "linha" if re.fullmatch(r"L\d", at) else "linha_grupo", at)
            else:
                v = variables[ref]
                own = expand(v["scope_type"], v["scope_value"])
                dep = (ref, *inst) if inst in own else None
                if dep is None and len(own) == 1:
                    dep = (ref, *own[0])
            if dep is None:
                unresolved.append((e["equation_id"], inst, ref))
            else:
                edges[dep].add(node)
for l in links:
    for i in l["instances"]:
        edges[(l["source_definition"], i["scope_type"], i["scope_value"])].add(
            (l["consumer_definition"], i["scope_type"], i["scope_value"]))


def reach(origins):
    """origins: {nó: (state, detail)} -> {nó: set((state, detail))}."""
    reached = defaultdict(set)
    stack = list(origins.items())
    while stack:
        node, sd = stack.pop()
        if sd in reached[node]:
            continue
        reached[node].add(sd)
        for child in edges.get(node, ()):
            stack.append((child, sd))
    return reached


# ------------------------------------------------------------------
# 3. decidir o ramo "F" de EQ16011 com a semântica do Python
# ------------------------------------------------------------------
def eval_seed(expression, categorical):
    names = {"ln": math.log, "exp": math.exp, "sqrt": math.sqrt, "abs": abs, "min": min, "max": max}

    def repl(match):
        ref, at = match.group(1), match.group(2)
        v = variables[ref]
        if v.get("value_type") == "categorico":
            return repr(categorical[f"{ref}@{at}"])
        return "1.0"

    return eval(REF.sub(repl, expression), {"__builtins__": {}}, names)  # noqa: S307


f_equation = next(e for e in equations if e["equation_id"] == "EQ16011")
hes = "VAR16021"
options = variables[hes]["allowed_values"]
f_choice = control_choice = None
for a, b in itertools.product(options, options):
    cat = {f"{hes}@L4": a, f"{hes}@L5": b, f"{hes}@L6": options[0], f"{hes}@L7": options[0]}
    result = eval_seed(f_equation["expression"], cat)
    if result == "F" and f_choice is None:
        f_choice = cat
    if result != "F" and control_choice is None:
        control_choice = cat
if f_choice is None or control_choice is None:
    fail("mapeamento F", "não foi possível escolher estados de hes para o ramo F / controle")


def declared_origins(categorical):
    """Instâncias cujo seed produz um literal declarado pela variável alvo."""
    found = {}
    for e in equations:
        target = e["target_variable_id"]
        if target not in declared:
            continue
        for inst in expand(e["scope_type"], e["scope_value"]):
            value = eval_seed(e["expression"], {**{f"{hes}@{l}": options[0] for l in LINES[3:]}, **categorical})
            if isinstance(value, str) and value in declared[target]:
                found[(target, *inst)] = (declared[target][value], None)
    return found


# ------------------------------------------------------------------
# 4. cenários
# ------------------------------------------------------------------
def override(var, st, sv, state, detail=None):
    return [var, st, sv, PERIOD[variables[var]["frequency"]], None, state, detail]


agg_rule = next(r for r in rules if r["target_variable_id"] == "VAR12002")


def first_input_ancestor(variable):
    """Primeira entrada (não calculada, não consumidora) na cadeia de equações."""
    frontier, seen = [variable], set()
    while frontier:
        current = frontier.pop(0)
        for e in sorted((x for x in equations if x["target_variable_id"] == current),
                        key=lambda x: x["equation_id"]):
            for ref, _ in REF.findall(e["expression"]):
                if ref not in variables or ref in seen:
                    continue
                seen.add(ref)
                if ref not in computed_vars and variables[ref].get("value_type") != "categorico":
                    return ref
                if ref in eq_targets:
                    frontier.append(ref)
    return None


agg_input = first_input_ancestor(agg_rule["source_variable_id"])
agg_overrides = [override(agg_input, st, sv, VFAIL)
                 for st, sv in expand(variables[agg_input]["scope_type"], variables[agg_input]["scope_value"])]

SCENARIOS = {
    "S1_A41_F": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=f_choice,
                     overrides=[], scalar_reads=[["VAR16025", "linha_grupo", "L4_L5", PERIOD["diário"]]]),
    "S2_A41_CONTROL": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=control_choice,
                           overrides=[]),
    "S3_LTH_META": dict(mode="derived", targets=["VAR16008", "VAR13039"], categorical={},
                        overrides=[override("VAR12066", "linha", "L2", INVALID, "meta")]),
    "S4_MULTI_STATE": dict(mode="derived", targets=["VAR16031", "VAR16034"], categorical=f_choice,
                           overrides=[override("VAR16017", "linha", "L1", INVALID)]),
    "S5_MULTI_DETAIL": dict(mode="derived", targets=["VAR16008"], categorical={},
                            overrides=[override("VAR12066", "linha", "L1", INVALID, "a"),
                                       override("VAR12066", "linha", "L2", INVALID, "b")]),
    "S6_SAME_DETAIL": dict(mode="derived", targets=["VAR16008"], categorical={},
                           overrides=[override("VAR12066", "linha", "L1", INVALID, "igual"),
                                      override("VAR12066", "linha", "L2", INVALID, "igual")]),
    "S7_AGGREGATION_3_3C": dict(mode="derived", targets=["VAR12002"], categorical={},
                                overrides=agg_overrides),
    "S8_OFFICIAL_ENERGY": dict(mode="official", targets=["VAR18011"], categorical={},
                               overrides=[override("VAR12066", "linha", "L3", VFAIL)]),
}

plan_evidence = list(csv.DictReader(
    (REPO / "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv").open(encoding="utf-8")))

commands = [{"kind": "run", "id": sid, "run_date": RUN_DATE, **spec} for sid, spec in SCENARIOS.items()]
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


observed, raw_a = probe("0")
_again, raw_b = probe("4242")
deterministic = raw_a == raw_b and raw_a != ""
if not deterministic:
    fail("determinismo", "saída da sonda difere entre PYTHONHASHSEED 0 e 4242")


# ------------------------------------------------------------------
# 5. expectativa x observado
# ------------------------------------------------------------------
def expectation(spec, steps):
    origins = {}
    for var, st, sv, _period, _value, state, detail in spec["overrides"]:
        origins[(var, st, sv)] = (state, detail)
    if spec["categorical"]:
        origins.update(declared_origins(spec["categorical"]))
    reached = reach(origins)
    stepped = set()
    for key in steps:
        kind, node = key.split(":", 1)
        if kind == "EQUATION":
            e = next(x for x in equations if x["equation_id"] == node)
            stepped |= {(e["target_variable_id"], *i) for i in expand(e["scope_type"], e["scope_value"])}
        elif kind == "TRANSFER":
            l = next(x for x in links if x["consumer_definition"] == node)
            stepped |= {(node, i["scope_type"], i["scope_value"]) for i in l["instances"]}
    code = None
    for node in sorted(stepped):
        sds = reached.get(node, set())
        if len({s for s, _d in sds}) > 1:
            code = code or "MULTI_STATE_COMBINATION_UNDEFINED"
        elif len(sds) > 1:
            code = code or "MULTI_DETAIL_COMPOSITION_UNDEFINED"
    if code is None:
        for key in steps:
            kind, node = key.split(":", 1)
            if kind == "AGGREGATION":
                source = next(r for r in rules if r["aggregation_rule_id"] == node)["source_variable_id"]
                if any(n[0] == source for n in reached):
                    code = "STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C"
    for eid, inst, ref in unresolved:
        target = next(e["target_variable_id"] for e in equations if e["equation_id"] == eid)
        if (target, *inst) in stepped and any(n[0] == ref for n in reached):
            fail("grafo", f"{eid} {inst}: referência {ref} sem instância resolvível e com estado")
    return code, reached, stepped


summary_scenarios = {}
for sid, spec in SCENARIOS.items():
    got = observed.get(sid)
    if got is None:
        fail("divergências", f"{sid}: sem observação")
        continue
    steps = got["steps"]
    want_code, reached, stepped = expectation(spec, steps)
    if got["code"] != want_code:
        fail("códigos", f"{sid}: código {got['code']} != {want_code}")
    if got["code"] and MATH_LIKE & set(got.get("error_bases", [])):
        fail("erros mascarados", f"{sid}: {got['code']} herda de {got['error_bases']}")
    context = {(r[0], r[1], r[2]): (r[4], r[5], r[6]) for r in got["context"]}
    overrides = {(o[0], o[1], o[2]) for o in spec["overrides"]}
    stated_nodes = {n for n, (_v, s, _d) in context.items() if s is not None}
    counted = Counter()
    for node in sorted(stepped):
        if node not in context:
            if want_code is None:
                fail("divergências", f"{sid}: {node} não gravado")
            continue
        value, state, detail = context[node]
        sds = reached.get(node, set())
        if len(sds) == 1:
            (want_state, want_detail), = sds
            ok = (value, state, detail) == (None, want_state, want_detail)
            counted["herdado"] += 1
            if not ok:
                fail("propagação", f"{sid}: {node} = {(value, state, detail)} != {(None, want_state, want_detail)}")
        elif len(sds) > 1:
            fail("combinação inventada", f"{sid}: {node} gravado com {(value, state, detail)} apesar de {sorted(sds, key=str)}")
            ok = False
        else:
            ok = state is None and detail is None and value is not None
            counted["isolado"] += 1
            if not ok:
                fail("isolamento", f"{sid}: {node} não alcançável recebeu {(value, state, detail)}")
        if value == "F":
            fail("literal F", f"{sid}: {node} gravou 'F' bruto")
        evidence_rows.append({
            "scenario": sid, "variable": node[0], "instance": f"{node[1]}/{node[2]}",
            "expected_state": "|".join(sorted(f"{s}:{d}" for s, d in sds)) or "",
            "received_value": value, "received_state": state or "", "received_detail": detail or "",
            "result": "OK" if ok else "DIVERGENT",
        })
    # nenhum estado fora do fecho causal (inclui entradas não sobrescritas)
    for node in stated_nodes:
        if node not in reached and node not in overrides:
            fail("isolamento", f"{sid}: estado espúrio em {node}")
    for read in got.get("scalar_reads", []):
        if read != ["ERR", "STATEFUL_RESULT_ON_SCALAR_API"]:
            fail("API escalar", f"{sid}: leitura escalar de estado devolveu {read}")
    summary_scenarios[sid] = {
        "code": got["code"], "expected_code": want_code, "steps": len(steps),
        "stated_results": len(stated_nodes), **counted,
    }

# topologia (3.2) preservada
official_plans = observed.get("PLANS", {})
for row in plan_evidence:
    got = official_plans.get(row["target"])
    if got is None or got[0] != row["observed"] or (got[0] == "OK" and str(len(got[1])) != row["steps"]):
        fail("topologia", f"{row['target']}: {got} != 3.2 {row['observed']}/{row['steps']}")


# ------------------------------------------------------------------
# 6. verificações estáticas (texto/AST, sem importar)
# ------------------------------------------------------------------
f_holders = sorted(
    str(p.relative_to(REPO)) for p in (REPO / "app").rglob("*.py")
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
    if isinstance(n, ast.Constant) and n.value == "F"
)
if f_holders != ["app/domain/values.py"]:
    fail("literal F", f"constante 'F' espalhada em {f_holders}")
state_tokens = set()
for p in (REPO / "app").rglob("*.py"):
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"[A-Z]+(_[A-Z]+)+", n.value):
            state_tokens.add(n.value)
if "OK" in state_tokens or "BLOCKED_BY_UPSTREAM_ERROR" in state_tokens:
    fail("estados inventados", "estado não contratado no código")
propagation_src = (REPO / "app/domain/state_propagation.py").read_text(encoding="utf-8")
imports = {n.module for n in ast.walk(ast.parse(propagation_src)) if isinstance(n, ast.ImportFrom)}
if not imports <= {"__future__", "app.domain.results"}:
    fail("centralização", f"state_propagation importa {imports}")
priority_words = re.findall(r"(?i)\b(priority|prioridade|precedence|max\(|min\()", propagation_src)
changed = subprocess.run(["git", "diff", "--name-only", BASELINE, "HEAD"], capture_output=True,
                         text=True, cwd=REPO).stdout.split()
protected = ("data/", "tools/", "app/engine/interblock_orchestrator.py", "app/domain/interblock/",
             "app/engine/temporal_aggregation_service.py")
touched = [p for p in changed if p.startswith(protected)]
if touched:
    fail("artefatos protegidos", f"alterados desde {BASELINE[:7]}: {touched}")


# ------------------------------------------------------------------
# 7. saída
# ------------------------------------------------------------------
summary = {
    "baseline": BASELINE,
    "literal_mapping": {
        "equations_with_state_literal": [list(x) for x in literal_equations],
        "declared_result_states": declared,
        "mapping_proven_per_variable": mapping_proven,
    },
    "f_branch_choice": f_choice, "control_choice": control_choice,
    "graph": {"nodes_with_edges": len(edges), "unresolved_references": len(unresolved)},
    "aggregation_scenario": {"rule": agg_rule["aggregation_rule_id"], "stated_input": agg_input},
    "scenarios": summary_scenarios,
    "evidence_rows": len(evidence_rows),
    "static": {"f_constant_holders": f_holders, "propagation_imports": sorted(imports),
               "priority_words_in_policy": priority_words, "changed_since_baseline": changed,
               "protected_touched": touched},
    "deterministic": deterministic,
    "problems": dict(counters),
}

if WRITE:
    (HERE / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (HERE / "propagation_evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    (HERE / "determinism_check.txt").write_text(
        f"probe PYTHONHASHSEED=0 sha-equal PYTHONHASHSEED=4242: {deterministic}\n"
        f"bytes: {len(raw_a)}\n", encoding="utf-8")

print(json.dumps({k: summary[k] for k in ("scenarios", "deterministic", "problems")}, ensure_ascii=False, indent=1))
for problem in problems:
    print(problem)
print("AUDIT:", "PASS" if not problems else "FAIL", f"({len(evidence_rows)} linhas de evidência)")
sys.exit(1 if problems else 0)
