from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastValue:
    """
    Representa um resultado temporal calculado pelo ForecastEngine.

    Identidade lógica de um ForecastValue:

        (variable_id, scope_type, scope_value, frequency, period_id)

    Duas execuções (`execution_id` diferente) que calculam o mesmo
    variable_id/escopo/frequência/period_id representam o MESMO valor
    lógico — `execution_id` é apenas proveniência (qual execução
    produziu este resultado), nunca parte da identidade. Ou seja,
    recalcular o mesmo período não cria uma nova identidade de valor.

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

    def identity(
        self,
    ) -> tuple[str, str | None, str | None, str, str]:
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
        )
