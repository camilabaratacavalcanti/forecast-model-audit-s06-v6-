"""
Stage 4B.2 — harness temporal anual: ano completo, virada de ano e ano bissexto (REAL_DERIVED_TEST_RESULT).

    python audit/stage4b/temporal/run_temporal_4b.py --range T1|T2|T3 [--no-write] [--order A|B]
                                                   [--hashseed N] [--log arquivo] [--skip-extras]
    python audit/stage4b/temporal/run_temporal_4b.py --range T2 --fingerprint     (uso interno: determinismo)

Reutiliza por IMPORT o universo de 5 blocos da 4A (`audit/stage4a/common.py`: fixture REAL_DERIVED +
protocolo de entradas DR-4A-5) e os auditores da 3.4C/3.4D (`checks.py`), sem modificá-los.

Verificações em TODAS as datas do intervalo (contexto único):
  * alvos (446), nós na ordem do plano (458, contagem de eventos), 13 transferências / 67 eventos
    (consumidor == produtor, sem duplicidade), identidade temporal de cada evento de alvo;
  * janelas: cada identidade mensal derivada tem exatamente "dia do mês" janelas; cada anual, "dia do ano";
  * crescimento do store = previsto pelos seeds (1227 / 1143 / 1109 chaves);
  * MOVING_AVERAGE reinicia no dia 1 (valor do alvo == valor da origem no dia 1);
  * fechamento: snapshot (hash) de cada mês e de cada ano no momento da virada == ao fim da execução.
Depois da sequência: reexecução idempotente de datas amostradas; conflito de entrada a montante de
transferência; E3 na virada do ano (T1/T3); invariante de prefixo contra a evidência 4A (T1/T3);
cenários de estado ao longo do ano (T1/T3: execução gêmea com injeções); determinismo (subprocessos).

Escrita atômica: a evidência só é gravada (em `evidence/<range>/`) quando a execução termina; uma
interrupção não corrompe a evidência anterior. Progresso em `--log` (ou stderr).
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
sys.path[:0] = [str(REPO / "audit" / "stage4a"), str(REPO / "audit" / "stage4a" / "integrated"), str(STAGE)]

import common  # noqa: E402  (4A, sem alteração)
import independent_calendar as cal  # noqa: E402

from app.domain.results import Result  # noqa: E402
from app.engine.interblock_orchestrator import TRANSFER  # noqa: E402

import checks  # noqa: E402  (3.4C/3.4D, sem alteração)

ri = common.ri
EXPECTED = json.loads((STAGE / "contract_expectations_4b.json").read_text(encoding="utf-8"))["temporal"]
EVIDENCE = HERE / "evidence"
INV = "INVALID_INPUT"
MA_RULES = ("AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE",
            "AGR-ENERGY-PRODUCAO_PLANTA_T_H_MEDIA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE")
STATE_DETAIL = "4b"


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def prefix_snapshot(store: dict, prefix: str) -> list:
    keys = sorted((list(k), v) for k, v in store.items() if (k[3] or "").startswith(prefix))
    return [len(keys), sha(keys)]


def date_range(label: str) -> list[date]:
    start, end = (date.fromisoformat(x) for x in EXPECTED["ranges"][label])
    return cal.days(start, end)


class Log:
    def __init__(self, path):
        self.handle = open(path, "a", encoding="utf-8") if path else sys.stderr

    def __call__(self, message: str):
        self.handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
        self.handle.flush()


# ------------------------------------------------------------------ execução com verificação por data
class Runner:
    def __init__(self, order: str = "A"):
        self.universe = common.Universe(order)
        u = self.universe
        o, plan = u.orchestrator, u.plan
        self.planned = [s.key for s in plan.steps]
        self.events, self.instances = ri.node_expectations(o, plan)
        self.transfer_expected = ri.transfer_expectations(o, plan)
        self.transfer_nodes = {k for k in self.planned if k.startswith(TRANSFER)}
        self.targets = set(plan.targets)
        vd = o.catalog.variable_definitions
        derived = ri.derived_variables(plan)
        self.monthly_ids, self.annual_ids = [], []
        for variable in sorted(derived):
            d = vd.get(variable)
            scopes = common.ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)
            if d.frequency == "mensal":
                self.monthly_ids += [(variable, st, sv) for st, sv in scopes]
            elif d.frequency == "anual":
                self.annual_ids += [(variable, st, sv) for st, sv in scopes]
        rules = {i.rule.aggregation_rule_id: i for i in o.catalog.aggregation_rule_instances.all()}
        self.ma = [(i.rule.source_variable_id, i.rule.target_variable_id, i.scope_type, i.scope_value)
                   for i in o.catalog.aggregation_rule_instances.all() if i.rule.aggregation_rule_id in MA_RULES]
        del rules

    def check_day(self, context, day: date, trace, first: bool) -> tuple[dict, list[str]]:
        o = self.universe.orchestrator
        iso = day.isoformat()
        problems = []
        executed, written, records, _cov, observed = ri.observe(o, context, {day: trace})
        problems += observed
        problems += checks.check_targets(self.instances, written)
        problems += checks.check_nodes(self.planned, self.events, executed)
        problems += checks.check_transfers(records, self.transfer_nodes, self.transfer_expected)
        problems += checks.check_target_identities(
            ri.target_records({day: trace}, self.targets), ri.expected_periods(o, self.targets, [day]))
        month, year = f"{day.year:04d}-{day.month:02d}", f"{day.year:04d}"
        expected = cal.expected_windows(day)
        monthly = Counter(len(context.result_windows(v, st, sv, month)) for v, st, sv in self.monthly_ids)
        annual = Counter(len(context.result_windows(v, st, sv, year)) for v, st, sv in self.annual_ids)
        if monthly != Counter({expected["monthly"]: len(self.monthly_ids)}):
            problems.append(f"TEMPORAL_FAILURE {iso} janelas mensais {dict(monthly)} != {expected['monthly']}")
        if annual != Counter({expected["annual"]: len(self.annual_ids)}):
            problems.append(f"TEMPORAL_FAILURE {iso} janelas anuais {dict(annual)} != {expected['annual']}")
        if day.day == 1:
            for source, target, st, sv in self.ma:
                a = context.get_variable_result(source, st, sv, iso)
                b = context.get_variable_result(target, st, sv, iso)
                if a.state is None and (b.value != a.value or b.state is not None):
                    problems.append(f"MOVING_AVERAGE_NOT_RESET {iso} {target} {sv}: {b} != origem {a}")
        row = {"date": iso, "events": len(trace.events), "transfer_events": len(trace.of_kind(TRANSFER)),
               "nodes": len(executed[iso]), "targets": len(written[iso]),
               "monthly_identities": len(self.monthly_ids), "monthly_windows_each": expected["monthly"],
               "annual_identities": len(self.annual_ids), "annual_windows_each": expected["annual"],
               "month_end": expected["month_end"], "year_end": expected["year_end"]}
        if (row["events"], row["transfer_events"], row["nodes"], row["targets"]) != (
                EXPECTED["events_per_date"], EXPECTED["transfer_events_per_date"], EXPECTED["planner_nodes"],
                EXPECTED["targets"]):
            problems.append(f"TEMPORAL_FAILURE {iso} plano incompleto {row}")
        if len({r['node'] for r in records}) != EXPECTED["transfers_per_date"]:
            problems.append(f"INTERBLOCK_FAILURE {iso} transferências != 13")
        return row, problems


def run_range(label: str, order: str, log: Log, keep_traces: set) -> dict:
    runner = Runner(order)
    u = runner.universe
    context = u.fresh_context()
    days = date_range(label)
    problems, rows, perf, snapshots, kept = [], [], [], {}, {}
    growth_expected = cal.identity_profile(cal.base.catalog())
    events_digest = hashlib.sha256()
    previous_size = 0
    t0 = time.perf_counter()
    for n, day in enumerate(days):
        if n and day.day == 1:                                  # virada de mês: snapshot do mês encerrado
            closed = days[n - 1]
            store = ri.store_of(context)
            snapshots[f"{closed.year:04d}-{closed.month:02d}"] = prefix_snapshot(store, f"{closed.year:04d}-{closed.month:02d}")
            if day.month == 1:
                snapshots[f"{closed.year:04d}"] = prefix_snapshot(store, f"{closed.year:04d}")
        t = time.perf_counter()
        trace = u.execute_day(context, day)
        elapsed = time.perf_counter() - t
        row, p = runner.check_day(context, day, trace, n == 0)
        problems += p
        size = len(context._scoped_results)
        want = cal.store_growth(growth_expected, day, n == 0)
        if size - previous_size != want:
            problems.append(f"STORE_GROWTH {day} {size - previous_size} != {want}")
        row.update({"store_keys": size, "new_keys": size - previous_size, "expected_new_keys": want})
        previous_size = size
        rows.append(row)
        perf.append({"date": day.isoformat(), "seconds": round(elapsed, 4), "store_keys": size})
        events_digest.update(sha(sorted(map(tuple, ri.events_of(trace)), key=lambda e: e[1:])).encode())
        if day.isoformat() in keep_traces:
            kept[day.isoformat()] = ri.events_of(trace)
        if n % 30 == 0 or n == len(days) - 1:
            log(f"{label} {order} {day} ({n + 1}/{len(days)}) store={size} problemas={len(problems)} "
                f"{time.perf_counter() - t0:.0f}s")
    store = ri.store_of(context)
    closure = {}
    for period, snap in snapshots.items():
        now = prefix_snapshot(store, period)
        closure[period] = {"at_turn": snap, "at_end": now, "unchanged": now == snap}
        if now != snap:
            problems.append(f"CLOSED_PERIOD_CHANGED {period}: {snap} -> {now}")
    first32 = [p["seconds"] for p in perf[:32]]
    last32 = [p["seconds"] for p in perf[-32:]]
    ratio = (sum(last32) / len(last32)) / (sum(first32) / len(first32))
    return {"runner": runner, "context": context, "rows": rows, "perf": perf, "snapshots": closure,
            "kept": kept, "problems": problems, "store": store,
            "fingerprint": {"order": order, "hash_seed": os.environ.get("PYTHONHASHSEED"),
                            "results_sha256": sha([ri.store_sha(context), events_digest.hexdigest()]),
                            "store_sha256": ri.store_sha(context), "dates": len(days),
                            "plan_order": sha([s.key for s in u.plan.steps])},
            "performance": {"dates": len(days), "total_seconds": round(time.perf_counter() - t0, 1),
                            "mean_first_32": sum(first32) / len(first32), "mean_last_32": sum(last32) / len(last32),
                            "ratio_last_over_first": ratio, "store_keys_final": len(store)}}


# ------------------------------------------------------------------ verificações depois da sequência
def reexecution(result: dict) -> tuple[dict, list[str]]:
    u, context = result["runner"].universe, result["context"]
    out, problems = {}, []
    for iso, first in sorted(result["kept"].items()):
        day = date.fromisoformat(iso)
        before = ri.store_of(context)
        trace = u.execute_day(context, day)
        after = ri.store_of(context)
        again = ri.events_of(trace)
        problems += checks.check_reexecution(iso, before, after, first, again)
        out[iso] = {"same_store": before == after, "new_keys": len(set(after) - set(before)),
                    "first_run_transfer_statuses": dict(Counter(e[8] for e in first if e[1] == TRANSFER)),
                    "transfer_statuses": dict(Counter(e[8] for e in again if e[1] == TRANSFER))}
    # entrada diferente a montante da transferência VAR11031 (production.VAR12031 -> yield) na reexecução
    iso = sorted(result["kept"])[0]
    day = date.fromisoformat(iso)
    trial = copy.deepcopy(context)
    u.seed_inputs(trial, day)
    for sv in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        trial.set_variable_result("VAR12054", Result(5.0), "linha", sv, iso)
    code = None
    try:
        u.orchestrator.execute(u.plan, trial, day)
    except Exception as exc:  # noqa: BLE001 — o código é a evidência
        code = getattr(exc, "code", type(exc).__name__)
    out["conflict_on_changed_upstream_input"] = {"date": iso, "changed": "VAR12054 (diário, a montante de VAR12031)",
                                                 "error": code}
    if code != "INTERBLOCK_CONSUMER_VALUE_CONFLICT":
        problems.append(f"REEXECUTION_FAILURE conflito não detectado: {code}")
    return out, problems


def missing_new_year_input(label: str) -> tuple[dict, list[str]]:
    """E3 na virada: contexto até a véspera do ano novo; sem a entrada anual do novo ano -> falha explícita."""
    days = date_range(label)
    turn = next((d for d in days if (d.month, d.day) == (1, 1) and d != days[0]), None)
    if turn is None:
        return {"applicable": False}, []
    u = common.Universe("A")
    context, _ = u.run_sequence([d for d in days if d < turn])
    u.seed_inputs(context, turn)
    removed = [k for k in list(context._scoped_results) if k.entity_id == "VAR12066" and k.period_id == f"{turn.year}"]
    for k in removed:
        del context._scoped_results[k]
    try:
        u.orchestrator.execute(u.plan, context, turn)
        error = None
    except Exception as exc:  # noqa: BLE001
        error = {"type": type(exc).__name__, "message": str(exc)[:200]}
    out = {"applicable": True, "date": turn.isoformat(), "removed": "VAR12066 (lth_meta, anual) do novo ano",
           "removed_keys": len(removed), "previous_year_value_exists": any(
               k.entity_id == "VAR12066" and k.period_id == f"{turn.year - 1}" for k in context._scoped_results),
           "error": error}
    return out, ([] if error else ["CARRY_OVER entrada anual ausente não falhou"])


def prefix_invariant(store: dict) -> tuple[dict, list[str]]:
    """T1/T3 nas 32 primeiras datas == evidência 4A (hash versionado + execução 4A chave a chave)."""
    committed = json.loads((REPO / "audit/stage4a/integrated/evidence/integrated_summary.json").read_text(encoding="utf-8"))
    reference = committed["determinism"]["RUN_A"]["store_sha256"]
    u = common.Universe("A")
    context4a, _ = u.run_sequence(common.DAYS)
    store4a = ri.store_of(context4a)
    last = common.DAYS[-1].isoformat()

    def in_prefix(k):
        if k[4] is not None:
            return k[4] <= last
        period = k[3] or ""
        return period <= last if len(period) == 10 else period in ("2026-01", "2026-02", "2026")

    subset = {k: v for k, v in store.items() if in_prefix(k)}
    different = sorted((k for k in set(subset) | set(store4a) if subset.get(k) != store4a.get(k)), key=repr)
    out = {"reference_4a_store_sha256": reference, "recomputed_4a_store_sha256": ri.store_sha(context4a),
           "prefix_subset_sha256": ri.sha(sorted([list(k), v] for k, v in subset.items())),
           "keys_compared": len(store4a), "differences": len(different), "first_differences": [list(k) for k in different[:3]]}
    problems = []
    if out["recomputed_4a_store_sha256"] != reference:
        problems.append("PREFIX_INVARIANT execução 4A recalculada != evidência 4A versionada")
    if different or out["prefix_subset_sha256"] != reference:
        problems.append(f"PREFIX_INVARIANT {len(different)} diferenças nas 32 primeiras datas")
    return out, problems


def state_scenarios(label: str, clean_store: dict) -> tuple[dict, list[str]]:
    """
    Execução gêmea do intervalo com três injeções (mesmo estado/detail para não criar composição indefinida):
      S1 valor_retirada@L1 (VAR16017) em 2026-03-10 -> mensal de março e anual de 2026 SÓ a partir de 03-10;
      S2 hes@L6 (VAR16021) em 2026-12-31 -> anual de 2026 (L6_L7) em 12-31; nada em 2027;
      S3 hes@L4 (VAR16021) em 2027-01-01 -> 2027 (L4_L5); o 2026 de L4_L5 continua limpo.
    """
    days = date_range(label)
    injections = {date(2026, 3, 10): ("VAR16017", "linha", "L1"), date(2026, 12, 31): ("VAR16021", "linha", "L6"),
                  date(2027, 1, 1): ("VAR16021", "linha", "L4")}

    def inject(d):
        if d in injections:
            v, st, sv = injections[d]
            return [(v, st, sv, d.isoformat(), Result(None, INV, STATE_DETAIL))]
        return []
    u = common.Universe("A")
    context, _ = u.run_sequence(days, None, inject)
    stated = ri.store_of(context)
    descendants = ri.descendants_of(u.orchestrator, {"VAR16017", "VAR16021"})

    def k(v, sv, period, window=None):
        st = "linha" if len(sv) == 2 else "linha_grupo"
        return (v, st, sv, period, window)

    def windows(v, sv, period):
        return sorted(key for key in stated if key[0] == v and key[2] == sv and key[3] == period and key[4])

    mar = windows("VAR16019", "L1_L3", "2026-03")
    ann26_13 = windows("VAR16020", "L1_L3", "2026")
    must = [w for w in mar if w[4] >= "2026-03-10"] + [w for w in ann26_13 if w[4] >= "2026-03-10"]
    plain = ([w for w in mar if w[4] < "2026-03-10"] + windows("VAR16019", "L1_L3", "2026-04")
             + [w for w in ann26_13 if w[4] < "2026-03-10"] + windows("VAR16020", "L1_L3", "2027"))
    ann26_67 = windows("VAR16030", "L6_L7", "2026")
    must += [w for w in ann26_67 if w[4] == "2026-12-31"] + [k("VAR16029", "L6_L7", "2026-12", "2026-12-31")]
    plain += ([w for w in ann26_67 if w[4] < "2026-12-31"] + windows("VAR16030", "L6_L7", "2027")
              + windows("VAR16029", "L6_L7", "2027-01"))
    must += windows("VAR16027", "L4_L5", "2027") + windows("VAR16026", "L4_L5", "2027-01")
    plain += windows("VAR16027", "L4_L5", "2026") + windows("VAR16026", "L4_L5", "2026-12")
    problems = checks.check_state_diff(clean_store, stated, descendants, INV, STATE_DETAIL)
    problems += checks.check_expectations(stated, must, plain, INV, STATE_DETAIL)
    problems += checks.check_result_contract(stated)
    l45_2026 = {key: v for key, v in stated.items() if key[2] in ("L4_L5", "L4", "L5") and (key[3] or "").startswith("2026")}
    clean_l45_2026 = {key: v for key, v in clean_store.items() if key in l45_2026}
    if l45_2026 != clean_l45_2026:
        problems.append("STATE_LEAK S3 (2027-01-01) alterou o 2026 de L4_L5")
    return {"injections": {d.isoformat(): list(v) for d, v in injections.items()},
            "must_keys": len(must), "plain_keys": len(plain),
            "differing_keys": sum(1 for key in clean_store if clean_store[key] != stated.get(key)),
            "stated_variables": sorted({key[0] for key, v in stated.items() if v[2] is not None}),
            "l4_l5_2026_keys_identical_to_clean": l45_2026 == clean_l45_2026,
            "problems": problems}, problems


def fingerprint_subprocess(label: str, order: str, seed: str) -> dict:
    out = subprocess.run([sys.executable, str(HERE / "run_temporal_4b.py"), "--range", label, "--order", order,
                          "--fingerprint"], cwd=REPO, capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONHASHSEED": seed})
    return json.loads(out.stdout.strip().splitlines()[-1])


def write_atomic(target: Path, files: dict) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="stage4b_", dir=str(HERE)))
    try:
        for name, content in files.items():
            (tmp / name).write_text(content, encoding="utf-8")
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            os.replace(tmp / name, target / name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def csv_text(rows: list[dict]) -> str:
    import io
    buffer = io.StringIO()
    w = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", default="T2", choices=("T1", "T2", "T3"))
    parser.add_argument("--order", default="A", choices=("A", "B"))
    parser.add_argument("--hashseed")
    parser.add_argument("--log")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--fingerprint", action="store_true")
    parser.add_argument("--skip-extras", action="store_true", help="só a sequência e as verificações por data")
    args = parser.parse_args()
    if args.hashseed is not None and os.environ.get("PYTHONHASHSEED") != args.hashseed:
        os.execve(sys.executable, [sys.executable, *sys.argv], {**os.environ, "PYTHONHASHSEED": args.hashseed})
    log = Log(args.log)
    label = args.range
    samples = set(EXPECTED["reexecution_dates"]) & {d.isoformat() for d in date_range(label)}
    result = run_range(label, args.order, log, set() if args.fingerprint else samples)
    if args.fingerprint:
        print(json.dumps(result["fingerprint"], sort_keys=True))
        return 0
    problems = list(result["problems"])
    summary = {"label": common.LABEL, "range": label, "order": args.order,
               "dates": {"first": result["rows"][0]["date"], "last": result["rows"][-1]["date"],
                         "count": len(result["rows"])},
               "per_date": {"targets": sorted({r["targets"] for r in result["rows"]}),
                            "nodes": sorted({r["nodes"] for r in result["rows"]}),
                            "events": sorted({r["events"] for r in result["rows"]}),
                            "transfer_events": sorted({r["transfer_events"] for r in result["rows"]})},
               "month_ends": [r["date"] for r in result["rows"] if r["month_end"]],
               "year_ends": [r["date"] for r in result["rows"] if r["year_end"]],
               "identities": {"monthly": len(result["runner"].monthly_ids), "annual": len(result["runner"].annual_ids)},
               "performance": result["performance"], "fingerprint": result["fingerprint"]}
    if result["performance"]["ratio_last_over_first"] > EXPECTED["performance_ratio_limit"]:
        summary["performance_followup"] = "REQUIRES_FOLLOWUP: razão acima do limite"
    extras = {}
    if not args.skip_extras:
        log(f"{label} reexecução e conflito")
        extras["reexecution"], p = reexecution(result)
        problems += p
        log(f"{label} E3 na virada")
        extras["missing_new_year_input"], p = missing_new_year_input(label)
        problems += p
        if label in ("T1", "T3"):
            log(f"{label} invariante de prefixo")
            summary["prefix_invariant"], p = prefix_invariant(result["store"])
            problems += p
        if label == "T1":
            log(f"{label} cenários de estado (execução gêmea)")
            extras["state"], p = state_scenarios(label, result["store"])
            problems += p
        configs = {"T2": (("RUN_B", "B", "0"), ("HASH_SEED_A", "A", "0"), ("HASH_SEED_B", "A", "4242")),
                   "T1": (("RUN_B", "B", "0"),), "T3": ()}[label]
        runs = {"RUN_A": result["fingerprint"]}
        for name, order, seed in configs:
            log(f"{label} determinismo {name}")
            runs[name] = fingerprint_subprocess(label, order, seed)
        summary["determinism"] = runs
        for field in ("results_sha256", "store_sha256", "plan_order"):
            if len({r[field] for r in runs.values()}) != 1:
                problems.append(f"DETERMINISM_FAILURE {label}.{field}")
    summary["closed_periods"] = {"checked": len(result["snapshots"]),
                                 "unchanged": sum(v["unchanged"] for v in result["snapshots"].values())}
    summary["problems"] = problems[:50] + ([f"+{len(problems) - 50}"] if len(problems) > 50 else [])
    summary["result"] = "PASS" if not problems else "FAIL"
    if not args.no_write:
        identities = [{k: r[k] for k in ("date", "monthly_identities", "monthly_windows_each", "annual_identities",
                                         "annual_windows_each", "month_end", "year_end", "store_keys", "new_keys",
                                         "expected_new_keys")} for r in result["rows"]]
        coverage = [{k: r[k] for k in ("date", "targets", "nodes", "events", "transfer_events")} for r in result["rows"]]
        files = {"temporal_coverage.csv": csv_text(coverage), "identities_by_date.csv": csv_text(identities),
                 "performance_profile.csv": csv_text(result["perf"]),
                 "period_snapshots.json": json.dumps(result["snapshots"], indent=1, sort_keys=True) + "\n",
                 "temporal_summary.json": json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False) + "\n"}
        if "reexecution" in extras:
            files["reexecution.json"] = json.dumps({**extras["reexecution"],
                                                    "missing_new_year_input": extras["missing_new_year_input"]},
                                                   indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        if "state" in extras:
            files["state_scenarios.json"] = json.dumps(extras["state"], indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        write_atomic(EVIDENCE / label, files)
    print(json.dumps({k: summary[k] for k in ("range", "dates", "per_date", "closed_periods", "performance",
                                              "problems", "result")}, indent=1, sort_keys=True, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
