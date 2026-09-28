"""
Etapa 3.1 — primeira camada de integração interbloco no runtime.

    seeds -> InterblockLinkRegistry (contrato canônico validado)
          -> InterblockValueResolver (lookup no CalculationContext)
          -> valor gravado no consumidor, identidade própria preservada

13.1..13.12: mecanismo em registros sintéticos; 14: os 13 vínculos
reais, a cadeia area_41.lth <- yield.lth <- production.lth e os 16
pendentes do artefato oficial.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import pytest

from app.domain.equations.models import EquationInstance
from app.domain.interblock.registry import InterblockLinkRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import (
    InterblockConsumerValueConflictError,
    InterblockCycleError,
    InterblockInstanceNotDeclaredError,
    InterblockLinkNotFoundError,
    InterblockLinkRejectedError,
    InterblockPeriodFrequencyMismatchError,
    InterblockSeedError,
    InterblockSourceNotLoadedError,
    InterblockSourceValueNotFoundError,
    VariableNotFoundError,
)
from app.engine.interblock_resolver import InterblockValueResolver
from app.repositories.seed_loader import SeedLoader


REPO = Path(__file__).resolve().parents[1]
SEED_ROOT = REPO / "data" / "seed"
LINES = [f"L{i}" for i in range(1, 8)]
PERIODS = {"diário": "2026-09-14", "mensal": "2026-09", "anual": "2026"}


# ------------------------------------------------------------
# Registros sintéticos
# ------------------------------------------------------------

def var(variable_id, name, frequency="diário", scope_type="linha", scope_value="L1_L7",
        unit="m³/h", value_type="numerico", source_reference=None):
    return {
        "variable_id": variable_id, "variable_name": name, "unit": unit,
        "frequency": frequency, "scope_type": scope_type, "scope_value": scope_value,
        "value_type": value_type, "source_reference": source_reference or f"{name}.xlsx",
    }


def link(consumer_block, consumer_id, source_block, source_id, frequency="diário",
         scope_type="linha", scope_value="L1_L7", instances=None):
    if instances is None:
        instances = LINES if scope_type == "linha" else [scope_value]
    return {
        "consumer_block": consumer_block, "consumer_definition": consumer_id,
        "consumer_frequency": frequency,
        "consumer_scope": {"scope_type": scope_type, "scope_value": scope_value},
        "source_block": source_block, "source_definition": source_id,
        "source_frequency": frequency,
        "source_scope": {"scope_type": scope_type, "scope_value": scope_value},
        "instances": [{"scope_type": scope_type, "scope_value": v} for v in instances],
        "consumer_rows": [1],
    }


def pending(consumer_block, consumer_id, name, source_block, frequency="diário",
            scope_type="linha", scope_value="L1_L7"):
    return {
        "consumer_block": consumer_block, "consumer_definition": consumer_id,
        "consumer_name": name, "consumer_frequency": frequency,
        "consumer_scope": {"scope_type": scope_type, "scope_value": scope_value},
        "consumer_rows": [2], "source_block": source_block, "source_definition": None,
        "resolution_status": "PENDING_LOAD", "validation_status": "SOURCE_BLOCK_NOT_LOADED",
        "errors": [{"code": "INTERBLOCK_SOURCE_BLOCK_NOT_LOADED", "severity": "pending"}],
    }


OFFICIAL = ["production", "yield", "area_41", "energy", "forecast", "maintenance", "max_ht"]


def world():
    """production.lth -> yield.lth -> area_41.lth; energy.lth -> production.lth."""
    variables = {
        "production": [var("VAR12031", "lth"), var("VAR12032", "lth", "mensal")],
        "yield": [var("VAR11031", "lth")],
        "area_41": [var("VAR16007", "lth"), var("VAR16021", "hes", unit="-", scope_value="L4_L7")],
        "energy": [var("VAR18008", "lth"), var("VAR18010", "lth_total", "mensal")],
    }
    payload = {
        "workbooks": {b: {} for b in variables},
        "taxonomy": {"official_blocks": OFFICIAL},
        "links": [
            link("yield", "VAR11031", "production", "VAR12031"),
            link("area_41", "VAR16007", "yield", "VAR11031"),
            link("energy", "VAR18008", "production", "VAR12031"),
        ],
        "pending": [pending("area_41", "VAR16021", "hes", "maintenance", scope_value="L4_L7")],
        "rejected": [],
    }
    return payload, variables


def registry(payload=None, variables=None):
    if payload is None:
        payload, variables = world()
    return InterblockLinkRegistry.from_payload(payload, variables)


def resolver(reg=None):
    context = CalculationContext()
    return InterblockValueResolver(reg or registry(), context), context


# ------------------------------------------------------------
# 13.1 .. 13.12
# ------------------------------------------------------------

def test_13_1_simple_lookup():
    r, ctx = resolver()
    ctx.set_variable_value("VAR12031", 1234.5, "linha", "L2", "2026-09-14")
    assert r.resolve("VAR18008", "linha", "L2", "2026-09-14") == 1234.5
    assert r.transfer("VAR18008", "linha", "L2", "2026-09-14") == 1234.5
    assert ctx.get_variable_value("VAR18008", "linha", "L2", "2026-09-14") == 1234.5


def test_13_2_local_identity_is_preserved():
    reg = registry()
    link_ = reg.link_for("VAR18008")
    assert (link_.consumer_block, link_.consumer_definition_id) == ("energy", "VAR18008")
    assert (link_.source_block, link_.source_definition_id) == ("production", "VAR12031")
    r, ctx = resolver(reg)
    ctx.set_variable_value("VAR12031", 7.0, "linha", "L1", "2026-09-14")
    r.transfer("VAR18008", "linha", "L1", "2026-09-14")
    # Duas chaves distintas no contexto; o produtor não é alterado.
    assert ctx.get_variable_value("VAR18008", "linha", "L1", "2026-09-14") == 7.0
    assert ctx.get_variable_value("VAR12031", "linha", "L1", "2026-09-14") == 7.0
    ctx.set_variable_value("VAR12031", 8.0, "linha", "L1", "2026-09-14")
    assert ctx.get_variable_value("VAR18008", "linha", "L1", "2026-09-14") == 7.0


def test_13_3_instance_is_exact():
    r, ctx = resolver()
    for i, line in enumerate(LINES, start=1):
        ctx.set_variable_value("VAR12031", 100.0 * i, "linha", line, "2026-09-14")
    assert r.resolve("VAR18008", "linha", "L3", "2026-09-14") == 300.0

    r2, ctx2 = resolver()
    ctx2.set_variable_value("VAR12031", 100.0, "linha", "L1", "2026-09-14")
    ctx2.set_variable_value("VAR12031", 999.0, "linha_grupo", "L1_L7", "2026-09-14")
    with pytest.raises(InterblockSourceValueNotFoundError) as error:
        r2.resolve("VAR18008", "linha", "L3", "2026-09-14")
    assert error.value.details["instance"] == ("linha", "L3")
    # Instância fora do vínculo: nem é tentada.
    with pytest.raises(InterblockInstanceNotDeclaredError):
        r2.resolve("VAR18008", "linha_grupo", "L1_L7", "2026-09-14")


def test_13_4_frequency_is_never_substituted():
    r, ctx = resolver()
    # Produtor mensal/anual existentes não servem a um vínculo diário.
    ctx.set_variable_value("VAR12031", 1.0, "linha", "L1", "2026-09")
    ctx.set_variable_value("VAR12031", 2.0, "linha", "L1", "2026")
    ctx.set_variable_value("VAR12032", 3.0, "linha", "L1", "2026-09")
    with pytest.raises(InterblockSourceValueNotFoundError):
        r.resolve("VAR18008", "linha", "L1", "2026-09-14")
    with pytest.raises(InterblockPeriodFrequencyMismatchError):
        r.resolve("VAR18008", "linha", "L1", "2026-09")
    with pytest.raises(InterblockPeriodFrequencyMismatchError):
        r.resolve("VAR18008", "linha", "L1", "2026")


def test_13_5_chain_a_b_c():
    r, ctx = resolver()
    for i, line in enumerate(LINES, start=1):
        ctx.set_variable_value("VAR12031", 1000.0 + i, "linha", line, "2026-09-14")
    transferred = r.transfer_all({"diário": "2026-09-14"})
    order = [consumer for consumer, *_ in transferred]
    assert order.index("VAR11031") < order.index("VAR16007")
    for i, line in enumerate(LINES, start=1):
        assert ctx.get_variable_value("VAR12031", "linha", line, "2026-09-14") == 1000.0 + i
        assert ctx.get_variable_value("VAR11031", "linha", line, "2026-09-14") == 1000.0 + i
        assert ctx.get_variable_value("VAR16007", "linha", line, "2026-09-14") == 1000.0 + i
    # O último salto lê o intermediário (yield), não o produtor final.
    assert registry().link_for("VAR16007").source_definition_id == "VAR11031"


def test_13_6_pending_link_is_an_explicit_error():
    r, ctx = resolver()
    for method in (r.resolve, r.transfer):
        with pytest.raises(InterblockSourceNotLoadedError) as error:
            method("VAR16021", "linha", "L5", "2026-09-14")
        assert error.value.code == "INTERBLOCK_SOURCE_NOT_LOADED"
        details = error.value.details
        assert (details["consumer_block"], details["consumer_definition_id"], details["source_block"]) == (
            "area_41", "VAR16021", "maintenance",
        )
        assert details["frequency"] == "diário" and details["scope"] == ("linha", "L4_L7")
        assert "hes" in str(error.value)
    # Nenhum valor fictício foi gravado no consumidor.
    with pytest.raises(VariableNotFoundError):
        ctx.get_variable_value("VAR16021", "linha", "L5", "2026-09-14")


CORRUPTIONS = {
    "unknown_consumer_id": lambda p, v: p["links"][0].update(consumer_definition="VAR11999"),
    "producer_in_other_block": lambda p, v: p["links"][0].update(source_definition="VAR11031"),
    "same_block": lambda p, v: p["links"][0].update(source_block="yield", source_definition="VAR11031"),
    "unloaded_source_in_links": lambda p, v: p["links"][0].update(source_block="forecast"),
    "frequency_differs_from_definition": lambda p, v: p["links"][0].update(source_frequency="mensal"),
    "frequency_conversion": lambda p, v: (
        p["links"][0].update(source_definition="VAR12032", source_frequency="mensal")
    ),
    "scope_differs": lambda p, v: p["links"][0]["consumer_scope"].update(scope_value="L1_L3"),
    "unit_conversion": lambda p, v: v["production"][0].update(unit="m³/d"),
    "value_type_differs": lambda p, v: v["production"][0].update(value_type="categorico"),
    "instance_not_in_producer": lambda p, v: p["links"][0]["instances"].append(
        {"scope_type": "linha_grupo", "scope_value": "L1_L7"}
    ),
    "repeated_instance": lambda p, v: p["links"][0]["instances"].append(
        {"scope_type": "linha", "scope_value": "L1"}
    ),
    "no_instances": lambda p, v: p["links"][0].update(instances=[]),
    "missing_field": lambda p, v: p["links"][0].pop("source_scope"),
    "duplicate_consumer": lambda p, v: p["links"].append(copy.deepcopy(p["links"][0])),
    "pending_with_fictitious_producer": lambda p, v: p["pending"][0].update(source_definition="VAR10001"),
    "pending_to_loaded_block": lambda p, v: p["pending"][0].update(source_block="production"),
    "pending_outside_taxonomy": lambda p, v: p["pending"][0].update(source_block="mx_ht"),
    "consumer_both_linked_and_pending": lambda p, v: p["pending"].append(
        pending("energy", "VAR18008", "lth", "forecast")
    ),
    "no_taxonomy": lambda p, v: p.pop("taxonomy"),
}


@pytest.mark.parametrize("corruption", sorted(CORRUPTIONS))
def test_13_7_corrupted_seed_is_not_a_valid_link(corruption):
    payload, variables = world()
    CORRUPTIONS[corruption](payload, variables)
    with pytest.raises(InterblockSeedError):
        registry(payload, variables)


def test_13_7b_unknown_and_rejected_consumers_are_explicit_errors():
    payload, variables = world()
    payload["rejected"].append({
        "consumer_block": "energy", "consumer_definition": "VAR18010",
        "source_block": "bloco production",
        "errors": [{"code": "INTERBLOCK_SOURCE_BLOCK_UNKNOWN"}],
    })
    r, ctx = resolver(registry(payload, variables))
    with pytest.raises(InterblockLinkRejectedError):
        r.resolve("VAR18010", "linha_grupo", "L1_L7", "2026-09")
    with pytest.raises(InterblockLinkNotFoundError):
        r.resolve("VAR12031", "linha", "L1", "2026-09-14")


def test_13_8_no_unit_conversion():
    r, ctx = resolver()
    assert registry().link_for("VAR18008").unit == "m³/h"
    for value in (1050, 1050.0, 0.1 + 0.2, 1e-12):
        ctx.set_variable_value("VAR12031", value, "linha", "L1", None)
        got = r.resolve("VAR18008", "linha", "L1", None)
        assert got == value and type(got) is type(value)


def test_13_9_same_name_in_two_blocks_stays_two_entities():
    reg = registry()
    names = {("production", "VAR12031"), ("yield", "VAR11031"), ("area_41", "VAR16007"), ("energy", "VAR18008")}
    assert {(l.consumer_block, l.consumer_definition_id) for l in reg.links()} | {("production", "VAR12031")} == names
    r, ctx = resolver(reg)
    ctx.set_variable_value("VAR12031", 1.0, "linha", "L1", "2026-09-14")
    ctx.set_variable_value("VAR11031", 2.0, "linha", "L1", "2026-09-14")
    # energy.lth lê production.lth, não yield.lth (mesmo nome).
    assert r.resolve("VAR18008", "linha", "L1", "2026-09-14") == 1.0
    assert r.resolve("VAR16007", "linha", "L1", "2026-09-14") == 2.0


def test_13_10_order_does_not_change_the_result():
    results = []
    for seed in (0, 1, 2, 3):
        payload, variables = world()
        rng = random.Random(seed)
        rng.shuffle(payload["links"])
        variables = dict(sorted(variables.items(), key=lambda _: rng.random()))
        reg = registry(payload, variables)
        r, ctx = resolver(reg)
        for i, line in enumerate(LINES, start=1):
            ctx.set_variable_value("VAR12031", 10.0 * i, "linha", line, "2026-09-14")
        results.append((
            [l.consumer_definition_id for l in reg.links()],
            r.transfer_all({"diário": "2026-09-14"}),
        ))
    assert all(result == results[0] for result in results)


def test_13_11_cycle_is_rejected_before_execution():
    payload, variables = world()
    payload["links"].append(link("production", "VAR12031", "area_41", "VAR16007"))
    with pytest.raises(InterblockCycleError) as error:
        registry(payload, variables)
    assert error.value.code == "INTERBLOCK_CYCLE"
    assert set(error.value.details["cycle"]) >= {"VAR12031", "VAR11031", "VAR16007"}


def test_13_12_no_fallback_of_any_kind():
    payload, variables = world()
    variables["production"][0]["source_reference"] = "yield"
    r, ctx = resolver(registry(payload, variables))
    # outro bloco com o mesmo nome, outra instância, outra frequência,
    # sem período, valor local do consumidor: nenhum é usado.
    ctx.set_variable_value("VAR11031", 1.0, "linha", "L4", "2026-09-14")
    ctx.set_variable_value("VAR12031", 2.0, "linha", "L3", "2026-09-14")
    ctx.set_variable_value("VAR12032", 3.0, "linha", "L4", "2026-09")
    ctx.set_variable_value("VAR12031", 4.0, "linha", "L4", None)
    ctx.set_variable_value("VAR12031", 5.0, "linha", "L4", "2026-09")
    ctx.set_variable_value("VAR18008", 6.0, "linha", "L4", "2026-09-14")
    with pytest.raises(InterblockSourceValueNotFoundError):
        r.resolve("VAR18008", "linha", "L4", "2026-09-14")
    # E um valor local divergente nunca é sobrescrito em silêncio.
    ctx.set_variable_value("VAR12031", 7.0, "linha", "L4", "2026-09-14")
    with pytest.raises(InterblockConsumerValueConflictError):
        r.transfer("VAR18008", "linha", "L4", "2026-09-14")
    assert ctx.get_variable_value("VAR18008", "linha", "L4", "2026-09-14") == 6.0


def _code_tokens(path):
    """Imports, constantes de texto (fora de docstrings), nomes e atributos."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    tokens = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tokens |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            tokens.add(node.module or "")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            tokens.add(node.value)
        elif isinstance(node, ast.Attribute):
            tokens.add(node.attr)
        elif isinstance(node, ast.Name):
            tokens.add(node.id)
    return tokens


