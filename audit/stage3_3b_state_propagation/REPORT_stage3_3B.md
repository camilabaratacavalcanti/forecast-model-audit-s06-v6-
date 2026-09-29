# Etapa 3.3B — Propagação causal de estado e isolamento

Branch `feature/area-41-block`. Baseline (HEAD real no início): `eee88d6c9045f040270bc0d7c99d958485db9fff`.
O HEAD informado no pedido (`eee88d6c…d0c7d99d958485`) está truncado/corrompido; o HEAD real da branch foi usado como autoridade.

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| árvore | limpa no início |
| HEAD | `eee88d6` — audit(stage3.3a): result contract evidence, gate PASS |
| suíte completa | 1620 passed |
| auditorias anteriores (`--no-write`) | 2.6C, 3.1, 3.2 e 3.3A com exit 0 |
| relatórios lidos | `REPORT_stage3_1.md`, `REPORT_stage3_2.md`, `REPORT_stage3_3A.md`; contrato da Etapa 2.2 (`audit/stage2_2_state_contract/REPORT.md`, commit `5c8dcfc`); R1 (`audit/stage2_3_closure/DECISION_REFINEMENT_R1_declared_result_states.md`) |

## 2. Inventário de estados

- Taxonomia no código (`app/domain/values.py`, `RESULT_STATE_TAXONOMY`): `NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED`.
- Nenhum estado novo foi criado. Não existe `"OK"`: a ausência de estado é `state=None`. Teste 01 e varredura AST na auditoria.
- O contrato 2.2 menciona `BLOCKED_BY_UPSTREAM_ERROR` e `TECHNICAL_ERROR`. Eles não estão na taxonomia do código e não foram implementados, porque não foram pedidos e criá-los seria inventar estados.
- Os parâmetros continuam sem estado: `set_parameter_value(Result(...))` é rejeitado com `CalculationValueError` (teste 05).

## 3. Evidência sobre `"F"`

| evidência | fonte |
|---|---|
| Só EQ16011 (alvo VAR16025, L4_L5) e EQ16012 (alvo VAR16028, L6_L7) produzem o literal `"F"`. Os demais literais de texto das equações são comparações com `allowed_values` de `hes`. | `data/seed/area_41/equations.json`; auditoria §1 |
| As duas variáveis declaram `declared_result_states = [{state: NO_APPLICABLE_RULE, literal: "F"}]`. | `data/seed/area_41/variables.json` |
| D1 (2.2): o literal é estado apenas para a variável alvo que o declara; a tradução é por variável, nunca global. | contrato 2.2 §6.3/§6.4 |
| R1 (2.3): a declaração é local e os herdeiros (`retirada_condensado_linha` VAR16031 e `_total` VAR16034) não redeclaram. | R1 |

Conclusão: o mapeamento `"F" → NO_APPLICABLE_RULE` está provado **por variável** (VAR16025 e VAR16028). `STATE_LITERAL_MAPPING_UNRESOLVED` não se aplica.

A conversão é feita num único ponto, `translate_declared_literal` (`app/domain/state_propagation.py`), e só quando a definição alvo é conhecida. Uma variável que não declara o literal mantém `"F"` como valor bruto (teste 04, variável FR). A única constante `"F"` no código continua sendo a de `app/domain/values.py`; não foi espalhado nenhum `if value == "F"`.

## 4. Política de propagação

- **Onde:** `EquationEngine.calculate_instance_result`.
  1. Coleta as dependências **reais** da expressão (`ExpressionEvaluator.dependency_results`), resolvidas pela mesma regra da avaliação: referência escopada com fallback de período, e não escopada com fallback espacial.
  2. `inherit_from_dependencies` decide:
     - nenhuma dependência com estado → calcula normalmente;
     - um único estado → `Result(None, estado, detail)`, sem avaliar a expressão.
  3. O valor calculado passa por `translate_declared_literal`.
- **Valor:** um resultado com estado tem `value=None` (contrato 2.2 §13: value presente sse VALID).
- **Alcance:** a propagação é estática sobre as referências da expressão, incluindo os ramos de um IF. Não se avalia o ramo antes de decidir, porque isso usaria o estado como valor.
- **APIs escalares legadas:** `get_variable_value`, `calculate_instance`, `resolve` e `transfer` levantam `STATEFUL_RESULT_ON_SCALAR_API` quando o resultado não tem valor.
- **Evaluator chamado diretamente:** levanta `STATED_RESULT_CONSUMED_AS_VALUE` (substitui `STATE_PROPAGATION_PENDING_STAGE_3.3B`).

