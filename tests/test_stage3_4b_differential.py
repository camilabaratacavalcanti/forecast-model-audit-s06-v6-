"""
Stage 3.4B — testes do contrato diferencial (DIFFERENTIAL_REGRESSION_ORACLE).

Validam o próprio harness em `audit/stage3_4/differential/`:
    * comparador exato e sensível (sem tolerância, sem normalização);
    * detecção de faltantes, duplicados e excedentes pela ExecutionCaseKey;
    * execução real ponta a ponta (7877551 x HEAD, git archive + python -I);
    * a evidência versionada reproduz a matriz executada e o universo atual
      (392 instâncias de equação, 395 de agregação, 3 vetores, 2 datas).
Nenhum teste altera o engine.

Stage 4C (classe H, DR-4C-3): a afirmação diferencial é a do fechamento da 3.4B. A execução real
roda o harness SEM alteração num clone temporário fixado em 4d54804 (intervalo 7877551..4d54804,
com os dados daquele commit), e o universo da evidência é recalculado no mesmo clone. Nunca lê o
HEAD: o runtime de referência não aceita dados de stages futuras. Regressões do app no HEAD ficam
com as regressões vivas (classe R) das 3.4C/4A/4B.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audit" / "baselines"))
import historical  # noqa: E402  (Stage 4C: clone no fechamento)

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "audit" / "stage3_4" / "differential"
sys.path.insert(0, str(HARNESS))

from compare import NA, case_key, compare_case, coverage, exact_equal  # noqa: E402

from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.repositories.seed_loader import SeedLoader  # noqa: E402

BLOCKS = ("energy", "max_ht", "production", "yield")
VECTORS = ("VECTOR_A", "VECTOR_B", "VECTOR_C")
DATES = ("2026-09-03", "2026-12-31")
CLOSURE_3_4B = "4d54804"


def value(v):
    return [type(v).__name__, repr(v)]


def equation_case(returned, stored=None, state=NA, detail=NA, **extra):
    base = {"block": "energy", "operation_type": "EQUATION", "instance_id": "EQ18003@v1@L1",
            "definition_id": "EQ18003", "target": "VAR18017", "scope": ["linha", "L1"],
            "period_id": "2026-09-03", "input_vector": "VECTOR_A", "run_date": "2026-09-03"}
    base.update(extra)
    stored = returned if stored is None else stored
    base["outcome"] = ["OK", value(returned), value(stored), state, detail]
    return base


def aggregation_case(v, state=NA, detail=NA):
    return {"block": "max_ht", "operation_type": "AGGREGATION", "instance_id": "AGR-X@linha@L1",
            "definition_id": "AGR-X", "aggregation_type": "SUM", "integration_factor": 24.0,
            "target": "VAR13066", "scope": ["linha", "L1"], "period_id": "2026", "input_vector": "VECTOR_B",
            "run_date": "2026-12-31",
            "outcome": ["OK", value(v), ["VAR13066", "linha", "L1", "anual", "2026"], state, detail]}


# ------------------------------------------------------------ comparador

def test_negative_comparator_10_vs_10_0000001_fails():
    reference = equation_case(10)
    candidate = equation_case(10.0000001, state=None, detail=None)
    assert compare_case(reference, candidate) == ["VALUE_DIFFERENCE"]
    assert compare_case(aggregation_case(10.0), aggregation_case(10.0000001, state=None, detail=None)) == \
        ["VALUE_DIFFERENCE"]


@pytest.mark.parametrize("left, right", [(1, 1.0), (None, 0), (0.0, float("nan")), (0.1 + 0.2, 0.3), (-0.0, 0.0)])
def test_no_normalization_between_distinct_representations(left, right):
    assert not exact_equal(value(left), value(right))
    assert "VALUE_DIFFERENCE" in compare_case(equation_case(left), equation_case(right))


def test_identical_results_match_and_reference_state_is_not_applicable():
    assert compare_case(equation_case(3.25), equation_case(3.25, state=None, detail=None)) == []
    assert compare_case(aggregation_case(7.5), aggregation_case(7.5, state=None, detail=None)) == []


def test_candidate_state_or_detail_on_the_stateless_path_is_a_difference():
    ref = equation_case(1.0)
    assert compare_case(ref, equation_case(1.0, state="INVALID_INPUT", detail=None)) == ["STATE_DIFFERENCE"]
    assert compare_case(ref, equation_case(1.0, state=None, detail="x")) == ["DETAIL_DIFFERENCE"]


def test_returned_and_stored_values_are_both_compared():
    assert compare_case(equation_case(2.0), equation_case(2.0, stored=2.5, state=None, detail=None)) == \
        ["VALUE_DIFFERENCE"]


def test_structural_exception_and_missing_results_are_reported():
    ref = aggregation_case(1.0)
    other = aggregation_case(1.0, state=None, detail=None)
    other["outcome"][2] = ["VAR13066", "linha", "L1", "anual", "2025"]
    assert compare_case(ref, other) == ["STRUCTURAL_DIFFERENCE"]
    broken = dict(ref, outcome=["EXCEPTION", "ZeroWeightSumError: x"])
    assert compare_case(ref, broken) == ["EXCEPTION_DIFFERENCE"]
    assert compare_case(broken, broken) == ["EXCEPTION_DIFFERENCE"]          # exceção nunca é "igual"
    assert compare_case(None, ref) == ["MISSING_REFERENCE_RESULT"]
    assert compare_case(ref, None) == ["MISSING_CANDIDATE_RESULT"]


def test_coverage_detects_duplicates_missing_and_unexpected():
    a, b = equation_case(1.0), equation_case(1.0, input_vector="VECTOR_B")
    expected = {case_key(a), case_key(b), ("energy", "EQUATION", "EQ18003@v1@L1", "VECTOR_C", "2026-09-03")}
    extra = equation_case(1.0, instance_id="EQ9@v1@L1")
    result = coverage([a, a, extra], expected)
    assert result["duplicates"] == [case_key(a)]
    assert set(result["missing"]) == expected - {case_key(a)}
    assert result["unexpected"] == [case_key(extra)]


# ------------------------------------------------------------ execução real

@pytest.fixture(scope="module")
def closure(tmp_path_factory):
    return historical.checkout(CLOSURE_3_4B, tmp_path_factory.mktemp("stage3_4b_closure") / "tree")


@pytest.fixture(scope="module")
def live(closure):
    completed = historical.run(closure, "audit/stage3_4/differential/run_differential.py", "--no-write")
    return completed.returncode, json.loads(completed.stdout)


def test_live_differential_reference_vs_head_matches_exactly(live):
    code, summary = live
    assert code == 0, summary["problems"]
    # D-TAX-01: única exceção — diff provadamente taxonômico (guard); qualquer outra mudança é FAIL.
    assert summary["REFERENCE_DATA_TOOLS_INVARIANT"] in ("PASS", "PASS_AUTHORIZED_TAXONOMY_MIGRATION_D-TAX-01")
    assert summary["reference_commit"].startswith("7877551")
    assert summary["candidate_commit"].startswith(CLOSURE_3_4B)                  # H: intervalo fixo
    assert summary["differences"] == 0 and summary["problems"] == []
    eq, agg = summary["coverage"]["EQUATION"], summary["coverage"]["AGGREGATION"]
    assert (eq["instances"], eq["expected_cases"], eq["actual_cases"], eq["matched"]) == (392, 2352, 2352, 2352)
    assert (agg["instances"], agg["expected_cases"], agg["actual_cases"], agg["matched"]) == (395, 2370, 2370, 2370)
    assert eq["vectors"] >= 3 and eq["dates"] >= 2
    assert summary["aggregation_types"] == {"AVERAGE": 342, "SUM": 42, "WEIGHTED_AVERAGE": 9, "MOVING_AVERAGE": 2}


# ------------------------------------------------------------ evidência versionada

UNIVERSE_SNIPPET = """
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "tests"))
from test_stage3_4b_differential import current_universe
print(json.dumps(sorted(map(list, current_universe()))))
"""


def universe_at(root):
    """Universo calculado no clone pela `current_universe` do próprio commit de fechamento."""
    done = subprocess.run([sys.executable, "-c", UNIVERSE_SNIPPET], cwd=root, capture_output=True, text=True,
                          env=historical.clean_env(), check=True)
    return {tuple(x) for x in json.loads(done.stdout)}


def current_universe():
    loader = SeedLoader(REPO / "data" / "seed")
    variables = loader.load_variable_definitions()
    equation_block, aggregation_block = {}, {}
    for block in BLOCKS:
        for row in json.loads((REPO / "data/seed" / block / "equations.json").read_text(encoding="utf-8")):
            equation_block[row["equation_id"]] = block
        for row in json.loads((REPO / "data/seed" / block / "aggregation_rules.json").read_text(encoding="utf-8")):
            aggregation_block[row["aggregation_rule_id"]] = block
    engine = ForecastEngine()
    instances = set()
    for definition in loader.load_equation_definitions().all():
        block = equation_block.get(definition.equation_definition_id)
        if block:
            instances |= {(block, "EQUATION", i.equation_instance_id) for i in engine.materialize_equation(definition)}
    for instance in loader.load_aggregation_rule_instances(variable_definition_registry=variables).all():
        block = aggregation_block.get(instance.rule.aggregation_rule_id)
        if block:
            instances.add((block, "AGGREGATION", instance.aggregation_rule_instance_id))
    return instances


def test_committed_evidence_reproduces_the_full_matrix(closure):
    rows = list(csv.DictReader((HARNESS / "evidence" / "differential_cases.csv").open(encoding="utf-8")))
    keys = [(r["block"], r["operation_type"], r["instance_id"], r["input_vector"], r["run_date"]) for r in rows]
    assert len(keys) == len(set(keys)) == 4722                                  # sem duplicados
    universe = universe_at(closure)                                             # H: seeds de 4d54804
    assert Counter(op for _b, op, _i in universe) == Counter({"EQUATION": 392, "AGGREGATION": 395})
    expected = {(b, op, i, v, d) for (b, op, i) in universe for v in VECTORS for d in DATES}
    assert set(keys) == expected                                               # nem faltante nem excedente
    assert {r["comparison"] for r in rows} == {"MATCH"}
    for r in rows:                                                              # MATCH exige representações idênticas
        assert r["reference"] != "null" and r["candidate"] != "null"
        ref, cand = json.loads(r["reference"]), json.loads(r["candidate"])
        assert ref[0] == cand[0]


def test_committed_summary_is_the_differential_oracle():
    summary = json.loads((HARNESS / "evidence" / "differential_summary.json").read_text(encoding="utf-8"))
    assert summary["oracle_type"] == "DIFFERENTIAL_REGRESSION_ORACLE"
    assert summary["result"] == "PASS" and summary["differences"] == 0
    assert summary["isolation"]["reference_app_sha256"] != summary["isolation"]["candidate_app_sha256"]
    assert summary["isolation"]["reference_foreign_modules"] == summary["isolation"]["candidate_foreign_modules"] == []
