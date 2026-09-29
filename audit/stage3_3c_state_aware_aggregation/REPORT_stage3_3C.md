# Etapa 3.3C — State-Aware Aggregation / Policy B

## A. Baseline

```text
baseline commit:   4faf5f1 (audit(stage3.3b): closure evidence, mutation check, gate PASS)
branch:            feature/area-41-block
working tree:      limpa
tests before:      1720 passed
```

Caminho mapeado antes da edição:

```text
input Result (CalculationContext, CalculationKey com window_end)
  → TemporalAggregationService.aggregate            [lia via require_plain_for_aggregation:
                                                      estado → STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C]
  → ForecastValue (value; state/detail sempre None)
  → InterblockExecutionOrchestrator._run_aggregation  [gravava set_variable_value(value.value):
                                                      estado perdido na escrita]
  → CalculationContext
  → InterblockValueResolver.transfer_result (Result completo, 3.1)
  → consumer
```

Pontos de perda identificados:

1. a leitura da origem (fronteira 3.3C);
2. a construção do `ForecastValue` (sem state/detail);
3. a gravação no orquestrador (só `value`).

## B. Implementação

| arquivo | mudança |
|---|---|
| `app/domain/state_propagation.py` | `compose_states` (núcleo único da política, O(n), ordenação só para a mensagem de erro); `inherit_from_dependencies` (3.3B) passa a usá-lo; nova `compose_aggregated_result` (Policy B) |
| `app/engine/temporal_aggregation_service.py` | lê cada componente como `(chave, Result)` uma vez (`_read_result`), incluindo os pesos da WEIGHTED_AVERAGE; compõe (1), roda a aritmética existente (2) e constrói o `ForecastValue` com state/detail (3); `_weighted_average` recebe os pesos já lidos |
| `app/engine/interblock_orchestrator.py` | `_run_aggregation` grava `value.result` (Result completo) e registra state/detail no evento; topologia e ordem inalteradas |
| `app/domain/results.py` | `require_plain_for_aggregation` removida; `StateAwareAggregationPendingError` mantida só para compatibilidade de importação, documentada como retirada |

Arquitetura:

```text
compose_aggregated_result(target, components, aggregate)
  1. semântica: compose_states(components)   → erro de composição antes de qualquer matemática
  2. matemática: aggregate()                  → a aritmética existente, inalterada
                 só se TODO componente tem value
  3. Result(value, state, detail)
```

Agregadores do runtime, todos cobertos: AVERAGE, SUM (com `integration_factor`), WEIGHTED_AVERAGE (pesos são componentes semânticos) e MOVING_AVERAGE. MIN, MAX e COUNT não existem no runtime e não foram criados.

## C. Semântica

| Cenário | Resultado |
|---|---|
| nenhum state | `Result(v)`, state/detail None |
| state único (repetido) | `Result(v, S)` |
| state + None | `Result(v, S)`: None é ausência, não conflito |
| states diferentes | `MULTI_STATE_COMBINATION_UNDEFINED` |
| mesmo state/detail | `Result(v, S, D)` |
| mesmo state/details diferentes | `MULTI_DETAIL_COMPOSITION_UNDEFINED` |
| state + None/text detail | `MULTI_DETAIL_COMPOSITION_UNDEFINED` |
| componente com state e **sem value** (ex.: estado herdado na 3.3B) | `Result(None, S, D)`: sem aritmética, nenhum componente descartado, denominador nunca alterado |
| janela vazia | `EmptyAggregationWindowError` (contrato existente, inalterado) |
| `"F"` / texto / pesos com soma 0 | `AggregationFailureError` / `NonNumericAggregationError` / `ZeroWeightSumError` (inalterados) |
| conflito semântico + erro matemático | o conflito semântico vence (a composição roda antes) |

Decisão registrada, sem estado novo: o value agregado é `None` quando algum componente não tem value. É a única representação que não fabrica número e já é válida no contrato, porque exige state. Sem ela seria preciso descartar componentes, o que muda o denominador, ou converter state em value; as duas opções são proibidas.

## D. Testes

```text
unit tests:          tests/test_stage3_3c_state_aware_aggregation.py — 100 testes
                     (13 cenários × 5 configurações de agregador, ordem, erros de
                     ordem, vazio, sem value, pesos, erros matemáticos, precedência,
                     compose_aggregated_result, sem estados/prioridade)
integration tests:   orquestrador sintético (interbloco, janelas, períodos,
                     reexecução/conflito) + cadeia real VAR18010; hash seeds
black-box cases:     3686 linhas (3645 combinações ordenadas × 5 agregadores, vazio,
                     "F", texto, F+conflito, detail sem state, pesos, pesos zero,
                     4 cadeias reais)
mutation tests:      13 mutantes
mutations detected:  13 (cada um por testes E auditoria)
mutations survived:  0
```

