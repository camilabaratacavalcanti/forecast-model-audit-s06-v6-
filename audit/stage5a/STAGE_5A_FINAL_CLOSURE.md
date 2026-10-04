# Stage 5A — fechamento: unidades novas, livro de IDs de equação, fim do ×24, energy v9 e max_ht v13

- Branch: `feature/stage-5a-contract-energy-maxht`, a partir de `main` = `e262e03`.
- Sem push e sem merge.
- Resultado: **`FINAL_STAGE_5A_GATE = PASS (após decisão F5A-07)`** (§10, §13). O gate estava em `READY_FOR_DECISION` até a decisão sobre F5A-07.

## 1. Baseline (Fase 0, recalculada)

| item | valor |
|---|---|
| `main` | `e262e03` (4B + 4C), árvore limpa |
| suíte em `e262e03` | **2040 passed** (clone limpo) |
| `rebaseline.py --check` | PASS, `current` = B0 |
| anexo energy v9 | `731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2` |
| anexo MaxHT v13 | `c9818920b3994ae6aaeef5f237e59dd94d8e1b8647f0bf64426fb5f3d9f0aa98` |

## 2. Decisões aplicadas

| id | decisão | onde |
|---|---|---|
| D-5A-1 | unidades `kWh/tv`, `tv/MWh`, `tv/t carvão`, `GJ/d`, `m³/d` nos validadores de variáveis e de parâmetros | `app/validation/variable_seed_validator.py`, `parameter_seed_validator.py` |
| D-5A-2 | SUM só com origem diária (fator 1). O builder recusa fator ≠ 1 com mensagem que cita `<origem>_ag`; o runtime recusa `integration_factor ≠ 1`; a checagem dimensional (`required_sum_factor`) foi mantida | `tools/workbook_seed/seeds.py`, `app/domain/forecast/aggregation.py` (ponto único de validação do fator) |
| D-5A-3 | renomeação `alimentação_evap*` → `alimentacao_evap*`: VAR13001–VAR13006 aposentados; 4 IDs de regra trocam de grafia | workbook MaxHT v13 + livro |
| D-5A-4 | livro de IDs de equação: identidade = identidade da variável alvo + escopo da instância. Mesma identidade ⇒ mesmo EQ; identidade que sai ⇒ `retired_equations`; EQ novo ⇒ acima do maior já emitido | `tools/workbook_seed/id_ledger.py`, `seeds.py`, `canonical.py`, `data/id_ledger/*.json` |
| DR-5A-1 | equações emitidas em ordem crescente de EQ | `seeds.py` |
| DR-5A-2 | testes de runtime com fator 24 são C e viram contrato D-5A-2 (recusa + `_ag` explícita com a mesma aritmética) | §5 |
| DR-5A-3 | `b0_reproduction.py` roda no clone `e262e03`; B0 também é verificado por `--check` | §9 |

## 3. F5A-01 — antes e depois

| bloco | EQ que mudariam de alvo **sem** o livro (numeração posicional) | **com** o livro |
|---|---|---|
| energy | **14** (EQ18011 … EQ18024) | **0**. +EQ18025 (`evaporado_total_evaporacao` = `VAR18053 / 1`) |
| max_ht | **9** (EQ13001, EQ13022 … EQ13029) | **0**. −EQ13001 (aposentado), +EQ13030, +EQ13031 |
| yield, production, area_41 | 0 | 0 |

- Verificado no 5A.2b: 0 VAR renumerados, 0 EQ movidos em todos os blocos. EQ18019 continua `VAR18027 + VAR18040`.
- Garantias contínuas:
  - `tests/test_stage5a_equation_ledger.py` (S contra B0 `e262e03`);
  - mutantes EQ-01, EQ-02 e LED-01 (§7).
- **F5A-01: resolvido.**

## 4. Mudanças de produção por commit