def test_runtime_does_not_read_workbooks_or_fonte():
    for module in ("app/engine/interblock_resolver.py", "app/domain/interblock/registry.py",
                   "app/domain/interblock/models.py"):
        tokens = _code_tokens(REPO / module)
        assert not [t for t in tokens if t.startswith(("openpyxl", "tools"))], module
        assert not [t for t in tokens if ".xlsx" in t], module
        assert "fonte" not in tokens and "source_reference" not in tokens, module


# ------------------------------------------------------------
# 14 — os vínculos reais
# ------------------------------------------------------------

@pytest.fixture(scope="module")
def real_registry():
    return SeedLoader(SEED_ROOT).load_interblock_links()


def _producer_value(link, instance):
    # Valor determinístico e distinto por vínculo/instância.
    number = int(link.source_definition_id[3:])
    line = instance[1] or ""
    return number + sum(ord(c) for c in line) / 1000.0


def test_14_all_13_real_links_are_consumable(real_registry):
    links = real_registry.links()
    assert len(links) == 13 and len(real_registry.pending()) == 16 and real_registry.rejected() == []

    context = CalculationContext()
    resolver_ = InterblockValueResolver(real_registry, context)
    chained = {l.consumer_definition_id for l in links}
    for link_ in links:
        if link_.source_definition_id in chained:
            continue  # o valor do intermediário vem do salto anterior
        for instance in link_.instances:
            context.set_variable_value(
                link_.source_definition_id, _producer_value(link_, instance),
                *instance, PERIODS[link_.frequency],
            )

    transferred = resolver_.transfer_all(PERIODS)
    assert len(transferred) == sum(len(l.instances) for l in links)

    for link_ in links:
        root = link_
        while root.source_definition_id in chained:
            root = real_registry.link_for(root.source_definition_id)
        for instance in link_.instances:
            expected = _producer_value(root, instance)
            period = PERIODS[link_.frequency]
            assert context.get_variable_value(link_.consumer_definition_id, *instance, period) == expected
            assert link_.consumer_definition_id != link_.source_definition_id
            assert link_.consumer_block != link_.source_block


