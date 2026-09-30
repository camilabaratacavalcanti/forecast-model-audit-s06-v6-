# Etapa 2.6C — Fechamento final do contrato interbloco

## 1. Baseline e git

| item | valor |
|---|---|
| branch / worktree | `feature/area-41-block`, worktree único `/home/user/forecast-model-audit-s06-v6-` |
| baseline | `eceffd4` (evidências 2.6B) sobre `5e681dc` (implementação 2.6B) |
| estado inicial | árvore limpa (`git status` vazio); suíte: 1475 testes passando |
| commit de implementação | `68cb5a1` |
| commit de evidências | o seguinte a `68cb5a1` (contém este relatório) |
| suíte ao final | **1496 passed**, 0 failed |

Nenhum artefato das etapas 2.5, 2.5B, 2.6 ou 2.6B foi modificado. Nenhum PR foi criado.

## 2. Resultado

| verificação | resultado |
|---|---|
| D26B-01 (production v11, OBS) | **fechada**: 3 células alteradas, todas em OBS, alinhadas |
| D26B-02 (nome do bloco) | **fechada**: `max_ht` em taxonomia, código, seeds e manifestos; `mx_ht` rejeitado |
| D26-01 (taxonomia) | implementada, 28 blocos, 8 classes distintas |
| D26-02 (`lth_meta`) | VALID, variable → variable |
| D26-03 (`fator_mpsa`/`fator_mrn`) | VALID: calculadas sem fonte; `*_kg_t` → forecast |
| livro de IDs | auditado: 530 preservados, 1 novo, 1 aposentado, 0 renumerados, 0 órfãos; determinístico e independente da ordem |
| vínculos | 29 (32 linhas): **13 VALID**, **16 SOURCE_BLOCK_NOT_LOADED**, 0 nas demais classes |
| auditoria independente | **0 divergências**, 0 falhas |
| runtime (`app/`) | inalterado |

## 3. Workbooks oficiais e SHA-256

| bloco | arquivo | SHA-256 |
|---|---|---|
| area_41 | `descritivo_das_variáveis_A41_v9.xlsx` | `36bbae135285ad9b3b88d21ef94e2bc9c92f2ef74736412b66bc62de4dcf3f50` |
| energy | `descritivo_das_variáveis_energy_v6.xlsx` | `cfc46031fc2f3f375b87ebbba58676d23ad92f3ee43fb81b353fe5a8247e1df8` |
| max_ht | `descritivo_das_variáveis_MaxHT_v10.xlsx` | `3e40aab12ec0ec07918c5e358145b09f138663f635ca9e7fc0990d1b765b683b` |
| production | `descritivo_das_variáveis_production_v11.xlsx` | **`d946dfd522c8cbb301c0c63caa3c62263b74a849e043d7b2f4bcb0bdb262c922`** |
| yield | `descritivo_das_variáveis_yield_v11.xlsx` | `639e8b980f19bc20429cf9763157ac1828d9067bdbabea3bf3db0badbc2df931` |

- O production v11 foi copiado byte a byte do anexo para `data/workbooks/`. O SHA-256 da cópia é igual ao do anexo.
- Os production v10 (`302cf18b…d72487`) e v9 continuam em `data/workbooks/`. As evidências da 2.6B continuam
  referindo o v10.
- Nenhum workbook foi editado, reformatado ou corrigido por código.

## 4. D26B-01 — diff production v10 → v11 (célula a célula)

`evidence/workbook_diff_v10_v11.csv`. As dimensões da aba (302 × 18) e os nomes das abas são iguais.

| célula | linha / definição | coluna | v10 | v11 | classificação |
|---|---|---|---:|---:|---|
| R36 | `lth` mensal | OBS | 1050 | vazio | D26B-01 |
| R38 | `lth_meta` L2 | OBS | 1100 | 1050 | D26B-01 |
| R43 | `lth_meta` L7 | OBS | vazio | 1100 | D26B-01 |

Alinhamento resultante, conferido contra os antigos `value` de `lth_meta` no v9:

| linha | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v9 `value` | 1050 | 1050 | 1100 | 1100 | 1100 | 1100 | 1100 |
| v11 `OBS` | 1050 | 1050 | 1100 | 1100 | 1100 | 1100 | 1100 |

A linha 36 (`lth` mensal) voltou a ter OBS vazio.