## 5. Política de isolamento

- A propagação percorre somente arestas reais: referências da equação e vínculos interbloco.
- Proximidade não propaga. Mesmo bloco, mesma instância de outra variável, mesmo período, mesma execução ou mesma expressão sem referência não recebem estado.
- Testes: 11–15 (sintético) e o caso A41 real, em que L1–L3 (VAR16018) e L6–L7 (VAR16028) permanecem numéricos enquanto L4_L5 carrega `NO_APPLICABLE_RULE`.
- A auditoria verifica também, em todos os cenários, que nenhum nó fora do fecho causal recebeu estado.

## 6. Política de múltiplos estados

O contrato não define como combinar estados diferentes. Implementação:

- `MULTI_STATE_COMBINATION_UNDEFINED` (`MultiStateCombinationUndefinedError`) lista os estados ordenados e as origens ordenadas, sem escolher prioridade.
- A mensagem e o comportamento independem da ordem dos operandos (`S = P + Q` × `S2 = Q + P`, teste 21).
- Mesmo estado vindo de várias origens com o mesmo detail não é combinação: é o mesmo dado, e o resultado independe da ordem (testes 17 e 23).
- Teste 24 (política definida): **não aplicável**, porque a política não existe no contrato. O teste 24 verifica o inverso: todo par de estados diferentes é erro.

**Decisão pendente: MULTI_STATE_COMBINATION_UNDEFINED.**

## 7. Política de detail

- **Origem única:** o detail é preservado byte a byte (teste 08, com espaços e tab).
- **Mesmo estado, details diferentes:** `MULTI_DETAIL_COMPOSITION_UNDEFINED`. Nenhuma concatenação é inventada.
- **Dependência com detail e sem estado:** `DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED`. O contrato 3.3A permite detail sem estado, mas não diz se ele propaga. Hoje nenhum seed produz esse caso.

**Decisões pendentes: MULTI_DETAIL_COMPOSITION_UNDEFINED e DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED.**

## 8. Interbloco

- A transferência move o `Result` inteiro (`transfer_result`, 3.3A), e o trace registra `value=None`, o estado e o detail (teste 26).
- A transferência nunca cria estado (teste 28). Link, instância e `period_id` são mantidos (teste 29).
- Reexecução com resultado diferente no consumidor gera o conflito existente da 3.1 (`INTERBLOCK_CONSUMER_VALUE_CONFLICT`) e nunca sobrescreve (teste 30).
- Cadeias reais:
  - REAL_DERIVED: `lth_meta` VAR12066 com estado em L2 → production VAR12031 → yield VAR11031 → area_41 VAR16007 → EQ16004 VAR16008 (L1_L3).
  - OFFICIAL: VAR12066 com estado em L3 → energy VAR18011 (anual).
- O orquestrador não foi alterado. A propagação entra pelo `ForecastEngine` e pelo resolver, e a topologia da 3.2 é idêntica (auditoria: 446 planos oficiais iguais ao `plan_evidence.csv`).

## 9. Temporalidade

- O estado herdado é gravado apenas no `period_id` do alvo (teste 31); outros períodos não são afetados (teste 15).
- Estado anual transferido fica no período anual (teste 35).
- Agregação diário → mensal sobre estado gera `STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C` (teste 32, e cenário real S7 com AGR-PRODUCTION-CONSUMO_BAUXITA… a partir de VAR12022). O consumidor mensal não recebe nada (teste 34).
- Agregação sem estado permanece inalterada (teste 33). A Policy B não foi implementada.

## 10. Testes

`tests/test_stage3_3b_state_propagation.py`: 54 testes. Todos passam.