| commit | o que mudou |
|---|---|
| `3dc83d7` audit(stage5a.1) | contrato e sonda da Fase 1; nada de produção |
| `2c5e942` feat(stage5a.2a) | D-5A-1 (5 unidades nos 2 validadores); D-5A-4 (livro de equações). **Seeds byte a byte idênticos**; o livro foi inicializado de forma determinística a partir da numeração vigente |
| `cb49775` feat(stage5a.2b) | workbooks energy v9 e MaxHT v13 adicionados (v6 e v10 mantidos); `BlockSpec` com os SHA aprovados. Seeds regenerados via `python -m tools.workbook_seed`: energy 53 vars / 25 eq; max_ht 117 vars / 30 eq / 78 regras |
| `fe95471` feat(stage5a.2c) | D-5A-2 no builder e no runtime. Seeds regenerados **idênticos** aos do 2b (nenhuma regra com fator ≠ 1) |

`git diff --stat main -- app` mostra só 3 arquivos, todos autorizados: os 2 validadores (enum) e `aggregation.py` (validação de `integration_factor`). `temporal_aggregation_service.py` não foi tocado; o ramo multiplicativo ficou inalcançável.

## 5. Testes C atualizados (commit `a12954a`), com justificativa no próprio teste

| arquivo | testes | antigo → novo | causa |
|---|---|---|---|
| `test_energy_seed_contract.py` | `test_entity_counts_match_the_workbook`, `test_equation_and_aggregation_counts`, `test_all_ids_are_inside_the_energy_range_and_unique`, `test_energy_ids_do_not_collide_with_other_blocks`, `test_variable_frequency_distribution`, `test_variable_type_distribution`, `test_scope_distribution`, `test_variable_instances_are_materialized_by_the_real_resolver` | vars 52 → 53, entidades 56 → 57, eq 24 → 25, diário 33 → 34, calculado 35 → 36, linha/L1_L7 20 → 21, instâncias 172 → 179 | energy v9: +`retirada_total_condensado_area13` (entrada); `evaporado_total_evaporacao` passa a calculado |
| `test_energy_seed_contract.py` | **novo** `test_evaporado_total_evaporacao_is_the_condensate_withdrawal_over_its_specific_volume` | — | exigido pelo prompt: EQ18025 = `VAR18053 / 1`, avaliado |
| `test_energy_runtime_contract.py` | fixture (`DAILY_EQUATION_IDS`, `LINE_INPUT_VARIABLES`, entradas de outros blocos, entrada ausente) | VAR18031 entrada → VAR18053 entrada; 23 → 24 equações diárias | idem |
| `test_max_ht_runtime_contract.py` | `test_entity_counts`, `test_all_math_equations_parse_successfully`, `test_full_seed_root_loads_without_errors` | 116 → 117 vars; 29 → 30 eq | MaxHT v13 |
| `test_stage2_4_workbook_contract.py` | `test_t24_02_each_block_builder_consumes_its_approved_workbook[energy, max_ht]`, `test_t24_02_total_rows_and_equations_match_stage_2_3`, `test_t24_06_max_ht_v9_ignores_trailing_empty_rows` | linhas 56/120 → 57/121, total 572 → 574, eq 238 → 240, última linha 122 → 123 | idem |
| `test_stage2_6_interblock_contract.py` | `test_15_every_real_fonte_is_classified` | `producao` na linha 98 → 99 | v13 insere uma linha antes |
| `test_stage2_6b_interblock_closure.py` | `test_17_max_ht_is_the_canonical_block_name`, `test_18_all_real_links_of_the_five_workbooks` | v10 → v13; pendentes `evaporado_total_evaporacao` → `retirada_total_condensado_area13`, `alimentação_evap` → `alimentacao_evap` | vínculos trocados (classes inalteradas) |
| `test_stage2_6c_interblock_final.py` | `test_17_independent_analysis_matches_the_builder` | script 2.6C → wrapper 5A (`audit/stage5a/analysis_interblock_5a.py`), que troca só as constantes de conteúdo (workbooks e lista exata de IDs novos/aposentados). Asserções iguais | evidência 2.6C não pode ser regravada; a forma histórica virou **novo** `test_17b` (H, clone `e262e03`) |
| `test_aggregation_dimensions.py` | `test_sum_factors_follow_the_approved_workbook_units`, `test_sum_applies_integration_factor` | {1: t/d, kg/d; 24: m³/h} → {1: t/d, kg/d, m³/d}; ×24 → recusa + `_ag` explícita (mesmo 1440) | D-5A-2 / DR-5A-2 |
| `test_stage3_3c_state_aware_aggregation.py` | agregador `SUM_X24` → `SUM_AG` (18 casos parametrizados) | mesma aritmética Σ v·24, mesmos cenários de estado | D-5A-2 / DR-5A-2 |

