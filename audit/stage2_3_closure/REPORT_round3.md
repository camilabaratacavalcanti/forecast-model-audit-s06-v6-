# Etapa 2.3 — Fechamento definitivo (round 3)

```text
Branch:        feature/area-41-block
HEAD:          1bfe3ae872473e3390a3d3cf9b99c552c684f515 (= origin/feature/area-41-block)
origin/main:   4510865f83fd3cf628782ad6a2e3de502aac4e7e
Resultado:     STAGE_2.3_GATE: BLOCKED — 3 blockers de workbook (energy r6, A41 r33/r34, yield r227–r233)
```

Nenhum workbook ou arquivo de código alterado nesta rodada. Nada da Stage 3 implementado.

## A. Pre-flight

| item | valor |
|---|---|
| SHA | `1bfe3ae` = `4510865` + `07af71b` (migração `numerico/categorico`) + `1bfe3ae` (relatório round 2); nada local não publicado |
| branch | `feature/area-41-block` |
| working tree | limpo |
| tests before | 1414 passed, 0 failed |

Workbooks (anexos desta execução; o texto do prompt também cita energy v3/MaxHT v7/production v4/yield v7 em §14–§17 —
foram usados os anexos, conforme §2):

| bloco | arquivo | SHA-256 |
|---|---|---|
| area_41 | `A41_v7.xlsx` (novo upload) | `04c96dba43b47734e3a8da887f11b348fbd50bac7f7c268b0b88ae407aa27fd2` |
| energy | `energy_v4.xlsx` | `fbf29395928e5fb985972a89889238bff432cd60eb6a4a33e9970400869c09f3` |
| max_ht | `MaxHT_v8.xlsx` | `3ebeba7d7bec9167d1894f67f028caece1aeb042dc62ff02c328eb8e762245a7` |
| production | `production_v5.xlsx` | `c168215a6d6665dd575e017cf78d1274a476a60232dbe1afc263783573955fc7` |
| yield | `yield_v8.xlsx` | `a41348e3e0d050eac27b4aa45d1725ca11e3654ccb8f763aee39781edb3edfec` |

Diferença célula a célula contra o round 2:

| bloco | células alteradas |
|---|---|
| A41 | O42 `NO_APPLICABLE_RULE → F` → `NO_APPLICABLE_RULE → "F"` |
| energy | D3 `tpd` → `t/d`; P6 média móvel passa a citar `'producao_t_h'` |
| MaxHT | P72, P73, P83–P88, P92, P93, P96, P97, P108–P113, P117, P118: origem `'X_somatorio'` → `'X'` |
| production | P5, P10, P16, P22, P75: origem `'X_somatorio'` → `'X'`; J26 `planta` → `PLANTA`; D75 `t/d` → `t/mês`; D76 `t/d` → `t/ano` |
| yield | B59–B61, B63–B65: `ltp_a_grupo` → `ltp_a_c_grupo` |

## B. Código

| item | resultado |
|---|---|
| `VALUE_TYPES` | `{'numerico', 'categorico'}` (commit `07af71b`) |
| busca por `"numeric"`/`"categorical"` em `app`, `tools`, `tests`, `data` | 0 literais de contrato (restam só os nomes de constantes `NUMERIC`/`CATEGORICAL` e o laço de teste que verifica a rejeição) |
| aliases / normalização / fallback | **não** — `numeric`/`categorical` são rejeitados por `VariableDefinition` e `validate_enum_values` |
| workbooks | 572/572 células `value_type` ∈ `{numerico, categorico}`; nenhuma ocorrência de `numeric`/`categorical` |

## C. Estados

- `declared_result_states` é local (refinamento R1 de D1/D2). Herança não exige redeclaração.
- `NO_APPLICABLE_RULE` é estado de negócio; declarado apenas em A41 r39 e r42 (`retirada_condensado_grupo` L4_L5, L6_L7).
- `"F"` canônico: 4 ocorrências nos cinco workbooks, todas em A41 (2 expressões `else "F"`, 2 declarações
  `NO_APPLICABLE_RULE → "F"`), todas com aspas. Nenhum `F` sem aspas como literal. Nenhum outro workbook usa `"F"`.
- `hes` não declara estado (entrada categórica; célula O vazia) — correto por R1.

## D. A019 — instâncias espaciais por linha

Contrato (docstring de `app/engine/reference_resolver.py`, regra 4, entregue em `4510865`): *"Escopo implícito: para cada
instância concreta do consumidor, a definição escolhida é a do escopo mais específico na hierarquia espacial (linha → grupo →
planta)"* — a resolução contextual por instância **faz parte do contrato**. A restrição que rejeita os casos abaixo é a
seguinte frase da mesma regra: *"Todas as instâncias do consumidor precisam apontar para a MESMA definição — uma expressão grava
um único ID."* Ela é de representação: o runtime já modela um conceito por linha como **uma** definição com uma instância por
`scope_value` (ex.: seed `PARAM12001 lth_meta` em L1…L7 com valores distintos; `PARAM11003 tanque_base`; `VAR11239 tanque`), e a
suíte executa esses blocos. Pelo §9 do prompt, as linhas do workbook são instâncias de um mesmo conceito, não definições
independentes. O que falta é o builder agrupar as linhas-instância numa definição antes de aplicar A019.

