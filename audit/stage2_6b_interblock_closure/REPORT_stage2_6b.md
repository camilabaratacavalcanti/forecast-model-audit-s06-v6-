# Etapa 2.6B — Fechamento do contrato interbloco

Branch `feature/area-41-block`.

| item | valor |
|---|---|
| baseline | `a126e02` (fim da 2.6, `READY_FOR_DECISION`), árvore limpa, 1441 testes passando |
| commit de implementação | `5e681dc` |
| commit de evidências | o seguinte a `5e681dc` (contém este relatório) |
| suíte ao final | **1475 passed**, 0 failed |

## 1. Resultado

| classificação | vínculos (definições) | linhas do workbook |
|---|---:|---:|
| VALID | **13** | 13 |
| SOURCE_BLOCK_NOT_LOADED (pendente de carregamento) | 16 | 19 |
| SOURCE_BLOCK_UNKNOWN | 0 | 0 |
| SOURCE_NOT_FOUND | 0 | 0 |
| CONTRACT_MISMATCH | 0 | 0 |
| INSTANCE_MISMATCH | 0 | 0 |
| AMBIGUOUS | 0 | 0 |
| CYCLE | 0 | 0 |
| **total** | **29** | **32** |

Em relação à 2.6 (31 vínculos, 12 válidos, 19 rejeitados):

- `energy.lth_meta` passou a VALID (D26-02).
- `production.fator_mpsa` e `production.fator_mrn` deixaram de declarar `fonte` e saíram da lista de vínculos (D26-03).
- Os 16 vínculos para blocos oficiais não carregados deixaram de ser erro e passaram a pendência explícita (D26-01).
  Nenhum foi convertido em válido.

Restam duas decisões do proprietário (D26B-01 e D26B-02, §10). Gate: **READY_FOR_DECISION**.

## 2. Workbooks e SHA-256

| bloco | arquivo | SHA-256 | situação |
|---|---|---|---|
| area_41 | `descritivo_das_variáveis_A41_v9.xlsx` | `36bbae13…603528` | inalterado |
| energy | `descritivo_das_variáveis_energy_v6.xlsx` | `cfc46031…8e1df8` | inalterado |
| max_ht | `descritivo_das_variáveis_MaxHT_v10.xlsx` | `3e40aab1…65b683b` | inalterado |
| production | `descritivo_das_variáveis_production_v10.xlsx` | `302cf18b92ac22c690b3add9bdd1ded0617bfa60636809696d010b8858d72487` | **novo oficial** |
| yield | `descritivo_das_variáveis_yield_v11.xlsx` | `639e8b98…df931` | inalterado |

- O production v10 foi copiado byte a byte do anexo para `data/workbooks/`.
- O production v9 (`3e3024e5…956a28`) continua em `data/workbooks/`. Nada foi sobrescrito nem apagado.
- Os hashes completos estão em `evidence/workbook_sha256.txt`.
- Nenhum workbook foi alterado por código. O builder só lê e confere o SHA-256.

## 3. Diff `production_v9 → production_v10` (célula a célula)

Há 37 células diferentes. O detalhe está em `evidence/production_v9_v10_diff.csv`.

| classificação | células | conteúdo |
|---|---:|---|
| D26-02 | 28 | `lth_meta` r37–r43 (L1..L7): `Type` parameter→variable; `value` 1050/1050/1100×5→vazio; `version` 1→vazio; `variable_type` vazio→`entrada_externa` |
| D26-03 | 2 | `fonte` de `fator_mpsa` (Q30) e `fator_mrn` (Q32): `forecast`→vazio |
| **não prevista** | **7** | coluna `OBS`, R36..R42 |

A alteração não prevista (D26B-01) não foi assumida como intencional. Os antigos `value` de `lth_meta` aparecem na
coluna livre `OBS`, **deslocados uma linha para cima**:

| linha | definição | v9 `value` | v10 `OBS` | alinhado |
|---|---|---:|---:|---|
| 36 | `lth` mensal | — | 1050 | não |
| 37 | lth_meta L1 | 1050 | 1050 | sim |
| 38 | lth_meta L2 | 1050 | **1100** | **não** |
| 39–42 | lth_meta L3–L6 | 1100 | 1100 | sim |
| 43 | lth_meta L7 | 1100 | **vazio** | **não** |

`OBS` é coluna opcional do reader: lida e nunca consumida por canonical, seeds, manifesto ou runtime. A alteração não
tem efeito nos seeds. Mesmo assim, o fechamento do diff fica pendente de decisão (§10).

Os valores de `unit`, `frequency`, `scope_*`, `value_type` e `status` de `lth_meta` não mudaram (`-`, anual,
linha/L1..L7, numerico, ativo).

## 4. D26-01 — taxonomia oficial

> **Historical note (D-TAX-01, posterior à Stage 3):** o registro canônico de blocos do repositório foi
> depois normalizado para **29 blocos**, na ordem das faixas de ID (`*_ID_RANGES`), incluindo
> `budget_vs_forecast`, e `monthly_ppt_assumptions` foi renomeado para `thickener_flocculant`
> (faixa 30000–30999). A lista de 28 nomes abaixo/acima registra o estado desta etapa, não o estado
> normativo atual. Ver `audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md`.

A taxonomia fica em `tools/workbook_seed/taxonomy.py` (`BLOCK_TAXONOMY`): 28 nomes na ordem recebida, comparados como
texto exato. É independente dos workbooks carregados e não substitui as faixas de ID por bloco
(`*_ID_RANGES`), que usam identificadores de código.

Resolução de `fonte` em três perguntas distintas:

1. **O nome pertence à taxonomia?** Se não, `INTERBLOCK_SOURCE_BLOCK_UNKNOWN`. É **erro** e o vínculo é rejeitado.
2. **O workbook do bloco está carregado?** Se não, `INTERBLOCK_SOURCE_BLOCK_NOT_LOADED`. É **pendência**:
   - não é vínculo válido nem erro de contrato;
   - `resolution_status=PENDING_LOAD`;
   - `severity=pending`.
3. **Há produtor compatível?** Se não, `SOURCE_NOT_FOUND`, `AMBIGUOUS`, `INSTANCE_MISMATCH` ou `CONTRACT_MISMATCH`.
   São **erros**.

Os `CYCLE` também são erros.

| `fonte` usada | na taxonomia | carregado | vínculos | classificação |
|---|---|---|---:|---|
| production | sim | sim | 11 | VALID |
| yield | sim | sim | 2 | VALID |
| forecast | sim | não | 2 | SOURCE_BLOCK_NOT_LOADED |
| maintenance | sim | não | 9 | SOURCE_BLOCK_NOT_LOADED |
| temperature_lp | sim | não | 3 | SOURCE_BLOCK_NOT_LOADED |
| area_04_13 | sim | não | 1 | SOURCE_BLOCK_NOT_LOADED |
| alumina | sim | não | 1 | SOURCE_BLOCK_NOT_LOADED |

Nenhum `fonte` atual está fora da taxonomia.

Blocos carregados diante da taxonomia:
- area_41, energy, production e yield: sim.
- **max_ht: não** (§7).

Seed `data/seed/interblock_links.json`:
- `links`: vínculos resolvidos, na forma canônica.
- `pending`: vínculos conhecidos, pendentes de carregamento, com `source_definition: null`. **Nenhum produtor é
  inventado.**
- `rejected`: vínculos rejeitados (hoje vazio).
- `taxonomy`: a lista oficial e a situação de cada bloco carregado.

`python -m tools.workbook_seed` termina com 1 só se houver `rejected`. Hoje termina com 0 e lista as pendências.
`require_valid()` falha só com erro. `require_resolved()` falha também com pendência.

## 5. D26-02 — `energy.lth_meta → production.lth_meta` (resolvida)

