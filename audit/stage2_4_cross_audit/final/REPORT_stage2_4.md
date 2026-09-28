# Etapa 2.4 — Cross-Audit Código × Workbooks — Relatório Final

Execução em modo **AUDITORIA**. Nenhum arquivo de código, builder, runtime, parser, workbook, seed ou contrato
foi alterado. Nenhum teste foi criado: os testes necessários estão **registrados** (T24-xx) em
`test_coverage_matrix.csv`. Os únicos arquivos novos estão em `audit/stage2_4_cross_audit/final/`.

Evidências (todas reexecutáveis, somente leitura):

| arquivo | conteúdo |
|---|---|
| `evidence/consumption_probe.py` / `consumption_probe_out.txt` | builders energy e max_ht executados em memória sobre energy v5 e MaxHT v9 |
| `evidence/runtime_probe.py` / `runtime_out.json` | P1 caminho builder A019; P2 runtime por instância (seed real); P3 value_type/allowed_values/declared_result_states pelo SeedLoader; P4 "F" e aborto; P5 identidade nos seeds |
| `evidence/a019_20_code.csv` | os 20 casos A019 × resultado do resolver da plataforma |
| `evidence/seed_vs_workbook.csv` | 572 linhas dos workbooks × seeds versionados |
| `evidence/pytest_baseline.txt`, `evidence/workbook_sha256.txt` | baseline |
| `defect_register.csv`, `test_coverage_matrix.csv` | registro de defeitos e matriz de testes |

---

## 29.1 Executive Summary

O contrato aprovado na Etapa 2.3 (5 workbooks, 572 linhas) **não é honrado pelo código atual**. O **runtime**
(ScopeResolver, CalculationContext, ForecastEngine, avaliador) suporta os mecanismos que o contrato exige.
O probe P2 provou isso: com o seed real, `oee@Lk = lth@Lk / lth_meta@Lk` usa `PARAM12001@Lk` com 1 ID e
7 instâncias (L1 = 1050, L3 = 1100), e a associação cruzada é detectável. O caminho **workbook → seed**, porém,
está quebrado ou ausente:

1. **3 de 5 workbooks não têm leitor.** Não existe leitor/builder para yield v9, production v6 e A41 v8
   (D24-01, IMPLEMENTATION_BLOCKER). Os seeds yield/production vêm de yield v4/production v1. Não existe seed area_41.
2. **Os 8 casos A019 continuam sem implementação.** O resolver da plataforma, aplicado às linhas dos workbooks,
   levanta `ReferenceResolutionError` nos 8 (D24-02, 2.4_IMPLEMENTATION_GAP). Nenhum componente agrupa linhas
   por-linha em 1 definição com instâncias.
3. **O builder MaxHT quebra no v9.** `LAST_DATA_ROW=154` fixo lê 32 linhas vazias, o que leva a um
   `TypeError` em `reference_resolver.py:308` (D24-03, IMPLEMENTATION_BLOCKER).
4. **`value_type` é descartado** pelos builders. Os 523 registros de variável dos seeds não têm o campo e o
   domínio assume `numerico` por default. As 4 linhas `categorico` do A41 não têm caminho até o runtime
   (D24-04, IMPLEMENTATION_BLOCKER).
5. **`allowed_values` e `declared_result_states` não existem no domínio.** Se aparecem no seed, `Variable(**)`
   levanta `TypeError` (D24-05, 2.4_IMPLEMENTATION_GAP).
6. **Os seeds divergiram dos workbooks aprovados** (D24-06). Exemplos: `ltp_tc_base` 273 × 274; unidades
   `tpd` × `t/d` e `tpd` × `-`; 298 variáveis e 3 parâmetros dos workbooks ausentes.

Os 1414 testes passam porque validam os seeds e snapshots antigos (energy v2, MaxHT v5), não os workbooks
aprovados (D24-16, TEST_COVERAGE_GAP).

Conforme o prompt ("se algum dos 8 A019 continuar sem implementação … BLOCKED"): **STAGE_2.4_GATE: BLOCKED**.

## 29.2 Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD | `14f2047e096b2ad2efb1ad36d25d00e2d5c2d155` (= origin; árvore limpa no início) |
| suíte | `1414 passed` (`evidence/pytest_baseline.txt`) |
| workbooks | SHA-256 idênticos aos da 2.3 rodada 5 (`evidence/workbook_sha256.txt`) |

