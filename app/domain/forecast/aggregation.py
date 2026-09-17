"""
Representa uma regra de agregação temporal (Fase B).

Uma AggregationRule descreve COMO um ForecastValue de uma frequência
(origem) é derivado em um ForecastValue de outra frequência (destino).
Não representa a execução em si — apenas a regra. A execução é
responsabilidade do TemporalAggregationService.

Não pertence a este modelo:
    - escopo (linha/grupo/planta): é informado na chamada do serviço,
      não faz parte da identidade da regra em si (a mesma regra pode
      ser aplicada a qualquer escopo);
    - frequência da EquationDefinition/EquationInstance: continua
      inexistente nesses modelos, sem alteração pela Fase B.
"""

from dataclasses import dataclass
from datetime import date

from app.engine.exceptions import InvalidAggregationRuleError


AGGREGATION_TYPES = {
    "AVERAGE",
    "SUM",
    "WEIGHTED_AVERAGE",
    "MOVING_AVERAGE",
}


@dataclass(frozen=True)
class AggregationRule:
    """
    Regra de agregação temporal de uma Variable de uma frequência de
    origem para uma frequência de destino.

    `window_start_date`/`window_end_date` são opcionais: quando
    ausentes (o caso comum), a janela é derivada da frequência de
    destino e do run_date da execução (ver
    TimePeriodResolver.effective_window), sempre truncada em
    run_date. Quando informados (tipicamente para MOVING_AVERAGE com
    uma janela explícita que não coincide com um período de
    calendário), prevalecem sobre a derivação automática.
    """

    aggregation_rule_id: str
    source_variable_id: str
    source_frequency: str
    target_variable_id: str
    target_frequency: str
    aggregation_type: str
    weight_variable_id: str | None = None
    window_start_date: date | None = None
    window_end_date: date | None = None

    def __post_init__(self) -> None:
        if self.aggregation_type not in AGGREGATION_TYPES:
            raise InvalidAggregationRuleError(
                "Tipo de agregação não suportado: "
                f"{self.aggregation_type}"
            )

        if (
            self.aggregation_type == "WEIGHTED_AVERAGE"
            and not self.weight_variable_id
        ):
            raise InvalidAggregationRuleError(
                "WEIGHTED_AVERAGE exige weight_variable_id."
            )

        has_start = self.window_start_date is not None
        has_end = self.window_end_date is not None

        if has_start != has_end:
            raise InvalidAggregationRuleError(
                "window_start_date e window_end_date devem ser "
                "informados juntos ou ambos omitidos."
            )

        if (
            has_start
            and has_end
            and self.window_start_date > self.window_end_date
        ):
            raise InvalidAggregationRuleError(
                "window_start_date deve ser anterior ou igual a "
                "window_end_date."
            )


class AggregationRuleRegistry:
    """
    Registry em memória de AggregationRule, indexado por
    `aggregation_rule_id` — mesmo padrão já usado por
    `EquationDefinitionRegistry`/`VariableDefinitionRegistry`/etc.

    Não é um Repository: sem I/O, sem persistência, apenas o
    container que o SeedLoader preenche a partir do seed.
    """

    def __init__(self):
        self._rules: dict[str, AggregationRule] = {}

    def add(self, rule: AggregationRule) -> None:
        if rule.aggregation_rule_id in self._rules:
            raise ValueError(
                "aggregation_rule_id já cadastrado: "
                f"{rule.aggregation_rule_id}"
            )

        self._rules[rule.aggregation_rule_id] = rule

    def get(self, aggregation_rule_id: str) -> AggregationRule:
        return self._rules[aggregation_rule_id]

    def all(self) -> list[AggregationRule]:
        return list(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules.values())
