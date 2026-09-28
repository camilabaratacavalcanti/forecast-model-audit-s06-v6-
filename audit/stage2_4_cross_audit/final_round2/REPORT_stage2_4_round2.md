# Etapa 2.4 — Rodada 2: correção dos blockers e reexecução do Cross-Audit

Esta é a execução corretiva da Etapa 2.4. A auditoria somente leitura da rodada 1 (commit `a519d8a`,
`audit/stage2_4_cross_audit/final/`, preservada sem alterações) terminou em `STAGE_2.4_GATE: BLOCKED`.

Nesta rodada foram alterados código, builders, domínio, loaders, validators, seeds e testes. Os cinco workbooks
aprovados **não** foram alterados: estão versionados em `data/workbooks/` como cópias byte a byte, e o builder
recusa qualquer arquivo cujo SHA-256 difira do aprovado.

Todas as evidências ficam em `final_round2/evidence/` e são reexecutáveis:

```
python audit/stage2_4_cross_audit/final_round2/evidence/audit_round2.py
python -m pytest tests/test_stage2_4_workbook_contract.py
python -m tools.workbook_seed        # regenera os seeds (idempotente; resultado = seeds versionados)
```

## 1. Resposta à pergunta central

> O sistema consegue representar e executar fielmente o contrato aprovado na Etapa 2.3 a partir dos workbooks
> reais, sem depender de snapshots históricos ou de contornos artificiais?

**Sim, para tudo o que o contrato aprovado define.** Os cinco workbooks são lidos diretamente e cada linha
percorre o caminho abaixo, sem snapshot e sem seed feito à mão.

```
workbook -> builder -> modelo canônico -> seed -> validator -> SeedLoader -> domínio -> resolver -> runtime
```

As provas estão em `evidence/workbook_vs_seed.csv` (572/572 linhas reconciliadas) e em T24-01..T24-18
(72 testes).

Ficam três **decisões contratuais pendentes**. Nenhuma foi decidida nesta rodada, todas estão registradas no
manifesto do seed e documentadas por teste:

| id | decisão pendente |
|---|---|
| D24-11 | mecanismo de ligação entre workbooks |
| D24-12 | significado de `value` numa linha `Type=variable` |
| R2-01 | nova: `desaguamento_oee` → `consumo_mpsa` não alcançável, no próprio texto do workbook production v6 |

## 2. Baseline (antes de qualquer alteração)

| item | valor |
|---|---|
| branch / HEAD | `feature/area-41-block` / `a519d8a` (= origin) |
| árvore | limpa |
| workbooks | 5/5 com SHA-256 idêntico ao da 2.3 e da 2.4 (`evidence/workbook_sha256.txt`) |
| suíte | 1414 passed |
| leitura integral | 2.3 final_round5, REPORT_stage2_4, defect_register, test_coverage_matrix, R1 |

| bloco | versão | SHA-256 (prefixo) | aba | cabeçalho | linhas | vazias ignoradas |
|---|---|---|---|---|---:|---:|
| area_41 | v8 | `be2372b4…` | A41 | 2 | 54 | 252 |
| energy | v5 | `34c1c88a…` | energy | 2 | 56 | 249 |
| max_ht | v9 | `74d5cbb7…` | MaxHT | 2 | 120 | 214 |
| production | v6 | `17cb83ca…` | production | 2 | 88 | 212 |
| yield | v9 | `1c7b5684…` | yield | **1** | 254 | 0 |

## 3. Arquitetura implementada

