"""
Validação dimensional das AggregationRule do tipo SUM.

Relata, para cada SUM, se a unidade de destino é a quantidade do
período obtida a partir da taxa de origem com o `integration_factor`
declarado (ver app.domain.units). Apenas relata: não altera regras nem
valores — a decisão de corrigir uma regra (e com qual fator) pertence
ao dono do bloco.
"""

from dataclasses import dataclass

from app.domain.units import check_sum_dimensions


@dataclass(frozen=True)
class SumDimensionIssue:
    aggregation_rule_id: str
    source_unit: str
    target_unit: str
    message: str


def find_sum_dimension_issues(
    rules,
    variable_definition_registry,
) -> list[SumDimensionIssue]:
    issues: list[SumDimensionIssue] = []

    for rule in rules:
        if rule.aggregation_type != "SUM":
            continue

        source_unit = variable_definition_registry.get(
            rule.source_variable_id
        ).unit
        target_unit = variable_definition_registry.get(
            rule.target_variable_id
        ).unit

        message = check_sum_dimensions(
            source_unit,
            target_unit,
            rule.target_frequency,
            rule.integration_factor,
        )

        if message is not None:
            issues.append(
                SumDimensionIssue(
                    rule.aggregation_rule_id,
                    source_unit,
                    target_unit,
                    message,
                )
            )

    return issues
