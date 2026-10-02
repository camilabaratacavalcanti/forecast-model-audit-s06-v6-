"""
Stage 4B.1 — mecânica temporal e experimentos controlados E1–E5 (REAL_DERIVED_TEST_RESULT).

    python audit/stage4b/derive_4b.py [--no-write]

Usa o engine REAL sobre o fixture REAL_DERIVED de 5 blocos (protocolo de entradas da 4A, DR-4A-5),
sempre em contextos próprios (nada em app/, data/, tools/ é alterado) e confronta com o recálculo
independente (`python -I independent_calendar.py`).

  M  mecânica: period_id / effective_window por frequência; colisões entre frequências, meses e anos;
  E1 virada de mês e de ano: contexto populado até 2026-12-27, execução contínua 2026-12-28 -> 2027-01-03;
  E2 lacunas: data pulada dentro da janela; contexto iniciado no meio do mês;
  E3 entradas do período novo ausentes (anual em 2027-01-01; mensal em 2027-01-01): falha explícita?
  E4 períodos encerrados: reexecução de datas antigas e execução de datas novas não alteram o encerrado;
  E5 calendário: 28/29 de fevereiro, meses de 30/31 dias, bissexto 2028;
  P  desempenho: tempo e tamanho do store por data (95 datas) e estimativa para T1/T2/T3.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "audit" / "stage4a"), str(HERE)]

import common  # noqa: E402  (4A, sem alteração)
import independent_calendar as cal  # noqa: E402

from app.domain.results import Result  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.interblock_orchestrator import TRANSFER  # noqa: E402
from app.engine.time_period_resolver import TimePeriodResolver  # noqa: E402

ri = common.ri
EVIDENCE = HERE / "evidence"
EXPECTATIONS = common.bp.path("stage4b_contract", "contract_expectations_4b.json")  # Stage 4C: fonte via --baseline-dir
PERIODS = TimePeriodResolver()
D = date


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def period_hash(store: dict, prefix: str) -> tuple[int, str]:
    """(nº de chaves, hash) de todas as chaves cujo period_id começa com `prefix` (ex.: '2026', '2026-01')."""
    keys = sorted((list(k), v) for k, v in store.items() if (k[3] or "").startswith(prefix))
    return len(keys), sha(keys)


def error_of(fn):
    try:
        fn()
        return None
    except Exception as exc:  # noqa: BLE001 — o tipo/código da falha é a evidência
        return {"type": type(exc).__name__, "code": getattr(exc, "code", None),
                "chain": common.error_chain(exc), "message": str(exc)[:240]}


# ------------------------------------------------------------------ M. mecânica
def mechanics() -> dict:
    samples = {}
    for day in ("2026-01-01", "2026-02-28", "2026-12-31", "2027-01-01", "2028-02-29"):
        d = D.fromisoformat(day)
        samples[day] = {f: {"period_id": (w := PERIODS.effective_window(f, d)).period_id,
                            "start": w.start_date.isoformat(), "end": w.end_date.isoformat()}
                        for f in ("diário", "mensal", "anual")}
    jan1 = samples["2026-01-01"]
    return {"effective_window": samples,
            "period_id_formats": {"diário": "AAAA-MM-DD (10)", "mensal": "AAAA-MM (7)", "anual": "AAAA (4)"},
            "distinct_ids_on_2026_01_01": len({jan1[f]["period_id"] for f in jan1}) == 3,
            "window_for": {f"{p}|{d}": CalculationContext.window_for(p, d) for p, d in (
                ("2026", "2026-01-01"), ("2026-01", "2026-01-31"), ("2026-01", "2026-02-01"),
                ("2026", "2027-01-01"), ("2026-01-01", "2026-01-01"))}}


def collisions(store: dict, universe) -> dict:
    """Cada entidade usa um único formato de period_id (a frequência da definição); chaves únicas por construção."""
    vd = universe.orchestrator.catalog.variable_definitions
    by_entity = defaultdict(set)
    for k in store:
        by_entity[k[0]].add(len(k[3] or ""))
    want = {"diário": 10, "mensal": 7, "anual": 4}
    wrong = sorted(e for e, lengths in by_entity.items()
                   if vd.get(e) is not None and lengths != {want[vd.get(e).frequency]})
    identities = Counter(k[:4] for k in store)
    windows_outside_period = sorted((k for k in store if k[4] and not k[4].startswith(k[3] + "-")), key=repr)[:3]
    return {"entities": len(by_entity), "entities_with_wrong_period_format": wrong,
            "keys": len(store), "identities": len(identities),
            "windows_outside_their_period": windows_outside_period,
            "monthly_and_annual_ids_share_entity": sorted(
                e for e, lengths in by_entity.items() if {7, 4} <= lengths)}


# ------------------------------------------------------------------ execução auxiliar
def run(universe, days, context=None, timings=None):
    context = context or universe.fresh_context()
    traces = {}
    for day in days:
        t = time.perf_counter()
        traces[day] = universe.execute_day(context, day)
        if timings is not None:
            timings.append((day.isoformat(), time.perf_counter() - t, len(context._scoped_results)))
    return context, traces


def windows(store, variable, scope_value, period):
    return sorted(k[4] for k in store if k[0] == variable and k[2] == scope_value and k[3] == period and k[4])


def main() -> int:  # noqa: C901 — sequência de experimentos documentados
    problems: list[str] = []
    universe = common.Universe("A")
    out: dict = {"label": common.LABEL, "mechanics": mechanics()}

    # P + base de E1/E4: contexto populado de 2026-01-01 até 2026-12-27 (com perfil)
    timings: list = []
    context, traces = run(universe, cal.days(D(2026, 1, 1), D(2026, 12, 27)), timings=timings)
    perf95 = timings[:95]
    per_day = [t for _d, t, _n in timings]
    out["performance"] = {
        "dates_measured": len(timings), "mean_seconds_first_32": sum(per_day[:32]) / 32,
        "mean_seconds_days_330_361": sum(per_day[-32:]) / 32,
        "ratio_late_over_early": (sum(per_day[-32:]) / 32) / (sum(per_day[:32]) / 32),
        "store_keys_after_361_dates": timings[-1][2],
        "store_growth_per_date": sorted(Counter(b[2] - a[2] for a, b in zip(timings, timings[1:])).items()),
        "first_95": [[d, round(t, 4), n] for d, t, n in perf95[::5]]}
    mean = out["performance"]["mean_seconds_days_330_361"]
    out["performance"]["estimate_seconds"] = {"T1_396": round(396 * mean), "T2_62": round(62 * mean),
                                              "T3_792": round(792 * mean * 1.5)}

    # E1 — virada de mês e de ano
    before_store = ri.store_of(context)
    n2026_before = period_hash(before_store, "2026")
    turn_days = cal.days(D(2026, 12, 28), D(2027, 1, 3))
    year_snapshot = None
    e1 = {"dates": [d.isoformat() for d in turn_days], "per_date": {}}
    for day in turn_days:
        if day == D(2027, 1, 1):
            year_snapshot = period_hash(ri.store_of(context), "2026")
            dec_snapshot = period_hash(ri.store_of(context), "2026-12")
        traces[day] = universe.execute_day(context, day)
        store = ri.store_of(context)
        e1["per_date"][day.isoformat()] = {
            "monthly_period": PERIODS.effective_window("mensal", day).period_id,
            "annual_period": PERIODS.effective_window("anual", day).period_id,
            "VAR16019_monthly_windows": len(windows(store, "VAR16019", "L1_L3", PERIODS.effective_window("mensal", day).period_id)),
            "VAR16020_annual_windows": len(windows(store, "VAR16020", "L1_L3", PERIODS.effective_window("anual", day).period_id)),
            "transfer_events": len(traces[day].of_kind(TRANSFER)), "events": len(traces[day].events)}
    store = ri.store_of(context)
    e1["annual_2026_windows_per_identity"] = sorted(Counter(
        len(v) for v in _windows_by_identity(store, "2026").values()).items())
    e1["annual_2027_windows_per_identity"] = sorted(Counter(
        len(v) for v in _windows_by_identity(store, "2027").values()).items())
    e1["snapshot_2026_at_2027_01_01"] = year_snapshot
    e1["snapshot_2026_after_2027_01_03"] = period_hash(store, "2026")
    e1["snapshot_2026_12_unchanged"] = dec_snapshot == period_hash(store, "2026-12")
    e1["year_2026_closed_unchanged"] = year_snapshot == e1["snapshot_2026_after_2027_01_03"]
    e1["keys_2026_before_turn"] = n2026_before
    want = {"2026-12-31": (31, 365), "2027-01-01": (1, 1), "2027-01-03": (3, 3)}
    for day, (m, a) in want.items():
        got = e1["per_date"][day]
        if (got["VAR16019_monthly_windows"], got["VAR16020_annual_windows"]) != (m, a):
            problems.append(f"E1_FAILURE {day}: janelas {got} != mensal {m} / anual {a}")
    if e1["annual_2026_windows_per_identity"] != [(365, 196)] or e1["annual_2027_windows_per_identity"] != [(3, 196)]:
        problems.append("E1_FAILURE janelas anuais por identidade")
    if not (e1["year_2026_closed_unchanged"] and e1["snapshot_2026_12_unchanged"]):
        problems.append("E1_FAILURE período de 2026 alterado depois da virada")
    out["E1_turn_of_year"] = e1
    out["collisions"] = collisions(store, universe)
    if out["collisions"]["entities_with_wrong_period_format"] or out["collisions"]["windows_outside_their_period"]:
        problems.append("IDENTITY_COLLISION formato de period_id/janela")

    # E4 — períodos encerrados: reexecuta datas antigas (fechadas) depois da virada
    e4 = {}
    for day in (D(2026, 6, 15), D(2026, 12, 31)):
        before = ri.store_of(context)
        trace = universe.execute_day(context, day)
        after = ri.store_of(context)
        e4[day.isoformat()] = {"new_keys": len(set(after) - set(before)),
                               "changed_keys": sum(1 for k in before if before[k] != after.get(k)),
                               "transfer_statuses": dict(Counter(e.status for e in trace.of_kind(TRANSFER)))}
    for day in cal.days(D(2027, 1, 4), D(2027, 1, 6)):
        universe.execute_day(context, day)
    e4["snapshot_2026_after_reexecution_and_new_dates"] = period_hash(ri.store_of(context), "2026")
    e4["year_2026_unchanged"] = e4["snapshot_2026_after_reexecution_and_new_dates"] == year_snapshot
    if not e4["year_2026_unchanged"] or any(v["new_keys"] or v["changed_keys"] for k, v in e4.items()
                                            if isinstance(v, dict) and "new_keys" in v):
        problems.append("E4_FAILURE período encerrado alterado / identidade nova")
    out["E4_closed_periods"] = e4

    # E3 — entrada do período novo ausente (cópia do contexto em 2026-12-31)
    # Casos: (variável, período removido, forçar o ramo IF de EQ12012 que lê VAR12024, deve falhar?)
    #   VAR12024 só é lido no ramo ativo do IF (3.3B): sem forçar, a ausência não é lida (prova abaixo).
    e3 = {}
    cases = {"annual_input_VAR12066_2027": ("VAR12066", "2027", False, True),
             "monthly_input_VAR16001_2027-01_unconditional": ("VAR16001", "2027-01", False, True),
             "monthly_input_VAR12024_2027-01_if_branch_inactive": ("VAR12024", "2027-01", False, False),
             "monthly_input_VAR12024_2027-01_if_branch_forced": ("VAR12024", "2027-01", True, True)}
    day = D(2027, 1, 7)
    for label, (variable, period, force_if, must_fail) in cases.items():
        trial = copy.deepcopy(context)
        universe.seed_inputs(trial, day)
        if force_if:          # lth_meta mínimo => condição verdadeira => ramo que lê VAR12024 executado (SC1)
            for sv in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
                trial.set_variable_result("VAR12066", Result(0.0001), "linha", sv, "2027")
        removed = [k for k in list(trial._scoped_results) if k.entity_id == variable and k.period_id == period]
        for k in removed:
            del trial._scoped_results[k]
        previous_exists = any(k.entity_id == variable and k.period_id != period for k in trial._scoped_results)
        err = error_of(lambda: universe.orchestrator.execute(universe.plan, trial, day))
        e3[label] = {"removed_keys": len(removed), "previous_period_value_exists": previous_exists,
                     "if_branch_forced": force_if, "must_fail": must_fail, "error": err}
        if must_fail and err is None:
            problems.append(f"BLOCKER E3 {label}: execução sem a entrada do período novo não falhou (carry-over)")
    # prova de que, com o ramo inativo, VAR12024 não é lido: valor arbitrário => 0 diferenças nos resultados
    a, b = copy.deepcopy(context), copy.deepcopy(context)
    universe.seed_inputs(a, day)
    universe.seed_inputs(b, day)
    for sv in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        b.set_variable_value("VAR12024", 999.0, "linha", sv, "2027-01")
    universe.orchestrator.execute(universe.plan, a, day)
    universe.orchestrator.execute(universe.plan, b, day)
    sa, sb = ri.store_of(a), ri.store_of(b)
    e3["VAR12024_not_read_when_branch_inactive"] = {
        "differences_excluding_VAR12024": sum(1 for k in sa if k[0] != "VAR12024" and sa[k] != sb.get(k))}
    if e3["VAR12024_not_read_when_branch_inactive"]["differences_excluding_VAR12024"]:
        problems.append("E3_FAILURE VAR12024 lido com o ramo inativo")
    e3["carry_over"] = "NONE: nenhuma leitura cai no período anterior; a chave é (variável, escopo, period_id[, janela])"
    out["E3_missing_new_period_input"] = e3

    # E2 — lacunas
    e2 = {}
    gap_ctx, _ = run(universe, cal.days(D(2026, 1, 1), D(2026, 1, 5)))
    e2["skip_2026_01_06_then_run_01_07"] = error_of(lambda: universe.execute_day(gap_ctx, D(2026, 1, 7)))
    e2["fresh_context_starting_2026_01_10"] = error_of(lambda: universe.execute_day(universe.fresh_context(), D(2026, 1, 10)))
    e2["fresh_context_starting_2026_02_01"] = error_of(lambda: universe.execute_day(universe.fresh_context(), D(2026, 2, 1)))
    e2["policy"] = ("EXPLICIT_FAILURE" if all(e2[k] is not None for k in e2) else "SILENT_OR_PARTIAL")
    if e2["policy"] != "EXPLICIT_FAILURE":
        problems.append("E2_REQUIRES_FOLLOWUP lacuna não falha explicitamente (registro, não bloqueio)")
    out["E2_gaps"] = e2

    # E5 — calendário (2026 em E1: fevereiro 28, abril 30; 2028 bissexto)
    e5 = {"2026": {}}
    for label, (variable, sv, period, n) in {"2026-02 (28)": ("VAR16019", "L1_L3", "2026-02", 28),
                                             "2026-04 (30)": ("VAR16019", "L1_L3", "2026-04", 30),
                                             "2026-07 (31)": ("VAR16019", "L1_L3", "2026-07", 31)}.items():
        e5["2026"][label] = len(windows(ri.store_of(context), variable, sv, period)) == n
    leap_ctx, _ = run(universe, cal.days(D(2028, 1, 1), D(2028, 3, 2)))
    leap = ri.store_of(leap_ctx)
    e5["2028"] = {"feb_windows_VAR16019": len(windows(leap, "VAR16019", "L1_L3", "2028-02")),
                  "feb_29_daily_present": ("VAR16018", "linha_grupo", "L1_L3", "2028-02-29", None) in leap,
                  "mar_windows_VAR16019": len(windows(leap, "VAR16019", "L1_L3", "2028-03")),
                  "annual_windows_VAR16020": len(windows(leap, "VAR16020", "L1_L3", "2028")),
                  "annual_windows_per_identity": sorted(Counter(len(v) for v in _windows_by_identity(leap, "2028").values()).items())}
    if not all(e5["2026"].values()) or (e5["2028"]["feb_windows_VAR16019"], e5["2028"]["mar_windows_VAR16019"],
                                        e5["2028"]["annual_windows_VAR16020"]) != (29, 2, 62) \
            or not e5["2028"]["feb_29_daily_present"]:
        problems.append(f"E5_FAILURE calendário {e5}")
    out["E5_calendar"] = e5

    # recálculo independente
    completed = subprocess.run([sys.executable, "-I", str(HERE / "independent_calendar.py")], cwd=REPO,
                               capture_output=True, text=True)
    ind = json.loads(completed.stdout)
    out["independent"] = {"result": ind["result"], "imports_app_or_tools": ind["imports_app_or_tools"],
                          "cycles": ind["cycles"]}
    growth = dict(out["performance"]["store_growth_per_date"])
    for label, value in (("regular", ind["store_growth_regular_day"]), ("first_of_month", ind["store_growth_first_of_month"])):
        if value not in growth:
            problems.append(f"STORE_GROWTH_DIVERGENCE {label}: {value} não observado em {growth}")
    if timings[0][2] != ind["store_growth_first_day"]:
        problems.append("STORE_GROWTH_DIVERGENCE primeiro dia")
    if ind["cycles"]["instance_cycles"]:
        problems.append(f"BLOCKER INSTANCE_CYCLE {ind['cycles']['instance_cycles'][:2]}")
    # verificação empírica de aciclicidade: em cada data, todo nó do plano executa depois dos seus produtores
    out["empirical_acyclicity"] = {"plan_nodes": len(universe.plan.steps),
                                   "topological_order_valid": _topological(universe)}
    if not out["empirical_acyclicity"]["topological_order_valid"]:
        problems.append("BLOCKER plano sem ordem topológica válida")

    expectations = {
        "independent": {
            "calendar.T1.dates": ind["calendar"]["T1"]["dates"], "calendar.T2.dates": ind["calendar"]["T2"]["dates"],
            "calendar.T3.dates": ind["calendar"]["T3"]["dates"],
            "calendar.T2.feb_29_dates": ind["calendar"]["T2"]["feb_29_dates"],
            "identity_profile": ind["identity_profile"],
            "store_growth_first_day": ind["store_growth_first_day"],
            "store_growth_regular_day": ind["store_growth_regular_day"],
            "store_growth_first_of_month": ind["store_growth_first_of_month"],
            "cycles.instance_cycles": [], "cycles.variable_cycles": [],
            "cycles.block_cycles": ind["cycles"]["block_cycles"], "cycles.lag_references": [],
        },
        "temporal": {
            "targets": 446, "planner_nodes": 458, "transfers_per_date": 13,
            "transfer_events_per_date": 67, "events_per_date": 896,
            "derived_monthly_identities": ind["identity_profile"]["derived_mensal"],
            "derived_annual_identities": ind["identity_profile"]["derived_anual"],
            "derived_daily_instances": ind["identity_profile"]["derived_diário"],
            "ranges": {k: [v[0].isoformat(), v[1].isoformat()] for k, v in cal.RANGES.items() if k != "4A"},
            "reexecution_dates": ["2026-02-28", "2026-12-31", "2027-01-01", "2028-02-29", "2028-03-01"],
            "performance_ratio_limit": 3.0,
        },
    }
    out["problems"] = problems
    out["result"] = "PASS" if not problems else "FAIL"
    if "--no-write" in sys.argv[1:]:
        if json.loads(json.dumps(expectations)) != json.loads(EXPECTATIONS.read_text(encoding="utf-8")):
            problems.append("EXPECTATIONS_DRIFT")
            out["result"] = "FAIL"
    else:
        if common.bp.is_default():
            EVIDENCE.mkdir(exist_ok=True)
        common.bp.writable("stage4b_contract", "contract_audit_4b.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str)
                                                         + "\n", encoding="utf-8")
        common.bp.writable("stage4b_contract", "contract_expectations_4b.json").write_text(json.dumps(expectations, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                encoding="utf-8")
        with common.bp.writable("stage4b_contract", "performance_probe.csv").open("w", encoding="utf-8") as handle:
            handle.write("date,seconds,store_keys\n")
            for d, t, n in timings:
                handle.write(f"{d},{t:.4f},{n}\n")
    print(json.dumps({k: out[k] for k in ("E1_turn_of_year", "E2_gaps", "E3_missing_new_period_input",
                                          "E4_closed_periods", "E5_calendar", "collisions", "problems", "result")},
                     indent=1, ensure_ascii=False, default=str)[:6000])
    return 0 if out["result"] == "PASS" else 1


def _windows_by_identity(store, period):
    out = defaultdict(set)
    for k in store:
        if k[3] == period and k[4]:
            out[k[:4]].add(k[4])
    return out


def _topological(universe) -> bool:
    o = universe.orchestrator
    position = {s.key: i for i, s in enumerate(universe.plan.steps)}
    for s in universe.plan.steps:
        for variable in o._deps[s.key]:
            for producer in o._producers.get(variable, ()):
                if producer in position and position[producer] >= position[s.key]:
                    return False
    return True


if __name__ == "__main__":
    sys.exit(main())