- **Nenhuma** alteração em Type, name, description, unit, value, version, variable_type, frequency, scope_type,
  scope_value, source_reference, status, value_type, allowed_values, declared_result_states, expression ou fonte.
- Contagens v10 = v11:

  | linhas | definições de variável | definições de parâmetro | linhas de parâmetro | linhas com expressão | linhas com fonte |
  |---:|---:|---:|---:|---:|---:|
  | 88 | 66 | 4 | 10 | 55 | 11 |

- Seeds regenerados: a única diferença é a proveniência (nome e SHA do workbook). IDs, equações e regras não mudaram.
- `OBS` continua fora de seed e runtime (arquitetura atual; teste `test_01b`). O workbook-fonte está correto.

**D26B-01: fechada.**

## 5. D26B-02 — `max_ht` (fechada)

Decisão do proprietário: `max_ht` é o nome canônico em taxonomia, código, `fonte`, seeds e manifestos. `mx_ht` não é
oficial nem sinônimo.

Artefatos ativos corrigidos:
- **`tools/workbook_seed/taxonomy.py`:**
  - `mx_ht` foi trocado por `max_ht`;
  - o registro de decisão de nomenclatura pendente foi removido;
  - o docstring registra que `mx_ht` não é oficial.
- **`tools/workbook_seed/interblock.py`:** foram removidas as mensagens de diagnóstico da nomenclatura pendente. Não
  há alias.
- **`data/seed/interblock_links.json`:** a seção `taxonomy` agora lista `max_ht`, e todos os blocos carregados têm
  `in_taxonomy: true`.

Ocorrências no repositório (`evidence/max_ht_occurrences.csv`):

| termo | categoria | classificação |
|---|---|---|
| `mx_ht` | auditoria 2.6B (5 arquivos) | histórico: decisão pendente à época. **Mantido**, sem reescrever a história |
| `mx_ht` | `tools/workbook_seed/taxonomy.py` (1) | docstring normativo que declara `mx_ht` não oficial |
| `mx_ht` | testes 2.6B / 2.6C | casos de rejeição (`fonte=mx_ht` → desconhecido) |
| `mx_ht` | análise 2.6C | verificação de ausência |
| `mx_ht` | seeds, manifestos, livro de IDs, `app/`, workbooks | **0** |
| `max_ht` | código ativo, testes, seeds, manifestos, livro | nome canônico, correto |
| `max_ht` | auditorias históricas | mantido |

O nome também está coerente no workbook: arquivo `…_MaxHT_v10.xlsx`, aba `MaxHT`, nenhum título de bloco declarado.
Esse arquivo não foi alterado, e o nome canônico do bloco é o identificador `max_ht`. Nenhum `fonte` atual usa
`max_ht` ou `mx_ht`.

Comportamento testado:
- `fonte=max_ht` resolve para `max_ht.lth` (test_04).
- `fonte=mx_ht` resulta em `INTERBLOCK_SOURCE_BLOCK_UNKNOWN` (test_05).

## 6. D26-01 — taxonomia (28 blocos)

> **Historical note (D-TAX-01, posterior à Stage 3):** o registro canônico de blocos do repositório foi
> depois normalizado para **29 blocos**, na ordem das faixas de ID (`*_ID_RANGES`), incluindo
> `budget_vs_forecast`, e `monthly_ppt_assumptions` foi renomeado para `thickener_flocculant`
> (faixa 30000–30999). A lista de 28 nomes abaixo/acima registra o estado desta etapa, não o estado
> normativo atual. Ver `audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md`.

maintenance, area_04_13, forecast_volume, acido, yield, energy, meta_volume_cheio, custo_budget, production, boilers,
controle_espaco_vazio_meta, custo_forecast_bdgt, **max_ht**, volume, lime_dia, custo_forecast_real, alumina, soda,
floculante_hidrato_2026, budget, temperature_lp, fator_residuo, floculante_lama_dia, forecast, area_41,
vazao_condensado, premissas_ppt_mensal, shared.

