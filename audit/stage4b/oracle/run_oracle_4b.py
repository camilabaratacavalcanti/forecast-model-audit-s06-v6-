"""
Stage 4B.3a — confronto ENGINE x ORACLE TEMPORAL (REAL_DERIVED_TEST_RESULT).

    python audit/stage4b/oracle/run_oracle_4b.py [--no-write] [--ranges T1,T2]

O engine executa T1 (2026-01-01 -> 2027-01-31) e T2 (2028-01-01 -> 2028-03-02) no grafo de 5 blocos
(4A, DR-4A-5); o oracle puro (`oracle_temporal.py`, sem app/) recalcula:
  * janelas/identidades por data só com datetime/calendar (contagem de janelas de cada identidade
    mensal/anual = dia do mês/ano; nenhuma janela fora do período);
  * TODAS as agregações (207 regras, 417 instâncias) em TODAS as datas a partir dos diários brutos.
Mais uma execução curta com estado (Policy B), para comparar resultados com estado.
Tolerância (DR-4B-8): math.isclose(rel_tol=1e-12, abs_tol=1e-12); reporta igualdade bit a bit.
"""

from __future__ import annotations

import ast
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
sys.path[:0] = [str(REPO / "audit" / "stage4a"), str(STAGE), str(HERE)]

import common  # noqa: E402
import independent_calendar as cal  # noqa: E402
import oracle_temporal as oracle  # noqa: E402

from app.domain.results import Result  # noqa: E402

ri = common.ri
EVIDENCE = HERE / "evidence"
REL_TOL = ABS_TOL = 1e-12


def oracle_is_pure() -> list[str]:
    tree = ast.parse((HERE / "oracle_temporal.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    extra = imported - {"__future__", "calendar", "json", "datetime", "pathlib"}
    return [f"ORACLE_IMPURE importa {sorted(extra)}"] if extra else []


def engine_result(store, key):
    kind, text, state, detail = store[key]
    if state is not None:
        return ("STATE", (state, detail)) if kind == "NoneType" else ("STATE_WITH_VALUE", (state, detail, text))
    return ("VALUE", float(text))


def compare(got, expected) -> tuple[bool, bool]:
    if got[0] != expected[0]:
        return False, False
    if got[0] == "VALUE":
        return math.isclose(got[1], expected[1], rel_tol=REL_TOL, abs_tol=ABS_TOL), got[1] == expected[1]
    return got[1] == expected[1], got[1] == expected[1]


def check_range(store: dict, days: list[date], rules: list[dict]) -> tuple[dict, list[str]]:
    problems = []
    by_type = defaultdict(Counter)
    exact = 0
    for rule in rules:
        for day in days:
            expected = oracle.aggregate(rule, store, day)
            key = oracle.target_key(rule, day)
            if key not in store:
                problems.append(f"ORACLE_MISSING {key}")
                continue
            ok, bitwise = compare(engine_result(store, key), expected)
            by_type[rule["aggregation_type"]]["compared"] += 1
            by_type[rule["aggregation_type"]]["agree"] += ok
            by_type[rule["aggregation_type"]]["state"] += expected[0] == "STATE"
            exact += bitwise
            if not ok and len(problems) < 20:
                problems.append(f"ORACLE_MISMATCH {rule['aggregation_rule_id']} {rule['scope_value']} {day}: "
                                f"engine {engine_result(store, key)} != oracle {expected}")
    # calendário: janelas por identidade = dia do mês / dia do ano; nada fora do período
    windows = defaultdict(set)
    for k in store:
        if k[4] is not None:
            windows[k[:4]].add(k[4])
    last = days[-1]
    calendar_problems = 0
    for (entity, st, sv, period), ws in windows.items():
        frequency = "mensal" if len(period) == 7 else "anual"
        in_range = [d for d in days if oracle.period_id(frequency, d) == period]
        expected_ws = {d.isoformat() for d in in_range}
        if ws != expected_ws:
            calendar_problems += 1
            if len(problems) < 40:
                problems.append(f"ORACLE_CALENDAR {entity} {sv} {period}: {len(ws)} janelas != {len(expected_ws)}")
        if in_range and in_range[-1] == last and len(ws) != oracle.expected_window_count(frequency, last) and \
                in_range[0] == (date(last.year, last.month, 1) if frequency == "mensal" else date(last.year, 1, 1)):
            calendar_problems += 1
    summary = {"aggregations": {k: dict(v) for k, v in sorted(by_type.items())},
               "compared": sum(v["compared"] for v in by_type.values()),
               "agree": sum(v["agree"] for v in by_type.values()), "bitwise_equal": exact,
               "windowed_identities": len(windows), "calendar_mismatches": calendar_problems}
    return summary, problems


def main() -> int:
    ranges = (sys.argv[sys.argv.index("--ranges") + 1].split(",") if "--ranges" in sys.argv else ["T1", "T2"])
    problems = oracle_is_pure()
    rules = oracle.load_rules()
    out = {"label": common.LABEL,
           "oracle": "INDEPENDENT_TEMPORAL_ORACLE (calendário + aritmética de agregação)",
           "tolerance": {"rel_tol": REL_TOL, "abs_tol": ABS_TOL, "states": "igualdade exata"},
           "limitations": ["valida coerência temporal e aritmética de agregação, não correção de negócio",
                           "os resultados diários que alimentam as agregações vêm do próprio engine"],
           "rules": len({r["aggregation_rule_id"] for r in rules}), "rule_instances": len(rules),
           "by_range": {}}
    for label in ranges:
        days = cal.days(*cal.RANGES[label])
        universe = common.Universe("A")
        context, _ = universe.run_sequence(days)
        summary, p = check_range(ri.store_of(context), days, rules)
        out["by_range"][label] = {"dates": len(days), **summary}
        problems += p
    # Policy B: estado num diário-fonte em 2026-01-03 (valor_retirada@L1 e entrada de energy), 10 datas
    days = cal.days(date(2026, 1, 1), date(2026, 1, 10))
    universe = common.Universe("A")

    def inject(d):
        if d == date(2026, 1, 3):
            return [("VAR16017", "linha", "L1", d.isoformat(), Result(None, "INVALID_INPUT", "o")),
                    ("VAR18046", "linha_grupo", "L1_L7", d.isoformat(), Result(None, "INVALID_INPUT", "o"))]
        return []
    try:
        context, _ = universe.run_sequence(days, None, inject)
        summary, p = check_range(ri.store_of(context), days, rules)
        out["by_range"]["STATED_2026-01-01_10"] = {"dates": len(days), **summary}
        problems += p
        if summary["aggregations"].get("AVERAGE", {}).get("state", 0) == 0:
            problems.append("ORACLE_COVERAGE nenhum resultado com estado comparado")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"ORACLE_STATED_RUN_FAILED {type(exc).__name__}: {str(exc)[:160]}")
    out["compared"] = sum(r["compared"] for r in out["by_range"].values())
    out["agree"] = sum(r["agree"] for r in out["by_range"].values())
    out["bitwise_equal"] = sum(r["bitwise_equal"] for r in out["by_range"].values())
    out["types_covered"] = sorted({t for r in out["by_range"].values() for t in r["aggregations"]})
    if out["types_covered"] != ["AVERAGE", "MOVING_AVERAGE", "SUM", "WEIGHTED_AVERAGE"]:
        problems.append(f"ORACLE_COVERAGE tipos {out['types_covered']}")
    out["problems"] = problems
    out["result"] = "PASS" if not problems else "FAIL"
    if "--no-write" not in sys.argv[1:]:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / "oracle_temporal_summary.json").write_text(
            json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