| grupo | testes |
|---|---|
| estado básico | 01–05 |
| propagação simples | 06–10 |
| isolamento | 11–15 |
| branching (A→B e A→C; B→D←C; grupo) | 16–19 |
| dependência múltipla | 20–25 (24 = sem política: todo par é erro) |
| interbloco | 26–30 |
| temporal | 31–35 |
| runtime | 36–39 |
| determinismo (ordem de equações, blocos, vínculos, PYTHONHASHSEED) | 40–43 |
| regressão (yield, production, energy, max_ht; area_41; topologia; D32-01/D32-02) | 44–48 |
| reais | A41 `"F"` e herdeiros, controle sem `"F"`, `lth_meta` interbloco, `lth_meta` → energy oficial |
| guarda | módulo central sem dependências; constante `"F"` só em `values.py` |

Testes legados alterados pelo contrato (`LEGACY_TEST_EXPECTATION`, nenhum removido):

- `test_t24_10_no_applicable_rule_produces_the_text_literal_f` (`tests/test_stage2_4_workbook_contract.py`). Antes, o resultado era o texto `"F"`. Agora VAR16025 L4_L5 é `Result(None, NO_APPLICABLE_RULE)`, e a API escalar levanta `STATEFUL_RESULT_ON_SCALAR_API`. Motivo: D1/R1.
- `test_equation_reading_a_stated_result_is_an_explicit_boundary` (`tests/test_stage3_3a_result_contract.py`). Antes, a fronteira era `STATE_PROPAGATION_PENDING_STAGE_3.3B`. Agora o estado propaga (L1 herda `INVALID_INPUT` e L2 fica 40.0), e o evaluator direto levanta `STATED_RESULT_CONSUMED_AS_VALUE`.

Suíte completa: **1674 passed** (1620 + 54). Saída em `evidence/test_output.txt`.

## 11. Auditoria independente

`evidence/analysis_stage3_3b.py` não importa `app/` nem `tools/`. Arquivos gerados: `analysis_summary.json`, `propagation_evidence.csv` e `determinism_check.txt`. A sonda de caixa-preta é `runtime_probe.py`, executada em subprocesso.

- O grafo de instâncias é reconstruído do texto das expressões e dos vínculos: 630 nós com arestas e 0 referências não resolvidas.
- O ramo `"F"` de EQ16011 é decidido avaliando a expressão do seed com a semântica do Python: hes L4=Normal e L5="1 By pass e LC".
- As expectativas vêm do fecho causal e das fronteiras documentadas.

| cenário | esperado | observado |
|---|---|---|
| S1 A41 `"F"` | VAR16025 L4_L5, VAR16031 L4/L5 e VAR16034 = NO_APPLICABLE_RULE; 37 nós isolados numéricos; leitura escalar = STATEFUL_RESULT_ON_SCALAR_API | igual |
| S2 controle | nenhum estado | igual |
| S3 lth_meta L2 | 6 herdeiros, 30 isolados | igual |
| S4 `"F"` + VAR16017 L1 INVALID | MULTI_STATE_COMBINATION_UNDEFINED em VAR16034 | igual |
| S5 details a/b | MULTI_DETAIL_COMPOSITION_UNDEFINED | igual |
| S6 mesmo detail | estado com detail preservado | igual |
| S7 agregação | STATE_AWARE_AGGREGATION_PENDING_STAGE_3.3C | igual |
| S8 oficial energy | VAR18011 L3 = VALIDATION_FAILED, demais numéricos | igual |

- Topologia: 446 planos iguais aos da 3.2.
- Determinismo: saída da sonda idêntica com PYTHONHASHSEED 0 e 4242.
- Estático: nenhum artefato protegido alterado desde `eee88d6`.
- Resultado: **AUDIT: PASS (338 linhas de evidência)**.
- Controle negativo, feito manualmente e revertido:
  - trocar o erro de multi-estado por uma escolha faz a auditoria falhar em `[códigos]` e `[combinação inventada]`;
  - desligar a propagação a faz falhar em `STATED_RESULT_CONSUMED_AS_VALUE` e `[divergências]`.

## 12. Regressão

- Comportamento numérico e sem estado inalterado: 1620 testes anteriores passam (2 com expectativa legada atualizada, §10).
- Regressão dos blocos reais: testes 44–47 (yield, production, energy, max_ht) e 45 (cadeia area_41).
- Auditorias anteriores com `--no-write` e exit 0: 2.6C, 3.1, 3.2 e 3.3A.

## 13. Arquivos alterados

