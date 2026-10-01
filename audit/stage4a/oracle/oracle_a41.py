"""
Stage 4A.3a — oracle INDEPENDENTE de fidelidade ao workbook A41 v9 (Python puro).

As 20 equações do area_41 foram reescritas À MÃO a partir do texto da coluna
`expression` do workbook `descritivo_das_variáveis_A41_v9.xlsx` (aba A41):
    * `ln` -> `math.log`, com a falha de domínio PREVISTA explicitamente (x <= 0);
    * condicionais por `if/elif` explícito, reproduzindo LITERALMENTE a cadeia do
      workbook: a ordem dos ramos (precedência LC > Overhaul/Parada > 1 By pass >
      1 By pass e LC), o `desconto_retirada_41d` só em L4_L5, as constantes
      100, 50, 14, 10, 24, 2 e o retorno "F";
    * mesma ordem de operações do texto (mesmas operações IEEE-754).

Este módulo NÃO importa `app/`, `tools/` nem os harnesses: só `math`, `re` e
`openpyxl` (para a guarda do texto). `WORKBOOK_TEXT` guarda o texto transcrito;
`check_workbook_text()` relê o workbook e falha se qualquer expressão divergir
(o oracle ficaria desatualizado).

Limitações (declaradas no fechamento): o oracle valida FIDELIDADE AO WORKBOOK, não
correção de negócio; e compartilha com o engine a LEITURA do workbook (o mesmo
texto é a fonte dos dois).

Entradas por nome do workbook e escopo:
    vazao_ltp[g], fator_retirada_cond_corr_lth[g], lth[L], valor_retirada[L], hes[L],
    desconto_retirada_41c[g], desconto_retirada_41d["L4_L5"]   (g em L1_L3, L4_L5, L6_L7)
"""

from __future__ import annotations

import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKBOOK = REPO / "data" / "workbooks" / "descritivo_das_variáveis_A41_v9.xlsx"
F = "F"
GROUPS = {"L1_L3": ("L1", "L2", "L3"), "L4_L5": ("L4", "L5"), "L6_L7": ("L6", "L7")}
GROUP_OF = {line: g for g, lines in GROUPS.items() for line in lines}


class DomainFailure(Exception):
    """Falha PREVISTA pelo oracle (o engine deve falhar de forma explícita no mesmo ponto)."""

    def __init__(self, kind: str, where: str):
        super().__init__(f"{kind} em {where}")
        self.kind = kind          # "LN_DOMAIN" | "DIVISION_BY_ZERO"
        self.where = where


class Stated:
    """Operando/resultado com estado (sem valor): propagação causal mínima do oracle."""

    def __init__(self, state: str, detail=None):
        self.state, self.detail = state, detail

    def __eq__(self, other):
        return isinstance(other, Stated) and (self.state, self.detail) == (other.state, other.detail)

    def __repr__(self):
        return f"Stated({self.state!r}, {self.detail!r})"