```
data/workbooks/*.xlsx                     cópias aprovadas (SHA-256 conferido em tools/workbook_seed/blocks.py)
tools/workbook_seed/reader.py             cabeçalho localizado; janela = conteúdo; linha sem name / conteúdo
                                          residual / coluna obrigatória ausente = erro; nenhum valor alterado
tools/workbook_seed/canonical.py          Type x expressão; value_type obrigatório; parâmetro numérico físico;
                                          definição com instâncias por linha; identidade por instância;
                                          allowed_values / declared_result_states (R1: literal na própria
                                          fórmula); value em Type=variable -> decisão pendente
tools/workbook_seed/aggregation_dsl.py    gramática das 4 agregações textuais (sem nº de linha)
tools/workbook_seed/seeds.py              projeção: variables, parameters, equations, aggregation_rules,
                                          manifest (proveniência + decisões pendentes); nomes -> IDs pela
                                          A019 da plataforma, sem desempate próprio; referência inalcançável
                                          -> decisão pendente registrada
tools/{area_41,energy,max_ht,production,yield}_seed_builder.py    um módulo fino por workbook
app/domain/variables/models.py            value_type obrigatório; allowed_values; DeclaredResultState;
                                          VariableInstanceDeclaration; is_value_in_domain()
app/domain/parameters/models.py           value_type obrigatório (numerico + valor numérico); frequency
app/validation/variable_seed_validator.py value_type obrigatório; campos desconhecidos = erro;
                                          allowed_values; declared_result_states; instances; identidade
app/validation/parameter_seed_validator.py value_type/frequency; campos desconhecidos; identidade
app/engine/registry_validator.py          equação pode produzir uma instância DECLARADA da definição alvo
```

O `ScopeResolver` e o runtime não foram alterados. A única mudança fora de builder, domínio e validação está no
`RegistryIntegrityValidator`. Antes, ele exigia escopo idêntico entre equação e variável alvo. Agora aceita
também uma equação cujo escopo seja uma das instâncias que a definição alvo declara. Isso é necessário porque
cada linha por-linha do workbook tem a sua própria expressão (por exemplo, `pick_up` L1..L7). A regra não
afrouxa nada para definições sem instâncias declaradas, como mostra
`test_t24_05_equation_may_produce_only_a_declared_instance`.

### Representação da definição com instâncias por linha (D24-02, D24-10)

Linhas com o mesmo (tipo, `name`, `frequency`, `scope_type="linha"`) e `scope_value` atômico formam UMA
definição. Todos os atributos de definição têm de ser iguais entre as linhas (`unit`, `variable_type`,
`value_type`, `allowed_values`, `declared_result_states`, `status`, `fonte`); se divergirem, é erro. Por
instância ficam `description`, `source_reference`, expressão e valor.

| workbook | definição | linhas do workbook | escopo declarado | representação no seed |
|---|---|---|---|---|
| area_41 | `valor_retirada` diário | 19–21 | linha/L1_L3 | 1 variável + `instances` L1..L3 |
| area_41 | `hes` diário (categorico) | 25–28 | linha/L4_L7 | 1 variável + `instances` L4..L7 |
| area_41 | `retirada_condensado_linha` diário | 45–51 | linha/L1_L7 | 1 variável + 7 equações (uma por linha) |
| production | `lth_meta` anual | 37–43 | linha | 1 `parameter_id`, 7 registros por escopo |
| production | `pick_up` diário | 53–59 | linha/L1_L7 | 1 variável + 7 equações (uma por linha) |
| production | `pick_up_yield` anual | 64–70 | linha | 1 `parameter_id`, 7 registros por escopo |
| yield | `tanque` diário | 227–233 | linha/L1_L7 | 1 variável + `instances` L1..L7 |
| yield | `tanque_base` anual | 234–240 | linha | 1 `parameter_id`, 7 registros por escopo |

Parâmetros usam o modelo já existente, com um ID e um registro por escopo na chave composta do
`ParameterDefinitionRegistry`. Variáveis usam a faixa contígua (L4_L7, L1_L3, L1_L7) mais `instances`
declaradas. A faixa só é aceita pelo validator quando `instances` existem, e linhas não contíguas são erro.
`producao` (production r71) é uma linha linha/L1_L7 e virou 1 definição e 1 equação, no lugar das 7 definições
artificiais do seed histórico.

## 4. Status dos defeitos da rodada 1

Detalhe completo em `defect_register.csv`.

### FIXED

