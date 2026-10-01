# Lista mestre de pendências da plataforma

Estado após **D-TAX-02**. A lista separa:
- pendências **funcionais**;
- pendências de **dados**;
- **dívidas arquiteturais**;
- **decisões concluídas**;
- registros apenas **históricos**.

As fontes de cada item estão indicadas. Nenhuma pendência funcional foi resolvida por D-TAX-01 ou D-TAX-02.

## 1. Pendências funcionais (abertas)

| id | pendência | estado | fonte |
|---|---|---|---|
| F-01 | carregamento operacional dos **16 vínculos `PENDING_LOAD`**: maintenance 9, temperature_lp 3, forecast 2, area_04_13 1, alumina 1 | **PENDING_LOAD** (não resolvido) | `data/seed/interblock_links.json`; `STAGE_3_FINAL_CLOSURE.md` §15, §20 |
| F-02 | execução oficial das cadeias fora do conjunto carregado (287 dos 446 alvos oficiais bloqueados) | aberta (DR-1) | `STAGE_3_FINAL_CLOSURE.md` §17 L9 |
| F-03 | oracle numérico independente completo (`INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE`) | aberta | `STAGE_3_FINAL_CLOSURE.md` §17 L1 |
| F-04 | convergência variável a variável do ciclo production ↔ yield | aberta | `STAGE_3_FINAL_CLOSURE.md` §17 L5 |
| F-05 | cobertura temporal anual completa (virada de ano, ano fiscal) | aberta | `STAGE_3_FINAL_CLOSURE.md` §17 L4 |

## 2. Pendências de dados (abertas)

| id | pendência | estado | fonte |
|---|---|---|---|
| DA-01 | workbooks ausentes: maintenance, forecast, temperature_lp, area_04_13, alumina (produtores dos 16 `PENDING_LOAD`) | aberta | `STAGE_3_FINAL_CLOSURE.md` §20 |
| DA-02 | conteúdo dos blocos de custo (32000–34999): nenhuma entidade existe nas faixas | aberta (fora do escopo das decisões de taxonomia) | `STAGE_3_4_TAXONOMY_D_TAX_02.md` §3.4 |

## 3. Dívidas arquiteturais

| id | dívida | estado | bloqueador funcional | fonte |
|---|---|---|---|---|
| TD-TAX-01 | **TECH-DEBT — Duplicação Física da Taxonomia Canônica** (`app/validation` × `tools/workbook_seed/taxonomy.py`) | **OPEN** | não | `TECH_DEBT_TAXONOMY_DUPLICATION.md` |

## 4. Decisões concluídas

| id | decisão | estado | fonte |
|---|---|---|---|
| D-TAX-02 | **Crosswalk histórico dos três blocos de custo** (`custo_budget → budget_cost`, `custo_forecast_bdgt → budget_forecast_cost`, `custo_forecast_real → actual_forecast_cost`; os três **CONFIRMED**) | **CLOSED / APPLIED** | `STAGE_3_4_TAXONOMY_D_TAX_02.md`; `taxonomy_migration/cost_crosswalk_d_tax_02.json` |
| D-TAX-01 | taxonomia canônica de 29 blocos; 30000–30999 = `thickener_flocculant` | **APPLIED** | `STAGE_3_4_TAXONOMY_MIGRATION.md` |
| D32-01 | execução oficial fora do escopo da Stage 3 | `CLOSED_FOR_STAGE_3_SCOPE` | `STAGE_3_4A_DECISION_CONTRACT.md` (DR-1) |
| D32-02 | identidade temporal por janela efetiva | resolvida (3.3B) | `STAGE_3_FINAL_CLOSURE.md` §3.1 |
| Stage 3 | `FINAL_STAGE_3_GATE` | **CLOSED** (PASS) | `STAGE_3_FINAL_CLOSURE.md` §19 |

**Item removido por D-TAX-02.** O item "pareamento dos três blocos de custo continua sendo inferido" vinha do relatório D-TAX-01 (§18, limitação 2). Ele **saiu da lista de pendências**. Motivo: os três pares foram confirmados com evidência explícita de repositório (commit `1d3276e` e a mesma faixa nos três registries) e aplicados como crosswalk normativo, protegido por guard e testes. Nenhum par permaneceu `UNRESOLVED`.

## 5. Registros históricos (sem ação)

| registro | estado | fonte |
|---|---|---|
| G1–G5 (lacunas do auditor da 3.4C) | remediados na 3.4D | `STAGE_3_FINAL_CLOSURE.md` §12 |
| lista D26-01 da Stage 2.6B (nomes históricos `custo_*`, sem `budget_vs_forecast`) | substituída por D-TAX-01; os nomes são traduzidos pelo crosswalk D-TAX-02 | `audit/stage2_6b_interblock_closure/` |
| nome `monthly_ppt_assumptions` (30000–30999) | aposentado por D-TAX-01 | `STAGE_3_4_TAXONOMY_MIGRATION.md` |
| evidência versionada das 3.4B–3.4E | descreve o estado da época; não regenerada | `STAGE_3_FINAL_CLOSURE.md` §18 |
