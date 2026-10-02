# Stage 4C — fechamento: governança de baseline (guardas históricas e re-baseline)

```
FINAL_STAGE_4C_GATE = PASS
```

- Branch: `feature/stage-4c-baseline-governance`, a partir de `f573c1b`.
- Sem push, sem merge, sem squash/rebase e sem opções que desativem hooks.
- Superfície de produção (`app/`, `data/**`, `tools/**`) intacta: `git diff --stat origin/main -- app data tools` = vazio.
- Os anexos (energy v9, MaxHT v13) não entraram no repositório: só foram usados no clone temporário do ensaio R1.

## 1. O que a 4C entrega

1. **Classificação de toda guarda** (contrato §2; `inventory/guard_inventory.json`): **121 testes**.

   | classe | testes |
   |---|---|
   | H | 21 |
   | E | 35 |
   | R | 16 |
   | S | 8 |
   | W | 2 |
   | C | 39 |

   Inclui a reclassificação F4C-05.
2. **Registro de baseline** `audit/baselines/BASELINE_REGISTRY.json`:
   - **B0** aponta, sem cópia, para a evidência das Stages 3.2–4B: 14 conjuntos (6 R regenerados, 8 H/E herdados), sha256 por arquivo, expectativas e selo de aprovação;
   - `current` = B0.
3. **Re-baseline governado** `audit/baselines/rebaseline.py`:
   - `--id/--stage/--reason` propõe (PROPOSED, com DIFF_REPORT);
   - `--approve` aprova (APPROVED + selo + `current`);
   - `--check` verifica sem escrever;
   - `--preflight-only` só roda as recusas;
   - recusa árvore suja, motivo ausente, id repetido ou inválido e proposta pendente.
4. **Harnesses R** (3.2 plano, 3.4C, 4A contrato/integrado/mutação, 4B contrato/temporal/mutação) recebem só `--baseline-dir`, com default idêntico. **B0 reproduzido**: 32 arquivos bit a bit + 8 equivalentes (diferem só em tempo de execução medido, DR-4C-7). Evidência: `evidence/b0_reproduction.json`.
5. **F4B-06 resolvido**: as guardas de fechamento 4A/4B viraram H com intervalos `d2847ab..0a924e6` e `0a924e6..f573c1b`.
6. **Procedimento**: `REBASELINE_PROCEDURE.md`.

## 2. Testes convertidos (nenhum removido, pulado ou afrouxado)

| classe | testes | mecanismo |
|---|---|---|
| H | 3.4B (`test_live_differential…`, `test_committed_evidence_reproduces…`) | harness sem alteração em clone em `4d54804` |
| H | 3.4D (`test_live_evidence_mutations…`, `test_live_run_reproduces…`, `test_live_code_mutant…`) | clone em `d8b5d55` (F4C-06) |
| H | 3.4D `test_no_production_artifact…` | `classify_git(043fe9c, d8b5d55)` |
| H | D-TAX-01 TAX-06..10, cardinalidades, negativos do guard, proveniência | snapshot em clone `d8b5d55`; intervalo `547b920..d8b5d55` (F4C-03) |
| H | D-TAX-02 TAX-02-07 | `d8b5d55..d2847ab`; a faixa viva segue como S |
| H | 3.3A `test_23_25` | `a733487` x `eee88d6` |
| H | fechamento 4A | reconciliação em clone `0a924e6`; superfície `d2847ab..0a924e6` |
| H | fechamento 4B | reconciliação em clone `f573c1b`; superfície `0a924e6..f573c1b` |
| H+E | 4A `test_stage_3_4c_evidence_is_untouched` | H no intervalo da 4A; E da evidência (não-código) x `0a924e6` |
| S | 2.6B `test_no_historical_id_was_renumbered`, 2.6C `test_12[a126e02, eceffd4]` | sem renumeração; removido ⇒ no `retired`; novo ⇒ ID inédito. O congelamento total vira H nos fechamentos |
| R | 3.4C (3), 4A contrato (5), 4A integrado (4), 4A mutação, 4B contrato, 4B temporal, 4B mutação | referência do `current` (`tests/conftest.py` + `harness_args()`). Os literais B0 são provados em `test_stage4c_baseline_registry.py` |
| E | todo arquivo B0 | sha256 registrado + `git diff <commit da evidência> -- arquivo` vazio (novo, no teste do registro) |

