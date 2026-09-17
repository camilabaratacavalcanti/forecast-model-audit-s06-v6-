"""
AUDITORIA (nao faz parte do produto).

Executa experimentos reais, usando componentes REAIS da plataforma
(SeedLoader, Definition/Instance Registries, ScopeResolver,
DependencyGraph, DependencyResolver, ExpressionParser/Evaluator,
EquationEngine, ForecastEngine), para determinar se o Yield e
executavel ponta a ponta com as 106 EquationDefinitions atuais.

Nao altera nenhum arquivo de produto. Nao cria uma mini-engine
paralela -- toda a execucao passa pelos componentes reais do
pacote `app`.
"""

import json
import sys
import time
from pathlib import Path

REPO = Path("/home/user/forecast-model-audit-s06-v6-")
sys.path.insert(0, str(REPO))

from app.repositories.seed_loader import SeedLoader
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_resolver import DependencyResolver
from app.engine.equation_engine import EquationEngine
from app.engine.expression_parser import ExpressionParser
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.exceptions import (
    DependencyCycleError,
    VariableNotFoundError,
    ParameterNotFoundError,
)
from app.domain.equations.models import EquationDefinition, EquationInstance

OUT_DIR = REPO / "audit" / "yield_e2e_readiness"

LINES = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

results = {}


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ====================================================================
# 1. Carregamento real: Seed -> Definitions -> Instances
# ====================================================================

section("1. SEED LOADER REAL -- Definitions e Instances")

loader = SeedLoader(REPO / "data" / "seed")

(
    variable_definitions,
    variable_instances,
    parameter_definitions,
    parameter_instances,
    equation_definitions,
    equation_instances,
) = loader.load_all_definitions_and_instances()

n_eq_defs = len(equation_definitions.all())
n_eq_instances = len(equation_instances.all())
n_var_defs = len(variable_definitions.all())
n_var_instances = len(variable_instances.all())
n_param_defs = len(parameter_definitions.all())
n_param_instances = len(parameter_instances.all())

print(f"VariableDefinitions:  {n_var_defs}")
print(f"VariableInstances:    {n_var_instances}")
print(f"ParameterDefinitions: {n_param_defs}")
print(f"ParameterInstances:   {n_param_instances}")
print(f"EquationDefinitions:  {n_eq_defs}")
print(f"EquationInstances:    {n_eq_instances}")

assert n_eq_defs == 106, f"esperado 106 EquationDefinitions, obtido {n_eq_defs}"

results["equation_definitions_count"] = n_eq_defs
results["equation_instances_count"] = n_eq_instances
results["variable_definitions_count"] = n_var_defs
results["variable_instances_count"] = n_var_instances
results["parameter_definitions_count"] = n_param_defs
results["parameter_instances_count"] = n_param_instances

status_dist = {}
for d in equation_definitions.all():
    status_dist[d.status] = status_dist.get(d.status, 0) + 1
print(f"Status distribution: {status_dist}")
results["status_distribution"] = status_dist


# ====================================================================
# 2. DependencyGraph real construido a partir das 106 definitions
# ====================================================================

section("2. DEPENDENCY GRAPH REAL -- 106 EquationDefinitions / 166 Instances")

engine = ForecastEngine()
extractor = DependencyExtractor()

definitions_by_id_and_version = {
    (d.equation_definition_id, d.version): d
    for d in equation_definitions.all()
}

all_instances = []
for definition in equation_definitions.all():
    all_instances.extend(engine.materialize_equation(definition))

assert len(all_instances) == n_eq_instances

variable_producers = engine._build_instance_variable_producers(all_instances)

graph = DependencyGraph()
for instance in all_instances:
    definition = definitions_by_id_and_version[
        (instance.equation_definition_id, instance.version)
    ]
    graph.add_instance(
        instance=instance,
        definition=definition,
        variable_producers=variable_producers,
        extractor=extractor,
    )

graph_dict = graph.as_dict()
n_nodes = len(graph_dict)
n_edges = sum(len(deps) for deps in graph_dict.values())

