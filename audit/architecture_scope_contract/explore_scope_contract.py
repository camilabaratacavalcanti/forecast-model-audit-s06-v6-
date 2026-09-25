"""
Verificação arquitetural (não destrutiva) do contrato de escopo,
identidade e tipos da plataforma Forecast.

Executa sondas diretas contra o código de produção (sem modificá-lo),
os seeds de todos os blocos, os builders e os workbooks reais, e grava
as matrizes/evidências deste diretório. Não usa harnesses nem relatórios
de auditorias anteriores como evidência.

    python3 audit/architecture_scope_contract/explore_scope_contract.py

IDs de fixture: VAR97xxx/PARAM97xxx (efêmeros, fora de faixas produtivas).
"""

import csv
import inspect
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.domain import values as values_module  # noqa: E402
from app.domain.forecast.aggregation import AggregationRule  # noqa: E402
from app.domain.parameters.models import ParameterDefinition  # noqa: E402
from app.domain.parameters.registry import ParameterDefinitionRegistry  # noqa: E402
from app.domain.variables.models import VariableDefinition, VariableInstance  # noqa: E402
from app.domain.variables.registry import VariableDefinitionRegistry  # noqa: E402
from app.engine import reference_resolver, scoped_reference  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.exceptions import (  # noqa: E402
    AggregationFailureError,
    CalculationValueError,
    ConditionalFailureError,
    UnsafeExpressionError,
    VariableNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator  # noqa: E402
from app.engine.expression_parser import ExpressionParser  # noqa: E402
from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.spatial_candidate_resolver import get_spatial_candidates  # noqa: E402
from app.engine.temporal_aggregation_service import TemporalAggregationService  # noqa: E402
from app.validation import (  # noqa: E402
    equation_seed_validator as eqv,
    parameter_seed_validator as pv,
    variable_seed_validator as vv,
)

EVIDENCE = HERE / "evidence"
WORKBOOKS = EVIDENCE / "workbooks"
SEED = ROOT / "data" / "seed"
BLOCKS = ["yield", "production", "energy", "max_ht"]

RESULTS: list[dict] = []


def where(obj) -> str:
    """arquivo:linha de um símbolo de produção (evidência primária)."""

    try:
        path = Path(inspect.getsourcefile(obj)).resolve().relative_to(ROOT)
        return f"{path}:{inspect.getsourcelines(obj)[1]}"
    except (TypeError, OSError, ValueError):
        return "?"


def probe(case_id, layer, description, fn, expected, symbol=None):
    """Executa uma sonda; registra entrada, resultado observado e comparação."""

    try:
        observed = fn()
        observed_text = f"OK: {observed!r}"
    except Exception as exc:  # noqa: BLE001
        observed_text = f"{type(exc).__name__}: {str(exc)[:160]}"
    status = "CONSISTENT" if re.search(expected, observed_text) else "DIVERGENT"
    RESULTS.append({
        "id": case_id, "layer": layer, "description": description,
        "expected_regex": expected, "observed": observed_text, "status": status,
        "code": where(symbol) if symbol else "",
    })
    return observed_text


def write_csv(name, rows):
    with open(HERE / name, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# Q1 — scope_type / scope_value: aceitação em cada camada
# ============================================================


def accepts_variable_validator(st, sv):
    row = {"variable_id": "VAR97001", "_block": "probe", "scope_type": st, "scope_value": sv}
    errs = vv.validate_enum_values([row]) + vv.validate_scope_consistency([row]) + vv.validate_scope_type_value_combination([row])
    return not errs


def accepts_module(module, st, sv):
    """Enums + regra de combinação real de cada validador."""

    ok_type = st in module.ALLOWED_SCOPE_TYPES
    ok_value = sv is None or sv in module.ALLOWED_SCOPE_VALUES
    if module is pv:
        combo = not pv.validate_scope_values({"scope_type": st, "scope_value": sv}, "probe")
    else:
        combo = not eqv.validate_scope_consistency([{"scope_type": st, "scope_value": sv}])
    return ok_type and ok_value and combo


def scope_resolver_result(st, sv):
    try:
        return "; ".join(f"{a}/{b}" for a, b in ScopeResolver().resolve_scopes(st, sv))
    except ValueError as exc:
        return f"REJEITA ({exc})"


def dsl_result(sv):
    if sv is None:
        return "n/a"
    try:
        return f"@{sv} -> {scoped_reference.scope_type_for(sv)}"
    except scoped_reference.InvalidScopeReferenceError:
        return f"@{sv} REJEITADO"


MEANING = {
    "linha": "linha de produção; scope_value = linha (L1..L7) ou faixa Lx_Ly EXPANDIDA em uma instância por linha",
    "linha_grupo": "grupo de linhas tratado como UMA unidade (não expandido); scope_value = grupo registrado em ScopeResolver.LINE_GROUP_SCOPES",
    "planta": "planta inteira; scope_value obrigatório = 'PLANTA'",
    "área": "escopo singular sem materialização; scope_value = None",
    "global": "escopo singular sem materialização; scope_value = None",
}


def q1_scope_matrix():
    combos = [("linha", v) for v in ("L1", "L4", "L7", "L1_L7", "L1_L3", "L4_L5", "L2_L6", "L8", "PLANTA")]
    combos += [("linha_grupo", v) for v in ("L1_L3", "L4_L5", "L6_L7", "L1_L7", "L2_L6", "L4", "L5_L4")]
    combos += [("planta", "PLANTA"), ("planta", "L1"), ("área", None), ("área", "L1"), ("global", None), ("setor", "X")]
    rows = []
    for st, sv in combos:
        rows.append({
            "scope_type": st, "scope_value": "" if sv is None else sv,
            "variable_seed_validator": "aceita" if accepts_variable_validator(st, sv) else "rejeita",
            "parameter_seed_validator": "aceita" if accepts_module(pv, st, sv) else "rejeita",
            "equation_seed_validator": "aceita" if accepts_module(eqv, st, sv) else "rejeita",
            "ScopeResolver.resolve_scopes": scope_resolver_result(st, sv),
            "DSL_@referencia": dsl_result(sv),
            "significado": MEANING.get(st, "não suportado"),
        })
    write_csv("scope_contract_matrix.csv", rows)
    enums = {
        "variable_seed_validator": (sorted(vv.ALLOWED_SCOPE_TYPES), sorted(vv.ALLOWED_SCOPE_VALUES)),
        "parameter_seed_validator": (sorted(pv.ALLOWED_SCOPE_TYPES), sorted(pv.ALLOWED_SCOPE_VALUES)),
        "equation_seed_validator": (sorted(eqv.ALLOWED_SCOPE_TYPES), sorted(eqv.ALLOWED_SCOPE_VALUES)),
        "ScopeResolver": (["linha", "linha_grupo", "planta", "área", "global"],
                          sorted(ScopeResolver.LINE_SCOPES | ScopeResolver.LINE_GROUP_SCOPES | {ScopeResolver.PLANT_SCOPE})),
        "ScopeResolver.GROUP_MEMBERS": {k: sorted(v) for k, v in ScopeResolver.GROUP_MEMBERS.items()},
    }
    return rows, enums


# ============================================================
# Q2/Q3/Q4 — referências name@scope (camada de nomes e camada de IDs)
# ============================================================


def entity(eid, name, freq, st, sv, kind="variable"):
    return {"entity_id": eid, "name": name, "kind": kind, "frequency": freq, "scope_type": st, "scope_value": sv}


HES = [
    entity("VAR97001", "hes", "diário", "linha", "L4"),
    entity("VAR97002", "hes", "diário", "linha", "L5"),
    entity("VAR97003", "hes", "mensal", "linha", "L4"),
    entity("VAR97004", "hes", "diário", "linha_grupo", "L4_L5"),
    entity("VAR97005", "hes_l4", "diário", "linha", "L4"),
    entity("VAR97006", "serie", "diário", "linha", "L1_L7"),
]


def resolve(name, freq, consumer, explicit=None, entities=HES):
    return reference_resolver.resolve_reference(
        name, reference_resolver.build_name_index(entities), freq, consumer_scope=consumer, explicit_scope_value=explicit)


def evaluate(expr, context, scope=(None, None)):
    return ExpressionEvaluator(context, scope[0], scope[1]).evaluate(ExpressionParser().parse(expr))


def q2_q3_q4_probes():
    rr, P = reference_resolver.resolve_reference, ExpressionParser.parse
    # --- camada de NOMES (workbook -> builder) ---
    probe("N01", "nomes", "hes@L4 (consumidor grupo L4_L5, diário)", lambda: resolve("hes", "diário", ("linha_grupo", "L4_L5"), "L4"), r"VAR97001", rr)
    probe("N02", "nomes", "hes@L5", lambda: resolve("hes", "diário", ("linha_grupo", "L4_L5"), "L5"), r"VAR97002", rr)
    probe("N03", "nomes", "hes@L4 com frequência mensal", lambda: resolve("hes", "mensal", ("linha", "L4"), "L4"), r"VAR97003", rr)
    probe("N04", "nomes", "hes@L4_L5 (grupo explícito)", lambda: resolve("hes", "diário", ("planta", "PLANTA"), "L4_L5"), r"VAR97004", rr)
    probe("N05", "nomes", "hes implícito do consumidor linha/L4", lambda: resolve("hes", "diário", ("linha", "L4")), r"VAR97001", rr)
    probe("N06", "nomes", "hes implícito do consumidor linha/L5", lambda: resolve("hes", "diário", ("linha", "L5")), r"VAR97002", rr)
    probe("N07", "nomes", "hes implícito do consumidor grupo L4_L5", lambda: resolve("hes", "diário", ("linha_grupo", "L4_L5")), r"VAR97004", rr)
    probe("N08", "nomes", "hes implícito do consumidor planta (nenhum candidato alcançável)", lambda: resolve("hes", "diário", ("planta", "PLANTA")), r"ReferenceResolutionError.*amb", rr)
    probe("N09", "nomes", "hes sem escopo e sem consumidor (ambíguo)", lambda: resolve("hes", "diário", None), r"ReferenceResolutionError", rr)
    probe("N10", "nomes", "hes@L6 (escopo sem definição)", lambda: resolve("hes", "diário", ("linha", "L6"), "L6"), r"ReferenceResolutionError", rr)
    probe("N11", "nomes", "hes@L8 (escopo inexistente)", lambda: resolve("hes", "diário", ("linha", "L4"), "L8"), r"Error", rr)
    probe("N12", "nomes", "nome inexistente", lambda: resolve("xyz", "diário", ("linha", "L4")), r"ReferenceNotFoundError", rr)
    probe("N13", "nomes", "consumidor linha/L4_L5 (2 instâncias -> definições diferentes)", lambda: resolve("hes", "diário", ("linha", "L4_L5")), r"ReferenceResolutionError.*definições diferentes", rr)
    probe("N14", "nomes", "hes_l4 e hes coexistem (nomes distintos, mesmo escopo)", lambda: (resolve("hes_l4", "diário", ("linha", "L4")), resolve("hes", "diário", ("linha", "L4"), "L4")), r"VAR97005.*VAR97001", rr)
    probe("N15", "nomes", "serie@L4_L5 com definição linha/L1_L7 (grupo não agrega linhas)", lambda: resolve("serie", "diário", ("planta", "PLANTA"), "L4_L5"), r"ReferenceResolutionError", rr)
    probe("N16", "nomes", "translate preserva sufixo: hes@L4 + hes@L5", lambda: reference_resolver.translate_expression("hes@L4 + hes@L5", reference_resolver.build_name_index(HES), "diário", consumer_scope=("linha_grupo", "L4_L5")), r"VAR97001@L4 \+ VAR97002@L5", reference_resolver.translate_expression)
    stable = []
    for seed in range(5):
        shuffled = list(HES)
        random.Random(seed).shuffle(shuffled)
        stable.append(tuple(resolve("hes", "diário", ("linha", l), l, shuffled) for l in ("L4", "L5")))
    probe("N17", "nomes", "resolução independente da ordem de inserção (5 embaralhamentos)", lambda: len(set(stable)), r"OK: 1$", rr)

    # --- camada de IDs (runtime DSL) ---
    p = ExpressionParser()
    probe("P01", "parser", "hes@L4 (NOME) no parser do runtime", lambda: p.parse("hes@L4"), r"UnsafeExpressionError", ExpressionParser.parse)
    probe("P02", "parser", "retirada_condensado_linha@L4 (NOME) no parser", lambda: p.parse("retirada_condensado_linha@L4"), r"UnsafeExpressionError", ExpressionParser.parse)
    for i, tok in enumerate(["L4", "L5", "L4_L5", "L1_L3", "L6_L7", "L1_L7"], start=3):
        probe(f"P{i:02d}", "parser", f"VAR97001@{tok} (ID) -> nome interno do AST",
              lambda tok=tok: p.parse(f"VAR97001@{tok}").body.id, rf"VAR97001__{tok}", scoped_reference.to_internal)
    for i, tok in enumerate(["L8", "L5_L4", "L2_L6", "PLANTA", "L1_L2"], start=9):
        probe(f"P{i:02d}", "parser", f"VAR97001@{tok} (escopo não registrado)", lambda tok=tok: p.parse(f"VAR97001@{tok}"), r"UnsafeExpressionError", scoped_reference.scope_type_for)
    probe("P14", "parser", "@ solto (MatMult)", lambda: p.parse("VAR97001 @ VAR97002"), r"UnsafeExpressionError", scoped_reference.to_internal)
    probe("P15", "parser", "split_internal de grupo", lambda: scoped_reference.split_internal("VAR97001__L4_L5"), r"linha_grupo", scoped_reference.split_internal)
    probe("P16", "parser", "split_internal de linha", lambda: scoped_reference.split_internal("VAR97001__L4"), r"'linha', 'L4'", scoped_reference.split_internal)

    # --- runtime: resolução/armazenamento com IDs ---
    def ctx_l4_l5():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 4.0, "linha", "L4")
        c.set_variable_value("VAR97001", 5.0, "linha", "L5")
        return c

    ev = ExpressionEvaluator._resolve_name
    probe("R01", "runtime", "VAR@L4 lê só L4", lambda: evaluate("VAR97001@L4", ctx_l4_l5()), r"OK: 4\.0", ev)
    probe("R02", "runtime", "VAR@L5 lê só L5", lambda: evaluate("VAR97001@L5", ctx_l4_l5()), r"OK: 5\.0", ev)

    def only_l5():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 5.0, "linha", "L5")
        return evaluate("VAR97001@L4", c)
    probe("R03", "runtime", "VAR@L4 sem valor em L4 (existe L5): não cai para L5", only_l5, r"VariableNotFoundError", ev)

    def explicit_vs_legacy():
        c = CalculationContext({"VAR97001": 99.0})
        return evaluate("VAR97001@L4", c)
    probe("R04", "runtime", "VAR@L4 com apenas valor legado sem escopo: não cai para o legado", explicit_vs_legacy, r"VariableNotFoundError", ev)

    def implicit_legacy():
        c = CalculationContext({"VAR97001": 99.0})
        c.set_variable_value("VAR97001", 5.0, "linha", "L5")
        return evaluate("VAR97001", c, ("linha", "L4"))
    probe("R05", "runtime", "VAR implícito (consumidor L4) sem valor em L4/grupos/planta mas com legado sem escopo", implicit_legacy, r"OK: 99\.0", ev)

    def implicit_lateral():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 5.0, "linha", "L5")
        return evaluate("VAR97001", c, ("linha", "L4"))
    probe("R06", "runtime", "VAR implícito (consumidor L4) com valor só em L5: não lateraliza", implicit_lateral, r"VariableNotFoundError", ev)

    def implicit_outward():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 45.0, "linha_grupo", "L4_L5")
        return evaluate("VAR97001", c, ("linha", "L4"))
    probe("R07", "runtime", "VAR implícito (consumidor L4) com valor no grupo L4_L5: sobe ao grupo", implicit_outward, r"OK: 45\.0", ev)

    def group_not_aggregate():
        c = ctx_l4_l5()
        return evaluate("VAR97001@L4_L5", c)
    probe("R08", "runtime", "VAR@L4_L5 com valores só em L4 e L5: grupo NÃO é agregado das linhas", group_not_aggregate, r"VariableNotFoundError", ev)

    def group_in_line_context():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 45.0, "linha_grupo", "L4_L5")
        return evaluate("VAR97001@L4_L5", c, ("linha", "L4"))
    probe("R09", "runtime", "VAR@L4_L5 em contexto de linha L4", group_in_line_context, r"OK: 45\.0", ev)

    def group_inward():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 4.0, "linha", "L4")
        return evaluate("VAR97001", c, ("linha_grupo", "L4_L5"))
    probe("R10", "runtime", "VAR implícito do grupo L4_L5 com valor só em linha L4: nunca desce", group_inward, r"VariableNotFoundError", ev)

    # --- grupos ---
    probe("G01", "grupos", "linha_grupo/L4_L5 materializa 1 instância (não expande)", lambda: ScopeResolver().resolve_scopes("linha_grupo", "L4_L5"), r"\[\('linha_grupo', 'L4_L5'\)\]$", ScopeResolver._resolve_line_group_scope)
    probe("G02", "grupos", "linha/L4_L5 expande em L4, L5", lambda: ScopeResolver().resolve_scopes("linha", "L4_L5"), r"\('linha', 'L4'\), \('linha', 'L5'\)", ScopeResolver._resolve_line_scope)
    probe("G03", "grupos", "linha/L2_L6 (faixa não registrada) aceita pelo ScopeResolver", lambda: ScopeResolver().resolve_scopes("linha", "L2_L6"), r"L6", ScopeResolver._parse_line_range)
    probe("G04", "grupos", "linha_grupo/L2_L6 (grupo não registrado)", lambda: ScopeResolver().resolve_scopes("linha_grupo", "L2_L6"), r"ValueError", ScopeResolver._resolve_line_group_scope)
    probe("G05", "grupos", "linha/L1_L8 (membro inexistente)", lambda: ScopeResolver().resolve_scopes("linha", "L1_L8"), r"ValueError", ScopeResolver._parse_line_range)
    probe("G06", "grupos", "linha/L5_L4 (ordem invertida)", lambda: ScopeResolver().resolve_scopes("linha", "L5_L4"), r"ValueError", ScopeResolver._parse_line_range)
    probe("G07", "grupos", "GROUP_MEMBERS é imutável", lambda: __import__("operator").setitem(ScopeResolver.GROUP_MEMBERS, "L1_L2", frozenset()), r"TypeError.*does not support item assignment", ScopeResolver)
    probe("G08", "grupos", "cadeia espacial de L4", lambda: get_spatial_candidates("linha", "L4"), r"L4_L5.*L1_L7.*PLANTA", get_spatial_candidates)
    probe("G09", "grupos", "cadeia espacial do grupo L4_L5", lambda: get_spatial_candidates("linha_grupo", "L4_L5"), r"L1_L7.*PLANTA", get_spatial_candidates)

    # --- armazenamento/identidade ---
    def store_modify():
        c = ctx_l4_l5()
        c.set_variable_value("VAR97001", 40.0, "linha", "L4")
        return (c.get_variable_value("VAR97001", "linha", "L4"), c.get_variable_value("VAR97001", "linha", "L5"))
    probe("S01", "armazenamento", "alterar L4 não altera L5 (mesmo ID)", store_modify, r"OK: \(40\.0, 5\.0\)", CalculationContext.set_variable_value)

    def store_period():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 1.0, "linha", "L4", "2026-07-01")
        c.set_variable_value("VAR97001", 2.0, "linha", "L4", "2026-07")
        return (c.get_variable_value("VAR97001", "linha", "L4", "2026-07-01"), c.get_variable_value("VAR97001", "linha", "L4", "2026-07"))
    probe("S02", "armazenamento", "mesmo ID e escopo, períodos distintos: chaves distintas", store_period, r"OK: \(1\.0, 2\.0\)", CalculationContext.set_variable_value)

    def legacy_separate():
        c = ctx_l4_l5()
        c.set_variable("VAR97001", 7.0)
        return (c.get_variable("VAR97001"), c.get_variable_value("VAR97001", "linha", "L4"))
    probe("S03", "armazenamento", "API legada (chave só ID) coexiste com a contextual", legacy_separate, r"OK: \(7\.0, 4\.0\)", CalculationContext.set_variable)

    def definition_same_id_two_scopes():
        r = VariableDefinitionRegistry()
        r.add(VariableDefinition("VAR97001", "hes", "-", "-", "entrada", "diário", "linha", "L4", "t", "ativo"))
        r.add(VariableDefinition("VAR97001", "hes", "-", "-", "entrada", "diário", "linha", "L5", "t", "ativo"))
    probe("S04", "armazenamento", "VariableDefinitionRegistry: mesmo ID em 2 escopos", definition_same_id_two_scopes, r"ValueError", VariableDefinitionRegistry.add)

    def parameter_same_id_two_scopes():
        r = ParameterDefinitionRegistry()
        for sv in ("L4", "L5"):
            r.add(ParameterDefinition("PARAM97001", "k", "-", "-", 1.0, 1, "linha", sv, "t", "ativo"))
        return len(r.all())
    probe("S05", "armazenamento", "ParameterDefinitionRegistry: mesmo ID em 2 escopos", parameter_same_id_two_scopes, r"OK: 2", ParameterDefinitionRegistry.add)

    def instance_ids():
        d = VariableDefinition("VAR97001", "hes", "-", "-", "entrada", "diário", "linha", "L4_L5", "t", "ativo")
        return [VariableInstance.create(d, st, sv).variable_instance_id for st, sv in ScopeResolver().resolve_scopes("linha", "L4_L5")]
    probe("S06", "armazenamento", "instâncias de uma definição linha/L4_L5", instance_ids, r"VAR97001@L4.*VAR97001@L5", VariableInstance.create)

    def name_index():
        return {k: len(v) for k, v in reference_resolver.build_name_index(HES).items()}
    probe("S07", "armazenamento", "índice por nome guarda TODAS as ocorrências", name_index, r"'hes': 4", reference_resolver.build_name_index)

    # --- value_type / "F" ---
    def mixed():
        VariableDefinition("VAR97001", "x", "-", "-", "calculado", "diário", "linha", "L4", "t", "ativo", "mixed")
    probe("T01", "value_type", "value_type 'mixed'", mixed, r"ValueError", VariableDefinition.__post_init__)
    probe("T02", "value_type", "texto em variável numeric", lambda: CalculationContext().set_variable("VAR97001", "Normal"), r"CalculationValueError", CalculationContext._validate_variable_value)
    probe("T03", "value_type", "texto em variável categorical", lambda: CalculationContext(categorical_variable_ids={"VAR97001"}).set_variable("VAR97001", "Normal"), r"OK: None", CalculationContext._validate_variable_value)
    probe("T04", "value_type", '"F" em variável numeric (sentinela de falha)', lambda: CalculationContext().set_variable("VAR97001", "F"), r"OK: None", CalculationContext._validate_variable_value)
    probe("T05", "value_type", '"F" em parâmetro', lambda: CalculationContext().set_parameter("PARAM97001", "F"), r"CalculationValueError", CalculationContext.set_parameter)
    probe("T06", "value_type", 'consumir "F" em aritmética', lambda: evaluate("VAR97001 + 1", CalculationContext({"VAR97001": "F"})), r"ConditionalFailureError", ExpressionEvaluator)
    probe("T07", "value_type", 'detecção explícita == "F"', lambda: evaluate('1 if VAR97001 == "F" else 0', CalculationContext({"VAR97001": "F"})), r"OK: 1", ExpressionEvaluator)

    def agg_f():
        c = CalculationContext()
        c.set_variable_value("VAR97001", 1.0, "linha", "L4", "2026-03-01")
        c.set_variable_value("VAR97001", "F", "linha", "L4", "2026-03-02")
        from datetime import date
        return TemporalAggregationService().aggregate(AggregationRule("R", "VAR97001", "diário", "VAR97002", "mensal", "AVERAGE"), c, "linha", "L4", date(2026, 3, 2))
    probe("T08", "value_type", 'agregação com "F"', agg_f, r"AggregationFailureError", TemporalAggregationService.aggregate)
    probe("T09", "value_type", "VALUE_TYPES e sentinela", lambda: (sorted(values_module.VALUE_TYPES), values_module.CONDITIONAL_FAILURE), r"\['categorical', 'numeric'\], 'F'", values_module.is_conditional_failure)


