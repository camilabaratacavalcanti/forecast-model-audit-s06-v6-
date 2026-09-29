from dataclasses import dataclass
from datetime import date

from app.domain.results import Result, ResultContractError
from app.domain.values import RESULT_STATE_TAXONOMY, ScalarValue


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

    `run_date`, como `execution_id`, é proveniência — não faz parte
    da identidade. Foi adicionado (TD-C02) porque, sem ele, não havia
    como reconstruir "até que dia este número é válido" a partir de
    um ForecastValue já calculado (um período mensal em andamento
    recalculado em dias diferentes produz o mesmo period_id com
    valores diferentes; sem run_date, os dois resultados eram
    indistinguíveis exceto pelo value).

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
    # Numérico no caso geral; texto quando a variável é categórica ou
    # quando o resultado DIRECT é a falha condicional "F" (repassada
    # sem conversão). Agregações só produzem números.
    value: ScalarValue
    execution_id: str | None = None
    aggregation_rule_id: str | None = None
    run_date: date | None = None
    # Etapa 3.3A: estado e detalhe do resultado canônico (ver
    # app.domain.results). Não fazem parte da identidade lógica.
    state: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        # Etapa 3.3B: sem valor só com estado (contrato 2.2 §13).
        if self.value is None and self.state is None:
            raise ResultContractError(
                f"{ResultContractError.code}: ForecastValue sem valor e sem estado."
            )

        if self.state is not None and self.state not in RESULT_STATE_TAXONOMY:
            raise ResultContractError(
                f"{ResultContractError.code}: state {self.state!r} fora da "
                f"taxonomia {sorted(RESULT_STATE_TAXONOMY)}."
            )

        if self.detail is not None and not isinstance(self.detail, str):
            raise ResultContractError(
                f"{ResultContractError.code}: detail deve ser texto ou None."
            )

    @property
    def result(self) -> Result:
        """Resultado canônico (value, state, detail) deste valor."""

        return Result(value=self.value, state=self.state, detail=self.detail)

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
