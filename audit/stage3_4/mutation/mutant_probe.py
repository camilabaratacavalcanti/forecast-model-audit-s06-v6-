"""
Stage 3.4D — sonda integrada para MUTANTES DE CÓDIGO.

    python -I <árvore temporária>/audit/stage3_4/mutation/mutant_probe.py '<expected json>'

Executada dentro de uma árvore temporária (git archive HEAD + harness atual)
cujo `app/` pode ter sido mutado; `python -I` e o sys.path abaixo garantem que
só o `app/` dessa árvore é importado. Roda os auditores REAIS da 3.4C:

  * regressão contra a evidência versionada da 3.4C (fingerprint RUN_A e
    ordem dos 427 nós em nodes.csv);
  * cobertura de alvos, nós e transferências, identidade temporal e
    reexecução numa sequência de 32 datas;
  * cenários de estado SC1/SC2/SC3 e composições SC4.

Imprime {"problems": [...], "modules_outside_tree": [...]} — nenhuma escrita.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "audit" / "stage3_4" / "integrated")]

import checks  # noqa: E402
import fixture  # noqa: E402
import run_integrated as h  # noqa: E402

from app.domain.results import Result  # noqa: E402

FEB1 = h.FEB1


def step(problems: list, label: str, fn) -> None:
    try:
        problems += fn()
    except Exception as exc:  # noqa: BLE001 — exceção do engine mutado é detecção
        problems.append(f"{getattr(exc, 'code', type(exc).__name__)} [{label}] {str(exc)[:200]}")


def main() -> int:
    expected = json.loads(sys.argv[1])
    problems: list[str] = []
    o = fixture.build("A")
    plan = h.integrated_plan(o)

    def regression():
        p = []
        order = [s.key for s in plan.steps]
        if hashlib.sha256(json.dumps(order).encode()).hexdigest() != expected["plan_order_sha256"]:
            p.append("PLANNER_ORDER_REGRESSION ordem do plano != nodes.csv da 3.4C")
        fp = h.fingerprint("A")
        if fp["results_sha256"] != expected["results_sha256"]:
            p.append("INTEGRATED_REGRESSION results_sha256 != RUN_A da 3.4C")
        return p

    def coverage():
        events, instances = h.node_expectations(o, plan)
        context = h.fresh_context(o)
        traces, snapshot = {}, None
        for day in h.DAYS:
            if day == FEB1:
                snapshot = {k: v for k, v in h.store_of(context).items() if k[3] == "2026-01"}
            traces[day] = h.execute_day(o, plan, context, day)
        executed, written, records, _rows, p = h.observe(o, context, traces)
        planned = [s.key for s in plan.steps]
        p += checks.check_targets(instances, written) + checks.check_nodes(planned, events, executed)
        p += checks.check_transfers(records, {k for k in planned if k.startswith("TRANSFER")},
                                    h.transfer_expectations(o, plan))
        p += checks.check_target_identities(h.target_records(traces, set(plan.targets)),
                                            h.expected_periods(o, plan.targets, h.DAYS))
        store = h.store_of(context)
        p += checks.check_temporal(store, snapshot, [d.isoformat() for d in h.DAYS], h.derived_variables(plan))[1]
        p += checks.check_clean_context(store) + checks.check_result_contract(store)
        for day in h.REEXECUTE:
            before = h.store_of(context)
            trace = h.execute_day(o, plan, context, day)
            p += checks.check_reexecution(day.isoformat(), before, h.store_of(context), h.events_of(traces[day]),
                                          h.events_of(trace))
        return p

    def scenarios():
        p = []
        for build in (h.scenario_sc1, h.scenario_sc2, h.scenario_sc3):
            scenario = build(o, plan)
            p += scenario["audit"](scenario["stated"])
        for second, code in ((Result(None, h.VF, "x"), "MULTI_STATE_COMBINATION_UNDEFINED"),
                             (Result(None, h.INV, "y"), "MULTI_DETAIL_COMPOSITION_UNDEFINED"),
                             (Result(None, h.INV, "x"), None)):
            got, _store = h.composition_run(o, plan, second)
            if got != code:
                p.append(f"AGGREGATION_FAILURE composição {second}: {got} != {code}")
        return p

    stages = (("regression", regression), ("coverage", coverage), ("scenarios", scenarios))
    if "--regression-only" in sys.argv:          # segunda semente de hash: só fingerprint e ordem
        stages = stages[:1]
    for label, fn in stages:
        step(problems, label, fn)
    outside = sorted({m.__file__ for name, m in sys.modules.items()
                      if name.startswith("app") and getattr(m, "__file__", None)
                      and not Path(m.__file__).resolve().is_relative_to(ROOT.resolve())})
    print(json.dumps({"problems": problems, "modules_outside_tree": outside}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