# ============================================================
# Q6/Q7/Q8 — seeds, builders, workbooks, nomes espacializados
# ============================================================

SPATIAL = re.compile(r"_(?:l|L)(\d+)(?![a-z])")
SCOPE_LINES = {sv: set(ScopeResolver.GROUP_MEMBERS.get(sv, {sv})) for sv in list(ScopeResolver.LINE_SCOPES) + list(ScopeResolver.LINE_GROUP_SCOPES)}


def suffix_lines(name):
    m = SPATIAL.search(name)
    if not m:
        return None
    digits = m.group(1)
    return {f"L{d}" for d in digits}


def read_workbook(path):
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and "name" in r and "scope_type" in r)
    header = [str(h).lower() if h else None for h in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        d = dict(zip(header, r))
        if d.get("name"):
            out.append(d)
    return out


def classify(name, scope_type, scope_value, siblings):
    lines = suffix_lines(name)
    if lines is None:
        return None
    declared = SCOPE_LINES.get(scope_value, set())
    if siblings > 1 and lines == declared:
        return "2/3: espacialização por nome redundante com o escopo (mesmo radical em vários escopos)"
    if lines == declared:
        return "2: sufixo repete o escopo (redundante), sem irmãos no mesmo bloco"
    if scope_value in ("L1_L7", "PLANTA") or scope_type in ("planta",):
        return "5: sufixo diverge do escopo declarado — revisar"
    return "5: sufixo não corresponde ao escopo — revisar"


def q6_q7_q8():
    usage, inventory, builder_rows = [], [], []
    sources = [(f"seed:{b}", json.load(open(SEED / b / "variables.json")), json.load(open(SEED / b / "equations.json"))) for b in BLOCKS]
    for wb in sorted(WORKBOOKS.glob("*.xlsx")):
        rows = read_workbook(wb)
        vars_ = [{"variable_name": r["name"], "frequency": r.get("frequency"), "scope_type": r.get("scope_type"), "scope_value": r.get("scope_value")}
                 for r in rows if str(r.get("type", "")).startswith("variable")]
        eqs = [{"expression": str(r.get("expression") or "")} for r in rows]
        sources.append((f"workbook:{wb.stem}", vars_, eqs))
    summary = {}
    for label, variables, equations in sources:
        by_name = defaultdict(set)
        for v in variables:
            by_name[v["variable_name"]].add((v["scope_type"], v["scope_value"]))
        multi = {n for n, s in by_name.items() if len(s) > 1}
        refs = Counter(m for e in equations for m in re.findall(r"@(L[1-7](?:_L[1-7])?)", e["expression"]))
        stems = defaultdict(set)
        for n in by_name:
            if suffix_lines(n):
                stems[SPATIAL.sub("", n)].add(n)
        spatial_names = [n for n in by_name if suffix_lines(n)]
        summary[label] = {"variáveis": len(variables), "nomes": len(by_name), "nomes_em_>1_escopo": len(multi),
                          "refs_@linha": sum(c for k, c in refs.items() if "_" not in k), "refs_@grupo": sum(c for k, c in refs.items() if "_" in k),
                          "nomes_espacializados": len(spatial_names)}
        for n in sorted(multi)[:6]:
            usage.append({"Workbook": label, "Variável": n, "Nome": n, "Scope": " | ".join(sorted(f"{a}/{b}" for a, b in by_name[n])),
                          "Referência": "", "Padrão": "mesmo nome em vários escopos (identidade por escopo)"})
        for tok, c in sorted(refs.items()):
            usage.append({"Workbook": label, "Variável": "(expressões)", "Nome": "", "Scope": tok, "Referência": f"@{tok} × {c}",
                          "Padrão": "referência explícita de grupo (@grupo)" if "_" in tok else "referência explícita de linha (@linha)"})
        for n in sorted(spatial_names):
            for st, sv in sorted(by_name[n], key=str):
                stem = SPATIAL.sub("", n)
                category = classify(n, st, sv, len(stems[stem]))
                inventory.append({"fonte": label, "nome": n, "radical": stem, "irmaos_mesmo_radical": " ".join(sorted(stems[stem])),
                                  "scope": f"{st}/{sv}", "linhas_no_sufixo": " ".join(sorted(suffix_lines(n))),
                                  "radical_existe_como_nome": "sim" if stem in by_name else "não", "classificacao": category})
                usage.append({"Workbook": label, "Variável": n, "Nome": n, "Scope": f"{st}/{sv}", "Referência": "",
                              "Padrão": "nome artificialmente espacializado"})
    write_csv("workbook_usage_matrix.csv", usage)
    write_csv("spatialized_name_inventory.csv", inventory)

    # builders
    for path in sorted((ROOT / "tools").glob("*.py")):
        text = path.read_text()
        builder_rows.append({
            "arquivo": str(path.relative_to(ROOT)),
            "usa_reference_resolver_central": "sim" if "reference_resolver." in text else "não",
            "passa_consumer_scope": "sim" if "consumer_scope=" in text else "não",
            "cria_referencias_@": "preserva @ do workbook (translate_expression)" if "translate_expression" in text else "não",
            "gera_nomes_espacializados": "sim" if re.search(r'f"\{[^}]*name[^}]*\}_\{', text) else "não encontrado",
            "resolucao_manual_de_escopo": "sim" if re.search(r"split\(['\"]@", text) else "não",
            "tratamento_especifico_A41": "sim" if re.search(r"A41|area_41|hes_", text) else "não",
            "politica_especifica_do_bloco": "prefer_sum_variant (desempate SUM)" if "prefer_sum_variant" in text else "",
        })
    for b in BLOCKS:
        builder_rows.append({"arquivo": f"data/seed/{b} (seed)", "usa_reference_resolver_central": "gerado por builder" if (ROOT / "tools" / f"{b}_seed_builder.py").exists() else "seed versionado sem builder",
                             "passa_consumer_scope": "", "cria_referencias_@": f"@linha={summary[f'seed:{b}']['refs_@linha']} @grupo={summary[f'seed:{b}']['refs_@grupo']}",
                             "gera_nomes_espacializados": str(summary[f"seed:{b}"]["nomes_espacializados"]), "resolucao_manual_de_escopo": "",
                             "tratamento_especifico_A41": "", "politica_especifica_do_bloco": f"nomes em >1 escopo: {summary[f'seed:{b}']['nomes_em_>1_escopo']}"})
    write_csv("builder_seed_matrix.csv", builder_rows)
    return summary


# ============================================================
# Q5 — chaves de armazenamento (inspeção de fonte + sondas S*)
# ============================================================


def storage_matrix():
    rows = [
        ("VariableDefinitionRegistry._definitions", "variable_definition_id", "1 ID = 1 definição = 1 escopo declarado", "S04", VariableDefinitionRegistry.add),
        ("VariableInstanceRegistry._instances", "variable_instance_id = ID@scope_value", "instância por escopo concreto", "S06", VariableInstance.create),
        ("ParameterDefinitionRegistry._definitions", "(id, version, scope_type, scope_value)", "mesmo ID pode ter N escopos (assimetria com variáveis)", "S05", ParameterDefinitionRegistry.add),
        ("CalculationContext._scoped_variables", "CalculationKey(entity_id, scope_type, scope_value, period_id)", "L4 e L5 distintos; período distinto", "S01/S02", CalculationContext.set_variable_value),
        ("CalculationContext._variables (legado)", "entity_id apenas", "sem escopo; usado como fallback de referência IMPLÍCITA", "S03/R05", CalculationContext.set_variable),
        ("ForecastEngine producers", "VAR@Lx (linha), VAR@grupo + VAR (linha_grupo), VAR (demais)", "produtores por instância", "—", None),
        ("reference_resolver.build_name_index", "name -> lista de TODAS as definições", "sem colisão; desambiguação por frequência+escopo", "S07", reference_resolver.build_name_index),
    ]
    from app.engine.forecast_engine import ForecastEngine
    out = []
    for structure, key, meaning, probes, symbol in rows:
        out.append({"estrutura": structure, "chave_efetiva": key, "consequencia": meaning, "sondas": probes,
                    "codigo": where(symbol) if symbol else where(ForecastEngine._build_instance_variable_producers)})
    write_csv("storage_identity_matrix.csv", out)


def main():
    EVIDENCE.mkdir(exist_ok=True)
    scope_rows, enums = q1_scope_matrix()
    q2_q3_q4_probes()
    storage_matrix()
    summary = q6_q7_q8()
    ref_rows = [r for r in RESULTS if r["layer"] in ("nomes", "parser", "runtime", "grupos")]
    write_csv("reference_resolution_matrix.csv", ref_rows)
    (HERE / "negative_tests_results.json").write_text(json.dumps({"results": RESULTS}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    enums_equal = enums["variable_seed_validator"] == enums["parameter_seed_validator"] == enums["equation_seed_validator"]
    contract = {
        "scope_types": {"validators": enums["variable_seed_validator"][0], "ScopeResolver": enums["ScopeResolver"][0], "validators_enums_identicos": enums_equal},
        "scope_values": {"validators": enums["variable_seed_validator"][1], "group_members": enums["ScopeResolver.GROUP_MEMBERS"]},
        "identity": {
            "workbook_builder_layer": "name + frequency + (scope_type, scope_value) — reference_resolver.resolve_reference",
            "runtime_definition": "variable_definition_id (1 escopo declarado por ID)",
            "runtime_value": "CalculationKey(entity_id, scope_type, scope_value, period_id)",
            "seed_validation": "variable_id único = ERRO; assinatura (name, unit, variable_type, frequency, scope) duplicada = apenas WARNING",
        },
        "reference_syntax": {"runtime_dsl": "ID@Lx | ID@<grupo registrado>; NOMES rejeitados", "builder_layer": "name@Lx | name@<grupo>, traduzido para ID@escopo"},
        "seed_summary": summary,
        "probes": Counter(r["status"] for r in RESULTS),
    }
    (HERE / "architecture_contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    for r in RESULTS:
        print(f"{r['status']:10} {r['id']} [{r['layer']}] {r['description']} -> {r['observed'][:90]}")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("enums dos 3 validadores idênticos:", enums_equal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
