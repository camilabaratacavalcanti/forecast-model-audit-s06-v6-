# Stage 4C — contrato de decisão: governança de baseline (guardas históricas e re-baseline)

Estado: **Fase 1 concluída** (inventário e classificação completos ANTES de qualquer edição de teste).
Branch: `feature/stage-4c-baseline-governance` (a partir de `f573c1b`, fechamento da 4B). Nada foi enviado ao remoto.

Superfície de produção congelada: `app/`, `data/**` (seeds, workbooks, ledger, `interblock_links.json`) e `tools/**`
não são alterados na 4C. Os anexos (energy v9, MaxHT v13) **não entram no repositório**: só são usados no clone
temporário do ensaio R1 (Fase 3).

## 0. Baseline da Fase 0 (recalculado nesta execução)

| item | valor |
|---|---|
| HEAD de partida | `f573c1b6cb9365b4669ec6af688f0ada36ad438d` (fechamento 4B) |
| `origin/main` | `0a924e66cfd0774a13e46a332b460b770283a554` (fechamento 4A); `git diff --stat origin/main -- app data tools` = vazio |
| suíte completa | **2004 passed, 1 failed** (556 s). Única falha: `tests/test_stage4a_closure.py::test_production_surface_and_stage_3_closure_untouched` (= F4B-06) |
| anexo energy v9 | `731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2` |
| anexo MaxHT v13 | `c9818920b3994ae6aaeef5f237e59dd94d8e1b8647f0bf64426fb5f3d9f0aa98` |
| BlockSpec vigente | energy v6 `cfc46031…`, max_ht v10 `3e40aab1…`, area_41 v9 `36bbae13…`, production v11 `d946dfd5…`, yield v11 `639e8b98…` |

### 0.1 Fatos `[ref]` reconfirmados (recalculados)

| `[ref]` do prompt | recalculado | situação |
|---|---|---|
| F4B-06: guardas 4A/4B viram H em `d2847ab..0a924e6` e `0a924e6..f573c1b` | `git diff --stat d2847ab 0a924e6 -- app data tools` = vazio; fora de `audit/stage4a/`/`tests/test_stage4a_*` só `PLATFORM_PENDING_ITEMS.md`. `git diff 0a924e6 f573c1b`: idem para a 4B | **confere** |
| ensaio R1 antes do re-baseline: 60 falhas + 19 erros em 25 arquivos | **59 failed + 19 errors = 78 itens (69 funções) em 21 arquivos**; 1927 passed (total 2005 = Fase 0) | **diverge → F4C-01** |
| seeds R1: energy +1 variável/+1 equação (VAR18053 nova); max_ht +1/+1, VAR13001–VAR13006 aposentadas, VAR13117–VAR13123 novas | energy 52→53 variáveis, 24→25 equações; max_ht 116→117 variáveis, 29→30 equações (o detalhe por ID sai do DIFF_REPORT da Fase 3) | confere nas cardinalidades |
| vínculos "40 → ver relatório" | gerador no clone: **29 declarados, 13 válidos, 16 pendentes, 0 rejeitados** (mesmos números de hoje) | **diverge → F4C-02** |
| 3.4D: intervalo `043fe9c..8095011` sem mudança em app/data/tools | `git diff --stat 043fe9c 8095011 -- app data tools` = vazio | confere |
| 3.4B: candidato da evidência | `differential_summary.json`: reference `7877551`, candidate `95e7ade`, invariante `PASS`; `git diff 95e7ade 4d54804 -- app data tools` = vazio | confere |
| D-TAX-02 só tocou comentários de 2 validadores | `git diff --name-only d8b5d55 d2847ab -- app tools data` = os 2 validadores | confere |

## 1. Classes

| classe | significado | tratamento |
|---|---|---|
| H | fechamento histórico | intervalo fixo `baseline_X..fechamento_X`; nunca lê HEAD |
| E | imutabilidade de evidência histórica | arquivo do HEAD x commit de fechamento da stage (+ sha256 no registro B0) |
| R | regressão viva | referência vem do registro (`current`); harness recebe só parâmetro de diretório (default idêntico) |
| S | invariante semântico | IDs não renumerados; aposentados no `retired` do ledger; sem reuso; faixas inalteradas; append-only |
| W | árvore intacta pela execução | status antes/depois |
| C | contrato de conteúdo atual | **não alterado na 4C**; pré-lista da 5A |

## 2. Inventário e rastreabilidade

Gerado por `audit/stage4c/inventory/build_inventory.py` (`guard_inventory.json`). As linhas são as da definição
do teste no commit 4c.1, antes de qualquer conversão. **Total: 121 testes**:

| classe | testes |
|---|---|
| H | 21 |
| E | 35 |
| R | 17 |
| S | 8 |
| W | 2 |
| C | 38 |

Os 78 itens que falham no ensaio R1 (69 funções) estão todos na tabela.

Critério de inclusão: o teste
- cita hash de commit;
- compara HEAD ou a árvore com um commit;
- compara execução viva com evidência versionada ou expectativas JSON;
- congela cardinalidades, IDs, vínculos ou SHAs e falha no R1;
- ou verifica a árvore intacta.

Testes de conteúdo que **não** falham no R1 e não citam commit nem evidência continuam fora da tabela. São C pela mesma regra e só entram na pré-lista da 5A se o ensaio os quebrar.

