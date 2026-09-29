# Etapa 3.3A — Contrato global de resultado `value + state + detail`

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` (árvore limpa) |
| HEAD inicial | `a733487` (Etapa 3.2, `STAGE_3.2_GATE: READY_FOR_DECISION`, mantida assim) |
| commits anteriores | `11c8931` (3.2), `2cfc52a`, `a733487` |
| suíte inicial | **1570 passed** |
| relatórios lidos | `REPORT_stage3_1.md`, `REPORT_stage3_2.md` |
| commit de implementação | `472949b` |
| commit de evidências | o seguinte a `472949b` (contém este relatório) |
| suíte final | **1620 passed**, 0 failed (1570 + 50) |

## 2. Inventário encontrado, antes de qualquer alteração

| estrutura | onde | hipótese "resultado = número" |
|---|---|---|
| valor de cálculo | `ScalarValue = int \| float \| str` (`app/domain/values.py`) | escalar puro |
| resultado de equação | `EquationEngine.calculate_instance` devolve escalar; `ForecastEngine` grava com `set_variable_value` | escalar |
| resultado de agregação | `TemporalAggregationService.aggregate` → `ForecastValue.value` (número) | escalar; quem chama grava no contexto |
| resultado transferido | `InterblockValueResolver.transfer` (3.1) lê e grava escalar | escalar |
| `CalculationContext` | `_scoped_variables: dict[CalculationKey, ScalarValue]`; chave = (entidade, scope_type, scope_value, period_id) | escalar |
| resultado por instância/período | `CalculationKey` + `VariableInstance`; a frequência vem da `VariableDefinition` e se expressa na granularidade do `period_id` | — |
| saída temporal | `ForecastValue(value)` e `ForecastValueRegistry` (identidade sem proveniência; conflito da mesma execução comparava só o valor) | escalar |
| estados | `RESULT_STATE_TAXONOMY = {NO_APPLICABLE_RULE, INVALID_INPUT, VALIDATION_FAILED}` (contrato D2, Etapa 2.3/2.4); `declared_result_states` por variável (estado ↔ literal, ex.: NO_APPLICABLE_RULE → `"F"`) | em runtime, o estado só existe como o literal `"F"` no lugar do valor |
| `allowed_values` | só em `VariableDefinition` categórica: é o **domínio do VALOR**, não do estado (contrato 2.4: "allowed_values só se aplica a value_type categorico"; `is_value_in_domain`). Nos seeds: `area_41.hes` (VAR16021) | não validado em runtime |
| leitura em equação | `ExpressionEvaluator._get_variable_with_period_fallback` usa `get_variable_value` | escalar |

## 3. Contrato adotado (`app/domain/results.py`)

```
Result
├── value   ScalarValue: int | float | str (inclui o marcador "F"); sem conversão; bool, None e coleções são rejeitados
├── state   None | NO_APPLICABLE_RULE | INVALID_INPUT | VALIDATION_FAILED (taxonomia D2; nenhum estado novo)
└── detail  None | texto preservado exatamente (sem strip nem normalização)
```

Pontos centrais, cada um com implementação única:

| elemento | função |
|---|---|
| `as_result(x)` | único ponto de compatibilidade: um escalar legado (ex.: `42`) vira `Result(42)`; um `Result` passa inalterado |
| `check_value_domain(variable_id, value, allowed_values)` | única validação de `allowed_values` |
| `require_plain_for_calculation` | fronteira `STATE_PROPAGATION_PENDING_STAGE_3.3B` |
| `require_plain_for_aggregation` | fronteira `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C` |
| `ResultIdentity` | torna explícita a identidade (variável, scope_type, scope_value, frequência, period_id) |

Erros com código:

| erro | código |
|---|---|
| `ResultContractError` | `RESULT_CONTRACT_INVALID` |
| `ResultValueDomainError` | `RESULT_VALUE_OUTSIDE_ALLOWED_VALUES` |
| `StatePropagationPendingError` | `STATE_PROPAGATION_PENDING_STAGE_3.3B` |
| `StateAwareAggregationPendingError` | `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C` |

`ResultContractError` herda de `Exception`, não de `ValueError`, de propósito. Assim uma violação de contrato nunca é
confundida com erro matemático nem reembalada como falha de avaliação.

## 4. Decisões explícitas

| ID | decisão | evidência / motivo |
|---|---|---|
| D33A-01 | domínio de `state` = `RESULT_STATE_TAXONOMY` (3 estados); ausência de estado é `None` | taxonomia D2 comprovada; não há evidência de um estado "OK", então nenhum foi inventado |
| D33A-02 | `allowed_values` valida o **valor** de variáveis categóricas, não o estado | contrato 2.4 (`VariableDefinition.__post_init__`, `is_value_in_domain`); não há ambiguidade no código |
| D33A-03 | o marcador `"F"` continua aceito como valor de qualquer variável e não é validado contra `allowed_values` | regra existente do `CalculationContext` (valor não de negócio) |
| D33A-04 | `detail` é texto opaco (ou `None`), preservado exatamente; não é exigido nem proibido junto de `state` | nenhuma regra comprovada liga os dois; estrutura mais rica fica para decisão futura |
| D33A-05 | parâmetros não são resultados: continuam numéricos, com `value`/`version` | D24-12 intocado |
| D33A-06 | o runtime **não deriva** estado a partir de literais (ex.: `"F"` → NO_APPLICABLE_RULE) | derivação e propagação de estado pertencem à Etapa 3.3B; nesta etapa o estado só existe se for fornecido e é transportado sem perda |
| D33A-07 | consumir em equação um resultado com `state` ou `detail` gera erro `STATE_PROPAGATION_PENDING_STAGE_3.3B` | sem semântica definida, calcular sobre o valor descartaria o estado em silêncio |
| D33A-08 | agregar resultados com `state` ou `detail` gera erro `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C`; resultados sem estado mantêm o comportamento numérico atual | Policy B não implementada |
| D33A-09 | a validação de domínio é ativada quando o contexto conhece a definição (`declare_variable_definitions`); o orquestrador sempre declara | não altera o motor (`ForecastEngine`) nem caminhos existentes que não declaram definições |

## 5. Arquivos alterados

Commit `472949b`, 10 arquivos, +1004 −36. Nada em `data/` mudou.

| arquivo | alteração |
|---|---|
| `app/domain/results.py` | **novo**: contrato, compatibilidade, domínio e fronteiras |
| `app/engine/calculation_context.py` | armazenamento canônico `_scoped_results: dict[CalculationKey, Result]` (mesma chave); `get/set_variable_result`; `get/set_variable_value` derivados; `declare_variable_definitions`; `_scoped_variables` passa a ser uma visão escalar derivada (compatibilidade); CRLF preservado |
| `app/engine/interblock_resolver.py` | `resolve_result`/`transfer_result` movem o `Result` inteiro; o conflito compara o resultado completo; `resolve`/`transfer` continuam devolvendo o valor |
| `app/engine/interblock_orchestrator.py` | declara as definições ao contexto; eventos do trace ganham `state`/`detail`; as transferências usam `transfer_result`; **planejamento e topologia inalterados** (AST idêntico, ver §6) |
| `app/engine/expression_evaluator.py` | leitura via `get_variable_result` + fronteira 3.3B; `ResultContractError` nunca é reembalada; CRLF preservado |
| `app/engine/temporal_aggregation_service.py` | leitura via `get_variable_result` + fronteira 3.3C |
| `app/engine/temporal_forecast_orchestrator.py` | `direct_forecast_value` leva `state`/`detail` do contexto para o `ForecastValue` |
| `app/domain/forecast/models.py` | `ForecastValue.state/detail` (opcionais, fora da identidade) e a propriedade `result` |
| `app/domain/forecast/collection.py` | histórico guarda `state`/`detail`; o conflito da mesma execução compara o resultado completo |
| `tests/test_stage3_3a_result_contract.py` | **novo**: 50 testes |

Não alterados:
- workbooks, `fonte`, `source_block` e `interblock_links.json`;
- taxonomia de blocos, livro de IDs, IDs e seeds;
- fórmulas;
- `ForecastEngine`, `EquationEngine` e o registry do 3.1;
- as regras das Etapas 2.6, 3.1 e 3.2;
- os testes existentes.

## 6. Testes (`tests/test_stage3_3a_result_contract.py`, 50)

| # | exigido | teste |
|---|---|---|
| 1–3 | `value` / `value+state` / `value+state+detail` | `test_01`, `test_02`, `test_03` |
| 4 | `detail` preservado exatamente | `test_04` (espaços, `\n`, `\t`, acentos, vazio) |
| 5 | estado inválido rejeitado | `test_05` (6 casos: `OK`, minúsculas, espaço, `F`, vazio, `ERROR`) |
| 6 | estado válido aceito | `test_06` (os 3 estados), `test_06b` (sem conversão de tipos) |
| 7–8 | domínio válido / inválido | `test_07`, `test_08` (`area_41.hes` real) |
| 9 | sem `allowed_values` | `test_09` |
| 10 | validação centralizada | `test_10` (espião em `check_value_domain` + AST: nenhum outro módulo de runtime acessa `allowed_values`) |
| 11–14 | identidade: instâncias, períodos, frequências, mesma variável | `test_11` a `test_14` |
| 15 | conflito continua detectado | `test_15` (inclusive mesmo valor com estado diferente) |
| 16–21 | interblock preserva value/state/detail, instância, período, sem conversão | `test_16_21_*` (4 parametrizações, cadeia de 2 saltos, orquestrador com trace), `test_consumer_domain_is_validated_on_transfer` |
| 22–26 | orquestrador | `test_22`; `test_23`/`test_24`/`test_25` (ordens reais iguais às da 3.2); `test_23_25_planning_code_is_unchanged_since_stage_3_2` (AST de `_build_graph`, `_upstream`, `targets_of_blocks`, `plan`, `_order`, `_find_cycle` idêntico ao de `a733487`); `test_26` (pendente continua `INTERBLOCK_SOURCE_NOT_LOADED`, 0 resultados gravados) |
| 27 | testes existentes | suíte completa: 1620 passed; `test_27` (visão escalar derivada) |
| 28–31 | regressão yield/production/energy/max_ht | `test_28_31_*`: equações reais do bloco pelo orquestrador × `ForecastEngine` direto, com **resultados canônicos idênticos** e todos sem estado |
| 32–34 | determinismo | `test_32` (ordem de blocos e de vínculos), `test_33` (3 `PYTHONHASHSEED`), `test_34` (execução repetida idempotente) |
| fronteiras | 3.3B, 3.3C, `ForecastValue` | `test_equation_reading_a_stated_result_is_an_explicit_boundary`, `test_aggregation_over_a_stated_result_is_an_explicit_boundary`, `test_forecast_value_carries_state_and_detail` |

**LEGACY_TEST_EXPECTATION: nenhum.** Nenhum teste existente falhou nem foi alterado.

## 7. Auditoria independente

`evidence/analysis_stage3_3a.py` não importa `app/` nem `tools/` e não replica a implementação. As expectativas vêm de:
- seeds;
- `interblock_links.json`;
- taxonomia D2;
- evidência histórica da 3.2 (`plan_evidence.csv`).

O runtime é observado pela sonda `evidence/runtime_probe.py`, executada em subprocesso.

| verificação | escopo | falhas |
|---|---|---:|
| representação | 19 casos (válidos, estados, 5 `detail` difíceis, estados e tipos inválidos) | 0 |
| `allowed_values` | 10 gravações (5 opções de `hes`, 3 inválidas, `"F"`, numérica sem domínio); rejeitado não é gravado | 0 |
| identidade | 7 leituras (4 chaves distintas + 3 leituras cruzadas de instância/período/frequência) | 0 |
| transferência sem perda | **13 vínculos, 67 instâncias**: value, tipo, state e detail iguais ao produtor; 156 iscas em outros períodos | 0 |
| atalhos | cadeia area_41 ← yield ← production com resultados diferentes em yield e production: area_41 recebe o de **yield**; 0 iscas lidas | 0 |
| pendências | 16 transferências pendentes → `INTERBLOCK_SOURCE_NOT_LOADED`; 19 execuções bloqueadas com 0 resultados | 0 |
| topologia | 446 planos oficiais iguais (estado e número de passos) aos da 3.2; 3 cadeias reais iguais | 0 |
| determinismo | sonda com `PYTHONHASHSEED` 0 × 31337: saída idêntica | 0 |

Evidências:
- `evidence/result_transfer_evidence.csv`: 67 linhas;
- `evidence/analysis_summary.json`;
- `evidence/determinism_check.txt`: 3 `PYTHONHASHSEED`, mesmo SHA-256;
- `evidence/test_output.txt`: inclui a reexecução das auditorias 2.6C, 3.1 e 3.2, todas com código de saída 0.

## 8. Compatibilidade

- `get_variable_value`/`set_variable_value`, `resolve`/`transfer` e `transfer_all` mantêm assinatura e retorno.
- Um escalar legado equivale a `Result(value)` pelo único ponto `as_result`.
- `context._scoped_variables`, usado por testes e sondas antigas, é uma visão escalar derivada do armazenamento
  canônico; atribuir a ela converte por `as_result`.
- Erros existentes mantidos: um booleano continua levantando `CalculationValueError` antes de qualquer conversão.
- `ForecastValue` sem `state`/`detail` é idêntico ao anterior; os campos novos são opcionais e ficam fora da
  identidade.
- As auditorias anteriores (2.6C, 3.1 e 3.2) continuam passando no HEAD sem alteração.

## 9. Impacto na Etapa 3.1

- O contrato 3.1 continua o mesmo: instância exata, período da frequência, sem fallback, sem conversão, conflito
  explícito.
- O que é transportado passou de valor para o `Result` completo.
- O conflito agora também detecta diferença de `state`/`detail` com o mesmo valor, o que evita perda silenciosa de
  informação.

## 10. Impacto na Etapa 3.2

A topologia não mudou: o AST das funções de planejamento é idêntico e os 446 planos oficiais batem com a evidência da
3.2. Mudou apenas:
- o contexto recebe as definições;
- as transferências usam `transfer_result`;
- o trace registra `state`/`detail`.

O gate da 3.2 continua `READY_FOR_DECISION`, como pedido.

## 11. D32-01 — fontes não carregadas

Preservado. Planos que dependem de blocos não carregados continuam falhando com `INTERBLOCK_SOURCE_NOT_LOADED` antes
de executar, com 0 resultados gravados (teste 26, auditoria §7). Nenhum fallback, default, valor sintético ou override
foi introduzido; os valores fornecidos nos testes REAL_DERIVED continuam sendo só fixtures.

## 12. D32-02 — reexecução no mesmo contexto

Preservado. O conflito `INTERBLOCK_CONSUMER_VALUE_CONFLICT` continua (o teste da 3.2 segue verde) e nenhum workaround
foi criado.

A identidade do resultado ficou explícita e separada da proveniência:
- a identidade é (`variável`, `scope_type`, `scope_value`, frequência via definição, `period_id`), igual em
  `CalculationKey`, `ResultIdentity` e `ForecastValue.identity()`;
- proveniência (`run_date`, `execution_id`) não entra na identidade.

`ForecastValueRegistry` já versiona por `execution_id`, com o valor anterior arquivado em `history()`. Resolver a D32-02
depois exige apenas decidir se o contexto aplica essa regra também às transferências; a chave e o `Result` não mudam.

## 13. Limitações

1. O runtime ainda não **produz** estados. Eles só existem quando fornecidos (ex.: entradas) e são transportados sem
   perda. A derivação a partir de `declared_result_states` e dos literais (`"F"`) é da Etapa 3.3B.
2. Equações e agregações recusam resultados com estado (fronteiras 3.3B/3.3C). É o comportamento seguro enquanto a
   semântica não existe.
3. `detail` é texto. Uma estrutura mais rica exigirá decisão.
4. A validação de `allowed_values` depende de o contexto conhecer a definição. O orquestrador sempre informa; o
   `ForecastEngine` usado diretamente só declara categóricas (inalterado).
5. D32-01 e D32-02 continuam abertas, conforme o gate da 3.2.

## 14. Próximo passo recomendado

**Etapa 3.3B — propagação de estados:**
- derivar o estado de um resultado a partir de `declared_result_states` (literal ↔ estado);
- definir a regra de consumo de entradas com estado nas equações, substituindo a fronteira 3.3B;
- isolar estados entre ramos.

Depois, **3.3C**: agregação state-aware (Policy B), substituindo a fronteira 3.3C. Nenhuma das duas exige mudar
`Result`, o contexto, o resolver ou a topologia.

## 15. Push

Os commits `472949b` e o de evidências são enviados com `git push -u origin feature/area-41-block`. Nenhum PR foi
criado.

STAGE_3.3A_GATE: PASS
