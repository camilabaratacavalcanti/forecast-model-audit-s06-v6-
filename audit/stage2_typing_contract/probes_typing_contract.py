"""
Auditoria conceitual de tipagem e resultados heterogêneos — probes.

Somente leitura: executa o código de produção com fixtures genéricas
(IDs VAR96xxx, efêmeros) e grava evidence/*.json e matrizes CSV neste
diretório. Não altera código, seeds, workbooks nem testes.

    python3 audit/stage2_typing_contract/probes_typing_contract.py
"""

import csv
import itertools
import json
import platform
import random
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from app.domain.equations.models import EquationDefinition  # noqa: E402
from app.domain.equations.registry import EquationDefinitionRegistry  # noqa: E402
from app.domain.forecast.aggregation import AggregationRule  # noqa: E402
from app.domain.variables.models import VariableDefinition  # noqa: E402
from app.domain.variables.registry import VariableDefinitionRegistry  # noqa: E402
from app.engine import reference_resolver  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.expression_evaluator import ExpressionEvaluator  # noqa: E402
from app.engine.expression_parser import ExpressionParser  # noqa: E402
from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.temporal_aggregation_service import TemporalAggregationService  # noqa: E402

EVIDENCE = HERE / "evidence"
DAY = date(2026, 3, 2)
COMMIT = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def outcome(fn):
    try:
        value = fn()
        return {"kind": "value", "type": type(value).__name__, "repr": repr(value)}
    except Exception as exc:  # noqa: BLE001
        original = getattr(exc, "original_error", None)
        return {"kind": "error", "type": type(exc).__name__,
                "original": type(original).__name__ if original else None, "repr": str(exc)[:200]}


# ------------------------------------------------------------
# Mini-plataforma genérica: definições + equações + run do ForecastEngine
# ------------------------------------------------------------


def define(specs):
    """specs: [(id, value_type, scope_type, scope_value, expression|None)]"""

    variables, equations = VariableDefinitionRegistry(), EquationDefinitionRegistry()
    for n, (vid, vt, st, sv, expr) in enumerate(specs):
        variables.add(VariableDefinition(vid, vid.lower(), "-", "-", "calculado" if expr else "entrada",
                                         "diário", st, sv, "probe", "ativo", vt))
        if expr:
            equations.add(EquationDefinition(f"EQ96{n:03d}", vid, 1, st, sv, expr, "probe", "PUBLISHED"))
    return variables, equations


def run(specs, inputs, order=None):
    """inputs: {(id, scope_value): value}. Retorna (valores calculados, erro)."""

    variables, equations = define(specs)
    if order is not None:
        reordered = EquationDefinitionRegistry()
        for d in order(equations.all()):
            reordered.add(d)
        equations = reordered
    ctx = CalculationContext()
    ctx.declare_categorical_variables(d.variable_definition_id for d in variables.all() if d.is_categorical)
    for (vid, sv), value in inputs.items():
        st = next(d.scope_type for d in variables.all() if d.variable_definition_id == vid)
        ctx.set_variable_value(vid, value, st, sv, period_id=DAY.isoformat())
    error = None
    try:
        ForecastEngine().calculate_from_definition_registry(equations, ctx, variables, run_date=DAY)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}({type(getattr(exc, 'original_error', exc)).__name__})"
    produced = {d.target_variable_id: ctx._scoped_variables.get(next(
        (k for k in ctx._scoped_variables if k.entity_id == d.target_variable_id), None))
        for d in equations.all()}
    produced = {k: v for k, v in produced.items() if v is not None}
    return produced, error


def evaluate(expr, variables=None, categorical=()):
    ctx = CalculationContext(categorical_variable_ids=categorical)
    for k, v in (variables or {}).items():
        ctx.set_variable(k, v)
    return ExpressionEvaluator(ctx).evaluate(ExpressionParser().parse(expr))


PROBES = []


def probe(pid, title, inputs, expected, fn, interpretation):
    PROBES.append({"id": pid, "title": title, "input": inputs, "expected_behavior": expected,
                   "actual_behavior": outcome(fn), "interpretation": interpretation})


