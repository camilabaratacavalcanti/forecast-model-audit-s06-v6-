"""
Stage 4A.3a — confronto ENGINE x ORACLE de fidelidade ao workbook A41 v9 (REAL_DERIVED_TEST_RESULT).

    python audit/stage4a/oracle/run_oracle.py [--no-write]

O oracle (`oracle_a41.py`) é Python puro reescrito do texto do workbook; este driver
importa o engine só para obter o lado "engine" da comparação.

A. equação a equação (20/20): o engine executa CADA equação isolada com os operandos
   diretos do texto; grade determinística de magnitudes (inclui ~0, valores grandes e
   inválidos para `ln` e divisão por zero: a falha explícita do engine precisa ser a
   falha prevista pelo oracle);
B. cadeia do dia (as 20 juntas) a partir das entradas de fronteira; TODAS as 25 combinações
   de `hes` para (L4, L5) e para (L6, L7), cobrindo cada ramo e o NO_APPLICABLE_RULE do "F";
C. integrado: nas 32 datas do grafo de 5 blocos, o oracle recalcula os diários do area_41 a
   partir das entradas efetivas do contexto (inclusive `lth` transferido do yield) e as
   agregações mensais/anuais (média manual; `statistics.fmean` como conferência); mais um
   trecho com "F" (Policy B).

Tolerância (DR-4A-7): math.isclose(rel_tol=1e-12, abs_tol=1e-12) para valores; estados e
falhas por igualdade exata.
"""

from __future__ import annotations

import ast
import csv
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(HERE))

import common  # noqa: E402
import oracle_a41 as oracle  # noqa: E402

from app.domain.results import Result  # noqa: E402

EVIDENCE = HERE / "evidence"
REL_TOL = ABS_TOL = 1e-12
HES = ("Normal", "LC", "Overhaul/Parada", "1 By pass", "1 By pass e LC")
NAMES = {"vazao_ltp", "fator_retirada_cond_corr_lth", "lth", "valor_retirada", "hes", "desconto_retirada_41c",
         "desconto_retirada_41d", "retirada_cond_corr_ltp", "lth_grupo", "retirada_cond_corr_lth",
         "retirada_condensado_grupo", "retirada_condensado_linha", "retirada_condensado_total"}
MAGNITUDES = (1e-9, 1e-3, 0.5, 1.0, 1.1, 3.0, 47.0, 48.0, 970.0, 1100.0, 1320.0, 1.0e6)


# ------------------------------------------------------------------ mapeamento nome@escopo -> ID (seeds)
def identity_map(orchestrator) -> dict:
    """
    {(nome, escopo): (variável, scope_type, scope_value)} das variáveis diárias e entradas
    do area_41 (leitura dos seeds: é o ponto compartilhado com o engine, declarado).
    """
    catalog = orchestrator.catalog
    out = {}
    for d in catalog.variable_definitions.all():
        vid = d.variable_definition_id
        if catalog.block_of.get(vid) != "area_41" or (d.variable_type == "calculado" and d.frequency != "diário"):
            continue
        for st, sv in common.ScopeResolver().resolve_scopes(d.scope_type, d.scope_value):
            out[(d.variable_name, sv)] = (vid, st, sv)
    return out


def operands_of(name: str, scope: str) -> dict:
    """
    Operandos do texto transcrito: {(nome, escopo): rótulo}. Sem sufixo => escopo da
    equação e rótulo = nome; com sufixo => rótulo = "nome@escopo" (como no texto).
    """
    text = oracle.WORKBOOK_TEXT[(name, scope)]
    found = {}
    for ident, suffix in re.findall(r"\b([a-z][a-z_0-9]*)(?:@(L\d(?:_L\d)?))?", text):
        if ident in NAMES:
            found.setdefault((ident, suffix or scope), f"{ident}@{suffix}" if suffix else ident)
    return found


def classify_engine(results, error, target):
    if error is not None:
        chain = common.error_chain(error)
        if "MathDomainError" in chain:
            return ("FAILURE", "LN_DOMAIN")
        if "DivisionByZeroError" in chain:
            return ("FAILURE", "DIVISION_BY_ZERO")
        return ("FAILURE", "OTHER:" + "/".join(chain))
    r = results.get(target)
    if r is None:
        return ("MISSING", None)
    if r.state is not None:
        return ("STATE", (r.state, r.detail, r.value))
    return ("VALUE", r.value)


