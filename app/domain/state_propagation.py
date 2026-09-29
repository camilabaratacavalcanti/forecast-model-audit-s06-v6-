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
        estado herdado das dependências EXECUTADAS de uma equação: os
        operandos com estado efetivamente consumidos pela avaliação
        normal (ExpressionEvaluator.evaluate_with_state). Um ramo de IF
        não escolhido não é executado e não contribui. Um único estado
        -> Result(None, estado, detail).

    Contrato fechado (Etapa 3.3B, decisões D33B-01..03):
        D33B-01  estados diferentes -> MULTI_STATE_COMBINATION_UNDEFINED
                 (sem prioridade, sem primeiro/último, sem estado novo)
        D33B-02  mesmo estado, details diferentes ->
                 MULTI_DETAIL_COMPOSITION_UNDEFINED (sem concatenação,
                 sem escolha). Mesmo estado e mesmo detail (inclusive
                 todos None) -> propaga. None e um texto são details
                 diferentes: o contrato não define compatibilidade entre
                 "sem complemento" e um complemento.
        D33B-03  detail sem estado é inválido já na construção do Result
                 (DETAIL_WITHOUT_STATE, app.domain.results) — não chega
                 aqui.

Isolamento: a propagação só percorre dependências executadas; bloco,
instância, período ou execução em comum não propagam nada.

Etapa 3.3C (Policy B): a agregação temporal usa o MESMO núcleo
(`compose_states`) via `compose_aggregated_result`; a fronteira
STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C deixa de existir.
"""

from __future__ import annotations

from app.domain.results import Result, ResultContractError


class MultiStateCombinationUndefinedError(ResultContractError):
    code = "MULTI_STATE_COMBINATION_UNDEFINED"


class MultiDetailCompositionUndefinedError(ResultContractError):
    code = "MULTI_DETAIL_COMPOSITION_UNDEFINED"


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


def _raise_multi_state(target_variable_id: str, present: dict) -> None:
    states = sorted(present)
    origins = sorted(
        _origin(key) for details in present.values() for keys in details.values() for key in keys
    )
    raise MultiStateCombinationUndefinedError(
        f"{MultiStateCombinationUndefinedError.code}: {target_variable_id} "
        f"depende de estados diferentes {states} (origens {origins}); o "
        "contrato não define como combiná-los — nenhuma prioridade é escolhida."
    )


def _raise_multi_detail(target_variable_id: str, state: str, details: dict) -> None:
    origins = sorted(_origin(key) for keys in details.values() for key in keys)
    raise MultiDetailCompositionUndefinedError(
        f"{MultiDetailCompositionUndefinedError.code}: {target_variable_id} "
        f"herda {state} de {origins} com details diferentes "
        f"{sorted(details, key=lambda d: (d is None, d or ''))}; composição "
        "de details não definida pelo contrato."
    )


def compose_states(target_variable_id: str, components) -> tuple | None:
    """
    Núcleo ÚNICO da política de composição (D33B-01/02, reutilizado pela
    agregação da Etapa 3.3C). `components`: pares (chave, Result).

        present_states = {estados efetivamente presentes}; None é
        ausência de estado, nunca um estado conflitante.
        0 estados              -> None
        1 estado, 1 detail     -> (estado, detail)   (detail pode ser None)
        >1 estado              -> MULTI_STATE_COMBINATION_UNDEFINED
        1 estado, >1 detail    -> MULTI_DETAIL_COMPOSITION_UNDEFINED
                                  (None e texto são details diferentes)

    Uma passada O(n) com conjuntos; ordenação só para montar a mensagem
    de erro — o resultado e o erro independem da ordem dos componentes.
    """

    present: dict = {}

    for key, result in components:
        if result.state is not None:
            present.setdefault(result.state, {}).setdefault(result.detail, []).append(key)

    if not present:
        return None

    states = list(present)

    if len(states) > 1:
        _raise_multi_state(target_variable_id, present)

    state = states[0]
    details = list(present[state])

    if len(details) > 1:
        _raise_multi_detail(target_variable_id, state, present[state])

    return state, details[0]


def inherit_from_dependencies(target_variable_id: str, dependencies) -> Result | None:
    """
    `dependencies`: pares (chave, Result) das dependências executadas
    da equação, chave = (variable_id, scope_type, scope_value, period_id).
    Resultado independente da ordem dos operandos.
    """

    composed = compose_states(target_variable_id, dependencies)

    if composed is None:
        return None

    state, detail = composed

    return Result(value=None, state=state, detail=detail)


def compose_aggregated_result(target_variable_id: str, components, aggregate) -> Result:
    """
    Policy B (Etapa 3.3C) — resultado de uma agregação sobre Results.

        1. semântica: `compose_states` sobre TODOS os componentes
           consumidos (valores de origem e, quando houver, pesos); um
           conflito é erro antes de qualquer matemática;
        2. matemática: `aggregate()` (a aritmética existente do
           agregador, sem alteração) só é chamada se TODO componente tem
           value. Um componente com estado e sem value (contrato 2.2 §13,
           ex.: estado herdado na 3.3B) não é número: nenhuma aritmética
           é feita, nenhum componente é descartado (o denominador nunca
           muda) e o value agregado é None — o que só é possível porque
           esse componente tem estado;
        3. Result(value, state, detail).

    Nunca escolhe estado ou detail, nunca converte estado em value.
    """

    composed = compose_states(target_variable_id, components)

    if any(result.value is None for _key, result in components):
        value = None
    else:
        value = aggregate()

    if composed is None:
        return Result(value=value)

    state, detail = composed

    return Result(value=value, state=state, detail=detail)


__all__ = [
    "MultiDetailCompositionUndefinedError",
    "MultiStateCombinationUndefinedError",
    "compose_aggregated_result",
    "compose_states",
    "inherit_from_dependencies",
    "translate_declared_literal",
]
