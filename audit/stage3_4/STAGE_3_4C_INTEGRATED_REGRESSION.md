# Stage 3.4C — Integrated Four-Block Regression

Execução do contrato de regressão integrada da Stage 3.4A (`STAGE_3_4A_DECISION_CONTRACT.md`, DR-1..DR-5).

- **Reproduzir:** `python audit/stage3_4/integrated/run_integrated.py` (grava `evidence/`; `--no-write` só imprime).
- **Testes:** `tests/test_stage3_4c_integrated.py` (11 testes).
- **Rótulo de todo resultado desta etapa:** `REAL_DERIVED_TEST_RESULT`.

---

## 1. Executive Summary

A regressão integrada executa planner, orquestrador, engine, transferências interbloco, execução temporal e estados sobre os quatro blocos oficiais (`yield`, `production`, `energy`, `max_ht`). A execução roda no fixture `REAL_DERIVED` (TEST_FIXTURE_ONLY), em 32 datas diárias contíguas (2026-01-01..2026-02-01) no mesmo contexto.

| verificação | resultado |
|---|---|
| alvos integrados executados em todas as datas | **421 / 421** |
| nós do planner executados em todas as datas | **427 / 427** (218 EQUATION + 197 AGGREGATION + 12 TRANSFER) |
| nós só no planner / só no engine | 0 / 0 |
| transferências executadas e verificadas (value, state, detail) | **12 / 12**, 1 920 / 1 920 eventos |
| orquestrador × `ForecastEngine` por bloco (equações) | 12 544 comparações, 0 diferenças |
| virada 2026-01-31 → 2026-02-01 | janelas de janeiro intactas; fevereiro abre `window_end = 2026-02-01` |
| reexecução de 2026-01-15 e 2026-02-01 | store idêntico, 0 chaves novas, transferências `UNCHANGED`, 0 estados |
| determinismo (2 hash seeds, ORDER_A/ORDER_B) | 5 fingerprints idênticos |
| estados (propagação, isolamento, EQ12012, EQ18003, 4 tipos de agregação, MULTI_*) | todos satisfeitos |
| testes negativos (alvo, nó, transferência, estado) | todos detectados |
| defeitos de produção encontrados | **nenhum** |
| `app/`, `data/`, `tools/`, workbooks, seeds, `interblock_links.json` | inalterados |

Nenhum resultado desta etapa se apoia na 3.4B: a 3.4B validou blocos isolados, e a 3.4C valida a integração. O fato de a 3.4B ter passado não é usado como argumento de correção.

## 2. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD inicial / origin | `4d54804` / `4d54804` (Stage 3.4B) |
| árvore inicial | limpa |
| suíte inicial | 1834 passed, 0 failed, 0 skipped |
| 3.4A | `STAGE_3.4A_GATE: PASS` (`95e7ade`) |
| 3.4B | `STAGE_3.4B_GATE: PASS` (`4d54804`) |
| Python | 3.11.15 |

## 3. Scope

- **Dentro:**
  - os 421 alvos integrados e os 427 nós do plano;
  - planner, orquestrador e engine;
  - 12 transferências e o ciclo production ↔ yield no nível de bloco;
  - janelas diária, mensal e anual (YTD);
  - estados e o IF causal;
  - agregação state-aware (Policy B, 3.3C);
  - reexecução e determinismo;
  - testes negativos do próprio auditor.
- **Fora:**
  - `area_41` (25 alvos);
  - os blocos sem workbook `maintenance`, `forecast`, `temperature_lp`, `area_04_13` e `alumina`, que continuam `PENDING_LOAD` normativo e não foram carregados;
  - a Stage 3.4D (mutation & audit closure).
- **Oráculos:**
  - `INDEPENDENT_ORACLE = NO`: a 3.4A estabeleceu `INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE`, e nenhum oráculo numérico novo foi criado.
  - `ENERGY_PYTHON_ORACLE = NOT_USED` nesta etapa. As entradas do fixture são sintéticas, e o oráculo existente cobre casos que o fluxo integrado não reproduz com as mesmas entradas. Ele não foi alterado.