## 3. Ensaio da 5A (R1) e obrigatoriedade do re-baseline (R2)

Detalhes em `rehearsal/REHEARSAL_SUMMARY.md` e `rehearsal/R1_B1_ENSAIO_DIFF_REPORT.md`.

| ensaio | antes | depois |
|---|---|---|
| R1 (energy v9 + MaxHT v13 + 5 unidades + seeds regenerados) | 42 failed + 16 errors: **C 42 + R 16** | re-baseline `B1-ensaio` proposto e aprovado (`--check` PASS) → 29 failed + 13 errors: **só C (42)** |
| R2a (comentário + unidade `kWh/tv` no `app/`) | — | **2040 passed, 0 falhas** |
| R2b (EQ16001 19.475 → 19.476 sem re-baseline) | — | 8 falhas. Os **3 testes R falham** (4A integrado, 4B T2, mutação 4B). Também detectam a mudança: oracle A41 (C), build reproduzível (S) e consumo 2.4 (C) |

Resumo do DIFF_REPORT do R1 (confere com o `[ref]`):
- **energy**: +VAR18053 (entrada), +EQ18025. VAR18031 passa a calculada (EQ18011 = `VAR18053 / 1`).
- **max_ht**: VAR13001–VAR13006 aposentadas no ledger; VAR13117–VAR13123 novas; +EQ13030. 4 IDs de regra de agregação trocam de grafia (F4C-11).
- **vínculos**: 29 / 13 / 16 / 0 inalterados; 2 pendentes trocados (`VAR18031→VAR18053`, `VAR13003→VAR13119`). O "40" do `[ref]` não se confirma (F4C-02).
- **universos**: plano oficial 446 → 448; 3.4C 421/427 → 423/429; 4A 446/458 → 448/460; eventos por data 896 → 904; 13 transferências / 67 eventos inalterados.

## 4. Pré-lista da 5A (testes C a atualizar; valores do R1)