def probes():
    L = ("linha", "L1")
    probe("P01", "numeric -> numeric", "VAR96002 = VAR96001*2 ; VAR96001=5",
          "10 armazenado", lambda: run([("VAR96001", "numeric", *L, None), ("VAR96002", "numeric", *L, "VAR96001 * 2")], {("VAR96001", "L1"): 5.0}),
          "Caminho nominal.")
    probe("P02", "categorical -> categorical", 'VAR96012 = "ALTO" if VAR96011 == "LC" else "BAIXO" ; VAR96011="LC"',
          '"ALTO" armazenado', lambda: run([("VAR96011", "categorical", *L, None), ("VAR96012", "categorical", *L, '"ALTO" if VAR96011 == "LC" else "BAIXO"')], {("VAR96011", "L1"): "LC"}),
          "Texto é valor de domínio quando a variável é declarada categorical.")
    probe("P03a", "boolean como resultado final", "VAR96022 = VAR96021 > 0",
          "rejeitado", lambda: run([("VAR96021", "numeric", *L, None), ("VAR96022", "numeric", *L, "VAR96021 > 0")], {("VAR96021", "L1"): 1.0}),
          "Booleano não é valor armazenável; só existe como condição intermediária.")
    probe("P03b", "boolean como entrada", "set_variable(True)", "rejeitado",
          lambda: CalculationContext().set_variable("VAR96021", True), "Storage rejeita bool.")
    probe("P03c", "literal True/VERDADEIRO na DSL", "VAR96021 + True", "rejeitado",
          lambda: ExpressionParser().parse("VAR96021 + True"), "Parser rejeita constantes booleanas.")
    probe("P04", 'numeric -> "F"', 'VAR96032 = VAR96031 if VAR96031 > 0 else "F" ; VAR96031=-1',
          '"F" armazenado em variável numeric', lambda: run([("VAR96031", "numeric", *L, None), ("VAR96032", "numeric", *L, 'VAR96031 if VAR96031 > 0 else "F"')], {("VAR96031", "L1"): -1.0}),
          '"F" atravessa o gate de value_type: é tratado como estado, não como texto.')
    probe("P05a", 'numeric -> "ERRO!!!" (ramo executado)', 'VAR96042 = VAR96041 if VAR96041 > 0 else "ERRO!!!" ; VAR96041=-1',
          "rejeitado no armazenamento", lambda: run([("VAR96041", "numeric", *L, None), ("VAR96042", "numeric", *L, 'VAR96041 if VAR96041 > 0 else "ERRO!!!"')], {("VAR96041", "L1"): -1.0}),
          "Só detectado em runtime, quando o ramo executa.")
    probe("P05b", 'numeric -> "ERRO!!!" (ramo não executado)', "mesma equação ; VAR96041=3",
          "sem detecção (latente)", lambda: run([("VAR96041", "numeric", *L, None), ("VAR96042", "numeric", *L, 'VAR96041 if VAR96041 > 0 else "ERRO!!!"')], {("VAR96041", "L1"): 3.0}),
          "Não há verificação estática do tipo dos ramos contra value_type.")
    probe("P05c", 'categorical -> "ERRO!!!"', 'VAR96052 (categorical) = "OK" if VAR96051 > 0 else "ERRO!!!" ; VAR96051=-1',
          "?", lambda: run([("VAR96051", "numeric", *L, None), ("VAR96052", "categorical", *L, '"OK" if VAR96051 > 0 else "ERRO!!!"')], {("VAR96051", "L1"): -1.0}),
          "Erro de negócio indistinguível de categoria de domínio.")
    probe("P06a", "numeric -> None na DSL", "VAR96061 if VAR96061 > 0 else None", "rejeitado",
          lambda: ExpressionParser().parse("VAR96061 if VAR96061 > 0 else None"), "None não é expressável.")
    probe("P06b", "None no storage", "set_variable(None)", "rejeitado",
          lambda: CalculationContext().set_variable("VAR96061", None), "Ausência é representada por ausência de chave, nunca por None.")
    probe("P07", "numeric + numeric", "VAR96071 + VAR96072 (2+3)", "5",
          lambda: evaluate("VAR96071 + VAR96072", {"VAR96071": 2.0, "VAR96072": 3.0}), "Nominal.")
    probe("P08", 'numeric + "F"', 'VAR96081 + VAR96082 (2 + "F")', "falha explícita",
          lambda: evaluate("VAR96081 + VAR96082", {"VAR96081": 2.0, "VAR96082": "F"}), "Consumo de estado gera exceção, não valor.")

    def average_with_f(kind):
        ctx = CalculationContext()
        ctx.set_variable_value("VAR96091", 10.0, "linha", "L1", "2026-03-01")
        ctx.set_variable_value("VAR96091", "F", "linha", "L1", "2026-03-02")
        return TemporalAggregationService().aggregate(
            AggregationRule("AGG96", "VAR96091", "diário", "VAR96092", "mensal", kind), ctx, "linha", "L1", DAY).value
    probe("P09a", 'AVERAGE com "F"', "[10, F]", "falha explícita", lambda: average_with_f("AVERAGE"), "Nunca parcial.")
    probe("P09b", 'SUM com "F"', "[10, F]", "falha explícita", lambda: average_with_f("SUM"), "Nunca parcial.")
    probe("P10a", "IF numeric/numeric", "1 if VAR96101 > 0 else 2", "1",
          lambda: evaluate("1 if VAR96101 > 0 else 2", {"VAR96101": 1.0}), "Nominal.")
    probe("P10b", "IF numeric/string (ramo string)", '1 if VAR96101 > 0 else "X"', '"X" (avaliação); rejeitado ao armazenar em numeric',
          lambda: evaluate('1 if VAR96101 > 0 else "X"', {"VAR96101": -1.0}), "O evaluator não conhece value_type; o tipo do resultado depende do ramo.")
    probe("P10c", "IF string/string", '"A" if VAR96101 > 0 else "B"', '"B"',
          lambda: evaluate('"A" if VAR96101 > 0 else "B"', {"VAR96101": -1.0}), "Nominal para categorical.")

    chain = [("VAR96110", "numeric", *L, None), ("VAR96111", "numeric", *L, "VAR96110 * 2"),
             ("VAR96112", "numeric", *L, "VAR96111 + 1"), ("VAR96113", "numeric", *L, "VAR96112 / 2")]
    probe("P11a", 'propagação aritmética A="F" -> B -> C -> D', "B=A*2; C=B+1; D=C/2", "?",
          lambda: run(chain, {("VAR96110", "L1"): "F"}), "B falha; C e D não são calculados; nenhum recebe \"F\".")
    passthrough = [("VAR96120", "numeric", *L, None), ("VAR96121", "numeric", *L, "VAR96120"),
                   ("VAR96122", "numeric", *L, "VAR96121 if VAR96123 > 0 else 0"), ("VAR96123", "numeric", *L, None),
                   ("VAR96124", "numeric", *L, "VAR96122 + 1")]
    probe("P11b", 'propagação por referência/IF A="F" -> B=A -> C=(B if k>0 else 0) -> D=C+1', "k=1", "?",
          lambda: run(passthrough, {("VAR96120", "L1"): "F", ("VAR96123", "L1"): 1.0}),
          "Referência e ramo de IF repassam \"F\" como VALOR; só a aritmética converte em exceção.")
    probe("P13", "texto de domínio", 'VAR96131="LC" (categorical) comparado a "LC"', "1",
          lambda: evaluate('1 if VAR96131 == "LC" else 0', {"VAR96131": "LC"}, {"VAR96131"}), "Categoria legítima.")
    probe("P14a", 'categoria legítima com código "F"', 'VAR96141="F" (categorical) == "A"', "?",
          lambda: evaluate('1 if VAR96141 == "A" else 0', {"VAR96141": "F"}, {"VAR96141"}),
          'Colisão: um domínio categórico não pode usar o código "F".')
    probe("P14b", "texto de erro em categorical", 'VAR96142="ERRO!!!" (categorical)', "?",
          lambda: evaluate('1 if VAR96142 == "ERRO!!!" else 0', {"VAR96142": "ERRO!!!"}, {"VAR96142"}),
          "Erro de negócio armazenado como categoria, sem distinção.")