| bloco | arquivo | SHA-256 (prefixo) | linhas semânticas | parâmetros | `_somatorio` |
|---|---|---|---|---|---|
| area_41 | A41 v8 | `be2372b4…` | 54 | 7 | 0 |
| energy | energy v5 | `34c1c88a…` | 56 | 4 | 0 |
| max_ht | MaxHT v9 | `74d5cbb7…` | 120 | 4 | 20 |
| production | production v6 | `17cb83ca…` | 88 | 17 | 5 |
| yield | yield v9 | `1c7b5684…` | 254 | 8 | 0 |

Seeds versionados:

| seed | variables | parameters | equations | aggregation_rules |
|---|---|---|---|---|
| energy | 52 | 4 | 24 | 11 |
| max_ht | 148 | 4 | 29 | 110 |
| production | 83 | 17 | 26 | 29 |
| yield | 240 | 8 | 138 | 80 |

## 29.3 Architecture Map

```
workbook .xlsx
  └─ reader/builder ........ tools/energy_seed_builder.py      (energy; SHEET energy, linhas 3..58 fixas)
                             tools/max_ht_seed_builder.py      (max_ht; SHEET MaxHT, linhas 3..154 fixas)
                             (AUSENTE: yield, production, area_41)
       extract_rows → build_canonical_model → build_variables/parameters/equations/aggregation_rules
       resolução nome→ID: app/engine/reference_resolver.py (build_name_index, resolve_reference,
                          translate_expression; tie_breaker opcional — max_ht usa prefer_sum_variant)
  └─ seed JSON ............. data/seed/{energy,max_ht,production,yield}/*.json   (sem area_41)
  └─ validators ............ app/validation/{variable,parameter,equation}_seed_validator.py
  └─ loader ................ app/repositories/seed_loader.py  (Variable(**), Parameter(**), Equation → Definition)
  └─ domínio/registries .... app/domain/{variables,parameters,equations}/{models,registry}.py
                             identidade de instância: ScopeResolver (app/engine/scope_resolver.py)
  └─ parser/avaliador ...... app/engine/expression_parser.py, expression_evaluator.py ("F", categóricas)
  └─ contexto .............. app/engine/calculation_context.py  CalculationKey(entity_id, scope_type, scope_value, period_id)
  └─ execução .............. app/engine/forecast_engine.py (materialize → DependencyGraph → Resolver → EquationEngine)
  └─ agregação temporal .... app/engine/temporal_aggregation_service.py (AVERAGE, SUM, WEIGHTED_AVERAGE, MOVING_AVERAGE)
```

Colunas do workbook e onde o fluxo as perde:

| coluna | builder lê | entidade canônica | seed | domínio |
|---|---|---|---|---|
| Type, name, unit, frequency, scope_type, scope_value, status, variable_type, description | sim | sim | sim | sim |
| value, version | sim | sim | só parâmetros | Parameter.value / version |
| expression | sim | sim | equations / aggregation_rules | EquationDefinition.expression |
| fonte | sim | sim | **não** | — |
| **value_type** | lida pelo openpyxl | **não** | **não** | default `numerico` |
| **allowed_values** | lida | **não** | **não** | **sem campo** (TypeError se presente) |
| **declared_result_states** | lida | **não** | **não** | **sem campo** (TypeError se presente) |
| source_reference | lida | **não** | substituída por constante | string livre |
| OBS | lida | não | não | — |

## 29.4 Contract×Code Matrix

| # | cláusula do contrato (2.3) | componente | status no código | evidência | defeito |
|---|---|---|---|---|---|
| C1 | os 5 workbooks aprovados são consumidos | builders | 2/5 têm builder; 1 dos 2 quebra no v9 | consumption_probe_out.txt | D24-01, D24-03 |
| C2 | identidade = name+frequency+scope_type+scope_value | validator / registry | não imposta (warning por assinatura com unit) | runtime_out.json P5; validator:774 | D24-07 |
| C3 | A019 regras 1–5 | reference_resolver | implementadas; regra 4 levanta erro nas 8 linhas-instância | a019_20_code.csv | D24-02 |
| C4 | instância por escopo com 1 ID | ScopeResolver/Context/Engine | **CONFORME** no runtime | P2 (7/7 OK, cruzado detectado) | — |
| C5 | frequência filtra antes do escopo | reference_resolver:217-226 | CONFORME | test_frequency_still_filters_before_scope | — |
| C6 | value_type ∈ {numerico, categorico}, sem alias | domínio + validator | CONFORME no domínio; **não transportado** do workbook | P3 | D24-04 |
| C7 | allowed_values | — | ausente | P3 | D24-05 |
| C8 | declared_result_states locais (R1); NO_APPLICABLE_RULE → "F" | — | ausente (só o literal "F" existe no avaliador) | P3, P4 | D24-05 |
| C9 | "F" nunca vira número | expression_evaluator | CONFORME (ConditionalFailureError; `==/!= "F"` permitido) | P4 | — |
| C10 | Política B de agregação (estado não-VALID invalida) | temporal_aggregation_service | CONFORME para "F" (AggregationFailureError) | test_dsl_structural_contracts | — |
| C11 | 207 agregações, 4 tipos | builders + service | service suporta os 4 tipos; seeds divergem da contagem | §29.11 | D24-06, D24-08 |
| C12 | 13 vínculos entre workbooks | seeds | 1 ligado por ID; demais redeclarados | §29.13 | D24-11 |
| C13 | metadados (source_reference) | builders | constantes fixas v2/v5 | consumption_probe_out.txt | D24-09 |