# ------------------------------------------------------------------ texto transcrito (guarda)
# (nome, frequência, escopo) -> texto da coluna `expression` do workbook (espaços normalizados).
WORKBOOK_TEXT = {
    ("retirada_cond_corr_ltp", "L1_L3"): "19.475*ln(vazao_ltp) - 85.999",
    ("retirada_cond_corr_ltp", "L4_L5"): "19.475*ln(vazao_ltp) - 85.999",
    ("retirada_cond_corr_ltp", "L6_L7"): "19.475*ln(vazao_ltp) - 85.999",
    ("lth_grupo", "L1_L3"): "( lth@L1 + lth@L2 + lth@L3 ) / 3",
    ("lth_grupo", "L4_L5"): "( lth@L4 + lth@L5 ) / 2",
    ("lth_grupo", "L6_L7"): "( lth@L6 + lth@L7 ) /2",
    ("retirada_cond_corr_lth", "L1_L3"): "19.475*ln(lth_grupo * fator_retirada_cond_corr_lth) - 85.999",
    ("retirada_cond_corr_lth", "L4_L5"): "19.475*ln(lth_grupo * fator_retirada_cond_corr_lth) - 85.999",
    ("retirada_cond_corr_lth", "L6_L7"): "19.475*ln(lth_grupo * fator_retirada_cond_corr_lth) - 85.999",
    ("retirada_condensado_grupo", "L1_L3"):
        "valor_retirada@L1 + valor_retirada@L2 + valor_retirada@L3 - 3*(retirada_cond_corr_ltp - retirada_cond_corr_lth)",
    ("retirada_condensado_grupo", "L4_L5"):
        '( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) if hes@L4 == "Normal" and hes@L5 == '
        '"Normal" else ( ( ( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) * 14 + ( (100 - '
        '((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) / 2 ) * 10 ) / 24 ) if hes@L4 == "LC" or hes@L5 '
        '== "LC" else ( 50 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2) ) if hes@L4 == '
        '"Overhaul/Parada" or hes@L5 == "Overhaul/Parada" else ( 100 - ((retirada_cond_corr_ltp - '
        'retirada_cond_corr_lth) * 2) - desconto_retirada_41d ) if hes@L4 == "1 By pass" or hes@L5 == "1 By pass" '
        'else ( ( ( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) * 14 + ( ( (100 - '
        '((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) - desconto_retirada_41c ) / 2 ) * 10 ) / 24 ) if '
        'hes@L4 == "1 By pass e LC" and hes@L5 == "1 By pass e LC" else "F" ) ) )',
    ("retirada_condensado_grupo", "L6_L7"):
        '( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) if hes@L6 == "Normal" and hes@L7 == '
        '"Normal" else ( ( ( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) * 14 + ( (100 - '
        '((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) / 2 ) * 10 ) / 24 ) if hes@L6 == "LC" or hes@L7 '
        '== "LC" else ( 50 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2) ) if hes@L6 == '
        '"Overhaul/Parada" or hes@L7 == "Overhaul/Parada" else ( 100 - ((retirada_cond_corr_ltp - '
        'retirada_cond_corr_lth) * 2) - desconto_retirada_41c ) if hes@L6 == "1 By pass" or hes@L7 == "1 By pass" '
        'else ( ( ( (100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) * 14 + ( ( (100 - '
        '((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)) - desconto_retirada_41c ) / 2 ) * 10 ) / 24 ) if '
        'hes@L6 == "1 By pass e LC" and hes@L7 == "1 By pass e LC" else "F" ) ) )',
    ("retirada_condensado_linha", "L1"): "( retirada_condensado_grupo@L1_L3 * lth@L1 ) / ( lth@L1 + lth@L2 + lth@L3 )",
    ("retirada_condensado_linha", "L2"): "( retirada_condensado_grupo@L1_L3 * lth@L2 ) / ( lth@L1 + lth@L2 + lth@L3 )",
    ("retirada_condensado_linha", "L3"): "( retirada_condensado_grupo@L1_L3 * lth@L3 ) / ( lth@L1 + lth@L2 + lth@L3 )",
    ("retirada_condensado_linha", "L4"): "( retirada_condensado_grupo@L4_L5 * lth@L4 ) / ( lth@L4 + lth@L5 )",
    ("retirada_condensado_linha", "L5"): "( retirada_condensado_grupo@L4_L5 * lth@L5 ) / ( lth@L4 + lth@L5 )",
    ("retirada_condensado_linha", "L6"): "( retirada_condensado_grupo@L6_L7 * lth@L6 ) / ( lth@L6 + lth@L7 )",
    ("retirada_condensado_linha", "L7"): "( retirada_condensado_grupo@L6_L7 * lth@L7 ) / ( lth@L6 + lth@L7 )",
    ("retirada_condensado_total", "L1_L7"):
        "retirada_condensado_grupo@L1_L3 + retirada_condensado_grupo@L4_L5 + retirada_condensado_grupo@L6_L7",
}
DECLARED_F_STATE = "NO_APPLICABLE_RULE"      # coluna declared_result_states: NO_APPLICABLE_RULE → "F"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read_workbook_expressions() -> tuple[dict, dict]:
    """{(nome, escopo): texto} das linhas diárias com expressão; {(nome, escopo): declared_result_states}."""
    import openpyxl
    sheet = openpyxl.load_workbook(WORKBOOK, read_only=True)["A41"]
    expressions, declared = {}, {}
    for row in sheet.iter_rows(min_row=3, values_only=True):
        if row[15] and row[7] == "diário":
            expressions[(row[1], row[9])] = normalize(row[15])
            if row[14]:
                declared[(row[1], row[9])] = row[14]
    return expressions, declared