# ------------------------------------------------------------
# F-001: grupos independentes
# ------------------------------------------------------------


def f001():
    specs = [
        ("VAR96201", "numeric", "linha_grupo", "L1_L3", None),       # entrada A
        ("VAR96202", "numeric", "linha_grupo", "L4_L5", None),       # entrada B
        ("VAR96211", "numeric", "linha_grupo", "L1_L3", 'VAR96201 if VAR96201 >= 0 else "F"'),  # grupo A
        ("VAR96212", "numeric", "linha_grupo", "L4_L5", 'VAR96202 if VAR96202 >= 0 else "F"'),  # grupo B
        ("VAR96221", "numeric", "linha", "L1", "VAR96211@L1_L3 * 2"),  # dependente só de A
        ("VAR96222", "numeric", "linha", "L4", "VAR96212@L4_L5 * 2"),  # dependente só de B
        ("VAR96230", "numeric", "linha_grupo", "L1_L7", "VAR96211@L1_L3 + VAR96212@L4_L5"),  # agregador
    ]
    cases = {"1: A=num, B=num": (1.0, 2.0), "2: A=F, B=num": (-1.0, 2.0), "3: A=num, B=F": (1.0, -2.0), "4: A=F, B=F": (-1.0, -2.0)}
    orders = {"original": lambda d: d, "reversa": lambda d: list(reversed(d)),
              "aleatória(7)": lambda d: random.Random(7).sample(d, len(d))}
    rows = []
    for case, (a, b) in cases.items():
        for oname, order in orders.items():
            produced, error = run(specs, {("VAR96201", "L1_L3"): a, ("VAR96202", "L4_L5"): b}, order)
            rows.append({
                "caso": case, "ordem": oname, "erro": error or "",
                "grupo_A": produced.get("VAR96211", "—"), "grupo_B": produced.get("VAR96212", "—"),
                "dep_A (só A)": produced.get("VAR96221", "—"), "dep_B (só B)": produced.get("VAR96222", "—"),
                "agregador(A+B)": produced.get("VAR96230", "—"),
            })
    return rows


