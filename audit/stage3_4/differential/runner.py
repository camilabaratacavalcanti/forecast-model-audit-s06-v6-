"""
Stage 3.4B — runner de UMA versão do runtime (reference ou candidate).

    python -I runner.py <app_root> <seed_root> <out_json>

Executado em subprocesso isolado (`python -I`: ignora PYTHONPATH, site do
usuário e o diretório corrente). `<app_root>` é um diretório que contém
SOMENTE o `app/` extraído por `git archive` de um commit; ele é o primeiro
item de `sys.path` e o runner prova, pelo `__file__` de cada módulo
`app.*` carregado, que nenhum código de outra versão foi importado.

Chama exclusivamente a API pública existente nas duas versões (mesmas
assinaturas em 7877551 e 95e7ade):

    SeedLoader(seed_root).load_variable_definitions / load_equation_definitions
        / load_parameter_instances / load_aggregation_rule_instances
    ForecastEngine.materialize_equation / calculate_from_definition_registry
    TemporalAggregationService.aggregate
    CalculationContext.set_variable_value / set_parameter_instance_value

Nenhuma lógica do engine é reimplementada; nenhum estado é injetado; nenhum
vínculo interbloco é usado (cada bloco roda isolado, com as variáveis
externas como entradas — o caminho comum às duas versões).

Universo (contrato 3.4A): instâncias de equação e de agregação dos quatro
blocos oficiais (yield, production, energy, max_ht) × VECTORS × DATES.
"""

import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

APP_ROOT = Path(sys.argv[1]).resolve()
SEED_ROOT = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3])
sys.path.insert(0, str(APP_ROOT))

from app.repositories.seed_loader import SeedLoader  # noqa: E402
from app.domain.equations.registry import EquationDefinitionRegistry  # noqa: E402
from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.forecast_engine import ForecastEngine  # noqa: E402
from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.temporal_aggregation_service import TemporalAggregationService  # noqa: E402
from app.engine.time_period_resolver import TimePeriodResolver  # noqa: E402

BLOCKS = ("energy", "max_ht", "production", "yield")          # ordem fixa
DATES = ("2026-09-03", "2026-12-31")                          # meio de mês/ano parcial; fim de mês e de ano
VECTORS = ("VECTOR_A", "VECTOR_B", "VECTOR_C")


def equation_input(vector: str, i: int, k: int, doy: int) -> float:
    """
    Entrada da variável de índice i (ordem alfabética) no escopo de índice k,
    no dia do ano `doy` do run_date (a data também muda os valores).
    """
    if vector == "VECTOR_A":                                   # nominal: ~1.5–1.8
        return 1.5 + 0.013 * i + 0.0007 * k + 0.0001 * doy
    if vector == "VECTOR_B":                                   # ~10–18.2
        return 10.0 + 0.37 * ((7 * i + 3 * k) % 23) + 0.01 * (doy % 7)
    return 50.0 + 5.0 * ((11 * i + k) % 17) + (doy % 3)        # VECTOR_C: 50–132 (ex. EQ18003: VAR18012 > 72)


def aggregation_input(vector: str, d: int, n: int, weight: bool) -> float:
    """Série de origem (ou peso) no dia d da janela, para a instância de ordinal n."""
    if vector == "VECTOR_A":
        return 2.0 + 0.01 * ((7 * d + n) % 97) + (0.5 if weight else 0.0)
    if vector == "VECTOR_B":
        return (1.0 + ((d + n) % 5)) if weight else 100.0 + 0.25 * ((13 * d + 3 * n) % 101)
    return (0.1 + ((3 * d + n) % 11) / 4.0) if weight else 0.5 + ((d * d + n) % 53) / 7.0


def encode(value):
    """Representação exata: (tipo, repr). repr de float é round-trip exato."""
    return [type(value).__name__, repr(value)]


def result_parts(context, variable_id, scope_type, scope_value, period_id):
    """value/state/detail do contexto; state/detail só existem na versão com Result."""
    if hasattr(context, "get_variable_result"):
        result = context.get_variable_result(variable_id, scope_type, scope_value, period_id)
        return encode(result.value), result.state, result.detail
    value = context.get_variable_value(variable_id, scope_type, scope_value, period_id)
    return encode(value), "NOT_APPLICABLE_TO_REFERENCE", "NOT_APPLICABLE_TO_REFERENCE"


def block_index(kind):
    """entidade -> bloco, lido dos seeds (data/, invariante)."""
    index = {}
    for block in BLOCKS:
        rows = json.loads((SEED_ROOT / block / kind).read_text(encoding="utf-8"))
        for row in rows:
            index[row["equation_id"] if kind == "equations.json" else row["aggregation_rule_id"]] = block
    return index


loader = SeedLoader(SEED_ROOT)
variables = loader.load_variable_definitions()
equations = loader.load_equation_definitions()
parameters = sorted(loader.load_parameter_instances().all(), key=lambda p: p.parameter_instance_id)
aggregation_instances = loader.load_aggregation_rule_instances(variable_definition_registry=variables)
equation_block = block_index("equations.json")
aggregation_block = block_index("aggregation_rules.json")
periods = TimePeriodResolver()
cases = []

