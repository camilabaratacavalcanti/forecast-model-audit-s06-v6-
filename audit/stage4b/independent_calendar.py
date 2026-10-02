"""
Stage 4B — recálculo INDEPENDENTE de calendário, identidades esperadas e análise estrutural de ciclos.

    python -I audit/stage4b/independent_calendar.py [--check]

Não importa `app/` nem `tools/` (verifica `sys.modules`). Usa só `datetime`/`calendar`, os JSON dos
seeds e `interblock_links.json`, e as funções puras de grafo de `audit/stage4a/independent_count.py`
(que também não importam `app/`).

1. calendário: datas de T1/T2/T3, dias por mês, dia do ano, bissexto, janelas esperadas por identidade;
2. identidades esperadas por data (derivadas diárias/mensais/anuais, entradas) e crescimento do store;
3. ciclos: grafo no nível de VARIÁVEL e de INSTÂNCIA (variável × escopo × período efetivo da data),
   componentes fortemente conexos por Tarjan próprio (sem o DependencyGraph do engine);
   ciclo entre BLOCOS (production <-> yield) reportado à parte;
4. defasagem: nenhuma referência a período anterior (t-1) na sintaxe das expressões.
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "audit" / "stage4a"))

import independent_count as base  # noqa: E402  (puro: sem app/)

EXPECTATIONS = base.bp.path("stage4b_contract", "contract_expectations_4b.json")   # Stage 4C: fonte via --baseline-dir
RANGES = {"T1": (date(2026, 1, 1), date(2027, 1, 31)), "T2": (date(2028, 1, 1), date(2028, 3, 2)),
          "T3": (date(2026, 1, 1), date(2028, 3, 2)), "4A": (date(2026, 1, 1), date(2026, 2, 1))}
LAG = re.compile(r"t\s*-\s*\d|\[\s*-?\d+\s*\]|\b(lag|prev|shift|anterior|offset)\s*\(", re.I)


# ------------------------------------------------------------------ calendário
def days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def expected_windows(day: date) -> dict:
    """Janelas por identidade na data: mensal = dia do mês; anual = dia do ano (início do período até a data)."""
    return {"monthly": day.day, "annual": day.timetuple().tm_yday,
            "month_length": calendar.monthrange(day.year, day.month)[1],
            "year_length": 366 if calendar.isleap(day.year) else 365,
            "month_end": day.day == calendar.monthrange(day.year, day.month)[1],
            "year_end": (day.month, day.day) == (12, 31)}


def calendar_summary(label: str) -> dict:
    start, end = RANGES[label]
    ds = days(start, end)
    months = sorted({(d.year, d.month) for d in ds})
    return {"dates": len(ds), "first": start.isoformat(), "last": end.isoformat(),
            "months": len(months), "years": sorted({d.year for d in ds}),
            "leap_years": sorted({d.year for d in ds if calendar.isleap(d.year)}),
            "feb_29_dates": [d.isoformat() for d in ds if (d.month, d.day) == (2, 29)],
            "month_lengths": {f"{y:04d}-{m:02d}": calendar.monthrange(y, m)[1] for y, m in months},
            "complete_months": sum(1 for y, m in months if date(y, m, 1) >= start
                                   and date(y, m, calendar.monthrange(y, m)[1]) <= end),
            "year_ends": [d.isoformat() for d in ds if (d.month, d.day) == (12, 31)],
            "month_ends": sum(1 for d in ds if expected_windows(d)["month_end"])}


# ------------------------------------------------------------------ identidades esperadas (dos seeds)
def identity_profile(cat) -> dict:
    nodes, deps, producers = base.graph(cat)
    targets = base.targets_of(nodes, base.BLOCKS5)
    selected, visited = base.closure(targets, deps, producers)
    produced = {nodes[k][2] for k in selected}
    inputs = visited - produced
    count = Counter()
    for variable in produced:
        v = cat["variables"][variable]
        count[("derived", v["frequency"])] += len(base.scope_instances(v["scope_type"], v["scope_value"]))
    for variable in inputs:
        v = cat["variables"][variable]
        count[("input", v["frequency"])] += len(base.scope_instances(v["scope_type"], v["scope_value"]))
    return {f"{k[0]}_{k[1]}": n for k, n in sorted(count.items())}


def store_growth(profile: dict, day: date, first: bool) -> int:
    """
    Chaves novas por data no contexto único (protocolo do fixture): derivadas diárias + 1 janela por
    identidade mensal/anual derivada + entradas diárias; entradas mensais no 1º dia executado do mês
    (ou da execução), anuais no 1º dia executado do ano.
    """
    keys = profile.get("derived_diário", 0) + profile.get("derived_mensal", 0) + profile.get("derived_anual", 0)
    keys += profile.get("input_diário", 0)
    if first or day.day == 1:
        keys += profile.get("input_mensal", 0)
    if first or (day.month, day.day) == (1, 1):
        keys += profile.get("input_anual", 0)
    return keys


# ------------------------------------------------------------------ ciclos
def tarjan(adjacency: dict) -> list[list]:
    """Componentes fortemente conexos (Tarjan iterativo)."""
    index, low, on_stack, stack, out = {}, {}, set(), [], []
    counter = [0]
    for root in sorted(adjacency, key=repr):
        if root in index:
            continue
        work = [(root, iter(sorted(adjacency.get(root, ()), key=repr)))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(adjacency.get(child, ()), key=repr))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    item = stack.pop()
                    on_stack.discard(item)
                    component.append(item)
                    if item == node:
                        break
                out.append(component)
    return out


def cyclic_components(adjacency: dict) -> list[list]:
    return [sorted(c, key=repr) for c in tarjan(adjacency)
            if len(c) > 1 or c[0] in adjacency.get(c[0], ())]


REFERENCE = re.compile(r"\b(VAR\d{5})(?:@(L\d(?:_L\d)?))?")


def instance_graph(cat) -> tuple[dict, dict]:
    """
    Nível de instância: nó = (variável, escopo concreto); toda aresta é na MESMA data de execução
    (período efetivo da data; a sintaxe não tem defasagem). Referência sem sufixo resolve para a
    mesma instância quando ela existe na variável referenciada, senão (sobre-aproximação
    conservadora) para TODAS as instâncias dela. Arestas: dependência -> dependente.
    """
    adjacency = defaultdict(set)
    instances = {v: base.scope_instances(d["scope_type"], d["scope_value"]) for v, d in cat["variables"].items()}

    def node(variable, scope):
        return (variable, scope)

    for e in cat["equations"].values():
        for scope in base.scope_instances(e["scope_type"], e["scope_value"]):
            target = node(e["target_variable_id"], scope)
            adjacency.setdefault(target, set())
            for variable, suffix in REFERENCE.findall(e["expression"]):
                if variable not in instances:
                    continue
                sources = [suffix] if suffix else ([scope] if scope in instances[variable] else instances[variable])
                for s in sources:
                    adjacency[node(variable, s)].add(target)
    for r in cat["rules"].values():
        for scope in instances[r["target_variable_id"]]:
            target = node(r["target_variable_id"], scope)
            adjacency.setdefault(target, set())
            for variable in filter(None, (r["source_variable_id"], r.get("weight_variable_id"))):
                sources = [scope] if scope in instances[variable] else instances[variable]
                for s in sources:
                    adjacency[node(variable, s)].add(target)
    for link in cat["links"]:
        for inst in link["instances"]:
            adjacency[node(link["source_definition"], inst["scope_value"])].add(
                node(link["consumer_definition"], inst["scope_value"]))
    variable_level = defaultdict(set)
    for (v, _s), targets in adjacency.items():
        for (w, _t) in targets:
            variable_level[v].add(w)
    return dict(adjacency), dict(variable_level)


def cycle_analysis(cat) -> dict:
    instance_adj, variable_adj = instance_graph(cat)
    block_adj = defaultdict(set)
    for v, targets in variable_adj.items():
        for w in targets:
            a, b = cat["block_of"].get(v), cat["block_of"].get(w)
            if a and b and a != b:
                block_adj[a].add(b)
    lag_hits = sorted(e["equation_id"] for e in cat["equations"].values() if LAG.search(e["expression"]))
    self_aggregations = sorted(r for r, x in cat["rules"].items() if x["source_variable_id"] == x["target_variable_id"])
    explicit_windows = sorted(r for r, x in cat["rules"].items() if x.get("window_start_date") or x.get("window_end_date"))
    return {
        "instance_nodes": len(set(instance_adj) | {t for ts in instance_adj.values() for t in ts}),
        "instance_edges": sum(len(t) for t in instance_adj.values()),
        "instance_cycles": cyclic_components(instance_adj),
        "variable_nodes": len(set(variable_adj) | {t for ts in variable_adj.values() for t in ts}),
        "variable_cycles": cyclic_components(variable_adj),
        "block_cycles": [sorted(c) for c in cyclic_components({k: v for k, v in block_adj.items()})],
        "block_edges": sorted([a, b] for a, ts in block_adj.items() for b in ts),
        "lag_references": lag_hits, "self_aggregations": self_aggregations, "explicit_windows": explicit_windows,
        "temporal_edges": "agregações leem apenas sub-períodos <= data de execução da mesma variável-fonte; "
                          "nenhuma equação lê período anterior",
    }


def main() -> int:
    cat = base.catalog()
    profile = identity_profile(cat)
    out = {"calendar": {label: calendar_summary(label) for label in RANGES},
           "identity_profile": profile,
           "store_growth_first_day": store_growth(profile, date(2026, 1, 1), True),
           "store_growth_regular_day": store_growth(profile, date(2026, 1, 2), False),
           "store_growth_first_of_month": store_growth(profile, date(2026, 2, 1), False),
           "store_growth_new_year": store_growth(profile, date(2027, 1, 1), False),
           "expected_windows_samples": {d: expected_windows(date.fromisoformat(d)) for d in (
               "2026-01-31", "2026-02-28", "2026-03-01", "2026-04-30", "2026-12-31", "2027-01-01",
               "2028-02-28", "2028-02-29", "2028-03-01", "2028-12-31")},
           "cycles": cycle_analysis(cat)}
    imported = sorted(m for m in sys.modules if m == "app" or m.startswith(("app.", "tools")))
    problems = [f"INDEPENDENCE_FAILURE {imported}"] if imported else []
    if out["cycles"]["instance_cycles"]:
        problems.append(f"INSTANCE_CYCLE {out['cycles']['instance_cycles'][:3]}")
    if "--check" in sys.argv[1:]:
        expected = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))["independent"]
        for path, want in expected.items():
            got = out
            for part in path.split("."):
                got = got[part]
            if json.loads(json.dumps(got)) != want:
                problems.append(f"EXPECTATION_DIVERGENCE {path}: {got!r} != {want!r}")
    out["imports_app_or_tools"] = imported
    out["problems"] = problems
    out["result"] = "PASS" if not problems else "FAIL"
    print(json.dumps(out, indent=1, ensure_ascii=False, default=list))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