# ------------------------------------------------------------
# Agregação / compatibilidade / propagação / negativos / mutação
# ------------------------------------------------------------


def aggregation_matrix():
    rows = []
    series = {"numeric+numeric": [1.0, 3.0], 'numeric+"F"': [1.0, "F"], "numeric+string": [1.0, "X"],
              "string+string": ["A", "B"], "numeric+ausente": [1.0, None]}
    for label, values in series.items():
        for kind in ("SUM", "AVERAGE", "MIN", "MAX"):
            def agg(values=values, kind=kind):
                rule = AggregationRule("AGG96", "VAR96301", "diário", "VAR96302", "mensal", kind)
                ctx = CalculationContext(categorical_variable_ids={"VAR96301"})
                for i, v in enumerate(values, start=1):
                    if v is not None:
                        ctx.set_variable_value("VAR96301", v, "linha", "L1", f"2026-03-{i:02d}")
                return TemporalAggregationService().aggregate(rule, ctx, "linha", "L1", DAY).value
            o = outcome(agg)
            rows.append({"serie": label, "agregacao": kind, "resultado": o["repr"] if o["kind"] == "value" else f"{o['type']}: {o['repr'][:90]}"})
    return rows


def compatibility_matrix():
    produced = {"Numeric": 1.5, "Categorical": "LC", "Boolean": True, "String(erro)": "ERRO!!!", "F/Estado": "F", "None": None}
    rows = []
    for label, value in produced.items():
        row = {"Produzido": label}
        for declared in ("numeric", "categorical"):
            ctx = CalculationContext(categorical_variable_ids={"VAR96401"} if declared == "categorical" else ())
            o = outcome(lambda: ctx.set_variable("VAR96401", value))
            row[f"armazenar em {declared}"] = "aceito" if o["kind"] == "value" else f"rejeitado ({o['type']})"
        o = outcome(lambda: evaluate("VAR96402 + 1", {"VAR96402": value} if not isinstance(value, (bool, type(None))) else {}, {"VAR96402"}))
        row["aritmética"] = o["repr"] if o["kind"] == "value" else o["type"]
        o = outcome(lambda: evaluate('1 if VAR96402 == "LC" else 0', {"VAR96402": value}, {"VAR96402"}) if not isinstance(value, (bool, type(None))) else (_ for _ in ()).throw(TypeError("não armazenável")))
        row['== "LC"'] = o["repr"] if o["kind"] == "value" else o["type"]
        rows.append(row)
    return rows


