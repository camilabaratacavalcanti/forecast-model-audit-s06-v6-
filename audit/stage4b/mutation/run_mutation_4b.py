"""
Stage 4B.3b — mutação e controles temporais (REAL_DERIVED_TEST_RESULT).

    python audit/stage4b/mutation/run_mutation_4b.py [--no-write] [--skip-code-mutants]

1. MUTAÇÕES DE EVIDÊNCIA sobre a evidência REAL da 4B (execução T2 de 62 datas em 2028, linhas de
   identidades por data, snapshots de períodos encerrados, janelas, estado ao longo do ano,
   reexecução, determinismo, invariante de prefixo, proveniência): uma corrupção por mutação; o auditor
   correspondente (os mesmos do harness/oracle 4B) precisa detectar. Controles positivos: cada
   auditor aceita a evidência sem mutação.
2. MUTANTES DE CÓDIGO (`code_mutants_4b.py`): só em cópia temporária.
Meta: 100% detectado. `git status -- app data tools` vazio antes e depois.
"""

from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
REPO = STAGE.parents[1]
sys.path[:0] = [str(REPO / "audit" / "stage4a"), str(REPO / "audit" / "stage4a" / "integrated"), str(STAGE),
                str(STAGE / "temporal"), str(STAGE / "oracle"), str(HERE)]

import checks_4a  # noqa: E402
import code_mutants_4b  # noqa: E402
import common  # noqa: E402
import independent_calendar as cal  # noqa: E402
import oracle_temporal as oracle  # noqa: E402
import run_oracle_4b as oracle_driver  # noqa: E402
import run_temporal_4b as harness  # noqa: E402

from app.domain.results import Result  # noqa: E402
from app.engine.interblock_orchestrator import TRANSFER  # noqa: E402

import checks  # noqa: E402  (3.4C/3.4D, sem alteração)

ri = common.ri
EVIDENCE = HERE / "evidence"
# Stage 4C: evidência de referência (T1/T2 e expectativas da 4A) via `--baseline-dir`.
T2_EVIDENCE = common.bp.path("stage4b_temporal", "T2/temporal_summary.json").parent
T1_EVIDENCE = common.bp.path("stage4b_temporal", "T1/temporal_summary.json").parent
C_RUN = "4B temporal: execução real T2 (5 blocos, 2028-01-01..03-02, contexto único)"
C_EVID = "4B temporal: evidência versionada (identities_by_date.csv / period_snapshots.json / reexecution.json)"
C_STATE = "4B temporal: execução gêmea real com injeção (2028-01-10)"
C_DET = "4B temporal: fingerprints versionados (T1/T2)"
C_PREF = "4A: execução real das 32 datas x evidência 4A"
C_PROV = "registro oficial de vínculos (bytes reais)"


