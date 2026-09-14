from dataclasses import dataclass
from datetime import date, timedelta
import calendar


@dataclass(frozen=True)
class TimePeriod:
    """
    Representa um período temporal do forecast.

    Para frequência diária:
        start_date == end_date

    Para frequência mensal:
        start_date corresponde ao primeiro dia do mês
        end_date corresponde ao último dia do mês
    """

    period_id: str
    frequency: str
    start_date: date
    end_date: date


class TimePeriodResolver:
    """
    Resolve um horizonte temporal em períodos concretos.

    Responsabilidades:
    - interpretar a frequência temporal da variável;
    - gerar períodos diários ou mensais;
    - respeitar o horizonte informado.

    Não é responsabilidade deste componente:
    - calcular valores;
    - interpretar equações;
    - resolver escopos espaciais;
    - realizar agregações.
    """

    SUPPORTED_FREQUENCIES = {"diário", "mensal", "anual"}

    def resolve(
        self,
        frequency: str,
        start_date: date,
        end_date: date,
    ) -> list[TimePeriod]:
        """
        Gera os períodos correspondentes ao horizonte informado.
        """

        self._validate_frequency(frequency)
        self._validate_dates(start_date, end_date)

        if frequency == "diário":
            return self._resolve_daily(start_date, end_date)

        if frequency == "mensal":
            return self._resolve_monthly(start_date, end_date)

        if frequency == "anual":
            return self._resolve_annual(start_date, end_date)

        # Proteção adicional caso novas frequências sejam adicionadas.
        raise ValueError(f"Unsupported frequency: {frequency}")

    def effective_window(
        self,
        frequency: str,
        run_date: date,
    ) -> TimePeriod:
        """
        Resolve a janela efetiva do período corrente em `run_date`.

        Diferente de `resolve()` (que sempre gera períodos completos de
        calendário), esta janela é truncada em `run_date`: o `end_date`
        nunca ultrapassa `run_date`, mesmo que o mês/ano de calendário
        ainda não tenha terminado.

        - diário: period_id = run_date (start == end == run_date).
        - mensal: period_id = ano-mês de run_date; start = primeiro dia
          do mês; end = run_date.
        - anual: period_id = ano de run_date; start = 1º de janeiro;
          end = run_date.
        """

        self._validate_frequency(frequency)
        self._validate_dates(run_date, run_date)

        if frequency == "diário":
            return TimePeriod(
                period_id=run_date.isoformat(),
                frequency="diário",
                start_date=run_date,
                end_date=run_date,
            )

        if frequency == "mensal":
            period_id = f"{run_date.year:04d}-{run_date.month:02d}"
            month_start = date(run_date.year, run_date.month, 1)

            return TimePeriod(
                period_id=period_id,
                frequency="mensal",
                start_date=month_start,
                end_date=run_date,
            )

        if frequency == "anual":
            year_start = date(run_date.year, 1, 1)

            return TimePeriod(
                period_id=f"{run_date.year:04d}",
                frequency="anual",
                start_date=year_start,
                end_date=run_date,
            )

        # Proteção adicional caso novas frequências sejam adicionadas.
        raise ValueError(f"Unsupported frequency: {frequency}")

    def _resolve_daily(
        self,
        start_date: date,
        end_date: date,
    ) -> list[TimePeriod]:
        periods: list[TimePeriod] = []

        current_date = start_date

        while current_date <= end_date:
            period_id = current_date.isoformat()

            periods.append(
                TimePeriod(
                    period_id=period_id,
                    frequency="diário",
                    start_date=current_date,
                    end_date=current_date,
                )
            )

            current_date += timedelta(days=1)

        return periods

    def _resolve_monthly(
        self,
        start_date: date,
        end_date: date,
    ) -> list[TimePeriod]:
        periods: list[TimePeriod] = []

        current_year = start_date.year
        current_month = start_date.month

        while True:
            month_start = date(
                current_year,
                current_month,
                1,
            )

            last_day = calendar.monthrange(
                current_year,
                current_month,
            )[1]

            month_end = date(
                current_year,
                current_month,
                last_day,
            )

            # Inclui somente meses que tenham interseção
            # com o horizonte solicitado.
            if month_end >= start_date and month_start <= end_date:
                period_id = f"{current_year:04d}-{current_month:02d}"

                periods.append(
                    TimePeriod(
                        period_id=period_id,
                        frequency="mensal",
                        start_date=month_start,
                        end_date=month_end,
                    )
                )

            if (
                current_year > end_date.year
                or (
                    current_year == end_date.year
                    and current_month >= end_date.month
                )
            ):
                break

            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        return periods

    def _resolve_annual(
        self,
        start_date: date,
        end_date: date,
    ) -> list[TimePeriod]:
        periods: list[TimePeriod] = []

        for year in range(start_date.year, end_date.year + 1):
            periods.append(
                TimePeriod(
                    period_id=f"{year:04d}",
                    frequency="anual",
                    start_date=date(year, 1, 1),
                    end_date=date(year, 12, 31),
                )
            )

        return periods

    def _validate_frequency(self, frequency: str) -> None:
        if not frequency:
            raise ValueError("Frequency is required")

        if frequency not in self.SUPPORTED_FREQUENCIES:
            raise ValueError(
                f"Unsupported frequency: {frequency}"
            )

    def _validate_dates(
        self,
        start_date: date,
        end_date: date,
    ) -> None:
        if not isinstance(start_date, date):
            raise TypeError("start_date must be a date")

        if not isinstance(end_date, date):
            raise TypeError("end_date must be a date")

        if start_date > end_date:
            raise ValueError(
                "start_date must be earlier than or equal to end_date"
            )
