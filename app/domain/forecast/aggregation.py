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
    # Conversão dimensional de uma SUM de taxas (ver app.domain.units):
    # cada valor diário é multiplicado pelo fator antes da soma (ex.:
    # 24 para kg/h -> kg/mês). 1.0 (padrão) mantém a soma simples de
    # todas as regras existentes. Só SUM pode declarar outro valor.
    integration_factor: float = 1.0

    def __post_init__(self) -> None:
        if self.aggregation_type not in AGGREGATION_TYPES:
            raise InvalidAggregationRuleError(
                "Tipo de agregação não suportado: "
                f"{self.aggregation_type}"
            )

        if (
            isinstance(self.integration_factor, bool)
            or not isinstance(self.integration_factor, (int, float))
            or not self.integration_factor > 0
        ):
            raise InvalidAggregationRuleError(
                "integration_factor deve ser um número positivo: "
                f"{self.integration_factor!r}"
            )

        if (
            self.integration_factor != 1
            and self.aggregation_type != "SUM"
        ):
            raise InvalidAggregationRuleError(
                "integration_factor só se aplica a SUM "
                f"(regra {self.aggregation_rule_id} é "
                f"{self.aggregation_type})."
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


@dataclass(frozen=True)
class AggregationRuleInstance:
    """
    Aplicação concreta de uma AggregationRule em UM escopo resolvido.

    A AggregationRule é lógica (não carrega escopo). Uma definição
    `linha/L1_L7` materializa 7 VariableInstances; a regra que a agrega
    materializa, pelo mesmo ScopeResolver, uma AggregationRuleInstance
    por escopo concreto — 7 séries independentes, cada uma com seu
    próprio escopo, em vez de uma regra única cujo escopo dependeria
    de quem a chama.
    """

    aggregation_rule_instance_id: str
    rule: AggregationRule
    scope_type: str | None
    scope_value: str | None

    @classmethod
    def create(
        cls,
        rule: AggregationRule,
        scope_type: str | None,
        scope_value: str | None,
    ) -> "AggregationRuleInstance":
        instance_id = (
            f"{rule.aggregation_rule_id}@{scope_value}"
            if scope_value
            else rule.aggregation_rule_id
        )

        return cls(
            aggregation_rule_instance_id=instance_id,
            rule=rule,
            scope_type=scope_type,
            scope_value=scope_value,
        )


class AggregationRuleInstanceRegistry:
    """Registry em memória de AggregationRuleInstance."""

    def __init__(self):
        self._instances: dict[str, AggregationRuleInstance] = {}

    def add(self, instance: AggregationRuleInstance) -> None:
        if instance.aggregation_rule_instance_id in self._instances:
            raise ValueError(
                "aggregation_rule_instance_id já cadastrado: "
                f"{instance.aggregation_rule_instance_id}"
            )

        self._instances[instance.aggregation_rule_instance_id] = instance

    def get(self, aggregation_rule_instance_id: str) -> AggregationRuleInstance:
        return self._instances[aggregation_rule_instance_id]

    def all(self) -> list[AggregationRuleInstance]:
        return list(self._instances.values())

    def for_rule(self, aggregation_rule_id: str) -> list[AggregationRuleInstance]:
        return [
            instance
            for instance in self._instances.values()
            if instance.rule.aggregation_rule_id == aggregation_rule_id
        ]

    def __len__(self) -> int:
        return len(self._instances)

    def __iter__(self):
        return iter(self._instances.values())


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