class World:
    def __init__(self):
        self.runner = harness.Runner("A")
        u = self.runner.universe
        self.days = harness.date_range("T2")
        self.context = u.fresh_context()
        self.traces = {}
        for day in self.days:
            self.traces[day] = u.execute_day(self.context, day)
        self.store = ri.store_of(self.context)
        self.last = self.days[-1]
        self.rules = oracle.load_rules()
        self.identity_rows = list(csv.DictReader((T2_EVIDENCE / "identities_by_date.csv").open(encoding="utf-8")))
        self.coverage_rows = list(csv.DictReader((T2_EVIDENCE / "temporal_coverage.csv").open(encoding="utf-8")))
        self.snapshots = json.loads((T1_EVIDENCE / "period_snapshots.json").read_text(encoding="utf-8"))
        self.reex_t1 = json.loads((T1_EVIDENCE / "reexecution.json").read_text(encoding="utf-8"))
        self.determinism = json.loads((T2_EVIDENCE / "temporal_summary.json").read_text(encoding="utf-8"))["determinism"]
        jan = self.store_month_closed()
        self.jan_snapshot = jan
        # reexecução real de 2028-02-29
        day = date(2028, 2, 29)
        self.reex = {"before": ri.store_of(self.context), "first": ri.events_of(self.traces[day])}
        trace = u.execute_day(self.context, day)
        self.reex.update({"after": ri.store_of(self.context), "again": ri.events_of(trace)})
        # estado: injeção em 2028-01-10 (valor_retirada@L1), execução gêmea de 20 datas
        twin_days = self.days[:20]
        clean, _ = u.run_sequence(twin_days)
        def inject(d):
            if d == date(2028, 1, 10):
                return [("VAR16017", "linha", "L1", d.isoformat(), Result(None, "INVALID_INPUT", "m"))]
            return []
        stated, _ = u.run_sequence(twin_days, None, inject)
        self.clean, self.stated = ri.store_of(clean), ri.store_of(stated)
        self.descendants = ri.descendants_of(u.orchestrator, {"VAR16017"})
        jan_windows = sorted(k for k in self.stated if k[0] == "VAR16019" and k[3] == "2028-01" and k[4])
        self.must = [k for k in jan_windows if k[4] >= "2028-01-10"]
        self.plain = [k for k in jan_windows if k[4] < "2028-01-10"] + \
            [k for k in self.stated if k[0] == "VAR16028" and k[3] == "2028-01-10"]
        self.links_bytes = (common.fixture.SEED / "interblock_links.json").read_bytes()

    def store_month_closed(self):
        return harness.prefix_snapshot(self.store, "2028-01")

    # ------------------------------------------------------------ auditores
    def audit_day(self, context=None, day=None) -> list[str]:
        day = day or self.last
        return self.runner.check_day(context or self.context, day, self.traces[day], False)[1]

    def audit_identity_rows(self, rows=None) -> list[str]:
        problems = []
        for r in rows or self.identity_rows:
            want = cal.expected_windows(date.fromisoformat(r["date"]))
            if int(r["monthly_windows_each"]) != want["monthly"] or int(r["annual_windows_each"]) != want["annual"]:
                problems.append(f"IDENTITY_ROW {r['date']} janelas != calendário")
            if r["new_keys"] != r["expected_new_keys"]:
                problems.append(f"STORE_GROWTH {r['date']}")
        return problems

    def audit_coverage_rows(self, rows=None) -> list[str]:
        want = {"targets": "446", "nodes": "458", "events": "896", "transfer_events": "67"}
        return [f"COVERAGE {r['date']} {k}" for r in rows or self.coverage_rows for k, v in want.items() if r[k] != v]

    def audit_snapshots(self, snapshots=None) -> list[str]:
        return [f"CLOSED_PERIOD_CHANGED {p}" for p, v in (snapshots or self.snapshots).items()
                if v["at_turn"] != v["at_end"] or not v["unchanged"]]

    def audit_closed_month(self, store=None) -> list[str]:
        now = harness.prefix_snapshot(self.store if store is None else store, "2028-01")
        return [] if now == self.jan_snapshot else ["CLOSED_PERIOD_CHANGED 2028-01"]

    def audit_aggregations(self, store=None, day=None) -> list[str]:
        store = self.store if store is None else store
        day = day or self.last
        problems = []
        for rule in self.rules:
            got = oracle_driver.engine_result(store, oracle.target_key(rule, day))
            if not oracle_driver.compare(got, oracle.aggregate(rule, store, day))[0]:
                problems.append(f"ORACLE_MISMATCH {rule['aggregation_rule_id']} {rule['scope_value']}")
        return problems

    def audit_state(self, stated=None) -> list[str]:
        stated = self.stated if stated is None else stated
        return (checks.check_state_diff(self.clean, stated, self.descendants, "INVALID_INPUT", "m")
                + checks.check_expectations(stated, self.must, self.plain, "INVALID_INPUT", "m"))

    def audit_reexecution(self, after=None, again=None) -> list[str]:
        return checks.check_reexecution("2028-02-29", self.reex["before"], after or self.reex["after"],
                                        self.reex["first"], again or self.reex["again"])

    def audit_conflict_and_e3(self, record=None) -> list[str]:
        r = record or self.reex_t1
        problems = []
        if r["conflict_on_changed_upstream_input"]["error"] != "INTERBLOCK_CONSUMER_VALUE_CONFLICT":
            problems.append("CONFLICT_NOT_DETECTED")
        if not r["missing_new_year_input"].get("error"):
            problems.append("CARRY_OVER entrada anual ausente sem falha")
        return problems

    def audit_determinism(self, runs=None) -> list[str]:
        runs = runs or self.determinism
        return [f"DETERMINISM_FAILURE {f}" for f in ("results_sha256", "store_sha256", "plan_order")
                if len({r[f] for r in runs.values()}) != 1]

    def audit_prefix(self, store=None) -> list[str]:
        if store is None:
            if not hasattr(self, "_prefix_store"):
                context, _ = common.Universe("A").run_sequence(common.DAYS)
                self._prefix_store = ri.store_of(context)
            store = self._prefix_store
        return harness.prefix_invariant(store)[1]

    def audit_provenance(self, links_bytes=None) -> list[str]:
        expected = json.loads(common.bp.path("stage4a_contract", "contract_expectations.json").read_text(
            encoding="utf-8"))["integrated"]["interblock_links_sha256"]
        return checks_4a.check_provenance(links_bytes or self.links_bytes, expected, 16, 0)