def check_workbook_text() -> list[str]:
    """Guarda: o texto transcrito no oracle == texto atual do workbook (20 equações)."""
    expressions, declared = read_workbook_expressions()
    problems = []
    for identity in sorted(set(expressions) | set(WORKBOOK_TEXT)):
        got, want = expressions.get(identity), WORKBOOK_TEXT.get(identity)
        if got is None or want is None or normalize(want) != got:
            problems.append(f"ORACLE_STALE {identity}: workbook {got!r} != transcrito {want!r}")
    for identity in (("retirada_condensado_grupo", "L4_L5"), ("retirada_condensado_grupo", "L6_L7")):
        if declared.get(identity) != f'{DECLARED_F_STATE} → "F"':
            problems.append(f"ORACLE_STALE declared_result_states {identity}: {declared.get(identity)!r}")
    if len(expressions) != 20:
        problems.append(f"ORACLE_STALE {len(expressions)} expressões diárias no workbook != 20")
    return problems


# ------------------------------------------------------------------ primitivas
def ln(x, where):
    if isinstance(x, Stated):
        return x
    if x <= 0:
        raise DomainFailure("LN_DOMAIN", where)
    return math.log(x)


def div(a, b, where):
    if isinstance(a, Stated):
        return a
    if isinstance(b, Stated):
        return b
    if b == 0:
        raise DomainFailure("DIVISION_BY_ZERO", where)
    return a / b


def first_state(*values):
    """Propagação: o primeiro operando com estado (o oracle só gera estados de um único tipo)."""
    states = [v for v in values if isinstance(v, Stated)]
    if not states:
        return None
    if any(s != states[0] for s in states):
        raise DomainFailure("MULTI_STATE", "composição")
    return states[0]


# ------------------------------------------------------------------ as 20 equações (texto do workbook)
def retirada_cond_corr_ltp(vazao_ltp, where="retirada_cond_corr_ltp"):
    # 19.475*ln(vazao_ltp) - 85.999
    s = first_state(vazao_ltp)
    if s:
        return s
    return 19.475 * ln(vazao_ltp, where) - 85.999


def lth_grupo(group, lth):
    if group == "L1_L3":
        # ( lth@L1 + lth@L2 + lth@L3 ) / 3
        s = first_state(lth["L1"], lth["L2"], lth["L3"])
        return s or (lth["L1"] + lth["L2"] + lth["L3"]) / 3
    if group == "L4_L5":
        # ( lth@L4 + lth@L5 ) / 2
        s = first_state(lth["L4"], lth["L5"])
        return s or (lth["L4"] + lth["L5"]) / 2
    # ( lth@L6 + lth@L7 ) /2
    s = first_state(lth["L6"], lth["L7"])
    return s or (lth["L6"] + lth["L7"]) / 2


def retirada_cond_corr_lth(lth_g, fator, where="retirada_cond_corr_lth"):
    # 19.475*ln(lth_grupo * fator_retirada_cond_corr_lth) - 85.999
    s = first_state(lth_g, fator)
    if s:
        return s
    return 19.475 * ln(lth_g * fator, where) - 85.999


def retirada_condensado_grupo_l1_l3(valor_retirada, ltp, lth):
    # valor_retirada@L1 + valor_retirada@L2 + valor_retirada@L3 - 3*(retirada_cond_corr_ltp - retirada_cond_corr_lth)
    s = first_state(valor_retirada["L1"], valor_retirada["L2"], valor_retirada["L3"], ltp, lth)
    if s:
        return s
    return valor_retirada["L1"] + valor_retirada["L2"] + valor_retirada["L3"] - 3 * (ltp - lth)


