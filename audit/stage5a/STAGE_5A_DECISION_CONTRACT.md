# Stage 5A — contrato de decisão: unidades, IDs estáveis de equação, fim do ×24, energy v9 e max_ht v13

Estado: **Fase 1 concluída**, sem mudança de produção.
- Branch: `feature/stage-5a-contract-energy-maxht`, a partir de `main` = `e262e03`.
- Evidência recalculada: `audit/stage5a/phase1_probe.py` → `evidence/phase1_probe.json`.
  - Roda num clone temporário com os anexos e o código atual.
  - Não importa `app/`.

## 0. Pré-requisitos (Fase 0, recalculados)

| item | valor |
|---|---|
| `main` | `e262e03` (4B + 4C) |
| árvore | limpa |
| suíte | **2040 passed** |
| `rebaseline.py --check` | PASS, `current` = B0 |
| anexo energy v9 | `731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2` (= §1 do prompt) |
| anexo MaxHT v13 | `c9818920b3994ae6aaeef5f237e59dd94d8e1b8647f0bf64426fb5f3d9f0aa98` (= §1 do prompt) |

## 1. F5A-01 reconfirmado: EQ atribuídos por posição

O gerador atual (`seeds.build_equations`, contador `next_id`) foi rodado com os workbooks novos num clone temporário. EQ cujo par (variável alvo, escopo da instância) muda em relação a B0:

| bloco | EQ com outro alvo (sem livro) | lista |
|---|---|---|
| energy | **14** | EQ18011 … EQ18024 (todo EQ depois da equação nova de `evaporado_total_evaporacao`) |
| max_ht | **9** | EQ13001, EQ13022 … EQ13029 |
| yield, production, area_41 | 0 | — |

Confere com o `[ref]` (14 e 9).

**Com o livro de equações** (D-5A-4, simulação independente na mesma sonda), nenhum EQ existente muda de alvo:

| bloco | EQ mantidos | EQ novos | EQ aposentados | expressão mudou, mesmo ID |
|---|---|---|---|---|
| energy | 24 | **EQ18025** (`evaporado_total_evaporacao` diário linha/L1_L7) | — | — |
| max_ht | 28 | **EQ13030** (`alimentacao_evap_total`), **EQ13031** (`lth_total_ag`) | **EQ13001** (`alimentação_evap_total`, nome aposentado por D-5A-3) | **EQ13019** (passa a ler os IDs renomeados) |
| demais | todos | — | — | — |

O sintoma da pré-lista 4C (`test_energia_bayer…`: `VAR18027 + VAR18040` → `VAR18038*2.455609`) era EQ18019 apontando para outra equação. Com o livro, EQ18019 continua `VAR18027 + VAR18040`.

## 2. Desenho do livro de equações (D-5A-4)

- **Formato.** `data/id_ledger/<bloco>.json` ganha duas chaves novas. As chaves existentes (`block`, `entries`, `retired`) ficam inalteradas, então o formato é retrocompatível.
  - `equations`: lista de `{equation_id, kind, name, frequency, scope_type, scope_value, equation_scope_value}`;
  - `retired_equations`: os mesmos campos + `retired_in`.
- **Identidade.** Identidade da variável alvo (`kind, name, frequency, scope_type, scope_value`) + `scope_value` da instância da equação (a linha). Uma identidade repetida no mesmo build é erro explícito.
- **Numeração.**
  - Identidade presente no livro mantém o ID, **mesmo que a expressão mude**.
  - Identidade nova recebe `max(id_base, maior EQ emitido, ativo ou aposentado) + 1`, em ordem de linha do workbook.
  - Identidade ausente é aposentada, de forma permanente; o ID nunca é reutilizado.
- **Sem a seção** (livro anterior à 5A), a numeração é a sequencial de hoje. Por isso a inicialização reproduz B0.
- **Inicialização (5A.2a).** `python -m tools.workbook_seed` sobre os workbooks atuais (energy v6, MaxHT v10): os livros ainda não têm a seção, os IDs saem sequenciais e iguais a B0, e o livro passa a gravá-los. É determinística, porque depende só do workbook e do livro versionado.
- **Integração.**
  - `build_canonical_model` guarda o livro no modelo.
  - `seeds.build_equations` consulta o livro e registra as atribuições no modelo.
  - `id_ledger.ledger_payload(model, previous)` grava a seção, com a mesma assinatura.
  - O manifesto e as `pending_contract_decisions` usam o ID atribuído.