- Total, contado no diff `main..a12954a`: **20 funções de teste C editadas** em 9 arquivos, mais **5 tabelas ou fixtures de módulo C**:
  - `EXPECTED_ROWS` (2.4), usado por `test_t24_02_each_block…`;
  - `EXPECTED_VALID` (2.6), usado por `test_15`;
  - `EXPECTED` (2.6B), usado por `test_18`;
  - o fixture de entradas do runtime do energy;
  - `AGGREGATORS`/`rule`/`aggregate` da 3.3C, nos 18 casos `SUM_X24` → `SUM_AG`.
- Testes novos: 1 de conteúdo (EQ18025) e 1 H (`test_17b`).
- Previstos para deixar de falhar com D-5A-4, sem edição: `test_energia_bayer…` e `test_explicit_scoped_references…`.
- Nenhum teste foi apagado, pulado ou afrouxado.
- Depois do commit `a12954a`, a suíte teve **16 falhas, todas R** do inventário 4C (13 FAILED + 3 ERROR de fixture) e nenhuma H/E/S/W/C.

**Fora da regra "só C" (decisão da engenheira): F5A-07.**
- `tests/test_stage4c_baseline_registry.py` (10 casos: controle positivo, recusas de motivo, id e repetição, e árvore suja) fixava `"B1"` como próximo ID livre.
- Com B1 aprovado, os casos passariam a testar outra recusa ("proposta pendente" / "já existe").
- A correção deriva o próximo ID do registro do HEAD (`NEXT = B2`); nenhuma asserção muda.
- `rebaseline.py` está correto. O teste não estava no inventário 4C.

## 6. Re-baseline B1

- Proposta (`d78302a`) a partir de `a12954a`: 17 passos, todos com returncode 0, incluindo os recálculos independentes da 4A e da 4B.
- Aprovação (`28ac352`): selo `c8ad92b2bf6dc3cfb1573e9f607b6d5453f9409894ab816246945c88db79a9ef`, `current` = B1, `--check` PASS.
- Resumo do `DIFF_REPORT`, conferido item a item em `B1_REVIEW.md`:
  - **Conteúdo:**
    - energy +VAR18053, +EQ18025;
    - max_ht +VAR13117..123, −VAR13001..006 (aposentados), +EQ13030/31, −EQ13001;
    - 4 regras renomeadas.
    - Vínculos 29/13/16/0, com 2 pendentes trocados.
  - **Universos:** plano 446 → 448; 3.4C 421/427 → 423/429; 4A 446/458 → 448/460; eventos por data 896 → 904; transferências 13 (iguais).
  - **Valores:**
    - 91 alvos comuns mudaram de valor, só pela posição das entradas sintéticas no fixture.
    - A sonda `b1_value_attribution.py` reindexa as entradas pela ordem de B0. Com isso, **416/416** alvos comuns, os 5 renomeados e VAR18031 ficam **idênticos** a B0.
    - VAR13067 (SUM de `lth_total_ag`) também fica idêntico ao ×24 antigo.
  - **4B:**
    - +8 identidades por data;
    - snapshots +8 × dias do período;
    - grafo continua acíclico;
    - mensagem de lacuna cita VAR13119 (renomeado);
    - desempenho +30% por data, que é campo de tempo de execução.
- Nenhuma divergência sem explicação.

## 7. Mutação (`audit/stage5a/mutation/`, clones temporários)