def retirada_condensado_grupo_l4_l5(ltp, lth, hes_l4, hes_l5, desconto_41c, desconto_41d):
    """Cadeia LITERAL do workbook (L4_L5): o ramo `1 By pass` usa desconto_retirada_41d."""
    if isinstance(hes_l4, Stated) or isinstance(hes_l5, Stated):
        return first_state(hes_l4, hes_l5)          # condição avaliada com estado: o alvo herda
    if hes_l4 == "Normal" and hes_l5 == "Normal":
        operands = (ltp, lth)
        s = first_state(*operands)
        return s or (100 - ((ltp - lth) * 2))
    elif hes_l4 == "LC" or hes_l5 == "LC":
        s = first_state(ltp, lth)
        return s or (((100 - ((ltp - lth) * 2)) * 14 + ((100 - ((ltp - lth) * 2)) / 2) * 10) / 24)
    elif hes_l4 == "Overhaul/Parada" or hes_l5 == "Overhaul/Parada":
        s = first_state(ltp, lth)
        return s or (50 - ((ltp - lth) * 2))
    elif hes_l4 == "1 By pass" or hes_l5 == "1 By pass":
        s = first_state(ltp, lth, desconto_41d)
        return s or (100 - ((ltp - lth) * 2) - desconto_41d)
    elif hes_l4 == "1 By pass e LC" and hes_l5 == "1 By pass e LC":
        s = first_state(ltp, lth, desconto_41c)
        return s or (((100 - ((ltp - lth) * 2)) * 14 + (((100 - ((ltp - lth) * 2)) - desconto_41c) / 2) * 10) / 24)
    else:
        return F


def retirada_condensado_grupo_l6_l7(ltp, lth, hes_l6, hes_l7, desconto_41c):
    """Cadeia LITERAL do workbook (L6_L7): o ramo `1 By pass` usa desconto_retirada_41c."""
    if isinstance(hes_l6, Stated) or isinstance(hes_l7, Stated):
        return first_state(hes_l6, hes_l7)
    if hes_l6 == "Normal" and hes_l7 == "Normal":
        s = first_state(ltp, lth)
        return s or (100 - ((ltp - lth) * 2))
    elif hes_l6 == "LC" or hes_l7 == "LC":
        s = first_state(ltp, lth)
        return s or (((100 - ((ltp - lth) * 2)) * 14 + ((100 - ((ltp - lth) * 2)) / 2) * 10) / 24)
    elif hes_l6 == "Overhaul/Parada" or hes_l7 == "Overhaul/Parada":
        s = first_state(ltp, lth)
        return s or (50 - ((ltp - lth) * 2))
    elif hes_l6 == "1 By pass" or hes_l7 == "1 By pass":
        s = first_state(ltp, lth, desconto_41c)
        return s or (100 - ((ltp - lth) * 2) - desconto_41c)
    elif hes_l6 == "1 By pass e LC" and hes_l7 == "1 By pass e LC":
        s = first_state(ltp, lth, desconto_41c)
        return s or (((100 - ((ltp - lth) * 2)) * 14 + (((100 - ((ltp - lth) * 2)) - desconto_41c) / 2) * 10) / 24)
    else:
        return F


def declared(value):
    """declared_result_states: o literal "F" das duas variáveis de grupo vira NO_APPLICABLE_RULE (sem valor)."""
    return Stated(DECLARED_F_STATE) if value == F else value


def retirada_condensado_linha(line, grupo, lth):
    """( retirada_condensado_grupo@<grupo> * lth@Lx ) / ( soma dos lth do grupo )."""
    group = GROUP_OF[line]
    members = GROUPS[group]
    s = first_state(grupo, *(lth[m] for m in members))
    if s:
        return s
    if group == "L1_L3":
        denominator = lth["L1"] + lth["L2"] + lth["L3"]
    elif group == "L4_L5":
        denominator = lth["L4"] + lth["L5"]
    else:
        denominator = lth["L6"] + lth["L7"]
    return div(grupo * lth[line], denominator, f"retirada_condensado_linha@{line}")


def retirada_condensado_total(g13, g45, g67):
    # retirada_condensado_grupo@L1_L3 + retirada_condensado_grupo@L4_L5 + retirada_condensado_grupo@L6_L7
    s = first_state(g13, g45, g67)
    return s or (g13 + g45 + g67)