| id | antes (rodada 1) | agora | prova |
|---|---|---|---|
| D24-01 | 3/5 workbooks sem builder | 5 builders sobre um pipeline comum; `area_41` ganhou seed | T24-01, T24-02 |
| D24-02 | 8 casos A019 com `ReferenceResolutionError` | **20/20 RESOLVED**; 0 erros | T24-03..05, `evidence/a019_20.csv` |
| D24-03 | MaxHT v9 `TypeError` (LAST_DATA_ROW=154) | janela derivada do conteúdo; 120 linhas; 78 regras | T24-06 |
| D24-04 | value_type descartado; default `numerico` | obrigatório do workbook ao domínio; sem default; sem alias | T24-07, T24-08 |
| D24-05 | allowed_values / declared_result_states sem domínio | transportados e validados até o domínio | T24-09, T24-10 |
| D24-06 | seeds divergentes (273, `tpd`, 298 variáveis ausentes) | seeds regenerados; builder == seed; 572/572 | T24-01, T24-11 |
| D24-07 | identidade só por aviso (com unit) | colisão no bloco = erro; entre blocos = aviso D24-11 | T24-12 |
| D24-08 | agregações energy por nº de linha | derivadas do texto; reordenar linhas não muda nada | T24-13 |
| D24-09 | `source_reference` constante (`energy_v2`, `MaxHT_v5`) | célula ou workbook lido; manifesto com SHA-256 | T24-14 |
| D24-10 | producao em 7 definições | 1 definição | T24-05 |
| D24-14 | `float()` no builder MaxHT | sem coerção; valor não numérico = erro | T24-18 |
| D24-15 | cabeçalho fixo na linha 2 | cabeçalho localizado (yield = 1) | T24-02, T24-06 |
| D24-16 | nenhum teste sobre os workbooks reais | 72 testes T24 | `evidence/t24_tests.txt` |

### REMAINING IMPLEMENTATION_BLOCKER

Nenhum.

### REMAINING IMPLEMENTATION_DEFECT

Nenhum.

### CONTRACT_GAP (pendentes; nenhum resolvido unilateralmente)

| id | decisão necessária | estado no código | teste |
|---|---|---|---|
| D24-11 | Como ligar consumidor e produtor entre workbooks: identidade global × entrada local; `fonte`; produtor parâmetro × consumidor variável (`lth_meta` em energy) | Cada workbook representa o que escreve: as entradas de outro bloco são definições próprias do consumidor (`entrada`/`entrada_externa`, sem valor calculado). Nenhum ID é ligado entre blocos. O validator emite 27 avisos rotulados `D24-11`. A ligação por ID production ← yield (`VAR11001@Lx`) existia apenas no seed histórico, feito à mão; o workbook aprovado production v6 declara `yield` como linha própria (entrada, fonte "bloco yield") | T24-15; `evidence/cross_workbook.csv` |
| D24-12 | Significado de `value`/`version` preenchidos numa linha `Type=variable` (yield v9 r92, `ltp_tc`: 273 / 1) | Não transportado ao domínio (Variable não tem `value`) e não descartado: fica em `data/seed/yield/manifest.json` → `pending_contract_decisions` | T24-16 |
| R2-01 (nova) | production v6 r25: `desaguamento_oee` (anual, linha_grupo/L1_L7) escreve `consumo_mpsa`, mas a única definição com esse nome é diária linha/L1_L7 (a anual chama-se `consumo_mpsa_grupo`). A A019 liga pelo fallback de frequência, só que nenhuma instância do consumidor alcança essa definição | A equação é gravada como escrita no workbook e falha de forma **explícita** ao ser avaliada (nunca silenciosa). O builder registra `R2-A019-UNREACHABLE` no manifesto. Varri as 238 equações: é o único caso. A Etapa 2.3 não detectou porque a resolução nominal não falha | `test_production_v1::test_desaguamento_oee_reference_to_consumo_mpsa_is_a_recorded_pending_decision` |

### NON_BLOCKING

