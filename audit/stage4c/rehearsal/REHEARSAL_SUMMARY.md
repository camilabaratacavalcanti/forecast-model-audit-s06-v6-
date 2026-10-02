# Stage 4C.3 — ensaio da 5A e prova de obrigatoriedade do re-baseline

Tudo rodou em clones temporários (`rehearse_5a.py`): `git clone --shared` do HEAD + árvore atual de `audit/` e `tests/`. A árvore de trabalho não foi tocada (`working_tree_untouched` = True). Os workbooks anexos **não** entraram no repositório. As falhas foram classificadas pelo inventário 4C (`guard_inventory.json` + adendo F4C-05).

## R1 — ensaio real da 5A (energy v9, MaxHT v13, 5 unidades novas, seeds regenerados)

- workbooks: energy v9 `731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2`, MaxHT v13 `c9818920b3994ae6aaeef5f237e59dd94d8e1b8647f0bf64426fb5f3d9f0aa98`
- gerador: interblock: 29 vínculos declarados em fonte, 13 válidos, 16 pendentes de carregamento, 0 rejeitados

| fase | resultado da suíte | falhas por classe |
|---|---|---|
| antes do re-baseline | 42 failed, 1982 passed, 16 errors in 814.59s (0:13:34) | C 42, R 16 |
| re-baseline `B1-ensaio` | rebaseline rc=0, aprovação rc=0 | — |
| depois da aprovação | 29 failed, 1998 passed, 13 errors in 778.83s (0:12:58) | C 42 |

Antes do re-baseline falharam só testes C e R. Depois da aprovação falham **só testes C**: os mesmos 42, que formam a pré-lista da 5A em `STAGE_4C_FINAL_CLOSURE.md`. Nenhum teste H, E, S ou W falhou em nenhuma fase.

DIFF_REPORT completo: `R1_B1_ENSAIO_DIFF_REPORT.md`. Resumo:
- energy: +1 variável (**VAR18053**, entrada nova); +1 equação (EQ18025). VAR18031 passa a ser calculada (EQ18011 = `VAR18053 / 1`) e vira alvo;
- max_ht: 116 → 117 variáveis. **VAR13001–VAR13006 aposentadas** (no `retired` do ledger) e **VAR13117–VAR13123 novas**; +1 equação (EQ13030). 4 IDs de regra de agregação trocam de grafia (`ALIMENTAÇÃO` → `ALIMENTACAO`, F4C-11);
- vínculos: 29 declarados / 13 válidos / 16 pendentes / 0 rejeitados (inalterados). Pendentes trocados: `energy.VAR18031<-area_04_13` → `energy.VAR18053<-area_04_13` e `max_ht.VAR13003<-alumina` → `max_ht.VAR13119<-alumina`;
- plano oficial: 446 → 448 alvos (289 bloqueados);
- universos: 3.4C 421/427 → 423/429; 4A 446/458 → 448/460; eventos por data 896 → 904; transferências 13/67 iguais.

## R2 — prova de obrigatoriedade do re-baseline

| cenário | mudança | resultado | falhas por classe |
|---|---|---|---|
| R2a | `app/`: comentário + unidade nova `kWh/tv` no enum (sem efeito de comportamento) | 2040 passed in 858.06s (0:14:18) | — |
| R2b | `data/seed/area_41/equations.json`: EQ16001 19.475 → 19.476, **sem re-baseline** | 8 failed, 2032 passed in 858.07s (0:14:18) | C 1, FORA_DO_INVENTARIO 3, R 3, S 1 |

No R2b falham os 3 testes R que comparam o comportamento vivo com a referência:
- 4A integrado: `EVIDENCE_REGRESSION`;
- 4B T2;
- mutação 4B (controle positivo).

Também detectam a mudança:
- o oracle do area_41 (C, fidelidade ao workbook);
- o build reproduzível dos seeds (S, `test_14`);
- o contrato de consumo do workbook 2.4 (C).

A mudança de comportamento não passa sem re-baseline.

Falhas R2b:
- `tests/test_stage4a_oracle.py::test_live_oracle_agrees_with_engine_on_20_equations_and_25_hes_combinations`
- `tests/test_stage2_4_workbook_contract.py::test_t24_01_builder_output_equals_versioned_seed[area_41]`
- `tests/test_stage2_4_workbook_contract.py::test_t24_01_every_workbook_row_is_represented_in_the_seed[area_41]`
- `tests/test_stage4a_oracle.py::test_negative_oracle_detects_a_deviating_engine_behaviour`
- `tests/test_stage4a_integrated.py::test_live_five_block_regression_passes_and_reproduces_committed_evidence`
- `tests/test_stage4b_mutation.py::test_live_evidence_mutations_detected_and_controls_accepted`
- `tests/test_stage4b_temporal.py::test_live_t2_leap_year_passes`
- `tests/test_stage2_6c_interblock_final.py::test_14_repeated_builds_are_byte_identical_and_order_independent`