- **DR-5A-1.** O builder emite `equations.json` e as linhas de equação do manifesto **em ordem crescente de EQ**. Uma equação nova entra no fim, sem deslocar as demais. Com IDs sequenciais a ordem é a de hoje, então os seeds ficam byte a byte iguais no 5A.2a.
- **Invariantes S** passam a cobrir EQ, com teste novo no 5A.2a:
  - sem renumeração;
  - aposentado no `retired_equations`;
  - sem reuso.

## 3. Desenho do D-5A-2 (fim do ×24)

- **Builder.** Em `tools/workbook_seed/seeds.py::build_aggregation_rules`, depois de `required_sum_factor`:
  - fator `None` continua com o erro dimensional atual;
  - fator ≠ 1 passa a dar `CanonicalModelError`, com a mensagem: `"<arquivo> linha N (<alvo>): SUM de <origem> (<unidade>) exige fator <f>; a conversão para quantidade diária deve ser explícita no workbook por uma variável intermediária '<origem>_ag' (<numerador>/d) — D-5A-2"`.
  - A regra gravada passa a ter sempre `integration_factor = 1`.
- **Runtime.** No ponto exato da validação, `app/domain/forecast/aggregation.py::AggregationRule.__post_init__`: `integration_factor ≠ 1` dá `InvalidAggregationRuleError`, para qualquer tipo de agregação.
  - O ramo multiplicativo de `temporal_aggregation_service.py` fica inalcançável e não é editado (fora da superfície autorizada).
  - A checagem dimensional (`required_sum_factor`, `check_sum_dimensions`) continua.
- **Inventário das SUM com fator ≠ 1:**

  | | regras |
  |---|---|
  | B0 | **2**: `AGR-MAX_HT-LTH_TOTAL_SOMATORIO-GRUPO-L1_L7-MENSAL-SUM` e `…-ANUAL-SUM` (origem `lth_total`, m³/h) |
  | workbooks novos | **0**: no MaxHT v13, `lth_total_somatorio` soma `lth_total_ag` (m³/d) |

  Confere com o `[ref]`. Total de SUM em B0: production 10 + max_ht 20 = 30.

## 4. Expectativas do re-baseline B1 (recalculadas pela sonda; o ensaio R1 da 4C confirmou os universos)

| item | B0 → B1 |
|---|---|
| energy variáveis | 52 → 53: **+VAR18053** (`retirada_total_condensado_area13`, entrada m³/h, fonte `area_04_13`). VAR18031 (`evaporado_total_evaporacao`) passa a `calculado` |
| energy equações | 24 → 25: **+EQ18025** (VAR18031 = `VAR18053 / 1`). Nenhum EQ existente muda |
| energy regras de agregação | 11 → 11 |
| max_ht variáveis | 116 → 117: **VAR13001–VAR13006 aposentadas** (`alimentação_evap*`) e **VAR13117–VAR13123 novas** (`alimentacao_evap*` + `lth_total_ag`) |
| max_ht equações | 29 → 30: **−EQ13001**, **+EQ13030, +EQ13031**. EQ13019 mantém o ID com expressão nova |
| max_ht regras | 78 → 78: 4 IDs trocam de grafia (`ALIMENTAÇÃO` → `ALIMENTACAO`, D-5A-3). As 2 SUM de `lth_total_somatorio` passam a fator 1 |
| yield / production / area_41 | inalterados |
| vínculos | 29 declarados / 13 válidos / 16 pendentes / 0 rejeitados. Pendentes trocados: `energy.VAR18031<-area_04_13` → `energy.VAR18053<-area_04_13`; `max_ht.VAR13003<-alumina` → `max_ht.VAR13119<-alumina` |
| plano oficial | 446 → **448** alvos |
| universo 3.4C | 421/427 → **423/429** |
| universo 4A | 446/458 → **448/460** |
| eventos por data | 896 → **904** (13 transferências / 67 eventos inalterados) |

Os nós de equação do plano usam os EQ estáveis. No `nodes.csv`, portanto, aparecem só os acréscimos (EQ13030, EQ13031, EQ18025) e a saída de EQ13001, sem troca de alvo entre IDs.