| dimensão | energy (consumidor, r13) | production (produtor, VAR12066) | resultado |
|---|---|---|---|
| natureza | variable | variable | OK (não há mais `variable × parameter`) |
| name | lth_meta | lth_meta | OK |
| unit | `-` | `-` | OK |
| value_type | numerico | numerico | OK |
| allowed_values | — | — | OK |
| declared_result_states | — | — | OK |
| frequência | anual | anual | OK |
| escopo | linha/L1_L7 | linha/L1_L7 (7 linhas) | OK |
| instâncias | L1..L7 | L1..L7 | OK |
| variable_type | entrada | entrada_externa | **não é dimensão do contrato** |

- O vínculo é VALID e a cadeia termina no produtor.
- A diferença `entrada` × `entrada_externa` é semântica interna de cada bloco. Não é comparada, e nenhuma exceção
  foi criada para ela (teste 06).
- `kind` continua comparado: um produtor parameter ainda dá `CONTRACT_MISMATCH`, dimensão `kind` (teste 06).
- O parâmetro `production.lth_meta` não existe mais nos seeds.

## 6. D26-03 — `fator_mpsa` / `fator_mrn` (resolvida)

| definição | Type / variable_type | unit | escopo | expressão | `fonte` | situação |
|---|---|---|---|---|---|---|
| fator_mpsa | variable / equation, calculado | `-` | diário linha/L1_L7 | `fator_mpsa_kg_t / 1000` | vazia | sem vínculo |
| fator_mrn | variable / equation, calculado | `-` | diário linha/L1_L7 | `fator_mrn_kg_t / 1000` | vazia | sem vínculo |
| fator_mpsa_kg_t | variable, entrada | kg/t | diário linha_grupo/L1_L7 | — | forecast | SOURCE_BLOCK_NOT_LOADED |
| fator_mrn_kg_t | variable, entrada | kg/t | diário linha_grupo/L1_L7 | — | forecast | SOURCE_BLOCK_NOT_LOADED |

Nenhum vínculo tem mais erro `consumer_context`. As definições calculadas têm um único produtor, a própria expressão.

## 7. `mx_ht` × `max_ht` (D26B-02, pendente)

| fonte da informação | nome |
|---|---|
| taxonomia oficial (D26-01) | `mx_ht` |
| arquivo | `descritivo_das_variáveis_MaxHT_v10.xlsx` |
| aba | `MaxHT` |
| título de bloco declarado no workbook | **nenhum** (nenhuma célula ou propriedade `title` declara o bloco) |
| identificador no código | `max_ht`: `BLOCKS`, `VARIABLE/PARAMETER/EQUATION_ID_RANGES` (13000–13999), `data/seed/max_ht/`, `data/id_ledger/max_ht.json`, `tools/max_ht_seed_builder.py` |
| `fonte` usando `mx_ht` | nenhum |
| `fonte` usando `max_ht` | nenhum |

**Há divergência** entre taxonomia e código/arquivo. Nenhum nome foi escolhido e nada foi normalizado:

- `PENDING_NAMING_DECISIONS["max_ht"]` registra a decisão. Serve só para diagnóstico: aparece em mensagem e no seed,
  nunca na resolução.
- `fonte=max_ht` resulta em SOURCE_BLOCK_UNKNOWN, porque o nome está fora da taxonomia.
- `fonte=mx_ht` resulta em SOURCE_BLOCK_NOT_LOADED, porque nenhum bloco está carregado com esse nome.
- As duas mensagens citam D26B-02. Nenhuma das duas resolve para as definições do bloco carregado `max_ht`
  (teste 17).

Hoje nenhum vínculo é afetado. A decisão é necessária antes que algum `fonte` aponte para esse bloco, ou antes de
renomear o bloco no código (seed, faixa de IDs e livro de IDs).

A taxonomia D26-01 também difere nominalmente da lista de faixas de ID (`acido` × `acid`, `custo_budget` ×
`budget_cost`, `lime_dia` × `lime` etc.). Isso não afeta vínculos (nenhum `fonte` usa esses nomes) e não foi alterado.

## 8. Cadeias e ciclos

