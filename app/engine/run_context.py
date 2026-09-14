from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RunContext:
    """
    Contexto mínimo de execução temporal do forecast.

    Não é um modelo de execução persistido (não é um `CalculationRun`):
    representa apenas `run_date` e o `ForecastYear` derivado dele,
    suficientes para resolver o período corrente de uma execução.
    """

    run_date: date
    forecast_year: int

    @classmethod
    def from_run_date(cls, run_date: date) -> "RunContext":
        return cls(run_date=run_date, forecast_year=run_date.year)
