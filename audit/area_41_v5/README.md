# A41 v5 — Etapa 2: saneamento controlado do workbook `area_41`

**Conclusão: `BLOCKED`.** Há um único bloqueio: a origem de 41c/41d (B1). Todos
os demais critérios têm evidência objetiva e reproduzível.

## Como reproduzir

```bash
python3 -m pytest audit/area_41_v5/check_a41_v5.py -v      # 43 PASS + 1 FAIL esperado (B1)
python3 audit/area_41_v5/check_a41_v5.py                    # regenera evidence/*
A41_WORKBOOK=<input.xlsx> python3 -m pytest audit/area_41_v5/check_a41_v5.py   # defeitos do input
python3 -m pytest -q                                        # suíte da plataforma
```

O harness `check_a41_v5.py` lê o workbook e usa **apenas** componentes
genéricos da plataforma:

- `reference_resolver`, `ExpressionParser`, `DependencyExtractor`;
- `ForecastEngine`, `ScopeResolver`, `TemporalAggregationService`;
- `find_sum_dimension_issues`;
- a DSL de agregação já usada por `tools/max_ht_seed_builder.py`.

Os IDs `VAR99xxx`/`PARAM99xxx`/`EQ99xxx` são efêmeros: existem só em memória
durante a verificação. Os valores esperados vêm de fórmulas de referência
independentes, escritas a partir das decisões vinculantes (§5, §7, §10, §12).

## 1. Pre-flight

| item | valor |
|---|---|
| branch | `claude/funny-noether-nbcr7b` |
| commit | `4510865` (Etapa 1). Base comum com `origin/main`: `202d4cb` (1 commit à frente, 0 atrás). Sincronizado com `origin` |
| working tree | limpo antes da etapa |
| input_workbook | `descritivo_das_variáveis_A41_v5.xlsx` (anexado nesta etapa; upload `4fe1bdbb-…`), 35 065 bytes, modificado em 2026-09-24 19:07 (propriedades do arquivo), 1 aba (`A41`, 308×15) |
| input_sha256 | `ea3d2e51863376c34c91c1e3fc55f1ad320b2d715f668634ed586625f9152188` |

Identificação inequívoca do input: comparado célula a célula com o v4
(`383c462b…`), o input contém **exatamente** v4 + 54 descrições (antes
vazias) + os 7 denominadores do §7. Ou seja, é a base aprovada com as
descrições aprovadas, e nada além disso.

Cadeia de proveniência (versões históricas não alteradas):

| versão | sha256 | entidades |
|---|---|---|
| A41 v3 | `59f82304…fd85` | 60 (com identidades duplicadas) |
| A41 v4 | `383c462b…2a4c` | 54 |
| input (v4 + descrições + §7) | `ea3d2e51…8152188` | 54 |
| **A41 v5 (saída)** | `c8be0a3c70bb04682163ebc489b83a1bc6af58c8105a7bb58c63381c2f915125` | 54 |

## 2. Output

| item | valor |
|---|---|
| output_workbook | `audit/area_41_v5/descritivo_das_variáveis_A41_v5.xlsx` |
| output_sha256 | `c8be0a3c70bb04682163ebc489b83a1bc6af58c8105a7bb58c63381c2f915125` |

## 3. Alterações input → v5 (51 células; auditoria célula a célula)

| item | alteração | classe | justificativa | evidência |
|---|---|---|---|---|
| **D1** — coluna P `value_type` (P1 `Variables`, P2 `value_type`) | `categorical` para `hes_l4..l7`; `numeric` para as outras 43 variáveis; vazio para os 7 parâmetros (como as demais colunas exclusivas de variável) | STRUCTURAL | O contrato da Etapa 1 (`VariableDefinition.value_type`) exige que um estado textual seja declarado. Sem a coluna, a única saída seria uma regra por nome, proibida (§27). O §11 e o OBS das linhas 25–28 já definem esses valores como textuais. A coluna foi **acrescentada ao final** para manter todas as coordenadas de célula do v4. | No input, 27 testes do harness falham com `CalculationValueError` (texto em variável não categórica). No v5, `test_states_are_categorical` e `test_value_type_is_declared_for_every_variable` passam |
| **D2** — M39 e M42 | `hes_l4` → `hes_l4@L4` (e L5/L6/L7), 16 ocorrências | STRUCTURAL | Um consumidor `linha_grupo` só alcança uma referência implícita de dentro para fora (grupo → planta); nunca lê uma linha para dentro (Decision E). Cada `hes_lN` só existe em `linha/LN`, então a forma explícita é a única correta. É o mesmo padrão que o workbook já usa em `valor_retirada@L1`. Nada mais muda: a ordem dos ramos, `and`/`or`, os textos e o `"F"` ficam idênticos. | Na scope matrix do input há 4 linhas FAIL (`implícita-para-dentro`). Com só D1 aplicado, o runtime falha com `VariableNotFoundError` na variável de `hes_l4`. Com D1+D2, o total reconcilia com a referência. No v5, as 59 linhas da matriz dão PASS |

