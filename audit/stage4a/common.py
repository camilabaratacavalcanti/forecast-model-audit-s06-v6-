"""
Stage 4A — base compartilhada do universo integrado de 5 blocos (REAL_DERIVED_TEST_RESULT).

Reutiliza, por IMPORT, o fixture e as utilidades da regressão integrada da 3.4C
(`audit/stage3_4/integrated/`), sem modificá-los:

    * fixture.build(order)        catálogo oficial + registro de vínculos em memória com pending = []
    * run_integrated.store_of/... codificação de resultados, observação, hashes

Protocolo de entradas (DR-4A-5): o fixture da 3.4C atribui a cada entrada livre o
valor `input_value(i, k, ...)`, onde i é a posição da variável em
`plan.required_inputs`. No plano de 5 blocos as 11 entradas do area_41 entram
INTERCALADAS nessa tupla (posições 44..54), o que deslocaria o índice de 7 entradas
dos 4 blocos e mudaria os valores dos 421 alvos por um artefato do fixture, e não
por regressão. Aqui o índice de cada entrada é a sua posição no plano de 4 blocos
(idêntico à 3.4C); as entradas novas do area_41 recebem os índices seguintes (51..61),
na ordem do plano de 5 blocos. Assim as entradas dos 4 blocos são byte a byte as
mesmas da 3.4C e a comparação de não-regressão é exata.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STAGE34_INTEGRATED = REPO / "audit" / "stage3_4" / "integrated"
for path in (str(REPO), str(STAGE34_INTEGRATED)):
    if path not in sys.path:
        sys.path.insert(0, path)

import fixture  # noqa: E402  (3.4C, importado sem alteração)
import run_integrated as ri  # noqa: E402  (3.4C, importado sem alteração)

from app.engine.scope_resolver import ScopeResolver  # noqa: E402
from app.engine.time_period_resolver import TimePeriodResolver  # noqa: E402

LABEL = fixture.LABEL
BLOCKS4 = fixture.OFFICIAL_BLOCKS
BLOCKS5 = BLOCKS4 + ("area_41",)
START, END = date(2026, 1, 1), date(2026, 2, 1)
DAYS = [START + timedelta(days=n) for n in range((END - START).days + 1)]
STAGE34_EVIDENCE = STAGE34_INTEGRATED / "evidence"
sys.path.insert(0, str(REPO / "audit" / "baselines"))
import baseline_paths as bp  # noqa: E402  (Stage 4C: fonte da referência da 3.4C)


def stage34(name: str) -> Path:
    """Arquivo da evidência de referência da 3.4C: histórico (default) ou do `--baseline-dir`."""
    return bp.path("stage3_4c_integrated", name)
PERIODS = TimePeriodResolver()


def plans(orchestrator):
    """(plano de 4 blocos da 3.4C, plano integrado de 5 blocos)."""
    return (orchestrator.plan(orchestrator.targets_of_blocks(BLOCKS4)),
            orchestrator.plan(orchestrator.targets_of_blocks(BLOCKS5)))


def input_index(plan4, plan5) -> dict:
    """DR-4A-5: índice da 3.4C para as entradas dos 4 blocos; novos índices para o area_41."""
    base = list(plan4.required_inputs)
    index = {variable: i for i, variable in enumerate(base)}
    extra = [v for v in plan5.required_inputs if v not in index]
    index.update({variable: len(base) + j for j, variable in enumerate(extra)})
    return index


class Universe:
    """Orquestrador do fixture + planos + protocolo de entradas, para uma ordem (A ou B)."""

    def __init__(self, order: str = "A"):
        self.order = order
        self.orchestrator = fixture.build(order)
        self.plan4, self.plan = plans(self.orchestrator)
        self.index = input_index(self.plan4, self.plan)
        catalog = self.orchestrator.catalog
        self.area_41_entities = {v.variable_definition_id for v in catalog.variable_definitions.all()
                                 if catalog.block_of.get(v.variable_definition_id) == "area_41"}

    # ------------------------------------------------------------ entradas e execução
    def seed_inputs(self, context, day: date) -> None:
        orchestrator = self.orchestrator
        orchestrator.seed_parameters(context)
        for variable_id in self.plan.required_inputs:
            definition = orchestrator.catalog.variable_definitions.get(variable_id)
            period = PERIODS.effective_window(definition.frequency, day).period_id
            for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(definition.scope_type,
                                                                        definition.scope_value)):
                value = (definition.allowed_values[0] if definition.is_categorical
                         else fixture.input_value(self.index[variable_id], k, definition.frequency, day))
                context.set_variable_value(variable_id, value, st, sv, period)

    def fresh_context(self):
        return ri.fresh_context(self.orchestrator)

    def execute_day(self, context, day, overrides=(), injections=()):
        self.seed_inputs(context, day)
        for variable_id, st, sv, period, result in list(overrides) + list(injections):
            context.set_variable_result(variable_id, result, st, sv, period)
        return self.orchestrator.execute(self.plan, context, day)

    def run_sequence(self, days=DAYS, overrides=None, injections=None, context=None):
        context = context or self.fresh_context()
        traces = {}
        for day in days:
            traces[day] = self.execute_day(context, day, (overrides or (lambda d: []))(day),
                                           (injections or (lambda d: []))(day))
        return context, traces


def subset_sha(store: dict, exclude: set) -> str:
    """Hash do subconjunto do store sem as entidades excluídas (mesma função da 3.4C)."""
    return ri.sha(sorted([list(k), v] for k, v in store.items() if k[0] not in exclude))


def only_sha(store: dict, include: set) -> str:
    return ri.sha(sorted([list(k), v] for k, v in store.items() if k[0] in include))


# ------------------------------------------------------------------ engine isolado do area_41
def area_41_equations(orchestrator) -> list:
    catalog = orchestrator.catalog
    return sorted((d for d in catalog.equation_definitions.all()
                   if catalog.block_of.get(d.equation_definition_id) == "area_41"),
                  key=lambda d: d.equation_definition_id)


def engine_area_41(orchestrator, inputs: dict, day: date = START, only=None):
    """
    Executa as equações do area_41 no ForecastEngine (caminho de produção), num contexto
    novo, com as entradas dadas: {(variável, scope_type, scope_value): valor}. O período de
    cada entrada vem da frequência da definição. Devolve ({(variável, st, sv): Result}, erro).
    `only`: ids de equação a executar (padrão: as 20).
    """
    from app.domain.equations.registry import EquationDefinitionRegistry
    from app.engine.calculation_context import CalculationContext
    from app.engine.forecast_engine import ForecastEngine

    catalog = orchestrator.catalog
    context = CalculationContext()
    context.declare_variable_definitions(catalog.variable_definitions.all())
    for (variable_id, st, sv), value in inputs.items():
        frequency = catalog.variable_definitions.get(variable_id).frequency
        context.set_variable_value(variable_id, value, st, sv, PERIODS.effective_window(frequency, day).period_id)
    registry = EquationDefinitionRegistry()
    definitions = [d for d in area_41_equations(orchestrator) if only is None or d.equation_definition_id in only]
    for definition in definitions:
        registry.add(definition)
    error = None
    try:
        with context.effective_window(day):
            ForecastEngine().calculate_from_definition_registry(
                equation_definition_registry=registry, calculation_context=context,
                variable_definition_registry=catalog.variable_definitions, run_date=day)
    except Exception as exc:  # noqa: BLE001 — a falha explícita é parte da evidência
        error = exc
    out = {}
    for definition in definitions:
        target = catalog.variable_definitions.get(definition.target_variable_id)
        period = PERIODS.effective_window(target.frequency, day).period_id
        for st, sv in ScopeResolver().resolve_scopes(definition.scope_type, definition.scope_value):
            try:
                out[(definition.target_variable_id, st, sv)] = context.get_variable_result(
                    definition.target_variable_id, st, sv, period)
            except Exception:  # noqa: BLE001 — não calculado (falha anterior)
                pass
    return out, error


def error_chain(exc) -> list[str]:
    """Nomes das classes na cadeia de causas (original_error/__cause__)."""
    names, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        names.append(type(exc).__name__)
        exc = getattr(exc, "original_error", None) or exc.__cause__
    return names
