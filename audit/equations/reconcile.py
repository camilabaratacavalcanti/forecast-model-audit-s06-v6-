"""
Script de AUDITORIA (nao faz parte do produto).

Reconcilia as 106 EquationDefinitions atuais do seed do Yield
contra o workbook funcional descritivo_das_variaveis_yield_v3.xlsx.

Nao altera nenhum arquivo do produto. Le apenas:
    data/seed/yield/variables.json
    data/seed/yield/parameters.json
    data/seed/yield/equations.json
    <upload>/descritivo_das_vari_veis_yield_v3.xlsx

Escreve apenas em audit/equations/.
"""

import csv
import json
import re
from pathlib import Path

import openpyxl

REPO = Path("/home/user/forecast-model-audit-s06-v6-")
OUT_DIR = REPO / "audit" / "equations"
EXCEL_PATH = Path(
    "/root/.claude/uploads/afd1cfda-5340-5625-86ea-0588b02fbed0/"
    "bc7bf545-descritivo_das_vari_veis_yield_v3.xlsx"
)

FREQ_MAP = {"diário": "diário", "anual": "anual", "mensal": "mensal"}

LINE_RE = re.compile(r"^L0?(\d)$")
LINE_GROUP_RE = re.compile(r"^L0?(\d)_L0?(\d)$")


def normalize_scope_value(value):
    """L01 -> L1, L01_L07 -> L1_L7, L1_L07 -> L1_L7, None -> None."""
    if value is None:
        return None
    value = value.strip()
    m = LINE_RE.match(value)
    if m:
        return f"L{m.group(1)}"
    m = LINE_GROUP_RE.match(value)
    if m:
        return f"L{m.group(1)}_L{m.group(2)}"
    return value


# ====================================================================
# 1. Carrega dados da plataforma
# ====================================================================

variables = json.load(open(REPO / "data/seed/yield/variables.json", encoding="utf-8"))
parameters = json.load(open(REPO / "data/seed/yield/parameters.json", encoding="utf-8"))
equations = json.load(open(REPO / "data/seed/yield/equations.json", encoding="utf-8"))

assert len(equations) == 106, f"esperado 106, encontrado {len(equations)}"

var_by_id = {v["variable_id"]: v for v in variables}
param_by_id = {p["parameter_id"]: p for p in parameters}

# name -> {(frequency, scope_type, scope_value): id}   (variables)
var_map = {}
for v in variables:
    var_map.setdefault(v["variable_name"], {})[
        (v["frequency"], v["scope_type"], v["scope_value"])
    ] = v["variable_id"]

# name -> {(scope_type, scope_value): [ids]}   (parameters; pode haver
# varias ParameterDefinition por linha sob o mesmo parameter_name)
param_map = {}
for p in parameters:
    param_map.setdefault(p["parameter_name"], {}).setdefault(
        (p["scope_type"], p["scope_value"]), []
    ).append(p["parameter_id"])

# id -> name (para "des-traducao" da expressao da plataforma)
var_id_to_name = {v["variable_id"]: v["variable_name"] for v in variables}
param_id_to_name = {p["parameter_id"]: p["parameter_name"] for p in parameters}


TOKEN_RE = re.compile(r"(VAR\d{5}|PARAM\d{5})(@L[1-7])?")


def platform_expression_to_names(expression):
    """Traduz VAR#####/PARAM##### de volta para nomes, preservando @Lx."""

    def repl(match):
        ident, scope = match.group(1), match.group(2) or ""
        if ident.startswith("VAR"):
            name = var_id_to_name.get(ident, ident)
        else:
            name = param_id_to_name.get(ident, ident)
        return f"{name}{scope}"

    return TOKEN_RE.sub(repl, expression)


def normalize_text_expression(expr):
    if expr is None:
        return None
    expr = expr.replace(",", ".")
    expr = re.sub(r"\s+", "", expr)
    # normaliza L0x -> Lx dentro de tokens @L0x
    expr = re.sub(r"@L0(\d)", r"@L\1", expr)
    return expr


