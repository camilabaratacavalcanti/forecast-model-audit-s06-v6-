"""
Objetivo (Fase B):
    Aplicar uma AggregationRule sobre valores temporais já calculados
    (armazenados no CalculationContext), produzindo um ForecastValue
    derivado em outra frequência.

    Esta é uma camada independente da lógica das EquationDefinitions:
    não participa do parsing/avaliação de expressões, não é chamada
    pelo EquationEngine e não introduz nenhuma dimensão temporal no
    DependencyGraph. Opera inteiramente sobre resultados já
    calculados (DIRECT ou de outra agregação), lendo-os do
    CalculationContext pelo period_id de cada sub-período dentro da
    janela.

Responsabilidades:
    - resolver a janela temporal efetiva de uma AggregationRule
      (derivada da frequência de destino + run_date, ou explícita,
      quando a regra a define);
    - enumerar os period_ids de origem dentro dessa janela,
      respeitando a frequência de origem;
    - ler os valores de origem no escopo informado;
    - aplicar o algoritmo de agregação (AVERAGE, SUM,
      WEIGHTED_AVERAGE, MOVING_AVERAGE);
    - produzir um ForecastValue de destino, identificado também pela
      regra que o produziu (aggregation_rule_id), para que múltiplas
      regras sobre a mesma Variable/frequência não colidam.

Não é responsabilidade deste componente:
    - persistir o resultado;
    - decidir quais variáveis devem ter regras de agregação;
    - alterar o CalculationContext (o serviço apenas lê valores de
      origem; o resultado é devolvido ao chamador como ForecastValue,
      nunca escrito de volta automaticamente).
"""

from datetime import date, timedelta

from app.domain.forecast.aggregation import AggregationRule
from app.domain.forecast.models import ForecastValue
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    EmptyAggregationWindowError,
    ZeroWeightSumError,
)
from app.engine.time_period_resolver import TimePeriodResolver


class TemporalAggregationService:
    """
    Executa uma AggregationRule sobre um CalculationContext já
    populado com resultados temporais (DIRECT ou de outras
    agregações), produzindo um ForecastValue derivado.
    """

    def __init__(
        self,
        time_period_resolver: TimePeriodResolver | None = None,
    ):
        self.time_period_resolver = (
            time_period_resolver or TimePeriodResolver()
        )

    def aggregate(
        self,
        rule: AggregationRule,
        calculation_context: CalculationContext,
        scope_type: str | None,
        scope_value: str | None,
        run_date: date,
        execution_id: str | None = None,
    ) -> ForecastValue:
        """
        Aplica `rule` sobre os valores de `rule.source_variable_id`
        já presentes em `calculation_context`, no escopo informado,
        dentro da janela temporal efetiva em `run_date`, produzindo
        um ForecastValue de `rule.target_variable_id`.
        """

        window_start, window_end = self._resolve_window(
            rule=rule,
            run_date=run_date,
        )

        source_period_ids = self._enumerate_source_period_ids(
            frequency=rule.source_frequency,
            start_date=window_start,
            end_date=window_end,
        )

        values = [
            calculation_context.get_variable_value(
                rule.source_variable_id,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=period_id,
            )
            for period_id in source_period_ids
        ]

        if not values:
            raise EmptyAggregationWindowError(
                "Nenhum valor de origem encontrado para "
                f"{rule.source_variable_id} entre "
                f"{window_start.isoformat()} e "
                f"{window_end.isoformat()} "
                f"(regra {rule.aggregation_rule_id})."
            )

        if rule.aggregation_type == "WEIGHTED_AVERAGE":
            result = self._weighted_average(
                rule=rule,
                calculation_context=calculation_context,
                scope_type=scope_type,
                scope_value=scope_value,
                source_period_ids=source_period_ids,
                values=values,
            )
        elif rule.aggregation_type == "SUM":
            result = sum(values)
        else:
            # AVERAGE e MOVING_AVERAGE: mesma aritmética (média
            # simples), distintas apenas pela origem da janela —
            # calendário derivado da frequência (AVERAGE) ou janela
            # explícita da regra (MOVING_AVERAGE, ver
            # `_resolve_window`).
            result = sum(values) / len(values)

        target_period = self.time_period_resolver.effective_window(
            frequency=rule.target_frequency,
            run_date=run_date,
        )

        return ForecastValue(
            variable_id=rule.target_variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            frequency=rule.target_frequency,
            forecast_year=run_date.year,
            period_id=target_period.period_id,
            value=result,
            execution_id=execution_id,
            aggregation_rule_id=rule.aggregation_rule_id,
        )

    def _resolve_window(
        self,
        rule: AggregationRule,
        run_date: date,
    ) -> tuple[date, date]:
        """
        Resolve a janela [start_date, end_date] (inclusiva) que
        delimita quais sub-períodos de origem entram na agregação.

        Quando a regra define uma janela explícita
        (`window_start_date`/`window_end_date`), ela prevalece —
        nunca é permitido ultrapassar run_date. Caso contrário, a
        janela é derivada da frequência de destino truncada em
        run_date (o mesmo mecanismo usado pelo ForecastEngine para
        uma Equation DIRECT).
        """

        if (
            rule.window_start_date is not None
            and rule.window_end_date is not None
        ):
            window_end = min(rule.window_end_date, run_date)

            return rule.window_start_date, window_end

        target_period = self.time_period_resolver.effective_window(
            frequency=rule.target_frequency,
            run_date=run_date,
        )

        return target_period.start_date, target_period.end_date

    @staticmethod
    def _enumerate_source_period_ids(
        frequency: str,
        start_date: date,
        end_date: date,
    ) -> list[str]:
        """
        Enumera os period_ids de origem estritamente dentro de
        [start_date, end_date], na convenção de period_id da
        frequência informada (YYYY-MM-DD / YYYY-MM / YYYY).

        Diferente de `TimePeriodResolver.resolve()`, que sempre
        devolve períodos completos de calendário, esta enumeração
        nunca ultrapassa os limites exatos da janela — necessário
        para que uma agregação nunca consuma um sub-período fora da
        janela efetiva (ex.: dados futuros, ou de outro ForecastYear).
        """

        period_ids: list[str] = []
        seen: set[str] = set()

        current_date = start_date

        while current_date <= end_date:
            if frequency == "diário":
                period_id = current_date.isoformat()
            elif frequency == "mensal":
                period_id = (
                    f"{current_date.year:04d}-"
                    f"{current_date.month:02d}"
                )
            elif frequency == "anual":
                period_id = f"{current_date.year:04d}"
            else:
                raise ValueError(
                    f"Unsupported frequency: {frequency}"
                )

            if period_id not in seen:
                seen.add(period_id)
                period_ids.append(period_id)

            current_date += timedelta(days=1)

        return period_ids

    @staticmethod
    def _weighted_average(
        rule: AggregationRule,
        calculation_context: CalculationContext,
        scope_type: str | None,
        scope_value: str | None,
        source_period_ids: list[str],
        values: list[int | float],
    ) -> int | float:
        weights = [
            calculation_context.get_variable_value(
                rule.weight_variable_id,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=period_id,
            )
            for period_id in source_period_ids
        ]

        weight_sum = sum(weights)

        if weight_sum == 0:
            raise ZeroWeightSumError(
                "SUM(weight) é zero para "
                f"{rule.weight_variable_id} "
                f"(regra {rule.aggregation_rule_id}): "
                "WEIGHTED_AVERAGE não pode ser calculada."
            )

        weighted_sum = sum(
            value * weight
            for value, weight in zip(values, weights)
        )

        return weighted_sum / weight_sum
