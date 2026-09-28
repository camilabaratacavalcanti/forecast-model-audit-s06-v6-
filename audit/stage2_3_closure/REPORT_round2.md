# Etapa 2.3 — Rodada final (round 2)

```text
Branch:        feature/area-41-block
HEAD:          07af71b8d5d02d8d714eb332e0f3c16b3cb29d49  (= origin/feature/area-41-block)
origin/main:   4510865f83fd3cf628782ad6a2e3de502aac4e7e
Resultado:     STAGE_2.3_GATE: BLOCKED (8 blockers de workbook; código e contrato conformes)
```

Nenhum workbook alterado. Nada da Stage 3 implementado. Critério de blocker usado em toda esta rodada:
**o workbook, como entregue, viola uma regra que a plataforma atual já aplica (validator, `ScopeResolver`,
`CalculationContext`, `required_sum_factor`) ou a regra explícita de Política B (origem da agregação identificável).**

## A. Pre-flight

| item | valor |
|---|---|
| BASELINE_SHA | `07af71b` sobre `4510865` — desvio registrado: `07af71b` é a migração `numerico/categorico` já commitada e publicada na rodada anterior; nenhum outro commit local, nada não commitado |
| WORKTREE | limpo, sincronizado com `origin/feature/area-41-block` |
| TESTS_BEFORE | 1414 passed, 0 failed |
| código do contrato `value_type` | `app/domain/values.py`, `app/domain/variables/models.py`, `app/validation/variable_seed_validator.py`, `app/engine/calculation_context.py`, `app/engine/forecast_engine.py` |
| testes do contrato | `tests/test_dsl_structural_contracts.py` (value_type, categóricas, `"F"`, `@grupo`, `ln`) |

### Workbooks usados (anexados nesta mensagem)

| bloco | arquivo anexado | SHA-256 | observação |
|---|---|---|---|
| area_41 | `A41_v7.xlsx` | `a6c89353…35dcd685` | mesmo nome da v7 anterior (`0fe3f1ff…`), conteúdo diferente (3 células) |
| energy | `energy_v3.xlsx` | `9b73daaf…7a4e5` | idêntico à v3 anterior |
| max_ht | `MaxHT_v7.xlsx` | `9f7f6b56…3c4c` | o texto do prompt cita v6; o anexo é v7 |
| production | `production_v4.xlsx` | `9464f447…94d1` | o texto do prompt cita v3; o anexo é v4 |
| yield | `yield_v7.xlsx` | `c1655821…ac261` | o texto do prompt cita v6; o anexo é v7 |

Os anexos foram tratados como a especificação vigente; as versões citadas no texto (MaxHT v6, production v3,
yield v6) são as já reprovadas na rodada anterior. Estrutura física: uma aba cada, sem abas ocultas, fórmulas
Excel, named ranges; as mesmas 18 colunas de contrato.

## B. Alteração do contrato `value_type`

| item | resultado |
|---|---|
| ocorrências encontradas antes (rodada 1) | 2 constantes (CONTRATO), 6 literais de teste (TESTE), 7 comentários/docstrings (DOCUMENTAÇÃO), ~70 identificadores Python sem relação (IMPLEMENTAÇÃO — não alterados) |
| ocorrências alteradas | as 15 primeiras, commit `07af71b` |
| busca final (`git grep` por `"numeric"`, `"categorical"`, alias, legacy) em `app`, `tools`, `tests`, `data` | **0** literais residuais de contrato; restam apenas os nomes de constantes `NUMERIC`/`CATEGORICAL` (valores `"numerico"`/`"categorico"`) e o laço de teste que verifica a rejeição dos rótulos antigos |
| aliases / normalização / fallback | **nenhum**. `VALUE_TYPES = {"numerico", "categorico"}`; `VariableDefinition` e `validate_enum_values` rejeitam `numeric`/`categorical` (asserções em `test_dsl_structural_contracts.py`) |
| workbooks | 572/572 células `value_type` ∈ `{numerico, categorico}` |

## C. Estados