## 29.5 Builder Audit

### energy v5 → `tools/energy_seed_builder.py`

As 56 linhas foram lidas, sem nenhuma vazia. Resultado gerado × seed:

| saída | gerados × seed | igual? |
|---|---|---|
| parameters | 4 × 4 | sim |
| equations | 24 × 24 | sim |
| aggregation_rules | 11 × 11 | sim |
| variables | 52 × 52 | **não**: 1 diferença, `VAR18001 unit 'tpd' → 't/d'`; o seed está defasado |

| campo | valor no workbook | leitura | destino | conforme? |
|---|---|---|---|---|
| name | 56 nomes | `row["name"]` | variable_name / parameter_name; índice A019 | sim |
| value | 4 parâmetros numéricos | repassado sem conversão | Parameter.value | sim |
| value_type | 56 × `numerico` | **descartado** | ausente → default `numerico` | **não** (resultado correto por coincidência) |
| frequency | diário/mensal/anual | repassado | frequency; filtro A019 | sim |
| scope_type | linha / linha_grupo | repassado | scope_type | sim |
| scope_value | L1_L7 etc. | repassado | scope_value → ScopeResolver | sim |
| declared_result_states | 0 linhas | descartado | — | n/a (vazio) |
| allowed_values | 0 linhas | descartado | — | n/a (vazio) |
| expression | 35 | aritmética → translate_expression; agregação → **AGGREGATION_SPECS por nº de linha** | equations / aggregation_rules | parcial (D24-08) |

### MaxHT v9 → `tools/max_ht_seed_builder.py`

Execução sem alterações: 152 linhas lidas (3..154), das quais **32 vazias** (123..154). `build_seeds` levanta
`TypeError: object of type 'NoneType' has no len()` em `reference_resolver.py:308 _translate_code_segment`.
**v9 não é consumível** (D24-03).

Diagnóstico com `LAST_DATA_ROW=122` aplicado apenas em memória:

- 78 regras de agregação (AVERAGE 58, SUM 20), idênticas linha a linha ao inventário da 2.3;
- 0 colisões de identidade (os `_somatorio` desambiguam);
- nenhuma saída é igual ao seed versionado (116 × 148 variáveis, 78 × 110 regras): o seed é do v5.

| campo | valor no workbook | leitura | destino | conforme? |
|---|---|---|---|---|
| name | 120 (+32 None lidos) | `row["name"]` | índice A019; None quebra o índice | **não** (D24-03) |
| value | 4 × 1.05 | `float(value)` | Parameter.value | coerção (D24-14) |
| value_type | 120 × numerico | **descartado** | default | **não** (D24-04) |
| frequency | diário/mensal/anual | repassado; DSL confere a frequência alvo | sim | sim |
| scope_type / scope_value | linha, linha_grupo | repassado | sim | sim |
| declared_result_states / allowed_values | 0 / 0 | descartados | — | n/a |
| expression | 107 | DSL_PATTERN (78) + translate_expression | sim | sim, após correção da janela |

### production v6, yield v9, A41 v8 — sem builder

| campo | production v6 | yield v9 | A41 v8 |
|---|---|---|---|
| name / value / frequency / scope_type / scope_value / expression | **não lidos por código algum** | **não lidos** (cabeçalho na linha 1) | **não lidos** |
| value_type | 88 × numerico | 254 × numerico | 50 × numerico, **4 × categorico** |
| allowed_values | 0 | 0 | **4** (hes L4..L7) |
| declared_result_states | 0 | 0 | **2** (r39, r42) |
| seed existente | production v1 (83/17/26/29) | yield v4 (240/8/138/80) | **nenhum** |

Resultado: IMPLEMENTATION_BLOCKER D24-01.

## 29.6 Identity Audit