print(f"Nodes: {n_nodes}")
print(f"Edges: {n_edges}")

results["graph_nodes"] = n_nodes
results["graph_edges"] = n_edges

# ciclos?
resolver = DependencyResolver()
try:
    execution_order = resolver.resolve(graph)
    has_cycle = False
    n_cycles = 0
    print(f"Topological order resolved: {len(execution_order)} nodes")
except DependencyCycleError as exc:
    has_cycle = True
    n_cycles = 1
    execution_order = None
    print(f"CYCLE DETECTED: {exc}")

results["has_cycle"] = has_cycle
results["cycles_found"] = n_cycles
results["execution_order_length"] = len(execution_order) if execution_order else 0

# determinismo: resolver duas vezes e comparar
if execution_order:
    execution_order_2 = resolver.resolve(graph)
    deterministic = execution_order == execution_order_2
    print(f"Deterministic across repeated resolve(): {deterministic}")
    results["deterministic_order"] = deterministic

# nos-produtor (instances) vs nos-referenciados sem producer (leaf/input)
instance_node_ids = {
    engine._build_instance_node_id(i) for i in all_instances
}
leaf_nodes = [n for n in graph_dict if n not in instance_node_ids]
print(f"Equation-instance nodes: {len(instance_node_ids)}")
print(f"Leaf/unresolved-producer nodes referenced in graph: {len(leaf_nodes)}")
print(f"  sample: {leaf_nodes[:10]}")
results["leaf_nodes_count"] = len(leaf_nodes)
results["leaf_nodes_sample"] = leaf_nodes[:20]

# produtores ambiguos? (_build_instance_variable_producers ja lanca
# DuplicateVariableProducerError se houvesse -- nao lancou, entao 0)
results["duplicate_producers"] = 0
print("Duplicate/ambiguous producers: 0 (nenhuma excecao levantada por "
      "_build_instance_variable_producers)")

# dependencias de variavel vs parametro (contagem via DependencyExtractor)
var_dep_count = 0
param_dep_count = 0
cross_scope_count = 0
for definition in equation_definitions.all():
    deps = extractor.extract(definition.expression)
    var_dep_count += len(deps.variables)
    param_dep_count += len(deps.parameters)
    for ref in deps.variables | deps.parameters:
        if "@" in ref:
            cross_scope_count += 1

print(f"Variable dependency references (across 106 definitions): {var_dep_count}")
print(f"Parameter dependency references (across 106 definitions): {param_dep_count}")
print(f"References with explicit @Lx scope: {cross_scope_count}")
results["variable_dependency_refs"] = var_dep_count
results["parameter_dependency_refs"] = param_dep_count
results["explicit_scope_refs"] = cross_scope_count


# ====================================================================
# 3. Cenario critico de escopo -- L2/L3 explicitos em instance L5
# ====================================================================

section("3. SCOPE RESOLUTION -- explicit / implicit / mixed / PARAM / linha_grupo")

scope_results = {}


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    scope_results[name] = status
    return condition


# Caso A/B -- duas referencias explicitas em instance L5
definition = EquationDefinition(
    "EQ_AUDIT_A", "VAR_AUDIT_A", 1, "linha", "L1_L7",
    "VAR10001@L2 + VAR10001@L3", "AUDIT", "PUBLISHED",
)
instance_l5 = EquationInstance.create(definition, "linha", "L5")

ctx = CalculationContext()
ctx.set_variable_value("VAR10001", 20, "linha", "L2")
ctx.set_variable_value("VAR10001", 30, "linha", "L3")
ctx.set_variable_value("VAR10001", 100, "linha", "L5")

eq_engine = EquationEngine()
result_ab = eq_engine.calculate_instance(instance_l5, definition, ctx)
check("Caso A/B: VAR@L2 + VAR@L3 em instance L5 == 50 (nao 200)", result_ab == 50)