| teste | motivo | atual → esperado na 5A |
|---|---|---|
| `test_energy_seed_contract.py::test_entity_counts_match_the_workbook` | contagem de variáveis energy | 52 → 53 |
| `test_energy_seed_contract.py::test_equation_and_aggregation_counts` | equações energy | 24 → 25 |
| `test_energy_seed_contract.py::test_all_ids_are_inside_the_energy_range_and_unique` | lista de IDs | + VAR18053 |
| `test_energy_seed_contract.py::test_energy_ids_do_not_collide_with_other_blocks` | contagem de IDs | 52 → 53 |
| `test_energy_seed_contract.py::test_variable_frequency_distribution` | frequências | diário 33 → 34 |
| `test_energy_seed_contract.py::test_variable_type_distribution` | tipos | VAR18031 `calculado`; VAR18053 `entrada` |
| `test_energy_seed_contract.py::test_scope_distribution` | escopos | + escopo de VAR18053 |
| `test_energy_seed_contract.py::test_variable_instances_are_materialized_by_the_real_resolver` | instâncias | 172 → 179 |
| `test_energy_seed_contract.py::test_explicit_scoped_references_are_extracted` | equações com referência escopada | a lista muda a partir de EQ18015/EQ18016 (conteúdo do energy v9) |
| `test_energy_seed_contract.py::test_energia_bayer_and_energia_media_frct_bind_by_id_not_name` | expressão | `VAR18027 + VAR18040` → `VAR18038*2.455609` |
| `test_energy_runtime_contract.py` — 13 com ERROR no fixture (`test_per_line_results[L1..L7]`, `test_plant_group_results`, `test_subgroup_specific_evaporation[3]`, `test_both_branches…`, `test_energia_bayer_equals…`) e 7 FAILED (`test_the_23_daily…`, `test_no_calculated_variable…`, `test_perturbing_one_line…`, `test_perturbing_an_unrelated_line…`, `test_cross_block_inputs…`, `test_daily_to_monthly_chain…`, `test_eq18020_cannot…`) | o fixture não fornece a entrada nova VAR18053 (`VariableNotFoundError`); VAR18031 deixou de ser entrada | fixture + VAR18053; VAR18031 `calculado` |
| `test_max_ht_runtime_contract.py::test_entity_counts` / `::test_full_seed_root_loads_without_errors` | variáveis max_ht | 116 → 117 |
| `test_max_ht_runtime_contract.py::test_all_math_equations_parse_successfully` | equações max_ht | 29 → 30 |
| `test_stage2_4_workbook_contract.py::test_t24_02_each_block_builder_consumes_its_approved_workbook[energy]` | linhas do workbook | 56 → 57 |
| `test_stage2_4_workbook_contract.py::test_t24_02_each_block_builder_consumes_its_approved_workbook[max_ht]` | linhas do workbook | 120 → 121 |
| `test_stage2_4_workbook_contract.py::test_t24_02_total_rows_and_equations_match_stage_2_3` | total de linhas | 572 → 574 |
| `test_stage2_4_workbook_contract.py::test_t24_06_max_ht_v9_ignores_trailing_empty_rows` | linhas MaxHT | 120 → 121 |
| `test_stage2_6_interblock_contract.py::test_15_every_real_fonte_is_classified` | conjunto de vínculos reais | pendentes `energy.VAR18053`/`max_ht.VAR13119` no lugar de `VAR18031`/`VAR13003` |
| `test_stage2_6b_interblock_closure.py::test_17_max_ht_is_the_canonical_block_name` | nome do workbook | `…MaxHT_v10.xlsx` → `…MaxHT_v13.xlsx` |
| `test_stage2_6b_interblock_closure.py::test_18_all_real_links_of_the_five_workbooks` | conjunto EXPECTED de vínculos | idem ao `test_15` |
| `test_stage2_6c_interblock_final.py::test_17_independent_analysis_matches_the_builder` | análise independente 2.6C x builder | rever pares de vínculo trocados |
| `test_aggregation_dimensions.py::test_sum_factors_follow_the_approved_workbook_units` | unidades por fator de integração | `{1.0: {kg/d, t/d, …}, 24.0: {m³/h}}` → `{1.0: {kg/d, m³/d, t/d}}` (o fator 24.0 / `m³/h` deixa de existir) |

Total: **42 itens** (29 FAILED + 13 ERROR), todos classe C. Nenhum H, E, S, W ou R.

## 5. Mutação das guardas (Fase 4)

`mutation/mutation_summary.json`: **21 mutantes, 21 detectados (100.0%)**.

Detectados por classe:

| classe | detectados |
|---|---|
| E | 3/3 |
| H | 8/8 |
| R | 1/1 |
| REG | 5/5 |
| S | 3/3 |
| W | 1/1 |

- Controle positivo (clone sem mutação, mesmos 23 testes): **ACCEPT**.
- `git status --porcelain -- app data tools`: vazio antes e depois.

| id | classe | mutante |
|---|---|---|
| H-01 | H | commit sintético alterando app/ dentro do intervalo da 4A (d2847ab..X) |
| H-02 | H | commit sintético alterando data/ dentro do intervalo da 4B (0a924e6..X) |
| H-03 | H | commit sintético removendo um alvo da evidência 4A no fechamento (reconcile_4a no clone) |
| H-04 | H | commit sintético mudando a média de agregação sobre o fechamento 3.4B (diferencial no clone) |
| H-05 | H | commit sintético não taxonômico em app/ no intervalo 043fe9c..X da 3.4D |
| H-06 | H | commit sintético mudando uma fórmula no intervalo da D-TAX-01 (547b920..X) |
| H-07 | H | commit sintético alterando o planner no intervalo da 3.3A (a733487..X) |
| H-08 | H | commit sintético mudando uma faixa de ID no intervalo da D-TAX-02 (d8b5d55..X) |
| E-01 | E | evidência 3.4C reescrita (última linha de transfers.csv removida) |
| E-02 | E | evidência 4A reescrita (última linha de targets.csv removida) |
| E-03 | E | evidência 4B reescrita (última linha de T2/temporal_coverage.csv removida) |
| S-01 | S | ID renumerado (primeira entidade do energy) |
| S-02 | S | ID aposentado reutilizado (PARAM12003 numa identidade nova do production) |
| S-03 | S | identidade removida sem entrar no `retired` do ledger (VAR13001 do max_ht) |
| W-01 | W | harness de mutação 4A grava um arquivo em data/ durante a execução |
| REG-01 | REG | sha256 de um arquivo de B0 alterado no registro |
| REG-02 | REG | entrada APPROVED (B0) editada depois da aprovação |
| REG-03 | REG | re-baseline sem a recusa de árvore suja |
| REG-04 | REG | re-baseline sem a recusa de motivo ausente |
| REG-05 | REG | current apontando para uma entrada PROPOSED |
| R-01 | R | mudança de comportamento sem re-baseline (EQ16001 19.475 -> 19.476, = R2-b) |