def classify_oracle(fn):
    try:
        value = fn()
    except oracle.DomainFailure as exc:
        return ("FAILURE", exc.kind)
    if isinstance(value, oracle.Stated):
        return ("STATE", (value.state, value.detail, None))
    return ("VALUE", value)


def agree(engine, expected) -> tuple[bool, bool]:
    """(concorda dentro da tolerância, igualdade exata)."""
    if engine[0] != expected[0]:
        return False, False
    if engine[0] == "VALUE":
        a, b = engine[1], expected[1]
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            return False, False
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL), a == b
    return engine[1] == expected[1], engine[1] == expected[1]


# ------------------------------------------------------------------ A. equação a equação
def operand_values(rng, operands, hes_combo=None):
    values = {}
    for name, scope in operands:
        if name == "hes":
            values[(name, scope)] = hes_combo[scope] if hes_combo else "Normal"
        else:
            values[(name, scope)] = rng.choice(MAGNITUDES) * rng.choice((1.0, 1.0, 1.0, 1.7))
    return values


def failure_cases(name, scope, operands):
    """Casos que DEVEM falhar: argumento de ln <= 0 e denominador zero."""
    cases = []
    if name == "retirada_cond_corr_ltp":
        cases += [{("vazao_ltp", scope): x} for x in (0.0, -1.0, -1e-9)]
    if name == "retirada_cond_corr_lth":
        cases += [{("lth_grupo", scope): 0.0, ("fator_retirada_cond_corr_lth", scope): 1.1},
                  {("lth_grupo", scope): 970.0, ("fator_retirada_cond_corr_lth", scope): 0.0},
                  {("lth_grupo", scope): -970.0, ("fator_retirada_cond_corr_lth", scope): 1.1}]
    if name == "retirada_condensado_linha":
        zero = {op: (0.0 if op[0] == "lth" else 10.0) for op in operands}
        cancel = {op: 10.0 for op in operands}
        members = oracle.GROUPS[oracle.GROUP_OF[scope]]
        cancel[("lth", members[0])] = 5.0
        cancel[("lth", members[1])] = -5.0 if len(members) == 2 else -2.0
        if len(members) == 3:
            cancel[("lth", members[2])] = -3.0
        cases += [zero, cancel]
    return cases


def run_equation_grid(orchestrator, ids, rng) -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    catalog = orchestrator.catalog
    by_target = {}
    for d in common.area_41_equations(orchestrator):
        target = catalog.variable_definitions.get(d.target_variable_id)
        for st, sv in common.ScopeResolver().resolve_scopes(d.scope_type, d.scope_value):
            by_target[(target.variable_name, sv)] = d.equation_definition_id
    for (name, scope), equation_id in sorted(by_target.items()):
        operands = operands_of(name, scope)
        has_hes = any(op[0] == "hes" for op in operands)
        cases = []
        if has_hes:
            lines = oracle.GROUPS[scope]
            for a in HES:
                for b in HES:
                    for _ in range(3):
                        cases.append(operand_values(rng, operands, {lines[0]: a, lines[1]: b}))
        else:
            cases += [operand_values(rng, operands) for _ in range(40)]
        cases += failure_cases(name, scope, operands)
        target_key = ids[(name, scope)]
        for case in cases:
            engine_inputs = {ids[op]: value for op, value in case.items()}
            results, error = common.engine_area_41(orchestrator, engine_inputs, only={equation_id})
            got = classify_engine(results, error, target_key)
            named = {operands[op]: value for op, value in case.items()}
            expected = classify_oracle(lambda: oracle.evaluate_equation(name, scope, named))
            ok, exact = agree(got, expected)
            rows.append({"mode": "equation", "equation": equation_id, "target": f"{name}@{scope}",
                         "inputs": json.dumps({f"{n}@{s}": v for (n, s), v in case.items()}, ensure_ascii=False),
                         "engine": repr(got), "oracle": repr(expected), "agree": ok, "exact": exact})
            if not ok:
                problems.append(f"ORACLE_MISMATCH {equation_id} {name}@{scope} {case}: engine {got} != oracle {expected}")
    return rows, problems