| consumidor | cadeia | estado |
|---|---|---|
| area_41.lth | area_41.lth → yield.lth → production.lth | VALID |
| energy.{producao, pick_up, pick_up_total×2, lth, lth_total×2, lth_meta} | → production.* | VALID |
| max_ht.{lth, producao} | → production.* | VALID |
| production.yield | → yield.yield | VALID |
| yield.lth | → production.lth | VALID |
| 16 pendentes | → bloco não carregado | `PENDING_AT:<consumidor>` |

- Ciclos no builder: SCC sobre os vínculos somados às dependências intrabloco (equações e agregações). Resultado: 0.
- Ciclos na análise independente: sobre-aproximação em que todo nome citado numa expressão liga todas as definições
  desse nome. Resultado: 0 ciclos.
- production ↔ yield continua dependência mútua **de bloco**, sem ciclo de definição (`interblock_graph.csv`).
- Nenhum fallback temporal ou espacial entre blocos (teste 12). Esses fallbacks continuam só na resolução intrabloco
  (A019).

## 9. Identidade local e IDs

Identidade local:
- `production.lth` (VAR12031) e `yield.lth` (VAR11031) continuam definições distintas. O vínculo só declara a relação
  (teste 16).
- IDs de variável são únicos entre os cinco blocos.

**Livro de IDs (novo, `tools/workbook_seed/id_ledger.py`, `data/id_ledger/<bloco>.json`).**

O problema: a numeração sequencial da 2.4 renumeraria todas as definições do production posteriores a `lth_meta`
(cerca de 35 IDs, de VAR12033 em diante, além dos PARAM seguintes), porque `lth_meta` mudou de natureza.

O livro, gerado a partir do estado `a126e02` antes da troca para v10, fixa o ID de cada identidade
`(kind, name, frequency, scope_type, scope_value)`:
- identidade conhecida mantém o ID;
- identidade nova recebe o próximo número acima do maior já emitido (ativos e aposentados);
- identidade removida é aposentada e nunca é reutilizada.

Resultado conferido pela análise independente contra os manifestos de `a126e02`:
- **0 IDs renumerados** nos cinco blocos.
- PARAM12003 (`lth_meta` parameter) foi aposentado, com `retired_in` igual ao production v10.
- `lth_meta` variable recebeu VAR12066.
- IDs de equação (EQ12001..EQ12027) e de regras de agregação ficaram inalterados. Três equações (EQ12012 `lth`,
  EQ12014 `oee`, EQ12015 `oee_total`) passaram a referenciar VAR12066 no lugar de PARAM12003.

## 10. Decisões pendentes

| ID | assunto | o que se pede ao proprietário |
|---|---|---|
| **D26B-01** | production v10, coluna `OBS` R36..R42 | Confirmar se os números em `OBS` são intencionais. Hoje estão deslocados uma linha: `lth` mensal com 1050, L2 com 1100 em vez de 1050, L7 vazio. Se forem valores de referência de `lth_meta`, corrigir o alinhamento; se não forem, removê-los. Sem efeito em seeds. |
| **D26B-02** | `mx_ht` × `max_ht` | Definir o nome canônico do bloco. Adotar `mx_ht` exige renomear o identificador de código (seed, faixa de IDs, livro) numa etapa própria; adotar `max_ht` exige corrigir a taxonomia. |

Não são decisões pendentes:
- os 16 vínculos `SOURCE_BLOCK_NOT_LOADED`: é o estado normativo definido por D26-01 e passam a VALID quando os
  workbooks desses blocos forem carregados e validados;
- a propagação de valores, que pertence à Etapa 3.

## 11. Testes

`tests/test_stage2_6b_interblock_closure.py` tem 33 testes:

| # | exigido | teste |
|---|---|---|
| 1 | taxonomia + carregado | `test_01` |
| 2 | taxonomia + não carregado | `test_02` (forecast, maintenance, temperature_lp, area_04_13, alumina) + `test_official_fonte_names_classified_by_taxonomy` |
| 3 | fora da taxonomia | `test_03` (`forcast`, `bloco forecast`, `Forecast`, `forecast `, `max_ht`, `hydrate`) |
| 4 | produtor inexistente em workbook carregado | `test_04` |
| 5 | D26-02 variable → variable | `test_05` |
| 6 | entrada → entrada_externa sem falso positivo | `test_06` |
| 7, 8 | fator_mpsa / fator_mrn sem fonte | `test_07_08` |
| 9, 10 | *_kg_t → forecast | `test_09_10` |
| 11 | source_reference | `test_11` |
| 12 | sem fallback interbloco | `test_12` |
| 13 | instância incompatível | `test_13` |
| 14 | ambiguidade | `test_14` |
| 15 | ciclo | `test_15` |
| 16 | identidade local | `test_16` |
| 17 | mx_ht × max_ht | `test_17` |
| 18 | todos os vínculos reais | `test_18` (32 linhas, 29 vínculos, classe de cada um) |
| — | IDs | `test_no_historical_id_was_renumbered`, `test_ledger_retires_ids_and_never_reuses_them`, `test_ledger_assigns_new_identities_after_the_highest_issued_id`, `test_seed_does_not_invent_producers_for_unloaded_blocks`, `test_taxonomy_is_the_owner_list_exactly` |

**LEGACY_TEST_EXPECTATION.** São 17 testes antigos, atualizados porque a decisão contratual mudou. Nenhum foi
apagado, e cada um documenta a mudança no próprio código.

| teste | antes | agora |
|---|---|---|
| `test_production_v1::test_lth_meta_parameters_have_expected_values` → `test_lth_meta_is_an_external_input_variable` | lth_meta Parameter 1050/1050/1100×5 | Variable entrada_externa anual, 7 instâncias, sem parâmetro |
| `test_production_v1::test_oee_total_bd04_uses_distinct_per_line_values` | valores via `set_parameter_value` | via `set_variable_value`; fórmula e resultado iguais |
| `test_production_v1::test_lth_real_equation_applies_fator_ajuste_only_above_floor` | idem | idem (anual, `period_id="2026"`) |
| `test_production_v1::test_production_integration_chain_inputs_to_producao_planta` | lth_meta vinha dos ParameterInstances | mesmos valores injetados como variável anual |
| `test_stage2_4::test_t24_03_*` (4 testes) | lth_meta Parameter | mesma regra A019 por instância com lth_meta Variable; instância ausente continua erro |
| `test_stage2_4::test_t24_18_physical_types_are_preserved` | int de referência `lth_meta@L1` | `n_dias_ano`, `desaguamento_produtividade` |
| `test_stage2_6::test_03_*` (4 casos) | SOURCE_NOT_FOUND | SOURCE_BLOCK_UNKNOWN / SOURCE_BLOCK_NOT_LOADED |
| `test_stage2_6::test_10_cycle_*` | blocos sintéticos `a_block`… | blocos oficiais |
| `test_stage2_6::test_15_every_real_fonte_is_classified` | 34/31, 12/16/3 | 32/29, 13 VALID / 16 NOT_LOADED |
| `test_stage2_6::test_interblock_seed_is_the_builder_output` | 12 links / 19 rejected | 13 / 16 pending / 0 |
| `test_stage2_6::test_builder_main_fails_while_links_are_rejected` | build oficial com rejeição | rejeição sintética; e mais `test_builder_main_succeeds_with_only_pending_links` |

Resultado: suíte completa **1475 passed**. Antes eram 1441; entram 33 testes da 2.6B e 1 da 2.6. Detalhe em
`evidence/test_output.txt`.

## 12. Análise independente

`evidence/analysis_stage2_6b.py` **não importa nada de `tools/` nem de `app/`**. O script:

- lê os cinco workbooks com openpyxl;
- declara a taxonomia D26-01 por conta própria;
- reconstrói as definições por linha e classifica cada `fonte` pelas regras normativas;
- detecta ciclos por sobre-aproximação;
- compara o resultado com `data/seed/interblock_links.json`. A igualdade entre esse arquivo e o build é testada por
  `test_interblock_seed_is_the_builder_output`.

