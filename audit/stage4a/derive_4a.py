"""
Stage 4A.1 — derivação EMPÍRICA (planner/engine) do universo de 5 blocos e auditoria
específica do area_41, confrontada com o recálculo independente (REAL_DERIVED_TEST_RESULT).

    python audit/stage4a/derive_4a.py [--no-write]

1. universo 5 blocos (fixture REAL_DERIVED), 4 blocos (3.4C) e area_41 isolado;
2. recálculo independente (`python -I independent_count.py`) confrontado campo a campo;
3. plano oficial (sem fixture) x plan_evidence.csv (3.2); 16 PENDING_LOAD; sha256 dos vínculos;
4. árvore de decisão de `hes` (25 combinações x 2 grupos) no ENGINE x avaliação literal do workbook;
5. retorno "F": estado, value, detail e propagação (verificação técnica, §10.5);
6. escopos: sufixos aceitos pelo parser, escopo da equação x escopo da variável-alvo;
7. regras de agregação do area_41; entradas (vínculo x fronteira); unidades e descrições;
8. coluna OBS do workbook (openpyxl) classificada.

Sem `--no-write`: grava `evidence/contract_audit.json`, `evidence/obs_register.csv`,
`evidence/hes_decision_matrix.csv` e `contract_expectations.json` (expectativas do contrato).
Com `--no-write`: confronta com o `contract_expectations.json` versionado.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common  # noqa: E402
import independent_count as independent  # noqa: E402  (funções puras; o processo -I prova a independência)

from app.engine.expression_parser import ExpressionParser  # noqa: E402
from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.interblock_orchestrator import (  # noqa: E402
    AGGREGATION, EQUATION, TRANSFER, InterblockExecutionOrchestrator, InterblockSourceNotLoadedError,
)
from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.scoped_reference import InvalidScopeReferenceError, scope_type_for  # noqa: E402
from app.validation.variable_seed_validator import ALLOWED_UNITS  # noqa: E402

REPO = common.REPO
EVIDENCE = HERE / "evidence"
EXPECTATIONS = HERE / "contract_expectations.json"
BASELINE = "d2847ab36933668bf4a1299b3ffe058827a82037"
HES = independent.HES_VALUES
NAR = "NO_APPLICABLE_RULE"


def git_bytes(spec: str) -> bytes:
    return subprocess.run(["git", "show", spec], cwd=REPO, capture_output=True, check=True).stdout


# ------------------------------------------------------------------ 1. universo
def universe(u: common.Universe) -> dict:
    o, catalog = u.orchestrator, u.orchestrator.catalog
    engine = ForecastEngine()
    plan_a = o.plan(o.targets_of_blocks(("area_41",)))
    out = {}
    for label, plan in (("universe_5", u.plan), ("universe_4", u.plan4), ("universe_area_41_only", plan_a)):
        steps = plan.steps
        eq = sum(len(engine.materialize_equation(catalog.equation_definitions.get(s.node_id)))
                 for s in steps if s.kind == EQUATION)
        agg = sum(1 for s in steps if s.kind == AGGREGATION for i in catalog.aggregation_rule_instances.all()
                  if i.rule.aggregation_rule_id == s.node_id)
        tr = sum(len(catalog.links.link_for(s.node_id).instances) for s in steps if s.kind == TRANSFER)
        by_block: dict = {}
        for s in steps:
            by_block.setdefault(s.block, Counter())[s.kind] += 1
        out[label] = {"targets": len(plan.targets),
                      "targets_by_block": dict(Counter(catalog.block_of.get(t) for t in plan.targets)),
                      "nodes": len(steps), "nodes_by_kind": dict(sorted(Counter(s.kind for s in steps).items())),
                      "nodes_by_block": {b: dict(sorted(c.items())) for b, c in sorted(by_block.items())},
                      "required_inputs": len(plan.required_inputs), "pending_blockers": len(plan.pending_blockers),
                      "equation_instances": eq, "aggregation_instances": agg,
                      "transfer_instances_per_date": tr, "events_per_date": eq + agg + tr,
                      "transfers": sorted(s.key for s in steps if s.kind == TRANSFER)}
    k4 = [s.key for s in u.plan4.steps]
    ka = [s.key for s in plan_a.steps]
    k5 = [s.key for s in u.plan.steps]
    out["union"] = {"nodes_4": len(k4), "nodes_area_41_only": len(ka), "shared": sorted(set(k4) & set(ka)),
                    "union": len(set(k4) | set(ka)), "union_equals_5": set(k4) | set(ka) == set(k5),
                    "plan4_relative_order_preserved_in_5": [k for k in k5 if k in set(k4)] == k4}
    out["link_VAR16007_used_in_5"] = "TRANSFER:VAR16007" in k5
    out["link_VAR16007_used_in_4"] = "TRANSFER:VAR16007" in k4
    # eventos por data observados numa execução real de 1 dia
    context = u.fresh_context()
    trace = u.execute_day(context, common.START)
    out["observed_events_one_day"] = len(trace.events)
    out["observed_transfer_events_one_day"] = len(trace.of_kind(TRANSFER))
    out["required_inputs_area_41"] = [v for v in u.plan.required_inputs if v in u.area_41_entities]
    out["input_protocol"] = {"plan4_inputs": len(u.plan4.required_inputs),
                             "area_41_positions_in_plan5": [i for i, v in enumerate(u.plan.required_inputs)
                                                            if v in u.area_41_entities],
                             "area_41_indices_assigned": sorted(u.index[v] for v in u.plan.required_inputs
                                                                if v in u.area_41_entities),
                             "plan4_inputs_keep_3_4c_index": all(u.index[v] == i
                                                                 for i, v in enumerate(u.plan4.required_inputs))}
    return out


# ------------------------------------------------------------------ 3. plano oficial
def official_plan() -> dict:
    official = InterblockExecutionOrchestrator.from_seed_root(common.fixture.SEED)
    rows = {}
    for target in official.targets_of_blocks(common.BLOCKS5):
        block = official.catalog.block_of.get(target)
        try:
            plan = official.plan([target])
            rows[target] = (block, "OK", "", str(len(plan.steps)))
        except InterblockSourceNotLoadedError:
            report = official.plan([target], on_pending="report")
            blocked = ";".join(sorted({b.source_block for b in report.pending_blockers}))
            rows[target] = (block, "INTERBLOCK_SOURCE_NOT_LOADED", blocked, "")
    evidence = {r["target"]: (r["block"], r["observed"], r["pending_blocks"], r["steps"])
                for r in csv.DictReader(independent.PLAN_EVIDENCE.open(encoding="utf-8"))}
    links_now = (common.fixture.SEED / "interblock_links.json").read_bytes()
    links_base = git_bytes(f"{BASELINE}:data/seed/interblock_links.json")
    area = [v for v in rows.values() if v[0] == "area_41"]
    return {"targets": len(rows), "identical_to_plan_evidence": rows == evidence,
            "differences": sorted(t for t in set(rows) | set(evidence) if rows.get(t) != evidence.get(t)),
            "area_41": dict(Counter(v[1] for v in area)),
            "area_41_pending_blocks": sorted({v[2] for v in area if v[2]}),
            "pending_links": len(official.catalog.links.pending()),
            "pending_by_source_block": dict(sorted(Counter(p.source_block for p in official.catalog.links.pending()).items())),
            "interblock_links_sha256": hashlib.sha256(links_now).hexdigest(),
            "interblock_links_sha256_at_baseline": hashlib.sha256(links_base).hexdigest()}


# ------------------------------------------------------------------ 4/5. hes e "F"
HES_NUMBERS = {"VAR16005": 3.0, "VAR16015": 2.0, "VAR16006": 3.0, "VAR16016": 2.0,
               "VAR16022": 3.0, "VAR16023": 3.0, "VAR16024": 5.0}       # mesmas entradas da avaliação independente
GROUPS = {"L4_L5": ("EQ16011", "VAR16025", ("L4", "L5"), ("VAR16005", "VAR16015", "VAR16022", "VAR16024")),
          "L6_L7": ("EQ16012", "VAR16028", ("L6", "L7"), ("VAR16006", "VAR16016", "VAR16023"))}


def hes_engine(o) -> list[dict]:
    rows = []
    for group, (eq, target, (la, lb), operands) in GROUPS.items():
        for a in HES:
            for b in HES:
                inputs = {(v, "linha_grupo", group): HES_NUMBERS[v] for v in operands}
                inputs[("VAR16021", "linha", la)] = a
                inputs[("VAR16021", "linha", lb)] = b
                results, error = common.engine_area_41(o, inputs, only={eq})
                r = results.get((target, "linha_grupo", group))
                rows.append({"group": group, "hes_first": a, "hes_second": b,
                             "engine_value": None if r is None else r.value,
                             "engine_value_type": None if r is None else type(r.value).__name__,
                             "engine_state": None if r is None else r.state,
                             "engine_detail": None if r is None else r.detail,
                             "engine_error": common.error_chain(error) if error else None})
    return rows


def f_propagation(o) -> dict:
    """(Normal, 1 By pass e LC) em L4/L5 e (1 By pass e LC, Normal) em L6/L7: alvos e descendentes."""
    out = {}
    base = {("VAR16001", "linha_grupo", "L1_L3"): 1500.0, ("VAR16002", "linha_grupo", "L4_L5"): 1500.0,
            ("VAR16003", "linha_grupo", "L6_L7"): 1500.0, ("VAR16011", "linha_grupo", "L1_L3"): 1.1,
            ("VAR16012", "linha_grupo", "L4_L5"): 1.1, ("VAR16013", "linha_grupo", "L6_L7"): 1.1,
            ("VAR16022", "linha_grupo", "L4_L5"): 3.0, ("VAR16023", "linha_grupo", "L6_L7"): 3.0,
            ("VAR16024", "linha_grupo", "L4_L5"): 5.0}
    base.update({("VAR16017", "linha", f"L{i}"): 47.0 for i in (1, 2, 3)})
    base.update({("VAR16007", "linha", f"L{i}"): 1000.0 + 10 * i for i in range(1, 8)})
    for label, hes in (("L4_L5_(Normal,1BPLC)", ("Normal", "1 By pass e LC", "Normal", "Normal")),
                       ("L4_L5_(1BPLC,Normal)", ("1 By pass e LC", "Normal", "Normal", "Normal")),
                       ("L6_L7_(Normal,1BPLC)", ("Normal", "Normal", "Normal", "1 By pass e LC")),
                       ("L6_L7_(1BPLC,Normal)", ("Normal", "Normal", "1 By pass e LC", "Normal"))):
        inputs = dict(base)
        inputs.update({("VAR16021", "linha", line): h for line, h in zip(("L4", "L5", "L6", "L7"), hes)})
        results, error = common.engine_area_41(o, inputs)
        out[label] = {"error": common.error_chain(error) if error else None,
                      "stated": {f"{k[0]}@{k[2]}": [r.value, r.state, r.detail]
                                 for k, r in sorted(results.items()) if r.state is not None},
                      "unstated_count": sum(1 for r in results.values() if r.state is None)}
    return out


# ------------------------------------------------------------------ 6. escopos
def scopes(o) -> dict:
    catalog = o.catalog
    parser, engine = ExpressionParser(), ForecastEngine()
    suffixes = {}
    for token in ("L1", "L4", "L7", "L1_L3", "L4_L5", "L6_L7", "L1_L7", "L8", "L1_L5", "L4_L7", "L2_L3"):
        try:
            suffixes[token] = scope_type_for(token)
        except InvalidScopeReferenceError as exc:
            suffixes[token] = f"REJEITADO: {type(exc).__name__}"
    parse_errors, mismatches, coverage = [], [], {}
    produced: dict = {}
    for d in common.area_41_equations(o):
        try:
            parser.parse(d.expression)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append(f"{d.equation_definition_id}: {exc}")
        target = catalog.variable_definitions.get(d.target_variable_id)
        target_scopes = set(ScopeResolver().resolve_scopes(target.scope_type, target.scope_value))
        eq_scopes = [(i.scope_type, i.scope_value) for i in engine.materialize_equation(d)]
        if not set(eq_scopes) <= target_scopes or d.scope_type != target.scope_type:
            mismatches.append(f"{d.equation_definition_id}: {eq_scopes} fora de {sorted(target_scopes)}")
        produced.setdefault(d.target_variable_id, []).extend(eq_scopes)
    for variable_id, got in produced.items():
        target = catalog.variable_definitions.get(variable_id)
        want = ScopeResolver().resolve_scopes(target.scope_type, target.scope_value)
        coverage[variable_id] = {"instances": len(want), "covered_once": sorted(got) == sorted(want)}
    return {"suffix_scope_type": suffixes, "parse_errors": parse_errors,
            "equation_vs_target_scope_mismatches": mismatches, "target_instance_coverage": coverage}


# ------------------------------------------------------------------ 7. agregações, entradas, documentação
def aggregations(o) -> list[dict]:
    catalog = o.catalog
    rows = []
    for rule_id in sorted({i.rule.aggregation_rule_id for i in catalog.aggregation_rule_instances.all()
                           if catalog.block_of.get(i.rule.aggregation_rule_id) == "area_41"}):
        instances = [i for i in catalog.aggregation_rule_instances.all() if i.rule.aggregation_rule_id == rule_id]
        rule = instances[0].rule
        rows.append({"rule": rule_id, "type": rule.aggregation_type, "source": rule.source_variable_id,
                     "source_frequency": rule.source_frequency, "target": rule.target_variable_id,
                     "target_frequency": rule.target_frequency, "weight": rule.weight_variable_id,
                     "integration_factor": getattr(rule, "integration_factor", None),
                     "instances": sorted(f"{i.scope_type}/{i.scope_value}" for i in instances)})
    return rows


def ytd_probe(u: common.Universe) -> dict:
    """3 datas no grafo de 5 blocos: o anual de 2026-01-03 = média dos 3 diários (YTD parcial)."""
    days = common.DAYS[:3]
    context, _traces = u.run_sequence(days)
    store = common.ri.store_of(context)
    daily = [store[("VAR16018", "linha_grupo", "L1_L3", d.isoformat(), None)] for d in days]
    annual = store[("VAR16020", "linha_grupo", "L1_L3", "2026", days[-1].isoformat())]
    values = [float(v[1]) for v in daily]
    return {"annual_2026_window_2026-01-03": annual, "daily_values": values,
            "mean_of_3": sum(values) / 3, "windows_of_annual_identity": sorted(
                k[4] for k in store if k[:4] == ("VAR16020", "linha_grupo", "L1_L3", "2026")),
            "coverage_class": "YEAR_TO_DATE_PARTIAL_COVERAGE"}


def inputs_and_docs(u: common.Universe) -> dict:
    catalog = u.orchestrator.catalog
    links = {link.consumer_definition_id: link for link in catalog.links.links()}
    pending = {p.consumer_definition_id: p for p in
               InterblockExecutionOrchestrator.from_seed_root(common.fixture.SEED).catalog.links.pending()}
    rows, docs = [], []
    for variable_id in sorted(u.area_41_entities):
        d = catalog.variable_definitions.get(variable_id)
        if d.variable_type in ("entrada", "entrada_externa"):
            origin = ("VÍNCULO " + links[variable_id].source_block + "." + links[variable_id].source_definition_id
                      if variable_id in links else
                      "PENDENTE " + pending[variable_id].source_block + " (entrada livre só no fixture)"
                      if variable_id in pending else "FRONTEIRA (entrada_externa; valor arbitrário do fixture)")
            rows.append({"variable": f"{d.variable_name} ({variable_id})", "type": d.variable_type,
                         "frequency": d.frequency, "scope": f"{d.scope_type}/{d.scope_value}", "origin": origin})
        if d.unit not in ALLOWED_UNITS:
            docs.append(f"UNIT_OUTSIDE_ENUM {variable_id} {d.unit!r}")
        if not d.description:
            docs.append(f"EMPTY_DESCRIPTION {d.variable_name} ({variable_id}) — descrições só por instância")
    return {"inputs": rows, "documentation_points": docs}


# ------------------------------------------------------------------ principal
def main() -> int:
    problems: list[str] = []
    u = common.Universe("A")
    o = u.orchestrator
    audit: dict = {"label": common.LABEL}
    audit.update(universe(u))
    audit["official_plan"] = official_plan()

    completed = subprocess.run([sys.executable, "-I", str(HERE / "independent_count.py")],
                               cwd=REPO, capture_output=True, text=True)
    ind = json.loads(completed.stdout)
    audit["independent"] = {"result": ind["result"], "imports_app_or_tools": ind["imports_app_or_tools"]}
    if completed.returncode != 0:
        problems.append(f"INDEPENDENT_COUNT_FAILURE {ind['problems']}")
    compared = []
    for section in ("universe_5", "universe_4", "universe_area_41_only"):
        for field, value in ind[section].items():
            compared.append(f"{section}.{field}")
            if audit[section][field] != value:
                problems.append(f"DERIVED_VS_INDEPENDENT {section}.{field}: {audit[section][field]} != {value}")
    for field in ("shared", "union", "union_equals_5"):
        compared.append(f"union.{field}")
        if audit["union"][field] != ind["union"][field]:
            problems.append(f"DERIVED_VS_INDEPENDENT union.{field}")
    for field in ("area_41", "area_41_pending_blocks", "pending_links", "pending_by_source_block"):
        compared.append(f"official_plan.{field}")
        if audit["official_plan"][field] != ind["official_plan"][field]:
            problems.append(f"DERIVED_VS_INDEPENDENT official_plan.{field}")
    if audit["link_VAR16007_used_in_5"] != ind["link_VAR16007_used_in_5"]:
        problems.append("DERIVED_VS_INDEPENDENT link_VAR16007_used_in_5")
    audit["independent"]["fields_compared"] = len(compared)
    if audit["observed_events_one_day"] != audit["universe_5"]["events_per_date"]:
        problems.append("UNIVERSE_FAILURE eventos observados != eventos derivados")
    plan = audit["official_plan"]
    if not plan["identical_to_plan_evidence"]:
        problems.append(f"OFFICIAL_PLAN_CHANGED {plan['differences'][:3]}")
    if plan["interblock_links_sha256"] != plan["interblock_links_sha256_at_baseline"]:
        problems.append("INTERBLOCK_LINKS_CHANGED")

    # hes: engine x avaliação literal do workbook
    literal = {(r["group"], r["hes_first"], r["hes_second"]): r for r in independent.hes_matrix()}
    engine_rows = hes_engine(o)
    matrix = []
    for r in engine_rows:
        lit = literal[(r["group"], r["hes_first"], r["hes_second"])]
        expected_state = NAR if lit["value"] == "F" else None
        expected_value = None if lit["value"] == "F" else lit["value"]
        agree = (r["engine_error"] is None and r["engine_state"] == expected_state
                 and r["engine_value"] == expected_value and r["engine_detail"] is None)
        matrix.append({**r, "workbook_branch": lit["branch"], "workbook_value": lit["value"], "agree": agree})
        if not agree:
            problems.append(f"HES_ENGINE_VS_WORKBOOK {r['group']} ({r['hes_first']}, {r['hes_second']}): {r} x {lit}")
    f_rows = [m for m in matrix if m["workbook_branch"] == "F"]
    audit["hes"] = {"combinations": len(matrix), "agree": sum(m["agree"] for m in matrix),
                    "f_combinations": sorted([m["group"], m["hes_first"], m["hes_second"]] for m in f_rows),
                    "branch_counts": {g: dict(sorted(Counter(m["workbook_branch"] for m in matrix
                                                             if m["group"] == g).items())) for g in GROUPS}}
    audit["f_literal"] = {"engine_results": sorted({(m["engine_value_type"], repr(m["engine_value"]), m["engine_state"],
                                                     repr(m["engine_detail"])) for m in f_rows}),
                          "value_is_text": any(isinstance(m["engine_value"], str) for m in matrix),
                          "propagation": f_propagation(o)}
    if audit["f_literal"]["value_is_text"]:
        problems.append("F_LITERAL_AS_VALUE texto no valor de variável numérica")

    audit["scopes"] = scopes(o)
    if audit["scopes"]["parse_errors"] or audit["scopes"]["equation_vs_target_scope_mismatches"]:
        problems.append("SCOPE_FAILURE parser/escopo")
    if not all(c["covered_once"] for c in audit["scopes"]["target_instance_coverage"].values()):
        problems.append("SCOPE_FAILURE instância de alvo não coberta exatamente uma vez")
    audit["aggregations"] = aggregations(o)
    audit["ytd_probe"] = ytd_probe(u)
    if abs(float(audit["ytd_probe"]["annual_2026_window_2026-01-03"][1]) - audit["ytd_probe"]["mean_of_3"]) > 1e-9:
        problems.append("YTD_FAILURE anual != média das datas executadas")
    audit.update(inputs_and_docs(u))
    obs = independent.obs_register()
    audit["obs"] = {"rows": len(obs), "by_classification": dict(Counter(r["classification"] for r in obs)),
                    "distinct_texts": len({r["obs"] for r in obs})}

    expectations = {
        "independent": {
            "universe_5.targets": audit["universe_5"]["targets"],
            "universe_5.nodes": audit["universe_5"]["nodes"],
            "universe_5.nodes_by_kind": audit["universe_5"]["nodes_by_kind"],
            "universe_5.required_inputs": audit["universe_5"]["required_inputs"],
            "universe_5.equation_instances": audit["universe_5"]["equation_instances"],
            "universe_5.aggregation_instances": audit["universe_5"]["aggregation_instances"],
            "universe_5.transfer_instances_per_date": audit["universe_5"]["transfer_instances_per_date"],
            "universe_5.events_per_date": audit["universe_5"]["events_per_date"],
            "universe_4.nodes": audit["universe_4"]["nodes"],
            "union.shared": audit["union"]["shared"],
            "official_plan.area_41": audit["official_plan"]["area_41"],
            "official_plan.pending_links": audit["official_plan"]["pending_links"],
            "interblock_links_sha256": audit["official_plan"]["interblock_links_sha256"],
            "hes_f_combinations": [list(x) for x in independent.json.loads(json.dumps(ind["hes_f_combinations"]))],
            "obs_rows": len(obs),
        },
        "integrated": {
            "official_targets": 446, "integrated_targets": audit["universe_5"]["targets"],
            "area_41_targets": audit["universe_5"]["targets_by_block"].get("area_41"),
            "planner_nodes": audit["universe_5"]["nodes"],
            "nodes_by_kind": audit["universe_5"]["nodes_by_kind"],
            "transfers": audit["universe_5"]["transfers"],
            "required_inputs": audit["universe_5"]["required_inputs"],
            "events_per_date": audit["universe_5"]["events_per_date"],
            "transfer_events_per_date": audit["universe_5"]["transfer_instances_per_date"],
            "pending_blockers": 0, "previous_targets": audit["universe_4"]["targets"],
            "previous_nodes": audit["universe_4"]["nodes"], "dates": len(common.DAYS),
            "interblock_links_sha256": audit["official_plan"]["interblock_links_sha256"],
        },
    }
    audit["problems"] = problems
    audit["result"] = "PASS" if not problems else "FAIL"

    if "--no-write" in sys.argv[1:]:
        committed = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
        if json.loads(json.dumps(expectations)) != committed:
            problems.append("EXPECTATIONS_DRIFT expectativas derivadas != contract_expectations.json")
            audit["result"] = "FAIL"
    else:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / "contract_audit.json").write_text(
            json.dumps(audit, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
        EXPECTATIONS.write_text(json.dumps(expectations, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                encoding="utf-8")
        with (EVIDENCE / "obs_register.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=list(obs[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(obs)
        with (EVIDENCE / "hes_decision_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=list(matrix[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(matrix)
    print(json.dumps({k: audit[k] for k in ("universe_5", "union", "official_plan", "hes", "f_literal", "independent",
                                            "problems", "result")}, indent=1, ensure_ascii=False, default=str))
    return 0 if audit["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