g = DependencyGraph()
g.add_instance(
    instance_l5, definition,
    variable_producers={"VAR10001@L2": "PROD_L2", "VAR10001@L3": "PROD_L3", "VAR10001@L5": "PROD_L5"},
    extractor=extractor,
)
deps_ab = g.get_dependencies("EQ_AUDIT_A@linha:L5")
check(
    "Caso A/B (graph): dependencies == {PROD_L2, PROD_L3}, sem PROD_L5",
    deps_ab == {"PROD_L2@linha:L2", "PROD_L3@linha:L3"},
)

# Caso C -- implicita
definition_c = EquationDefinition(
    "EQ_AUDIT_C", "VAR_AUDIT_C", 1, "linha", "L1_L7", "VAR10001", "AUDIT", "PUBLISHED",
)
instance_c = EquationInstance.create(definition_c, "linha", "L5")
result_c = eq_engine.calculate_instance(instance_c, definition_c, ctx)
check("Caso C: VAR implicita em instance L5 == 100 (usa L5)", result_c == 100)

# Caso D -- mistura
definition_d = EquationDefinition(
    "EQ_AUDIT_D", "VAR_AUDIT_D", 1, "linha", "L1_L7", "VAR10001@L2 + VAR10001", "AUDIT", "PUBLISHED",
)
instance_d = EquationInstance.create(definition_d, "linha", "L5")
result_d = eq_engine.calculate_instance(instance_d, definition_d, ctx)
check("Caso D: VAR@L2 + VAR (implicita) em L5 == 20 + 100 == 120", result_d == 120)

# Caso E -- parametros
definition_e = EquationDefinition(
    "EQ_AUDIT_E", "VAR_AUDIT_E", 1, "linha", "L1_L7", "PARAM10001@L2 + PARAM10001@L3", "AUDIT", "PUBLISHED",
)
instance_e = EquationInstance.create(definition_e, "linha", "L5")
ctx.set_parameter_value("PARAM10001", 5, "linha", "L2")
ctx.set_parameter_value("PARAM10001", 7, "linha", "L3")
ctx.set_parameter_value("PARAM10001", 999, "linha", "L5")
result_e = eq_engine.calculate_instance(instance_e, definition_e, ctx)
check("Caso E: PARAM@L2 + PARAM@L3 em L5 == 12 (nao 1998)", result_e == 12)

g_e = DependencyGraph()
g_e.add_instance(
    instance_e, definition_e,
    variable_producers={"PARAM10001@L2": "PPROD_L2", "PARAM10001@L3": "PPROD_L3", "PARAM10001@L5": "PPROD_L5"},
    extractor=extractor,
)
deps_e = g_e.get_dependencies("EQ_AUDIT_E@linha:L5")
check(
    "Caso E (graph): PARAM@Lx preserva escopo explicito no grafo",
    deps_e == {"PPROD_L2@linha:L2", "PPROD_L3@linha:L3"},
)

# Caso F -- linha_grupo (real, usando equacoes reais do seed: EQ11011 yield@L1_L3)
real_group_def = next(
    d for d in equation_definitions.all()
    if d.equation_definition_id == "EQ11011"
)
print(f"  Real linha_grupo definition used: {real_group_def.equation_definition_id} "
      f"({real_group_def.scope_type}/{real_group_def.scope_value})")
print(f"  expression: {real_group_def.expression}")
check(
    "Caso F: EQ11011 (yield@L1_L3) usa referencias @L1/@L2/@L3 explicitas",
    "@L1" in real_group_def.expression and "@L2" in real_group_def.expression and "@L3" in real_group_def.expression,
)

results["scope_resolution_cases"] = scope_results


# ====================================================================
# 4. Cadeia real E2E: parameter -> variable -> equation -> equation -> equation
# ====================================================================

section("4. CADEIA REAL E2E -- tanque_base/tanque -> n_ppt -> ratio_spent -> yield")

chain_context = CalculationContext()

# --- inputs reais do seed (tanque_base: 7 ParameterDefinition reais) ---
for instance in parameter_instances.all():
    chain_context.set_parameter_instance_value(instance, instance.value)