# ------------------------------------------------------------------ B. cadeia do dia e as 25 combinações de hes
def chain_inputs(rng, hes):
    return {"vazao_ltp": {g: rng.choice((0.5, 47.0, 970.0, 1320.0, 1.0e6)) for g in oracle.GROUPS},
            "fator_retirada_cond_corr_lth": {g: rng.choice((1e-3, 1.1, 1.15, 3.0)) for g in oracle.GROUPS},
            "lth": {line: rng.choice((1e-3, 1.0, 970.0, 1100.0, 1.0e5)) for line in oracle.GROUP_OF},
            "valor_retirada": {line: rng.choice((0.0, 47.0, 48.0, 1.0e4)) for line in ("L1", "L2", "L3")},
            "hes": dict(hes), "desconto_retirada_41c": {"L4_L5": rng.choice((0.0, 3.0, 50.0)),
                                                        "L6_L7": rng.choice((0.0, 3.0, 50.0))},
            "desconto_retirada_41d": {"L4_L5": rng.choice((0.0, 5.0, 50.0))}}


def to_engine(inputs, ids):
    out = {}
    for name, per_scope in inputs.items():
        for scope, value in per_scope.items():
            out[ids[(name, scope)]] = value
    return out


def run_chain(orchestrator, ids, rng) -> tuple[list[dict], list[str], dict]:
    rows, problems = [], []
    cases = []
    normal = {line: "Normal" for line in ("L4", "L5", "L6", "L7")}
    cases += [("grid", chain_inputs(rng, normal)) for _ in range(30)]
    for group, (la, lb) in (("L4_L5", ("L4", "L5")), ("L6_L7", ("L6", "L7"))):
        for a in HES:
            for b in HES:
                hes = dict(normal, **{la: a, lb: b})
                for _ in range(2):
                    cases.append((f"hes_{group}", chain_inputs(rng, hes)))
    failure = chain_inputs(rng, normal)
    failure["vazao_ltp"]["L4_L5"] = 0.0
    cases.append(("failure_ln", failure))
    coverage = defaultdict(Counter)
    for label, inputs in cases:
        results, error = common.engine_area_41(orchestrator, to_engine(inputs, ids))
        try:
            expected_all = oracle.evaluate_day(inputs)
            failure_kind = None
        except oracle.DomainFailure as exc:
            expected_all, failure_kind = None, exc.kind
        if failure_kind or error is not None:
            got = classify_engine(results, error, None)
            ok = got == ("FAILURE", failure_kind)
            rows.append({"mode": "chain", "equation": label, "target": "*", "inputs": json.dumps(inputs, ensure_ascii=False),
                         "engine": repr(got), "oracle": repr(("FAILURE", failure_kind)), "agree": ok, "exact": ok})
            if not ok:
                problems.append(f"ORACLE_MISMATCH chain {label}: engine {got} != oracle FAILURE {failure_kind}")
            continue
        for (name, scope), value in expected_all.items():
            expected = ("STATE", (value.state, value.detail, None)) if isinstance(value, oracle.Stated) else ("VALUE", value)
            got = classify_engine(results, None, ids[(name, scope)])
            ok, exact = agree(got, expected)
            rows.append({"mode": "chain", "equation": label, "target": f"{name}@{scope}",
                         "inputs": json.dumps({"hes": inputs["hes"]}, ensure_ascii=False),
                         "engine": repr(got), "oracle": repr(expected), "agree": ok, "exact": exact})
            if not ok:
                problems.append(f"ORACLE_MISMATCH chain {label} {name}@{scope}: engine {got} != oracle {expected}")
        for group, (la, lb) in (("L4_L5", ("L4", "L5")), ("L6_L7", ("L6", "L7"))):
            if label == f"hes_{group}":
                v = expected_all[("retirada_condensado_grupo", group)]
                coverage[group][(inputs["hes"][la], inputs["hes"][lb],
                                 "NO_APPLICABLE_RULE" if isinstance(v, oracle.Stated) else "VALUE")] += 1
    hes_cov = {g: {"combinations": len({(a, b) for a, b, _ in c}),
                   "no_applicable_rule": sorted([a, b] for a, b, s in c if s == "NO_APPLICABLE_RULE")}
               for g, c in coverage.items()}
    return rows, problems, hes_cov