| mutante | detecção |
|---|---|
| M1 descartar state (composição) | testes + auditoria |
| M1b descartar state (serviço) | testes + auditoria |
| M1c gravar só value (orquestrador) | testes + auditoria |
| M2 first state wins | testes + auditoria |
| M3 last state wins | testes + auditoria |
| M4 first detail wins | testes + auditoria |
| M5 ignorar conflito de detail | testes + auditoria |
| M6 None como state | testes + auditoria |
| M7 dependente de ordem | testes + auditoria |
| M8 descartar detail | testes + auditoria |
| M9a semântica sem os pesos | testes + auditoria |
| M9b semântica só do último dia (a matemática usa a janela) | testes + auditoria |
| M9c matemática ignorando componente sem value | testes + auditoria |

## E. Determinismo

- Testes 3.3B + 3.3B-closure + 3.3C (200) com `PYTHONHASHSEED` 0, 1, 4242 e 987654321: 200 passed em todos.
- `test_hash_seed_determinism` (3.3C): mesmo SHA-256 da matriz completa de resultados e erros nos 4 seeds.
- Sonda da auditoria com `PYTHONHASHSEED` 0 e 4242: saída byte a byte idêntica (hashes em `evidence/determinism_check.txt`).
- Ordem: as 825 classes de permutação do sweep têm o mesmo state/detail/erro. O value também é o mesmo, exceto na WEIGHTED_AVERAGE, onde cada valor é pareado ao peso do seu dia. Com pares valor/peso preservados, o value também não muda (teste 21.10).

## F. Regressão

```text
tests before:  1720
tests after:   1820
passed:        1820
failed:        0
skipped:       0
```

| Gate | Resultado |
|---|---|
| 2.6C | PASS |
| 3.1 | PASS |
| 3.2 | PASS |
| 3.3A | PASS |
| 3.3B | PASS (auditoria 742 linhas; mutações 3.3B 6/6) |

Expectativas legadas atualizadas (`LEGACY_TEST_EXPECTATION`, justificativa no código; nenhum teste removido). Todas codificavam a fronteira retirada `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C`:

- `test_stage3_3a_result_contract.py::test_aggregation_over_a_stated_result_*`: agora o state e o detail são preservados;
- `test_stage3_3b_state_propagation.py::test_32`: agora compõe; `::test_34`: o consumidor mensal recebe o estado;
- `test_stage3_3b_closure.py::test_no_new_states_and_no_policy_b`: o serviço usa a composição central;
- auditoria 3.3B, cenário S7: o oráculo agora compõe (VAR12002 herda o estado); evidência regenerada.

## G. Interblock

Sintético (`test_21_13`), com a janela até 2026-09-02:

```text
source P_out VAR12902 L2:  09-01 Result(10.0, INVALID_INPUT, "d1")   09-02 Result(30.0, INVALID_INPUT, "d1")
aggregated  P_mes VAR12903 L2 (2026-09): Result(20.0, INVALID_INPUT, "d1")
→ transfer
consumer    E_mes VAR18901 L2 (2026-09): Result(20.0, INVALID_INPUT, "d1")
L3 (componente sem value): Result(None, VALIDATION_FAILED, "v") → idem no consumidor
```

Real (seeds, REAL_DERIVED): AGR-PRODUCTION-LTH_TOTAL (AVERAGE diário→mensal) → energy VAR18010. O consumidor recebe `Result(100+k, INVALID_INPUT, "lth")` (teste) e, na auditoria, value/state/detail iguais ao produtor em cada identidade (C1, C4).

## H. Temporalidade

- Mesma janela, reexecução: store inalterado, transferências `UNCHANGED` (`test_21_15`; auditoria C1 passo 3).
- Mesmo período, janelas diferentes: `2026-09` até 09-01 = `Result(10.0, S, "a")` e até 09-02 = `Result(15.0, S, "a")` coexistem (`test_21_14`; C1).
- Períodos diferentes: `2026-10` = `Result(5.0, VALIDATION_FAILED)` independente (`test_21_14`; C1).
- Mesma identidade, Result diferente: a agregação recalcula, como sempre fez (write-once não foi estendido). A transferência detecta `INTERBLOCK_CONSUMER_VALUE_CONFLICT` e o consumidor mantém o anterior (`test_21_15`; C2).
- `period_id` e `window_end` vêm da `CalculationKey` inalterada.

## I. Alterações proibidas

```text
workbooks:       unchanged
seeds:           unchanged
taxonomy:        unchanged
IDs:             unchanged
formulas:        unchanged
units:           unchanged
fonte:           unchanged
source_block:    unchanged
CalculationKey:  unchanged
```

A auditoria verifica que nada em `data/`, `tools/`, `app/domain/values.py`, `app/domain/interblock/`, `time_period_resolver.py`, `calculation_context.py` ou `app/domain/forecast/aggregation.py` foi alterado desde `4faf5f1`. Nenhum estado novo e nenhuma prioridade de estados foram criados.

Performance: uma leitura por componente, composição O(n) por conjuntos; a ordenação só ocorre para montar mensagens de erro.

## J. Gate

STAGE_3.3C_GATE: PASS