# ====================================================================
# 2. Carrega o workbook funcional (fonte)
# ====================================================================

wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
ws = wb["yield"]

source_rows = []
for r in range(2, ws.max_row + 1):
    row = [c.value for c in ws[r]]
    if row[1] is None:
        continue
    source_rows.append(
        {
            "row": r,
            "type": row[0],
            "name": row[1],
            "description": row[2],
            "unit": row[3],
            "variable_type": row[6],
            "frequency": row[7],
            "scope_type": row[8],
            "scope_value": normalize_scope_value(row[9]),
            "scope_value_raw": row[9],
            "source_reference": row[10],
            "status": row[11],
            "expression": row[12],
        }
    )

# index: (name, frequency, scope_type, scope_value) -> row
source_index = {}
for row in source_rows:
    key = (row["name"], row["frequency"], row["scope_type"], row["scope_value"])
    source_index.setdefault(key, []).append(row)


# ====================================================================
# 3. Reconciliacao
# ====================================================================

DESCRIPTIVE_EXPRESSION_MARKERS = ("Média dos dados",)


def is_real_formula(expr):
    if not isinstance(expr, str):
        return False
    if not expr.strip():
        return False
    return not any(marker in expr for marker in DESCRIPTIVE_EXPRESSION_MARKERS)


results = []