MUTATIONS = []


def mutation(mutation_id, contract, description, artifact, real_path):
    def register(fn):
        MUTATIONS.append({"mutation_id": mutation_id, "contract": contract, "description": description,
                          "artifact": artifact, "real_path": real_path, "fn": fn})
        return fn
    return register


def _ctx_copy(w):
    return copy.deepcopy(w.context)


@mutation("EM4B-01", "identidades por data", "linha de 2028-02-29 com 59 janelas anuais", "identities_by_date.csv", C_EVID)
def _m01(w):
    rows = copy.deepcopy(w.identity_rows)
    next(r for r in rows if r["date"] == "2028-02-29")["annual_windows_each"] = "59"
    return w.audit_identity_rows(rows)


@mutation("EM4B-02", "identidades por data", "crescimento do store diferente do previsto", "identities_by_date.csv", C_EVID)
def _m02(w):
    rows = copy.deepcopy(w.identity_rows)
    rows[10]["new_keys"] = str(int(rows[10]["new_keys"]) - 1)
    return w.audit_identity_rows(rows)


@mutation("EM4B-03", "janelas", "janela mensal de 2028-03-02 ausente numa identidade", "context._windows", C_RUN)
def _m03(w):
    ctx = _ctx_copy(w)
    key = next(k for k in ctx._windows if k[3] == "2028-03")
    ctx._windows[key].discard("2028-03-02")
    return w.audit_day(ctx)


@mutation("EM4B-04", "janelas", "janela anual extra (data futura) numa identidade", "context._windows", C_RUN)
def _m04(w):
    ctx = _ctx_copy(w)
    key = next(k for k in ctx._windows if k[3] == "2028")
    ctx._windows[key].add("2028-12-31")
    return w.audit_day(ctx)


@mutation("EM4B-05", "MOVING_AVERAGE", "média móvel não reinicia em 2028-03-01", "store", C_RUN)
def _m05(w):
    ctx = _ctx_copy(w)
    source, target, st, sv = w.runner.ma[0]
    key = next(k for k in ctx._scoped_results if k.entity_id == target and k.scope_value == sv and k.period_id == "2028-03-01")
    ctx._scoped_results[key] = Result(ctx._scoped_results[key].value + 1.0)
    return w.runner.check_day(ctx, date(2028, 3, 1), w.traces[date(2028, 3, 1)], False)[1]


@mutation("EM4B-06", "snapshots", "snapshot de 2026 com hash diferente ao fim (T1)", "period_snapshots.json", C_EVID)
def _m06(w):
    snapshots = copy.deepcopy(w.snapshots)
    snapshots["2026"]["at_end"] = [snapshots["2026"]["at_end"][0], "0" * 64]
    return w.audit_snapshots(snapshots)


@mutation("EM4B-07", "períodos encerrados", "resultado de janeiro/2028 alterado depois do fechamento", "store", C_RUN)
def _m07(w):
    store = dict(w.store)
    k = next(k for k, v in store.items() if k[3] == "2028-01" and v[0] == "float")
    store[k] = ["float", repr(float(store[k][1]) + 1.0), None, None]
    return w.audit_closed_month(store)