O que **não** foi alterado:

- nomes, unidades, `source_reference`, frequências, escopos, status e parâmetros;
- as demais expressões;
- 41c/41d (ver B1);
- a nota OBS da linha 39 (que continua registrando a dúvida de 41c/41d).

### Matriz de mudanças v3 → v4 → v5

| entidade | v3 | v4 | v5 | mudança | classe | evidência | status |
|---|---|---|---|---|---|---|---|
| `lth` | 3 linhas (`linha/L1_L3`, `L4_L5`, `L6_L7`) | 1 linha `linha/L1_L7` | = v4 | unificação de escopo | STRUCTURAL | A019/ScopeResolver | OK |
| `lth_grupo` ×3 | soma, sem source | média `/3`, `/2` (A020) + source | = v4 | soma → média | SEMANTIC | E4 | RESOLVED |
| `retirada_cond_corr_lth` ×3 | `ln(lth * fator)` | `ln(lth_grupo * fator)` | = v4 | referência correta | SEMANTIC | E7 | OK |
| agregações de grupo/linha/total (10) | pares Somatório + Média com a mesma identidade | só Média + source | = v4 | duplicatas removidas | REMOVAL | E5 | OK |
| `retirada_condensado_linha` diário | 1 linha `L1_L7` com `lth_grupo` | 7 linhas L1..L7, `/lth_grupo@grupo` | 7 linhas, denominador `Σ lth` do grupo (§7; já no input) | denominador | SEMANTIC | E10 | RESOLVED |
| parâmetros ×7 | `scope_value=planta` | `PLANTA` | = v4 | valor canônico | STRUCTURAL | enums | OK |
| OBS L4_L5 / L6_L7 | vazio | nota 41c/41d | = v4 | documentação | DOCUMENTATION | — | OK |
| 54 descrições | vazias | vazias | preenchidas (input) | descrições aprovadas | DOCUMENTATION | E3 | OK |
| `hes_l4..l7` + demais variáveis | — | — | `value_type` | D1 | STRUCTURAL | E8 | OK |
| `retirada_condensado_grupo` L4_L5 / L6_L7 | `hes_lN` | `hes_lN` | `hes_lN@LN` | D2 | STRUCTURAL | E6 | OK |
| `desconto_retirada_41c/41d` ×3 | C26 / C27 / C26 | = v3 | = v4 | nenhuma | NO_CHANGE | B1 | **BLOCKING** |
| demais 30 entidades | — | — | — | nenhuma | NO_CHANGE | — | OK |

## 4. Decisões

| decision | status | evidence |
|---|---|---|
| A019 | RESOLVED | Resolvedor central por nome + frequência + escopo, usado pelos builders (`tools/*_seed_builder.py`). No A41, 59/59 referências são vinculadas por escopo (`evidence/scope_matrix.csv`) |
| A020 | RESOLVED | `lth_grupo` = média. Com L1..L7 = 10/20/30/40/60/70/30, o resultado é L1_L3 = 20 (não 60), L4_L5 = 50, L6_L7 = 50 |
| A021 | RESOLVED | `retirada_condensado_linha` mensal e anual materializam 7 instâncias cada (L1..L7), todas AVERAGE, a partir de **uma** linha no workbook |
| A022 (@grupo) | RESOLVED | `@L1_L3`, `@L4_L5`, `@L6_L7` são resolvidas como `linha_grupo` exato; o grafo ordena os produtores de grupo antes dos consumidores (teste com o registry em ordem inversa) |
| ln() | RESOLVED | As 6 equações com `ln` batem com `19.475·ln(x) − 85.999` |
| text/categorical | RESOLVED (D1) | `hes_l4..l7` são `categorical` e recebem os 5 estados |
| `"F"` | RESOLVED | 6 combinações não cobertas resultam em `"F"`, gravado sem conversão; o consumidor falha com `ConditionalFailureError` |
| 41c/41d | **BLOCKING** | Ver B1 |
| max_ht | DEFERRED | Ver §5; nenhuma conversão foi aplicada |

### B1 — 41c/41d (BLOCKING, §14/§37.2)

Na aba `Forecast A41`, cada linha corresponde a uma condição, conforme os próprios
parâmetros do workbook (`retirada_meta_41X` na coluna B):