# --- SYNTHETIC TEST VALUE: nao existe no seed nenhum valor diario real
# de "tanque" (entrada operacional, populada em runtime real a partir de
# leituras diarias -- nao ha tal leitura disponivel nesta auditoria).
# Usado APENAS para provar que a infraestrutura resolve a cadeia; NAO
# representa um resultado funcional do Yield.
SYNTHETIC_TANQUE = 12.0
tanque_def = next(v for v in variable_definitions.all() if v.variable_name == "tanque")
for line in LINES:
    chain_context.set_variable_value(
        tanque_def.variable_definition_id, SYNTHETIC_TANQUE, "linha", line,
    )

# demais entradas diarias e anuais necessarias ao restante da cadeia ate "yield"
# (mesmos valores SYNTHETIC usados na Fase 3A / auditoria de reconciliacao)
SYNTHETIC_DAILY = {
    "lth": 500.0, "oee": 0.9, "ltp_lth": 1.1, "ltp_a_c": 1.5,
    "sl_solids": 140.0, "ssa_sf": 3.0, "ssa_sg": 1.5,
    "eoc_temp": 74.0, "eoc_solids": 250.0,
}
SYNTHETIC_ANNUAL = {
    "lth_base": 500.0, "oee_base": 0.9, "ltp_lth_base": 1.1,
    "ltp_a_c_base": 1.5, "sl_solids_base": 140.0, "ratio_spent_base": 0.5,
    "ssa_sf_base": 3.0, "ssa_sg_base": 1.5, "n_ppt_base": 10.0,
    "eoc_temp_base": 74.0, "eoc_solids_base": 250.0,
}

definitions_by_name_scope = {}
for d in variable_definitions.all():
    definitions_by_name_scope.setdefault(d.variable_name, {})[
        (d.frequency, d.scope_type, d.scope_value)
    ] = d

for name, value in SYNTHETIC_DAILY.items():
    d = definitions_by_name_scope[name][("diário", "linha", "L1_L7")]
    for line in LINES:
        chain_context.set_variable_value(d.variable_definition_id, value, "linha", line)

for name, value in SYNTHETIC_ANNUAL.items():
    d = definitions_by_name_scope[name][("anual", "linha", "L1_L7")]
    for line in LINES:
        chain_context.set_variable_value(d.variable_definition_id, value, "linha", line)

print("Inputs registrados:")
print(f"  ParameterInstances reais do seed: {len(parameter_instances.all())} "
      "(inclui tanque_base, ltp_tc, ltp_tc_base -- valores reais do seed)")
print(f"  tanque (VariableInstance): SYNTHETIC TEST VALUE = {SYNTHETIC_TANQUE} "
      "em todas as 7 linhas (nao existe leitura diaria real no seed)")
print(f"  demais entradas diarias/anuais: SYNTHETIC TEST VALUE (mesmos valores "
      "usados na auditoria de reconciliacao anterior)")

chain_start = time.time()
try:
    full_results = engine.calculate_from_definition_registry(
        equation_definition_registry=equation_definitions,
        calculation_context=chain_context,
    )
    chain_status = "PASS"
    chain_error = None
except (VariableNotFoundError, ParameterNotFoundError) as exc:
    full_results = {}
    chain_status = "FAIL"
    chain_error = str(exc)
chain_elapsed = time.time() - chain_start

print(f"\nFull 106-EquationDefinition execution: {chain_status} "
      f"({len(full_results)} results, {chain_elapsed*1000:.1f}ms)")
if chain_error:
    print(f"  ERROR: {chain_error}")

results["full_execution_status"] = chain_status
results["full_execution_result_count"] = len(full_results)
results["full_execution_expected_count"] = n_eq_instances
results["full_execution_error"] = chain_error