- **Runtime.** `CalculationKey(entity_id, scope_type, scope_value, period_id)` e os registries indexados por
  definition_id/instance_id identificam instâncias corretamente (P2).
  `ParameterDefinitionRegistry.get("PARAM12001")` sem escopo levanta
  `ValueError: Mais de uma ParameterDefinition encontrada…`. É um erro explícito, não uma escolha silenciosa: conforme.
- **Unicidade de identidade.** Não é imposta (D24-07). `validate_variable_signatures`
  (`variable_seed_validator.py:774`) só emite *warning* (7 no seed atual), e a assinatura inclui `unit` e
  `variable_type`, que não fazem parte da identidade.
  - No seed max_ht há **49 identidades intra-bloco duplicadas** (ex.: `producao` mensal linha/L1_L7 =
    VAR13002 e VAR13004). Elas só resolvem via `prefer_sum_variant`.
  - Nos workbooks v9 aprovados não há nenhuma colisão.
- **Entre blocos.** 10 identidades repetidas (ex.: `lth` diário linha/L1_L7 em 4 blocos). Ver §29.13.

## 29.7 Frequency Audit

- A frequência é repassada da célula ao seed nos 2 builders existentes.
- A019 regra 2 (`reference_resolver.py:217-226`): o filtro de mesma frequência vem antes do escopo, conforme.
  Quando nenhum candidato tem a mesma frequência, o pool volta a todas as frequências
  (`test_monthly_input_resolves_for_daily_consumer`). Esse é o comportamento aprovado para parâmetros e
  entradas anuais/mensais, confirmado nos 12 casos CONFORME (ex.: `pick_up` diário ← `pick_up_yield` anual).
- MaxHT: `build_aggregation_rules` faz `assert` entre a frequência declarada no texto DSL e a da linha, sem
  normalização silenciosa.
- energy: a frequência alvo das regras vem da linha, mas o par origem/alvo vem de `AGGREGATION_SPECS` por
  número de linha (D24-08).
- `TimePeriodResolver` gera o `period_id` a partir da frequência da VariableDefinition (forecast_engine.py:417).

## 29.8 Scope Audit

- `scope_type`/`scope_value` chegam intactos ao seed.
- `ScopeResolver` expande `L1_L7` em 7 instâncias; `linha_grupo` resolve por `GROUP_MEMBERS`.
- `@Lx` explícito é conforme nos casos 1, 2, 3, 8 e 10 (a019_20_code.csv).
- Controle negativo P2: sem `PARAM12001@L3`, o runtime levanta `ParameterNotFoundError`. Não recai sobre outra
  linha nem sobre o escopo pai; conforme.
- Desvio estrutural no seed production (D24-10): `producao` (v6 r71, **uma** linha linha/L1_L7) está dividido
  em 7 definições (VAR12046..52) e 7 equações (EQ12014..20). É o contorno manual do D24-02.

## 29.9 Value Type Audit (probe P3, SeedLoader real sobre cópia temporária dos seeds)

| entrada no seed | resultado |
|---|---|
| sem value_type (estado atual dos 4 seeds) | carrega, `value_type='numerico'` (**default implícito**) |
| `numerico` | carrega `numerico` |
| `categorico` | carrega `categorico` |
| `numeric` | rejeitado pelo validator: `allowed values: categorico, numerico` |
| `categorical` | rejeitado pelo validator |

- O vocabulário está correto e sem aliases (commit 07af71b).
- Nenhum builder transporta value_type. As 4 linhas `categorico` do A41 (`hes` L4..L7, produtor externo
  "bloco maintenance") não têm caminho: sem builder A41, e mesmo com builder o campo seria descartado.
- A ausência do campo vira `numerico` sem erro. Isso é uma regra implícita, vedada pelo prompt (D24-04).
- `ParameterDefinition.value` é tipado `float | int`, o que é consistente com os 40 parâmetros numéricos.
  O builder MaxHT coage com `float()` (D24-14).

## 29.10 State Audit

- **"F".** `ConditionalFailureError` quando "F" é consumido aritmeticamente (P4: `EquationEvaluationError`,
  original `ConditionalFailureError`). O resultado `"F"` é preservado quando produzido por comparação
  (`'"F" if VAR99001 == "F" else "OK"'` → `'F'`). Conforme.
- **declared_result_states (R1).** Não há campo no domínio; `Variable(**)` levanta
  `TypeError: unexpected keyword argument 'declared_result_states'`. A41 r39/r42 declaram
  `NO_APPLICABLE_RULE → "F"`. O literal está correto no workbook, mas não há transporte (D24-05).