## 4. REAL_DERIVED classification

`REAL_DERIVED = TEST_FIXTURE_ONLY` (DR-2). O fixture fica em `audit/stage3_4/integrated/fixture.py`:

- o catálogo oficial é carregado dos seeds;
- o registro de vínculos é reconstruído **em memória** a partir de `interblock_links.json`, com `pending = []`;
- as consumidoras dos 16 vínculos pendentes viram entradas livres do plano (ex.: VAR18012, pendente de `temperature_lp`);
- nada é escrito em disco, e nenhum bloco ausente é "carregado".

É a mesma receita de `tests/test_stage3_2_execution_orchestration.py::real_derived_orchestrator`. Os hashes de grafo dos dois são iguais (§20).

- **Entradas determinísticas:** a variável de índice *i* em `required_inputs` (51 variáveis), no escopo de índice *k*, recebe `1.0 + 0.01·i + 0.001·k`. Só as entradas diárias somam `0.0001·dia_do_ano`; as mensais e anuais dependem apenas do período. Variáveis categóricas recebem `allowed_values[0]`. Os parâmetros vêm dos seeds.
- **Impacto operacional:** nenhum. O fixture não altera seeds, vínculos, proveniência nem o registro oficial, que continua com 16 pendências (`pending_official = 16`).

## 5. 421-target universe

```text
Official planning targets = 446
Integrated targets        = 421
Area_41 excluded targets  = 25

Planner nodes = 427
  EQUATION    = 218
  AGGREGATION = 197
  TRANSFER    = 12

446 != 421 != 427   (universos diferentes)
```

- A lista dos 421 alvos não é fixa no código. O harness a deriva de `targets_of_blocks(("production", "yield", "energy", "max_ht"))`.
- O harness verifica a lista contra `audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv`: 446 linhas, iguais a `targets_of_blocks` com os 5 blocos no orquestrador oficial.
- Removidas as 25 linhas de `area_41`, sobram exatamente os 421.
- A interseção com os alvos de `area_41` é vazia (teste `test_area_41_is_outside_the_integrated_universe`).
- Por bloco, derivado do planner: yield 219, production 50, energy 43, max_ht 109.

## 6. 427-node universe

- O plano integrado dos 421 alvos tem 427 nós (`ExecutionNode.key = KIND:node_id`): 218 EQUATION, 197 AGGREGATION e 12 TRANSFER.
- Não há `pending_blockers`, e há 51 entradas requeridas.
- **Por que 427 ≠ 421:** a variável VAR12041 (production) tem 7 definições de equação, uma por linha. São 7 nós EQUATION para 1 alvo, e 427 − 421 = 6.
- **32 datas não são 32 × 421 alvos.** As datas são casos de execução temporal. A cada data, os mesmos 427 nós executam e gravam 847 eventos (392 instâncias de equação + 395 instâncias de agregação + 60 instâncias de transferência). No total são 27 104 eventos em 32 datas, e o contexto final tem 33 740 resultados, entradas incluídas.

## 7. Target/node reconciliation

Evidência: `evidence/targets.csv` e `evidence/nodes.csv`.

- **Alvo → nós.** `targets.csv` tem uma linha por alvo com as colunas:
  - `planner_status` (PLANNED);
  - `producer_nodes` (nós que produzem o alvo);
  - `planner_nodes` (fecho completo `plan([alvo]).steps`, sem assumir 1:1);
  - `executed_nodes`, que é o número de nós do fecho executados em todas as 32 datas e é sempre igual ao tamanho do fecho;
  - `instances`, `execution_status`, `result_status`;
  - resultado final (value, state, detail) por instância em 2026-02-01.
- **Nó → alvos.** `nodes.csv` tem uma linha por nó com:
  - `order` e `kind`;
  - `result_identity` (variável@frequência);
  - `dependencies`, `upstream_nodes`, `events_per_day`, `dates_executed`;
  - `dependent_targets` (lista de todos os alvos cujo fecho contém o nó);
  - `execution_status`.
