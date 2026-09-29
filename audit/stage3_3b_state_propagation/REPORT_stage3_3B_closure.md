# Etapa 3.3B — Fechamento: contrato de estados, propagação causal e identidade temporal

Continuação de `REPORT_stage3_3B.md`, cujo gate foi `READY_FOR_DECISION`. Este relatório fecha as decisões D33B-01..04 e resolve D32-02.

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| commit inicial | `06a7907` — audit(stage3.3b): state propagation evidence, gate READY_FOR_DECISION |
| árvore | limpa |
| suíte | 1674 passed |
| relatórios lidos | 2.6C, 3.1, 3.2 (D32-01/D32-02, §11), 3.3A, 3.3B; contrato 2.2 (D1–D4, commit `5c8dcfc`); R1 |

Arquitetura mapeada antes da edição:

- `app/domain/results.py`: `Result`, erros de contrato.
- `app/domain/state_propagation.py`: tradução e herança.
- `app/engine/expression_evaluator.py`: avaliação da AST com fallback espacial e temporal.
- `app/engine/equation_engine.py`: `calculate_instance_result`.
- `app/engine/forecast_engine.py`.
- `app/engine/interblock_resolver.py`: `transfer_result` com conflito da 3.1.
- `app/engine/interblock_orchestrator.py`: plano e execução.
- `app/engine/calculation_context.py`: armazenamento canônico `_scoped_results` por `CalculationKey`.
- `app/engine/time_period_resolver.py`: `effective_window`.

## 2. D33B-01 — estados diferentes

- **Decisão:** estados diferentes vindos de dependências causais levantam `MULTI_STATE_COMBINATION_UNDEFINED`. Não há prioridade, primeiro ou último, ordenação com escolha, concatenação ou estado novo.
- **Implementação:** `inherit_from_dependencies` (único ponto). As origens ficam ordenadas pela chave, então a mensagem independe da ordem.
- **Testes:**
  - `test_d33b_01_*`: os 6 pares ordenados de estados, em ambas as ordens, com mensagem idêntica;
  - `test_without_if_every_operand_is_executed`;
  - 3.3B: testes 20, 21 e 24.
- **Evidência:**
  - auditoria S4 (real: `"F"` em L4_L5 + INVALID_INPUT em VAR16017 L1 → VAR16034) → `MULTI_STATE_COMBINATION_UNDEFINED`;
  - mutação M1 (escolher um estado) é detectada.

## 3. D33B-02 — mesmo estado, details diferentes

- **Decisão:**
  - mesmo estado com mesmo detail (inclusive todos `None`) propaga;
  - details diferentes levantam `MULTI_DETAIL_COMPOSITION_UNDEFINED`, sem concatenação e sem escolha;
  - `None` e um texto são details **diferentes**. O contrato não define compatibilidade entre "sem complemento" e um complemento, então a regra 3 (details diferentes → erro) se aplica.
- **Testes:**
  - `test_d33b_02_*`: ("a","b"), ("a",None), (None,"b") e ("a","a ") em ambas as ordens;
  - `test_same_state_*`;
  - 3.3B: testes 22 e 23.
- **Evidência:**
  - auditoria S5 → erro;
  - auditoria S6 (mesmo detail) → propaga;
  - mutação M2 (escolher um detail) é detectada, inclusive como não-determinismo entre hash seeds.

## 4. D33B-03 — detail sem state

- **Decisão:** detail só existe como complemento de um estado.

  | state | detail | resultado |
  |---|---|---|
  | None | None | válido |
  | estado | None | válido |
  | estado | texto | válido |
  | None | texto | **inválido**: `DETAIL_WITHOUT_STATE` (`DetailWithoutStateError`) |

- **Implementação:**
  - `require_detail_with_state` (único ponto) é chamado por `Result.__post_init__` e `ForecastValue.__post_init__`;
  - como `Result` é imutável, nenhum armazenamento, transformação ou transferência consegue produzir a combinação;
  - o ramo `DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED` da propagação foi removido, porque ficou inalcançável.
- **Testes:**
  - `test_d33b_03_*`: as 4 combinações em `Result` e `ForecastValue`; a gravação no contexto é rejeitada e nada é gravado;
  - 3.3B: teste 25.
- **Evidência:** auditoria `D33B03_*` (construção + gravação); mutação M6 detectada.

## 5. Propagação causal

- **Antes:** `ExpressionEvaluator.dependency_results` percorria **todas** as referências da AST (dependência estrutural). Se alguma tinha estado, o alvo herdava sem avaliar. Um ramo de IF não escolhido contaminava o resultado.
- **Problema:** dependência estrutural ≠ dependência executada.
  - `IF(c, A, B)` com `c` escolhendo `A` herdava o estado de `B`.
  - Com dois estados em ramos diferentes, o resultado virava `MULTI_STATE` indevido.