| id | mutante | detectado por |
|---|---|---|
| EQ-01 | EQ18001 → EQ18099 (seeds + livro) | `test_equation_ids_are_never_renumbered…[energy]` |
| EQ-02 | EQ13001 (aposentado) reutilizado | `…[max_ht]` |
| LED-01 | livro de equações ignorado (posicional) | `test_ledger_payload_reproduces_the_versioned_ledger[energy, max_ht]` |
| SUM-01 | builder aceita SUM /h em silêncio | `test_builder_rejects_sum_of_an_hourly_origin…` |
| RT-01 | runtime aceita fator 24 | `test_runtime_refuses_integration_factor…[24-SUM, 24.0-SUM]`, `test_sum_applies_integration_factor` |
| UNIT-01..05 | cada unidade nova removida do enum de variáveis | `test_new_units_are_allowed…[unidade]` |
| UNIT-06 | `GJ/d` removida do enum de parâmetros | idem |
| SPEC-01 | sha256 do `BlockSpec` do energy divergente | `test_t24_14_source_reference_is_the_workbook_actually_read[energy]` |
| VAR-01 | VAR13001 (aposentado) reaparece em `alimentacao_evap` | `test_no_historical_id_was_renumbered`, `test_12_ids_are_stable_against_baselines[a126e02, eceffd4]` |

- **13/13 detectados (100%)**; controle positivo ACCEPT (17 testes).
- `git status -- app data tools` vazio antes e depois.
- Teste: `tests/test_stage5a_mutation.py`.

## 8. Findings

| id | classe | finding | estado |
|---|---|---|---|
| F5A-01 | BLOCKER | EQ atribuídos por posição (14 + 9 mudariam de alvo) | **resolvido** (D-5A-4) |
| F5A-02 | DOCUMENTATION_ONLY | EQ13019 mantém o ID e muda a expressão (lê VAR13119 em vez de VAR13003) | registrado; visível no DIFF |
| F5A-03 | DOCUMENTATION_ONLY | testes W exigem as mudanças de produção commitadas antes da suíte | procedimento seguido |
| F5A-04 | DOCUMENTATION_ONLY | impacto C do D-5A-2 maior que o previsto: 18 casos `SUM_X24` + `test_sum_applies_integration_factor` (contrato previa 6) | atualizados por DR-5A-2 |
| F5A-05 | DOCUMENTATION_ONLY | entradas do fixture REAL_DERIVED dependem da posição em `required_inputs`; troca de entrada muda valores a jusante sem mudança de fórmula. Provado com a sonda de atribuição | recomendação: rodar a sonda em todo re-baseline que troque entradas |
| F5A-06 | DOCUMENTATION_ONLY | desempenho medido +30% por data (grafo +0,4%) | campo de tempo de execução; longe do limite |
| F5A-07 | REQUIRES_FOLLOWUP (decisão) | testes de recusa do re-baseline (4C) fixavam `"B1"`; corrigidos para o próximo ID do registro. Teste fora do inventário 4C, logo fora da regra "só C" | **decisão da engenheira** |
| F5A-08 | DOCUMENTATION_ONLY | scripts de evidência 2.6C (`analysis_stage2_6c.py`) e 3.3C (`analysis_stage3_3c.py`, com `SUM_X24`) fixam o conteúdo da época. No HEAD divergem por construção; não foram editados. A 2.6C é verificada em clone (`test_17b`); a 3.3C não é executada por teste | histórico |

Nenhum BLOCKER aberto. As pendências de negócio e as colunas OBS seguem inalteradas e não bloqueiam.

## 9. Verificações finais

| verificação | resultado |
|---|---|
| suíte completa (HEAD) | **2085 passed**, 0 falhas (HEAD `ee05c0c` + documentos de fechamento) |
| `rebaseline.py --check` | PASS, `current` = B1 |
| `b0_reproduction.py` (clone `e262e03`, DR-5A-3) | **PASS**: 32 BIT_A_BIT, 8 EQUIVALENTE (só tempo de execução), 0 DIVERGENTE |
| `git diff --stat main -- app` | 3 arquivos autorizados (§4) |
| `data/workbooks/` | +2 anexos; nenhum removido |