def propagation_matrix():
    F = {"VAR96501": "F", "VAR96502": 2.0}
    ops = {
        "comparação (== 0)": "1 if VAR96501 == 0 else 2", 'comparação (== "F")': '1 if VAR96501 == "F" else 2',
        "comparação (> 0)": "1 if VAR96501 > 0 else 2", "soma": "VAR96501 + VAR96502", "multiplicação": "VAR96501 * VAR96502",
        "divisão": "VAR96501 / VAR96502", "ln()": "ln(VAR96501)", "IF (condição)": "1 if VAR96501 else 2",
        "IF (ramo devolvido)": "VAR96501 if VAR96502 > 0 else 0", "referência": "VAR96501", "and/or": "1 if VAR96501 > 0 and VAR96502 > 0 else 2",
    }
    rows = []
    for op, expr in ops.items():
        o = outcome(lambda: evaluate(expr, F))
        rows.append({"operacao": op, "expressao": expr, "resultado": o["repr"] if o["kind"] == "value" else o["type"]})
    return rows


def negative_tests():
    L = ("linha", "L1")
    cases = [
        ("NT01", '"F" convertido implicitamente', lambda: evaluate("VAR96601 * 1", {"VAR96601": "F"})),
        ("NT02", "string somada", lambda: evaluate('VAR96602 + 1', {"VAR96602": "LC"}, {"VAR96602"})),
        ("NT03", "string tratada como zero", lambda: evaluate('VAR96602 * 0', {"VAR96602": "LC"}, {"VAR96602"})),
        ("NT04", "bool convertido em número", lambda: evaluate("(VAR96603 > 0) + 1", {"VAR96603": 1.0})),
        ("NT05", "número como condição de IF (legado)", lambda: evaluate("1 if VAR96603 else 2", {"VAR96603": 3.0})),
        ("NT06", "None ignorado", lambda: CalculationContext().set_variable("VAR96604", None)),
        ("NT07", "texto em variável não declarada", lambda: CalculationContext().set_variable("VAR96605", "LC")),
        ("NT08", "número em variável categorical", lambda: CalculationContext(categorical_variable_ids={"VAR96606"}).set_variable("VAR96606", 7.0)),
        ("NT09", "value_type mixed", lambda: VariableDefinition("VAR96607", "x", "-", "-", "calculado", "diário", *L, "t", "ativo", "mixed")),
        ("NT10", "value_type string/boolean", lambda: [VariableDefinition("VAR96608", "x", "-", "-", "calculado", "diário", *L, "t", "ativo", t) for t in ("string",)]),
        ("NT11", "categorical sem registry (engine chamado sem variable_definition_registry)",
         lambda: _engine_without_registry()),
        ("NT12", "agregação declarada sobre variável categorical (estático)", lambda: AggregationRule("AGG96", "VAR96609", "diário", "VAR96610", "mensal", "AVERAGE")),
        ("NT13", 'categoria "F" colide com o sentinela', lambda: evaluate('1 if VAR96611 == "A" else 0', {"VAR96611": "F"}, {"VAR96611"})),
        ("NT14", "erro técnico e estado de negócio na mesma família de exceção",
         lambda: [c.__mro__[1].__name__ for c in (__import__("app.engine.exceptions", fromlist=["x"]).ConditionalFailureError,
                                                  __import__("app.engine.exceptions", fromlist=["x"]).DivisionByZeroError)]),
    ]
    classification = {
        "NT01": "SAFE", "NT02": "SAFE", "NT03": "SAFE", "NT04": "SAFE", "NT05": "DEFINED", "NT06": "SAFE", "NT07": "SAFE",
        "NT08": "AMBIGUOUS", "NT09": "SAFE", "NT10": "SAFE", "NT11": "AMBIGUOUS", "NT12": "AMBIGUOUS", "NT13": "UNSAFE", "NT14": "AMBIGUOUS",
    }
    return [{"id": cid, "caso": title, "resultado": (lambda o: o["repr"] if o["kind"] == "value" else f"{o['type']}: {o['repr'][:100]}")(outcome(fn)),
             "classificacao": classification[cid]} for cid, title, fn in cases]


