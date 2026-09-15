"""
Objetivo (Fase C):
    Orquestrar a execução temporal do Forecast sobre os componentes já
    existentes (ForecastEngine, TemporalAggregationService,
    TimePeriodResolver, CalculationContext), sem alterar nenhum deles
    e sem duplicar sua lógica.

    O TemporalForecastOrchestrator NÃO calcula equações, NÃO agrega
    valores e NÃO conhece a sintaxe de expressões — ele apenas
    coordena QUANDO e SOBRE QUAL período cada componente já existente
    deve ser chamado:

        run_date
            ↓
        start_execution (Execution.start, status=RUNNING)
            ↓
        TemporalForecastOrchestrator
            ↓
        ┌──────────────────┬──────────────────────────┐
        │                  │                           │
        ▼                  ▼                           ▼
    available_periods   run_direct                run_aggregation
    (TimePeriodResolver) (ForecastEngine)     (TemporalAggregationService)
                            │                           │
                            ▼                           ▼
                 direct_forecast_value       Aggregated ForecastValue
                            │                           │
                            └─────────────┬─────────────┘
                                          ▼
                                ForecastValueRegistry (opcional)
                                          │
                                          ▼
                        execution.complete() / execution.fail()
                          (decidido pelo chamador, não automático)

    Uma Execution (TD-C02) contextualiza a rodada — não calcula nada
    e não é armazenada dentro de ForecastValue: apenas seu
    `execution_id` é propagado como proveniência. `ForecastValueRegistry`
    (TD-C01/TD-C03) usa esse `execution_id` para saber quando um novo
    valor está substituindo o vigente, arquivando o anterior em
    histórico em vez de rejeitá-lo.

Não é responsabilidade deste componente:
    - persistir resultados ou Executions (ver ForecastValueRegistry:
      apenas memória, sem Repository/Azure);
    - decidir regras de negócio de agregação (isso pertence a cada
      AggregationRule, definida pelo chamador);
    - transicionar automaticamente o status de uma Execution em caso
      de erro (ver docstring de `run_aggregation`);
    - alterar EquationDefinition/EquationInstance/DependencyGraph/
      ExpressionEvaluator/EquationEngine — nenhum deles é modificado
      ou tem sua semântica alterada por este módulo.
"""

from datetime import date

from app.domain.equations.registry import EquationDefinitionRegistry
from app.domain.forecast.aggregation import AggregationRule
from app.domain.forecast.execution import Execution
from app.domain.forecast.models import ForecastValue
from app.domain.variables.registry import VariableDefinitionRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.forecast_engine import ForecastEngine
from app.engine.run_context import RunContext
from app.engine.temporal_aggregation_service import (
    TemporalAggregationService,
)
from app.engine.time_period_resolver import TimePeriod, TimePeriodResolver


