"""
Propagação causal e isolamento de estados (Etapa 3.3B).

Base normativa (não inventada aqui):

    D1 (Etapa 2.2, §6.3/§6.4)  um literal da fórmula (ex.: "F") só é
        estado para a variável ALVO que o declara em
        `declared_result_states`; a tradução é por variável, nunca global.
    D2 (§12/§13)  value presente sse o resultado é VALID (sem estado);
        um estado herdado ou traduzido não tem valor.
    D3 (§16) + R1 (Etapa 2.3)  o estado propaga como dado aos
        descendentes ALCANÇÁVEIS pelo grafo de dependências; nós não
        alcançáveis não são afetados; o herdeiro não redeclara o estado.

Três funções, únicas e centrais:

    translate_declared_literal(value, target_definition)
        valor calculado -> Result; literal declarado pela própria
        variável alvo vira Result(None, <estado>); qualquer outro valor
        (inclusive "F" numa variável que não o declara) fica como está.

    inherit_from_dependencies(target, dependencies)
        estado herdado das dependências REAIS de uma equação (as
        referências da própria expressão, resolvidas pela mesma regra do
        evaluator). Nenhuma dependência com estado -> None (calcula
        normalmente). Um único estado -> Result(None, estado, detail).

    As combinações sem contrato são erro explícito, nunca prioridade
    escolhida aqui:
        MULTI_STATE_COMBINATION_UNDEFINED   estados diferentes
        MULTI_DETAIL_COMPOSITION_UNDEFINED  mesmo estado, details diferentes
        DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED  dependência com detail
                                            e sem estado

Isolamento: a propagação só percorre dependências reais; bloco,
instância, período ou execução em comum não propagam nada. Agregação
temporal state-aware continua fora (STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C).
"""

from __future__ import annotations

from app.domain.results import Result, ResultContractError


class MultiStateCombinationUndefinedError(ResultContractError):
    code = "MULTI_STATE_COMBINATION_UNDEFINED"


class MultiDetailCompositionUndefinedError(ResultContractError):
    code = "MULTI_DETAIL_COMPOSITION_UNDEFINED"


class DetailWithoutStatePropagationUndefinedError(ResultContractError):
    code = "DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED"


def translate_declared_literal(value, target_definition) -> Result:
    """
    Tradução D1, por variável. Sem definição conhecida (callers legados)
    ou sem `declared_result_states`, o valor é preservado como está.
    """

    declared = getattr(target_definition, "declared_result_states", None)

    if declared and isinstance(value, str):
        for declared_state in declared:
            if value == declared_state.literal:
                return Result(value=None, state=declared_state.state)

    return Result(value=value)


def _origin(key) -> str:
    variable_id, scope_type, scope_value, period_id = key
    return f"{variable_id}[{scope_type}/{scope_value}@{period_id}]"


def inherit_from_dependencies(target_variable_id: str, dependencies) -> Result | None:
    """
    `dependencies`: pares (chave, Result) das dependências reais da
    equação, chave = (variable_id, scope_type, scope_value, period_id).
    Resultado independente da ordem dos operandos.
    """

    stated = []

    for key, result in dependencies:
        if result.state is not None:
            stated.append((key, result))
        elif result.detail is not None:
            raise DetailWithoutStatePropagationUndefinedError(
                f"{DetailWithoutStatePropagationUndefinedError.code}: "
                f"{target_variable_id} depende de {_origin(key)} com detail "
                f"{result.detail!r} e sem estado; o contrato não define se esse "
                "detail propaga."
            )

    if not stated:
        return None

    origins = sorted(_origin(key) for key, _result in stated)
    states = sorted({result.state for _key, result in stated})

    if len(states) > 1:
        raise MultiStateCombinationUndefinedError(
            f"{MultiStateCombinationUndefinedError.code}: {target_variable_id} "
            f"depende de estados diferentes {states} (origens {origins}); o "
            "contrato não define como combiná-los — nenhuma prioridade é escolhida."
        )

    details = {result.detail for _key, result in stated}

    if len(details) > 1:
        raise MultiDetailCompositionUndefinedError(
            f"{MultiDetailCompositionUndefinedError.code}: {target_variable_id} "
            f"herda {states[0]} de {origins} com details diferentes "
            f"{sorted(details, key=lambda d: (d is None, d or ''))}; composição "
            "de details não definida pelo contrato."
        )

    return Result(value=None, state=states[0], detail=details.pop())


__all__ = [
    "DetailWithoutStatePropagationUndefinedError",
    "MultiDetailCompositionUndefinedError",
    "MultiStateCombinationUndefinedError",
    "inherit_from_dependencies",
    "translate_declared_literal",
]