- **Verificações do harness:**
  - todo alvo tem ≥ 1 nó produtor, contido no seu fecho;
  - todo nó serve ≥ 1 alvo (não há nó órfão).
- **Resultado:**
  - 421/421 alvos `EXECUTED` com resultado final sem estado (`VALUE_WITHOUT_STATE`);
  - 427/427 nós `EXECUTED` em 32/32 datas;
  - nenhuma exceção formal foi necessária.

## 8. Planner/engine reconciliation

`checks.check_nodes` compara, por data, a lista de nós do plano com os nós que emitiram eventos no `ExecutionTrace`. Ele detecta cinco situações:

- `PLANNER_ONLY_NODE`: nó planejado sem execução;
- `ENGINE_ONLY_NODE`: execução sem nó no plano;
- `NODE_EXECUTED_TWICE`;
- `NODE_ORDER_DIFFERS_FROM_PLAN`;
- `NODE_EVENT_COUNT`: o número de eventos do nó difere do número esperado de instâncias. O esperado é `materialize_equation` para equações, as instâncias da regra para agregações e as instâncias do vínculo para transferências.

`checks.check_targets` exige que cada alvo grave **todas** as suas instâncias espaciais em **todas** as datas, e acusa `TARGET_NOT_EXECUTED` e `TARGET_OUTSIDE_UNIVERSE`.

Resultado em 32 datas:

- planner nodes = engine nodes = 427;
- 0 planner-only, 0 engine-only, 0 execuções duplicadas;
- a ordem é idêntica à do plano;
- as contagens batem.

**Orquestrador × `ForecastEngine`.** Para cada data e cada bloco, as equações do bloco são recalculadas pelo caminho por bloco (`ForecastEngine.calculate_from_definition_registry`):

- o cálculo roda num contexto espelho que recebe todos os resultados do contexto integrado, exceto os alvos daquele bloco;
- o espelho recebe também os parâmetros dos seeds e roda dentro de `effective_window(data)`.

O resultado são 12 544 comparações (392 instâncias × 32 datas), com 0 diferenças em `[tipo, repr(valor), state, detail]`. Isso é **consistência entre caminhos** que compartilham o engine, não oráculo de correção.

## 9. Interblock graph

Arestas interbloco efetivamente usadas pelo plano, derivadas de `_deps` e `_producers`, sem vínculo inventado:

```text
production -> energy
production -> max_ht
production -> yield
yield      -> production
```

(`area_41 <- yield` existe no registro, mas `area_41` está fora do universo.)

- **Ordem das dependências.** Para cada nó, todos os nós produtores das suas dependências aparecem antes dele no plano (`dependencies_precede_consumers = true`).
- **Ciclo production ↔ yield.** Existe no nível de bloco e não existe no nível de variável:
  - `TRANSFER:VAR11031` (production VAR12031 → yield) fica na posição 193;
  - `TRANSFER:VAR12062` (yield VAR11226 → production) fica na posição 257.
  - O planner atual já resolve esse ciclo intercalando nós dos dois blocos numa ordem topológica de variáveis. O ciclo não foi quebrado artificialmente, e não houve workaround.
  - Cada nó executa uma única vez por data (`NODE_EXECUTED_TWICE` nunca ocorre).
  - Não há iteração de convergência porque não há ciclo de variáveis.

## 10. Transfer coverage

Evidência: `evidence/transfers.csv`. Para cada evento de transferência, `checks.check_transfers` lê o consumidor e o produtor no contexto, na mesma identidade temporal (`period_id` e `as_of`), e exige igualdade exata de `[tipo, repr(valor), state, detail]`.

