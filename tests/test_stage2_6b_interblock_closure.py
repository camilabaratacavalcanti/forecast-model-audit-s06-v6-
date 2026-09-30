"""
Etapa 2.6B — fechamento do contrato interbloco.

    D26-01  taxonomia oficial de blocos (conhecido / carregado / produtor)
    D26-02  energy.lth_meta <- production.lth_meta (variable x variable)
    D26-03  fator_mpsa / fator_mrn calculadas sem fonte
            fator_mpsa_kg_t / fator_mrn_kg_t -> forecast
    livro de IDs: nenhuma renumeração histórica

Os testes 01..18 seguem a lista da etapa.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from tests.test_stage2_6_interblock_contract import entity, model, only_link, producer
from tools.workbook_seed.blocks import (
    BLOCKS,
    ID_LEDGER_ROOT,
    REPO_ROOT,
    build_all,
    build_block,
    read_interblock_seed,
    read_seed_file,
)
from tools.workbook_seed.canonical import build_canonical_model
from tools.workbook_seed.id_ledger import IdLedger, identity_key, ledger_payload, load_ledger
from tools.workbook_seed.interblock import (
    AMBIGUOUS,
    CONTRACT_MISMATCH,
    CYCLE,
    INSTANCE_MISMATCH,
    PENDING,
    SOURCE_BLOCK_NOT_LOADED,
    SOURCE_BLOCK_NOT_LOADED_CODE,
    SOURCE_BLOCK_UNKNOWN,
    SOURCE_BLOCK_UNKNOWN_CODE,
    SOURCE_NOT_FOUND,
    VALID,
    link_record,
    validate_interblock,
)
from tools.workbook_seed.reader import read_workbook
from tools.workbook_seed.taxonomy import (
    BLOCK_TAXONOMY,
    OFFICIAL_BLOCKS,
)


# LEGACY_TEST_EXPECTATION (Etapa 2.6C, D26B-02): a lista recebida na
# D-TAX-01 (posterior à Stage 3) substitui a lista D26-01 de 28 nomes: o
# registro canônico tem 29 blocos, na ordem das faixas de ID. Lista histórica
# D26-01 (2.6B tinha `mx_ht`; o proprietário fixou `max_ht`), mantida só como
# registro: maintenance, area_04_13, forecast_volume, acido, yield, energy,
# meta_volume_cheio, custo_budget, production, boilers,
# controle_espaco_vazio_meta, custo_forecast_bdgt, max_ht, volume, lime_dia,
# custo_forecast_real, alumina, soda, floculante_hidrato_2026, budget,
# temperature_lp, fator_residuo, floculante_lama_dia, forecast, area_41,
# vazao_condensado, premissas_ppt_mensal, shared.
D_TAX_01_TAXONOMY = (
    "maintenance", "yield", "production", "max_ht", "alumina", "temperature_lp",
    "area_41", "area_04_13", "energy", "boilers", "volume", "soda",
    "residue_factor", "condensate_flow", "forecast_volume", "full_volume_target",
    "empty_space_target_control", "lime", "hydrated_flocculant",
    "sludge_flocculant", "thickener_flocculant", "acid", "budget_cost",
    "budget_forecast_cost", "actual_forecast_cost", "budget", "forecast",
    "budget_vs_forecast", "shared",
)


@pytest.fixture(scope="module")
def official():
    return build_all()


def _link(official, block, name, frequency=None):
    return next(
        l for l in official.interblock.links
        if (l.consumer_block, l.consumer.name) == (block, name)
        and (frequency is None or l.consumer.frequency == frequency)
    )


def _entity(official, block, name, frequency="diário"):
    return next(
        e for e in official.blocks[block].model.entities
        if e.name == name and e.frequency == frequency
    )


# ------------------------------------------------------------
# D26-01 — taxonomia (lista atual: D-TAX-01, 29 blocos)
# ------------------------------------------------------------

def test_taxonomy_is_the_owner_list_exactly():
    assert BLOCK_TAXONOMY == D_TAX_01_TAXONOMY
    assert len(OFFICIAL_BLOCKS) == 29


def test_01_block_in_taxonomy_and_loaded_resolves():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer()),
    })
    assert only_link(result).validation_status == VALID


@pytest.mark.parametrize("block", ["forecast", "maintenance", "temperature_lp", "area_04_13", "alumina"])
def test_02_block_in_taxonomy_but_not_loaded_is_pending(block):
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "x", fonte=block)),
    })
    link = only_link(result)
    assert link.validation_status == SOURCE_BLOCK_NOT_LOADED
    assert link.is_pending and not link.is_valid and not link.is_rejected
    assert link.producer is None
    assert [f.severity for f in link.findings] == [PENDING]
    assert result.rejected == [] and result.valid == []


# LEGACY_TEST_EXPECTATION (Etapa 2.6C, D26B-02): o caso "max_ht" (fora
# da taxonomia na 2.6B) foi trocado por "mx_ht", que deixou de ser oficial.
@pytest.mark.parametrize("fonte", ["forcast", "bloco forecast", "Forecast", "forecast ", "mx_ht", "hydrate"])
def test_03_block_outside_taxonomy_is_an_error(fonte):
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "x", fonte=fonte)),
        # Mesmo carregado com esse identificador, o nome não é oficial.
        "max_ht": model("max_ht", producer("VAR13001", "x")),
    })
    link = only_link(result)
    assert link.validation_status == SOURCE_BLOCK_UNKNOWN
    assert link.findings[0].code == SOURCE_BLOCK_UNKNOWN_CODE
    assert link.is_rejected and link.producer is None


def test_04_missing_producer_in_loaded_workbook():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "inexistente", fonte="production")),
        "production": model("production", producer()),
    })
    link = only_link(result)
    assert link.validation_status == SOURCE_NOT_FOUND
    assert link.is_rejected


def test_official_fonte_names_classified_by_taxonomy(official):
    names = {l.source_block for l in official.interblock.links}
    assert names == {"yield", "production", "maintenance", "temperature_lp", "area_04_13", "alumina", "forecast"}
    assert names <= OFFICIAL_BLOCKS
    loaded = {n for n in names if n in BLOCKS}
    assert loaded == {"yield", "production"}
    for name in ("forecast", "maintenance", "temperature_lp", "area_04_13", "alumina"):
        links = [l for l in official.interblock.links if l.source_block == name]
        assert links and all(l.validation_status == SOURCE_BLOCK_NOT_LOADED for l in links), name


# ------------------------------------------------------------
# D26-02 — energy.lth_meta <- production.lth_meta
# ------------------------------------------------------------

def test_05_d26_02_lth_meta_is_variable_to_variable(official):
    link = _link(official, "energy", "lth_meta")
    assert link.validation_status == VALID
    assert (link.consumer.kind, link.producer.kind) == ("variable", "variable")
    assert (link.consumer.variable_type, link.producer.variable_type) == ("entrada", "entrada_externa")
    for dimension in ("name", "unit", "value_type", "allowed_values", "declared_result_states",
                      "frequency", "scope_type", "scope_value"):
        assert getattr(link.consumer, dimension) == getattr(link.producer, dimension), dimension
    assert link.producer.frequency == "anual"
    assert (link.producer.scope_type, link.producer.scope_value) == ("linha", "L1_L7")
    assert [i["scope_value"] for i in link_record(link)["instances"]] == [f"L{i}" for i in range(1, 8)]
    assert not [
        e for e in official.blocks["production"].model.entities
        if e.name == "lth_meta" and e.kind == "parameter"
    ]


def test_06_entrada_to_entrada_externa_is_not_a_kind_mismatch():
    for consumer_type, producer_type in (("entrada", "entrada_externa"), ("entrada_externa", "entrada"),
                                         ("entrada", "calculado")):
        result = validate_interblock({
            "energy": model("energy", entity("VAR18001", "lth_meta", frequency="anual", unit="-",
                                             variable_type=consumer_type, fonte="production")),
            "production": model("production", entity("VAR12066", "lth_meta", frequency="anual", unit="-",
                                                     variable_type=producer_type)),
        })
        assert only_link(result).validation_status == VALID, (consumer_type, producer_type)

    # kind continua sendo dimensão do contrato.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth_meta", frequency="anual", unit="-",
                                         fonte="production")),
        "production": model("production", entity("PARAM12003", "lth_meta", kind="parameter",
                                                 frequency="anual", unit="-")),
    })
    assert [f.dimension for f in only_link(result).findings] == ["kind"]


# ------------------------------------------------------------
# D26-03 — fator_mpsa / fator_mrn
# ------------------------------------------------------------

@pytest.mark.parametrize("name, source", [("fator_mpsa", "fator_mpsa_kg_t / 1000"),
                                          ("fator_mrn", "fator_mrn_kg_t / 1000")])
def test_07_08_calculated_factor_has_no_fonte(official, name, source):
    factor = _entity(official, "production", name)
    assert factor.fonte is None
    assert (factor.unit, factor.variable_type, factor.scope_type, factor.scope_value) == (
        "-", "calculado", "linha", "L1_L7",
    )
    assert [r.expression for r in factor.rows] == [source]
    assert not [l for l in official.interblock.links if l.consumer is factor]
    assert not [
        l for l in official.interblock.links
        if any(f.dimension == "consumer_context" for f in l.findings)
    ]


@pytest.mark.parametrize("name", ["fator_mpsa_kg_t", "fator_mrn_kg_t"])
def test_09_10_kg_t_inputs_link_to_forecast(official, name):
    link = _link(official, "production", name)
    assert link.source_block == "forecast"
    assert (link.consumer.unit, link.consumer.variable_type) == ("kg/t", "entrada")
    assert (link.consumer.scope_type, link.consumer.scope_value) == ("linha_grupo", "L1_L7")
    assert link.validation_status == SOURCE_BLOCK_NOT_LOADED
    assert link.findings[0].code == SOURCE_BLOCK_NOT_LOADED_CODE


# ------------------------------------------------------------
# Regras gerais
# ------------------------------------------------------------

def test_11_source_reference_does_not_interfere():
    for reference in (None, "forecast", "bloco forecast", "production"):
        result = validate_interblock({
            "energy": model("energy", entity("VAR18001", "lth", fonte="yield", source_reference=reference)),
            "production": model("production", producer("VAR12031")),
            "yield": model("yield", producer("VAR11031")),
        })
        assert only_link(result).producer.entity_id == "VAR11031"


def test_12_no_interblock_fallback():
    for producer_kw in ({"frequency": "mensal"}, {"frequency": "anual"},
                        {"scope_type": "linha_grupo"}, {"scope_type": "planta", "scope_value": "PLANTA"}):
        result = validate_interblock({
            "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
            "production": model("production", producer(**producer_kw)),
        })
        link = only_link(result)
        assert link.validation_status == SOURCE_NOT_FOUND and link.producer is None, producer_kw


def test_13_instance_mismatch():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer(scope_value="L1_L3")),
    })
    assert only_link(result).validation_status == INSTANCE_MISMATCH


def test_14_ambiguity():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer("VAR12031", scope_value="L1_L3"),
                            producer("VAR12032", scope_value="L4_L7")),
    })
    assert only_link(result).validation_status == AMBIGUOUS


def test_15_cycle():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "x", fonte="production")),
        "production": model("production", entity("VAR12001", "x", fonte="energy")),
    })
    assert {l.validation_status for l in result.links} == {CYCLE}
    assert len(result.cycles) == 1


def test_16_local_identity_preserved(official):
    production_lth = _entity(official, "production", "lth")
    yield_lth = _entity(official, "yield", "lth")
    assert production_lth.entity_id != yield_lth.entity_id
    assert production_lth in official.blocks["production"].model.entities
    assert yield_lth in official.blocks["yield"].model.entities
    link = _link(official, "yield", "lth")
    assert link.consumer is yield_lth and link.producer is production_lth
    ids = [v["variable_id"] for b in BLOCKS for v in read_seed_file(b, "variables")]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------
# 17 — max_ht (D26B-02 resolvida na Etapa 2.6C)
# ------------------------------------------------------------

def test_17_max_ht_is_the_canonical_block_name(official):
    """
    LEGACY_TEST_EXPECTATION (Etapa 2.6C). Na 2.6B este teste fixava a
    divergência pendente mx_ht (taxonomia) x max_ht (código). Decisão do
    proprietário: o nome canônico é `max_ht` em taxonomia, código, seeds
    e fonte; `mx_ht` não é oficial nem sinônimo.
    """

    spec = BLOCKS["max_ht"]
    assert "max_ht" in BLOCKS and "max_ht" in OFFICIAL_BLOCKS
    assert "mx_ht" not in OFFICIAL_BLOCKS and "mx_ht" not in BLOCKS
    assert (spec.sheet, spec.file_name) == ("MaxHT", "descritivo_das_variáveis_MaxHT_v10.xlsx")
    assert not {"mx_ht", "max_ht"} & {l.source_block for l in official.interblock.links}

    seed = read_interblock_seed()
    assert "max_ht" in seed["taxonomy"]["official_blocks"]
    assert "mx_ht" not in seed["taxonomy"]["official_blocks"]
    assert all(b["in_taxonomy"] for b in seed["taxonomy"]["loaded_blocks"])


def test_17b_fonte_max_ht_resolves_and_mx_ht_is_unknown(official):
    models = {b: r.model for b, r in official.blocks.items()}
    lth = _entity(official, "max_ht", "lth")

    result = validate_interblock({
        **models,
        "energy": model("energy", entity("VAR18999", "lth", fonte="max_ht")),
    })
    link = next(l for l in result.links if l.consumer.entity_id == "VAR18999")
    assert link.validation_status == VALID
    assert link.producer is lth

    result = validate_interblock({
        **models,
        "energy": model("energy", entity("VAR18999", "lth", fonte="mx_ht")),
    })
    link = next(l for l in result.links if l.consumer.entity_id == "VAR18999")
    assert link.validation_status == SOURCE_BLOCK_UNKNOWN
    assert link.findings[0].code == SOURCE_BLOCK_UNKNOWN_CODE
    assert link.is_rejected and link.producer is None


# ------------------------------------------------------------
# 18 — todos os vínculos reais
# ------------------------------------------------------------

EXPECTED = {
    ("area_41", "lth", "diário"): VALID,
    ("area_41", "hes", "diário"): SOURCE_BLOCK_NOT_LOADED,
    ("energy", "producao", "diário"): VALID,
    ("energy", "pick_up", "diário"): VALID,
    ("energy", "pick_up_total", "diário"): VALID,
    ("energy", "pick_up_total", "mensal"): VALID,
    ("energy", "lth", "diário"): VALID,
    ("energy", "lth_total", "diário"): VALID,
    ("energy", "lth_total", "mensal"): VALID,
    ("energy", "lth_meta", "anual"): VALID,
    ("energy", "temperatura_lp", "diário"): SOURCE_BLOCK_NOT_LOADED,
    ("energy", "temperatura_lp", "mensal"): SOURCE_BLOCK_NOT_LOADED,
    ("energy", "temperatura_lp_media", "mensal"): SOURCE_BLOCK_NOT_LOADED,
    ("energy", "evaporado_total_evaporacao", "diário"): SOURCE_BLOCK_NOT_LOADED,
    ("max_ht", "alimentação_evap", "diário"): SOURCE_BLOCK_NOT_LOADED,
    ("max_ht", "lth", "diário"): VALID,
    ("max_ht", "producao", "diário"): VALID,
    ("production", "fator_mpsa_kg_t", "diário"): SOURCE_BLOCK_NOT_LOADED,
    ("production", "fator_mrn_kg_t", "diário"): SOURCE_BLOCK_NOT_LOADED,
    **{
        ("production", name, "diário"): SOURCE_BLOCK_NOT_LOADED
        for name in (
            "reducao_lth_calcinacao", "reducao_lth_clarificacao", "reducao_lth_digestao",
            "reducao_lth_precipitacao", "tempo_calcinacao", "tempo_clarificacao",
            "tempo_digestao", "tempo_precipitacao",
        )
    },
    ("production", "yield", "diário"): VALID,
    ("yield", "lth", "diário"): VALID,
}


def test_18_all_real_links_of_the_five_workbooks(official):
    fonte_rows = []
    for block, spec in BLOCKS.items():
        workbook = read_workbook(spec.workbook_path, spec.sheet)
        fonte_rows += [(block, r.row) for r in workbook.rows if r.get("fonte") is not None]
    classified = [(l.consumer_block, row) for l in official.interblock.links for row in l.consumer_rows]
    assert sorted(classified) == sorted(fonte_rows)
    assert len(fonte_rows) == 32

    actual = {
        (l.consumer_block, l.consumer.name, l.consumer.frequency): l.validation_status
        for l in official.interblock.links
    }
    assert actual == EXPECTED
    assert official.interblock.rejected == []
    assert official.interblock.cycles == []
    for link in official.interblock.valid:
        assert link.chain_status == VALID, link.chain


# ------------------------------------------------------------
# Livro de IDs — nenhuma renumeração histórica
# ------------------------------------------------------------

def _head_manifest(block):
    raw = subprocess.check_output(
        ["git", "show", f"a126e02:data/seed/{block}/manifest.json"], cwd=REPO_ROOT,
    )
    return json.loads(raw)


def test_no_historical_id_was_renumbered():
    for block in BLOCKS:
        before = {
            identity_key(e["kind"], e["name"], e["frequency"], e["scope_type"], e["scope_value"]): e["entity_id"]
            for e in _head_manifest(block)["entities"]
        }
        after = {
            identity_key(e["kind"], e["name"], e["frequency"], e["scope_type"], e["scope_value"]): e["entity_id"]
            for e in read_seed_file(block, "manifest")["entities"]
        }
        for key in before.keys() & after.keys():
            assert before[key] == after[key], (block, key)
        removed = before.keys() - after.keys()
        added = after.keys() - before.keys()
        if block == "production":
            assert removed == {("parameter", "lth_meta", "anual", "linha", "L1_L7")}
            assert added == {("variable", "lth_meta", "anual", "linha", "L1_L7")}
            assert after[next(iter(added))] == "VAR12066"
        else:
            assert removed == added == set(), block


def test_ledger_retires_ids_and_never_reuses_them():
    ledger = load_ledger(ID_LEDGER_ROOT / "production.json")
    assert [r["entity_id"] for r in ledger.retired] == ["PARAM12003"]
    assert ledger.highest("parameter") >= 12003
    assert "PARAM12003" not in ledger.entries.values()

    for block in BLOCKS:
        built = build_block(block)
        assert ledger_payload(built.model, built.id_ledger) == json.loads(
            (ID_LEDGER_ROOT / f"{block}.json").read_text(encoding="utf-8")
        ), block


def test_ledger_assigns_new_identities_after_the_highest_issued_id():
    spec = BLOCKS["production"]
    workbook = read_workbook(spec.workbook_path, spec.sheet)
    ledger = load_ledger(ID_LEDGER_ROOT / "production.json")
    # Retirar lth_meta do livro: a identidade vira "nova".
    key = identity_key("variable", "lth_meta", "anual", "linha", "L1_L7")
    shrunk = IdLedger(
        block="production",
        entries={k: v for k, v in ledger.entries.items() if k != key},
        retired=ledger.retired + ({"entity_id": "VAR12066", "kind": "variable", "name": "x",
                                   "frequency": "diário", "scope_type": "linha",
                                   "scope_value": "L1", "retired_in": "teste"},),
    )
    m = build_canonical_model("production", workbook, spec.id_base, shrunk)
    lth_meta = next(e for e in m.entities if e.name == "lth_meta")
    assert lth_meta.entity_id == "VAR12067"
    # Sem livro, a numeração sequencial deslocaria as definições seguintes.
    sequential = build_canonical_model("production", workbook, spec.id_base)
    ids = {e.name + e.frequency + e.scope_type: e.entity_id for e in sequential.entities}
    assert ids["lth_totaldiáriolinha_grupo"] != "VAR12033"


def test_seed_does_not_invent_producers_for_unloaded_blocks():
    seed = read_interblock_seed()
    produced = {(l["source_block"], l["source_definition"]) for l in seed["links"]}
    assert {b for b, _ in produced} <= set(BLOCKS)
    for record in seed["pending"]:
        assert record["source_block"] not in BLOCKS
        assert record["source_definition"] is None
        assert record["validation_status"] == SOURCE_BLOCK_NOT_LOADED
        assert all(e["severity"] == PENDING for e in record["errors"])