def _engine_without_registry():
    variables, equations = define([("VAR96620", "categorical", "linha", "L1", None), ("VAR96621", "categorical", "linha", "L1", '"A" if VAR96620 == "LC" else "B"')])
    ctx = CalculationContext()
    ctx.set_variable_value("VAR96620", "LC", "linha", "L1")
    return ForecastEngine().calculate_from_definition_registry(equations, ctx)


GROUP_EXPR = ('(1 if VAR96701 == "Normal" and VAR96702 == "Normal" else 2 if VAR96701 == "LC" or VAR96702 == "LC" '
              'else 3 if VAR96701 == "Overhaul/Parada" or VAR96702 == "Overhaul/Parada" else 4 if VAR96701 == "1 By pass" or VAR96702 == "1 By pass" '
              'else 5 if VAR96701 == "1 By pass e LC" and VAR96702 == "1 By pass e LC" else "F")')


def mini(vt_a="categorical", vt_group="numeric", expr=GROUP_EXPR, a="Normal", b="Normal"):
    specs = [("VAR96701", vt_a, "linha", "L1", None), ("VAR96702", vt_a, "linha", "L1", None),
             ("VAR96703", vt_group, "linha", "L1", expr), ("VAR96704", "numeric", "linha", "L1", "VAR96703 * 10")]
    return run(specs, {("VAR96701", "L1"): a, ("VAR96702", "L1"): b})


def mutation_tests():
    """Corrupções controladas do padrão A41 (fixture genérica) — detectadas? quando?"""

    mutations = [
        ("MT00", "baseline (Normal/Normal)", lambda: mini()),
        ("MT01", "estados declarados numeric", lambda: mini(vt_a="numeric")),
        ("MT02", "resultado numérico declarado categorical", lambda: mini(vt_group="categorical")),
        ("MT03", '"F" trocado por "ERRO!!!" (ramo não executado)', lambda: mini(expr=GROUP_EXPR.replace('"F"', '"ERRO!!!"'))),
        ("MT04", '"F" trocado por "ERRO!!!" (ramo executado)', lambda: mini(expr=GROUP_EXPR.replace('"F"', '"ERRO!!!"'), a="Normal", b="1 By pass e LC")),
        ("MT05", "value_type mixed", lambda: mini(vt_group="mixed")),
        ("MT06", "resultado booleano", lambda: mini(expr='VAR96701 == "Normal"')),
        ("MT07", 'ramo numérico vira texto "100" em aritmética', lambda: ExpressionParser().parse('("100" + 1) if VAR96701 == "Normal" else 2')),
        ("MT08", 'estado com erro de digitação ("Overhaul")', lambda: mini(a="Overhaul", b="Normal")),
        ("MT09", 'estado "F" legítimo? (hes="F")', lambda: mini(a="F", b="Normal")),
    ]
    rows = []
    for mid, title, fn in mutations:
        o = outcome(fn)
        rows.append({"id": mid, "mutacao": title, "resultado": o["repr"][:200] if o["kind"] == "value" else f"{o['type']}: {o['repr'][:120]}"})
    return rows


# ------------------------------------------------------------
# A41 (estudo de caso): texto real da equação L4_L5 do workbook
# ------------------------------------------------------------


