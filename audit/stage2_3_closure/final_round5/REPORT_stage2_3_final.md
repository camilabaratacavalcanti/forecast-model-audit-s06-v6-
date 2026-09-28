# Etapa 2.3 — Auditoria integral dos cinco workbooks (rodada 5)

Auditoria célula a célula, linha a linha, workbook a workbook — não por diferença entre versões. Nenhum workbook, código,
teste, seed ou contrato alterado. Único artefato: este relatório e as evidências em `final_round5/`.

## 25.1 Executive Summary

| resultado | valor |
|---|---|
| gate | **STAGE_2.3_GATE: PASS** |
| BLOCKER | 0 |
| NON_BLOCKING | 3 |
| 2.4_IMPLEMENTATION_GAP | 8 casos (1 mecanismo: agrupar instâncias por linha no builder) |
| CONTRACT_GAP | 0 |
| INFORMATIONAL | 4 |

Os cinco workbooks estão conformes ao contrato fechado. Os 40 parâmetros têm valor numérico físico; os 572 `status` e
`value_type` são válidos; o validador de seed da plataforma não rejeita nenhuma linha; todas as 207 agregações têm origem
explícita; as 13 dependências entre os cinco workbooks resolvem por identidade completa.

## 25.2 Pre-flight

| item | valor |
|---|---|
| commit | `c95abcb71fb9a88f03da50911a43397b61d60ed2` (= `origin/feature/area-41-block`) |
| branch | `feature/area-41-block` |
| origin/main | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` |
| commits locais sobre origin/main (todos publicados) | `07af71b` migração `numerico/categorico`; `1bfe3ae`, `d0192f3`, `c95abcb` relatórios de auditoria |
| working tree | limpo |
| testes iniciais | 1414 passed, 0 failed, 0 errors |

## 25.3 Workbook Inventory

| bloco | versão | arquivo auditado | bytes | SHA-256 | aba | dimensão | linhas semânticas |
|---|---|---|---:|---|---|---|---:|
| area_41 | v8 | `27ac153c-descritivo_das_vari_veis_A41_v8.xlsx` | 38 454 | `be2372b4f4f35f5aea720dcc00c680f3e47e359138995dd35a6dcabd3d603528` | `A41` | A1:R308 | 54 |
| energy | v5 | `b7873d62-descritivo_das_vari_veis_energy_v5.xlsx` | 37 598 | `34c1c88af318e57026c08c21fd2a1cf308258e575eddbb11d98ba0bba6878047` | `energy` | A1:R307 | 56 |
| MaxHT | v9 | `28284f78-descritivo_das_vari_veis_MaxHT_v9.xlsx` | 45 832 | `74d5cbb7624d5c7101b5f25ecd76e156c9d019968c7e5f9af2ed04aa50b27004` | `MaxHT` | A1:S336 | 120 |
| production | v6 | `f72ff723-descritivo_das_vari_veis_production_v6.xlsx` | 36 488 | `17cb83ca15d92c0b3243a606ddfd194a110dcc4f01fb71bf30511a4c6fb07210` | `production` | A1:R302 | 88 |
| yield | v9 | `e8cae0eb-descritivo_das_vari_veis_yield_v9.xlsx` | 42 399 | `1c7b5684cc49d9498edceb520ced2e8a1f673812057d4094846820074098a76b` | `yield` | A1:R255 | 254 |

Todos com timestamp 2026-09-28 17:56:08. As cópias de A41 v8, energy v5 e yield v9 anexadas nesta rodada são byte a byte
idênticas às da rodada anterior (mesmo SHA-256); foram usadas as anexadas nesta rodada. Uma aba visível por arquivo; nenhuma
aba oculta, linha/coluna oculta, fórmula Excel, named range, data validation ou comentário.

## 25.4 Contract Compliance

Método: `final_round5/integral.py` percorre todas as células de todas as linhas semânticas (tipo físico, espaços nas pontas,
caracteres ocultos, enum, escopo via `ScopeResolver`, unidade via `ALLOWED_UNITS`, `value_type`, `allowed_values`,
`declared_result_states`); os validadores oficiais (`variable_seed_validator`, `parameter_seed_validator`) rodam sobre todas as
linhas com os valores do workbook como estão (só IDs e `source_reference`, que são do builder, e `description` vazia foram
preenchidos); A019 e parser via `probe2.py`; coerência `value_type`/estados via AST de cada expressão.

| regra | resultado | evidência |
|---|---|---|
| `value_type` | PASS | 572/572 ∈ `{numerico, categorico}` (568 `numerico`, 4 `categorico` = `hes`); 0 `numeric`/`categorical` nos workbooks |
| `value` | PASS | 40/40 parâmetros com `int`/`float` físico (`parameters.csv`); 0 textos numéricos |
| estados | PASS | `NO_APPLICABLE_RULE → "F"` só em A41 r39, r42 (produtor local); 4 ocorrências de `"F"`, todas com aspas; 0 `→ F` |
| identidade | PASS | 0 colisões de `name + frequency + scope_type + scope_value` nos cinco |
| escopo | PASS | todos os pares aceitos pelo `ScopeResolver`; 0 `L6_7`; `PLANTA` canônico |
| frequência | PASS | variáveis ∈ `{diário, mensal, anual}` |
| unidades | PASS | todas em `ALLOWED_UNITS`, nenhuma vazia; 0 `tpd`; `tanque` = `-` |
| expressões | PASS | 234 expressões executáveis parseadas; 0 inválidas; `ln()` 6× (A41); 4 recusas A019 = 2.4 gap |
| agregações | PASS | 207 com origem explícita; 30 SUMs coerentes; 9 médias ponderadas com peso presente |
| metadados | NON_BLOCKING | ver 25.4.1 |
| validador de seed | PASS | 0 rejeições em 572 linhas |
| coerência `value_type`/estados (AST) | PASS | nenhum literal de resultado não declarado, nenhuma comparação textual com variável numérica, nenhuma aritmética sobre categórica, todo literal comparado ∈ `allowed_values` |

### 25.4.1 Achados não bloqueantes e informativos

| id | classe | workbook | local | achado |
|---|---|---|---|---|
| NB-1 | NON_BLOCKING | yield v9 | E92, F92 (`ltp_tc`, variable, diário) | `value = 273` e `version = 1` preenchidos numa **variável** (resquício de quando `ltp_tc` era parâmetro, v4). Para variáveis esses campos não fazem parte do contrato e são ignorados; sem efeito em identidade, tipo ou referência |
| NB-2 | NON_BLOCKING | production v6, yield v9 | coluna C | `description` vazia em 88/88 e 254/254 linhas. Os seeds atuais trazem descrições; o validador exige descrição no seed. Registrado para a 2.4 (fonte das descrições) |
| NB-3 | NON_BLOCKING | energy, MaxHT, production, yield | coluna K | `source_reference` vazia em 56, 117, 86, 199 linhas. É preenchida pelo builder (nome do workbook) nos seeds existentes |
| I-1 | INFORMATIONAL | production v6 | r6, r11, r17, r23, r76 | somas anuais sem sufixo `_somatorio` (`consumo_bauxita`, `consumo_*_grupo`, `producao_planta` anual). Não há média anual de mesmo nome, portanto sem colisão; convenção de nome diferente das somas mensais |
| I-2 | INFORMATIONAL | yield v9 | r59–r65 | a entidade de grupo chama-se `ltp_a_c_grupo` (renomeada na v8); nenhuma referência a `ltp_a_grupo`; nome e referências consistentes |
| I-3 | INFORMATIONAL | energy × production | `pick_up`, `lth_meta` | energy declara 1 definição `linha/L1_L7`; production declara as 7 instâncias por linha do mesmo conceito — diferença representacional |
| I-4 | INFORMATIONAL | energy, production, MaxHT | coluna `fonte` | 21 entradas vêm de blocos fora dos cinco (maintenance, maintenance_plan, forecast, temperature_lp, alumina, area_04_13); não verificáveis nesta auditoria |

## 25.5 Parameter Type Audit

```text
No numeric parameter values stored as text were found.
```

40 parâmetros (A41 7, energy 4, MaxHT 4, production 17, yield 8), todos com `value` físico `int`/`float`, `version` inteiro,
`value_type = numerico`, `status = ativo`, sem expressão. Lista completa: `parameters.csv`.

## 25.6 A019 Matrix (`a019_cases.csv`)

Contrato A019 (`reference_resolver`, regra 4): resolução por instância do consumidor pelo escopo mais específico. O resolver
recusa quando essas instâncias caem em linhas distintas do workbook ("uma expressão grava um único ID"); o runtime já
representa o conceito por linha como uma definição com instâncias por `scope_value` (seeds `PARAM12001 lth_meta`,
`PARAM11003 tanque_base`, `VAR11239 tanque`).

| consumidor | escopo consumidor | produtor | instâncias | forma | resolução | classificação |
|---|---|---|---:|---|---|---|
| production `lth` r35 | linha/L1_L7 | `lth_meta` anual | 7 | contextual | recusa | 2.4_IMPLEMENTATION_GAP |
| production `oee` r48 | linha/L1_L7 | `lth_meta` anual | 7 | contextual | recusa | 2.4_IMPLEMENTATION_GAP |
| production `producao` r71 | linha/L1_L7 | `pick_up` diário | 7 | contextual | recusa | 2.4_IMPLEMENTATION_GAP |
| yield `n_ppt` r107 | linha/L1_L7 | `tanque` diário | 7 | contextual | recusa | 2.4_IMPLEMENTATION_GAP |
| yield `n_ppt` r107 | linha/L1_L7 | `tanque_base` anual | 7 | contextual | recusa | 2.4_IMPLEMENTATION_GAP |
| A41 `retirada_condensado_linha` r52, r53 | linha/L1_L7 | mesmo nome diário | 7 | agregação temporal | builder | 2.4_IMPLEMENTATION_GAP (2) |
| production `pick_up` mensal r60 | linha/L1_L7 | `pick_up` diário | 7 | agregação temporal | builder | 2.4_IMPLEMENTATION_GAP |
| production `oee_total` r50 | linha_grupo/L1_L7 | `lth_meta` | 7 | `@L1…@L7` | resolve | CONFORME |
| production `pick_up_total` r61 | linha_grupo/L1_L7 | `pick_up` | 7 | `@L1…@L7` | resolve | CONFORME |
| production `pick_up` r53–r59 | linha/L1 … L7 | `pick_up_yield` | 7 | contextual, consumidor de 1 linha | resolve | CONFORME (7) |
| A41 `retirada_condensado_grupo` r22 | linha_grupo/L1_L3 | `valor_retirada` | 3 | `@L1…@L3` | resolve | CONFORME |
| A41 `retirada_condensado_grupo` r39, r42 | linha_grupo/L4_L5, L6_L7 | `hes` | 4 | `@L4…@L7` | resolve | CONFORME (2) |

20 casos: 12 CONFORME, 8 2.4_IMPLEMENTATION_GAP, 0 WORKBOOK_ISSUE, 0 CONTRACT_GAP. As únicas quatro recusas A019 nos cinco
workbooks são as quatro linhas contextuais da tabela.

## 25.7 Aggregation Audit (`aggregations.csv`)

207 agregações temporais: AVERAGE 166, SUM 30, WEIGHTED_AVERAGE 9, MOVING_AVERAGE 2. 204 com origem explícita no mesmo escopo
e unidade coerente; 3 sobre instâncias por linha (2.4). 25 variantes `_somatorio` (MaxHT 20, production 5): 0 auto-referências,
todas citam a origem diária real. 30 SUMs coerentes por `required_sum_factor` (0 incoerentes). Médias móveis: energy r6 ←
`producao_planta_t_h` (`linha_grupo/L1_L7`), production r77 ← `producao_planta`. Agregação espacial só por equações explícitas
(`@L1 + … + @L7`, `@L1_L3 + @L4_L5 + @L6_L7`); nenhuma dentro de regra temporal; `@grupo` nunca como frequência.

## 25.8 Cross-Workbook Matrix (`cross_workbook.csv`)

| consumidor | entidade | frequência | escopo | unit | produtor | resultado |
|---|---|---|---|---|---|---|
| A41 | `lth` | diário | linha/L1_L7 | m³/h | yield | OK |
| energy | `producao` | diário | linha/L1_L7 | t/d | production | OK |
| energy | `pick_up` | diário | linha/L1_L7 | g/l | production | OK (7 instâncias no produtor) |
| energy | `pick_up_total` | diário, mensal | linha_grupo/L1_L7 | g/l | production | OK |
| energy | `lth` | diário | linha/L1_L7 | m³/h | production | OK |
| energy | `lth_total` | diário, mensal | linha_grupo/L1_L7 | m³/h | production | OK |
| energy | `lth_meta` | anual | linha/L1_L7 | - | production | OK (7 instâncias no produtor) |
| MaxHT | `lth` | diário | linha/L1_L7 | m³/h | production | OK |
| MaxHT | `producao` | diário | linha/L1_L7 | t/d | production | OK |
| production | `yield` | diário | linha/L1_L7 | g/l | yield | OK |
| yield | `lth` | diário | linha/L1_L7 | m³/h | production | OK |

13/13 com unidade e `value_type` iguais ao produtor. 21 entradas de blocos fora dos cinco (I-4).

## 25.9 Regression Checklist

| correção histórica | resultado | evidência |
|---|---|---|
| A41 `retirada_meta_41b` = `47.5` numérico | PASS | E33 `float` |
| A41 `retirada_meta_41x` = `47.5` numérico | PASS | E34 `float` |
| A41 `"F"` sempre com aspas; 0 `→ F` | PASS | O39, O42, P39, P42 |
| energy média móvel ← `producao_planta_t_h` | PASS | P6 |
| energy sem `tpd` | PASS | D3 `t/d` |
| MaxHT `fator_massa_total_max_ht` = `1.05` numérico | PASS | E23–E26 `float` (única diferença v8 → v9) |
| MaxHT sem outro parâmetro-texto | PASS | 4/4 numéricos |
| MaxHT `_somatorio` → fonte real | PASS | 20/20 |
| MaxHT `L1_L3`/`L4_L5`/`L6_L7` preservados; 0 `L6_7` | PASS | |
| production `fator_producao` numérico | PASS | E34 `float` |
| production `pick_up_yield` numéricos | PASS | E64–E70 `float` |
| production `status` de `pick_up_yield` | PASS | L64–L70 `ativo` (diferenças v5 → v6: só E34, E64–E70, L64–L70) |
| production `_somatorio` → fonte real | PASS | 5/5 |
| production `consumo_bauxita` com origem diária `linha_grupo` | PASS | r3 |
| production `t/d`, `t/mês`, `t/ano`; 0 `tpd` | PASS | r73, r75, r76 |
| production `PLANTA` | PASS | r26 |
| production `oee_total`, `pick_up_total` corretos | PASS | parseiam e resolvem |
| yield sem referência inexistente (`ltp_a_grupo`/`ltp_a_c_grupo`) | PASS | ver I-2 |
| yield `tanque` com unidade | PASS | D227–D233 `-` |
| yield `tanque_base` como instâncias por linha | PASS | 7 linhas L1…L7 |
| yield `L6_L7`; 0 `L6_7` | PASS | |
| yield sem parâmetro-texto | PASS | 8/8 numéricos |

## 25.10 Test Results

```text
targeted tests (contrato DSL/estados/value_type, A019, parser, escopo, agregação, validadores, seeds, builders/reconciliação): 929 passed
full suite: 1414 passed
failures: 0   errors: 0
```

Código: `VALUE_TYPES = {'numerico', 'categorico'}`; `numeric`/`categorical` rejeitados por `VariableDefinition` e pelo
validador; as duas únicas ocorrências literais estão no teste que verifica essa rejeição
(`tests/test_dsl_structural_contracts.py:339, 368`). Nenhum alias ou normalização de `value_type` — os únicos "alias"/
"normaliza" no código são de unidade (`tph`→`t/h`), do parser (`@`→`__` interno) e das ferramentas de reconciliação.

## 25.11 Final Gate

```text
STAGE_2.3_GATE: PASS
```

Blockers: nenhum. A Etapa 2.3 pode ser encerrada; os cinco workbooks estão prontos para a Etapa 2.4, que recebe:
o agrupamento das instâncias por linha no builder (8 casos A019), a fonte de `description`/`source_reference` para os seeds
de production e yield (NB-2, NB-3) e a decisão sobre o campo `value` em variáveis de entrada como `ltp_tc` (NB-1).