| arquivo | mudança |
|---|---|
| `app/domain/state_propagation.py` (novo) | tradução por variável, herança, erros das combinações indefinidas |
| `app/domain/results.py` | `value=None` permitido só com state; `StatedResultConsumedAsValueError`, `StatefulResultOnScalarApiError`, `scalar_of` |
| `app/engine/equation_engine.py` (CRLF) | `calculate_instance_result`; `calculate_instance` via `scalar_of` |
| `app/engine/expression_evaluator.py` (CRLF) | `dependency_results` (dependências reais, mesma resolução) |
| `app/engine/forecast_engine.py` (CRLF) | grava `Result`; passa a definição alvo |
| `app/engine/calculation_context.py` (CRLF) | leitura escalar via `scalar_of`; estado sem valor não é validado como valor |
| `app/engine/interblock_resolver.py` | APIs escalares via `scalar_of` |
| `app/domain/forecast/models.py` | `ForecastValue` sem valor e sem estado é erro |
| `tests/test_stage3_3b_state_propagation.py` (novo) | 54 testes |
| `tests/test_stage2_4_workbook_contract.py`, `tests/test_stage3_3a_result_contract.py` | `LEGACY_TEST_EXPECTATION` (§10) |
| `audit/stage3_3b_state_propagation/**` | este relatório e as evidências |

Não alterados: workbooks, fonte, source_block, `interblock_links.json`, taxonomia, ledger de IDs, IDs, fórmulas dos quatro blocos, Stage 2.6/3.1, orquestrador e topologia da 3.2, serviço de agregação (Policy B). A auditoria verifica isso contra `eee88d6`.

## 14. Decisões

Registradas por falta de contrato:

1. **MULTI_STATE_COMBINATION_UNDEFINED.** Estados diferentes numa mesma equação: qual resultado (ou erro) o contrato quer? Hoje: erro explícito, e a execução para.
2. **MULTI_DETAIL_COMPOSITION_UNDEFINED.** Mesmo estado com details diferentes: como compor? Hoje: erro explícito.
3. **DETAIL_WITHOUT_STATE_PROPAGATION_UNDEFINED.** Detail sem estado numa dependência: propaga ou não? Hoje: erro explícito (nenhum seed produz o caso).

Decisões de desenho tomadas com base no contrato existente, para revisão:

4. Resultado com estado tem `value=None` (2.2 §13).
5. Propagação estática pelas referências, incluindo ramos de IF não tomados. Consequência: uma equação que só consome um estado num ramo não tomado herda o estado. Avaliar o ramo exigiria usar o estado como valor.
6. A tradução de literal só ocorre quando a definição alvo é conhecida (caminho `ForecastEngine` com registro). Callers legados sem definição mantêm o valor bruto.
7. `INVALID_INPUT` por violação de `allowed_values` continua sendo rejeição na gravação, como na 3.3A. Não se converte em estado.
8. `BLOCKED_BY_UPSTREAM_ERROR` e `TECHNICAL_ERROR` (2.2) não foram implementados.

## 15. Limitações

- Se a execução parar numa combinação indefinida, os resultados já gravados permanecem no contexto, como em qualquer erro do orquestrador (comportamento da 3.2).
- Agregação state-aware continua fora (3.3C).
- A leitura de detail sem estado nunca é produzida pelos seeds atuais; o caso foi testado apenas de forma sintética.
- Os cenários reais com cadeias completas dependem de REAL_DERIVED, porque as pendências `maintenance` (D32-01) bloqueiam os planos oficiais.

## 16. D32-01

Preservada. Fontes não carregadas → `INTERBLOCK_SOURCE_NOT_LOADED` no planejamento (teste 48; auditoria: 446 planos iguais à 3.2).

## 17. D32-02

Preservada, sem workaround. Reexecução progressiva no mesmo contexto → `INTERBLOCK_CONSUMER_VALUE_CONFLICT` (teste 48; teste 30 para estado divergente).

## 18. Próximo passo

1. Decidir os itens 1–3 da §14 (política de combinação de estados e de details).
2. Etapa 3.3C: agregação state-aware (Policy B).
3. Decidir D32-01 e D32-02.

STAGE_3.3B_GATE: READY_FOR_DECISION
