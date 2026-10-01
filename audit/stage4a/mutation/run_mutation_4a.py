"""
Stage 4A.3b — mutação e controles do area_41 (método da 3.4D estendido; REAL_DERIVED_TEST_RESULT).

    python audit/stage4a/mutation/run_mutation_4a.py [--no-write] [--skip-code-mutants]

1. MUTAÇÕES DE EVIDÊNCIA: a evidência REAL da 4A (execução de 5 blocos, 32 datas; cenário SA5
   do "F"; reexecução; fingerprints versionados; registro de vínculos) é copiada e UMA coisa é
   corrompida por mutação; o auditor correspondente (os mesmos usados pelo harness 4A) precisa
   detectar. Controles positivos: cada auditor aceita a evidência sem mutação.
2. MUTANTES DE CÓDIGO/SEED (`code_mutants_4a.py`): só em cópia temporária (`git clone --shared`).

Meta: 100% detectado; sobrevivente = finding com análise. `git status -- app data tools` vazio
antes e depois (registrado).
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
sys.path[:0] = [str(STAGE), str(STAGE / "integrated"), str(HERE)]

import checks_4a  # noqa: E402
import code_mutants_4a  # noqa: E402
import common  # noqa: E402
import run_integrated_4a as harness  # noqa: E402

import checks  # noqa: E402  (3.4C/3.4D, sem alteração)

ri, fixture = common.ri, common.fixture
DAYS = common.DAYS
DAYS_ISO = [d.isoformat() for d in DAYS]
JAN15 = date(2026, 1, 15)
EVIDENCE = HERE / "evidence"
C_RUN = "4A integrated: real planner + orchestrator + engine trace (5 blocos, 32 datas)"
C_STATE = "4A integrated: cenário SA5 real (execuções gêmeas, \"F\" -> NO_APPLICABLE_RULE)"
C_TEMP = "4A integrated: store temporal real"
C_REEX = "4A integrated: FIRST_RUN x REEXECUTION reais (2026-01-15)"
C_DET = "4A integrated: fingerprints versionados (subprocessos ORDER_A/B, PYTHONHASHSEED 0/4242)"
C_NREG = "4A integrated: store real de 5 blocos x 3.4C (hash versionado + 4 blocos isolados)"
C_PROV = "registro oficial de vínculos (bytes reais) + fixture"


class World:
    """A evidência real, produzida uma vez; cada mutação trabalha numa cópia."""

    def __init__(self):
        u = self.universe = common.Universe("A")
        o, plan = u.orchestrator, u.plan
        self.context = u.fresh_context()
        self.traces, self.snapshot = {}, None
        for day in DAYS:
            if day == date(2026, 2, 1):
                self.snapshot = {k: v for k, v in ri.store_of(self.context).items() if k[3] == "2026-01"}
            self.traces[day] = u.execute_day(self.context, day)
        self.store = ri.store_of(self.context)
        (self.executed, self.written, self.transfers, _cov, _obs) = ri.observe(o, self.context, self.traces)
        self.events, self.instances = ri.node_expectations(o, plan)
        self.planned = [s.key for s in plan.steps]
        self.transfer_expected = ri.transfer_expectations(o, plan)
        self.target_records = ri.target_records(self.traces, set(plan.targets))
        self.expected_periods = ri.expected_periods(o, plan.targets, DAYS)
        self.derived = ri.derived_variables(plan)
        self.numeric = harness.numeric_variables(u)
        before = ri.store_of(self.context)
        trace = u.execute_day(self.context, JAN15)
        self.reex = {"before": before, "after": ri.store_of(self.context),
                     "first": ri.events_of(self.traces[JAN15]), "again": ri.events_of(trace)}
        committed = json.loads((STAGE / "integrated" / "evidence" / "integrated_summary.json").read_text(encoding="utf-8"))
        self.runs = {k: committed["determinism"][k] for k in ("RUN_A", "RUN_B", "HASH_SEED_A", "HASH_SEED_B")}
        self.sa5 = next(s for s in harness.scenarios(u) if s["name"] == "SA5_F_literal_no_applicable_rule")
        self.links_bytes = (fixture.SEED / "interblock_links.json").read_bytes()
        self.links_sha = harness.EXPECTED["interblock_links_sha256"]

    # ------------------------------------------------------------ auditores (os do harness 4A)
    def audit_run(self, written=None, executed=None, transfers=None, records=None) -> list[str]:
        return (checks.check_targets(self.instances, written or self.written)
                + checks.check_nodes(self.planned, self.events, executed or self.executed)
                + checks.check_transfers(transfers or self.transfers, {k for k in self.planned if k.startswith("TRANSFER")},
                                         self.transfer_expected)
                + checks.check_target_identities(records or self.target_records, self.expected_periods))

    def audit_contract(self, store=None) -> list[str]:
        store = self.store if store is None else store
        return checks.check_result_contract(store) + checks_4a.check_no_text_in_numeric(store, self.numeric)

    def audit_temporal(self, store=None, snapshot=None) -> list[str]:
        return checks.check_temporal(self.store if store is None else store,
                                     self.snapshot if snapshot is None else snapshot, DAYS_ISO, self.derived)[1]

    def audit_reexecution(self, after=None, again=None) -> list[str]:
        return checks.check_reexecution(JAN15.isoformat(), self.reex["before"], after or self.reex["after"],
                                        self.reex["first"], again or self.reex["again"])

    def audit_determinism(self, runs=None) -> list[str]:
        runs = runs or self.runs
        return checks.check_determinism(runs) + checks_4a.check_area_41_determinism(runs)

    def audit_state(self, stated=None) -> list[str]:
        return self.sa5["audit"](self.sa5["stated"] if stated is None else stated)

    def audit_non_regression(self, store=None) -> list[str]:
        return harness.non_regression(self.universe, self.store if store is None else store, self.context)[1]

    def audit_provenance(self, links_bytes=None, official_pending=16, fixture_pending=0) -> list[str]:
        return checks_4a.check_provenance(links_bytes or self.links_bytes, self.links_sha, official_pending,
                                          fixture_pending)


MUTATIONS = []


def mutation(mutation_id, contract, description, artifact, real_path):
    def register(fn):
        MUTATIONS.append({"mutation_id": mutation_id, "contract": contract, "description": description,
                          "artifact": artifact, "real_path": real_path, "fn": fn})
        return fn
    return register


def a41_key(store, variable, sv=None, period_len=10):
    return min(k for k in store if k[0] == variable and (sv is None or k[2] == sv) and len(k[3] or "") == period_len)


@mutation("EM4A-01", "alvos", "alvo do area_41 (retirada_condensado_linha VAR16031) omitido numa data", "written", C_RUN)
def _m01(w):
    written = copy.deepcopy(w.written)
    del written["2026-01-10"]["VAR16031"]
    return w.audit_run(written=written)


@mutation("EM4A-02", "alvos", "instância L5 de VAR16031 ausente numa data", "written", C_RUN)
def _m02(w):
    written = copy.deepcopy(w.written)
    written["2026-01-20"]["VAR16031"].discard(("linha", "L5"))
    return w.audit_run(written=written)


@mutation("EM4A-03", "nós", "nó EQUATION:EQ16011 (condicional L4_L5) não executado numa data", "executed_nodes", C_RUN)
def _m03(w):
    executed = copy.deepcopy(w.executed)
    executed["2026-01-05"] = [x for x in executed["2026-01-05"] if x[0] != "EQUATION:EQ16011"]
    return w.audit_run(executed=executed)


@mutation("EM4A-04", "nós", "ordem de dois nós do area_41 trocada", "executed_nodes", C_RUN)
def _m04(w):
    executed = copy.deepcopy(w.executed)
    day = executed["2026-01-06"]
    i = next(n for n, x in enumerate(day) if x[0] == "EQUATION:EQ16004")
    j = next(n for n, x in enumerate(day) if x[0] == "EQUATION:EQ16005")
    day[i], day[j] = day[j], day[i]
    return w.audit_run(executed=executed)


@mutation("EM4A-05", "transferências", "lth transferido (VAR16007) diverge do produtor yield.VAR11031", "transfers", C_RUN)
def _m05(w):
    records = copy.deepcopy(w.transfers)
    r = next(r for r in records if r["node"] == "TRANSFER:VAR16007")
    r["consumer"] = [r["consumer"][0], repr(float(r["consumer"][1]) + 1.0), None, None]
    return w.audit_run(transfers=records)


@mutation("EM4A-06", "transferências", "evento de transferência VAR16007 duplicado", "transfers", C_RUN)
def _m06(w):
    records = copy.deepcopy(w.transfers)
    records.append(copy.deepcopy(next(r for r in records if r["node"] == "TRANSFER:VAR16007")))
    return w.audit_run(transfers=records)


@mutation("EM4A-07", "transferências", "bloco-fonte do vínculo VAR16007 trocado (production)", "transfers", C_RUN)
def _m07(w):
    records = copy.deepcopy(w.transfers)
    next(r for r in records if r["node"] == "TRANSFER:VAR16007")["source_block"] = "production"
    return w.audit_run(transfers=records)


@mutation("EM4A-08", "identidade temporal", "VAR16032 (mensal) gravado no período diário", "target_records", C_RUN)
def _m08(w):
    records = list(w.target_records)
    i = next(n for n, r in enumerate(records) if r[1] == "VAR16032")
    day, variable, st, sv, _period = records[i]
    records[i] = (day, variable, st, sv, day)
    return w.audit_run(records=records)


@mutation("EM4A-09", "estado", "NO_APPLICABLE_RULE retirado de VAR16031@L4 (descendente do \"F\")", "SA5 stated", C_STATE)
def _m09(w):
    stated = dict(w.sa5["stated"])
    k = next(k for k in w.sa5["must"] if k[0] == "VAR16031" and k[2] == "L4")
    stated[k] = ["float", "1.0", None, None]
    return w.audit_state(stated)


@mutation("EM4A-10", "estado", "NO_APPLICABLE_RULE vazado para o grupo L1_L3 (isolamento)", "SA5 stated", C_STATE)
def _m10(w):
    stated = dict(w.sa5["stated"])
    k = next(k for k in w.sa5["plain"] if k[0] == "VAR16018")
    stated[k] = ["NoneType", "None", "NO_APPLICABLE_RULE", None]
    return w.audit_state(stated)


@mutation("EM4A-11", "estado", "estado trocado: INVALID_INPUT no lugar de NO_APPLICABLE_RULE em VAR16025", "SA5 stated", C_STATE)
def _m11(w):
    stated = dict(w.sa5["stated"])
    k = next(k for k in w.sa5["must"] if k[0] == "VAR16025")
    stated[k] = ["NoneType", "None", "INVALID_INPUT", None]
    return w.audit_state(stated)


@mutation("EM4A-12", "estado (Policy B)", "agregação mensal VAR16026 sem o estado do componente \"F\"", "SA5 stated", C_STATE)
def _m12(w):
    stated = dict(w.sa5["stated"])
    k = next(k for k in w.sa5["must"] if k[0] == "VAR16026")
    stated[k] = ["float", "100.0", None, None]
    return w.audit_state(stated)


@mutation("EM4A-13", "contrato de resultado", "\"F\" como texto no valor de VAR16025 (numerico)", "store", C_RUN)
def _m13(w):
    store = dict(w.store)
    store[a41_key(store, "VAR16025")] = ["str", "'F'", None, None]
    return w.audit_contract(store)


@mutation("EM4A-14", "contrato de resultado", "detail sem state numa chave do area_41", "store", C_RUN)
def _m14(w):
    store = dict(w.store)
    k = a41_key(store, "VAR16034")
    store[k] = [store[k][0], store[k][1], None, "x"]
    return w.audit_contract(store)


@mutation("EM4A-15", "temporal", "janela de 2026-01-10 de VAR16019 (mensal L1_L3) ausente", "store", C_TEMP)
def _m15(w):
    store = dict(w.store)
    del store[("VAR16019", "linha_grupo", "L1_L3", "2026-01", "2026-01-10")]
    return w.audit_temporal(store)


@mutation("EM4A-16", "temporal", "janela de janeiro do area_41 alterada depois de 2026-02-01", "january snapshot", C_TEMP)
def _m16(w):
    snapshot = dict(w.snapshot)
    k = min(k for k in snapshot if k[0] == "VAR16032")
    snapshot[k] = ["float", "0.0", None, None]
    return w.audit_temporal(None, snapshot)


@mutation("EM4A-17", "temporal", "janela anual YTD do area_41 com uma data a menos", "store", C_TEMP)
def _m17(w):
    store = dict(w.store)
    del store[("VAR16036", "linha_grupo", "L1_L7", "2026", "2026-01-20")]
    return w.audit_temporal(store)


@mutation("EM4A-18", "reexecução", "reexecução cria identidade nova do area_41", "after store", C_REEX)
def _m18(w):
    after = dict(w.reex["after"])
    after[("VAR16025", "linha_grupo", "L4_L5", "2026-01-15", "2026-01-15")] = ["float", "1.0", None, None]
    return w.audit_reexecution(after=after)


@mutation("EM4A-19", "reexecução", "transferência VAR16007 regravada (WRITTEN) na reexecução", "again events", C_REEX)
def _m19(w):
    again = copy.deepcopy(w.reex["again"])
    e = next(e for e in again if e[1] == "TRANSFER" and e[2] == "VAR16007")
    e[8] = "WRITTEN"
    return w.audit_reexecution(again=again)


@mutation("EM4A-20", "determinismo", "RUN_B (ORDER_B) com results_sha256 diferente", "fingerprints", C_DET)
def _m20(w):
    runs = copy.deepcopy(w.runs)
    runs["RUN_B"]["results_sha256"] = "0" * 64
    return w.audit_determinism(runs)


@mutation("EM4A-21", "determinismo", "HASH_SEED_B (4242) com hash do area_41 diferente", "fingerprints", C_DET)
def _m21(w):
    runs = copy.deepcopy(w.runs)
    runs["HASH_SEED_B"]["area_41_store_sha256"] = "f" * 64
    return w.audit_determinism(runs)


@mutation("EM4A-22", "não-regressão", "chave de um dos 421 alvos anteriores alterada", "store", C_NREG)
def _m22(w):
    store = dict(w.store)
    k = min(k for k, v in store.items() if k[0] not in w.universe.area_41_entities and v[0] == "float")
    store[k] = ["float", repr(float(store[k][1]) * 1.000001), None, None]
    return w.audit_non_regression(store)


@mutation("EM4A-23", "proveniência", "interblock_links.json alterado (1 byte)", "links bytes", C_PROV)
def _m23(w):
    return w.audit_provenance(links_bytes=w.links_bytes + b" ")


@mutation("EM4A-24", "proveniência", "PENDING_LOAD oficiais 15 em vez de 16", "registro oficial", C_PROV)
def _m24(w):
    return w.audit_provenance(official_pending=15)


@mutation("EM4A-25", "proveniência", "pendência no fixture (pending != [])", "fixture", C_PROV)
def _m25(w):
    return w.audit_provenance(fixture_pending=1)


POSITIVE = {
    "PC4A-01 run (alvos, nós, transferências, identidades)": lambda w: w.audit_run(),
    "PC4A-02 contrato de resultado + sem texto em numérico": lambda w: w.audit_contract(),
    "PC4A-03 temporal": lambda w: w.audit_temporal(),
    "PC4A-04 reexecução": lambda w: w.audit_reexecution(),
    "PC4A-05 determinismo": lambda w: w.audit_determinism(),
    "PC4A-06 estado (SA5)": lambda w: w.audit_state(),
    "PC4A-07 não-regressão dos 421": lambda w: w.audit_non_regression(),
    "PC4A-08 proveniência": lambda w: w.audit_provenance(),
}


def run_evidence_mutations() -> tuple[list[dict], list[dict]]:
    world = World()
    controls = []
    for name, fn in POSITIVE.items():
        problems = fn(world)
        controls.append({"control": name, "problems": len(problems), "result": "ACCEPT" if not problems else "REJECT",
                         "evidence": " | ".join(problems[:2])[:300]})
    rows = []
    for m in MUTATIONS:
        problems = m["fn"](world)
        rows.append({k: m[k] for k in ("mutation_id", "contract", "description", "artifact", "real_path")}
                    | {"detected": "TRUE" if problems else "FALSE", "problems": len(problems),
                       "first_problem": (problems[0] if problems else "")[:240]})
    return rows, controls


def main() -> int:
    problems = []
    before = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=common.REPO,
                            capture_output=True, text=True, check=True).stdout
    rows, controls = run_evidence_mutations()
    summary = {"label": common.LABEL, "stage": "4A",
               "evidence_mutations": {"defined": len(rows), "detected": sum(r["detected"] == "TRUE" for r in rows),
                                      "missed": [r["mutation_id"] for r in rows if r["detected"] != "TRUE"]},
               "positive_controls": {"total": len(controls), "accepted": sum(c["result"] == "ACCEPT" for c in controls),
                                     "rejected_unexpectedly": [c["control"] for c in controls if c["result"] != "ACCEPT"]}}
    problems += [f"EVIDENCE_MUTATION_SURVIVED {m}" for m in summary["evidence_mutations"]["missed"]]
    problems += [f"POSITIVE_CONTROL_REJECTED {c}" for c in summary["positive_controls"]["rejected_unexpectedly"]]
    code_rows = []
    if "--skip-code-mutants" not in sys.argv[1:]:
        code_summary, code_rows = code_mutants_4a.run_all()
        summary["code_mutants"] = code_summary
        problems += [f"CODE_MUTANT_SURVIVED {m}" for m in code_summary["surviving_ids"]]
        if code_summary["positive_control"]["result"] != "ACCEPT":
            problems.append(f"CODE_POSITIVE_CONTROL_REJECTED {code_summary['positive_control']['evidence']}")
        if not code_summary["repository_untouched"]:
            problems.append("REPOSITORY_TOUCHED app/data/tools alterados pela mutação")
        problems += [f"EXPECTED_DETECTOR_MISSED {k}: {v}" for k, v in code_summary["expected_detectors_missed"].items()]
        total = len(rows) + code_summary["introduced"]
        detected = summary["evidence_mutations"]["detected"] + code_summary["detected"]
        summary["detection_rate"] = f"{100.0 * detected / total:.1f}%"
    after = subprocess.run(["git", "status", "--porcelain", "--", "app", "data", "tools"], cwd=common.REPO,
                           capture_output=True, text=True, check=True).stdout
    summary["git_status_app_data_tools"] = {"before": before, "after": after, "empty": before == after == ""}
    if before or after:
        problems.append("REPOSITORY_TOUCHED git status app/data/tools não vazio")
    summary["problems"] = problems
    summary["result"] = "PASS" if not problems else "FAIL"
    if "--no-write" not in sys.argv[1:]:
        EVIDENCE.mkdir(exist_ok=True)
        if code_rows:
            with (EVIDENCE / "code_mutation_results.csv").open("w", encoding="utf-8", newline="") as handle:
                w = csv.DictWriter(handle, fieldnames=list(code_rows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(code_rows)
        for name, data in (("mutation_results.csv", rows), ("positive_controls.csv", controls)):
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