| id | item |
|---|---|
| D24-13 | F-001 (isolamento de falha por nó) fica para a Etapa 3. T24-17 fixa o comportamento atual: a primeira falha aborta com erro explícito, sem valor parcial silencioso |
| — | Tratamento em runtime de valor fora de `allowed_values` (`INVALID_INPUT`) e propagação de `declared_result_states` são da Etapa 3 (R1 §4, D2). Nesta rodada o metadado é transportado e validável (`VariableDefinition.is_value_in_domain`), sem antecipar a arquitetura de resultados |

### INFORMATIONAL

| id | item |
|---|---|
| R2-02 | Duas SUMs m³/h → m³/mês e m³/ano (MaxHT v9) recebem `integration_factor` 24 pela regra dimensional já existente (`app.domain.units.required_sum_factor`), igual ao "fator 24" registrado na 2.3. As outras 28 SUMs somam taxas diárias (fator 1). O validador dimensional aponta 0 incoerências |
| R2-03 | **Os IDs mudaram.** Eles são atribuídos na ordem das linhas do workbook aprovado, então um ID do seed histórico não significa mais a mesma coisa (ex.: `VAR11001` era `yield`, agora é `eoc_solids`). Um consumidor externo de IDs antigos precisa remapear pela identidade. Os testes passaram a localizar entidades por identidade (`tests/seed_ids.py`) |
| R2-04 | Inventário de testes: 1414 → 1409 (92 removidos, 87 adicionados; lista completa em `evidence/test_inventory_delta.txt`), detalhado abaixo desta tabela |
| R2-05 | A normalização de unidade `tph` → `t/h` nos validators é anterior a esta rodada e não foi alterada; há 0 ocorrências nos cinco workbooks |
| R2-06 | `final/evidence/consumption_probe.py` (rodada 1) usa a API antiga dos builders. Foi preservado como registro histórico de `a519d8a` |

Detalhe do inventário de testes (R2-04):

- **Removidos:**
  - reconciliação contra os snapshots energy v2 / MaxHT v5 (52 testes), substituída por T24-01 contra os
    workbooks reais;
  - `test_yield_production_runtime_contract` (25), que provava a ligação por ID que o workbook aprovado não
    tem — é a D24-11;
  - testes de "assinatura"/"pendência" substituídos pelos de identidade e de dimensão.
- **Portados para identidade** (mesmas asserções de negócio sobre v6/v9, IDs localizados por nome):
  - regras BD-01..11 de production;
  - decisões 1–3 de yield v4, que continuam válidas em v9 com os nomes `_total`.

## 5. Critérios de PASS (§21 do prompt)

| critério | resultado | evidência |
|---|---|---|
| os cinco workbooks são consumíveis | SIM | `evidence/builders.txt` |
| os cinco builders funcionam | SIM | T24-02 |
| os seeds correspondem aos workbooks aprovados | SIM: builder == seed nos 5 blocos × 5 arquivos; 572/572 linhas reconciliadas (independente do builder) | T24-01, `evidence/workbook_vs_seed.csv` |
| os 20 casos A019 resolvem corretamente | SIM, 20/20 | `evidence/a019_20.csv`, T24-05 |
| nenhum `ReferenceResolutionError` nos 8 casos antes bloqueados | SIM, 0 | idem |
| `value_type` chega ao domínio | SIM: 508 numerico + 1 categorico (`hes`) | T24-07, T24-08, `evidence/domain_contract_fields.csv` |
| `allowed_values` chega ao domínio | SIM (`hes`: 5 opções) | T24-09 |
| `declared_result_states` chega ao domínio | SIM (A41 r39, r42: `NO_APPLICABLE_RULE` → "F") | T24-10 |
| sem default silencioso de `value_type` | SIM: sem default no domínio; obrigatório no seed e no workbook | T24-07, `evidence/code_scans.json` |
| sem coerção silenciosa de parâmetros | SIM | T24-18, `evidence/code_scans.json` |
| 207 agregações presentes e coerentes | SIM: 10/11/78/28/80; AVERAGE 166, SUM 30, WAVG 9, MA 2; 0 incoerências dimensionais; 417 instâncias | T24-13, `evidence/aggregations.csv` |
| testes T24 obrigatórios passam | SIM, 72/72 | `evidence/t24_tests.txt` |
| a suíte completa passa | SIM, 1409 passed | `evidence/full_suite.txt` |
| nenhuma divergência de workbook introduzida | SIM: 5/5 SHA-256 aprovados; builder recusa arquivo alterado | T24-14 |
| nenhum CONTRACT_GAP resolvido unilateralmente | SIM: D24-11, D24-12 e R2-01 apenas documentados, registrados e testados como pendentes | T24-15, T24-16, R2-01 |

