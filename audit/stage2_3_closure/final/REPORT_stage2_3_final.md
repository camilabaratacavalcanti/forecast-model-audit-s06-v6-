# Etapa 2.3 — Auditoria de fechamento (rodada 4)

```text
Resultado: STAGE_2.3_GATE: BLOCKED
Motivo:    parâmetros com valor numérico gravado como texto em MaxHT v8 (4) e production v5 (8),
           e status vazio em production v5 (7) — rejeitados pelo validador de seed da plataforma.
           A41 v8, energy v5 e yield v9: PASS.
```

Nenhum workbook ou arquivo de código alterado nesta rodada.

## A. Pre-flight

| item | valor |
|---|---|
| BASELINE_SHA | `d0192f36fce790648fb829c6f08bdbfb123b92b9` |
| BRANCH | `feature/area-41-block` (= `origin/feature/area-41-block`) |
| ORIGIN_MAIN | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` |
| WORKTREE_STATUS | limpo |
| LOCAL_COMMITS (sobre origin/main, todos publicados) | `07af71b` migração `numerico/categorico`; `1bfe3ae` relatório round 2; `d0192f3` relatório round 3 |
| TESTS_BEFORE | 1414 passed, 0 failed, 0 errors |

## B. Inventário dos workbooks

| workbook | arquivo | SHA-256 | linhas semânticas | colunas | abas |
|---|---|---|---:|---:|---|
| A41 v8 | `4057bfa6-…A41_v8.xlsx` | `be2372b4f4f35f5aea720dcc00c680f3e47e359138995dd35a6dcabd3d603528` | 54 (r3–r56) | 18 | `A41` |
| energy v5 | `2321b7fd-…energy_v5.xlsx` | `34c1c88af318e57026c08c21fd2a1cf308258e575eddbb11d98ba0bba6878047` | 56 (r3–r58) | 18 | `energy` |
| MaxHT v8 | `f3d4394a-…MaxHT_v8.xlsx` | `3ebeba7d7bec9167d1894f67f028caece1aeb042dc62ff02c328eb8e762245a7` | 120 (r3–r122) | 19 (S vazia) | `MaxHT` |
| production v5 | `3d070fab-…production_v5.xlsx` | `c168215a6d6665dd575e017cf78d1274a476a60232dbe1afc263783573955fc7` | 88 (r3–r90) | 18 | `production` |
| yield v9 | `cc3a7345-…yield_v9.xlsx` | `1c7b5684cc49d9498edceb520ced2e8a1f673812057d4094846820074098a76b` | 254 (r2–r255) | 18 | `yield` |

Uma aba por arquivo, visível; sem fórmulas Excel, named ranges ou tabelas. MaxHT v8 e production v5 são **byte a byte
idênticos** aos arquivos da rodada 3 (mesmo SHA-256).

## C. Código

| item | resultado |
|---|---|
| `VALUE_TYPES` | `{'numerico', 'categorico'}`; default `numerico` |
| `numerico`/`categorico` | aceitos por `VariableDefinition` e pelo `variable_seed_validator` |
| `numeric`/`categorical` | **rejeitados** pelos dois |
| busca `"numeric"`/`"categorical"` em `app`, `tools`, `data`, `tests` | 2 ocorrências, ambas em `tests/test_dsl_structural_contracts.py` (l. 339, 368): laço que **verifica a rejeição** do vocabulário antigo. Nenhuma no contrato/runtime ativo |
| aliases / normalização / compatibilidade retroativa de `value_type` | **inexistentes**. As únicas ocorrências de "alias"/"normaliza" são o `UNIT_ALIASES` de unidades (`tph` → `t/h`), anterior e sem relação com `value_type` |
| workbooks | 572/572 células `value_type` ∈ `{numerico, categorico}`; nenhuma ocorrência de `numeric`/`categorical` |

## D. Contrato de estados

| item | resultado |
|---|---|
| `declared_result_states` | só em A41 r39 e r42 (`retirada_condensado_grupo` diário L4_L5, L6_L7): `NO_APPLICABLE_RULE → "F"` — declaração local do produtor |
| herança | 13 herdeiros no A41 (r40, r41, r43, r44, r48–r56) não declaram — correto pelo refinamento R1; nenhum downstream obrigado a redeclarar |
| `NO_APPLICABLE_RULE` | estado de negócio, resultado `"F"` no ramo final do `IF`; `hes` (entrada categórica) não declara estado |
| `"F"` canônico | 4 ocorrências nos 5 workbooks, todas em A41 (2 expressões `else "F"`, 2 declarações), todas com aspas; nenhum `F` sem aspas como literal |

## E. Identidade lógica

`name + frequency + scope_type + scope_value` aplicado a todas as 572 linhas: **0 colisões**. `L1_L3`/`L4_L5`/`L6_L7` com mesmo
nome e frequência (ex.: MaxHT `massa_total_max_ht`, `esp_maxht`, `producao_grupo`, `fluxo_para_a18_linha_grupo`) são
identidades distintas. Instâncias por linha (`linha/L1…L7`) de um mesmo nome e frequência — A41 `valor_retirada`, `hes`,
`retirada_condensado_linha`; production `lth_meta`, `pick_up`, `pick_up_yield`; yield `tanque`, `tanque_base` — são tratadas
como instâncias espaciais de um conceito, não colisões.

## F. A019 (`final/a019_cases.csv`, 20 casos)

Contrato A019 (`app/engine/reference_resolver.py`, regra 4): *"para cada instância concreta do consumidor, a definição escolhida é
a do escopo mais específico na hierarquia espacial"* — a resolução contextual por instância é prevista. O resolver atual recusa
quando as instâncias do consumidor caem em **linhas distintas do workbook** ("uma expressão grava um único ID"), porque cada linha
do workbook vira uma definição. O runtime já representa o conceito por linha como **uma** definição com instâncias por
`scope_value` (seed `PARAM12001 lth_meta` L1…L7; `PARAM11003 tanque_base`; `VAR11239 tanque`) e a suíte executa esses blocos.

| consumer | consumer_scope | source | source_scope | reference | A019 | interpretação | classificação |
|---|---|---|---|---|---|---|---|
| production `lth` r35 | linha/L1_L7 | `lth_meta` anual | linha/L1…L7 | implícita | recusa | instância L_k usa `lth_meta` L_k | 2.4_IMPLEMENTATION_GAP |
| production `oee` r48 | linha/L1_L7 | `lth_meta` anual | linha/L1…L7 | implícita | recusa | idem | 2.4_IMPLEMENTATION_GAP |
| production `producao` r71 | linha/L1_L7 | `pick_up` diário | linha/L1…L7 | implícita | recusa | idem | 2.4_IMPLEMENTATION_GAP |
| yield `n_ppt` r107 | linha/L1_L7 | `tanque` diário, `tanque_base` anual | linha/L1…L7 | implícita | recusa | idem | 2.4_IMPLEMENTATION_GAP (2 casos) |
| A41 `retirada_condensado_linha` mensal r52, anual r53 | linha/L1_L7 | mesmo nome diário | linha/L1…L7 | agregação temporal | builder | origem = conceito agrupado | 2.4_IMPLEMENTATION_GAP (2 casos) |
| production `pick_up` mensal r60 | linha/L1_L7 | `pick_up` diário | linha/L1…L7 | agregação temporal | builder | idem | 2.4_IMPLEMENTATION_GAP |
| production `oee_total` r50 | linha_grupo/L1_L7 | `lth_meta` | linha/L1…L7 | `@L1…@L7` | resolve | explícita | CONFORME |
| production `pick_up_total` r61 | linha_grupo/L1_L7 | `pick_up` | linha/L1…L7 | `@L1…@L7` | resolve | explícita | CONFORME |
| production `pick_up` r53–r59 | linha/L1 … L7 | `pick_up_yield` | linha/L1…L7 | implícita, consumidor de 1 linha | resolve | uma definição por consumidor | CONFORME (7) |
| A41 `retirada_condensado_grupo` r22, r39, r42 | linha_grupo | `valor_retirada`, `hes` | linha/L1…L3, L4…L7 | `@Lx` | resolve | explícita | CONFORME (3) |

Totais: 12 CONFORME, 8 `2.4_IMPLEMENTATION_GAP`, 0 `WORKBOOK_CONTRACT_ISSUE`, 0 `CONTRACT_GAP`.

## G. A41 v8 — **PASS**

- Diferença contra v7: apenas E33 e E34 `'47.5'` (texto) → `47.5` (número). Corrige BLK-A41-1.
- Identidade 0 colisões; A019 20/20; `@Lx` (`hes@L4…@L7`, `valor_retirada@L1…@L3`) e `@grupo` (`@L1_L3`, `@L4_L5`,
  `@L6_L7` referenciando entidades de grupo calculadas) conformes.
- `value_type`: 50 `numerico`, 4 `categorico` (`hes`); `allowed_values` de `hes` (5 valores) = exatamente os literais comparados.
- Estados: `NO_APPLICABLE_RULE → "F"` só no produtor; `"F"` com aspas.
- `ln()`: 6 usos (r6–r8, r16–r18), allowlist e aridade conformes.
- 10 agregações (médias) com origem explícita e mesmo escopo; 7 parâmetros numéricos; validador de seed: 0 mensagens.

## H. Energy v5 — **PASS**

- Diferença contra v4: apenas P6 — origem da média móvel `'producao_t_h'` → `'producao_planta_t_h'`. Corrige BLK-EN-1.
- Média móvel r6: origem `producao_planta_t_h` diário `linha_grupo/L1_L7`, mesmo escopo e unidade (`t/h`) do destino; coincide
  com a regra implementada (`AGR-ENERGY-PRODUCAO_PLANTA_T_H_MEDIA_MOVEL-…`, `source = producao_planta_t_h`).
- 7 médias ponderadas (peso `producao_planta_t_h` diário, mesmo escopo) e 3 médias com origem explícita.
- Identidade, A019 24/24, `@Lx` 49, `@grupo` 0, frequências, `value_type` (56 `numerico`), unidades (`t/d`, sem `tpd`): conformes.
- `pick_up`, `lth_meta` (1 definição `linha/L1_L7` no energy × 7 instâncias no production): diferença representacional do mesmo
  conceito — INFORMATIONAL. Validador de seed: 0 mensagens.

## I. MaxHT v8 — **BLOCKED**

- Arquivo idêntico ao da rodada 3. Correções anteriores intactas: 20 linhas `*_somatorio` citam a origem diária real
  (ex.: r72 ← `'lth_total'`); 30 SUMs nos cinco workbooks, todas dimensionalmente coerentes (`required_sum_factor`).
- Identidade, A019 29/29, `@Lx`, `@grupo`, frequências, `value_type`: conformes.
- **BLK-MX-2** — r23, r24, r25, r26 `fator_massa_total_max_ht` (L1_L3, L4_L5, L6_L7, L1_L7): coluna E `value = '1.05'` (texto).
  `parameter_seed_validator.validate_field_types` → *"campo 'value' deve ser numérico"*. Presente desde a v5 (o seed atual foi
  gerado com `float(entity["value"])` em `tools/max_ht_seed_builder.py:274`, conversão específica desse builder; o builder do
  energy repassa o valor sem conversão). Mesmo defeito corrigido no A41 nesta rodada.

## J. Production v5 — **BLOCKED**

- Arquivo idêntico ao da rodada 3. Correções anteriores intactas: `oee_total`/`pick_up_total` sem fragmentos; origens das
  somas explícitas (r5, r10, r16, r22, r75); `consumo_bauxita` com origem diária `linha_grupo` (r3); `PLANTA` (r26);
  `producao_planta` `t/d` → `t/mês` (r75) → `t/ano` (r76); sem `tpd`.
- Identidade 0 colisões; A019 24/27 (as 3 restantes = 2.4 gap, §F); `value_type` 88 `numerico`.
- **BLK-PR-4** — coluna E `value` como texto em 8 parâmetros: r34 `fator_producao = '0.88'`; r64–r70 `pick_up_yield`
  (`'14.64'` ×3, `'14.4'` ×2, `'13.3'` ×2). Validador → *"campo 'value' deve ser numérico"*. Introduzido na v4 (v1 e v3 tinham números).
- **BLK-PR-5** — r64–r70 `pick_up_yield`: coluna L `status` vazia. Validador → *"valor inválido para 'status': 'None'.
  Valores permitidos: ['ativo', 'draft', 'inativo']"*. Presente desde a v1 (o seed atual foi escrito à mão com `ativo`).

## K. Yield v9 — **PASS**

- Diferença contra v8: apenas D227–D233 `tanque` unidade vazia → `-`. Corrige BLK-YI-2.
- `ltp_a_c_grupo` existe (r59–r61 diário, r63–r65 mensal); nenhuma referência a `ltp_a_grupo`; nenhuma referência inexistente.
- `tanque_base` e `tanque` como instâncias L1…L7; `n_ppt` sobre eles = 2.4 gap (§F).
- Identidade, `@Lx` (924), frequências, `value_type` (254 `numerico`), 80 médias com origem explícita, unidades: conformes.
  Validador de seed: 0 mensagens.

## L. Agregações (`final/aggregations.csv`)

207 agregações temporais: 204 com origem explícita no mesmo escopo, 3 sobre instâncias por linha (2.4 gap). Por operação:
AVERAGE 166, SUM 30 (todas coerentes), WEIGHTED_AVERAGE 9 (peso presente), MOVING_AVERAGE 2. Nenhuma origem inferida por nome.
Agregação espacial: só por equações explícitas (`@L1 + … + @L7`, `@L1_L3 + @L4_L5 + @L6_L7`); nenhuma dentro de regra temporal;
`@grupo` nunca usado como frequência.

## M. Cross-workbook (`final/cross_workbook.csv`)

13 vínculos entre os cinco: 11 OK por identidade completa (unidade e `value_type` iguais), 2 OK com diferença representacional
(`pick_up`, `lth_meta`). `producao` em `t/d` nos três blocos que o usam. 21 entradas vêm de blocos fora dos cinco
(maintenance, maintenance_plan, forecast, temperature_lp, alumina, area_04_13) — não verificáveis aqui.

## N. Regressões e rodada anterior

| achado anterior | workbook | situação | evidência |
|---|---|---|---|
| BLK-EN-1 média móvel com origem `producao_t_h` | energy | CORRIGIDO | P6 = `'producao_planta_t_h'` |
| BLK-A41-1 parâmetros `'47.5'` texto | A41 | CORRIGIDO | E33, E34 = `47.5` (float) |
| BLK-YI-2 `tanque` sem unidade | yield | CORRIGIDO | D227–D233 = `-` |
| parâmetros com valor texto em MaxHT (r23–r26) | MaxHT | PERSISTE — **não detectado na rodada 3** | E23–E26 = `'1.05'` |
| parâmetros com valor texto e status vazio em production (r34, r64–r70) | production | PERSISTE — **não detectado na rodada 3** | E34, E64–E70 texto; L64–L70 vazios |

Na rodada 3 a checagem de tipo do `value` de parâmetros só foi feita no A41 (pela diferença entre versões); MaxHT e
production foram declarados PASS sem ela. Nesta rodada o validador de seed da plataforma foi aplicado a todas as linhas dos
cinco workbooks, e os únicos defeitos que ele rejeita são os listados em P.

Regressões A41 v7→v8, energy v4→v5, yield v8→v9: **nenhuma** — cada versão nova difere da anterior só nas células corrigidas.

## O. Testes

```text
TESTS_BEFORE: 1414 passed
alvo (DSL/estados/value_type, A019, parser/@Lx/@grupo/ln, agregação, contexto, scope): 280 passed
TESTS_AFTER:  1414 passed, 0 failed, 0 errors
```

## P. Blockers

| id | workbook | células | hoje | correção |
|---|---|---|---|---|
| BLK-MX-2 | MaxHT v8 | E23, E24, E25, E26 | `'1.05'` (texto) | `1.05` (número) |
| BLK-PR-4 | production v5 | E34; E64–E70 | `'0.88'`; `'14.64'`, `'14.4'`, `'13.3'` (texto) | números |
| BLK-PR-5 | production v5 | L64–L70 | vazio | `ativo` |

NON-BLOCKING: `description` vazia em production (88/88) e yield (254/254) e `source_reference` vazia em várias linhas — são
metadados que os seeds atuais já trazem (preenchidos pelo builder ou à mão) e não fazem parte do contrato auditado na 2.3;
registrados para a 2.4. INFORMATIONAL: diferença representacional `pick_up`/`lth_meta` entre energy e production.
2.4_IMPLEMENTATION_GAP: agrupamento das instâncias por linha no builder (8 casos, §F). CONTRACT_GAP: nenhum.

## Q. Matriz final

| tema | status |
|---|---|
| D1-D4 | PASS |
| `numerico/categorico` | PASS |
| ausência de aliases | PASS |
| ausência de normalização | PASS |
| `declared_result_states` | PASS |
| herança de estados | PASS |
| `NO_APPLICABLE_RULE` | PASS |
| `"F"` canônico | PASS |
| identidade lógica | PASS |
| A019 | 2.4 (8 casos; 12 conformes; 0 contract gap) |
| instâncias espaciais por linha | PASS |
| `@Lx` | PASS |
| `@grupo` | PASS |
| frequência | PASS |
| agregação temporal | PASS |
| agregação espacial | PASS |
| `ln()` | PASS |
| A41 v8 | PASS |
| energy v5 | PASS |
| MaxHT v8 | **FAIL** (BLK-MX-2) |
| production v5 | **FAIL** (BLK-PR-4, BLK-PR-5) |
| yield v9 | PASS |
| cross-workbook | PASS |
| testes | PASS |

```text
STAGE_2.3_GATE: BLOCKED
```