# ------------------------------------------------------------------ C. integrado (32 datas) + agregações
INPUT_VARS = {"vazao_ltp": "VAR16001|VAR16002|VAR16003", "fator_retirada_cond_corr_lth": "VAR16011|VAR16012|VAR16013"}


def oracle_inputs_from_context(context, ids, day):
    inputs = defaultdict(dict)
    for (name, scope), (vid, st, sv) in ids.items():
        if name in ("vazao_ltp", "fator_retirada_cond_corr_lth", "lth", "valor_retirada", "hes",
                    "desconto_retirada_41c", "desconto_retirada_41d"):
            frequency = "mensal" if name in INPUT_VARS else "diário"
            period = common.PERIODS.effective_window(frequency, day).period_id
            r = context.get_variable_result(vid, st, sv, period, as_of=day)
            inputs[name][scope] = oracle.Stated(r.state, r.detail) if r.state is not None else r.value
    return dict(inputs)


def run_integrated(universe, ids, days, overrides=None) -> tuple[list[dict], list[str], dict]:
    context, _ = universe.run_sequence(days, overrides)
    catalog = universe.orchestrator.catalog
    rows, problems = [], []
    daily_oracle = {}
    for day in days:
        expected_all = oracle.evaluate_day(oracle_inputs_from_context(context, ids, day))
        for (name, scope), value in expected_all.items():
            daily_oracle[(name, scope, day)] = value
            vid, st, sv = ids[(name, scope)]
            r = context.get_variable_result(vid, st, sv, day.isoformat(), as_of=day)
            got = ("STATE", (r.state, r.detail, r.value)) if r.state is not None else ("VALUE", r.value)
            expected = ("STATE", (value.state, value.detail, None)) if isinstance(value, oracle.Stated) else ("VALUE", value)
            ok, exact = agree(got, expected)
            rows.append({"mode": "integrated_daily", "equation": day.isoformat(), "target": f"{name}@{scope}",
                         "inputs": "", "engine": repr(got), "oracle": repr(expected), "agree": ok, "exact": exact})
            if not ok:
                problems.append(f"ORACLE_MISMATCH integrado {day} {name}@{scope}: {got} != {expected}")
    # agregações: média manual dos diários DO ORACLE na janela efetiva
    windows = Counter()
    for instance in catalog.aggregation_rule_instances.all():
        rule = instance.rule
        if catalog.block_of.get(rule.aggregation_rule_id) != "area_41":
            continue
        source = catalog.variable_definitions.get(rule.source_variable_id)
        for day in days:
            window = [d for d in days if d <= day and (d.year == day.year if rule.target_frequency == "anual"
                                                      else (d.year, d.month) == (day.year, day.month))]
            values = [daily_oracle[(source.variable_name, instance.scope_value, d)] for d in window]
            expected_value = oracle.average(values)
            if not isinstance(expected_value, oracle.Stated):
                fmean = statistics.fmean(values)
                if not math.isclose(fmean, expected_value, rel_tol=REL_TOL, abs_tol=ABS_TOL):
                    problems.append(f"ORACLE_SELF_CHECK média manual != statistics.fmean {rule.aggregation_rule_id}")
            period = common.PERIODS.effective_window(rule.target_frequency, day).period_id
            r = context.get_variable_result(rule.target_variable_id, instance.scope_type, instance.scope_value, period,
                                            as_of=day)
            got = ("STATE", (r.state, r.detail, r.value)) if r.state is not None else ("VALUE", r.value)
            expected = (("STATE", (expected_value.state, expected_value.detail, None))
                        if isinstance(expected_value, oracle.Stated) else ("VALUE", expected_value))
            ok, exact = agree(got, expected)
            windows[rule.target_frequency] += 1
            rows.append({"mode": "integrated_aggregation", "equation": rule.aggregation_rule_id,
                         "target": f"{rule.target_variable_id}@{instance.scope_value}@{day.isoformat()}",
                         "inputs": f"{len(window)} diários", "engine": repr(got), "oracle": repr(expected),
                         "agree": ok, "exact": exact})
            if not ok:
                problems.append(f"ORACLE_MISMATCH agregação {rule.aggregation_rule_id} {instance.scope_value} {day}: "
                                f"{got} != {expected}")
    return rows, problems, dict(windows)