def test_14_real_chain_three_levels(real_registry):
    area_41 = real_registry.link_for("VAR16007")
    yield_ = real_registry.link_for("VAR11031")
    assert (area_41.consumer_block, area_41.source_block, area_41.source_definition_id) == ("area_41", "yield", "VAR11031")
    assert (yield_.consumer_block, yield_.source_block, yield_.source_definition_id) == ("yield", "production", "VAR12031")

    context = CalculationContext()
    resolver_ = InterblockValueResolver(real_registry, context)
    period = PERIODS["diário"]
    for i, line in enumerate(LINES, start=1):
        context.set_variable_value("VAR12031", 1100.0 + i, "linha", line, period)

    # Sem o salto intermediário, o último salto não tem valor.
    with pytest.raises(InterblockSourceValueNotFoundError):
        resolver_.resolve("VAR16007", "linha", "L3", period)

    resolver_.transfer_link("VAR11031", period)
    resolver_.transfer_link("VAR16007", period)
    for i, line in enumerate(LINES, start=1):
        assert context.get_variable_value("VAR12031", "linha", line, period) == 1100.0 + i
        assert context.get_variable_value("VAR11031", "linha", line, period) == 1100.0 + i
        assert context.get_variable_value("VAR16007", "linha", line, period) == 1100.0 + i