## 10. Gate

| # | critério | resultado |
|---|---|---|
| 1 | pré-requisitos reconciliados (e262e03, 2040 passed, B0, SHA dos anexos) | PASS |
| 2 | F5A-01 reconfirmado e resolvido; nenhum EQ muda de alvo; aposentados registrados; sem reuso | PASS |
| 3 | 5A.2a sem mudança de seeds; livro inicializado de forma determinística | PASS |
| 4 | energy v9 e MaxHT v13 com os SHA aprovados; workbooks antigos preservados | PASS |
| 5 | D-5A-2: builder e runtime recusam fator ≠ 1; nenhuma regra com fator ≠ 1; checagem dimensional mantida | PASS |
| 6 | 5 unidades novas nos dois validadores | PASS |
| 7 | só testes C atualizados (com justificativa); nenhum H/E/S/W alterado; nada apagado, pulado ou afrouxado | **PASS** (após decisão F5A-07, §13): F5A-07 alterou testes REG fora do inventário, sem afrouxar; aceito pela engenheira |
| 8 | B1 proposto, revisado item a item, aprovado; `--check` PASS | PASS |
| 9 | expectativas da Fase 1 confirmadas (448/460, 29/13/16, IDs novos e aposentados) | PASS |
| 10 | mutação 100%; controle positivo aceito | PASS |
| 11 | suíte completa verde | PASS (2085 passed) |
| 12 | `app/` só nos pontos autorizados; `data/` só via builder (+ 2 workbooks) | PASS |
| 13 | pendências registradas (append-only); nenhum BLOCKER aberto | PASS |

**`FINAL_STAGE_5A_GATE = PASS (após decisão F5A-07)`.** Os 13 critérios dão PASS. Antes da decisão (§13), o resultado era `READY_FOR_DECISION`.

## 11. Limitações

- O oracle numérico continua sendo o fixture sintético. A 5A não valida valores de negócio de energy e max_ht.
- `area_04_13`, `alumina` e `maintenance` continuam sem carga: F-01 tem 16 `PENDING_LOAD`.
- O ramo multiplicativo de `temporal_aggregation_service.py` ficou inalcançável, mas não foi removido, porque a superfície autorizada era só o ponto de validação.

## 12. Comandos de reprodução

```
python -m tools.workbook_seed                                   # seeds idênticos aos versionados
python -m pytest -q                                             # suíte completa
python audit/baselines/rebaseline.py --check                    # registro (current = B1)
python audit/stage5a/phase1_probe.py                            # F5A-01 sem/com livro
python audit/stage5a/analysis_interblock_5a.py --no-write       # análise independente 2.6C no conteúdo vigente
python audit/stage5a/b1_value_attribution.py                    # atribuição das diferenças de valor do B1
python audit/stage5a/mutation/run_mutation_5a.py                # 13 mutantes
# B0 íntegro como histórico (DR-5A-3):
git clone --shared --no-checkout . /tmp/b0 && git -C /tmp/b0 checkout e262e03 && (cd /tmp/b0 && python -I audit/stage4c/b0_reproduction.py)
```

## 13. Decisão pós-gate (2026-10-04)

Decisão da engenheira responsável: **F5A-07 ACEITO**.

- Os testes de `tests/test_stage4c_baseline_registry.py` fixavam `"B1"` como "próximo ID livre". Era um defeito latente da 4C: depois de qualquer re-baseline, o teste passaria a exercitar uma recusa diferente da que declara.
- Derivar o próximo ID do registro preserva a intenção e todas as asserções. Não é afrouxamento.
- Classificação: correção de teste de infraestrutura, fora do inventário C da 4C, autorizada.

Efeito: o critério 7 passa a PASS e o resultado vira **`FINAL_STAGE_5A_GATE = PASS (após decisão F5A-07)`**.