def oracle_is_pure() -> list[str]:
    """O módulo do oracle não importa app/, tools/ nem harnesses (verificação por AST)."""
    tree = ast.parse((HERE / "oracle_a41.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    allowed = {"__future__", "math", "re", "pathlib", "openpyxl"}
    return [f"ORACLE_IMPURE importa {sorted(imported - allowed)}"] if imported - allowed else []


def main() -> int:
    problems = oracle_is_pure() + oracle.check_workbook_text()
    universe = common.Universe("A")
    orchestrator = universe.orchestrator
    ids = identity_map(orchestrator)
    rng = random.Random(4242)
    eq_rows, p = run_equation_grid(orchestrator, ids, rng)
    problems += p
    chain_rows, p, hes_cov = run_chain(orchestrator, ids, rng)
    problems += p
    int_rows, p, windows = run_integrated(universe, ids, common.DAYS)
    problems += p
    d4 = common.DAYS[:4]
    f_over = lambda d: ([("VAR16021", "linha", "L5", d.isoformat(), Result("1 By pass e LC"))]  # noqa: E731
                        if d == d4[1] else [])
    f_rows, p, _ = run_integrated(universe, ids, d4, f_over)
    for r in f_rows:
        r["mode"] += "_with_F"
    problems += p
    rows = eq_rows + chain_rows + int_rows + f_rows

    per_equation = defaultdict(Counter)
    for r in eq_rows:
        per_equation[r["equation"]]["cases"] += 1
        per_equation[r["equation"]]["agree"] += r["agree"]
        per_equation[r["equation"]]["exact"] += r["exact"]
        kind = r["oracle"].split("'")[1]
        per_equation[r["equation"]][kind.lower()] += 1
    for group in ("L4_L5", "L6_L7"):
        cov = hes_cov.get(group, {})
        if cov.get("combinations") != 25 or sorted(map(tuple, cov.get("no_applicable_rule", []))) != sorted(
                {("Normal", "1 By pass e LC"), ("1 By pass e LC", "Normal")}):
            problems.append(f"ORACLE_COVERAGE {group}: {cov}")
    if len(per_equation) != 20:
        problems.append(f"ORACLE_COVERAGE {len(per_equation)} equações != 20")
    if not any(r["agree"] and "STATE" in r["engine"] for r in f_rows if r["mode"] == "integrated_aggregation_with_F"):
        problems.append("ORACLE_COVERAGE nenhuma agregação com NO_APPLICABLE_RULE comparada")
    by_mode = defaultdict(Counter)
    for r in rows:
        by_mode[r["mode"]]["compared"] += 1
        by_mode[r["mode"]]["agree"] += r["agree"]
        by_mode[r["mode"]]["exact"] += r["exact"]
    summary = {
        "label": common.LABEL, "oracle": "INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)",
        "tolerance": {"rel_tol": REL_TOL, "abs_tol": ABS_TOL, "states_and_failures": "igualdade exata"},
        "limitations": ["valida fidelidade ao workbook A41 v9, não correção de negócio",
                        "compartilha com o engine a leitura do workbook (o mesmo texto é a fonte dos dois); "
                        "o mapeamento nome@escopo -> ID vem dos seeds"],
        "workbook_text_guard": "PASS" if not oracle.check_workbook_text() else "FAIL",
        "equations_covered": len(per_equation),
        "per_equation": {k: dict(v) for k, v in sorted(per_equation.items())},
        "hes_coverage": hes_cov, "aggregation_windows_compared": windows,
        "by_mode": {k: dict(v) for k, v in sorted(by_mode.items())},
        "compared": len(rows), "agree": sum(r["agree"] for r in rows), "exact": sum(r["exact"] for r in rows),
        "problems": problems, "result": "PASS" if not problems else "FAIL",
    }
    if "--no-write" not in sys.argv[1:]:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / "oracle_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True)
                                                      + "\n", encoding="utf-8")
        with (EVIDENCE / "oracle_cases.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({k: summary[k] for k in ("equations_covered", "hes_coverage", "by_mode", "compared", "agree",
                                              "exact", "problems", "result")}, indent=1, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