| # | Source | Variable | Destination | Variable | Frequency | Executed | Verified |
|---|---|---|---|---|---|---:|---:|
| 1 | production | VAR12031 | yield | VAR11031 | diário | 224 | 224 |
| 2 | yield | VAR11226 | production | VAR12062 | diário | 224 | 224 |
| 3 | production | VAR12031 | max_ht | VAR13062 | diário | 224 | 224 |
| 4 | production | VAR12046 | max_ht | VAR13092 | diário | 224 | 224 |
| 5 | production | VAR12046 | energy | VAR18001 | diário | 224 | 224 |
| 6 | production | VAR12041 | energy | VAR18005 | diário | 224 | 224 |
| 7 | production | VAR12043 | energy | VAR18006 | diário | 32 | 32 |
| 8 | production | VAR12044 | energy | VAR18007 | mensal | 32 | 32 |
| 9 | production | VAR12031 | energy | VAR18008 | diário | 224 | 224 |
| 10 | production | VAR12033 | energy | VAR18009 | diário | 32 | 32 |
| 11 | production | VAR12034 | energy | VAR18010 | mensal | 32 | 32 |
| 12 | production | VAR12066 | energy | VAR18011 | anual | 224 | 224 |

- **Cobertura:** 12 / 12 transferências e 1 920 / 1 920 eventos (32 datas × instâncias).
- **Valor, state e detail em 2026-02-01:** registrados no CSV.
- **Estados através das transferências.** No cenário SC1 (§13), 11 das 12 transferências carregam estado. Todos os seus eventos com estado passam pela mesma verificação exata: a consumidora recebe o mesmo `state` e o mesmo `detail` do produtor.
  - A exceção é `TRANSFER:VAR18011`: a sua origem VAR12066 é uma entrada do plano, sem ancestral estado-injetável no cenário.

## 11. Temporal protocol

- A sequência começa em **2026-01-01** e avança dia a dia até **2026-02-01**: 32 datas contíguas, confirmadas no código (`contiguous = true`).
- O contexto é o mesmo em toda a sequência. Uma data isolada no meio do ano não é executável, porque as agregações móveis e YTD exigem o histórico desde 1º de janeiro.
- A cada data, o harness faz três coisas:
  1. semeia as entradas do dia;
  2. chama `InterblockExecutionOrchestrator.execute(plan, context, data)`, que abre `effective_window(data)`;
  3. registra o trace.

## 12. Temporal coverage

Evidência: `evidence/temporal_coverage.csv` (uma linha por data). As 32 datas são idênticas em cardinalidade:

| Date | Targets | Nodes | Transfers | Monthly events | Annual/YTD events | Events | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01-01 | 421 | 427 | 60 | 313 | 185 | 847 | 0 |
| … (2026-01-02 .. 2026-01-31, todas iguais) | 421 | 427 | 60 | 313 | 185 | 847 | 0 |
| 2026-02-01 | 421 | 427 | 60 | 313 | 185 | 847 | 0 |

- Nenhuma data executa um plano vazio ou incompleto. O harness falha se alguma linha tiver alvos ≠ 421 ou nós ≠ 427.
- **Virada de mês:**
  - o snapshot de todas as chaves `period_id = 2026-01` tirado antes de 2026-02-01 é idêntico ao estado final, então não há perda, sobrescrita nem duplicação;
  - as 313 identidades mensais de janeiro têm exatamente 31 janelas (`window_end` 2026-01-01..2026-01-31);
  - as 313 identidades de fevereiro abrem com a janela única `2026-02-01`.
- **Anual/YTD:**
  - há 48 regras de agregação anuais no plano;
  - as 185 identidades anuais têm 32 janelas cada;
  - a classificação é **`YEAR_TO_DATE_PARTIAL_COVERAGE`**. Nunca é FULL_YEAR, porque 32 dias não cobrem o ano.

## 13. State propagation

Os estados são injetados só no contexto de teste, com `set_variable_result`.

- **Oráculo:** diferença entre execuções gêmeas (`checks.check_state_diff`). As duas execuções têm as mesmas entradas, e só a execução com estado recebe a injeção.
  - As duas precisam ter exatamente as mesmas chaves.
  - Toda chave que difere precisa (i) ter exatamente o `state` e o `detail` injetados e (ii) pertencer a uma variável descendente da origem no grafo do planner.
  - Qualquer outra diferença é `STATE_DIFFERENCE`, em particular um vazamento para variável não descendente.