| consumer | consumer_scope | source | source_scope | reference | A019 hoje | interpretação | classificação |
|---|---|---|---|---|---|---|---|
| production `lth` (r35) | linha/L1_L7 | `lth_meta` | linha/L1…L7 (7 linhas) | implícita | rejeita ("uma expressão grava um único ID") | Caso B: instância L_k do consumidor usa `lth_meta` L_k | **2.4 IMPLEMENTATION GAP** |
| production `oee` (r48) | linha/L1_L7 | `lth_meta` | linha/L1…L7 | implícita | rejeita | Caso B | **2.4 IMPLEMENTATION GAP** |
| production `producao` (r71) | linha/L1_L7 | `pick_up` diário | linha/L1…L7 | implícita | rejeita | Caso B | **2.4 IMPLEMENTATION GAP** |
| yield `n_ppt` (r107) | linha/L1_L7 | `tanque_base` anual, `tanque` diário | linha/L1…L7 | implícita | rejeita | Caso B | **2.4 IMPLEMENTATION GAP** |
| production `oee_total` (r50) | linha_grupo/L1_L7 | `lth_meta` | linha/L1…L7 | `@L1…@L7` | resolve | Caso A satisfeito | CONFORME |
| production `pick_up_total` (r61) | linha_grupo/L1_L7 | `pick_up` | linha/L1…L7 | `@L1…@L7` | resolve | Caso A satisfeito | CONFORME |
| production `pick_up` (r53–r59) | linha/L_k | `pick_up_yield` | linha/L1…L7 | implícita, consumidor de uma linha | resolve | contextual, uma definição por consumidor | CONFORME |
| A41 `retirada_condensado_grupo` (r22, r39, r42) | linha_grupo | `valor_retirada`, `hes` | linha/L1…L3, L4…L7 | `@Lx` | resolve | Caso A satisfeito | CONFORME |
| A41 `retirada_condensado_linha` mensal/anual (r52, r53); production `pick_up` mensal | linha/L1_L7 | mesmo nome diário | linha/L1…L7 | agregação temporal | — | origem = definição agrupada | **2.4 IMPLEMENTATION GAP** (mesmo agrupamento) |

Nenhum caso é `WORKBOOK_CONTRACT_ISSUE` nem `CONTRACT_GAP`. Nenhum `@grupo` usado como frequência.

## E. A41 v7 (`04c96dba…`)

Identidade, A019 (20/20), `@Lx`, `@grupo`, `allowed_values` (5 = literais comparados), `declared_result_states` (r39, r42, ambos
`→ "F"`), `"F"`, `ln()` (6), agregações (10 explícitas): **PASS**.

**BLOCKER — BLK-A41-1 (pendente desde o round 2, não corrigido):** r33 `retirada_meta_41b` e r34 `retirada_meta_41x`, coluna E
`value = '47.5'` (texto). `parameter_seed_validator.validate_field_types` → *"campo 'value' deve ser numérico"*;
`CalculationContext` → `CalculationValueError`. Correção: número `47.5`.

**Status: BLOCKED.**

## F. Energy v4 (`fbf29395…`)

| item | resultado |
|---|---|
| Identidade | PASS |
| value_type | PASS (56 `numerico`) |
| allowed_values / declared_result_states / NO_APPLICABLE_RULE | PASS (não aplicável; nenhum) |
| Escopo, @Lx (49), @grupo (0), frequência | PASS |
| Unidades | PASS — `tpd` eliminado (D3 `t/d`) |
| Dependências / expressões | PASS — 24/24 |
| Médias ponderadas (7) e médias (3) | PASS — origem e peso explícitos |
| **Média móvel r6** | **FAIL** |
| Cross-workbook | PASS — `pick_up` e `lth_meta` (1 definição `linha/L1_L7` no energy × 7 instâncias no production) = DIVERGÊNCIA LEGÍTIMA de representação do mesmo conceito |

**BLOCKER — BLK-EN-1:** r6 `producao_planta_t_h_media_movel` (diário, `linha_grupo/L1_L7`) agora cita
`'producao_t_h'`, que é a variável **por linha** (`linha/L1_L7`, r4). Uma média móvel temporal de uma origem `linha` para um
destino `linha_grupo` introduz agregação espacial implícita dentro da regra temporal. A origem de mesma escala é
`producao_planta_t_h` (r5, `linha_grupo/L1_L7`), que é também a origem da regra já implementada
(`AGR-ENERGY-PRODUCAO_PLANTA_T_H_MEDIA_MOVEL-GRUPO-L1_L7-DIARIO-MOVING_AVERAGE`, `source = producao_planta_t_h`).
Correção: `Média móvel dos dados de 'producao_planta_t_h' entre o 1º e o dia atual de cada mês.`

**Status: BLOCKED.**