Resultado:
- **0 divergências** (29 vínculos, 32 linhas).
- 0 divergências de taxonomia.
- 0 IDs renumerados.
- Código de saída 0.

## 13. Arquivos alterados

Commit `5e681dc`:

| arquivo | alteração |
|---|---|
| `tools/workbook_seed/taxonomy.py` | **novo**: taxonomia D26-01 e decisão de nomenclatura pendente D26B-02 |
| `tools/workbook_seed/id_ledger.py` | **novo**: livro de IDs |
| `tools/workbook_seed/interblock.py` | classes SOURCE_BLOCK_UNKNOWN / SOURCE_BLOCK_NOT_LOADED, severidade `pending`, `require_resolved`, seções `pending` e `taxonomy` no seed; taxonomia deixa de vir de `VARIABLE_ID_RANGES` |
| `tools/workbook_seed/canonical.py` | parâmetro opcional `id_ledger` em `build_canonical_model`; sem livro, numeração sequencial como antes |
| `tools/workbook_seed/blocks.py` | production v10 (nome, versão, SHA); `ID_LEDGER_ROOT`, `write_id_ledger`; `build_block` lê o livro |
| `tools/workbook_seed/__main__.py` | grava o livro; relata pendências; sai com 1 só com rejeição |
| `data/workbooks/descritivo_das_variáveis_production_v10.xlsx` | **novo**, cópia byte a byte do anexo |
| `data/id_ledger/{area_41,energy,max_ht,production,yield}.json` | **novos** |
| `data/seed/production/{variables,parameters,equations,manifest}.json` | regenerados: lth_meta variable VAR12066, PARAM12003 fora, 3 equações com VAR12066, proveniência v10, `source_block` removido de fator_mpsa/fator_mrn |
| `data/seed/interblock_links.json` | reclassificado: 13 links, 16 pending, 0 rejected, seção taxonomy |
| `tests/test_stage2_6b_interblock_closure.py` | **novo** |
| `tests/test_production_v1.py`, `tests/test_stage2_4_workbook_contract.py`, `tests/test_stage2_6_interblock_contract.py` | LEGACY_TEST_EXPECTATION (§11) |

O commit de evidências adiciona apenas `audit/stage2_6b_interblock_closure/`.

Não alterados:
- `app/`, isto é, o runtime;
- os seeds de area_41, energy, max_ht e yield;
- os demais workbooks;
- os artefatos de auditoria das etapas anteriores;
- as regras A019, D24-11 e D24-12.

Não foram implementados propagação de valores, execução de cadeia nem materialização de valores (Etapa 3). Não há
alias, case folding, remoção de prefixo nem normalização de nomes. Nenhum PR foi criado.

## 14. Evidências

| arquivo | conteúdo |
|---|---|
| `contract_decisions.csv` | D26-01, D26-02, D26-03, D26B-01..04 com status |
| `interblock_links.csv` | 32 linhas: classificação, estado (RESOLVED / PENDING_LOAD / REJECTED), taxonomia, carregamento, cadeia, concordância com o builder |
| `contract_validation.csv` | dimensão a dimensão por vínculo; `variable_type` listado como informativo |
| `interblock_graph.csv` | arestas por definição e por bloco |
| `evidence/analysis_stage2_6b.py` | análise independente |
| `evidence/production_v9_v10_diff.csv` | as 37 células do diff, classificadas |
| `evidence/workbook_sha256.txt` | SHA-256 dos cinco oficiais + production v9 |
| `evidence/validation_results.json` | contagens, taxonomia, mx_ht/max_ht, alinhamento de OBS, estabilidade de IDs, divergências |
| `evidence/test_output.txt` | testes da 2.6B, suíte completa, saída do builder e da análise |

## 15. Push

Os commits `5e681dc` e o de evidências são enviados com `git push -u origin feature/area-41-block`. O que foi
alterado está descrito na §13.

STAGE_2.6B_GATE: READY_FOR_DECISION