- **SC1 — cadeia completa em 32 datas.**
  - Injeção: VAR12024 (`fator_ajuste_lth`, mensal), L3 e L4, recebe `Result(None, INVALID_INPUT, "fa")` só no período 2026-01.
  - Resultado: 6 452 chaves diferem, todas descendentes e todas `INVALID_INPUT/"fa"`. Elas se distribuem pelos 4 blocos: production 1 901, yield 1 240, energy 1 395 e max_ht 1 914.
  - A cadeia percorrida é a do contrato: `state source → producer (VAR12031) → transfer (VAR11031, VAR13062, VAR18008) → consumer → aggregation`.
- **Isolamento — mesmo grafo, alvo A com S e alvo B sem S.**
  - VAR12031 L3 recebe o estado, enquanto VAR12031 L1 e L4 não o recebem. Nos três blocos consumidores, VAR11031, VAR13062 e VAR18008 em L1 e L4 também não recebem o estado.
- **Isolamento entre datas.** VAR12031 L3 em 2026-02-01 não tem estado, porque o estado injetado era do período 2026-01.
- **Isolamento entre contextos.** O contexto limpo tem **0** resultados com estado ou detail após toda a sequência, os cenários e as reexecuções.

## 14. IF causal tests

**EQ12012 (production, VAR12031).** A condição é `A/24 >= VAR12066` (`lth_meta`, anual), e só o ramo verdadeiro lê VAR12024. No SC1, VAR12066 é sobrescrita por linha: L3 = 0.0001 (ramo ativo) e L4 = 1e6 (ramo inativo). VAR12024 recebe estado nas **duas** linhas.

- L3: o estado propaga pelo ramo executado.
- L4: VAR12031 continua sem estado, com o valor igual ao da execução gêmea limpa. Não há propagação a partir do ramo não executado nem cálculo especulativo.

**EQ18003 (energy, VAR18017).** A fórmula é `(VAR18015+P) if VAR18012 > PARAM18001 (72) else (VAR18016+P)`. VAR18012 está pendente de `temperature_lp` e é uma entrada livre no fixture; `temperature_lp` real não é usado.

- **SC2:** VAR18012 L1 = 10 (ramo `else` ativo, que lê VAR18016) e L2 = 100 (ramo `then`). VAR18016 L1 e L2 recebem `Result(None, VALIDATION_FAILED, "t")`.
- **Ramo ativo, L1:** `["NoneType","None","VALIDATION_FAILED","t"]`. O estado propaga para os descendentes executados, 19 variáveis de energy (VAR18017, VAR18019..VAR18028, VAR18042..VAR18045 e VAR18049..VAR18052).
- **Ramo inativo, L2:** `["float","1.4509999999999998",null,null]`, sem propagação.
- O oráculo de diferença não encontrou vazamento. Rótulo: `REAL_DERIVED_TEST_RESULT`.

## 15. State-aware aggregation

**SC3 (5 datas).** `Result(None, INVALID_INPUT, "agg")` é injetado em 2026-01-03 nas fontes das regras **reais** de cada tipo. VAR11001 L1 recebe a mesma injeção também em 2026-01-04, o que cobre o caso de mesmo estado e mesmo detail em dois componentes da janela.

| tipo | regra real (instância) | 2026-01-02 | 2026-01-03 | 2026-01-05 |
|---|---|---|---|---|
| AVERAGE | AGR-YIELD-EOC_SOLIDS-LINHA-L1_L7-MENSAL-AVERAGE (linha/L1) | 1.00015 | INVALID_INPUT/agg, value None | INVALID_INPUT/agg |
| SUM | AGR-MAX_HT-MASSA_TOTAL_MAX_HT_SOMATORIO-GRUPO-L1_L3-MENSAL-SUM e -ANUAL-SUM (via VAR13113 → VAR13068) | 0.03322901957785046 | INVALID_INPUT/agg | INVALID_INPUT/agg |
| WEIGHTED_AVERAGE | AGR-ENERGY-ESPECIFICO_VAPOR_OUTROS-GRUPO-L1_L7-MENSAL-WEIGHTED_AVERAGE (via VAR18046 → VAR18047) | 11.884293149167227 | INVALID_INPUT/agg | INVALID_INPUT/agg |
| MOVING_AVERAGE | AGR-PRODUCTION-PRODUCAO_PLANTA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE (via VAR12056 → VAR12048) | 3.029511267359043 | INVALID_INPUT/agg | INVALID_INPUT/agg |