| teste | arquivo:linha | classe | referência atual | referência nova | justificativa |
|---|---|---|---|---|---|
| `test_no_historical_id_was_renumbered` | `tests/test_stage2_6b_interblock_closure.py:410` | S | `git show a126e02:manifest` x seed do HEAD; exige removed == added == ∅ (exceto production) | S: chaves comuns com o mesmo ID; removidas => ID no `retired` do ledger; novas => ID nunca emitido; o literal de production (lth_meta) vira H no intervalo a126e02..eceffd4 | congela o conjunto de entidades desde a 2.6; a 5A aposenta VAR13001–13006 e cria VAR18053/VAR13117–13123 legitimamente. O invariante real (sem renumeração, sem reuso) continua ao vivo |
| `test_12_ids_are_stable_against_baselines` | `tests/test_stage2_6c_interblock_final.py:204` | S | `git show a126e02|eceffd4:manifest` x HEAD; para eceffd4 exige before == after | S ao vivo (mesmas regras); o `before == after` de eceffd4 vira H no intervalo eceffd4..7877551 | idem; o congelamento total era a afirmação do fechamento 2.6C |
| `test_13_retired_ids_are_recorded_and_never_reused` | `tests/test_stage2_6c_interblock_final.py:216` | S | ledger do HEAD | sem alteração | já é o invariante S (retired listado, sem reuso) |
| `test_ledger_retires_ids_and_never_reuses_them` | `tests/test_stage2_6b_interblock_closure.py:432` | S | ledger do HEAD + build | sem alteração | invariante S; passa no ensaio R1 |
| `test_17_max_ht_is_the_canonical_block_name` | `tests/test_stage2_6b_interblock_closure.py:300` | C | literal `descritivo_das_variáveis_MaxHT_v10.xlsx` | sem alteração (pré-lista 5A) | nome do workbook vigente é conteúdo atual |
| `test_18_all_real_links_of_the_five_workbooks` | `tests/test_stage2_6b_interblock_closure.py:379` | C | conjunto EXPECTED de vínculos (32 linhas fonte) | sem alteração (pré-lista 5A) | vínculos declarados nos workbooks vigentes |
| `test_17_independent_analysis_matches_the_builder` | `tests/test_stage2_6c_interblock_final.py:314` | C | análise 2.6C ao vivo + literal {SOURCE_BLOCK_NOT_LOADED: 16, VALID: 13} | sem alteração (pré-lista 5A) | contagens de vínculos do conteúdo vigente |
| `test_14_repeated_builds_are_byte_identical_and_order_independent` | `tests/test_stage2_6c_interblock_final.py:260` | S | build isolado x seeds do HEAD | sem alteração | determinismo do gerador; independe do conteúdo |
| `test_15_every_real_fonte_is_classified` | `tests/test_stage2_6_interblock_contract.py:594` | C | conjunto literal de vínculos reais | sem alteração (pré-lista 5A) | conteúdo dos workbooks |
| `test_t24_02_each_block_builder_consumes_its_approved_workbook` | `tests/test_stage2_4_workbook_contract.py:254` | C | linhas por workbook (56/120…) | sem alteração (pré-lista 5A) | cardinalidade do workbook vigente |
| `test_t24_02_total_rows_and_equations_match_stage_2_3` | `tests/test_stage2_4_workbook_contract.py:267` | C | total 572 linhas | sem alteração (pré-lista 5A) | cardinalidade do workbook vigente |
| `test_t24_06_max_ht_v9_ignores_trailing_empty_rows` | `tests/test_stage2_4_workbook_contract.py:559` | C | 120 linhas do MaxHT | sem alteração (pré-lista 5A) | cardinalidade do workbook vigente |
| `test_sum_factors_follow_the_approved_workbook_units` | `tests/test_aggregation_dimensions.py:171` | C | unidades por fator de integração | sem alteração (pré-lista 5A) | unidades do workbook vigente |
| `test_entity_counts_match_the_workbook` | `tests/test_energy_seed_contract.py:104` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_equation_and_aggregation_counts` | `tests/test_energy_seed_contract.py:115` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_all_ids_are_inside_the_energy_range_and_unique` | `tests/test_energy_seed_contract.py:125` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_energy_ids_do_not_collide_with_other_blocks` | `tests/test_energy_seed_contract.py:150` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_variable_frequency_distribution` | `tests/test_energy_seed_contract.py:239` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_variable_type_distribution` | `tests/test_energy_seed_contract.py:250` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_scope_distribution` | `tests/test_energy_seed_contract.py:265` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_variable_instances_are_materialized_by_the_real_resolver` | `tests/test_energy_seed_contract.py:340` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_explicit_scoped_references_are_extracted` | `tests/test_energy_seed_contract.py:456` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_energia_bayer_and_energia_media_frct_bind_by_id_not_name` | `tests/test_energy_seed_contract.py:489` | C | literais do seed energy v6 | sem alteração (pré-lista 5A) | contrato do conteúdo energy vigente |
| `test_the_23_daily_equations_all_execute` | `tests/test_energy_runtime_contract.py:381` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_per_line_results` | `tests/test_energy_runtime_contract.py:411` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_plant_group_results` | `tests/test_energy_runtime_contract.py:422` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_subgroup_specific_evaporation` | `tests/test_energy_runtime_contract.py:443` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_both_branches_of_the_conditional_are_exercised` | `tests/test_energy_runtime_contract.py:457` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_energia_bayer_equals_digestion_plus_evaporation` | `tests/test_energy_runtime_contract.py:491` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_no_calculated_variable_was_seeded_by_hand` | `tests/test_energy_runtime_contract.py:504` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_perturbing_one_line_propagates_to_the_plant` | `tests/test_energy_runtime_contract.py:544` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_perturbing_an_unrelated_line_does_not_change_a_subgroup` | `tests/test_energy_runtime_contract.py:592` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_cross_block_inputs_are_declared_as_inputs_with_a_source` | `tests/test_energy_runtime_contract.py:635` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_daily_to_monthly_chain_feeds_eq18020` | `tests/test_energy_runtime_contract.py:760` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_eq18020_cannot_be_satisfied_by_daily_values_alone` | `tests/test_energy_runtime_contract.py:902` | C | fixture de entradas do energy v6 | sem alteração (pré-lista 5A) | execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture) |
| `test_entity_counts` | `tests/test_max_ht_runtime_contract.py:67` | C | literais do seed max_ht v10 | sem alteração (pré-lista 5A) | contrato do conteúdo max_ht vigente |
| `test_all_math_equations_parse_successfully` | `tests/test_max_ht_runtime_contract.py:136` | C | literais do seed max_ht v10 | sem alteração (pré-lista 5A) | contrato do conteúdo max_ht vigente |
| `test_full_seed_root_loads_without_errors` | `tests/test_max_ht_runtime_contract.py:213` | C | literais do seed max_ht v10 | sem alteração (pré-lista 5A) | contrato do conteúdo max_ht vigente |
| `test_23_25_planning_code_is_unchanged_since_stage_3_2` | `tests/test_stage3_3a_result_contract.py:432` | H | `git show a733487:interblock_orchestrator.py` x arquivo do HEAD | funções do planner em a733487 x em eee88d6 (fechamento 3.3A) | a afirmação é da 3.3A (o contrato de resultado não mexeu no planner); regressões de plano no HEAD são pegas pelos testes R (plan_order nos fingerprints) |
| `test_live_differential_reference_vs_head_matches_exactly` | `tests/test_stage3_4b_differential.py:123` | H | harness ao vivo 7877551 x HEAD sobre data/seed do HEAD | mesmo harness, sem alteração, executado num clone temporário no fechamento 4d54804 (7877551..4d54804) | o runtime de referência (7877551) não carrega dados futuros (unidades novas); a afirmação diferencial é histórica da 3.4B. Regressão do app no HEAD fica com os testes R (3.4C/4A/4B) |
| `test_committed_evidence_reproduces_the_full_matrix` | `tests/test_stage3_4b_differential.py:161` | H | evidência versionada x universo dos seeds do HEAD | evidência versionada x universo dos seeds em 4d54804 (calculado no clone) | a evidência descreve o universo do seu fechamento |
| `test_committed_summary_is_the_differential_oracle` | `tests/test_stage3_4b_differential.py:176` | E | summary versionado | sem alteração (+ sha256 no B0 e diff x fechamento) | evidência histórica |
| `test_live_integrated_regression_passes` | `tests/test_stage3_4c_integrated.py:56` | R | harness ao vivo + literais 446/25/421/427/218/197/12 | harness com `--baseline-dir` do current; literais = universo da referência do registro (B0 = mesmos literais, provado em test_stage4c_baseline_registry) | regressão viva do HEAD |
| `test_live_run_reproduces_committed_evidence_and_is_deterministic` | `tests/test_stage3_4c_integrated.py:70` | R | `audit/stage3_4/integrated/evidence/integrated_summary.json` | arquivo do conjunto stage3_4c_integrated do current | regressão viva x referência aprovada |
| `test_committed_targets_nodes_transfers_and_coverage_are_complete` | `tests/test_stage3_4c_integrated.py:118` | R | CSVs versionados x plano vivo + literais 421/427/12/60 | CSVs do current x plano vivo; literais da referência | compara plano vivo com evidência |
| `test_committed_summary_contract` | `tests/test_stage3_4c_integrated.py:86` | E | summary versionado | sem alteração | conteúdo da evidência histórica |
| `test_area_41_is_outside_the_integrated_universe` | `tests/test_stage3_4c_integrated.py:141` | C | literal 25 alvos do area_41 | sem alteração (pré-lista 5A) | cardinalidade do conteúdo vigente |
| `test_live_evidence_mutations_are_all_detected` | `tests/test_stage3_4d_mutation.py:51` | H | harness de mutação ao vivo no HEAD (alvos VAR13001–13003, BASELINE 043fe9c) | mesmo harness, sem alteração, num clone temporário em 8095011 (fechamento 3.4D) | a matriz de mutações nomeia IDs reais que a 5A aposenta (VAR13001–13003); a afirmação 'auditores 3.4B/3.4C detectam 100%' é do fechamento |
| `test_live_run_reproduces_committed_mutation_results` | `tests/test_stage3_4d_mutation.py:64` | H | resultado vivo x mutation_results.csv | resultado no clone 8095011 x mutation_results.csv (E) | idem |
| `test_live_code_mutant_is_killed_in_a_temporary_copy` | `tests/test_stage3_4d_mutation.py:104` | H | mutante CM-13 numa cópia do HEAD + status antes/depois | mutante CM-13 numa cópia de 8095011; status antes/depois do repositório (W) mantido | os detectores 'TESTS' rodam a suíte da cópia; no HEAD futuro a suíte tem falhas C alheias ao mutante |
| `test_no_production_artifact_changed_since_baseline` | `tests/test_stage3_4d_mutation.py:179` | H | `classify_git(043fe9c)` x árvore de trabalho | `classify_git(043fe9c, 8095011)` | afirmação do fechamento 3.4D |
| `test_committed_mutation_matrix_is_formal_and_complete` | `tests/test_stage3_4d_mutation.py:73` | E | artefatos versionados da 3.4B/3.4C/3.4D | sem alteração (+ sha256 no B0 e diff x fechamento) | só lê evidência histórica |
| `test_committed_code_mutants_have_no_survivors` | `tests/test_stage3_4d_mutation.py:90` | E | artefatos versionados da 3.4B/3.4C/3.4D | sem alteração (+ sha256 no B0 e diff x fechamento) | só lê evidência histórica |
| `test_blackbox_audit_passes_without_importing_app` | `tests/test_stage3_4d_mutation.py:119` | E | artefatos versionados da 3.4B/3.4C/3.4D | sem alteração (+ sha256 no B0 e diff x fechamento) | só lê evidência histórica |
| `test_blackbox_audit_rejects_corrupted_evidence` | `tests/test_stage3_4d_mutation.py:157` | E | artefatos versionados da 3.4B/3.4C/3.4D | sem alteração (+ sha256 no B0 e diff x fechamento) | só lê evidência histórica |
| `test_baseline_gaps_are_recorded_and_closed` | `tests/test_stage3_4d_mutation.py:167` | E | artefatos versionados da 3.4B/3.4C/3.4D | sem alteração (+ sha256 no B0 e diff x fechamento) | só lê evidência histórica |
| `test_tax_06_no_id_changed_by_the_rename` | `tests/test_taxonomy_migration_d_tax_01.py:112` | H | snapshot da árvore de trabalho x before_snapshot.json (547b920) | snapshot calculado num clone temporário em d8b5d55 x before_snapshot.json | a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente |
| `test_tax_07_no_formula_changed` | `tests/test_taxonomy_migration_d_tax_01.py:121` | H | snapshot da árvore de trabalho x before_snapshot.json (547b920) | snapshot calculado num clone temporário em d8b5d55 x before_snapshot.json | a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente |
| `test_tax_08_no_interblock_link_changed_semantically` | `tests/test_taxonomy_migration_d_tax_01.py:126` | H | snapshot da árvore de trabalho x before_snapshot.json (547b920) | snapshot calculado num clone temporário em d8b5d55 x before_snapshot.json | a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente |
| `test_tax_09_the_16_pending_load_links_are_identical` | `tests/test_taxonomy_migration_d_tax_01.py:135` | H | snapshot da árvore de trabalho x before_snapshot.json (547b920) | snapshot calculado num clone temporário em d8b5d55 x before_snapshot.json | a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente |
| `test_cardinalities_results_and_graph_unchanged` | `tests/test_taxonomy_migration_d_tax_01.py:144` | H | snapshot da árvore de trabalho x before_snapshot.json (547b920) | snapshot calculado num clone temporário em d8b5d55 x before_snapshot.json | a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente |
| `test_tax_10_the_authorized_change_is_detected_as_taxonomic_not_functional` | `tests/test_taxonomy_migration_d_tax_01.py:156` | H | `classify_git(547b920)` e `protected_status(ref, None)` x árvore de trabalho | `classify_git(547b920, d8b5d55)` e `protected_status(ref, d8b5d55)` | idem |
| `test_guard_rejects_every_non_taxonomic_change` | `tests/test_taxonomy_migration_d_tax_01.py:210` | H | `changes_between(547b920)` (árvore de trabalho) + arquivos do HEAD | `changes_between(547b920, d8b5d55)` + arquivos em d8b5d55 | com a árvore futura já não-taxonômica o negativo passaria por vacuidade; fixar o intervalo preserva o poder |
| `test_stage3_provenance_still_rejects_masked_pending_links` | `tests/test_taxonomy_migration_d_tax_01.py:225` | H | interblock_links.json do HEAD x 043fe9c | interblock_links.json em d8b5d55 x 043fe9c | controle positivo é o arquivo pós-migração |
| `test_tax_02_07_crosswalk_changes_no_id_or_range` | `tests/test_taxonomy_d_tax_02.py:156` | H | `git diff d8b5d55` x árvore de trabalho | `git diff d8b5d55 d2847ab`; faixas ao vivo == CANONICAL (S) | afirmação do fechamento D-TAX-02; a parte 'faixas inalteradas' segue ao vivo como S |
| `test_tax_02_05_historical_names_are_not_canonical_anywhere_operational` | `tests/test_taxonomy_d_tax_02.py:111` | S | `git grep` no HEAD | sem alteração | invariante vivo; independe de conteúdo |
| `test_independent_reconciliation_passes_without_app` | `tests/test_stage4a_closure.py:26` | H | reconcile_4a.py no HEAD (recontagem viva + `git diff d2847ab`) | reconcile_4a.py, sem alteração, num clone temporário em 0a924e6; o JSON versionado segue E | reconciliação de fechamento |
| `test_production_surface_and_stage_3_closure_untouched` | `tests/test_stage4a_closure.py:53` | H | `git diff d2847ab` x HEAD | `git diff d2847ab 0a924e6` (F4B-06) | a guarda fecha a 4A; lida contra o HEAD falha a cada stage posterior (F4B-06) |
| `test_pending_items_dated_addition_keeps_f01_f02_open_and_f03_partial` | `tests/test_stage4a_closure.py:60` | S | `git show d2847ab:PLATFORM_PENDING_ITEMS.md` é prefixo do HEAD | sem alteração | invariante append-only da lista mestre; continua válido com adições futuras |
| `test_l8_comparison_only_area_41_changed` | `tests/test_stage4a_closure.py:37` | E | closure_reconciliation_4a.json | sem alteração | evidência histórica |
| `test_independent_recount_matches_contract_without_importing_app` | `tests/test_stage4a_contract.py:48` | R | independent_count --check x audit/stage4a/contract_expectations.json + literais 446/458/62/896 | expectativas do conjunto stage4a_contract do current (`--baseline-dir`); literais = referência | — |
| `test_nodes_are_the_union_not_the_sum` | `tests/test_stage4a_contract.py:59` | R | independent_count + literais (shared, 458) | expectativas do current | — |
| `test_derivation_agrees_with_independent_recount_and_frozen_expectations` | `tests/test_stage4a_contract.py:68` | R | derive_4a --no-write x contract_expectations.json | x expectativas do current | — |
| `test_official_plan_pending_links_and_links_sha_are_unchanged` | `tests/test_stage4a_contract.py:75` | R | plan_evidence.csv da 3.2 + sha dos vínculos em d2847ab + expectativas | plan_evidence e expectativas do current (R); 'vínculos iguais no intervalo da 4A' = H (d2847ab..0a924e6) | — |
| `test_official_plan_comparator_detects_a_changed_evidence_row` | `tests/test_stage4a_contract.py:88` | R | plan_evidence.csv da 3.2 | plan_evidence do current | negativo sobre a referência viva |
| `test_hes_decision_tree_engine_equals_literal_workbook_in_all_50_combinations` | `tests/test_stage4a_contract.py:102` | E | evidência versionada da 4A | sem alteração | lê evidência histórica (a parte viva é conteúdo do area_41, inalterado) |
| `test_scopes_and_suffixes_verified_in_the_parser` | `tests/test_stage4a_contract.py:153` | E | evidência versionada da 4A | sem alteração | lê evidência histórica (a parte viva é conteúdo do area_41, inalterado) |
| `test_area_41_aggregation_rules_and_ytd_partial` | `tests/test_stage4a_contract.py:164` | E | evidência versionada da 4A | sem alteração | lê evidência histórica (a parte viva é conteúdo do area_41, inalterado) |
| `test_contract_document_records_decisions_findings_and_obs` | `tests/test_stage4a_contract.py:194` | E | evidência versionada da 4A | sem alteração | lê evidência histórica (a parte viva é conteúdo do area_41, inalterado) |
| `test_input_protocol_keeps_every_3_4c_input_index` | `tests/test_stage4a_contract.py:185` | C | literal range(51, 62) | sem alteração (pré-lista 5A) | índices dependem do nº de entradas do plano vigente |
| `test_live_five_block_regression_passes_and_reproduces_committed_evidence` | `tests/test_stage4a_integrated.py:48` | R | harness ao vivo x evidência 4A + contract_expectations + literais 446/458/13/421/427 | harness com `--baseline-dir`; literais = referência do current | — |
| `test_non_regression_of_the_421_previous_targets` | `tests/test_stage4a_integrated.py:63` | R | 3.4C integrated_summary.json/targets.csv versionados | conjunto stage3_4c_integrated do current | — |
| `test_negative_corrupted_previous_key_is_detected` | `tests/test_stage4a_integrated.py:147` | R | harness.non_regression em processo (3.4C versionada) | idem, referência configurada pelo registro (conftest) | — |
| `test_negative_area_41_change_does_not_touch_the_421_check` | `tests/test_stage4a_integrated.py:157` | R | idem | idem | — |
| `test_stage_3_4c_evidence_is_untouched` | `tests/test_stage4a_integrated.py:127` | H | `git diff d2847ab` x árvore em audit/stage3_4/** e stage3_2/** | H: `git diff d2847ab 0a924e6` nesses caminhos; E: evidência (arquivos de dados) do HEAD x 0a924e6; não rastreados | a 4C muda harnesses da 3.4 só para o parâmetro de diretório; a evidência continua imutável |
| `test_committed_non_regression_report` | `tests/test_stage4a_integrated.py:72` | E | evidência versionada 4A (+3.4C) | sem alteração | evidência histórica |
| `test_committed_summary_temporal_reexecution_determinism_state` | `tests/test_stage4a_integrated.py:82` | E | evidência versionada 4A (+3.4C) | sem alteração | evidência histórica |
| `test_committed_csv_evidence_is_complete` | `tests/test_stage4a_integrated.py:113` | E | evidência versionada 4A (+3.4C) | sem alteração | evidência histórica |
| `test_live_evidence_mutations_are_all_detected_with_positive_controls` | `tests/test_stage4a_mutation.py:43` | R | evidência 4A e expectativas versionadas | conjuntos do current (`--baseline-dir`) | — |
| `test_minimum_mutant_set_is_defined_and_applies_to_unique_snippets` | `tests/test_stage4a_mutation.py:75` | C | trechos do código do app no HEAD | sem alteração (pré-lista 5A se a 5A tocar esses trechos) | contrato do código atual |
| `test_mutants_never_touch_the_working_tree` | `tests/test_stage4a_mutation.py:89` | W | `git status -- app data tools` vazio | sem alteração | árvore intacta |
| `test_committed_evidence_mutation_results` | `tests/test_stage4a_mutation.py:51` | E | evidência versionada | sem alteração | — |
| `test_committed_code_mutants_all_detected_in_temporary_copies` | `tests/test_stage4a_mutation.py:62` | E | evidência versionada | sem alteração | — |
| `test_live_oracle_agrees_with_engine_on_20_equations_and_25_hes_combinations` | `tests/test_stage4a_oracle.py:40` | C | workbook A41 v9 + literais (20 equações, 25 combinações) | sem alteração | fidelidade ao workbook vigente do area_41 |
| `test_committed_oracle_summary_declares_tolerance_and_limitations` | `tests/test_stage4a_oracle.py:53` | E | oracle_summary.json | sem alteração | — |
| `test_independent_reconciliation_passes_without_app` | `tests/test_stage4b_closure.py:26` | H | reconcile_4b.py no HEAD (G-01/G-02 com `git diff 0a924e6`) | reconcile_4b.py, sem alteração, num clone temporário em f573c1b; JSON versionado segue E | — |
| `test_production_surface_and_previous_stages_untouched` | `tests/test_stage4b_closure.py:36` | H | `git diff 0a924e6` x HEAD | `git diff 0a924e6 f573c1b`; arquivos não rastreados (W) mantidos | mesmo defeito do F4B-06, um fechamento adiante |
| `test_pending_items_dated_addition_is_append_only` | `tests/test_stage4b_closure.py:45` | S | `git show 0a924e6` é prefixo do HEAD | sem alteração | append-only |
| `test_independent_recount_matches_frozen_expectations` | `tests/test_stage4b_contract.py:36` | R | contract_expectations_4b.json + literais 324/196 | expectativas do conjunto stage4b_contract do current | — |
| `test_store_growth_predicted_from_seeds_matches_engine` | `tests/test_stage4b_contract.py:54` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_e1_turn_of_year_windows_and_snapshot` | `tests/test_stage4b_contract.py:60` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_e2_gaps_fail_explicitly` | `tests/test_stage4b_contract.py:71` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_e3_no_carry_over_of_new_period_inputs` | `tests/test_stage4b_contract.py:78` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_e4_closed_periods_and_e5_calendar` | `tests/test_stage4b_contract.py:88` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_performance_within_contract_limit` | `tests/test_stage4b_contract.py:132` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_contract_document_records_decisions_and_findings` | `tests/test_stage4b_contract.py:138` | E | contract_audit_4b.json / contrato | sem alteração | — |
| `test_live_t2_leap_year_passes` | `tests/test_stage4b_temporal.py:47` | R | harness T2 ao vivo x evidência T2 versionada + literais 446/458/896/67 | harness com `--baseline-dir`; literais = referência do current | — |
| `test_committed_runs_cover_every_date` | `tests/test_stage4b_temporal.py:56` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_identities_and_windows_follow_the_calendar` | `tests/test_stage4b_temporal.py:67` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_t1_turn_of_year_and_closed_periods` | `tests/test_stage4b_temporal.py:76` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_prefix_invariant_against_stage_4a` | `tests/test_stage4b_temporal.py:96` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_state_over_the_year_and_isolation_between_years` | `tests/test_stage4b_temporal.py:102` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_determinism_configurations` | `tests/test_stage4b_temporal.py:109` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_performance_ratio_within_limit_and_t3_leap_and_two_year_ends` | `tests/test_stage4b_temporal.py:119` | E | evidência T1/T2/T3 versionada | sem alteração | — |
| `test_live_evidence_mutations_detected_and_controls_accepted` | `tests/test_stage4b_mutation.py:42` | R | evidência T1/T2 + expectativas 4A/4B versionadas | conjuntos do current (`--baseline-dir`) | — |
| `test_required_mutants_apply_to_unique_snippets` | `tests/test_stage4b_mutation.py:71` | C | trechos do código do app | sem alteração | contrato do código atual |
| `test_working_tree_untouched` | `tests/test_stage4b_mutation.py:83` | W | `git status` vazio | sem alteração | — |
| `test_committed_evidence_mutations_cover_every_temporal_contract` | `tests/test_stage4b_mutation.py:50` | E | evidência versionada | sem alteração | — |
| `test_committed_code_mutants_all_detected` | `tests/test_stage4b_mutation.py:60` | E | evidência versionada | sem alteração | — |
| `test_live_oracle_t2_and_stated_run` | `tests/test_stage4b_oracle.py:37` | R | contract_expectations_4b.json (intervalos) via harness | expectativas do current | não compara com evidência |
| `test_committed_oracle_covers_every_aggregation_on_t1_and_t2` | `tests/test_stage4b_oracle.py:45` | E | oracle_temporal_summary.json | sem alteração | — |

## 3. Desenho do registro e do re-baseline

### 3.1 Layout

```
audit/baselines/
  BASELINE_REGISTRY.json      registro (lista encadeada) + ponteiro `current`
  baseline_paths.py           mapa histórico B0 (conjunto -> arquivo lógico -> caminho) e resolução por --baseline-dir
  baseline_registry.py        leitura, verificação (sha256, selo, cadeia) e resolução do `current` para os testes
  rebaseline.py               --id/--stage/--reason | --approve <id> | --check
  historical.py               clone temporário (`git clone --shared`) num commit fixo, para os testes H
  B<n>/<conjunto>/...         evidência regenerada (só a partir de B1)
```

### 3.2 Entrada do registro

```json
{"id": "B0", "commit_comportamento": "<sha>", "stage": "4C", "motivo": "...", "data": "AAAA-MM-DD",
  "anterior": null, "status": "PROPOSED|APPROVED", "layout": "historico|audit/baselines/B<n>",
  "conjuntos": {"<conjunto>": {"classe": "R|H|E", "herdado_de": null,
                                "arquivos": {"<lógico>": {"caminho": "...", "sha256": "..."}},
                                "expectativas": {...}}},
  "selo": "<sha256 da entrada canônica sem o selo>"}
```

- **B0** aponta para os diretórios de evidência existentes, sem cópia. São eles:
  - 3.2: `plan_evidence`;
  - 3.4B, 3.4C e 3.4D;
  - 4A: contrato, integrado, oracle, mutação e fechamento;
  - 4B: contrato, temporal, oracle, mutação e fechamento.
- `commit_comportamento` de B0 é `f573c1b`: o último commit em que toda essa evidência foi reproduzida (Fase 0).
- **Conjuntos R**, regenerados pelo re-baseline:
  - `stage3_2_plan` (`plan_evidence.csv` etc.);
  - `stage3_4c_integrated`;
  - `stage4a_contract` (`contract_expectations.json` + auditoria);
  - `stage4a_integrated`;
  - `stage4b_contract` (`contract_expectations_4b.json` + auditoria);
  - `stage4b_temporal` (T1/T2/T3).
- **Conjuntos H/E**, herdados sem regeneração (`herdado_de: "B0"`): 3.4B, 3.4D, 4A oracle/mutação/fechamento, 4B oracle/mutação/fechamento. Descrevem fechamentos.
- `expectativas` guarda, por conjunto R, os valores derivados dos próprios arquivos (universo, cardinalidades, sha dos vínculos). O `--check` os recalcula.
- O **selo** é calculado na aprovação. Editar uma entrada APPROVED quebra o selo.

### 3.3 `rebaseline.py`

- `--id Bn --stage X --reason "..."`:
  - **recusa** árvore suja (`git status --porcelain` não vazio), motivo ausente ou vazio, id já existente, diretório já existente e `current` não APPROVED;
  - roda cada harness R em ordem de dependência com `--baseline-dir audit/baselines/Bn`. A ordem é:
    1. 3.2 `plan_evidence`;
    2. 3.4C;
    3. `derive_4a`;
    4. 4A integrado;
    5. `derive_4b`;
    6. 4B T1/T2/T3;
  - depois roda a **verificação** `--no-write --baseline-dir audit/baselines/Bn`: a execução viva tem de reproduzir o que acabou de ser gravado. Rodam também `independent_count --check` e `independent_calendar --check`;
  - escreve **só** em `audit/baselines/Bn/<conjunto>/` e no registro;
  - gera `audit/baselines/Bn/DIFF_REPORT.md` contra o `current`;
  - acrescenta a entrada como **PROPOSED**. O `current` não muda.
- `--approve Bn`:
  - exige entrada PROPOSED cujo `anterior` seja o `current` e cujos arquivos confiram (sha256);
  - grava `APPROVED`, data e selo, e move o `current`.
- `--check`: verifica sem escrever. Exit 0/1. Confere:
  - esquema e ids únicos;
  - cadeia `anterior`;
  - `current` existente e APPROVED;
  - selos das APPROVED;
  - sha256 de todos os arquivos de todas as entradas;
  - expectativas recalculadas.

### 3.4 Parâmetro de diretório dos harnesses

- `--baseline-dir <dir>` é o **único** acréscimo aos harnesses R.
- Resolução, por `baseline_paths.py`:
  1. valor configurado em processo (`configure`);
  2. senão, `--baseline-dir` em `sys.argv`;
  3. senão, `None`, que dá os caminhos históricos B0. **O default é idêntico.**
- Com diretório, cada harness:
  - lê as referências próprias e as de montante em `<dir>/<conjunto>/`;
  - em modo escrita, grava ali.
- Na **regeneração** (modo escrita num diretório novo) a referência do próprio conjunto ainda não existe, então não é comparada. As de montante, já regeneradas, são.
- Se `<dir>` for passado em `--no-write` e a referência faltar, é `REFERENCE_MISSING` e a execução falha. Assim nada é ignorado em silêncio.
- Constantes embutidas que são referências mudam só de **fonte**: no default continuam as mesmas, e com diretório vêm do arquivo de referência. É o caso do universo 446/25/421/427/218/197/12 da 3.4C.
- Os testes leem o registro:
  - `tests/conftest.py` configura `baseline_paths` com o `current` (uso em processo);
  - cada execução em subprocesso recebe `baseline_registry.harness_args()`;
  - os literais dos testes R viram valores da referência;
  - um teste do registro prova que, em B0, a referência derivada é **igual** aos literais históricos. O poder de detecção não se perde em B0.

### 3.5 Mecanismos por classe

- **H**:
  - comparações entre dois commits fixos (`git diff A B`, `git show A:` x `git show B:`, `classify_git(A, B)`);
  - ou o harness histórico executado, **sem alteração**, num clone temporário no commit de fechamento (`historical.py`). É o caso de 3.4B, 3.4D, `reconcile_4a`, `reconcile_4b` e do snapshot D-TAX-01.
- **E**: os testes que só leem evidência versionada não mudam. O registro (Fase 2) acrescenta, para cada arquivo B0:
  - sha256 igual ao registrado;
  - `git diff <fechamento da stage> -- <arquivo>` vazio.
- **S**: regras do §1 (sem renumeração; aposentado ⇒ no `retired`; ID novo nunca emitido nem aposentado; append-only).
- **W**: `git status --porcelain -- app data tools` antes e depois.

## 4. Decisões

| id | decisão | estado |
|---|---|---|
| DR-4C-1 | a classe é atribuída por teste (tabela §2). Teste misto é separado **por asserção dentro do próprio teste**: a parte histórica vira H no intervalo da stage dona, a parte viva vira S/R. Nenhum teste é removido, marcado skip/xfail ou afrouxado | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-2 | B0 = evidência existente das Stages 3.2–4B, sem cópia. `commit_comportamento` = `f573c1b` (último commit em que toda a evidência foi reproduzida). `current` = B0 | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-3 | **3.4B é H**, executada sem alteração num clone em `4d54804` (intervalo `7877551..4d54804`). O runtime de referência `7877551` não aceita dados futuros (as unidades novas do energy v9/MaxHT v13 não existem no seu validador). A afirmação diferencial é histórica. Regressões do app no HEAD ficam a cargo de 3.4C, 4A e 4B (R), que comparam o HEAD com a referência aprovada | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-4 | **3.4D é H**, executada sem alteração num clone em `8095011`. A matriz de mutações nomeia IDs reais (VAR13001–VAR13003) que a 5A aposenta, e reescrever alvos seria mudar a lógica do harness (proibido) | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-5 | reconciliações de fechamento (`reconcile_4a`, `reconcile_4b`) e snapshot D-TAX-01: **H** por execução no clone do fechamento (`0a924e6`, `f573c1b`, `d8b5d55`). Os JSONs versionados seguem E | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-6 | regeneração = modo escrita num diretório novo. A referência do próprio conjunto não existe e não é comparada, mas o re-baseline sempre executa em seguida a verificação `--no-write` contra o que gravou, e só então propõe a entrada. A aprovação é humana (`--approve`), depois da leitura do DIFF_REPORT | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-7 | "bit a bit" de B0: cada harness R regenerado num diretório temporário reproduz os arquivos B0 com sha256 idêntico. Campos de **tempo de execução** (desempenho medido) são a única exceção admitida, comparados com o resto do conteúdo canônico. A exceção fica listada no relatório de reprodução | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-8 | `tests/conftest.py` (novo) só configura `baseline_paths` com o `current`. Não muda coleta, marcação nem asserção | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4C-9 | o ensaio (R1, R2) e as mutações da Fase 4 rodam só em clones temporários. No repositório ficam relatórios e listas (`audit/stage4c/rehearsal/`, `audit/stage4c/mutation/`) | `PROPOSED_ACCEPTED_BY_DEFAULT` |

### 4.1 Registros fechados nesta stage

| id | registro | estado |
|---|---|---|
| F4A-01 | `"F"` permanece `NO_APPLICABLE_RULE` com `detail = None` (contrato 3.3B, DR-4A-6). A expectativa `detail = "F"` do prompt 4A está encerrada sem mudança no `app/` | **CLOSED** |
| DR-4B-1..7 | invariante de prefixo, política de lacunas (só registro), ano fiscal (registro), T3 executada, protocolo de entradas, limite de desempenho 3,0, critérios do gate | **ACCEPTED** |
| F4B-06 | guardas de fechamento 4A/4B lidas contra o HEAD | resolvido pela conversão H da Fase 2 (`d2847ab..0a924e6`, `0a924e6..f573c1b`) |

### 4.2 Pontos de negócio (não bloqueiam)

| id | ponto | estado |
|---|---|---|
| F4B-02 | lacuna ⇒ `VariableNotFoundError` genérico; carga do realizado anterior ao início | REQUIRES_FOLLOWUP (negócio) |
| DR-4B-3 | ano fiscal x ano-calendário | pendência de negócio |

## 5. Findings da Fase 1

| id | classe | finding |
|---|---|---|
| F4C-01 | DOCUMENTATION_ONLY | ensaio R1 antes do re-baseline: 59 failed + 19 errors (78 itens, 69 funções) em **21** arquivos, não "60 + 19 em 25" `[ref]` |
| F4C-02 | DOCUMENTATION_ONLY | vínculos no R1: 29 declarados / 13 válidos / 16 pendentes (iguais aos de hoje), não "40" `[ref]`. O detalhe por vínculo sai do DIFF_REPORT |
| F4C-03 | REQUIRES_FOLLOWUP (resolvido na Fase 2) | `test_guard_rejects_every_non_taxonomic_change` (D-TAX-01) compara com a **árvore de trabalho**. Com a árvore já não taxonômica (5A), cada negativo passaria **por vacuidade** (perda silenciosa de poder). A conversão H fixa o intervalo `547b920..d8b5d55` |
| F4C-04 | DOCUMENTATION_ONLY | a evidência 4B grava tempos de execução (`performance`, `performance_profile.csv`, `performance_probe.csv`), que não são reprodutíveis bit a bit (DR-4C-7) |

## 6. Regra de parada

- Todos os 121 testes foram classificados sem perda de poder de detecção no próprio escopo.
- Nenhum BLOCKER de produção.
- **Segue para a Fase 2.**

## 7. Adendo da Fase 2 (append-only; a tabela do §2 fica como gerada no commit 4c.1)

| id | classe | finding / reclassificação |
|---|---|---|
| F4C-05 | DOCUMENTATION_ONLY | `test_stage4b_oracle.py::test_live_oracle_t2_and_stated_run` foi inventariado como R, mas `run_oracle_4b.py` **não lê nenhuma referência** (só calendário e engine x oracle puro). Classe corrigida: **C**, sem alteração no teste. Contagem final: H 21, E 35, **R 16**, S 8, W 2, **C 39** |
| F4C-06 | DOCUMENTATION_ONLY | o ponto fixo H da 3.4D é **`d8b5d55`**, não `8095011`. A D-TAX-01 fez a última revisão do harness e da evidência da 3.4D (`persisted_links_status`, `mutation_results.csv`), e em `8095011` o harness ainda não emitia o status taxonômico que o teste exige. Intervalo da guarda de produção: `043fe9c..d8b5d55` (só a migração autorizada). DR-4C-4 vale com esse commit |

## 8. Adendo da Fase 3 (ensaio R1, append-only)

O R1 mostrou três pontos em que os geradores de referência ainda fixavam conteúdo **dentro do harness**. Todos foram corrigidos só na **fonte da referência**, permitida pelo §3. Em B0 os arquivos regenerados continuam bit a bit iguais (`b0_reproduction.py`).

| id | classe | finding | correção |
|---|---|---|---|
| F4C-07 | REQUIRES_FOLLOWUP (resolvido) | `derive_4a.py` gravava o literal `official_targets: 446` nas expectativas, e `derive_4b.py` gravava 446/458/13/67/896 como universo por data. Com conteúdo novo, a regeneração falharia sempre | `official_targets` passa a vir do plano oficial derivado. O universo por data da 4B passa a vir das expectativas do contrato 4A do mesmo baseline (referência de montante). Em B0, mesmos valores |
| F4C-08 | REQUIRES_FOLLOWUP (resolvido) | `derive_4a.py` comparava os vínculos **vivos** com `d2847ab` (guarda H embutida, lida contra a árvore) | vira H no intervalo fixo `d2847ab` x `0a924e6`. O vínculo vivo continua guardado pela expectativa R `interblock_links_sha256` (`EXPECTATIONS_DRIFT`, `check_provenance`, teste R) |
| F4C-09 | DOCUMENTATION_ONLY | `derive_4a`/`derive_4b`/fingerprint 4A chamavam subprocessos do próprio harness sem repassar o diretório | repassam `--baseline-dir` (`bp.argv()`) |
| F4C-10 | REQUIRES_FOLLOWUP (resolvido) | o auditor `audit_coverage_rows` da mutação 4B (controle PC4B-03) comparava cada data com os literais 446/458/896/67 | fonte da referência = expectativas `temporal` do baseline (`harness.EXPECTED`). Em B0, mesmos valores |
| F4C-11 | REQUIRES_FOLLOWUP (pré-5A, conteúdo) | no R1 o gerador renomeia 4 IDs de regra de agregação do max_ht (`ALIMENTAÇÃO_EVAP…` → `ALIMENTACAO_EVAP…`; o nome da variável perdeu o acento no MaxHT v13). Regras de agregação não estão no ledger de IDs | a 5A deve confirmar com o cliente o nome canônico e registrar a troca no relatório da stage |