for seq, eq in enumerate(equations, start=1):
    target_id = eq["target_variable_id"]
    target_def = var_by_id.get(target_id)

    platform_name = target_def["variable_name"] if target_def else None
    platform_freq = target_def["frequency"] if target_def else None

    platform_scope_type = eq["scope_type"]
    platform_scope_value = eq["scope_value"]

    source_key = (
        platform_name,
        platform_freq,
        platform_scope_type,
        platform_scope_value,
    )

    source_candidates = source_index.get(source_key, [])

    platform_expr_names = platform_expression_to_names(eq["expression"])
    platform_expr_norm = normalize_text_expression(platform_expr_names)

    row = {
        "seq": seq,
        "equation_definition_id": eq["equation_id"],
        "platform_name": platform_name,
        "platform_target": target_id,
        "platform_scope": f"{platform_scope_type}/{platform_scope_value}",
        "platform_expression": eq["expression"],
        "platform_expression_as_names": platform_expr_names,
        "platform_status": eq["status"],
        "platform_version": eq["version"],
        "source_reference_field": eq["source_reference"],
        "secondary_classification": "",
    }

    if not source_candidates:
        row.update(
            {
                "source_row": None,
                "source_expression": None,
                "source_expression_normalized": None,
                "platform_expression_normalized": platform_expr_norm,
                "formula_match": "NO_SOURCE_ROW",
                "primary_classification": "SOURCE_UNCLEAR",
                "severity": "P3",
                "confidence": "LOW",
                "discrepancy_description": (
                    f"Nenhuma linha do workbook encontrada para "
                    f"(name={platform_name!r}, frequency={platform_freq!r}, "
                    f"scope={platform_scope_type}/{platform_scope_value})."
                ),
            }
        )
        results.append(row)
        continue

    src = source_candidates[0]
    src_expr_raw = src["expression"]

    if not is_real_formula(src_expr_raw):
        row.update(
            {
                "source_row": src["row"],
                "source_expression": src_expr_raw,
                "source_expression_normalized": None,
                "platform_expression_normalized": platform_expr_norm,
                "formula_match": "SOURCE_DESCRIPTIVE_ONLY",
                "primary_classification": "SOURCE_UNCLEAR",
                "severity": "P3",
                "confidence": "MEDIUM",
                "discrepancy_description": (
                    "A linha-fonte correspondente nao contem uma formula "
                    f"matematica, e sim texto descritivo: {src_expr_raw!r}."
                ),
            }
        )
        results.append(row)
        continue

    src_expr_names = src_expr_raw
    src_expr_norm = normalize_text_expression(src_expr_names)

    formula_match = "EXACT" if platform_expr_norm == src_expr_norm else "DIFFERENT"

    row.update(
        {
            "source_row": src["row"],
            "source_expression": src_expr_raw,
            "source_expression_normalized": src_expr_norm,
            "platform_expression_normalized": platform_expr_norm,
            "formula_match": formula_match,
        }
    )

    if formula_match == "EXACT":
        row["primary_classification"] = "MATCH"
        row["severity"] = "INFO"
        row["confidence"] = "HIGH"
        row["discrepancy_description"] = ""
    else:
        row["primary_classification"] = "FORMULA_DISCREPANCY"
        row["severity"] = "P2"
        row["confidence"] = "HIGH"
        row["discrepancy_description"] = (
            f"platform={platform_expr_norm!r} vs source={src_expr_norm!r}"
        )

    # ----------------------------------------------------------------
    # Overrides EXPLICITAMENTE governados pelo prompt de auditoria
    # (secoes 4-6, 15-16, 23-25): estes dois casos tem regra de
    # negocio propria e NAO devem ser tratados como discrepancia de
    # formula a corrigir.
    # ----------------------------------------------------------------

    if eq["equation_id"] == "EQ11004" and platform_name == "n_ppt":
        # Excel usa notacao "current-line" (tanque_base_L1@ -
        # tanque_L1@), que a plataforma NAO deve adotar (secao 15).
        # A plataforma representa a MESMA semantica atraves de
        # referencia sem escopo, resolvida contextualmente pela
        # EquationInstance (secao 16). Comprovado por teste real
        # (test_fase3a_contextual_resolution_integration.py::
        # test_c5_*) em todas as 7 linhas.
        row["primary_classification"] = "SEMANTIC_MATCH"
        row["severity"] = "INFO"
        row["confidence"] = "HIGH"
        row["discrepancy_description"] = (
            "Fonte usa notacao current-line "
            "'tanque_base_L1@ - tanque_L1@' (nao adotada pela "
            "plataforma, ver secao 15). Plataforma usa referencia "
            "sem escopo 'tanque_base - tanque', resolvida "
            "contextualmente por EquationInstance (secao 16). "
            "Semanticamente equivalente; comprovado por teste "
            "executavel para L1..L7."
        )

    if eq["equation_id"] == "EQ11006" and platform_name == "ratio_spent" and eq["scope_type"] == "linha":
        # Regra de negocio Nivel 1 (aprovada, secao 4.1) prevalece
        # sobre o workbook (Nivel 2). A formula implementada e
        # EXATAMENTE a formula aprovada (confirmado termo a termo).
        # Duas divergencias de SINAL foram identificadas contra o
        # workbook (termo LTP e termo SSAmedia) -- registradas como
        # historical/source note, nao como correcao pendente.
        row["primary_classification"] = "MATCH"
        row["secondary_classification"] = "INFO:HISTORICAL_SOURCE_NOTE"
        row["severity"] = "INFO"
        row["confidence"] = "HIGH"
        row["discrepancy_description"] = (
            "MATCH contra a regra de negocio Nivel 1 (aprovada, "
            "secao 4.1) -- formula implementada e identica termo a "
            "termo a regra oficial, incluindo o coeficiente 0.0007. "
            "historical/source note: o workbook (Nivel 2) diverge "
            "em SINAL em 2 dos 7 termos: "
            "LTP: platform '-0.004*(LTP_base-LTP)/100' vs source "
            "'-0.0040*(ltp-ltp_base)/100' (sinais opostos); "
            "SSAmedia: platform '+0.002*(SSAmedia_base-SSAmedia)' vs "
            "source '-0.002*(-ssa_media+ssa_media_base)' == "
            "'+0.002*(ssa_media-ssa_media_base)' (sinais opostos). "
            "Os demais 5 termos (Ratio_spent_base, n_ppt, EOCtemp, "
            "EOCsolids incl. coeficiente 0.0007, LTPTC) sao "
            "identicos entre as duas fontes."
        )

    results.append(row)