## 5. Pré-lista C revisada (a partir dos 42 da 4C)

**Previstos para deixar de falhar com D-5A-4** (IDs de EQ estáveis):
- `test_energy_seed_contract.py::test_energia_bayer_and_energia_media_frct_bind_by_id_not_name`;
- `test_energy_seed_contract.py::test_explicit_scoped_references_are_extracted`.

Os itens restantes, por categoria:

| categoria | itens |
|---|---|
| (a) contagem/conteúdo do workbook novo | energy seed: `test_entity_counts_match_the_workbook`, `test_equation_and_aggregation_counts`, `test_all_ids_are_inside_the_energy_range_and_unique`, `test_energy_ids_do_not_collide_with_other_blocks`, `test_variable_frequency_distribution`, `test_variable_type_distribution`, `test_scope_distribution`, `test_variable_instances_are_materialized_by_the_real_resolver`; max_ht: `test_entity_counts`, `test_all_math_equations_parse_successfully`, `test_full_seed_root_loads_without_errors`; 2.4: `test_t24_02_each_block_builder_consumes_its_approved_workbook[energy]`, `[max_ht]`, `test_t24_02_total_rows_and_equations_match_stage_2_3`, `test_t24_06_max_ht_v9_ignores_trailing_empty_rows`; 2.6B `test_17_max_ht_is_the_canonical_block_name` |
| (b) vínculo trocado | `test_stage2_6_interblock_contract.py::test_15_every_real_fonte_is_classified`, `test_stage2_6b…::test_18_all_real_links_of_the_five_workbooks`, `test_stage2_6c…::test_17_independent_analysis_matches_the_builder` |
| (c) fator de integração | `test_aggregation_dimensions.py::test_sum_factors_follow_the_approved_workbook_units`. Também, por **D-5A-2**, testes do contrato atual do runtime que constroem SUM com fator 24: `test_aggregation_dimensions.py::test_sum_applies_integration_factor` e os 6 casos `SUM_X24` de `test_stage3_3c_state_aware_aggregation.py` (a confirmar no 5A.2c) |
| (d) fixture de runtime | `test_energy_runtime_contract.py`: 20 itens (13 ERROR de fixture + 7 FAILED). VAR18053 entra como entrada sintética e VAR18031 passa a calculada |

Regra:
- só testes C são atualizados, com justificativa;
- R passa pelo re-baseline;
- falha H/E/S/W é defeito real.

## 6. Decisões

| id | decisão | estado |
|---|---|---|
| D-5A-1 | unidades `kWh/tv`, `tv/MWh`, `tv/t carvão`, `GJ/d`, `m³/d` nos dois validadores | aprovada (engenheira) |
| D-5A-2 | SUM só com origem diária (fator 1); builder e runtime recusam fator ≠ 1; checagem dimensional mantida | aprovada (engenheira) |
| D-5A-3 | renomeação `alimentação_evap*` → `alimentacao_evap*`: VAR13001–13006 aposentados, IDs de regra mudam | aprovada (engenheira) |
| D-5A-4 | livro de IDs de equação (§2) | aprovada por padrão |
| DR-5A-1 | equações emitidas em ordem crescente de EQ | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-5A-2 | testes de runtime com fator 24 são C do contrato vigente; viram contrato D-5A-2: recusa explícita + conversão explícita por `_ag`, preservando a aritmética testada | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-5A-3 | `b0_reproduction.py` no HEAD da 5A **diverge por construção** (comportamento mudou). A integridade de B0 como histórico é verificada por `rebaseline.py --check` (sha256 de todos os arquivos B0) e pela reprodução num clone em `e262e03` | `PROPOSED_ACCEPTED_BY_DEFAULT` |

## 7. Findings da Fase 1

| id | classe | finding |
|---|---|---|
| F5A-01 | BLOCKER (a resolver nesta stage) | EQ por posição: 14 (energy) + 9 (max_ht) mudariam de alvo |
| F5A-02 | DOCUMENTATION_ONLY | no MaxHT v13, EQ13019 mantém a identidade e muda a expressão (passa a ler os IDs renomeados): mudança real de conteúdo, visível no DIFF_REPORT |