- **Depois:** uma única avaliação normal (`evaluate_with_state`); o parser e a semântica matemática não mudaram.
  - Uma dependência lida com estado vira `StatedOperand`, nunca um número.
  - Toda operação que o consome (aritmética, função, comparação, condição) devolve um `StatedOperand` com a união das origens.
  - A avaliação segue a ordem e o curto-circuito existentes, então só as dependências **executadas** chegam a `inherit_from_dependencies`.

  | construção | regra |
  |---|---|
  | IF, condição sem estado | só o ramo escolhido é avaliado |
  | IF, condição com estado | nenhum ramo é executado; herda o estado da condição |
  | and/or | operando com estado interrompe o curto-circuito |
  | sem IF | todos os operandos são executados |

- `evaluate()` (chamada direta) continua nunca usando estado como valor: `STATED_RESULT_CONSUMED_AS_VALUE` só ocorre se o estado foi de fato consumido.
- **Casos testados** (`tests/test_stage3_3b_closure.py`):
  1. ramo ativo com estado;
  2. ramo inativo com estado → `None`;
  3. dois estados em ramos diferentes → só o ativo, sem `MULTI_STATE`;
  4. condição dinâmica alternando entre dias;
  5. IF aninhado (3 combinações);
  6. cadeia interbloco após IF.

  Também: condição com estado, curto-circuito e o caso real EQ16011, em que `desconto_retirada_41d` só está no ramo "1 By pass".
- **Evidência:**
  - S9: ramo inativo real (VAR16022) → nada propaga;
  - S10: ramo ativo → propaga;
  - S11: estado no ramo inativo + VALIDATION_FAILED em outra origem → só VALIDATION_FAILED, sem `MULTI_STATE`;
  - mutação M3 (propagação estrutural) é detectada.

## 6. D33B-04 — identidade temporal (D32-02)

**Identidade anterior:** `CalculationKey(entity_id, scope_type, scope_value, period_id)`.

**Problema D32-02:** o resultado mensal efetivo de "2026-09" é a média na janela truncada em `run_date` (`TimePeriodResolver.effective_window`: start = dia 1, end = `run_date`). "2026-09 até 09-01" e "2026-09 até 09-02" são resultados diferentes com o mesmo `period_id`. A segunda execução no mesmo contexto encontrava o consumidor com o valor da outra janela e dava `INTERBLOCK_CONSUMER_VALUE_CONFLICT`. Os períodos diários já coexistiam.

**Identidade final:**

```text
CalculationKey(entity_id, scope_type, scope_value, period_id, window_end)
```

- **Dimensões:**
  - variável;
  - instância (`scope_type`, `scope_value`);
  - período (`period_id`);
  - `window_end`: fim da janela efetiva, só para período mensal/anual que contém `run_date`.
- `window_end` não é dimensão inventada: é o `end_date` do `TimePeriod` efetivo que já definia o cálculo.
- Diário, período inteiro (ex.: entrada anual) e execuções fora do orquestrador: `window_end=None`, como antes. `state` e `detail` não participam da identidade.
- **Integração:**
  - `InterblockExecutionOrchestrator.execute` roda dentro de `context.effective_window(run_date)`; ordem, nós e topologia inalterados;
  - mesmo armazenamento (`_scoped_results`); `_windows` é só um índice das chaves;
  - nenhum `context.clear()`.
- **Leitura:**
  - dentro da janela: a versão da janela; senão o valor do período inteiro;
  - fora de janela: o período inteiro; senão a **única** janela;
  - mais de uma janela → `RESULT_WINDOW_AMBIGUOUS` (informe `as_of`); nunca escolhe uma versão.
- **Igualdade semântica (`results_equivalent`):**
  - `state` e `detail` exatos;
  - valor ausente/ausente, texto/texto `==`, ou número/número `==`;
  - `2 == 2.0` (um único domínio numérico), `"2" != 2`, NaN nunca igual.

**Reexecução e conflito:**

| situação | comportamento |
|---|---|
| mesma identidade + resultado equivalente | idempotente (`UNCHANGED`) |
| mesma identidade + resultado diferente | `INTERBLOCK_CONSUMER_VALUE_CONFLICT`, sem sobrescrita |
| janelas/períodos diferentes | coexistem |

**Testes temporais** (sintético, `tests/test_stage3_3b_closure.py`):
- A: períodos diferentes;
- B: mesmo resultado;
- C: resultado diferente → conflito;
- D: P1 → P2 → P3 acessíveis;
- E: P3 → P1 → P2 e P2 → P3 → P1 geram contexto idêntico ao da ordem natural;
- F: P1 → P2 → P1 idempotente;
- G: produtor e consumidor em P1/P2 sem conflito.

Também: estado num período não vaza para outro, leitura ambígua é explícita, valores de período inteiro são preservados e hash seed é determinístico.

**Testes interbloco** (auditoria, real):
- T1: VAR18010 (agregação mensal → energy mensal), VAR16008 (cadeia diária) e VAR18011 (anual) em 09-01..03 no mesmo contexto. Janelas {01, 02, 03}, cada consumidor igual ao produtor na mesma identidade, valores mensais distintos por janela.
- T2: P1 → P2 → P1 idempotente, contexto idêntico ao de P1 → P2.
- T3: ordem embaralhada gera o mesmo contexto.
- T4: produtor alterado no mesmo período → conflito, consumidor preservado.
- Mutações detectadas: M4 (remover a janela) e M5 (sobrescrita silenciosa).