def a41_case_study():
    path = ROOT / "audit" / "area_41_v6" / "descritivo_das_variáveis_A41_v6.xlsx"
    ws = openpyxl.load_workbook(path)["A41"]
    expr_l45 = ws["M39"].value
    ents = [
        {"entity_id": "VAR96801", "name": "retirada_cond_corr_ltp", "kind": "variable", "frequency": "diário", "scope_type": "linha_grupo", "scope_value": "L4_L5"},
        {"entity_id": "VAR96802", "name": "retirada_cond_corr_lth", "kind": "variable", "frequency": "diário", "scope_type": "linha_grupo", "scope_value": "L4_L5"},
        {"entity_id": "VAR96803", "name": "hes_l4", "kind": "variable", "frequency": "diário", "scope_type": "linha", "scope_value": "L4"},
        {"entity_id": "VAR96804", "name": "hes_l5", "kind": "variable", "frequency": "diário", "scope_type": "linha", "scope_value": "L5"},
        {"entity_id": "VAR96805", "name": "desconto_retirada_41c", "kind": "variable", "frequency": "diário", "scope_type": "linha_grupo", "scope_value": "L4_L5"},
        {"entity_id": "VAR96806", "name": "desconto_retirada_41d", "kind": "variable", "frequency": "diário", "scope_type": "linha_grupo", "scope_value": "L4_L5"},
    ]
    translated = reference_resolver.translate_expression(expr_l45, reference_resolver.build_name_index(ents), "diário",
                                                         consumer_scope=("linha_grupo", "L4_L5"))
    tree = ExpressionParser().parse(translated)
    states = ["Normal", "LC", "Overhaul/Parada", "1 By pass", "1 By pass e LC", "Overhaul", ""]
    rows = []
    for a, b in itertools.product(states, repeat=2):
        ctx = CalculationContext(categorical_variable_ids={"VAR96803", "VAR96804"})
        for vid, sv, v in (("VAR96801", "L4_L5", 20.0), ("VAR96802", "L4_L5", 15.0), ("VAR96805", "L4_L5", 5.0), ("VAR96806", "L4_L5", 4.0)):
            ctx.set_variable_value(vid, v, "linha_grupo", sv)
        if a:
            ctx.set_variable_value("VAR96803", a, "linha", "L4")
        if b:
            ctx.set_variable_value("VAR96804", b, "linha", "L5")
        o = outcome(lambda: ExpressionEvaluator(ctx, "linha_grupo", "L4_L5").evaluate(tree))
        rows.append({"hes_l4": a or "(vazio)", "hes_l5": b or "(vazio)",
                     "resultado": o["repr"] if o["kind"] == "value" else o["type"], "tipo": o["type"]})
    return {"workbook_sha_prefix": "4b0c41ae", "cell": "M39", "translated": translated, "rows": rows}


def write_csv(name, rows):
    with open(HERE / name, "w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    EVIDENCE.mkdir(exist_ok=True)
    probes()
    results = {
        "environment": {"commit": COMMIT, "python": platform.python_version(),
                        "command": "python3 audit/stage2_typing_contract/probes_typing_contract.py"},
        "probes": PROBES, "f001": f001(), "aggregation": aggregation_matrix(), "compatibility": compatibility_matrix(),
        "propagation": propagation_matrix(), "negative_tests": negative_tests(), "mutation_tests": mutation_tests(),
        "a41_case_study": a41_case_study(),
    }
    (EVIDENCE / "probes_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    write_csv("f001_matrix.csv", results["f001"])
    write_csv("aggregation_matrix.csv", results["aggregation"])
    write_csv("compatibility_matrix.csv", results["compatibility"])
    write_csv("propagation_matrix.csv", results["propagation"])
    write_csv("negative_tests.csv", results["negative_tests"])
    write_csv("mutation_tests.csv", results["mutation_tests"])
    write_csv("a41_case_study.csv", results["a41_case_study"]["rows"])
    for p in PROBES:
        a = p["actual_behavior"]
        print(f"{p['id']:5} {p['title'][:45]:45} -> {a['type']}{('/' + a['original']) if a.get('original') else ''}: {a['repr'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