## G. MaxHT v8 (`3ebeba7d…`)

Identidade (0 colisões; `L1_L3`/`L4_L5`/`L6_L7` distintos), A019 29/29, `@Lx`, `@grupo`, frequência, `value_type`: PASS.
As 20 linhas `*_somatorio` citam a origem diária real (ex.: r72 `lth_total_somatorio` ← `'lth_total'`); as 20 somas são
dimensionalmente coerentes (`required_sum_factor`: fator 1 para `/d`, 24 para `/h`). **Status: PASS.**

## H. Production v5 (`c168215a…`)

`oee_total`, `pick_up_total` sem fragmentos (parseiam e resolvem); origens `_somatorio` explícitas (r5, r10, r16, r22, r75);
`consumo_bauxita` com origem diária `linha_grupo/L1_L7` (r3); `PLANTA` (r26, aceito pelo `ScopeResolver`); `producao_planta`
diário `t/d`, soma mensal `t/mês` (r75), soma anual `t/ano` (r76), coerentes; nenhum `tpd`; identidade sem colisão; `value_type`
PASS. `lth`, `oee`, `producao` (implícitos sobre `lth_meta`/`pick_up`) = 2.4 IMPLEMENTATION GAP, não blocker. **Status: PASS.**

## I. Yield v8 (`a41348e3…`)

Sem `L6_7`, sem vírgula decimal, 80 médias com origem explícita; `ltp_a_c_grupo` agora existe como entidade (r59–r61 diário,
r63–r65 mensal) e nenhuma referência pendente a `ltp_a_grupo`; identidade, `@Lx`, frequência, `value_type` PASS; `n_ppt`
sobre `tanque_base`/`tanque` = 2.4 IMPLEMENTATION GAP.

**BLOCKER — BLK-YI-2 (pendente desde o round 2, não corrigido):** r227–r233 `tanque` (L1–L7), coluna D `unit` vazia;
`unit` é campo obrigatório (`NON_EMPTY_STRING_FIELDS` do `variable_seed_validator`). Correção: unidade de `tanque` (o seed
atual `VAR11239` usa `-`).

**Status: BLOCKED.**

## J. Cross-workbook

`evidence/round3/cross_workbook.csv`: 13 vínculos entre os cinco — 11 OK por identidade completa, 2 OK como instâncias por
linha no produtor (`pick_up`, `lth_meta`). `producao` agora `t/d` em production, energy e MaxHT. 21 entradas vêm de blocos fora
dos cinco (não verificáveis aqui). Nenhuma divergência de `value_type` ou estado.

## K. Testes

```text
TESTS_BEFORE: 1414 passed
targeted (DSL, A019, parser, @grupo, ln, value_type, agregação, contexto): 246 passed
TESTS_AFTER:  1414 passed, 0 failed, 0 errors (sem mudança de código)
```

## Resultado por workbook

| workbook | status | blockers |
|---|---|---|
| A41 v7 | BLOCKED | BLK-A41-1 (r33, r34 `value` texto) |
| energy v4 | BLOCKED | BLK-EN-1 (r6 origem `producao_t_h` de escopo `linha`) |
| MaxHT v8 | PASS | — |
| production v5 | PASS | — |
| yield v8 | BLOCKED | BLK-YI-2 (r227–r233 sem unidade) |

## Matriz final

| tema | status |
|---|---|
| D1-D4 | PASS |
| `numerico/categorico` | PASS |
| ausência de aliases | PASS |
| `declared_result_states` | PASS |
| herança de estados | PASS |
| `NO_APPLICABLE_RULE` | PASS |
| `"F"` canônico | PASS |
| A019 | 2.4 (4 consumidores + 3 agregações sobre instâncias por linha; demais PASS) |
| `@Lx` | PASS |
| `@grupo` | PASS |
| frequência | PASS |
| agregação temporal | FAIL (BLK-EN-1) |
| agregação espacial | FAIL (BLK-EN-1: espacial implícita dentro da média móvel) |
| `ln()` | PASS |
| A41 | FAIL (BLK-A41-1) |
| energy | FAIL (BLK-EN-1) |
| MaxHT | PASS |
| production | PASS |
| yield | FAIL (BLK-YI-2) |
| cross-workbook | PASS |
| testes | PASS |

## L. Gate

```text
STAGE_2.3_GATE: BLOCKED
```

Blockers reais restantes (todos células de workbook, sem decisão pendente, sem mudança de código):

1. **BLK-EN-1** — energy v4, P6: origem `'producao_t_h'` → `'producao_planta_t_h'`.
2. **BLK-A41-1** — A41 v7, E33 e E34: `'47.5'` (texto) → `47.5` (número).
3. **BLK-YI-2** — yield v8, D227–D233: unidade vazia → unidade de `tanque`.

Para a Etapa 2.4: agrupamento das linhas-instância por linha numa única definição antes do A019 (production `lth`, `oee`,
`producao`; yield `n_ppt`; agregações sobre `retirada_condensado_linha` e `pick_up` mensal).