- Antes da injeção a janela não tem estado.
- A partir da injeção o estado permanece no acumulado (Policy B): compõe o estado e deixa o valor em None se algum componente não tem valor.
- O oráculo de diferença não encontrou vazamento.

**SC4 (contextos próprios).** O VAR11001 L2 recebe INVALID_INPUT "x" em 2026-01-03, e em 2026-01-04 recebe:

- `VALIDATION_FAILED "x"`: a agregação levanta **`MULTI_STATE_COMBINATION_UNDEFINED`**;
- `INVALID_INPUT "y"`: a agregação levanta **`MULTI_DETAIL_COMPOSITION_UNDEFINED`**;
- `Result(2.0, None, "x")`: é recusado na construção com **`DETAIL_WITHOUT_STATE`**.

Nenhuma regra foi redefinida.

## 16. Temporal identity

- **Mesmo alvo com janelas efetivas diferentes gera identidades distintas:**
  - mensal: 31 `window_end` distintos em janeiro por identidade, e um em fevereiro;
  - anual: 32 janelas por identidade.
- **Diário:** chaves sem `window_end`; o dia é o próprio `period_id`.
- **Mesmo alvo e mesma janela** são reutilizados na reexecução sem criar chave nova (§17).
- A transferência preserva a identidade temporal: o consumidor e o produtor são lidos no mesmo `period_id` e `as_of`.

## 17. Reexecution

Depois da sequência completa, 2026-01-15 (data interna) e 2026-02-01 (última data, janela aberta) são reexecutadas no mesmo contexto:

| data | FIRST_RUN transfers | REEXECUTION transfers | store igual | chaves novas | estados | eventos iguais |
|---|---|---|---|---:|---:|---|
| 2026-01-15 | WRITTEN 60 | UNCHANGED 60 | sim | 0 | 0 | sim |
| 2026-02-01 | WRITTEN 60 | UNCHANGED 60 | sim | 0 | 0 | sim |

- A reexecução reproduz a mesma lista de eventos da primeira execução. A única diferença é o status das transferências, que passa de WRITTEN para UNCHANGED.
- O store continua com o mesmo hash. `REEXECUTION store_sha256 = 619b4abd…` é igual ao de RUN_A.
- Não há duplicação, acumulação nem estado residual.

## 18. Determinism

Fingerprint de resultados = SHA-256 do JSON canônico de:

- o store completo (chave estável `(entity, scope_type, scope_value, period_id, window_end)` e resultado `[tipo, repr, state, detail]`), que inclui alvos, nós e transferências;
- os eventos de cada data, sem o campo `step` e ordenados por identidade.

O fingerprint não tem timestamps.

| execução | como | results_sha256 | store_sha256 |
|---|---|---|---|
| RUN_A | processo atual, ORDER_A | `d4de1aea…e10d` | `619b4abd…730c` |
| RUN_B | subprocesso, ORDER_B, PYTHONHASHSEED=0 | `d4de1aea…e10d` | `619b4abd…730c` |
| HASH_SEED_A | subprocesso, ORDER_A, PYTHONHASHSEED=0 | `d4de1aea…e10d` | `619b4abd…730c` |
| HASH_SEED_B | subprocesso, ORDER_A, PYTHONHASHSEED=4242 | `d4de1aea…e10d` | `619b4abd…730c` |
| REEXECUTION | store após as reexecuções | — | `619b4abd…730c` |