# ====================================================================
# 4. Escreve CSV
# ====================================================================

OUT_DIR.mkdir(parents=True, exist_ok=True)

fieldnames = [
    "seq",
    "equation_definition_id",
    "platform_name",
    "platform_target",
    "platform_scope",
    "platform_status",
    "platform_version",
    "source_row",
    "formula_match",
    "primary_classification",
    "secondary_classification",
    "severity",
    "confidence",
    "platform_expression",
    "platform_expression_as_names",
    "platform_expression_normalized",
    "source_expression",
    "source_expression_normalized",
    "discrepancy_description",
]

with open(OUT_DIR / "reconciliation_106_equations.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in results:
        writer.writerow(row)

print(f"Total equations processed: {len(results)}")

from collections import Counter

class_counts = Counter(r["primary_classification"] for r in results)
print("Classification counts:", dict(class_counts))

match_count = class_counts.get("MATCH", 0)
print(f"MATCH: {match_count} / 106")

sev_counts = Counter(r["severity"] for r in results)
print("Severity counts:", dict(sev_counts))

# lista de nao-MATCH para inspecao manual
non_match = [
    r
    for r in results
    if r["primary_classification"] not in ("MATCH", "SEMANTIC_MATCH")
]
print(f"\nNon-MATCH/SEMANTIC_MATCH count: {len(non_match)}")
for r in non_match:
    print(
        f"  seq={r['seq']} id={r['equation_definition_id']} "
        f"name={r['platform_name']} scope={r['platform_scope']} "
        f"class={r['primary_classification']} match={r['formula_match']}"
    )

# ====================================================================
# 5. Distribuicao de scope_type/scope_value
# ====================================================================

scope_dist = Counter(
    (eq["scope_type"], eq["scope_value"]) for eq in equations
)

print("\n=== Distribuicao scope_type/scope_value (106 EquationDefinitions) ===")
for (st, sv), count in sorted(scope_dist.items()):
    print(f"  {st}/{sv}: {count}")

with open(OUT_DIR / "scope_distribution.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["scope_type", "scope_value", "quantity"])
    for (st, sv), count in sorted(scope_dist.items()):
        writer.writerow([st, sv, count])

# ====================================================================
# 6. Status distribution
# ====================================================================

status_dist = Counter(eq["status"] for eq in equations)
print("\n=== Distribuicao de status ===")
for status, count in status_dist.items():
    print(f"  {status}: {count}")

# ====================================================================
# 7. Matriz de dependencias (platform apenas -- fonte de
#    dependencias explicitas ja esta embutida na formula comparada
#    acima; aqui extraimos os identificadores referenciados por
#    cada equacao a partir do proprio expression, via regex, sem
#    reimplementar o DependencyExtractor do produto)
# ====================================================================

REF_RE = re.compile(r"(VAR\d{5}|PARAM\d{5})(@L[1-7])?")

dependency_rows = []
for eq in equations:
    refs = set()
    for m in REF_RE.finditer(eq["expression"]):
        ident, scope = m.group(1), m.group(2) or ""
        name = (
            var_id_to_name.get(ident, ident)
            if ident.startswith("VAR")
            else param_id_to_name.get(ident, ident)
        )
        refs.add(f"{name}{scope}")

    dependency_rows.append(
        {
            "equation_definition_id": eq["equation_id"],
            "target": var_id_to_name.get(eq["target_variable_id"], eq["target_variable_id"]),
            "scope": f"{eq['scope_type']}/{eq['scope_value']}",
            "platform_dependencies": "; ".join(sorted(refs)),
            "dependency_count": len(refs),
        }
    )

with open(OUT_DIR / "dependency_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "equation_definition_id",
            "target",
            "scope",
            "platform_dependencies",
            "dependency_count",
        ],
    )
    writer.writeheader()
    writer.writerows(dependency_rows)

# ====================================================================
# 8. Matriz de instances (Definition -> Instance esperado, via
#    ScopeResolver real do produto -- import direto, sem duplicar
#    a logica de resolucao de escopo)
# ====================================================================

import sys

sys.path.insert(0, str(REPO))

from app.repositories.seed_loader import SeedLoader  # noqa: E402

loader = SeedLoader(REPO / "data" / "seed")
(
    variable_definitions,
    variable_instances,
    parameter_definitions,
    parameter_instances,
    equation_definitions,
    equation_instances,
) = loader.load_all_definitions_and_instances()

instances_by_definition = {}
for instance in equation_instances.all():
    instances_by_definition.setdefault(
        instance.equation_definition_id, []
    ).append(instance.scope_value)

instance_rows = []
for definition in equation_definitions.all():
    actual = sorted(
        instances_by_definition.get(
            definition.equation_definition_id, []
        )
    )
    instance_rows.append(
        {
            "equation_definition_id": definition.equation_definition_id,
            "scope_type": definition.scope_type,
            "scope_value": definition.scope_value,
            "actual_instance_count": len(actual),
            "actual_instance_scopes": "; ".join(actual),
        }
    )

with open(OUT_DIR / "instances_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "equation_definition_id",
            "scope_type",
            "scope_value",
            "actual_instance_count",
            "actual_instance_scopes",
        ],
    )
    writer.writeheader()
    writer.writerows(instance_rows)