| classe | severidade | significado |
|---|---|---|
| VALID | — | bloco conhecido e carregado, produtor compatível |
| SOURCE_BLOCK_NOT_LOADED | pendência | bloco conhecido, workbook não carregado; nenhum produtor inventado |
| SOURCE_BLOCK_UNKNOWN | erro | nome fora da taxonomia |
| SOURCE_NOT_FOUND | erro | bloco carregado sem produtor |
| CONTRACT_MISMATCH | erro | produtor incompatível |
| AMBIGUOUS | erro | produtor não determinístico |
| INSTANCE_MISMATCH | erro | instância do consumidor ausente no produtor |
| CYCLE | erro | ciclo interbloco/intrabloco |

Os cinco blocos carregados pertencem à taxonomia. Os nomes de `fonte` usados são production e yield (carregados) e
forecast, maintenance, temperature_lp, area_04_13 e alumina (oficiais, não carregados).

## 7. Vínculos (recalculados)

| consumidor (linhas) | fonte | classificação | produtor | erros / pendências |
|---|---|---|---|---|
| area_41.lth (9) | yield | VALID | yield.lth [diário linha/L1_L7] → production.lth | — |
| area_41.hes (25–28) | maintenance | SOURCE_BLOCK_NOT_LOADED | — | pendente de carregamento |
| energy.producao (3) | production | VALID | production.producao [diário linha] | — |
| energy.pick_up (7) | production | VALID | production.pick_up [diário linha] | — |
| energy.pick_up_total (8) | production | VALID | production.pick_up_total [diário linha_grupo] | — |
| energy.pick_up_total (9) | production | VALID | production.pick_up_total [mensal linha_grupo] | — |
| energy.lth (10) | production | VALID | production.lth [diário linha] | — |
| energy.lth_total (11) | production | VALID | production.lth_total [diário linha_grupo] | — |
| energy.lth_total (12) | production | VALID | production.lth_total [mensal linha_grupo] | — |
| energy.lth_meta (13) | production | VALID | production.lth_meta VAR12066 [anual linha] | — |
| energy.temperatura_lp (14, 15) | temperature_lp | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| energy.temperatura_lp_media (16) | temperature_lp | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| energy.evaporado_total_evaporacao (37) | area_04_13 | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| max_ht.alimentação_evap (5) | alumina | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| max_ht.lth (68) | production | VALID | production.lth [diário linha] | — |
| max_ht.producao (98) | production | VALID | production.producao [diário linha] | — |
| production.fator_mpsa_kg_t (31) | forecast | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| production.fator_mrn_kg_t (33) | forecast | SOURCE_BLOCK_NOT_LOADED | — | pendente |
| production.reducao_lth_* (79–82), tempo_* (83–86) | maintenance | SOURCE_BLOCK_NOT_LOADED (8) | — | pendente |
| production.yield (87) | yield | VALID | yield.yield [diário linha] | — |
| yield.lth (32) | production | VALID | production.lth [diário linha] | — |

| classificação | vínculos | linhas |
|---|---:|---:|
| VALID | **13** | 13 |
| SOURCE_BLOCK_NOT_LOADED | **16** | 19 |
| SOURCE_BLOCK_UNKNOWN | 0 | 0 |
| SOURCE_NOT_FOUND | 0 | 0 |
| CONTRACT_MISMATCH | 0 | 0 |
| INSTANCE_MISMATCH | 0 | 0 |
| AMBIGUOUS | 0 | 0 |
| CYCLE | 0 | 0 |

- Todos os 13 vínculos válidos têm `chain_status` VALID.
- Ciclos: 0, tanto no builder (SCC de vínculos com equações e agregações) quanto na análise independente
  (sobre-aproximação por nome).
- Nenhum fallback temporal ou espacial entre blocos.
- Os detalhes estão em `interblock_links.csv`, `contract_validation.csv` e `interblock_graph.csv`.

## 8. D26-02 e D26-03

D26-02, `energy.lth_meta` (variable entrada, anual, linha/L1_L7) ← `production.lth_meta` (variable
entrada_externa, anual, linha/L1_L7, VAR12066):
- kind, unit (`-`), value_type (numerico), allowed_values, declared_result_states, frequência, escopo e instâncias
  (L1..L7) são iguais. O vínculo é **VALID**.
- `variable_type` (`entrada` × `entrada_externa`) não é dimensão do contrato e não gera erro.
- `kind` continua verificado.
- Não existe mais `lth_meta` parameter.

D26-03, no production v11:

| definição | Type / variable_type | expressão | fonte | vínculo |
|---|---|---|---|---|
| fator_mpsa | variable / equation, calculado | `fator_mpsa_kg_t / 1000` | vazia | nenhum |
| fator_mrn | variable / equation, calculado | `fator_mrn_kg_t / 1000` | vazia | nenhum |
| fator_mpsa_kg_t | variable, entrada | — | forecast | SOURCE_BLOCK_NOT_LOADED |
| fator_mrn_kg_t | variable, entrada | — | forecast | SOURCE_BLOCK_NOT_LOADED |

Nenhuma definição tem simultaneamente expressão e `fonte`.

## 9. Livro de IDs — auditoria

O `id_ledger_audit.csv` tem 532 identidades, comparadas contra os manifestos de `a126e02` (antes do livro) e
`eceffd4` (2.6B).

| item | resultado |
|---|---|
| 10.1 estabilidade | duas execuções consecutivas de `python -m tools.workbook_seed`: 31 arquivos (seeds + livro) byte a byte idênticos (`evidence/determinism_check.txt`) |
| 10.2 preservação | **530 PRESERVED**, 0 RENUMBERED; nenhuma identidade existente recebeu outro ID; os IDs atuais são iguais aos de `eceffd4` em todos os blocos |
| 10.3 novo ID | `production.lth_meta` (variable) = **VAR12066**; **PARAM12003 aposentado** (`retired_in`: production v10) |
| 10.4 dependências | as equações que referenciavam PARAM12003 em `a126e02` (EQ12012 `lth`, EQ12014 `oee`, EQ12015 `oee_total`) referenciam VAR12066 hoje; PARAM12003 não aparece em nenhum seed; 0 referências órfãs em equações, agregações e vínculos |
| 10.5 ordem | build com a ordem dos blocos invertida gera arquivos idênticos |
| 10.6 determinismo | builds isolados com `PYTHONHASHSEED` 0, 987654321 e 12345 (ordem direta e invertida) são idênticos entre si e aos versionados; sem timestamp, sem hash aleatório, sem estado fora do repositório |
| 10.7 aposentados | continuam registrados em `retired`, que é copiado de um build para o seguinte; nenhum aparece entre IDs ativos ou em seeds |

Regra contratual registrada em `tools/workbook_seed/id_ledger.py`:
1. Identidade conhecida mantém o ID.
2. Identidade nova recebe o próximo número acima do maior já emitido para a mesma natureza (ativo ou aposentado).
3. Identidade removida é aposentada de forma **permanente** e **nunca reutilizada**.
4. O livro depende só do livro versionado e do workbook.

## 10. Testes

`tests/test_stage2_6c_interblock_final.py` tem 20 testes:

| # | exigido | teste |
|---|---|---|
| 1 | v10 → v11 só com alterações esperadas | `test_01`, `test_01b` (OBS fora do seed) |
| 2 | taxonomia contém `max_ht` | `test_02` |
| 3 | taxonomia não contém `mx_ht` | `test_03` (inclui todos os JSON de `data/`) |
| 4 | `fonte=max_ht` válido | `test_04` |
| 5 | `fonte=mx_ht` rejeitado | `test_05` |
| 6 | lth_meta variable → variable | `test_06` |
| 7 | entrada → entrada_externa | `test_07` |
| 8, 9 | fator_mpsa / fator_mrn sem fonte | `test_08_09` |
| 10, 11 | *_kg_t → forecast | `test_10_11` |
| 12 | IDs estáveis | `test_12` (contra `a126e02` e `eceffd4`) |
| 13 | aposentados não reutilizados | `test_13` |
| 14 | build repetido idêntico | `test_14` (4 builds isolados; hash seeds e ordem) |
| 15 | nenhum ciclo | `test_15` |
| 16 | nenhum vínculo órfão | `test_16` |
| 17 | análise independente coincide | `test_17` (executa `analysis_stage2_6c.py --no-write`) |

**LEGACY_TEST_EXPECTATION** (decisão D26B-02). Nenhum teste foi removido.