## 6. Validação final (nesta execução)

| verificação | resultado |
|---|---|
| suíte completa | **2040 passed, 0 failed** (Fase 0: 2004 passed + 1 failed F4B-06; +30 testes do registro + 6 negativos parametrizados) |
| 3.4C `run_integrated.py --no-write` | PASS |
| 4A `run_integrated_4a.py --no-write` | PASS |
| 4B T2 / T1 `run_temporal_4b.py --no-write` | PASS / PASS |
| `reconcile_4a.py` (`python -I`) | clone `0a924e6`: **PASS 42/42**. No HEAD: 41/42, só a guarda L8-7 lida contra o HEAD acusa os caminhos de harness da 3.4 alterados pela 4C (parâmetro de diretório). É a classe H: F4C-12 |
| `reconcile_4b.py` (`python -I`) | clone `f573c1b`: **PASS 52/52**. No HEAD: 51/52, só a guarda G-01 acusa os arquivos da 4C (F4C-12) |
| `blackbox_audit.py` (`python -I`) | PASS, sem importar `app` |
| `rebaseline.py --check` | PASS (`current` = B0) |
| `b0_reproduction.py` | PASS (32 bit a bit + 8 equivalentes) |
| `build_inventory.py --check` | classificação igual à do commit 4c.1 |
| `git diff --stat origin/main -- app data tools` | vazio |

## 7. Findings

| id | classe | finding |
|---|---|---|
| F4C-01 | DOCUMENTATION_ONLY | R1 antes: 59+19 em 21 arquivos no primeiro ensaio (pré-conversão), não "60+19 em 25" `[ref]` |
| F4C-02 | DOCUMENTATION_ONLY | vínculos no R1: 29/13/16/0, não "40" `[ref]` |
| F4C-03 | REQUIRES_FOLLOWUP → resolvido | negativo do guard D-TAX-01 passaria por vacuidade com árvore não taxonômica; fixado em `547b920..d8b5d55` |
| F4C-04 | DOCUMENTATION_ONLY | evidência 4B contém tempos de execução (não bit a bit) |
| F4C-05 | DOCUMENTATION_ONLY | oracle 4B vivo reclassificado R → C (não lê referência) |
| F4C-06 | DOCUMENTATION_ONLY | ponto fixo H da 3.4D é `d8b5d55` (última revisão do harness/evidência), não `8095011` |
| F4C-07 | REQUIRES_FOLLOWUP → resolvido | literais de referência nos geradores 4A/4B (`official_targets`, universo por data) |
| F4C-08 | REQUIRES_FOLLOWUP → resolvido | guarda de vínculos da `derive_4a` lida contra a árvore → H `d2847ab` x `0a924e6` |
| F4C-09 | DOCUMENTATION_ONLY | subprocessos dos geradores repassam `--baseline-dir` |
| F4C-10 | REQUIRES_FOLLOWUP → resolvido | auditor de cobertura da mutação 4B com literais → expectativas do baseline |
| F4C-11 | REQUIRES_FOLLOWUP (5A, conteúdo) | 4 IDs de regra de agregação do max_ht trocam de grafia no MaxHT v13 (`ALIMENTAÇÃO` → `ALIMENTACAO`) |
| F4C-12 | DOCUMENTATION_ONLY | `reconcile_4a/4b` são scripts de fechamento (H). Rodados no HEAD, suas guardas de árvore acusam mudanças posteriores por construção; a forma válida é no clone do fechamento (testes H) |

