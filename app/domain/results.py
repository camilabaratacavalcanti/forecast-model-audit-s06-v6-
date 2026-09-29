"""
Contrato canônico de resultado (Etapa 3.3A).

    Result
    ├── value    valor calculado: ScalarValue (numerico int|float;
    │            categorico str; o marcador de falha condicional "F").
    │            Nenhuma conversão: o objeto é preservado. Etapa 3.3B:
    │            None é permitido SOMENTE com state (contrato D2/§13 da
    │            Etapa 2.2: "value presente sse result_state == VALID") —
    │            é o caso de um estado herdado ou traduzido de literal.
    ├── state    None (resultado sem estado declarado) ou um estado da
    │            taxonomia global comprovada RESULT_STATE_TAXONOMY (D2):
    │            NO_APPLICABLE_RULE, INVALID_INPUT, VALIDATION_FAILED.
    │            Nenhum outro texto é estado. Não existe estado "OK"
    │            inventado: ausência de estado é None.
    └── detail   None ou texto complementar DE UM ESTADO, preservado
                 byte a byte (sem strip, sem normalização). Não é erro
                 técnico, log, exceção, nome de variável nem source_block.
                 D33B-03: detail sem state é inválido
                 (DETAIL_WITHOUT_STATE) — não existe semântica para ele.

Combinações válidas (D33B-03):
    state=None,     detail=None     resultado válido
    state=<estado>, detail=None     estado sem complemento
    state=<estado>, detail=<texto>  estado com complemento
    state=None,     detail=<texto>  INVÁLIDO (DetailWithoutStateError)

Igualdade semântica (D33B-04, idempotência): `results_equivalent`.

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
        (Etapa 3.3A; substituída na 3.3B pela propagação causal em
        app.domain.state_propagation; o evaluator direto passa a levantar
        STATED_RESULT_CONSUMED_AS_VALUE.)
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


class DetailWithoutStateError(ResultContractError):
    """D33B-03: detail é complemento de um estado; sem estado é inválido."""

    code = "DETAIL_WITHOUT_STATE"


class AmbiguousResultWindowError(ResultContractError):
    """
    D33B-04: leitura sem janela de um período com mais de uma janela
    efetiva gravada; nenhuma versão é escolhida implicitamente.
    """

    code = "RESULT_WINDOW_AMBIGUOUS"


class StatePropagationPendingError(ResultContractError):
    """Consumo em cálculo de um resultado com state/detail (Etapa 3.3B)."""

    code = "STATE_PROPAGATION_PENDING_STAGE_3.3B"


class StatedResultConsumedAsValueError(ResultContractError):
    """
    Etapa 3.3B: um resultado com state/detail foi lido como valor por um
    ponto que não propaga estado (ex.: o evaluator chamado diretamente).
    A propagação é feita pelo EquationEngine (`calculate_instance_result`).
    """

    code = "STATED_RESULT_CONSUMED_AS_VALUE"


class StatefulResultOnScalarApiError(ResultContractError):
    """
    Uma API que devolve só o valor (legada) foi chamada para um resultado
    com estado e sem valor: o estado não cabe na resposta escalar.
    """

    code = "STATEFUL_RESULT_ON_SCALAR_API"


class StateAwareAggregationPendingError(ResultContractError):
    """Agregação sobre resultados com state/detail (Etapa 3.3C)."""

    code = "STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C"


@dataclass(frozen=True)
class Result:
    value: ScalarValue
    state: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.value is None and self.state is not None:
            pass  # estado sem valor (contrato 2.2 §13)
        elif isinstance(self.value, bool) or not (
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

        require_detail_with_state(self.state, self.detail)

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


def require_detail_with_state(state, detail) -> None:
    """D33B-03: único ponto que valida detail sem estado."""

    if detail is not None and state is None:
        raise DetailWithoutStateError(
            f"{DetailWithoutStateError.code}: detail {detail!r} sem state; "
            "detail só existe como complemento de um estado."
        )


def _value_kind(value) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        return "text"
    return "number"


def results_equivalent(first: Result, second: Result) -> bool:
    """
    Igualdade semântica de dois resultados da MESMA identidade (D33B-04):
    mesmo state (texto exato), mesmo detail (texto exato, byte a byte) e
    mesmo valor. Valor: ambos ausentes; ou ambos texto e iguais; ou ambos
    numéricos e numericamente iguais (value_type "numerico" é um único
    domínio int|float — 2 e 2.0 são o mesmo número). Texto nunca é igual
    a número ("2" != 2) e NaN nunca é igual a nada. Determinístico.
    """

    if first.state != second.state or first.detail != second.detail:
        return False

    kind = _value_kind(first.value)

    if kind != _value_kind(second.value):
        return False

    if kind == "number" and (first.value != first.value or second.value != second.value):
        return False  # NaN

    return first.value == second.value


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
    """
    Proteção do evaluator: um resultado com state/detail nunca é usado
    como número. No caminho do EquationEngine a propagação acontece
    antes da avaliação (Etapa 3.3B), então esta proteção só dispara para
    quem avalia expressões diretamente.
    """

    if not result.is_plain:
        raise StatedResultConsumedAsValueError(
            f"{StatedResultConsumedAsValueError.code}: {variable_id} tem "
            f"state={result.state!r}, detail={result.detail!r}; use o "
            "EquationEngine (calculate_instance_result), que propaga o estado."
        )


def scalar_of(result: Result, where: str):
    """Valor para APIs escalares legadas; estado sem valor é erro explícito."""

    if result.value is None:
        raise StatefulResultOnScalarApiError(
            f"{StatefulResultOnScalarApiError.code}: {where} tem "
            f"state={result.state!r} e não tem valor; use a API de Result."
        )

    return result.value


def require_plain_for_aggregation(variable_id: str, period_id, result: Result) -> None:
    if not result.is_plain:
        raise StateAwareAggregationPendingError(
            f"{StateAwareAggregationPendingError.code}: {variable_id} "
            f"(period_id={period_id!r}) tem state={result.state!r}, "
            f"detail={result.detail!r}; agregação state-aware (Policy B) "
            "pertence à Etapa 3.3C."
        )


__all__ = [
    "AmbiguousResultWindowError",
    "DetailWithoutStateError",
    "Result",
    "ResultContractError",
    "ResultIdentity",
    "ResultValueDomainError",
    "StateAwareAggregationPendingError",
    "StatePropagationPendingError",
    "StatefulResultOnScalarApiError",
    "StatedResultConsumedAsValueError",
    "as_result",
    "check_value_domain",
    "require_plain_for_aggregation",
    "require_detail_with_state",
    "require_plain_for_calculation",
    "results_equivalent",
    "scalar_of",
]