# cadeia especifica: tanque_base/tanque -> n_ppt -> ratio_spent -> yield, em L4
if chain_status == "PASS":
    n_ppt_l4 = chain_context.get_variable_value("VAR11012", "linha", "L4")
    ratio_spent_l4 = chain_context.get_variable_value("VAR11008", "linha", "L4")
    yield_l4 = chain_context.get_variable_value("VAR11001", "linha", "L4")

    print("\nCadeia real (linha L4):")
    print(f"  PARAM11003 (tanque_base@L4, real do seed)  = 18")
    print(f"  VAR11239   (tanque@L4, SYNTHETIC)           = {SYNTHETIC_TANQUE}")
    print(f"  -> EQ11004 n_ppt@L4       = {n_ppt_l4}  (esperado 18 - 12 = 6)")
    print(f"  -> EQ11006 ratio_spent@L4 = {ratio_spent_l4}")
    print(f"  -> EQ11001 yield@L4       = {yield_l4}")

    assert n_ppt_l4 == 6.0

    results["chain_n_ppt_L4"] = n_ppt_l4
    results["chain_ratio_spent_L4"] = ratio_spent_l4
    results["chain_yield_L4"] = yield_l4
    results["chain_status"] = "PASS"
else:
    results["chain_status"] = "FAIL"


# ====================================================================
# 5. Outputs finais -- rastreamento
# ====================================================================

section("5. OUTPUTS -- classificacao INPUT / INTERMEDIATE / FINAL_OUTPUT")

# "yield" (VAR11001, linha/L1_L7) e o alvo funcional do bloco: verifica
# se alguma OUTRA das 106 equacoes o referencia como dependencia.
yield_referenced_elsewhere = False
for d in equation_definitions.all():
    if d.equation_definition_id == "EQ11001":
        continue
    deps = extractor.extract(d.expression)
    refs = deps.variables | deps.parameters
    if any(ref == "VAR11001" or ref.startswith("VAR11001@") for ref in refs):
        yield_referenced_elsewhere = True
        break
print(f"'yield' (VAR11001) e referenciado como dependencia por outra equacao? "
      f"{yield_referenced_elsewhere}")
results["yield_is_leaf_output"] = not yield_referenced_elsewhere

if chain_status == "PASS":
    print(f"\nValor calculado (SYNTHETIC, apenas prova de infraestrutura):")
    for line in LINES:
        v = chain_context.get_variable_value("VAR11001", "linha", line)
        print(f"  yield@{line} = {v}")
    yield_group = chain_context.get_variable_value("VAR11016", "linha_grupo", "L1_L3")
    print(f"  yield@L1_L3 (agregado) = {yield_group}")
    results["final_output_sample"] = {
        line: chain_context.get_variable_value("VAR11001", "linha", line)
        for line in LINES
    }


# ====================================================================
# 6. Persistencia -- onde o resultado fica?
# ====================================================================

section("6. PERSISTENCIA")

print("CalculationContext e um objeto Python em memoria (dataclasses + dicts "
      "internos), sem serializacao/persistencia embutida.")
print("Apos o retorno de calculate_from_definition_registry(), o objeto "
      "'chain_context' passado pelo chamador contem os valores calculados "
      "e pode ser consultado programaticamente (get_variable_value) -- mas "
      "somente enquanto o processo Python que o criou estiver vivo.")
print("Nenhum repository/DAO grava VariableInstance/resultado em disco/DB.")

results["persistence_in_memory_only"] = True


# ====================================================================
# 7. Escrita dos resultados brutos para os artefatos MD/CSV
# ====================================================================