## 7. Regressão

| Gate | Resultado |
| ---- | --------- |
| 2.6C | PASS (auditoria exit 0) |
| 3.1  | PASS (auditoria exit 0) |
| 3.2  | PASS (auditoria exit 0; 446 planos oficiais iguais) |
| 3.3A | PASS (auditoria exit 0; gerador ajustado a D33B-03, ver §9) |
| 3.3B | PASS (auditoria black-box 741 linhas; mutações 6/6 detectadas) |

Suíte completa após o último commit: **1720 passed** (1674 + 46 novos).

## 8. Determinismo

- Sonda da auditoria: saída byte a byte idêntica com PYTHONHASHSEED 0 e 4242.
- Testes 3.3B + fechamento (100) passam com PYTHONHASHSEED 0, 1, 4242 e 987654321 (`evidence/determinism_check.txt`).
- `test_hash_seed_determinism`: 4 seeds, hash idêntico do contexto temporal embaralhado + IF.
- Ordem de operandos, de dependências (origens ordenadas pela chave), de links e de blocos (testes 40–42 da 3.3B), e de períodos (caso E, T3): sem efeito.

## 9. Alterações

| commit | conteúdo |
|---|---|
| `dd5696d` | contrato D33B-01..03 + propagação causal: `app/domain/results.py`, `app/domain/forecast/models.py`, `app/domain/state_propagation.py`, `app/engine/expression_evaluator.py` (CRLF), `app/engine/equation_engine.py` (CRLF), gerador da auditoria 3.3A e sua evidência CSV |
| `8900984` | identidade temporal D33B-04: `app/engine/calculation_context.py` (CRLF), `app/engine/interblock_resolver.py`, `app/engine/interblock_orchestrator.py` (apenas a janela em volta do laço de execução), testes |
| este commit | auditoria (`analysis_stage3_3b.py`, `runtime_probe.py`, `mutation_check.py`), evidências e este relatório |

Testes legados atualizados (`LEGACY_TEST_EXPECTATION`, justificativa no código, nenhum removido):

- `test_stage3_2_execution_orchestration.py`:
  - `test_progressive_period_rerun_in_same_context_*`: D32-02 agora resolvido; o conflito real continua testado;
  - `test_24_27_isolated_block_*` e `test_yield_official_*`: comparação sem `window_end` via `by_period`, com os mesmos valores.
- `test_stage3_3a_result_contract.py`:
  - `test_aggregation_over_a_stated_result_*`: detail agora acompanhado de estado;
  - `test_28_31_*`: `by_period`.
- `test_stage3_3b_state_propagation.py`:
  - teste 25: `DETAIL_WITHOUT_STATE` na construção;
  - teste 48: D32-02 resolvido.
- Auditoria 3.3A: o gerador não produz mais detail sem estado; a evidência CSV foi regenerada.

Confirmações:

```text
workbooks: unchanged
seeds: unchanged
taxonomy: unchanged
IDs: unchanged
formulas: unchanged
Policy B: not implemented
```

- Verificado pela auditoria: nenhum arquivo em `data/`, `tools/`, `app/domain/interblock/`, `app/domain/values.py`, `temporal_aggregation_service.py` ou `time_period_resolver.py` foi alterado desde `eee88d6`.
- A agregação sobre estado continua `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C` (S7).
- `BLOCKED_BY_UPSTREAM_ERROR` e `TECHNICAL_ERROR` não foram adicionados.

## 10. Critérios de aceite

- [x] D33B-01 erro explícito
- [x] D33B-02 erro explícito
- [x] D33B-03 validado
- [x] propagação só por dependências executadas
- [x] ramo inativo de IF não propaga
- [x] D32-02 resolvido
- [x] períodos diferentes coexistem
- [x] reexecução idêntica idempotente
- [x] reexecução incompatível gera conflito
- [x] identidade temporal documentada e testada
- [x] interbloco preserva a identidade temporal
- [x] nenhum estado novo
- [x] Policy B não implementada
- [x] gates anteriores passam
- [x] auditoria black-box passa
- [x] testes de mutação passam
- [x] determinismo comprovado
- [x] suíte completa passa

## 11. Pontos em aberto

Nenhuma decisão semântica bloqueia a 3.3C. Dois pontos foram registrados para confirmação:

1. **D33B-02, `None` + texto.** Aplicada a leitura estrita: é detail diferente, portanto erro. Se a intenção for que "sem complemento" seja compatível com um complemento, é uma política nova a decidir.
2. **Proteção de sobrescrita.** Continua onde existia (consumidor interbloco, 3.1). O alvo de uma equação ou agregação reexecutada no mesmo período com entradas alteradas é recalculado, como antes, e o conflito aparece na primeira transferência a jusante (T4). Estender o write-once a todas as gravações seria uma mudança de comportamento fora do escopo.

STAGE_3.3B_GATE: PASS
