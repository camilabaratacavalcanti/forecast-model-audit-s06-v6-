# Stage 5A — revisão do re-baseline B1 (proposta)

- Proposta: `python audit/baselines/rebaseline.py --id B1 --stage 5A --reason "energy v9, max_ht v13, livro de equações, fim do ×24, unidades novas"`.
  - Árvore limpa em `a12954a` (commit de comportamento).
  - Os 17 passos terminaram com returncode 0, incluindo o recálculo independente da 4A e da 4B e as 4 verificações `--no-write` contra a referência B1.
  - Resultado: `PROPOSED`; o `current` continua em B0.
- Relatório revisado: `audit/baselines/B1/DIFF_REPORT.md`.
- Expectativas usadas na revisão: `STAGE_5A_DECISION_CONTRACT.md` §4.
- Sonda de atribuição recalculada nesta stage: `audit/stage5a/b1_value_attribution.py` → `evidence/b1_value_attribution.json` (**PASS**).

**Veredito: toda diferença do DIFF_REPORT é explicada pela mudança da 5A. Nenhuma divergência sem explicação, portanto nenhum BLOCKER.**

## 1. Conteúdo (DIFF §1) x contrato §4

| item | DIFF_REPORT | contrato §4 | revisão |
|---|---|---|---|
| energy variáveis | 52 → 53, +VAR18053 | 52 → 53, +VAR18053 | ✔ |
| energy equações | 24 → 25, +EQ18025 | idem | ✔ (nenhum EQ existente muda: livro D-5A-4) |
| max_ht variáveis | 116 → 117, +VAR13117..123, −VAR13001..006 | idem | ✔ (D-5A-3 + `lth_total_ag`) |
| max_ht equações | 29 → 30, +EQ13030, +EQ13031, −EQ13001 | idem | ✔ (EQ13019 com expressão nova: F5A-02) |
| max_ht regras | 78 → 78, 4 trocam de grafia `ALIMENTAÇÃO` → `ALIMENTACAO` | idem | ✔ |
| yield, production, area_41 | inalterados | inalterados | ✔ |
| aposentados no livro | max_ht VAR13001..006 | idem | ✔ |
| vínculos | 29/13/16/0; pendentes `energy.VAR18031<-area_04_13` → `energy.VAR18053<-area_04_13`, `max_ht.VAR13003<-alumina` → `max_ht.VAR13119<-alumina` | idem | ✔ |
| workbooks | energy v6 → v9 (`731f71e9…`), MaxHT v10 → v13 (`c9818920…`) | idem | ✔ (SHA reconferidos na 5A.2b) |

## 2. Conjuntos R (DIFF §2), arquivo a arquivo

### stage3_2_plan

- `plan_evidence.csv`: 446 → 448.
  - Entram 7 alvos: VAR13117, 118, 120, 121, 122, 123 e VAR18031.
  - Saem 5 alvos: VAR13001, 002, 004, 005, 006.
  - VAR13119 e VAR13003 não aparecem como alvo porque são **entradas** pendentes de `alumina`. VAR18031 passa a alvo porque agora é calculado; VAR18053 é a entrada.
  - Nenhuma linha comum muda.
  - Saldo +2 = contrato.
- `analysis_summary.json`:
  - `targets_blocked_official` 287 → 289, porque os 2 alvos novos são bloqueados por pendência oficial;
  - `blocked_by_block.area_04_13` +1: VAR18031, calculado de VAR18053 ← area_04_13;
  - `maintenance` +1: VAR13123 (`lth_total_ag` = `lth` × 24), que lê o `lth` de production, já bloqueado por maintenance;
  - os 5 `alimentacao_*` substituem os 5 `alimentação_*`, todos bloqueados por `alumina` (saldo 0).
  - ✔
- `transfer_evidence.csv`: igual. ✔

### stage3_4c_integrated (fixture REAL_DERIVED, 4 blocos)

- Universo 421/427 → **423/429**; `EQUATION` 218 → 220. Igual ao contrato. ✔
- `targets.csv`: +7/−5 como acima. **93 linhas comuns alteradas**:
  - 20 só em `planner_nodes`/`executed_nodes`: o fecho de dependência passou a conter EQ18025, EQ13030/31 e as regras renomeadas;
  - 91 em `final_results_2026-02-01` (71 max_ht, 20 energy), por exemplo VAR13009 0,012977… → 0,013073….
  - **Causa (provada):** o fixture atribui a cada entrada `1 + 0,01·i + …`, com `i` = posição em `plan.required_inputs`. A 5A troca duas entradas (VAR13003 → VAR13119 e VAR18031 → VAR18053), o que desloca `i` das entradas seguintes.
  - A sonda `b1_value_attribution.py` reexecuta o motor da 5A nas 32 datas com as entradas reindexadas pela ordem de B0 (clone `e262e03`), por identidade. Resultado:
    - **416/416** alvos comuns são **idênticos** a B0;
    - os 5 alvos renomeados (`alimentacao_*`) são idênticos aos antigos (`alimentação_*`);
    - VAR18031 (agora `VAR18053 / 1`) é idêntico à entrada que B0 lhe dava;
    - VAR13067 (`lth_total_somatorio`, SUM mensal) é **idêntico**: a SUM de fator 1 sobre `lth_total_ag` = `VAR13063 × 24` reproduz exatamente o ×24 antigo (D-5A-2 preserva a aritmética).
    - Único alvo sem par: VAR13123 (`lth_total_ag`, identidade nova).
  - Não há mudança de fórmula fora das previstas (EQ13019, EQ13030/31, EQ18025).