OUT_DIR.mkdir(parents=True, exist_ok=True)
with open(OUT_DIR / "raw_experiment_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

print("\nRaw results written to audit/yield_e2e_readiness/raw_experiment_results.json")


# ====================================================================
# 8. yield_e2e_dependency_matrix.csv
# ====================================================================

import csv

var_id_to_name_map = {v["variable_id"]: v["variable_name"] for v in json.load(open(REPO / "data/seed/yield/variables.json", encoding="utf-8"))}
param_id_to_name_map = {p["parameter_id"]: p["parameter_name"] for p in json.load(open(REPO / "data/seed/yield/parameters.json", encoding="utf-8"))}

order_position = {node: i for i, node in enumerate(execution_order)} if execution_order else {}

dep_matrix_rows = []
for instance in all_instances:
    definition = definitions_by_id_and_version[
        (instance.equation_definition_id, instance.version)
    ]
    node_id = engine._build_instance_node_id(instance)
    deps = graph.get_dependencies(node_id)

    extracted = extractor.extract(definition.expression)
    all_refs = extracted.variables | extracted.parameters

    dep_matrix_rows.append(
        {
            "equation_id": node_id,
            "equation_definition_id": instance.equation_definition_id,
            "target_variable": var_id_to_name_map.get(instance.target_variable_id, instance.target_variable_id),
            "scope_type": instance.scope_type,
            "scope_value": instance.scope_value,
            "dependencies": "; ".join(sorted(deps)),
            "dependency_scopes": "; ".join(sorted(all_refs)),
            "producer_ids": "; ".join(sorted(deps)),
            "execution_order": order_position.get(node_id, ""),
            "status": definition.status,
            "executable": "YES" if chain_status == "PASS" else "UNKNOWN",
            "gap_id": "",
        }
    )

with open(OUT_DIR / "yield_e2e_dependency_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "equation_id", "equation_definition_id", "target_variable",
            "scope_type", "scope_value", "dependencies", "dependency_scopes",
            "producer_ids", "execution_order", "status", "executable", "gap_id",
        ],
    )
    writer.writeheader()
    writer.writerows(sorted(dep_matrix_rows, key=lambda r: r["execution_order"] if isinstance(r["execution_order"], int) else 999))

print(f"\nyield_e2e_dependency_matrix.csv written: {len(dep_matrix_rows)} rows")

# ====================================================================
# 9. yield_e2e_scope_aggregation_matrix.csv
# ====================================================================

agg_matrix_rows = [
    {
        "source_scope": "linha/L1..L7",
        "target_scope": "linha_grupo/L1_L3",
        "aggregation": "weighted average (peso=ltp) para yield/ratio_spent/eoc_temp; media simples para os demais; soma para producao_base_ppt",
        "supported": "YES",
        "required": "YES",
        "executed": "YES" if chain_status == "PASS" else "NO",
        "gap_id": "",
    },
    {
        "source_scope": "linha/L1..L7",
        "target_scope": "linha_grupo/L4_L5",
        "aggregation": "idem L1_L3",
        "supported": "YES",
        "required": "YES",
        "executed": "YES" if chain_status == "PASS" else "NO",
        "gap_id": "",
    },
    {
        "source_scope": "linha/L1..L7",
        "target_scope": "linha_grupo/L6_L7",
        "aggregation": "idem L1_L3",
        "supported": "YES",
        "required": "YES",
        "executed": "YES" if chain_status == "PASS" else "NO",
        "gap_id": "",
    },
    {
        "source_scope": "linha/L1..L7",
        "target_scope": "linha_grupo/L1_L7 (planta inteira)",
        "aggregation": "nao seedado (ver Fase 3A: anomalia de encadeamento de pesos na fonte)",
        "supported": "PARTIALLY",
        "required": "NOT_DEMONSTRATED",
        "executed": "NO",
        "gap_id": "GAP-06",
    },
    {
        "source_scope": "diário",
        "target_scope": "mensal",
        "aggregation": "media diario->mensal (nao seedada; TimePeriodResolver desconectado do calculo)",
        "supported": "NO",
        "required": "NOT_DEMONSTRATED",
        "executed": "NO",
        "gap_id": "GAP-04",
    },
]

with open(OUT_DIR / "yield_e2e_scope_aggregation_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["source_scope", "target_scope", "aggregation", "supported", "required", "executed", "gap_id"],
    )
    writer.writeheader()
    writer.writerows(agg_matrix_rows)

print(f"yield_e2e_scope_aggregation_matrix.csv written: {len(agg_matrix_rows)} rows")

print("\nALL EXPERIMENTS COMPLETE.")