- **ORDER_B** tem o mesmo conteúdo com a ordem de inserção invertida em:
  - todos os registros do catálogo (variáveis, equações, instâncias de agregação, parâmetros, `block_of`);
  - a lista de vínculos;
  - a ordem dos blocos passada ao registro de vínculos.

  O planner não foi alterado.
- **Ordem de blocos e de links:** suportada como ordem de entrada. O planner produz a **mesma** ordem canônica de 427 nós nas duas ordens (`identical_plan_order = true`), e os resultados são byte-idênticos.
- O hash do grafo também é idêntico: `e372425d…d1ff`.

## 19. Negative tests

Os testes estão em `tests/test_stage3_4c_integrated.py` e rodam sobre dados reais do fixture, com mutações em memória. Nenhuma remoção toca o modelo real.

| teste | mutação controlada | detectado como |
|---|---|---|
| omissão de alvo | plano real sem um alvo folha, executado; e uma instância espacial removida das observações | `TARGET_NOT_EXECUTED` |
| omissão de nó | `ExecutionPlan` em memória sem o último nó, executado pelo orquestrador | `PLANNER_ONLY_NODE 2026-01-01 <nó>` (exatamente um) |
| nó espúrio, repetido ou com contagem errada | observações sintéticas | `ENGINE_ONLY_NODE`, `NODE_EXECUTED_TWICE`, `NODE_EVENT_COUNT` |
| transferência adulterada | consumidor VAR11031 L2 sobrescrito com 999.0 após a execução | `INTERBLOCK_FAILURE 2026-01-01 TRANSFER:VAR11031 linha/L2` |
| transferência removida | registros de `TRANSFER:VAR18011` suprimidos | `INTERBLOCK_FAILURE transferência não executada` |
| propagação de estado corrompida | vazamento para não descendente; detail trocado; chave removida; estado perdido ou indevido | `STATE_DIFFERENCE` |

O teste `test_unmutated_short_run_passes_every_check` confirma que os mesmos verificadores devolvem vazio sem mutação.

## 20. Fixture integrity

| construção | graph hash |
|---|---|
| fixture ORDER_A | `e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff` |
| fixture ORDER_A reconstruído | idem |
| fixture ORDER_B | idem |
| `real_derived_orchestrator()` dos testes da 3.2 | idem |
| orquestrador oficial (16 pendências) | diferente (sensibilidade confirmada em teste) |

- **O hash cobre o grafo lógico canônico, ordenado:**
  - nós: tipo, id, bloco, produz, depende;
  - vínculos: consumidor, origem, frequência, instâncias;
  - pendências.
- **O hash não depende de ordem de sistema de arquivos, ordem de dicionário, UUID nem timestamp.**
- **REAL_DERIVED continua fixture:**
  - `pending_in_fixture = 0`;
  - `pending_official = 16`.

## 21. Protected artifacts

```text
git diff -- app/    -> vazio
git diff -- data/   -> vazio  (inclui data/workbooks/, seeds e interblock_links.json)
git diff -- tools/  -> vazio
```

- **Arquivos adicionados:** apenas `audit/stage3_4/integrated/`, este relatório e `tests/test_stage3_4c_integrated.py`.
- **Defeitos de produção:** nenhum foi encontrado.
- **Falhas de harness corrigidas durante a etapa**, todas no próprio harness e nenhuma em `app/`:
  - o contexto espelho da comparação com o engine não tinha os parâmetros dos seeds;
  - uma verificação de "resultado ausente" nunca disparava, porque a leitura levanta exceção em vez de devolver None.

## 22. Test results

| momento | resultado |
|---|---|
| antes | 1834 passed, 0 failed, 0 skipped |
| depois | 1845 passed, 0 failed, 0 skipped (+11 da 3.4C) |

- Nenhum teste foi removido ou enfraquecido.
- `ruff check` passa em `audit/stage3_4/integrated/` e no novo teste.
- Tempo:
  - harness completo: ≈ 70 s (sequência de 32 dias, 3 subprocessos de determinismo e 4 cenários de estado);
  - testes da 3.4C: ≈ 70 s.