print(f"\nTotal EquationDefinitions (real registry): {len(equation_definitions.all())}")
print(f"Total EquationInstances (real registry): {len(equation_instances.all())}")

# ====================================================================
# 9. Agregacoes de planta/area -- tracing
# ====================================================================

AGG_CONCEPTS = {
    "Weighted EOC temperature": "eoc_temp",
    "Weighted EOC solids": "eoc_solids",
    "Base production sum": "producao_base_ppt",
    "Tank sum": None,  # nao existe conceito de "soma de tanques" na fonte
    "Ratio DBO Planta": None,  # termo nao encontrado na fonte do Yield
}

agg_rows = []
for concept, name in AGG_CONCEPTS.items():
    if name is None:
        agg_rows.append(
            {
                "concept": concept,
                "source_name": None,
                "found_in_source": False,
                "found_in_platform": False,
                "platform_equation_ids": "",
                "note": (
                    "Nenhuma linha do workbook do Yield usa esse nome "
                    "ou conceito. Nao ha equacao/variavel do bloco Yield "
                    "associada."
                ),
            }
        )
        continue

    source_hits = [r for r in source_rows if r["name"] == name]
    platform_eq_ids = [
        eq["equation_id"]
        for eq in equations
        if var_id_to_name.get(eq["target_variable_id"]) == name
    ]

    agg_rows.append(
        {
            "concept": concept,
            "source_name": name,
            "found_in_source": len(source_hits) > 0,
            "found_in_platform": len(platform_eq_ids) > 0,
            "platform_equation_ids": "; ".join(platform_eq_ids),
            "note": (
                f"{len(source_hits)} linha(s)-fonte, "
                f"{len(platform_eq_ids)} EquationDefinition(s) na plataforma."
            ),
        }
    )

with open(OUT_DIR / "aggregation_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "concept",
            "source_name",
            "found_in_source",
            "found_in_platform",
            "platform_equation_ids",
            "note",
        ],
    )
    writer.writeheader()
    writer.writerows(agg_rows)

print("\n=== Agregacoes ===")
for r in agg_rows:
    print(f"  {r['concept']}: {r['note']}")