- linha 23 = 41a, 24 = 41b, 25 = 41x;
- linha 26 = **41c** (também `retirada_performance_41c`, F26);
- linha 27 = **41d**.

| entidade | source | condição da linha de origem | consistente |
|---|---|---|---|
| `desconto_retirada_41c@L4_L5` | C26 | 41c | sim, mas a célula é compartilhada |
| `desconto_retirada_41c@L6_L7` | C27 | **41d** | **não** |
| `desconto_retirada_41d@L4_L5` | C26 | **41c** | **não** (mesma célula de `41c@L4_L5`) |

Pontos adicionais:

- Não existe `desconto_retirada_41d@L6_L7`.
- A equação L4_L5 usa 41d no ramo "1 By pass" e 41c em "1 By pass e LC"; a L6_L7 usa 41c nos dois ramos.
- A fonte `Forecast A41` **não está disponível** nesta sessão (há apenas os descritivos v3/v4/v5).

Há leituras plausíveis (por exemplo, troca de rótulo), mas escolher uma seria
inventar semântica. Nada foi alterado. **Para desbloquear**, é preciso a aba
`Forecast A41` (células C26, C27 e os rótulos das linhas 26/27) ou uma
decisão do dono do modelo sobre qual desconto se aplica a cada grupo e a cada
condição.

## 5. `max_ht` — MAX_HT_SANITIZATION

**Regra aplicada ao workbook A41:** nenhuma entidade se enquadra.

- As 10 agregações do A41 são AVERAGE de `m³/h` para `m³/h`.
- O validador dimensional não encontra nenhuma SUM taxa/h → período (`test_no_implicit_temporal_conversion_in_a41`).
- Nenhum fator ×24/×720/×8760 foi introduzido.

**Bloco `max_ht` (fora do workbook A41):** o validador identifica 34
variáveis que se enquadram literalmente no §16:

- todas são `calculado`;
- são SUM de `/h`;
- nenhuma é consumida por equação ou agregação;
- `source` = `descritivo_das_variáveis_MaxHT_v5.xlsx`.

| variable (ID, freq, escopo) | action | reason |
|---|---|---|
| `alimentação_evap` VAR13012 mensal / VAR13013 anual (linha L1_L7) | IDENTIFIED, não removida | m³/h → m³/mês \| m³/ano sem duração operacional |
| `alimentação_evap_total` VAR13017 / VAR13018 (grupo L1_L7) | idem | m³/h → m³/mês \| m³/ano |
| `lth` VAR13022 / VAR13023 (linha L1_L7) | idem | m³/h → m³/mês \| m³/ano |
| `lth_total` VAR13027 / VAR13028 | idem | m³/h → m³/mês \| m³/ano |
| `fluxo_para_evap` VAR13033 / VAR13034 | idem | kg/h → kg/mês \| kg/ano |
| `fluxo_para_evap_total` VAR13038 / VAR13039 | idem | kg/h → kg/mês \| kg/ano |
| `fluxo_para_a18_linha` VAR13044 / VAR13045 | idem | kg/h → kg/mês \| kg/ano |
| `fluxo_para_a18_linha_total` VAR13049 / VAR13050 | idem | kg/h → kg/mês \| kg/ano |
| `a18_l123` VAR13054 / VAR13055; `a13_l123` VAR13059 / VAR13060; `a18_a13_l123` VAR13064 / VAR13065 (L1_L3) | idem | kg/h → kg/mês \| kg/ano |
| `a18_l45` VAR13083 / VAR13084; `a13_l45` VAR13088 / VAR13089; `a18_a13_l45` VAR13093 / VAR13094 (L4_L5) | idem | kg/h → kg/mês \| kg/ano |
| `a18_l67` VAR13112 / VAR13113; `a13_l67` VAR13117 / VAR13118; `a18_a13_l67` VAR13122 / VAR13123 (L6_L7) | idem | kg/h → kg/mês \| kg/ano |

As 34 não foram removidas nesta etapa. A remoção exige alterar
`data/seed/max_ht`, a saída do builder e testes fixados, e esta etapa
restringe o entregável ao workbook A41 (§35 manda parar diante de alterações
em seeds/builders). A lista fica pronta para a decisão do dono (ver
pendência P1).

## 6. Contratos da plataforma (verificados no código e em testes, sem assumir)