@mutation("EM4B-08", "períodos encerrados", "identidade nova no período encerrado (janeiro/2028)", "store", C_RUN)
def _m08(w):
    store = dict(w.store)
    store[("VAR16019", "linha_grupo", "L1_L3", "2028-01", "2028-02-01")] = ["float", "1.0", None, None]
    return w.audit_closed_month(store)


@mutation("EM4B-09", "agregação", "média mensal de 2028-03-02 alterada", "store", C_RUN)
def _m09(w):
    store = dict(w.store)
    rule = next(r for r in w.rules if r["aggregation_type"] == "AVERAGE" and r["target_frequency"] == "mensal")
    k = oracle.target_key(rule, w.last)
    store[k] = ["float", repr(float(store[k][1]) * 1.001), None, None]
    return w.audit_aggregations(store)


@mutation("EM4B-10", "agregação", "SUM anual com um dia a menos (29/fev omitido)", "store", C_RUN)
def _m10(w):
    store = dict(w.store)
    rule = next(r for r in w.rules if r["aggregation_type"] == "SUM" and r["target_frequency"] == "anual")
    src = store[(rule["source_variable_id"], rule["scope_type"], rule["scope_value"], "2028-02-29", None)]
    k = oracle.target_key(rule, w.last)
    store[k] = ["float", repr(float(store[k][1]) - float(src[1])), None, None]
    return w.audit_aggregations(store)


@mutation("EM4B-11", "estado", "estado ausente na janela mensal após a injeção", "stated store", C_STATE)
def _m11(w):
    stated = dict(w.stated)
    stated[w.must[0]] = ["float", "1.0", None, None]
    return w.audit_state(stated)


@mutation("EM4B-12", "estado", "estado vazado para a janela anterior à injeção", "stated store", C_STATE)
def _m12(w):
    stated = dict(w.stated)
    stated[w.plain[0]] = ["NoneType", "None", "INVALID_INPUT", "m"]
    return w.audit_state(stated)


@mutation("EM4B-13", "reexecução", "reexecução de 2028-02-29 cria identidade nova", "after store", C_RUN)
def _m13(w):
    after = dict(w.reex["after"])
    after[("VAR16019", "linha_grupo", "L1_L3", "2028-02", "2028-02-30")] = ["float", "1.0", None, None]
    return w.audit_reexecution(after=after)


@mutation("EM4B-14", "reexecução", "transferência regravada (WRITTEN) na reexecução", "again events", C_RUN)
def _m14(w):
    again = copy.deepcopy(w.reex["again"])
    next(e for e in again if e[1] == TRANSFER)[8] = "WRITTEN"
    return w.audit_reexecution(again=again)


@mutation("EM4B-15", "reexecução / E3", "conflito de entrada não detectado e entrada anual com carry-over", "reexecution.json", C_EVID)
def _m15(w):
    record = copy.deepcopy(w.reex_t1)
    record["conflict_on_changed_upstream_input"]["error"] = None
    record["missing_new_year_input"]["error"] = None
    return w.audit_conflict_and_e3(record)


@mutation("EM4B-16", "determinismo", "HASH_SEED_B (4242) com results_sha256 diferente", "fingerprints", C_DET)
def _m16(w):
    runs = copy.deepcopy(w.determinism)
    runs["HASH_SEED_B"]["results_sha256"] = "0" * 64
    return w.audit_determinism(runs)


@mutation("EM4B-17", "invariante de prefixo", "chave das 32 primeiras datas diferente da 4A", "store 4A", C_PREF)
def _m17(w):
    w.audit_prefix()
    store = dict(w._prefix_store)
    k = min(k for k, v in store.items() if v[0] == "float")
    store[k] = ["float", repr(float(store[k][1]) + 1.0), None, None]
    return w.audit_prefix(store)


@mutation("EM4B-18", "cobertura", "data com 12 transferências (66 eventos)", "temporal_coverage.csv", C_EVID)
def _m18(w):
    rows = copy.deepcopy(w.coverage_rows)
    rows[5]["transfer_events"] = "60"
    return w.audit_coverage_rows(rows)


@mutation("EM4B-19", "proveniência", "interblock_links.json alterado", "links bytes", C_PROV)
def _m19(w):
    return w.audit_provenance(w.links_bytes + b"\n")