- `declared_result_states` = estados que a própria variável produz pela própria regra (refinamento R1 de D1/D2,
  `DECISION_REFINEMENT_R1_declared_result_states.md`).
- Estado efetivo/herdado = runtime (Stage 3); não é redeclarado nos descendentes.
- `NO_APPLICABLE_RULE` = estado de negócio; nunca exceção, `None`, `NaN`.
- Fato do workbook: em A41 v7, `hes` **não** declara estado (é entrada categórica; células O25–O28 vazias).
  O produtor declarado é `retirada_condensado_grupo` (r39, r42). O exemplo do prompt (§4.1, "hes declara
  `NO_APPLICABLE_RULE`") não corresponde ao arquivo; a regra R1 vale igual e o arquivo está correto por ela.

## D. A41 v7 (`a6c89353…`)

| item | resultado |
|---|---|
| identidade | PASS — 0 colisões |
| A019 | PASS — 20/20 expressões resolvidas e parseadas |
| `@Lx` / `@grupo` | PASS — `hes@L4..@L7` resolvem para as 4 linhas `hes`; `@L1_L3/@L4_L5/@L6_L7` referenciam entidades de grupo calculadas; nenhum uso temporal |
| `allowed_values` | PASS — `hes` (5 valores) = exatamente os literais comparados em r39/r42 |
| `declared_result_states` / `"F"` | PASS — único literal de resultado é `"F"`, declarado em r39 e r42; nenhum herdeiro precisa declarar (R1) |
| `ln()` | PASS — 6 usos (r6–r8, r16–r18), allowlist e aridade conformes |
| agregação | PASS — 10 médias com origem explícita |
| **parâmetros** | **FAIL — r33 `retirada_meta_41b` e r34 `retirada_meta_41x`: `value` virou texto `'47.5'` (era número na v7 anterior). `validate_field_types` → "campo 'value' deve ser numérico"; `CalculationContext` → `CalculationValueError`** |
| serialização | NON-BLOCKING — r39 `NO_APPLICABLE_RULE → "F"`, r42 `NO_APPLICABLE_RULE → F` (formato não fixado pelo contrato, mas inconsistente no mesmo arquivo) |

**Status: FAIL** (1 blocker, BLK-A41-1).

## E. Energy v3 (`9b73daaf…`, inalterado)

| item | resultado |
|---|---|
| Identidade | PASS — 0 colisões; escopos distintos tratados como identidades distintas |
| value_type | PASS — 56 `numerico` |
| allowed_values | PASS — nenhuma categórica |
| declared_result_states | PASS — nenhum (no-op) |
| NO_APPLICABLE_RULE | PASS — não produz nem herda |
| Escopo | PASS |
| @Lx | PASS — 49 referências |
| @grupo | PASS — nenhuma |
| Frequência | PASS — diário, mensal, anual |
| **Agregação** | **FAIL — r6 `producao_planta_t_h_media_movel`: "Média móvel dos dados entre o 1º e o dia atual de cada mês." não nomeia a origem; só é resolvível por convenção de nome (`…_media_movel` → `producao_planta_t_h`). Viola §16 (origem explicitamente identificável). As outras 10 agregações (7 médias ponderadas com peso `producao_planta_t_h`, 3 médias) têm origem explícita** |
| Dependências | PASS — 24/24 resolvidas |
| Expressões | PASS |
| Cross-workbook | PASS — `producao`, `pick_up_total`, `lth`, `lth_total` resolvem por identidade completa; `pick_up` e `lth_meta` = DIVERGÊNCIA LEGÍTIMA (energy declara 1 definição `linha/L1_L7`; production declara as 7 instâncias por linha da mesma definição lógica); `producao` `tpd` (energy) × `t/d` (production) = DIVERGÊNCIA LEGÍTIMA (sinônimos aceitos; `units._ALIASES`) |

**Status: FAIL** (1 blocker, BLK-EN-1).

## F. MaxHT v7 (`9f7f6b56…`)

| item | resultado |
|---|---|
| identidade | PASS — 0 colisões. Os antigos 20 pares Soma/Média foram resolvidos renomeando a variante soma para `X_somatorio`. `L1_L3`/`L4_L5`/`L6_L7` com mesmo nome e frequência = identidades distintas (não colisão) |
| A019 | PASS — 29/29; `esp_max_ht_planta` agora resolve |
| @Lx / @grupo / escopo / frequência / value_type | PASS |
| unidades de SUM | PASS — 20 somas dimensionalmente coerentes (fator 1 para `/d`, 24 para `/h`) medidas contra a origem diária pretendida |
| **origem das somas** | **FAIL — as 20 linhas `*_somatorio` (r72, r73, r83–r88, r92, r93, r96, r97, r108–r113, r117, r118) descrevem "Somatório … de '`X_somatorio`'", mas não existe `X_somatorio` diário; a origem real é o `X` diário (ex.: r72 deveria citar `'lth_total'`). Origem não identificável (§16)** |

**Status: FAIL** (1 blocker, BLK-MX-1).

## G. Production v4 (`9464f447…`)

| item | resultado |
|---|---|
| identidade | PASS — 0 colisões (pares renomeados para `_somatorio`) |
| `oee_total`, `pick_up_total` | PASS — fragmentos soltos removidos; ambos parseiam |
| `consumo_bauxita` | PASS — agora existe origem diária `linha_grupo/L1_L7` (r3 = `consumo_mrn_grupo + consumo_mpsa_grupo + consumo_cbg_grupo`); sem agregação espacial implícita |
| vírgula decimal | PASS — nenhuma |
| value_type | PASS |
| A019 | 24/27 resolvidas; as 3 restantes (r35 `lth`, r48 `oee` → `lth_meta`; r71 `producao` → `pick_up`) são definição lógica com instâncias por linha consumida por `linha/L1_L7` — NON-BLOCKING, gap do builder (2.4) |
| **origem das somas** | **FAIL — r5, r10, r16, r22, r75 citam `'X_somatorio'` como origem diária inexistente (mesmo defeito do MaxHT)** |
| **unidade das somas** | **FAIL — `producao_planta` SUM: r75 (mensal) e r76 (anual) em `t/d`; `required_sum_factor` = incoerente. As somas de `consumo_*` foram corrigidas (`t/mês`/`t/ano`)** |
| **escopo** | **FAIL — r26 `desaguamento_produtividade`: `scope_value = planta`; `ScopeResolver` rejeita ("Invalid plant scope_value: planta"); canônico `PLANTA`** |

**Status: FAIL** (3 blockers, BLK-PR-1/2/3).

## H. Yield v7 (`c1655821…`)

| item | resultado |
|---|---|
| `L6_7` | PASS — 0 ocorrências; todos os grupos usam `L6_L7` |
| vírgula decimal | PASS — nenhuma |
| agregações implícitas | PASS — as 80 médias agora nomeiam a origem |
| identidade / @Lx / escopo / frequência / value_type | PASS |
| A019 | 137/138; r107 `n_ppt` → `tanque_base`/`tanque` por linha = NON-BLOCKING (mesmo gap do builder) |
| **origem** | **FAIL — r63, r64, r65 `ltp_a_grupo` mensal citam `'ltp_a_c_grupo'`, que não existe; a origem diária é `ltp_a_grupo` (r59–r61)** |
| **unidade** | **FAIL — r227–r233 `tanque` (L1–L7) sem `unit`; campo obrigatório (`NON_EMPTY_STRING_FIELDS`)** |

**Status: FAIL** (2 blockers, BLK-YI-1/2).

## I. Cross-workbook

`evidence/round2/cross_workbook.csv`. 13 vínculos entre os 5 workbooks: 11 OK, 2 OK como instâncias por linha
(`pick_up`, `lth_meta`); 1 divergência de grafia de unidade (`tpd`/`t/d`, legítima). 17 entradas vêm de blocos fora dos
cinco (maintenance, maintenance_plan, forecast, temperature_lp, alumina, area_04_13) e não são verificáveis aqui.
Nenhuma divergência de `value_type` ou de estado entre blocos.

## J. Testes

```text
TESTS_BEFORE: 1414 passed
TESTS_AFTER:  1414 passed, 0 failed, 0 errors   (nenhuma mudança de código nesta rodada)
```

## K. Busca final

Nenhum literal `numeric`/`categorical` de contrato em `app`, `tools`, `tests`, `data`. Nenhuma camada de alias,
normalização, vocabulário legado ou fallback.

## Matriz de blockers

| workbook | blocker | evidência | correção (não aplicada) | status |
|---|---|---|---|---|
| A41 | BLK-A41-1 parâmetro com valor texto | r33, r34 coluna E = `'47.5'` (str) | valor numérico `47.5` | FAIL |
| energy | BLK-EN-1 média móvel sem origem | r6 coluna P | `Média móvel dos dados de 'producao_planta_t_h' entre o 1º e o dia atual de cada mês.` (padrão já usado pelo production) | FAIL |
| MaxHT | BLK-MX-1 origem das 20 somas aponta para a própria variável | r72, r73, r83–r88, r92, r93, r96, r97, r108–r113, r117, r118 coluna P | citar a origem diária sem `_somatorio` (ex.: `'lth_total'`, `'massa_total_max_ht'`, `'producao'`, `'producao_grupo'`, `'refinery'`, `'massa_total_max_ht_total'`) | FAIL |
| production | BLK-PR-1 origem das 5 somas aponta para a própria variável | r5, r10, r16, r22, r75 coluna P | `'consumo_bauxita'`, `'consumo_cbg_grupo'`, `'consumo_mpsa_grupo'`, `'consumo_mrn_grupo'`, `'producao_planta'` | FAIL |
| production | BLK-PR-2 soma com unidade de taxa | r75 (mensal), r76 (anual) coluna D = `t/d` | `t/mês`, `t/ano` | FAIL |
| production | BLK-PR-3 escopo não canônico | r26 coluna J = `planta` | `PLANTA` | FAIL |
| yield | BLK-YI-1 origem inexistente | r63–r65 coluna P `'ltp_a_c_grupo'` | `'ltp_a_grupo'` | FAIL |
| yield | BLK-YI-2 unidade ausente | r227–r233 coluna D vazia | unidade de `tanque` (o seed atual usa `-`) | FAIL |

Não bloqueantes: serialização `→ "F"` × `→ F` (A41 r39/r42); instâncias por linha consumidas sem `@` (production
r35/r48/r71, yield r107 → gap do builder, 2.4); `tpd`/`t/d`; nome `producao_planta` da soma anual sem sufixo
`_somatorio` (r76), inconsistente com a convenção nova; parâmetros/entradas nunca consumidos (A41 7, energy 6).

## Matriz global

| tema | status |
|---|---|
| D1-D4 | PASS |
| `numerico/categorico` | PASS |
| ausência de aliases | PASS |
| `declared_result_states` | PASS |
| herança conceitual de estados | PASS (R1) |
| `NO_APPLICABLE_RULE` | PASS |
| A019 | PASS (4 casos restantes = gap do builder, não do workbook) |
| `@Lx` | PASS |
| `@grupo` | PASS |
| frequência | PASS |
| agregação temporal | **FAIL** (BLK-EN-1, BLK-MX-1, BLK-PR-1, BLK-PR-2, BLK-YI-1) |
| `ln()` | PASS |
| A41 | **FAIL** (BLK-A41-1) |
| energy | **FAIL** (BLK-EN-1) |
| MaxHT | **FAIL** (BLK-MX-1) |
| production | **FAIL** (BLK-PR-1/2/3) |
| yield | **FAIL** (BLK-YI-1/2) |
| testes | PASS |

## L. Gate final

```text
STAGE_2.3_GATE: BLOCKED
```

Blockers reais: BLK-A41-1, BLK-EN-1, BLK-MX-1, BLK-PR-1, BLK-PR-2, BLK-PR-3, BLK-YI-1, BLK-YI-2 — todos correções de
células de workbook, sem decisão de negócio pendente e sem mudança de código. Código, vocabulário, contrato de estados,
A019, `@Lx`, `@grupo` e testes estão conformes.