- **Símbolos ausentes do código** (grep em `app/` e `tools/`): `EvaluationResult`, `NO_APPLICABLE_RULE`,
  `BLOCKED_BY_UPSTREAM_ERROR`, `declared_result_states`. Esperado para a Etapa 3.
- **F-001.** A primeira exceção aborta o `ForecastEngine`: VAR99012, independente, não foi calculada (D24-13,
  NON_BLOCKING, Etapa 3).

## 29.11 Aggregation Audit

| bloco | workbook (2.3) | seed versionado | builder atual sobre o workbook aprovado |
|---|---|---|---|
| area_41 | 10 (AVERAGE 10) | — | sem builder |
| energy | 11 (WAVG 7, AVG 3, MA 1) | 11 (idem) | 11, **igual** ao seed |
| max_ht | 78 (AVG 58, SUM 20) | 110 (AVG 58, SUM 52; variantes v5) | crash; 78 corretas com a janela corrigida em memória |
| production | 28 (AVG 15, SUM 10, WAVG 2, MA 1) | 29 (AVG 23, SUM 3, WAVG 2, MA 1) | sem builder |
| yield | 80 (AVG 80) | 80 (AVG 80; escopos v4) | sem builder |
| **total** | **207** | 230 | — |

- `temporal_aggregation_service.py` implementa os 4 tipos. SUM é dimensional (Fase H), WEIGHTED_AVERAGE
  falha com peso zero, e "F" na série gera `AggregationFailureError` (Política B). Conforme.
- **`_somatorio` (25 linhas).** No MaxHT, 20 nomes são reconhecidos pelo DSL_PATTERN do builder (probe com
  janela corrigida). Os 5 da production não têm builder.
- **As agregações A019 sobre linhas-instância** (A41 r52/r53, production r60) falham no caminho builder
  (§29.12).

## 29.12 A019 Full Audit (20 casos)

A coluna "resolver" é `reference_resolver.resolve_reference` (código da plataforma) aplicado às linhas do
workbook aprovado, com o escopo e a frequência do consumidor (`evidence/a019_20_code.csv`).
A coluna "runtime" indica se o motor suporta a semântica quando o seed a expressa com 1 ID e instâncias.