- `nodes.csv`: 427 → 429.
  - Entram EQ13030, EQ13031 e EQ18025; sai EQ13001.
  - As 4 regras `ALIMENTAÇÃO` são substituídas pelas `ALIMENTACAO`.
  - EQ13021 passa a ter VAR13123 entre os dependentes, e EQ18011 passa a ter EQ18025 a montante.
  - As 257 linhas comuns alteradas resultam do deslocamento de `order` (inserções no plano topológico) e dos novos dependentes. ✔
- `temporal_coverage.csv`: 32 linhas, contagens por data 421/427 → 423/429. ✔
- `integrated_summary.json`:
  - hashes de grafo, store e resultados mudam (grafo novo + entradas reindexadas);
  - `nodes_executed` 427 → 429;
  - `orchestrator_vs_engine.compared` +256 = 8 instâncias × 32 datas;
  - posições de TRANSFER +1.
  - Determinismo preservado: HASH_SEED_A = B = RUN_A = RUN_B. ✔
- `transfers.csv`: igual (13 transferências). ✔

### stage4a_contract

- `independent.universe_5`: 446/458 → **448/460**, `equation_instances` 412 → 420, eventos 896 → **904**, `EQUATION` 238 → 240. Recálculo independente sem `app`: PASS.
- Composição do +8 de `equation_instances`: EQ18025 tem 7 instâncias (`linha/L1_L7`); EQ13030 e EQ13031 têm 1 cada (grupo); EQ13001 tinha 1. Total: 7 + 1 + 1 − 1 = +8. ✔
- `interblock_links_sha256` muda (2 pendentes trocados). `obs_register.csv` e `hes_decision_matrix.csv` iguais. ✔

### stage4a_integrated

- Universo 448/460, `previous` 423/429. ✔
- `non_regression_421`: `keys_compared` 33740 → 33996 (+256 = 8 × 32), `targets_compared` 421 → 423. O subconjunto de 4 blocos dentro de 5 blocos é idêntico ao isolado (`subset_store_sha256 == isolated_4_block_store_sha256 == reference_store_sha256`). ✔
- `targets.csv`/`nodes.csv`: mesmas explicações da 3.4C (inclui area_41, que não muda). ✔

### stage4b_contract / stage4b_temporal

- `derived_daily_instances` 376 → 384; crescimento do store +8 por data (1227 → 1235, 1143 → 1151, 1109 → 1117).
- Grafo de ciclos:
  - instâncias 1227 → 1235 nós, 2041 → 2049 arestas;
  - variáveis 505 → 507;
  - continua **acíclico**.
- Snapshots de período:
  - mês de 31 dias: +248 = 8 × 31;
  - mês de 30 dias: +240;
  - fevereiro: +224;
  - ano 2026: 405277 → 408197 = +2920 = 8 × 365.
  - A imutabilidade do período fechado (E4) continua: `at_turn == at_end`.
- `E2_gaps`: a mensagem passa a citar VAR13119 em vez de VAR13003. É a mesma entrada renomeada; a falha explícita na lacuna continua.
- Colisões: entidades 508 → 510 (+2 = +7 −5 entre variáveis), sem colisão.
- Prefix invariant (T1/T3 contra a 4A): mantido, com o novo store da 4A.
- Desempenho: média de 0,18 → 0,24 s por data e `estimate_seconds` maior.
  - Campo de **tempo de execução medido** (DR-4C-7). O grafo cresceu 0,4%; o resto é variação da máquina.
  - Razão último/primeiro 1,02 (T1), 0,99 (T2) e 0,93 (T3), longe do limite 3,0. DOCUMENTATION_ONLY.
- `reexecution.json` e `state_scenarios.json` iguais (T1, T2, T3). ✔

## 3. Conjuntos herdados (DIFF §3)

Não regenerados e iguais a B0: `stage3_4b_differential`, `stage3_4d_mutation`, `stage4a_oracle`, `stage4a_mutation`, `stage4a_closure`, `stage4b_oracle`, `stage4b_mutation`, `stage4b_closure`. São H/E e continuam verificados por sha256 (`--check`) e pelos testes H em clone. ✔

## 4. Findings da revisão

| id | classe | finding |
|---|---|---|
| F5A-05 | DOCUMENTATION_ONLY | Os valores de entrada do fixture REAL_DERIVED dependem da **posição** em `required_inputs`. Qualquer troca de entrada muda valores a jusante sem mudança de fórmula. Neste re-baseline, a sonda de atribuição provou que **todas** as 91 diferenças de valor vêm disso. Recomendação para stages futuras: rodar a mesma sonda em todo re-baseline que troque entradas |
| F5A-06 | DOCUMENTATION_ONLY | Desempenho medido +30% por data entre B0 e B1, com grafo +0,4%. Campo de tempo de execução (DR-4C-7), sem impacto em limite |

Nenhuma divergência sem explicação. **B1 pode ser aprovado.**