# ------------------------------------------------------------------ cadeia completa do dia
def evaluate_day(inputs: dict) -> dict:
    """
    inputs: {"vazao_ltp": {g: x}, "fator_retirada_cond_corr_lth": {g: x}, "lth": {L: x},
             "valor_retirada": {L1..L3: x}, "hes": {L4..L7: s}, "desconto_retirada_41c": {L4_L5, L6_L7},
             "desconto_retirada_41d": {"L4_L5": x}}
    Devolve {(nome, escopo): valor | Stated}. Levanta DomainFailure (falha prevista).
    """
    out = {}
    ltp, lth_g, lth_corr = {}, {}, {}
    for g in GROUPS:
        ltp[g] = out[("retirada_cond_corr_ltp", g)] = retirada_cond_corr_ltp(
            inputs["vazao_ltp"][g], f"retirada_cond_corr_ltp@{g}")
    for g in GROUPS:
        lth_g[g] = out[("lth_grupo", g)] = lth_grupo(g, inputs["lth"])
    for g in GROUPS:
        lth_corr[g] = out[("retirada_cond_corr_lth", g)] = retirada_cond_corr_lth(
            lth_g[g], inputs["fator_retirada_cond_corr_lth"][g], f"retirada_cond_corr_lth@{g}")
    hes, d41c = inputs["hes"], inputs["desconto_retirada_41c"]
    grupo = {
        "L1_L3": retirada_condensado_grupo_l1_l3(inputs["valor_retirada"], ltp["L1_L3"], lth_corr["L1_L3"]),
        "L4_L5": declared(retirada_condensado_grupo_l4_l5(ltp["L4_L5"], lth_corr["L4_L5"], hes["L4"], hes["L5"],
                                                          d41c["L4_L5"], inputs["desconto_retirada_41d"]["L4_L5"])),
        "L6_L7": declared(retirada_condensado_grupo_l6_l7(ltp["L6_L7"], lth_corr["L6_L7"], hes["L6"], hes["L7"],
                                                          d41c["L6_L7"])),
    }
    for g, value in grupo.items():
        out[("retirada_condensado_grupo", g)] = value
    for line in GROUP_OF:
        out[("retirada_condensado_linha", line)] = retirada_condensado_linha(line, grupo[GROUP_OF[line]],
                                                                             inputs["lth"])
    out[("retirada_condensado_total", "L1_L7")] = retirada_condensado_total(grupo["L1_L3"], grupo["L4_L5"],
                                                                            grupo["L6_L7"])
    return out


# ------------------------------------------------------------------ uma equação isolada (operandos diretos)
def evaluate_equation(name: str, scope: str, operands: dict):
    """
    Uma equação com os operandos DIRETOS do texto (nome[@escopo] -> valor), como o engine
    a avalia isoladamente. Devolve valor | Stated; levanta DomainFailure.
    """
    o = operands
    if name == "retirada_cond_corr_ltp":
        return retirada_cond_corr_ltp(o["vazao_ltp"], f"{name}@{scope}")
    if name == "lth_grupo":
        return lth_grupo(scope, {k.split("@")[1]: v for k, v in o.items()})
    if name == "retirada_cond_corr_lth":
        return retirada_cond_corr_lth(o["lth_grupo"], o["fator_retirada_cond_corr_lth"], f"{name}@{scope}")
    if name == "retirada_condensado_grupo" and scope == "L1_L3":
        return retirada_condensado_grupo_l1_l3({k.split("@")[1]: v for k, v in o.items() if k.startswith("valor")},
                                               o["retirada_cond_corr_ltp"], o["retirada_cond_corr_lth"])
    if name == "retirada_condensado_grupo" and scope == "L4_L5":
        return declared(retirada_condensado_grupo_l4_l5(o["retirada_cond_corr_ltp"], o["retirada_cond_corr_lth"],
                                                        o["hes@L4"], o["hes@L5"], o["desconto_retirada_41c"],
                                                        o["desconto_retirada_41d"]))
    if name == "retirada_condensado_grupo" and scope == "L6_L7":
        return declared(retirada_condensado_grupo_l6_l7(o["retirada_cond_corr_ltp"], o["retirada_cond_corr_lth"],
                                                        o["hes@L6"], o["hes@L7"], o["desconto_retirada_41c"]))
    if name == "retirada_condensado_linha":
        group = GROUP_OF[scope]
        return retirada_condensado_linha(scope, o[f"retirada_condensado_grupo@{group}"],
                                         {k.split("@")[1]: v for k, v in o.items() if k.startswith("lth@")})
    if name == "retirada_condensado_total":
        return retirada_condensado_total(o["retirada_condensado_grupo@L1_L3"], o["retirada_condensado_grupo@L4_L5"],
                                         o["retirada_condensado_grupo@L6_L7"])
    raise KeyError((name, scope))


# ------------------------------------------------------------------ agregação (AVERAGE, Policy B)
def average(values: list):
    """AVERAGE manual (soma / n). Qualquer componente com estado => o alvo herda o estado (Policy B)."""
    s = first_state(*values)
    if s:
        return s
    total = 0.0
    for v in values:
        total += v
    return total / len(values)
