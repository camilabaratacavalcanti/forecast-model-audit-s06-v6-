"""
Contrato canônico de resultado (Etapa 3.3A).

    Result
    ├── value    valor calculado: ScalarValue (numerico int|float;
    │            categorico str; o marcador de falha condicional "F").
    │            Nenhuma conversão: o objeto é preservado.
    ├── state    None (resultado sem estado declarado) ou um estado da
    │            taxonomia global comprovada RESULT_STATE_TAXONOMY (D2):
    │            NO_APPLICABLE_RULE, INVALID_INPUT, VALIDATION_FAILED.
    │            Nenhum outro texto é estado. Não existe estado "OK"
    │            inventado: ausência de estado é None.
    └── detail   None ou texto complementar associado ao resultado,
                 preservado byte a byte (sem strip, sem normalização).
                 Não é erro técnico, log, exceção, nome de variável nem
                 source_block.

Compatibilidade centralizada: `as_result(x)` é o ÚNICO ponto que
converte a representação legada (um ScalarValue, ex.: 42) no contrato
mínimo `Result(value=42)`. Um `Result` passa inalterado.

Identidade (inalterada, Etapa 3.1/3.2): o resultado é armazenado no
CalculationContext na chave (variável, scope_type, scope_value,
period_id); a frequência é a da definição da variável e se expressa na
granularidade do period_id. `ResultIdentity` torna essa identidade
explícita. Proveniência (run_date, execution_id) NÃO faz parte da
identidade — é a base para a decisão futura sobre reexecução (D32-02),
sem mudar a chave.

Domínio de valores (`allowed_values`): é o domínio do VALOR de variáveis
categóricas (contrato 2.4: `allowed_values` só existe em value_type
categorico). A validação é `check_value_domain`, única e reutilizada por
qualquer ponto que grave um resultado com a definição conhecida. O
marcador "F" não é valor de negócio e não é validado contra o domínio
(regra existente do CalculationContext).

Fronteiras explícitas (não implementadas nesta etapa, sem default):

    STATE_PROPAGATION_PENDING_STAGE_3.3B
        uma equação que lê um resultado com state/detail não tem
        semântica definida -> erro explícito, nunca descarte silencioso.
    STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C
        uma agregação sobre resultados com state/detail não tem regra
        definida (Policy B) -> erro explícito.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.values import (
    RESULT_STATE_TAXONOMY,
    ScalarValue,
    is_conditional_failure,
    is_numeric,
)


class ResultContractError(Exception):
    """
    Violação do contrato value/state/detail. Não é ValueError de
    propósito: nunca é confundida com erro matemático nem reembalada
    como falha de avaliação — sempre chega ao chamador com seu código.
    """

    code = "RESULT_CONTRACT_INVALID"


class ResultValueDomainError(ResultContractError):
    """Valor fora de `allowed_values` da variável."""

    code = "RESULT_VALUE_OUTSIDE_ALLOWED_VALUES"


class StatePropagationPendingError(ResultContractError):
    """Consumo em cálculo de um resultado com state/detail (Etapa 3.3B)."""

    code = "STATE_PROPAGATION_PENDING_STAGE_3.3B"


class StateAwareAggregationPendingError(ResultContractError):
    """Agregação sobre resultados com state/detail (Etapa 3.3C)."""

    code = "STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C"


@dataclass(frozen=True)
class Result:
    value: ScalarValue
    state: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not (
            is_numeric(self.value) or isinstance(self.value, str)
        ):
            raise ResultContractError(
                f"{self.code_prefix()}value deve ser numérico ou texto, "
                f"recebido {type(self.value).__name__} {self.value!r}."
            )

        if self.state is not None and self.state not in RESULT_STATE_TAXONOMY:
            raise ResultContractError(
                f"{self.code_prefix()}state {self.state!r} fora da taxonomia "
                f"{sorted(RESULT_STATE_TAXONOMY)}."
            )

        if self.detail is not None and not isinstance(self.detail, str):
            raise ResultContractError(
                f"{self.code_prefix()}detail deve ser texto ou None, "
                f"recebido {type(self.detail).__name__}."
            )

    @staticmethod
    def code_prefix() -> str:
        return f"{ResultContractError.code}: "

    @property
    def is_plain(self) -> bool:
        """Resultado sem state nem detail (contrato mínimo = valor legado)."""

        return self.state is None and self.detail is None


@dataclass(frozen=True)
class ResultIdentity:
    variable_id: str
    scope_type: str | None
    scope_value: str | None
    frequency: str | None
    period_id: str | None


def as_result(value) -> Result:
    """Único ponto de compatibilidade: ScalarValue legado -> Result."""

    if isinstance(value, Result):
        return value

    return Result(value=value)


def check_value_domain(variable_id: str, value, allowed_values) -> None:
    """
    `allowed_values` presente: o valor (texto de negócio) precisa ser uma
    das opções. Ausente: nenhuma validação artificial. O marcador "F"
    não é valor de negócio e segue a regra existente (aceito).
    """

    if allowed_values is None or is_conditional_failure(value):
        return

    if not isinstance(value, str) or value not in allowed_values:
        raise ResultValueDomainError(
            f"{ResultValueDomainError.code}: {variable_id} = {value!r} fora de "
            f"allowed_values {list(allowed_values)}."
        )


def require_plain_for_calculation(variable_id: str, result: Result) -> None:
    if not result.is_plain:
        raise StatePropagationPendingError(
            f"{StatePropagationPendingError.code}: {variable_id} tem "
            f"state={result.state!r}, detail={result.detail!r}; a semântica de "
            "consumo de estados em equações pertence à Etapa 3.3B."
        )


def require_plain_for_aggregation(variable_id: str, period_id, result: Result) -> None:
    if not result.is_plain:
        raise StateAwareAggregationPendingError(
            f"{StateAwareAggregationPendingError.code}: {variable_id} "
            f"(period_id={period_id!r}) tem state={result.state!r}, "
            f"detail={result.detail!r}; agregação state-aware (Policy B) "
            "pertence à Etapa 3.3C."
        )


__all__ = [
    "Result",
    "ResultContractError",
    "ResultIdentity",
    "ResultValueDomainError",
    "StateAwareAggregationPendingError",
    "StatePropagationPendingError",
    "as_result",
    "check_value_domain",
    "require_plain_for_aggregation",
    "require_plain_for_calculation",
]