class TemporalForecastOrchestrator:
    """
    Coordena, para um dado `run_date`, quais períodos precisam ser
    considerados e delega a execução real a ForecastEngine (DIRECT) e
    a TemporalAggregationService (TEMPORAL_AGGREGATED).
    """

    def __init__(
        self,
        forecast_engine: ForecastEngine | None = None,
        aggregation_service: TemporalAggregationService | None = None,
        time_period_resolver: TimePeriodResolver | None = None,
    ):
        self.forecast_engine = forecast_engine or ForecastEngine()
        self.aggregation_service = (
            aggregation_service or TemporalAggregationService()
        )
        self.time_period_resolver = (
            time_period_resolver or TimePeriodResolver()
        )

    def start_execution(
        self,
        run_date: date,
        model_version: str = "v1",
        execution_id: str | None = None,
    ) -> Execution:
        """
        Cria uma nova Execution (status RUNNING) para `run_date`.

        O TemporalForecastOrchestrator é responsável por CRIAR a
        Execution (esta chamada) — não por persisti-la nem por
        decidir seu ciclo de vida além disso: transições de status
        (`execution.complete()`/`execution.fail()`) são feitas pelo
        chamador, no ponto em que ele sabe se a rodada terminou com
        sucesso ou falhou (ver docstring de `run_aggregation` sobre
        por que este componente não envolve as chamadas em
        try/except automaticamente).
        """

        return Execution.start(
            run_date=run_date,
            model_version=model_version,
            execution_id=execution_id,
        )

    def available_periods(
        self,
        frequency: str,
        run_date: date,
    ) -> list[TimePeriod]:
        """
        Responde: quais períodos desta frequência estão disponíveis,
        desde o início do ForecastYear de `run_date`, até `run_date`?

        Reutiliza inteiramente `TimePeriodResolver`: `resolve()` já
        enumera corretamente os períodos completos de calendário
        (dias e meses passados), e `effective_window()` já resolve
        corretamente o período corrente truncado em `run_date`. A
        única composição nova é substituir o último período retornado
        por `resolve()` (que, para "mensal"/"anual", vem com a janela
        de calendário COMPLETA) pelo período corrente truncado — sem
        isso, o período em andamento apareceria com dados "futuros"
        (ex.: mês inteiro em vez de até `run_date`).

        O ForecastYear de `run_date` delimita o início da enumeração:
        nunca é possível um período de outro ano aparecer aqui, pois
        `year_start` é sempre 1º de janeiro do próprio ano de
        `run_date` (ver Fase B, TD-B01 — este método não sofre desse
        gap, pois nunca usa uma janela explícita externa).
        """

        forecast_year = RunContext.from_run_date(run_date).forecast_year
        year_start = date(forecast_year, 1, 1)

        periods = self.time_period_resolver.resolve(
            frequency, year_start, run_date
        )

        periods[-1] = self.time_period_resolver.effective_window(
            frequency, run_date
        )

        return periods

    def run_direct(
        self,
        equation_definition_registry: EquationDefinitionRegistry,
        variable_definition_registry: VariableDefinitionRegistry,
        calculation_context: CalculationContext,
        run_date: date,
    ) -> dict[str, int | float]:
        """
        Executa um snapshot DIRECT para `run_date`: delega
        integralmente a `ForecastEngine.calculate_from_definition_registry`,
        que já deriva a frequência de cada instância via
        VariableDefinition e resolve o period_id efetivo — nada é
        recalculado ou reinterpretado aqui.
        """

        return self.forecast_engine.calculate_from_definition_registry(
            equation_definition_registry=equation_definition_registry,
            calculation_context=calculation_context,
            variable_definition_registry=variable_definition_registry,
            run_date=run_date,
        )

    def run_direct_accumulated(
        self,
        equation_definition_registry: EquationDefinitionRegistry,
        variable_definition_registry: VariableDefinitionRegistry,
        calculation_context: CalculationContext,
        run_date: date,
    ) -> dict[date, dict[str, int | float]]:
        """
        Executa `run_direct` para cada dia disponível desde o início
        do ForecastYear de `run_date` até `run_date` (o cenário
        "processando o acumulado do ano" descrito na Fase C) —
        chamadas sucessivas ao mesmo `run_direct` já existente, sem
        nenhuma lógica de cálculo nova.

        Retorna o resultado de cada dia, indexado pela própria data,
        para inspeção; os valores já ficam armazenados em
        `calculation_context` sob o period_id de cada dia, exatamente
        como uma chamada manual dia-a-dia produziria.
        """

        results_by_day: dict[date, dict[str, int | float]] = {}

        for period in self.available_periods("diário", run_date):
            day = period.start_date

            results_by_day[day] = self.run_direct(
                equation_definition_registry=equation_definition_registry,
                variable_definition_registry=variable_definition_registry,
                calculation_context=calculation_context,
                run_date=day,
            )

        return results_by_day

    def direct_forecast_value(
        self,
        variable_id: str,
        scope_type: str | None,
        scope_value: str | None,
        variable_definition_registry: VariableDefinitionRegistry,
        calculation_context: CalculationContext,
        run_date: date,
        execution: Execution | None = None,
    ) -> ForecastValue:
        """
        Constrói o ForecastValue (DIRECT, aggregation_rule_id=None)
        correspondente a um resultado já calculado por `run_direct`
        e armazenado em `calculation_context`.

        `ForecastEngine.calculate_from_definition_registry` devolve
        apenas um dict bruto (equation_instance_id -> valor), sem
        empacotar ForecastValue — esta é a ponte mínima entre os dois
        mundos, reutilizando exatamente os mesmos dois blocos que o
        ForecastEngine já usa internamente para derivar o period_id
        efetivo (VariableDefinition.frequency +
        TimePeriodResolver.effective_window), sem duplicar nenhuma
        regra de calendário nova.

        `execution`, quando informado, identifica a Execution que
        produziu este valor (seu `execution_id` é copiado para o
        ForecastValue resultante — nunca a Execution inteira, que
        não é armazenada em ForecastValue). `execution.run_date`
        deve ser exatamente `run_date`: uma Execution pertence a um
        único run_date, por contrato.
        """

        self._validate_execution_run_date(execution, run_date)

        variable_definition = variable_definition_registry.get(
            variable_id
        )

        period = self.time_period_resolver.effective_window(
            frequency=variable_definition.frequency,
            run_date=run_date,
        )

        value = calculation_context.get_variable_value(
            variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period.period_id,
        )

        forecast_year = RunContext.from_run_date(run_date).forecast_year

        return ForecastValue(
            variable_id=variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            frequency=variable_definition.frequency,
            forecast_year=forecast_year,
            period_id=period.period_id,
            value=value,
            execution_id=(
                execution.execution_id if execution else None
            ),
            aggregation_rule_id=None,
            run_date=run_date,
        )

    def run_aggregation(
        self,
        rule: AggregationRule,
        calculation_context: CalculationContext,
        scope_type: str | None,
        scope_value: str | None,
        run_date: date,
        execution: Execution | None = None,
    ) -> ForecastValue:
        """
        Executa uma agregação TEMPORAL_AGGREGATED para `run_date`:
        delega integralmente a `TemporalAggregationService.aggregate`
        — nenhum algoritmo de agregação é reimplementado aqui.

        `execution`, quando informado, segue a mesma regra de
        `direct_forecast_value`: apenas seu `execution_id` é
        propagado ao ForecastValue resultante.

        Esta chamada NÃO envolve `execution.complete()`/`.fail()`
        automaticamente: se o cálculo falhar, a exceção original
        (ex.: VariableNotFoundError) propaga sem ser interceptada —
        decidir se isso significa que a Execution falhou é
        responsabilidade de quem chamou, no seu próprio bloco
        try/except, exatamente como o restante da plataforma trata
        erros (fail-fast, sem captura silenciosa em nenhuma camada).
        """

        self._validate_execution_run_date(execution, run_date)

        return self.aggregation_service.aggregate(
            rule=rule,
            calculation_context=calculation_context,
            scope_type=scope_type,
            scope_value=scope_value,
            run_date=run_date,
            execution_id=(
                execution.execution_id if execution else None
            ),
        )

    @staticmethod
    def _validate_execution_run_date(
        execution: Execution | None,
        run_date: date,
    ) -> None:
        if execution is not None and execution.run_date != run_date:
            raise ValueError(
                "run_date informado "
                f"({run_date.isoformat()}) não corresponde ao "
                "run_date da Execution "
                f"({execution.run_date.isoformat()}): uma "
                "Execution pertence a um único run_date."
            )