| teste | antes | agora |
|---|---|---|
| `test_stage2_6b::D26_01_TAXONOMY` / `test_taxonomy_is_the_owner_list_exactly` | lista com `mx_ht` | lista com `max_ht` |
| `test_stage2_6b::test_03_block_outside_taxonomy_is_an_error[max_ht]` | `max_ht` desconhecido | caso substituído por `mx_ht` |
| `test_stage2_6b::test_17_mx_ht_versus_max_ht_is_a_recorded_pending_decision` | divergência pendente | `test_17_max_ht_is_the_canonical_block_name` + `test_17b_fonte_max_ht_resolves_and_mx_ht_is_unknown` |

Suíte completa: **1496 passed**. Antes eram 1475; entram 20 testes da 2.6C e 1 da 2.6B.

## 11. Auditoria independente

`evidence/analysis_stage2_6c.py` **não importa `tools/` nem `app/`**. O script:
- lê os workbooks com openpyxl e declara a taxonomia final por conta própria;
- classifica todos os `fonte`;
- verifica D26-02, D26-03, `max_ht` e o diff v10 → v11 (incluindo as colunas de contrato e as contagens);
- audita o livro de IDs e as referências órfãs;
- compara com o seed do builder.

Resultado: **0 divergências, 0 falhas**, código de saída 0.

## 12. Arquivos alterados

Commit `68cb5a1`:

| arquivo | alteração |
|---|---|
| `data/workbooks/descritivo_das_variáveis_production_v11.xlsx` | **novo**, cópia byte a byte |
| `tools/workbook_seed/blocks.py` | production v11 (nome, versão, SHA); `build_all(order=...)` para auditoria de ordem |
| `tools/workbook_seed/taxonomy.py` | `max_ht` no lugar de `mx_ht`; remoção da decisão de nomenclatura pendente |
| `tools/workbook_seed/interblock.py` | remoção do diagnóstico de nomenclatura pendente (sem alias) |
| `tools/workbook_seed/id_ledger.py` | docstring: aposentadoria permanente e determinismo |
| `data/seed/production/*.json` | proveniência v11 |
| `data/seed/interblock_links.json` | proveniência v11; taxonomia com `max_ht` |
| `tests/test_stage2_6b_interblock_closure.py` | LEGACY_TEST_EXPECTATION (§10) |
| `tests/test_stage2_6c_interblock_final.py` | **novo** |

O commit de evidências adiciona apenas `audit/stage2_6c_interblock_final/`.

Não alterados:
- `app/`: runtime, execução de equações, propagação e materialização;
- `data/id_ledger/*.json`, que continuam idênticos à 2.6B;
- os seeds de area_41, energy, max_ht e yield;
- os demais workbooks;
- as evidências das etapas anteriores.

## 13. Decisões pendentes

**Nenhuma.**

Os 16 vínculos `SOURCE_BLOCK_NOT_LOADED` não são decisão do proprietário nem de arquitetura. São o estado normativo de
D26-01 (bloco oficial ainda não carregado): ficam em `pending` no seed, sem produtor fictício, e são resolvidos quando
os workbooks de maintenance, temperature_lp, area_04_13, alumina e forecast forem incorporados. A propagação de
valores entre blocos pertence à Etapa 3 e não foi iniciada.

## 14. Evidências

| arquivo | conteúdo |
|---|---|
| `contract_decisions.csv` | D26-01..03, D26B-01..04 com status |
| `interblock_links.csv` | 32 linhas: fonte, classificação, produtor, erros/pendências, cadeia, concordância |
| `contract_validation.csv` | dimensão a dimensão por vínculo |
| `interblock_graph.csv` | arestas por definição e por bloco |
| `id_ledger_audit.csv` | 532 identidades: IDs em `a126e02`, `eceffd4` e atuais, status |
| `evidence/analysis_stage2_6c.py` | análise independente |
| `evidence/determinism_check.py` / `.txt` | determinismo e independência de ordem |
| `evidence/workbook_diff_v10_v11.csv` | diff célula a célula |
| `evidence/workbook_sha256.txt` | SHA-256 dos cinco oficiais + production v10 e v9 |
| `evidence/max_ht_occurrences.csv` | ocorrências de `mx_ht` e `max_ht`, classificadas |
| `evidence/validation_results.json` | resumo completo |
| `evidence/test_output.txt` | testes da 2.6C, suíte completa, builder, análise, determinismo |

## 15. Push

Os commits `68cb5a1` e o de evidências são enviados com `git push -u origin feature/area-41-block`. O que foi
alterado está descrito na §12.

STAGE_2.6C_GATE: PASS