`BLOCKER`: **nenhum**.

## 8. Decisões e pendências

- **F4A-01: CLOSED.** `"F"` → `NO_APPLICABLE_RULE` com `detail = None`.
- **DR-4B-1..7: aceitos.**
- **DR-4C-1..9:** `PROPOSED_ACCEPTED_BY_DEFAULT` (contrato §4).
- **L8:** formalizado pelo re-baseline governado.
- **Pontos de negócio (não bloqueiam):**
  - **F4B-02**: lacunas e realizado anterior;
  - **DR-4B-3**: ano fiscal.
- **Continuam abertos:** F-01 (16 `PENDING_LOAD`) e F-02.
- Adição datada em `audit/stage3_4/PLATFORM_PENDING_ITEMS.md`.

## 9. Gate

| # | critério | resultado |
|---|---|---|
| 1 | Fase 0 recalculada (2004 passed + 1 failed F4B-06; SHA dos anexos) | PASS |
| 2 | inventário e classificação completos antes de editar teste (commit 4c.1) | PASS |
| 3 | contrato com rastreabilidade, DR-4C-n, F4A-01 CLOSED, DR-4B aceitos | PASS |
| 4 | superfície de produção intacta (`git diff origin/main -- app data tools` vazio) | PASS |
| 5 | registro B0 sem cópia; `rebaseline.py` com proposta, aprovação, `--check` e recusas | PASS |
| 6 | nenhum teste removido, pulado ou afrouxado; contagens por arquivo preservadas | PASS |
| 7 | harnesses só com parâmetro de diretório e fonte de referência; B0 reproduzido | PASS |
| 8 | F4B-06 resolvido (intervalos `d2847ab..0a924e6`, `0a924e6..f573c1b`) | PASS |
| 9 | suíte 100% verde | PASS (2040) |
| 10 | R1: antes só C+R; depois só C; DIFF_REPORT confere | PASS |
| 11 | R2a sem falhas indevidas; R2b com os testes R falhando | PASS |
| 12 | mutação 100%, controles positivos aceitos, árvore intacta | PASS |
| 13 | evidência histórica intacta (E) e anexos fora do repositório | PASS |
| 14 | fechamento, procedimento e adição append-only; sem push/merge | PASS |

## 10. Reprodução

```
python -m pytest -q
python audit/baselines/rebaseline.py --check
python audit/stage4c/b0_reproduction.py
python audit/stage4c/inventory/build_inventory.py --check
python audit/stage3_4/integrated/run_integrated.py --no-write
python audit/stage4a/integrated/run_integrated_4a.py --no-write
python audit/stage4b/temporal/run_temporal_4b.py --range T2 --no-write   # e --range T1
python -I audit/stage3_4/mutation/blackbox_audit.py --no-write
python audit/stage4c/rehearsal/rehearse_5a.py --scenario R1 --energy <energy_v9.xlsx> --maxht <MaxHT_v13.xlsx>
python audit/stage4c/rehearsal/rehearse_5a.py --scenario R2a      # e R2b
python audit/stage4c/mutation/run_mutation_4c.py
git diff --stat origin/main -- app data tools
```

## 11. Commits

| commit | conteúdo |
|---|---|
| `b487dc1` | audit(stage4c.1): inventário e classificação das guardas históricas |
| `2b753a7` | test(stage4c.2a): registro de baseline e re-baseline |
| `b872468` | test(stage4c.2b): conversão das guardas históricas |
| `de95ddb` | test(stage4c.3): ensaio da 5A e prova de obrigatoriedade do re-baseline |
| `19269f5` | test(stage4c.4): mutação das guardas e do registro |
| este | docs(stage4c.5): fechamento da Stage 4C |
