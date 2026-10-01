"""
Stage 4B.3a — oracle temporal INDEPENDENTE (Python puro): calendário e aritmética de agregação.

NÃO importa `app/`, `tools/` nem os harnesses (só `datetime`, `calendar`, `json`). Recebe o store
como dicionário simples `{(entity, scope_type, scope_value, period_id, window_end): [tipo, repr, state, detail]}`
(o formato de evidência da 3.4C/4A) e os JSON dos seeds, e:

  * calcula, só com `datetime`/`calendar`, a janela de cada regra em cada data
    (mensal: 1º do mês -> data; anual: 1º de janeiro -> data; MOVING_AVERAGE: 1º do mês -> data);
  * recalcula TODAS as agregações a partir dos resultados DIÁRIOS brutos da execução
    (AVERAGE, SUM com integration_factor, WEIGHTED_AVERAGE, MOVING_AVERAGE), com a Policy B mínima
    (componente com estado => alvo com o estado, sem valor; estados/details diferentes => indefinido);
  * devolve o esperado para comparação com o resultado do engine.

Limitação declarada: valida COERÊNCIA TEMPORAL E ARITMÉTICA DE AGREGAÇÃO, não correção de negócio;
os resultados diários de entrada vêm do próprio engine.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "data" / "seed"
BLOCKS = ("production", "yield", "energy", "max_ht", "area_41")


class Undefined(Exception):
    """Composição sem contrato (estados ou details diferentes) — o engine deve falhar."""


# ------------------------------------------------------------------ calendário puro
def period_id(frequency: str, day: date) -> str:
    if frequency == "diário":
        return day.isoformat()
    if frequency == "mensal":
        return f"{day.year:04d}-{day.month:02d}"
    if frequency == "anual":
        return f"{day.year:04d}"
    raise ValueError(frequency)


def window(rule: dict, day: date) -> list[date]:
    """Datas de origem (diárias) que entram na agregação em `day`."""
    if rule["aggregation_type"] == "MOVING_AVERAGE" or rule["target_frequency"] == "mensal":
        start = date(day.year, day.month, 1)
    elif rule["target_frequency"] == "anual":
        start = date(day.year, 1, 1)
    else:
        raise ValueError(rule["aggregation_rule_id"])
    return [start + timedelta(days=n) for n in range((day - start).days + 1)]


def expected_window_count(frequency: str, day: date) -> int:
    return {"mensal": day.day, "anual": day.timetuple().tm_yday}[frequency]


def month_length(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


# ------------------------------------------------------------------ regras e escopos (dos seeds)
def scope_instances(scope_type, scope_value):
    if scope_type == "linha" and "_" in scope_value:
        a, b = (int(x[1:]) for x in scope_value.split("_"))
        return [(scope_type, f"L{i}") for i in range(a, b + 1)]
    return [(scope_type, scope_value)]


def load_rules() -> list[dict]:
    variables = {}
    rules = []
    for block in BLOCKS:
        for v in json.loads((SEED / block / "variables.json").read_text(encoding="utf-8")):
            variables[v["variable_id"]] = v
        rules += json.loads((SEED / block / "aggregation_rules.json").read_text(encoding="utf-8"))
    out = []
    for r in rules:
        target = variables[r["target_variable_id"]]
        for st, sv in scope_instances(target["scope_type"], target["scope_value"]):
            out.append({**r, "scope_type": st, "scope_value": sv,
                        "integration_factor": r.get("integration_factor", 1.0)})
    return out


# ------------------------------------------------------------------ aritmética pura (Policy B mínima)
def component(store: dict, variable: str, st, sv, day: date):
    """(valor, state, detail) do diário bruto; KeyError se ausente (lacuna)."""
    kind, text, state, detail = store[(variable, st, sv, day.isoformat(), None)]
    value = None if kind == "NoneType" else float(text)
    return value, state, detail


def compose(components: list):
    states = {(s, d) for _v, s, d in components if s is not None}
    if not states:
        return None
    if len({s for s, _d in states}) > 1 or len(states) > 1:
        raise Undefined(sorted(map(str, states)))
    return next(iter(states))


def aggregate(rule: dict, store: dict, day: date):
    """Esperado: ("VALUE", float) | ("STATE", (state, detail)) | ("UNDEFINED", motivo)."""
    st, sv = rule["scope_type"], rule["scope_value"]
    days = window(rule, day)
    sources = [component(store, rule["source_variable_id"], st, sv, d) for d in days]
    weights = ([component(store, rule["weight_variable_id"], st, sv, d) for d in days]
               if rule["aggregation_type"] == "WEIGHTED_AVERAGE" else [])
    try:
        state = compose(sources + weights)
    except Undefined as exc:
        return ("UNDEFINED", str(exc))
    if state is not None:
        return ("STATE", state)
    values = [v for v, _s, _d in sources]
    kind = rule["aggregation_type"]
    if kind == "SUM":
        if rule["integration_factor"] == 1:
            total = 0
            for v in values:
                total += v
            return ("VALUE", total)
        total = 0
        for v in values:
            total += v * rule["integration_factor"]
        return ("VALUE", total)
    if kind == "WEIGHTED_AVERAGE":
        w = [x for x, _s, _d in weights]
        weight_sum = 0
        for x in w:
            weight_sum += x
        weighted = 0
        for v, x in zip(values, w):
            weighted += v * x
        return ("VALUE", weighted / weight_sum)
    total = 0                                   # AVERAGE e MOVING_AVERAGE: média simples
    for v in values:
        total += v
    return ("VALUE", total / len(values))


def target_key(rule: dict, day: date):
    """Chave do resultado do engine: período da frequência de destino; janela = data (mensal/anual)."""
    frequency = rule["target_frequency"]
    window_end = None if frequency == "diário" else day.isoformat()
    return (rule["target_variable_id"], rule["scope_type"], rule["scope_value"], period_id(frequency, day), window_end)
