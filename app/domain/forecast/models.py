from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastValue:
    """
    Representa um resultado temporal calculado pelo ForecastEngine ou
    pelo TemporalAggregationService (Fase B).

    Identidade lógica de um ForecastValue:

        (variable_id, scope_type, scope_value, frequency, period_id,
         aggregation_rule_id)

    Duas execuções (`execution_id` diferente) que calculam o mesmo
    variable_id/escopo/frequência/period_id/regra representam o MESMO
    valor lógico — `execution_id` é apenas proveniência (qual
    execução produziu este resultado), nunca parte da identidade.
    Recalcular o mesmo período não cria uma nova identidade de valor.

    `aggregation_rule_id` faz parte da identidade (e não é mera
    proveniência) porque a mesma Variable pode ter mais de uma regra
    de agregação para a mesma frequência (ex.: "production mensal
    SUM" e "production mensal AVERAGE") — sem a regra, os dois
    resultados colidiriam na mesma identidade lógica. Um ForecastValue
    calculado DIRECT (sem agregação) tem aggregation_rule_id=None.

    Este modelo não é persistido (sem Azure, sem repository próprio
    nesta fase) — representa apenas a forma mínima de um resultado
    temporal em memória.
    """

    variable_id: str
    scope_type: str | None
    scope_value: str | None
    frequency: str
    forecast_year: int
    period_id: str
    value: int | float
    execution_id: str | None = None
    aggregation_rule_id: str | None = None

    def identity(
        self,
    ) -> tuple[
        str, str | None, str | None, str, str, str | None
    ]:
        """
        Retorna a chave de identidade lógica do valor, excluindo
        `execution_id` (proveniência) e `value`.
        """

        return (
            self.variable_id,
            self.scope_type,
            self.scope_value,
            self.frequency,
            self.period_id,
            self.aggregation_rule_id,
        )