def test_14_real_pending_links_raise(real_registry):
    context = CalculationContext()
    resolver_ = InterblockValueResolver(real_registry, context)
    sources = set()
    for p in real_registry.pending():
        sources.add(p.source_block)
        instance = p.instances[0]
        with pytest.raises(InterblockSourceNotLoadedError) as error:
            resolver_.transfer(p.consumer_definition_id, *instance, PERIODS[p.consumer_frequency])
        assert error.value.details["source_block"] == p.source_block
    assert sources == {"maintenance", "temperature_lp", "area_04_13", "alumina", "forecast"}
    # fator_mpsa / fator_mrn (calculadas, D26-03) não são consumidoras.
    loader = SeedLoader(SEED_ROOT)
    names = {v.variable_definition_id: v.variable_name for v in loader.load_variable_definitions().all()}
    consumers = {l.consumer_definition_id for l in real_registry.links()} | {
        p.consumer_definition_id for p in real_registry.pending()
    }
    assert not {c for c in consumers if names[c] in ("fator_mpsa", "fator_mrn")}


def test_14_consumer_equation_runs_on_transferred_value(real_registry):
    """energy EQ18001: VAR18002 = VAR18001 / 24, VAR18001 <- production.producao."""
    loader = SeedLoader(SEED_ROOT)
    definition = loader.load_equation_definitions().get("EQ18001")
    assert definition.expression == "VAR18001 / 24"
    link_ = real_registry.link_for("VAR18001")
    assert (link_.source_block, link_.source_definition_id) == ("production", "VAR12046")

    context = CalculationContext()
    resolver_ = InterblockValueResolver(real_registry, context)
    period = PERIODS["diário"]
    context.set_variable_value("VAR12046", 4800.0, "linha", "L3", period)
    resolver_.transfer("VAR18001", "linha", "L3", period)

    instance = EquationInstance.create(definition=definition, scope_type="linha", scope_value="L3")
    result = EquationEngine().calculate_instance(
        instance=instance, definition=definition, calculation_context=context, period_id=period,
    )
    assert result == pytest.approx(200.0)


def test_14_real_registry_matches_seed_file(real_registry):
    payload = json.loads((SEED_ROOT / "interblock_links.json").read_text(encoding="utf-8"))
    assert sorted(l.consumer_definition_id for l in real_registry.links()) == sorted(
        r["consumer_definition"] for r in payload["links"]
    )
    for record in payload["links"]:
        l = real_registry.link_for(record["consumer_definition"])
        assert l.source_definition_id == record["source_definition"]
        assert [list(i) for i in l.instances] == [[i["scope_type"], i["scope_value"]] for i in record["instances"]]