| contrato | resultado | evidência |
|---|---|---|
| A019 | PASS | `tests/test_reference_resolver.py` (23) + scope matrix do A41 (59/59) |
| A021 | PASS | `tests/test_aggregation_rule_instances.py` (12) + E5 |
| @grupo | PASS | Fase C de `tests/test_dsl_structural_contracts.py` + E6 + ordem do grafo |
| ln | PASS | `ln(1)=0`, `ln(e)≈1`; `ln(0)` e `ln(<0)` → `MathDomainError`; aridade e allowlist fechada (Fase D) + E7 |
| text | PASS | `CalculationContext` aceita texto só em variáveis categóricas (Fase E) + E8 |
| boolean | PASS | `and`/`or` com curto-circuito e precedência; resultado final booleano é erro (Fase F); ramos do A41 conferidos contra a referência (16 casos) |
| F | PASS | `"F"` nunca é convertido; consumi-lo é erro (Fase G) + E9 |

`PLATFORM_CONTRACT_FAILURE`: **nenhum**. D2 não é defeito da plataforma: é a
regra documentada (referência implícita nunca desce do grupo para a linha).

## 7. Testes

| item | valor |
|---|---|
| baseline | 1414 passed, 0 failed, 0 skipped |
| final (suíte completa) | 1414 passed, 0 failed, 0 skipped |
| contratos da Etapa 1 | 186 passed |
| harness A41 v5 | 44 checks: 43 passed, 1 failed (= B1, esperado e não mascarado) |
| harness no input | 13 passed, 31 failed (D1: 27, D2: scope matrix/grafo, B1) |

## 8. Reconciliações (cenário determinístico de `check_a41_v5.py`)

| verificação | resultado |
|---|---|
| lth_grupo | L1_L3 = 20.0, L4_L5 = 50.0, L6_L7 = 50.0 (média; não soma) |
| rateio | Σ `retirada_condensado_linha` do grupo = `retirada_condensado_grupo`, para L1_L3, L4_L5 e L6_L7; cada linha = referência §7 |
| grupo | L1_L3 conforme a fórmula; L4_L5 e L6_L7 em 8 combinações de estados (inclui a precedência LC > Overhaul > By pass) = referência §12 |
| total | diário = soma dos 3 grupos. Em 33 dias (01/01 a 02/02/2026), mensal/anual = média dos totais diários, o que é igual à soma das médias dos grupos (mesmos dias) |
| aggregation materialization | 22 instâncias: linha mensal 7 + anual 7; grupos 3 + 3; total 1 + 1. Todas AVERAGE, e todos os valores = média diária de referência |

Os valores negativos no cenário vêm das entradas sintéticas do §21 (LTH
10..70 dentro de `ln`). A reconciliação é algébrica e não depende da faixa.

## 9. Gates

| gate | resultado |
|---|---|
| Workbook integrity | PASS (estrutura, enums, identidades únicas, descrições 54/54, sem fórmulas Excel, sem linhas órfãs) |
| Semantic closure | **FAIL** (B1: 41c/41d) |
| Platform contract validation | PASS |
| Aggregation materialization | PASS |
| Regression | PASS (1414/1414, 0 skipped) |
| Diff review | PASS (só `audit/area_41_v5/`; plataforma, seeds, builders e testes intocados) |
| Third-audit readiness | **FAIL** (depende de B1) |

## 10. Conclusão

**`BLOCKED`**

1. **B1 — 41c/41d:** `source_reference` contradiz o nome da condição em 2 de 3
   entidades, e a célula C26 é compartilhada por duas variáveis distintas.
   A fonte `Forecast A41` não está disponível.

Pendência de escopo (não bloqueia o A41):

- **P1:** confirmar se as 34 variáveis `max_ht` do §5 devem ser removidas do
  bloco `max_ht` agora (seeds + MaxHT workbook) ou na correção pós-A41.

## Evidências (E1–E12)

| id | onde |
|---|---|
| E1 identidade | §1/§2 (sha256 de input e output) |
| E2 integridade | 54 → 54 entidades (17 entradas, 20 equações, 10 agregações, 7 parâmetros) |
| E3 descrições | `test_every_entity_has_a_description`, `test_descriptions_match_frequency` |
| E4 A020 | `test_lth_grupo_is_average` |
| E5 A021 | `test_aggregation_materialization`, `test_aggregations_average_daily_results`, `evidence/a41_v5_evidence.json` |
| E6 @grupo | `test_line_to_group_bindings`, `evidence/scope_matrix.csv` |
| E7 ln | `test_ln_terms_match_reference` |
| E8 tipos | `test_states_are_categorical`, `test_value_type_is_declared_for_every_variable` |
| E9 "F" | `test_uncovered_combination_yields_F_and_fails_consumers` (6 casos) |
| E10 rateio | `test_group_total_and_rateio_reconcile` |
| E11 max_ht | §5 |
| E12 regressão | §7 |

Matriz de rastreabilidade: `evidence/traceability_matrix.csv` (54
entidades). Colunas: `source_reference`, sheet, cell, papel, frequência,
escopo, `value_type`, dependências, agregação e status de validação.