| # | workbook | linha | consumidor (freq, escopo) | produtor (freq, escopo) | @ | 2.3 | resolver | builder | runtime |
|---|---|---|---|---|---|---|---|---|---|
| 1 | area_41 | 22 | retirada_condensado_grupo (d, grupo L1_L3) | valor_retirada (d, L1/L2/L3) | sim | CONFORME | RESOLVED | **ausente** | sim |
| 2 | area_41 | 39 | retirada_condensado_grupo (d, grupo L4_L5) | hes (d, L4..L7) | sim | CONFORME | RESOLVED | **ausente** | sim |
| 3 | area_41 | 42 | retirada_condensado_grupo (d, grupo L6_L7) | hes (d, L4..L7) | sim | CONFORME | RESOLVED | **ausente** | sim |
| 4 | area_41 | 52 | retirada_condensado_linha (m, L1_L7) | retirada_condensado_linha (d, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* |
| 5 | area_41 | 53 | retirada_condensado_linha (a, L1_L7) | retirada_condensado_linha (d, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* |
| 6 | production | 35 | lth (d, L1_L7) | lth_meta (a, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | **sim (P2)** |
| 7 | production | 48 | oee (d, L1_L7) | lth_meta (a, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | **sim (P2: EQ12004)** |
| 8 | production | 50 | oee_total (d, grupo L1_L7) | lth_meta (a, L1..L7) | sim | CONFORME | RESOLVED | ausente | sim (EQ12005) |
| 9 | production | 60 | pick_up (m, L1_L7) | pick_up (d, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* |
| 10 | production | 61 | pick_up_total (d, grupo L1_L7) | pick_up (d, L1..L7) | sim | CONFORME | RESOLVED | ausente | sim |
| 11 | production | 71 | producao (d, L1_L7) | pick_up (d, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* (seed dividido, D24-10) |
| 12–18 | production | 53–59 | pick_up (d, Lk) | pick_up_yield (a, L1..L7) | não | CONFORME | RESOLVED (Lk→Lk) | ausente | sim |
| 19 | yield | 107 | n_ppt (d, L1_L7) | tanque (d, L1..L7) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* |
| 20 | yield | 107 | n_ppt (d, L1_L7) | tanque_base (a, L1..L7; 14/14/16/18/18/18/18) | não | **GAP** | **ReferenceResolutionError** | ausente | sim* |

\* O mecanismo é o mesmo provado em P2 (1 definição, instâncias por escopo; `CalculationKey` com scope_value),
mas não há teste nem seed que o exercite para esse caso específico.

Mensagem do resolver nos 8 GAP (ex. caso 6):
`Referência lth_meta: instâncias do consumidor linha/L1_L7 resolvem para definições diferentes
(production:37[anual, linha/L1] vs production:38[anual, linha/L2]). Uma expressão grava um único ID: use
escopo explícito (@) ou divida a definição consumidora por escopo.`

Essa mensagem está correta para N definições distintas. O que falta é o passo de construção que agrupe as
N linhas por-linha (mesmo name + frequency, escopos L1..L7) em **1 definição com N instâncias**, que é o
modelo que o runtime já executa.

**Prova runtime P2** (EQ12004 `VAR12016 / PARAM12001`, linha/L1_L7, seed real, 7 ParameterInstances de PARAM12001):

| linha | lth | lth_meta@linha | oee calculado | esperado | associação cruzada (lth/lth_meta de outra linha) | detectada |
|---|---|---|---|---|---|---|
| L1 | 913 | 1050 | 0.869524 | 0.869524 | 0.830000 | sim |
| L2 | 926 | 1050 | 0.881905 | 0.881905 | 0.841818 | sim |
| L3 | 939 | 1100 | 0.853636 | 0.853636 | 0.894286 | sim |
| L4 | 952 | 1100 | 0.865455 | 0.865455 | 0.906667 | sim |
| L5 | 965 | 1100 | 0.877273 | 0.877273 | 0.919048 | sim |
| L6 | 978 | 1100 | 0.889091 | 0.889091 | 0.931429 | sim |
| L7 | 991 | 1100 | 0.900909 | 0.900909 | 0.943810 | sim |

**Conclusão A019: 12/20 CONFORME no resolver; 8/20 sem implementação** no caminho workbook → seed (D24-02).
O runtime não é o bloqueio.

## 29.13 Cross-Workbook Audit (13 vínculos entre os 5 workbooks)

| # | consumidor | nome (freq, escopo) | produtor | ID(s) no seed consumidor | ID(s) no seed produtor | ligado por ID? |
|---|---|---|---|---|---|---|
| 1 | area_41 r9 | lth (d, linha/L1_L7) | yield | — (sem seed A41) | — | não |
| 2 | energy r3 | producao (d, linha/L1_L7) | production | VAR18001 | VAR12046..52 (dividido) | não |
| 3 | energy r7 | pick_up (d, linha/L1_L7) | production | VAR18005 | VAR12029..35 | não |
| 4 | energy r8 | pick_up_total (d, grupo L1_L7) | production | VAR18006 | VAR12043 | não |
| 5 | energy r9 | pick_up_total (m, grupo L1_L7) | production | VAR18007 | VAR12044 | não |
| 6 | energy r10 | lth (d, linha/L1_L7) | production | VAR18008 | VAR12016 | não |
| 7 | energy r11 | lth_total (d, grupo L1_L7) | production | VAR18009 | VAR12018 | não |
| 8 | energy r12 | lth_total (m, grupo L1_L7) | production | VAR18010 | VAR12019 | não |
| 9 | energy r13 | lth_meta (a, linha/L1_L7) | production | VAR18011 (variável) | PARAM12001 (parâmetro) | não |
| 10 | max_ht r68 | lth (d, linha/L1_L7) | production | VAR13021 | VAR12016 | não |
| 11 | max_ht r98 | producao (d, linha/L1_L7) | production | VAR13001 | VAR12046..52 | não |
| 12 | production r87 | yield (d, linha/L1_L7) | yield | usa VAR11001@Lx | VAR11001 | **sim** (EQ12003, EQ12006..12) |
| 13 | yield r32 | lth (d, linha/L1_L7) | production | VAR11003 | VAR12016 | não |

Os outros 21 produtores externos declarados nos workbooks (maintenance, temperature_lp, forecast, alumina,
maintenance_plan, area_04_13) não são verificáveis, pois estão fora dos 5 blocos.

O contrato 2.3 classificou os vínculos como documentais e **não define o mecanismo de ligação**: identidade
global × entrada_externa local. Por isso o item é registrado como CONTRACT_GAP (D24-11), e não como defeito
de código. Caso 9: o consumidor energy declara `lth_meta` como variável anual, enquanto o produtor o declara
como parâmetro. É uma divergência de kind que o contrato de ligação precisa decidir.

## 29.14 ltp_tc Audit

| item | workbook yield v9 | seed yield (v4) | código |
|---|---|---|---|
| r92 `ltp_tc` variable, entrada_externa, diário, linha/L1_L7 | **value=273, version=1** | VAR11240 (sem value) | `Variable` não tem campo `value`; sem builder yield → sem destino definido |
| r93 `ltp_tc` mensal (AVERAGE de r92) | agregação | VAR11164 + regra AVG | — |
| r102 `ltp_tc_base` parameter, linha/L1_L7 | **value=274** | PARAM11002 **value=273** | seed divergente (D24-06); teste `test_yield_v4_l1l7_and_aggregation_rules.py` referencia a versão v4 |

A 2.3 registrou r92 como NB. Na 2.4 o código não tem regra para `value` em `Type=variable`: um builder
futuro ou o descartaria em silêncio (vedado) ou quebraria `Variable(**)`. É preciso uma decisão explícita
(D24-12, CONTRACT_GAP).

## 29.15 Metadata Audit

| metadado | workbook | builder | seed | observação |
|---|---|---|---|---|
| source_reference | coluna presente (vazia no energy v5; `Yield!…` no yield) | ignorada; constante `…energy_v2.xlsx` / `…MaxHT_v5.xlsx` | constante em todo registro | rastreabilidade incorreta (D24-09) |
| description | preenchida no energy/MaxHT; vazia em partes de production/yield (NB 2.3) | repassada | repassada | sem regra de obrigatoriedade no builder |
| fonte | produtor externo textual | lida na entidade canônica | **não gravada** | necessária para o contrato de ligação (§29.13) |
| OBS | livre | ignorada | — | informativa |
| version (parâmetros) | 1 | `int(version)` | sim | conforme |

## 29.16 Test Coverage Matrix

Detalhe completo em `test_coverage_matrix.csv`.

| teste | comportamento exigido | cobertura atual |
|---|---|---|
| T24-01 | builder(workbook aprovado) == seed, todos os blocos | NÃO EXISTE (reconciliação contra snapshots v2/v5) |
| T24-02 | builders yield/production/A41 (cabeçalho explícito) | NÃO EXISTE |
| T24-03 | lth r35 / oee r48 por instância, cruzado falha | PARCIAL (apenas probe P2) |
| T24-04 | n_ppt r107 por instância (tanque, tanque_base) | NÃO EXISTE |
| T24-05 | agregação/consumo sobre 1 definição por-linha (pick_up r60/r71, A41 r52/r53) | NÃO EXISTE |
| T24-06 | janela de linhas / linha sem name | NÃO EXISTE |
| T24-07 | value_type célula → VariableDefinition | PARCIAL (domínio/validator) |
| T24-08 | hes categorico ponta a ponta; ausência = erro | NÃO EXISTE |
| T24-09 | allowed_values transportado e aplicado | NÃO EXISTE |
| T24-10 | declared_result_states (R1) transportado | NÃO EXISTE |
| T24-11 | ltp_tc_base = 274 | NÃO EXISTE |
| T24-12 | identidade duplicada = erro | NÃO EXISTE |
| T24-13 | agregações energy derivadas do texto | PARCIAL |
| T24-14 | source_reference = arquivo lido | NÃO EXISTE |
| T24-15 | 13 vínculos cross-workbook | PARCIAL (production←yield) |
| T24-16 | value em Type=variable | NÃO EXISTE |
| T24-17 | falha isolada por nó (Etapa 3) | NÃO EXISTE |
| T24-18 | sem coerção de valor de parâmetro | NÃO EXISTE |

Já coberto pela suíte atual: vocabulário value_type sem aliases, "F" no avaliador/agregação, A019 no
resolver com entidades sintéticas (`test_reference_resolver.py`), runtime production←yield
(`test_yield_production_runtime_contract.py`) e os 4 tipos de agregação.

## 29.17 Defect Register

Detalhe completo, com contrato, atual × esperado e teste necessário, em `defect_register.csv`.

| ID | arquivo | módulo | classe/função | linha | contrato | atual → esperado | sev. | classificação | teste |
|---|---|---|---|---|---|---|---|---|---|
| D24-01 | tools/ (ausente) | — | — | — | 5 workbooks consumidos | sem builder yield/production/A41 → builder por workbook | CRÍTICA | IMPLEMENTATION_BLOCKER | T24-01, T24-02 |
| D24-02 | app/engine/reference_resolver.py + builders | reference_resolver | _filter_by_consumer_scope | 180 | A019 regra 4 | 8 casos levantam erro → agrupar linhas-instância em 1 definição | CRÍTICA | 2.4_IMPLEMENTATION_GAP | T24-03..05 |
| D24-03 | tools/max_ht_seed_builder.py | max_ht_seed_builder | extract_rows / LAST_DATA_ROW | 48, 85 | MaxHT v9 | TypeError (32 linhas vazias) → janela pelo conteúdo, erro explícito | ALTA | IMPLEMENTATION_BLOCKER | T24-06 |
| D24-04 | builders; app/domain/variables/models.py | build_canonical_model; VariableDefinition | value_type | energy 105/195; max_ht 128/242; models 67 | value_type por linha | descartado + default numerico → transportado, ausência = erro | ALTA | IMPLEMENTATION_BLOCKER | T24-07, T24-08 |
| D24-05 | app/repositories/seed_loader.py | SeedLoader | load_variable_definitions → Variable(**) | 332 | allowed_values, R1 | sem campo, TypeError → metadado transportado | ALTA | 2.4_IMPLEMENTATION_GAP | T24-09, T24-10 |
| D24-06 | data/seed/* | seeds | — | — | seeds = workbooks aprovados | derivas de valor/unidade, 298 variáveis + 3 parâmetros ausentes → regenerar pelos builders | ALTA | IMPLEMENTATION_DEFECT | T24-01, T24-11 |
| D24-07 | app/validation/variable_seed_validator.py | variable_seed_validator | validate_variable_signatures | 774, 915 | identidade única | warning por assinatura com unit → erro por identidade | MÉDIA | IMPLEMENTATION_DEFECT | T24-12 |
| D24-08 | tools/energy_seed_builder.py | energy_seed_builder | AGGREGATION_SPECS | 282–296 | agregação da expressão | por nº de linha → derivada do texto | MÉDIA | IMPLEMENTATION_DEFECT | T24-13 |
| D24-09 | tools/energy_seed_builder.py; tools/max_ht_seed_builder.py | builders | SOURCE_REFERENCE | 45; 50 | rastreabilidade | constante v2/v5 → arquivo lido | BAIXA | IMPLEMENTATION_DEFECT | T24-14 |
| D24-10 | data/seed/production | seed production | EQ12014..20 / VAR12046..52 | — | r71 = 1 definição | 7 definições → 1 definição, 7 instâncias | MÉDIA | IMPLEMENTATION_DEFECT | T24-05 |
| D24-11 | (contrato) | cross-workbook | — | — | 13 vínculos | mecanismo de ligação indefinido → decisão explícita | MÉDIA | CONTRACT_GAP | T24-15 |
| D24-12 | (contrato) / yield v9 r92 | ltp_tc | — | — | Variable sem value | value=273 sem destino → regra explícita | BAIXA | CONTRACT_GAP | T24-16 |
| D24-13 | app/engine/forecast_engine.py | ForecastEngine | calculate_from_definition_registry | 375–396 | F-001 | aborto global → resultado por nó (Etapa 3) | MÉDIA | NON_BLOCKING | T24-17 |
| D24-14 | tools/max_ht_seed_builder.py | max_ht_seed_builder | build_parameters | 274 | sem normalização | float() → validar sem coagir | BAIXA | NON_BLOCKING | T24-18 |
| D24-15 | tools/* | builders | HEADER_ROW | 41; 46 | — | yield com cabeçalho na linha 1 | BAIXA | INFORMATIONAL | T24-02 |
| D24-16 | tests/ | suíte | — | — | evidência do contrato 2.3 | 1414 verdes sobre snapshots antigos → T24-01..18 | ALTA | TEST_COVERAGE_GAP | T24-01..18 |

Totais: IMPLEMENTATION_BLOCKER 3 · 2.4_IMPLEMENTATION_GAP 2 (D24-02 cobre os 8 casos A019) ·
IMPLEMENTATION_DEFECT 5 · CONTRACT_GAP 2 · NON_BLOCKING 2 · INFORMATIONAL 1 · TEST_COVERAGE_GAP 1.

## 29.18 Final Gate

O gate está bloqueado pelos seguintes itens:

- **D24-02.** Os 8 casos A019 continuam sem implementação e não há decisão posterior redefinindo seu escopo.
  Por regra explícita do prompt, isso basta para o bloqueio.
- **D24-01.** Não há builder para 3 dos 5 workbooks aprovados.
- **D24-03.** O builder MaxHT quebra no v9.
- **D24-04.** `value_type` não é transportado.

Para desbloquear, é necessária uma execução 2.4 autorizada a implementar, na seguinte ordem:

1. builders yield/production/A41 e correção da janela MaxHT;
2. agrupamento das linhas-instância A019;
3. transporte de value_type, allowed_values e declared_result_states;
4. regeneração dos seeds;
5. testes T24-01..T24-18.

STAGE_2.4_GATE: BLOCKED
