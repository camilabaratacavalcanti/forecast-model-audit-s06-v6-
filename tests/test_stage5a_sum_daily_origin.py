"""
Stage 5A — D-5A-2: fim da conversão automática ×24.

Uma SUM só é aceita se a origem já estiver por dia (fator exigido = 1). A conversão de taxa para
quantidade diária é sempre explícita no workbook, por variável intermediária `*_ag`.
Provam:
    * o builder rejeita, com erro explícito que cita a variável `_ag`, a SUM de origem /h — com dados
      reais: o MaxHT v10 (histórico, preservado em data/workbooks) soma `lth_total` (m³/h);
    * o MaxHT v13 (vigente) passa: `lth_total_somatorio` soma `lth_total_ag` (m³/d);
    * o runtime recusa `integration_factor` ≠ 1 em qualquer agregação e aceita 1;
    * a checagem dimensional continua (SUM incoerente rejeitada; fator exigido ainda calculado);
    * nenhuma regra dos seeds vigentes declara fator ≠ 1.
"""

from __future__ import annotations

import json

import pytest

from app.domain.forecast.aggregation import AggregationRule, InvalidAggregationRuleError
from app.domain.units import check_sum_dimensions, required_sum_factor
from tools.workbook_seed.blocks import BLOCKS, REPO_ROOT, SEED_ROOT, build_block
from tools.workbook_seed.canonical import CanonicalModelError, build_canonical_model
from tools.workbook_seed.reader import read_workbook
from tools.workbook_seed.seeds import build_aggregation_rules

MAXHT_V10 = REPO_ROOT / "data" / "workbooks" / "descritivo_das_variáveis_MaxHT_v10.xlsx"


def rule(kind="SUM", factor=1.0, **extra):
    return AggregationRule("AGR-5A", "VAR92001", "diário", "VAR92002", "mensal", kind,
                           integration_factor=factor, **extra)


def test_builder_rejects_sum_of_an_hourly_origin_and_names_the_ag_variable():
    spec = BLOCKS["max_ht"]
    model = build_canonical_model("max_ht", read_workbook(MAXHT_V10, spec.sheet), spec.id_base)
    with pytest.raises(CanonicalModelError) as error:
        build_aggregation_rules(model)
    message = str(error.value)
    assert "lth_total_somatorio" in message and "'lth_total_ag'" in message
    assert "m³/h" in message and "fator 24" in message and "D-5A-2" in message


def test_current_max_ht_sums_the_explicit_daily_quantity():
    built = build_block("max_ht")
    sums = {r["aggregation_rule_id"]: r for r in built.seeds["aggregation_rules"]
            if r["target_variable_id"] in {e.entity_id for e in built.model.entities if e.name == "lth_total_somatorio"}}
    assert len(sums) == 2
    source = {e.entity_id: e for e in built.model.entities}
    for r in sums.values():
        assert r["aggregation_type"] == "SUM" and r["integration_factor"] == 1
        assert source[r["source_variable_id"]].name == "lth_total_ag"
        assert source[r["source_variable_id"]].unit == "m³/d"


@pytest.mark.parametrize("kind", ["SUM", "AVERAGE", "MOVING_AVERAGE"])
@pytest.mark.parametrize("factor", [24.0, 24, 2.0, 1.5])
def test_runtime_refuses_integration_factor_other_than_one(kind, factor):
    with pytest.raises(InvalidAggregationRuleError) as error:
        rule(kind=kind, factor=factor)
    assert "D-5A-2" in str(error.value) and "_ag" in str(error.value)


def test_runtime_accepts_the_daily_sum():
    assert rule().integration_factor == 1.0
    assert rule(factor=1).integration_factor == 1


def test_dimensional_check_is_kept():
    assert required_sum_factor("m³/h", "m³/mês", "mensal") == 24       # o fator exigido continua calculado
    assert required_sum_factor("m³/d", "m³/mês", "mensal") == 1
    assert check_sum_dimensions("t/d", "kg/mês", "mensal", 1.0) is not None   # numerador incoerente
    assert check_sum_dimensions("t/d", "t/mês", "mensal", 1.0) is None


def test_no_current_seed_rule_declares_a_factor_other_than_one():
    factors = {}
    for block in BLOCKS:
        for r in json.loads((SEED_ROOT / block / "aggregation_rules.json").read_text(encoding="utf-8")):
            factors.setdefault(r.get("integration_factor", 1), []).append(r["aggregation_rule_id"])
    assert set(factors) <= {1, 1.0}, {k: v[:3] for k, v in factors.items() if k != 1}
