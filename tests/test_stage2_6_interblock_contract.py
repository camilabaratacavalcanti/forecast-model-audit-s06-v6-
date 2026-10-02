"""
Etapa 2.6 — contrato interbloco declarado na coluna `fonte`.

    workbook.fonte -> source_block canônico -> validação interbloco
        -> data/seed/interblock_links.json

Os testes 01..17 seguem a lista da etapa. Os modelos sintéticos são
montados diretamente no modelo canônico; os testes 15..17 e os de
build usam os cinco workbooks oficiais.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest

from tools.workbook_seed.blocks import (
    BLOCKS,
    SEED_ROOT,
    build_all,
    read_interblock_seed,
    read_seed_file,
    seed_json,
)
from tools.workbook_seed.canonical import CanonicalEntity, CanonicalModel, CanonicalRow
from tools.workbook_seed.interblock import (
    AMBIGUOUS,
    AMBIGUOUS_CODE,
    CONTRACT_MISMATCH,
    CONTRACT_MISMATCH_CODE,
    CYCLE,
    CYCLE_CODE,
    INSTANCE_MISMATCH,
    LINK_CLASSES,
    SOURCE_BLOCK_NOT_LOADED,
    SOURCE_BLOCK_NOT_LOADED_CODE,
    SOURCE_BLOCK_UNKNOWN,
    SOURCE_BLOCK_UNKNOWN_CODE,
    SOURCE_NOT_FOUND,
    SOURCE_NOT_FOUND_CODE,
    VALID,
    InterblockContractError,
    link_record,
    require_resolved,
    require_valid,
    validate_interblock,
)
from tools.workbook_seed.reader import WorkbookData, read_workbook


# ------------------------------------------------------------
# Modelos sintéticos
# ------------------------------------------------------------

def entity(
    entity_id,
    name,
    *,
    kind="variable",
    frequency="diário",
    scope_type="linha",
    scope_value="L1_L7",
    unit="m³/h",
    value_type="numerico",
    variable_type="entrada",
    allowed_values=None,
    declared_result_states=None,
    fonte=None,
    row=2,
    expression=None,
    source_reference=None,
):
    return CanonicalEntity(
        kind=kind,
        entity_id=entity_id,
        name=name,
        frequency=frequency,
        scope_type=scope_type,
        scope_value=scope_value,
        grouped=False,
        unit=unit,
        variable_type=variable_type if kind == "variable" else None,
        value_type=value_type,
        allowed_values=allowed_values,
        declared_result_states=declared_result_states,
        status="ativo",
        fonte=fonte,
        rows=(
            CanonicalRow(
                row=row,
                scope_value=scope_value,
                description=None,
                source_reference=source_reference,
                expression=expression,
                value=None,
                version=None,
                aggregation=None,
            ),
        ),
    )


def model(block, *entities):
    workbook = WorkbookData(
        path=Path(f"{block}.xlsx"),
        file_name=f"{block}.xlsx",
        sha256="0" * 64,
        sheet=block,
        header_row=1,
        columns=(),
        rows=(),
    )
    return CanonicalModel(block=block, workbook=workbook, entities=list(entities))


def producer(entity_id="VAR12031", name="lth", **kw):
    kw.setdefault("variable_type", "calculado")
    kw.setdefault("expression", "a + b")
    return entity(entity_id, name, **kw)


def only_link(result):
    assert len(result.links) == 1
    return result.links[0]


# ------------------------------------------------------------
# 01..14 — contrato em modelos sintéticos
# ------------------------------------------------------------

def test_01_empty_fonte_creates_no_link():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth")),
        "production": model("production", producer()),
    })

    assert result.links == []
    assert result.cycles == []


def test_02_valid_fonte_creates_a_validated_link():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production", row=10)),
        "production": model("production", producer()),
    })

    link = only_link(result)
    assert link.validation_status == VALID
    assert link.producer.entity_id == "VAR12031"
    require_valid(result)

    record = link_record(link)
    assert record == {
        "consumer_block": "energy",
        "consumer_definition": "VAR18001",
        "consumer_frequency": "diário",
        "consumer_scope": {"scope_type": "linha", "scope_value": "L1_L7"},
        "source_block": "production",
        "source_definition": "VAR12031",
        "source_frequency": "diário",
        "source_scope": {"scope_type": "linha", "scope_value": "L1_L7"},
        "instances": [
            {"scope_type": "linha", "scope_value": f"L{i}"} for i in range(1, 8)
        ],
        "consumer_rows": [10],
    }


@pytest.mark.parametrize(
    "fonte, expected_class, expected_code, expected_producer_value",
    [
        ("maintenance", SOURCE_BLOCK_NOT_LOADED, SOURCE_BLOCK_NOT_LOADED_CODE,
         "bloco da taxonomia oficial sem workbook carregado"),
        ("bloco production", SOURCE_BLOCK_UNKNOWN, SOURCE_BLOCK_UNKNOWN_CODE,
         "nome fora da taxonomia oficial de blocos (D26-01)"),
        ("production ", SOURCE_BLOCK_UNKNOWN, SOURCE_BLOCK_UNKNOWN_CODE,
         "nome fora da taxonomia oficial de blocos (D26-01)"),
        ("Production", SOURCE_BLOCK_UNKNOWN, SOURCE_BLOCK_UNKNOWN_CODE,
         "nome fora da taxonomia oficial de blocos (D26-01)"),
    ],
)
def test_03_nonexistent_source_block_is_an_error(
    fonte, expected_class, expected_code, expected_producer_value,
):
    """
    LEGACY_TEST_EXPECTATION (Etapa 2.6B, D26-01): na 2.6 os quatro casos
    eram INTERBLOCK_SOURCE_NOT_FOUND. Agora nome fora da taxonomia é
    SOURCE_BLOCK_UNKNOWN (erro) e bloco oficial sem workbook carregado é
    SOURCE_BLOCK_NOT_LOADED (pendência, não erro nem vínculo válido).
    """

    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte=fonte, row=10)),
        "production": model("production", producer()),
    })

    link = only_link(result)
    assert link.validation_status == expected_class
    [finding] = link.findings
    assert finding.code == expected_code
    assert finding.dimension == "source_block"
    assert finding.producer_value == expected_producer_value
    # Mensagem com bloco, linha, nome, bloco fonte e dimensão.
    for part in ("energy", "linha 10", "'lth'", repr(fonte), "source_block"):
        assert part in finding.message

    assert not link.is_valid
    if expected_class == SOURCE_BLOCK_UNKNOWN:
        with pytest.raises(InterblockContractError, match=expected_code):
            require_valid(result)
    else:
        assert link.is_pending and result.rejected == []
        require_valid(result)
        with pytest.raises(InterblockContractError, match=expected_code):
            require_resolved(result)


def test_03b_missing_definition_in_source_block_is_an_error():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer(name="lth_total")),
    })

    [finding] = only_link(result).findings
    assert (finding.code, finding.link_class, finding.dimension) == (
        SOURCE_NOT_FOUND_CODE, SOURCE_NOT_FOUND, "name"
    )


def test_03c_no_temporal_or_spatial_fallback():
    # Consumidor diário; produtor só mensal: nada de fallback temporal.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer(frequency="mensal")),
    })
    [finding] = only_link(result).findings
    assert (finding.link_class, finding.dimension) == (SOURCE_NOT_FOUND, "frequency")
    assert finding.producer_value == ["mensal linha/L1_L7"]

    # Consumidor linha; produtor só linha_grupo: nada de fallback espacial.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production", producer(scope_type="linha_grupo")),
    })
    [finding] = only_link(result).findings
    assert (finding.link_class, finding.dimension) == (SOURCE_NOT_FOUND, "scope")


def test_04_ambiguous_source_is_an_error():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model(
            "production", producer("VAR12031"), producer("VAR12099"),
        ),
    })

    link = only_link(result)
    assert link.validation_status == AMBIGUOUS
    [finding] = link.findings
    assert finding.code == AMBIGUOUS_CODE
    assert finding.producer_value == ["VAR12031", "VAR12099"]
    assert link.producer is None


def test_05_unit_mismatch_is_an_error_without_conversion():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", unit="m³/d", fonte="production", row=10)),
        "production": model("production", producer(unit="m³/h")),
    })

    link = only_link(result)
    assert link.validation_status == CONTRACT_MISMATCH
    [finding] = link.findings
    assert finding.code == CONTRACT_MISMATCH_CODE
    assert (finding.dimension, finding.consumer_value, finding.producer_value) == (
        "unit", "m³/d", "m³/h"
    )
    for part in ("energy", "linha 10", "'lth'", "'production'", "'unit'", "'m³/d'", "'m³/h'"):
        assert part in finding.message


def test_06_value_type_mismatch_is_an_error():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "estado", unit="-", value_type="categorico",
                                         allowed_values=("A", "B"), fonte="production")),
        "production": model("production", producer(name="estado", unit="-")),
    })

    dimensions = {f.dimension for f in only_link(result).findings}
    assert dimensions == {"value_type", "allowed_values"}
    assert only_link(result).validation_status == CONTRACT_MISMATCH


def test_06b_allowed_values_and_declared_states_must_match():
    from tools.workbook_seed.canonical import DeclaredState

    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "hes", unit="-", value_type="categorico",
                                         allowed_values=("Normal", "LC"), fonte="production")),
        "production": model("production", producer(
            name="hes", unit="-", value_type="categorico",
            allowed_values=("Normal", "LC", "Overhaul"),
            declared_result_states=(DeclaredState("ERRO", "ERRO!!!"),),
        )),
    })

    assert {f.dimension for f in only_link(result).findings} == {
        "allowed_values", "declared_result_states",
    }


def test_06c_parameter_producer_for_variable_consumer_is_a_contract_mismatch():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth_meta", frequency="anual", unit="-",
                                         fonte="production", row=13)),
        "production": model("production", entity(
            "PARAM12003", "lth_meta", kind="parameter", frequency="anual", unit="-",
        )),
    })

    link = only_link(result)
    [finding] = link.findings
    assert (finding.code, finding.dimension) == (CONTRACT_MISMATCH_CODE, "kind")
    assert link.validation_status == CONTRACT_MISMATCH


def test_07_missing_instance_is_an_error_and_never_substituted():
    result = validate_interblock({
        "area_41": model("area_41", entity("VAR16001", "lth", fonte="production")),
        "production": model("production", producer(scope_value="L4_L7")),
    })

    link = only_link(result)
    assert link.validation_status == INSTANCE_MISMATCH
    [finding] = link.findings
    assert finding.code == CONTRACT_MISMATCH_CODE
    assert finding.dimension == "instances"
    assert finding.consumer_value == [f"L{i}" for i in range(1, 8)]
    assert finding.producer_value == ["L4", "L5", "L6", "L7"]
    assert "['L1', 'L2', 'L3']" in finding.message
    assert link.producer is None


def test_07b_instance_of_a_grouped_producer_resolves_by_exact_scope_value():
    # Consumidor linha/L3; produtor por linha L1_L7: a instância L3 existe.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", scope_value="L3", fonte="production")),
        "production": model("production", producer()),
    })
    link = only_link(result)
    assert link.validation_status == VALID
    assert link_record(link)["instances"] == [{"scope_type": "linha", "scope_value": "L3"}]

    # linha_grupo L1_L7 não é servida por linha_grupo L1_L3 nem por linha L1..L7.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth_total", scope_type="linha_grupo",
                                         fonte="production")),
        "production": model("production",
                            producer("VAR12033", "lth_total", scope_type="linha_grupo",
                                     scope_value="L1_L3"),
                            producer("VAR12031", "lth_total")),
    })
    assert only_link(result).validation_status == INSTANCE_MISMATCH


def test_07c_instances_split_across_producer_definitions_is_ambiguous():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="production")),
        "production": model("production",
                            producer("VAR12031", scope_value="L1_L3"),
                            producer("VAR12032", scope_value="L4_L7")),
    })
    link = only_link(result)
    assert link.validation_status == AMBIGUOUS
    assert link.findings[0].producer_value == ["VAR12031", "VAR12032"]


def test_08_source_reference_has_no_influence():
    base = {
        "production": model("production", producer()),
        "yield": model("yield", producer("VAR11031")),
    }

    for reference in (None, "bloco yield", "yield", "production.xlsx"):
        result = validate_interblock({
            **base,
            "energy": model("energy", entity("VAR18001", "lth", fonte="production",
                                             source_reference=reference)),
        })
        link = only_link(result)
        assert (link.source_block, link.producer.entity_id) == ("production", "VAR12031")

    # source_reference sem fonte: nenhum vínculo.
    result = validate_interblock({
        **base,
        "energy": model("energy", entity("VAR18001", "lth", source_reference="production")),
    })
    assert result.links == []


def test_09_local_identity_is_preserved():
    consumer = entity("VAR18001", "lth", fonte="production")
    source = producer()
    models = {
        "energy": model("energy", consumer),
        "production": model("production", source),
    }

    link = only_link(validate_interblock(models))

    assert link.consumer is consumer and link.producer is source
    assert models["energy"].entities == [consumer]
    assert models["production"].entities == [source]
    record = link_record(link)
    assert record["consumer_definition"] != record["source_definition"]


def test_10_cycle_is_an_error_with_the_full_cycle():
    # LEGACY_TEST_EXPECTATION (Etapa 2.6B, D26-01): os blocos sintéticos
    # a_block/b_block/c_block ficaram fora da taxonomia oficial; o ciclo
    # usa agora três blocos oficiais.
    def build(order):
        pieces = {
            "a": model("energy", entity("VAR1", "x", fonte="production")),
            "b": model("production", entity("VAR2", "x", fonte="yield")),
            "c": model("yield", entity("VAR3", "x", fonte="energy")),
        }
        return validate_interblock({pieces[k].block: pieces[k] for k in order})

    first = build("abc")
    second = build("cba")

    assert all(link.validation_status == CYCLE for link in first.links)
    assert all(f.code == CYCLE_CODE for _l, f in first.findings)
    message = first.links[0].findings[0].message
    assert "energy.x" in message and "production.x" in message and "yield.x" in message
    # Independe da ordem de carga.
    assert first.cycles == second.cycles
    assert [f.message for _l, f in first.findings] == [f.message for _l, f in second.findings]


def test_10b_cycle_through_intra_block_dependencies_is_detected():
    models = {
        "energy": model(
            "energy",
            entity("VAR18001", "lth", fonte="production"),
            entity("VAR18002", "derivada", variable_type="calculado", expression="lth * 2"),
        ),
        "production": model(
            "production",
            entity("VAR12001", "derivada", fonte="energy"),
            producer("VAR12031", expression="derivada + 1"),
        ),
    }
    dependencies = [
        (("energy", "VAR18002"), ("energy", "VAR18001")),
        (("production", "VAR12031"), ("production", "VAR12001")),
    ]

    result = validate_interblock(models, dependencies)

    assert {link.validation_status for link in result.links} == {CYCLE}
    [cycle] = result.cycles
    assert cycle[0] == cycle[-1] and len(cycle) == 5

    # Sem as dependências intrabloco não há ciclo de dados.
    assert validate_interblock(models).cycles == []


def test_11_chain_a_b_c():
    result = validate_interblock({
        "area_41": model("area_41", entity("VAR16001", "lth", fonte="yield")),
        "yield": model("yield", entity("VAR11031", "lth", fonte="production")),
        "production": model("production", producer()),
    })

    by_block = {link.consumer_block: link for link in result.links}
    assert {b: l.validation_status for b, l in by_block.items()} == {
        "area_41": VALID, "yield": VALID,
    }
    assert by_block["area_41"].chain == ("area_41.lth", "yield.lth", "production.lth")
    assert by_block["area_41"].chain_status == VALID


def test_11b_chain_is_broken_by_an_invalid_upstream_hop():
    result = validate_interblock({
        "area_41": model("area_41", entity("VAR16001", "lth", fonte="yield")),
        "yield": model("yield", entity("VAR11031", "lth", fonte="production")),
        "production": model("production", producer(unit="t/h")),
    })

    by_block = {link.consumer_block: link for link in result.links}
    assert by_block["area_41"].validation_status == VALID
    assert by_block["yield"].validation_status == CONTRACT_MISMATCH
    assert by_block["area_41"].chain_status == "BROKEN_AT:yield.lth"


def test_12_same_name_without_fonte_creates_no_link():
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth")),
        "max_ht": model("max_ht", entity("VAR13001", "lth")),
        "production": model("production", producer()),
    })

    assert result.links == []


def test_13_changing_fonte_changes_the_producer():
    models = {
        "production": model("production", producer("VAR12031")),
        "yield": model("yield", producer("VAR11031")),
    }

    for fonte, expected in (("production", "VAR12031"), ("yield", "VAR11031")):
        result = validate_interblock({
            **models,
            "energy": model("energy", entity("VAR18001", "lth", fonte=fonte)),
        })
        link = only_link(result)
        assert (link.source_block, link.producer.entity_id) == (fonte, expected)


def test_14_fonte_in_an_invalid_context_is_an_error():
    # Linha calculada com expressão própria e fonte: dois produtores.
    result = validate_interblock({
        "production": model("production", entity(
            "VAR12030", "fator_mpsa", unit="-", variable_type="calculado",
            expression="fator_mpsa_kg_t / 1000", fonte="forecast", row=30,
        )),
    })
    link = only_link(result)
    assert link.validation_status == CONTRACT_MISMATCH
    assert [f.dimension for f in link.findings] == ["consumer_context", "source_block"]
    assert "fator_mpsa_kg_t / 1000" in link.findings[0].message

    # Parâmetro com fonte.
    result = validate_interblock({
        "energy": model("energy", entity("PARAM18001", "lth", kind="parameter", fonte="production")),
        "production": model("production", producer()),
    })
    assert "consumer_context" in {f.dimension for f in only_link(result).findings}

    # fonte apontando o próprio bloco.
    result = validate_interblock({
        "energy": model("energy", entity("VAR18001", "lth", fonte="energy")),
    })
    assert [f.dimension for f in only_link(result).findings] == ["source_block"]


# ------------------------------------------------------------
# 15..17 — os cinco workbooks oficiais
# ------------------------------------------------------------

EXPECTED_VALID = {
    ("area_41", 9, "lth", "yield"),
    ("energy", 3, "producao", "production"),
    ("energy", 7, "pick_up", "production"),
    ("energy", 8, "pick_up_total", "production"),
    ("energy", 9, "pick_up_total", "production"),
    ("energy", 10, "lth", "production"),
    ("energy", 11, "lth_total", "production"),
    ("energy", 12, "lth_total", "production"),
    # Etapa 2.6B (D26-02): production v10 corrigiu lth_meta.
    ("energy", 13, "lth_meta", "production"),
    ("max_ht", 68, "lth", "production"),
    # C (Stage 5A): MaxHT v13 insere uma linha antes de producao (98 -> 99).
    ("max_ht", 99, "producao", "production"),
    ("production", 87, "yield", "yield"),
    ("yield", 32, "lth", "production"),
}


@pytest.fixture(scope="module")
def official():
    return build_all()


def _fonte_rows():
    rows = []

    for block, spec in BLOCKS.items():
        workbook = read_workbook(spec.workbook_path, spec.sheet)
        rows += [
            (block, r.row, r.get("name"), r.get("fonte"))
            for r in workbook.rows
            if r.get("fonte") is not None
        ]

    return rows


def test_15_every_real_fonte_is_classified(official):
    """
    LEGACY_TEST_EXPECTATION (Etapa 2.6B). Na 2.6 (production v9): 34
    linhas, 31 vínculos, 12 VALID / 16 SOURCE_NOT_FOUND / 3
    CONTRACT_MISMATCH. Com production v10 (D26-02, D26-03) e a taxonomia
    D26-01: 32 linhas, 29 vínculos, 13 VALID / 16 SOURCE_BLOCK_NOT_LOADED.
    """

    result = official.interblock
    classified = {
        (link.consumer_block, row, link.consumer.name, link.source_block)
        for link in result.links
        for row in link.consumer_rows
    }

    assert sorted(classified) == sorted(set(_fonte_rows()))
    assert len(_fonte_rows()) == 32
    assert len(result.links) == 29
    assert all(link.validation_status in LINK_CLASSES for link in result.links)

    valid = {
        (link.consumer_block, row, link.consumer.name, link.source_block)
        for link in result.valid
        for row in link.consumer_rows
    }
    assert valid == EXPECTED_VALID

    assert Counter(link.validation_status for link in result.links) == {
        VALID: 13, SOURCE_BLOCK_NOT_LOADED: 16,
    }
    unloaded = [l for l in result.links if l.source_block not in BLOCKS]
    assert len(unloaded) == 16 and all(l.is_pending for l in unloaded)
    assert result.rejected == []
    assert result.cycles == []

    lth_meta = next(l for l in result.links if l.consumer.name == "lth_meta")
    assert lth_meta.is_valid and lth_meta.producer.kind == "variable"

    area_41_lth = next(
        l for l in result.links if (l.consumer_block, l.consumer.name) == ("area_41", "lth")
    )
    assert area_41_lth.chain == ("area_41.lth", "yield.lth", "production.lth")
    assert area_41_lth.chain_status == VALID

    require_valid(result)
    with pytest.raises(InterblockContractError, match=SOURCE_BLOCK_NOT_LOADED_CODE):
        require_resolved(result)


def test_16_no_link_is_resolved_by_unit_conversion(official):
    for link in official.interblock.links:
        if link.producer is not None and link.is_valid:
            assert link.consumer.unit == link.producer.unit
            assert link.consumer.name == link.producer.name
            assert link.consumer.frequency == link.producer.frequency
            assert (link.consumer.scope_type, link.consumer.scope_value) == (
                link.producer.scope_type, link.producer.scope_value,
            )


def test_17_resolution_does_not_depend_on_historical_ids(official):
    # Renumerar todas as definições não muda quem é o produtor.
    renumbered = {}

    for block, built in official.blocks.items():
        m = built.model
        renumbered[block] = CanonicalModel(
            block=m.block,
            workbook=m.workbook,
            entities=[
                dataclasses.replace(e, entity_id=f"X{block}{i:04d}")
                for i, e in enumerate(reversed(m.entities))
            ],
        )

    def summary(result):
        return sorted(
            (
                l.consumer_block, l.consumer.name, l.consumer.frequency,
                l.consumer.scope_type, l.consumer.scope_value,
                l.producer.name if l.producer else None,
                l.producer.kind if l.producer else None,
                l.validation_status,
            )
            for l in result.links
        )

    assert summary(validate_interblock(renumbered)) == summary(official.interblock)


# ------------------------------------------------------------
# Build: seed e manifesto
# ------------------------------------------------------------

def test_interblock_seed_is_the_builder_output(official):
    assert (SEED_ROOT / "interblock_links.json").read_text(encoding="utf-8") == seed_json(
        official.interblock_seed
    )

    # LEGACY_TEST_EXPECTATION (Etapa 2.6B): 12 links / 19 rejected na
    # 2.6; agora 13 links / 16 pending / 0 rejected.
    seed = read_interblock_seed()
    assert len(seed["links"]) == 13
    assert len(seed["pending"]) == 16
    assert seed["rejected"] == []
    assert set(seed["workbooks"]) == set(BLOCKS)
    for block, spec in BLOCKS.items():
        assert seed["workbooks"][block]["sha256"] == spec.sha256
    for record in seed["pending"]:
        assert record["source_definition"] is None
        assert [e["code"] for e in record["errors"]] == [SOURCE_BLOCK_NOT_LOADED_CODE]


def test_manifest_records_canonical_source_block(official):
    for block in BLOCKS:
        manifest = read_seed_file(block, "manifest")
        declared = {
            (e["name"], e["frequency"], e["scope_type"], e["scope_value"]): e["source_block"]
            for e in manifest["entities"]
            if "source_block" in e
        }
        expected = {
            (e.name, e.frequency, e.scope_type, e.scope_value): e.fonte
            for e in official.blocks[block].model.entities
            if e.fonte is not None
        }
        assert declared == expected


def test_source_block_is_not_a_seed_or_domain_field():
    for block in BLOCKS:
        for record in read_seed_file(block, "variables") + read_seed_file(block, "parameters"):
            assert "source_block" not in record
            assert "fonte" not in record


def _redirect_main_outputs(tmp_path, monkeypatch):
    import tools.workbook_seed.blocks as blocks

    original = blocks.write_seeds
    monkeypatch.setattr(
        "tools.workbook_seed.__main__.write_seeds",
        lambda result: original(result, tmp_path / result.spec.block),
    )
    monkeypatch.setattr(
        "tools.workbook_seed.__main__.write_id_ledger",
        lambda result: blocks.write_id_ledger(result, tmp_path / "id_ledger"),
    )
    monkeypatch.setattr(
        "tools.workbook_seed.__main__.write_interblock_seed",
        lambda result: blocks.write_interblock_seed(result, tmp_path),
    )


def test_builder_main_fails_while_links_are_rejected(tmp_path, monkeypatch, capsys):
    """
    LEGACY_TEST_EXPECTATION (Etapa 2.6B): na 2.6 o build oficial tinha
    19 vínculos rejeitados. Agora não tem nenhum; a regra (rejeição ->
    código 1) é exercitada com um resultado sintético rejeitado.
    """

    import tools.workbook_seed.__main__ as main_module
    from tools.workbook_seed.blocks import BuildAllResult

    real = build_all()
    rejected = validate_interblock({
        **{block: r.model for block, r in real.blocks.items()},
        "energy": model("energy", entity("VAR18001", "lth", fonte="bloco production")),
    })
    monkeypatch.setattr(
        main_module, "build_all",
        lambda: BuildAllResult(blocks=real.blocks, interblock=rejected),
    )
    _redirect_main_outputs(tmp_path, monkeypatch)

    assert main_module.main([]) == 1
    captured = capsys.readouterr()
    assert "1 rejeitados" in captured.out
    assert SOURCE_BLOCK_UNKNOWN_CODE in captured.err


def test_builder_main_succeeds_with_only_pending_links(tmp_path, monkeypatch, capsys):
    from tools.workbook_seed.__main__ import main

    _redirect_main_outputs(tmp_path, monkeypatch)

    assert main([]) == 0
    captured = capsys.readouterr()
    assert "13 válidos, 16 pendentes de carregamento, 0 rejeitados" in captured.out
    assert "[pending] " + SOURCE_BLOCK_NOT_LOADED_CODE in captured.err
    assert (tmp_path / "interblock_links.json").exists()
    assert (tmp_path / "id_ledger" / "production.json").exists()