# ---------------------------------------------------------------- equações
for block in BLOCKS:
    definitions = sorted((e for e in equations.all() if equation_block.get(e.equation_definition_id) == block),
                         key=lambda e: e.equation_definition_id)
    targets = {e.target_variable_id for e in definitions}
    external = sorted({ref for e in definitions for ref in re.findall(r"VAR\d+", e.expression)} - targets)
    for vector in VECTORS:
        for run in DATES:
            run_date = date.fromisoformat(run)
            registry = EquationDefinitionRegistry()
            for definition in definitions:
                registry.add(definition)
            context = CalculationContext()
            for parameter in parameters:
                context.set_parameter_instance_value(parameter, parameter.value)
            for i, variable_id in enumerate(external):
                d = variables.get(variable_id)
                period = periods.effective_window(d.frequency, run_date).period_id
                for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
                    context.set_variable_value(variable_id, equation_input(vector, i, k, run_date.timetuple().tm_yday),
                                               st, sv, period)
            engine = ForecastEngine()
            try:
                returned = engine.calculate_from_definition_registry(
                    equation_definition_registry=registry, calculation_context=context,
                    variable_definition_registry=variables, run_date=run_date)
                error = None
            except Exception as exc:  # noqa: BLE001 — registrado como EXCEPTION, nunca omitido
                returned, error = {}, f"{type(exc).__name__}: {exc}"
            for definition in definitions:
                target = variables.get(definition.target_variable_id)
                period = periods.effective_window(target.frequency, run_date).period_id
                for instance in sorted(engine.materialize_equation(definition), key=lambda x: x.equation_instance_id):
                    case = {"block": block, "operation_type": "EQUATION",
                            "instance_id": instance.equation_instance_id,
                            "definition_id": definition.equation_definition_id,
                            "target": definition.target_variable_id, "scope": [instance.scope_type, instance.scope_value],
                            "period_id": period, "input_vector": vector, "run_date": run}
                    if error or instance.equation_instance_id not in returned:
                        case["outcome"] = ["EXCEPTION", error or "instância sem retorno do engine"]
                    else:
                        value, state, detail = result_parts(context, definition.target_variable_id,
                                                            instance.scope_type, instance.scope_value, period)
                        case["outcome"] = ["OK", encode(returned[instance.equation_instance_id]), value, state, detail]
                    cases.append(case)

# ---------------------------------------------------------------- agregações
selected = sorted((i for i in aggregation_instances.all() if i.rule.aggregation_rule_id in aggregation_block),
                  key=lambda i: i.aggregation_rule_instance_id)
service = TemporalAggregationService()
for n, instance in enumerate(selected):
    rule = instance.rule
    for vector in VECTORS:
        for run in DATES:
            run_date = date.fromisoformat(run)
            context = CalculationContext()
            day, d = date(run_date.year, 1, 1), 0
            while day <= run_date:                                      # histórico desde 1º de janeiro
                for variable_id, weight in ((rule.source_variable_id, False), (rule.weight_variable_id, True)):
                    if variable_id:
                        context.set_variable_value(variable_id, aggregation_input(vector, d, n, weight),
                                                   instance.scope_type, instance.scope_value, day.isoformat())
                day, d = day + timedelta(days=1), d + 1
            case = {"block": aggregation_block[rule.aggregation_rule_id], "operation_type": "AGGREGATION",
                    "instance_id": instance.aggregation_rule_instance_id,
                    "definition_id": rule.aggregation_rule_id, "aggregation_type": rule.aggregation_type,
                    "integration_factor": rule.integration_factor, "target": rule.target_variable_id,
                    "scope": [instance.scope_type, instance.scope_value], "input_vector": vector, "run_date": run}
            try:
                fv = service.aggregate(rule, context, instance.scope_type, instance.scope_value, run_date)
                state = getattr(fv, "state", "NOT_APPLICABLE_TO_REFERENCE")
                detail = getattr(fv, "detail", "NOT_APPLICABLE_TO_REFERENCE")
                case["period_id"] = fv.period_id
                case["outcome"] = ["OK", encode(fv.value), [fv.variable_id, fv.scope_type, fv.scope_value,
                                                            fv.frequency, fv.period_id], state, detail]
            except Exception as exc:  # noqa: BLE001
                case["outcome"] = ["EXCEPTION", f"{type(exc).__name__}: {exc}"]
            cases.append(case)

# ---------------------------------------------------------------- prova de isolamento
loaded = sorted({str(Path(m.__file__).resolve()) for name, m in sys.modules.items()
                 if name == "app" or name.startswith("app.") if getattr(m, "__file__", None)})
foreign = [path for path in loaded if not path.startswith(str(APP_ROOT) + "/")]
fingerprint = hashlib.sha256()
for path in sorted((APP_ROOT / "app").rglob("*.py")):
    fingerprint.update(str(path.relative_to(APP_ROOT)).encode())
    fingerprint.update(path.read_bytes())

OUT.write_text(json.dumps({
    "app_root": str(APP_ROOT), "app_sha256": fingerprint.hexdigest(), "modules_loaded": len(loaded),
    "foreign_modules": foreign, "python": sys.version.split()[0], "vectors": list(VECTORS), "dates": list(DATES),
    "cases": cases,
}, sort_keys=True, indent=0), encoding="utf-8")