POSITIVE = {
    "PC4B-01 verificação por data (janelas, MA, plano)": lambda w: w.audit_day(),
    "PC4B-02 identidades por data x calendário": lambda w: w.audit_identity_rows(),
    "PC4B-03 cobertura por data": lambda w: w.audit_coverage_rows(),
    "PC4B-04 snapshots de T1": lambda w: w.audit_snapshots(),
    "PC4B-05 período encerrado (janeiro/2028)": lambda w: w.audit_closed_month(),
    "PC4B-06 agregações x oracle (2028-03-02)": lambda w: w.audit_aggregations(),
    "PC4B-07 estado (gêmeas)": lambda w: w.audit_state(),
    "PC4B-08 reexecução": lambda w: w.audit_reexecution(),
    "PC4B-09 conflito e E3 (T1)": lambda w: w.audit_conflict_and_e3(),
    "PC4B-10 determinismo (T2)": lambda w: w.audit_determinism(),
    "PC4B-11 invariante de prefixo": lambda w: w.audit_prefix(),
    "PC4B-12 proveniência": lambda w: w.audit_provenance(),
}


def main() -> int:
    problems = []
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    world = World()
    controls = []
    for name, fn in POSITIVE.items():
        p = fn(world)
        controls.append({"control": name, "problems": len(p), "result": "ACCEPT" if not p else "REJECT",
                         "evidence": " | ".join(p[:2])[:300]})
    rows = []
    for m in MUTATIONS:
        p = m["fn"](world)
        rows.append({k: m[k] for k in ("mutation_id", "contract", "description", "artifact", "real_path")}
                    | {"detected": "TRUE" if p else "FALSE", "problems": len(p), "first_problem": (p[0] if p else "")[:240]})
    summary = {"label": common.LABEL, "stage": "4B",
               "evidence_mutations": {"defined": len(rows), "detected": sum(r["detected"] == "TRUE" for r in rows),
                                      "missed": [r["mutation_id"] for r in rows if r["detected"] != "TRUE"]},
               "positive_controls": {"total": len(controls), "accepted": sum(c["result"] == "ACCEPT" for c in controls),
                                     "rejected_unexpectedly": [c["control"] for c in controls if c["result"] != "ACCEPT"]}}
    problems += [f"EVIDENCE_MUTATION_SURVIVED {m}" for m in summary["evidence_mutations"]["missed"]]
    problems += [f"POSITIVE_CONTROL_REJECTED {c}" for c in summary["positive_controls"]["rejected_unexpectedly"]]
    code_rows = []
    if "--skip-code-mutants" not in sys.argv[1:]:
        code_summary, code_rows = code_mutants_4b.run_all()
        summary["code_mutants"] = code_summary
        problems += [f"CODE_MUTANT_SURVIVED {m}" for m in code_summary["surviving_ids"]]
        problems += [f"EXPECTED_DETECTOR_MISSED {k}: {v}" for k, v in code_summary["expected_detectors_missed"].items()]
        if code_summary["positive_control"]["result"] != "ACCEPT":
            problems.append(f"CODE_POSITIVE_CONTROL_REJECTED {code_summary['positive_control']['evidence']}")
        total = len(rows) + code_summary["introduced"]
        summary["detection_rate"] = f"{100.0 * (summary['evidence_mutations']['detected'] + code_summary['detected']) / total:.1f}%"
    after = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout
    summary["git_status_app_data_tools"] = {"before": before, "after": after, "empty": before == after == ""}
    if before or after:
        problems.append("REPOSITORY_TOUCHED")
    summary["problems"] = problems
    summary["result"] = "PASS" if not problems else "FAIL"
    if "--no-write" not in sys.argv[1:]:
        EVIDENCE.mkdir(exist_ok=True)
        for name, data in (("mutation_results.csv", rows), ("positive_controls.csv", controls),
                           ("code_mutation_results.csv", code_rows)):
            if data:
                with (EVIDENCE / name).open("w", encoding="utf-8", newline="") as handle:
                    w = csv.DictWriter(handle, fieldnames=list(data[0]), lineterminator="\n")
                    w.writeheader()
                    w.writerows(data)
        (EVIDENCE / "mutation_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True)
                                                        + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