## 23. Limitations

1. **Sem oráculo independente de correção** (`INDEPENDENT_ORACLE = NO`, `ENERGY_PYTHON_ORACLE = NOT_USED`). A etapa prova completude, consistência, contrato de estados, identidade temporal e determinismo. Ela não prova que os valores numéricos estão certos no negócio.
2. **O fixture REAL_DERIVED não é operacional.** As 16 consumidoras pendentes são entradas sintéticas, e os resultados são `REAL_DERIVED_TEST_RESULT`.
3. **Entradas sintéticas determinísticas**, não dados reais de planta.
4. **A comparação orquestrador × `ForecastEngine` cobre as equações.** O engine de equações é compartilhado pelos dois caminhos, então é uma verificação de consistência. As agregações são verificadas por reconciliação de eventos e instâncias, pelos cenários de estado e pela 3.4B e 3.3C, e não por um segundo caminho de cálculo na 3.4C.
5. **A cobertura anual é YTD parcial** (32 dias). A virada de ano não é exercitada.
6. **O ciclo production ↔ yield existe só no nível de bloco.** Não há ciclo de variáveis nem convergência iterativa a testar.
7. **Os cenários SC2 e SC3 usam os primeiros 3 e 5 dias.** O SC1 cobre as 32 datas.
8. **Os testes negativos mutam o plano, o contexto e as observações em memória**, como exige §45–§47. Nada é mutado em disco.

## 24. Evidence

| arquivo | conteúdo |
|---|---|
| `audit/stage3_4/integrated/fixture.py` | fixture REAL_DERIVED (ORDER_A/ORDER_B), hash do grafo, entradas determinísticas |
| `audit/stage3_4/integrated/checks.py` | verificadores puros (alvos, nós, transferências, estado) |
| `audit/stage3_4/integrated/run_integrated.py` | driver completo e `--fingerprint` para determinismo |
| `audit/stage3_4/integrated/evidence/integrated_summary.json` | universo, grafo, temporal, reexecução, determinismo, estados, blocos, transferências, cobertura, problemas (vazio), `result = PASS` |
| `audit/stage3_4/integrated/evidence/targets.csv` | 421 alvos: nós do planner, nós executados, status, resultado final (value, state, detail) |
| `audit/stage3_4/integrated/evidence/nodes.csv` | 427 nós: ordem, identidade, dependências, alvos dependentes, datas executadas |
| `audit/stage3_4/integrated/evidence/transfers.csv` | 12 transferências: origem, destino, frequência, eventos executados e verificados, value/state/detail |
| `audit/stage3_4/integrated/evidence/temporal_coverage.csv` | 32 datas: alvos, nós, transferências, eventos mensais e anuais, erros |
| `tests/test_stage3_4c_integrated.py` | 11 testes (execução ao vivo, evidência, universo, fixture, negativos) |

**Cobertura por bloco** (derivada do planner):

| Block | Targets | Equation Nodes | Aggregation Nodes | Transfer Nodes | Executed |
|---|---:|---:|---:|---:|---:|
| yield | 219 | 138 | 80 | 1 | 219 |
| production | 50 | 27 | 28 | 1 | 56 |
| energy | 43 | 24 | 11 | 8 | 43 |
| max_ht | 109 | 29 | 78 | 2 | 109 |
| **TOTAL** | **421** | **218** | **197** | **12** | **427** |

(A coluna Executed conta nós executados nas 32 datas. Em production, 56 nós servem 50 alvos por causa das 7 definições de VAR12041.)

## 25. Final gate

Todos os critérios de aceite de §54 do prompt estão satisfeitos:

- baseline;
- cobertura 421/421 e 427/427;
- planner ↔ engine;
- interblock 12/12;
- temporal;
- estados;
- reexecução;
- determinismo;
- testes negativos;
- integridade;
- suíte verde.

Nenhum defeito de produção foi encontrado, e `app/`, `data/` e `tools/` não foram alterados.

STAGE_3.4C_GATE: PASS