## 6. Reexecução integral da auditoria (§20)

| verificação | resultado | arquivo |
|---|---|---|
| testes novos / existentes | 72 / 1409 passed | `t24_tests.txt`, `full_suite.txt` |
| auditoria célula a célula | 6195 células; 0 achados (tipo físico, espaços e caracteres ocultos, value_type, parâmetro numérico, formato de estado, conteúdo fora do cabeçalho) | `cell_audit.csv`, `cell_issues.csv` |
| validadores oficiais | variable 0 erros (27 avisos D24-11), parameter 0, equation 0, sintaxe das 238 expressões 0; RegistryIntegrityValidator OK | `validators.json` |
| builders nos cinco workbooks | ok; builder == seed | `builders.txt` |
| modelo canônico × seed | 572/572 linhas → definição, escopo, instâncias, equação ou regra | `workbook_vs_seed.csv` |
| A019 | 20/20 | `a019_20.csv` |
| 13 vínculos cross-workbook | 13 consumidores com definição local, unit e value_type iguais aos do produtor, sem ligação por ID (D24-11) | `cross_workbook.csv` |
| agregações | 207 | `aggregations.csv` |
| value_type / allowed_values / declared_result_states | 509 definições no domínio; `hes` categorico com 5 opções; 2 produtores locais de estado | `domain_contract_fields.csv` |
| identidade | 0 colisões por instância dentro de um bloco | `validators.json` |
| source_reference | célula ou workbook lido; 0 constantes históricas | T24-14, `code_scans.json` |
| aliases | 0 `numeric`/`categorical` em `app/`, `tools/`, `data/seed/` | `code_scans.json` |
| coerções | 0 `float(`/`int(` de valores em `tools/` | `code_scans.json` |
| linhas vazias como entidades | 0 (MaxHT 214, A41 252, energy 249, production 212 ignoradas) | `builders.txt` |
| decisões pendentes | D24-12 (yield r92) e R2-A019-UNREACHABLE (production r25) nos manifestos | `pending_contract_decisions.json` |

## 7. Arquivos alterados

| categoria | arquivos |
|---|---|
| builders | `tools/workbook_seed/` (novo); `tools/{area_41,production,yield}_seed_builder.py` (novos); `tools/{energy,max_ht}_seed_builder.py` (reescritos); `tools/{energy,max_ht}_reconciliation.py` (removidos) |
| domínio | `app/domain/values.py`, `app/domain/variables/models.py`, `app/domain/parameters/models.py` |
| validação | `app/validation/variable_seed_validator.py`, `app/validation/parameter_seed_validator.py`, `app/engine/registry_validator.py` |
| dados | `data/workbooks/` (5 workbooks aprovados, novos); `data/seed/*` (regenerados + `manifest.json`; `area_41` novo); `data/reference/*` (snapshots v2/v5 removidos) |
| testes | `tests/test_stage2_4_workbook_contract.py` e `tests/seed_ids.py` (novos); ajustes explícitos de `value_type` em fixtures; portes para identidade; retiradas listadas em R2-04 |
| outros | `requirements.txt` (openpyxl, pytest) |

## 8. Final Gate

STAGE_2.4_GATE: PASS
