"""
Stage 3.4D — sonda dos auditores da 3.4C NO BASELINE (043fe9c), antes do reforço.

    python audit/stage3_4/mutation/baseline_gap_probe.py [--no-write]

Extrai `audit/stage3_4/integrated` do commit 043fe9c (git archive, diretório
temporário) e aplica ao auditor ORIGINAL (checks.py / run_integrated.py daquele
commit) as mutações que a 3.4D identificou como gaps. Registra, para cada uma,
se o auditor original a rejeitava e por qual sinal. É a evidência de que os
reforços dos detectores (Stage 3.4D) fecharam gaps reais do harness, e não
foram criados para "procurar outro sinal". Nenhum código de produção é tocado.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = "043fe9c36d9d02664db8be7dd29c0fd7014c73f8"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stage3_4d_probe_") as tmp:
        archive = subprocess.run(["git", "archive", BASELINE, "audit/stage3_4/integrated"], cwd=REPO,
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True)
        old = Path(tmp) / "audit" / "stage3_4" / "integrated"
        sys.path[:0] = [str(old), str(REPO)]
        h = importlib.import_module("run_integrated")
        checks = importlib.import_module("checks")
        assert Path(checks.__file__).resolve().parent == old.resolve()
        # o fixture extraído aponta para seeds relativos ao diretório temporário: usa os seeds
        # do repositório (data/ é idêntico ao baseline — verificado pela 3.4D).
        h.fixture.SEED = REPO / "data" / "seed"
        from app.domain.results import Result
        from app.engine.interblock_orchestrator import TRANSFER, ExecutionTrace

        o = h.fixture.build("A")
        plan = h.integrated_plan(o)
        planned = [s.key for s in plan.steps]
        transfer_nodes = {k for k in planned if k.startswith(TRANSFER)}
        probes = {}

        # G1/G2 — cenário SC1 original (12 dias) com o auditor original do SC1
        def overrides(d):
            return [("VAR12066", "linha", "L3", "2026", Result(0.0001)), ("VAR12066", "linha", "L4", "2026", Result(1.0e6))]

        def injections(d):
            return [("VAR12024", "linha", sv, "2026-01", Result(None, "INVALID_INPUT", "fa")) for sv in ("L3", "L4")]
        days = h.DAYS[:12]
        clean, stated, _ = h.twin(o, plan, days, overrides, injections)
        descendants = h.descendants_of(o, {"VAR12024"})
        jan10 = date(2026, 1, 10)
        must = [h.key("VAR12031", "linha", "L3", jan10)] + [h.key(v, "linha", "L3", jan10)
                                                            for v in ("VAR11031", "VAR13062", "VAR18008")]

        def sc1_audit(store):
            return (checks.check_state_diff(clean, store, descendants, "INVALID_INPUT", "fa")
                    + checks.check_expectations(store, must, [], "INVALID_INPUT", "fa"))
        control = sc1_audit(stated)
        reach = h.key("VAR12031", "linha", "L3", date(2026, 1, 5))
        probes["G1_state_reach_unnamed_date"] = {"mutation": "VAR12031 L3 2026-01-05 perde o estado",
                                                 "problems": sc1_audit({**stated, reach: clean[reach]})}
        probes["G2_value_with_state"] = {"mutation": "VAR12031 L3 2026-01-05 = valor + INVALID_INPUT/fa",
                                         "problems": sc1_audit({**stated, reach: ["float", "1.0", "INVALID_INPUT", "fa"]})}

        # G3/G4 — transferência duplicada e reatribuída, auditor original de transferências
        ctx, traces = h.run_sequence(o, plan, h.DAYS[:2])
        day = h.DAYS[1]
        evts = list(traces[day].events)
        i = next(i for i, e in enumerate(evts) if e.kind == TRANSFER and e.node_id == "VAR18006")

        def transfer_audit(events):
            _e, _w, records, _r, _p = h.observe(o, ctx, {day: ExecutionTrace(day, plan, events)})
            return checks.check_transfers(records, transfer_nodes)
        probes["G3_duplicated_transfer_interblock_check"] = {
            "mutation": "evento TRANSFER:VAR18006 duplicado", "problems": transfer_audit(evts[:i + 1] + [evts[i]] + evts[i + 1:])}
        j = next(i for i, e in enumerate(evts) if e.kind == TRANSFER and e.node_id == "VAR11031" and e.scope_value == "L2")
        relabel = list(evts)
        relabel[j] = dataclasses.replace(relabel[j], node_id="VAR13062", variable_id="VAR13062")
        probes["G4_transfer_wrong_target_interblock_check"] = {
            "mutation": "TRANSFER:VAR11031 L2 atribuída a VAR13062", "problems": transfer_audit(relabel)}

        # G5 — identidade temporal: condição original (043fe9c run_integrated.py §6) ignora
        # identidades com window None (`None not in v`); inspeção do código do commit.
        source = (old / "run_integrated.py").read_text(encoding="utf-8")
        probes["G5_monthly_identity_without_window"] = {
            "mutation": "identidade mensal derivada com window_end None",
            "inspection": "filtro `None not in v` presente em 043fe9c" if "None not in v" in source else "ausente",
            "problems": [] if "None not in v" in source else ["?"]}

    summary = {"baseline": BASELINE, "control_sc1_original_problems": control,
               "probes": {k: {**v, "detected_by_original_auditor": bool(v["problems"])} for k, v in probes.items()}}
    if "--no-write" not in sys.argv[1:]:
        (HERE / "baseline_gap_probe.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n",
                                                      encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
