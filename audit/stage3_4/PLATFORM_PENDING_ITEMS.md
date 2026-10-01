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

---

## Adição datada — 2026-10-01: Stage 4A (area_41 no universo integrado)

Adição append-only. As seções acima não foram reescritas.

| item | estado após a 4A | fonte |
|---|---|---|
| Stage 4A — area_41 incluído na regressão integrada (5 blocos: 446 alvos, 458 nós, 13 transferências; 0 diferenças nos 421 alvos anteriores) | **concluída** (gate no fechamento 4A) | `audit/stage4a/STAGE_4A_FINAL_CLOSURE.md` |
| F-01 — 16 vínculos `PENDING_LOAD` | **continua aberto** (16 `PENDING_LOAD`, inalterados; o `hes` do area_41 continua pendente de `maintenance`) | `audit/stage4a/STAGE_4A_DECISION_CONTRACT.md` §1.5 |
| F-02 — execução oficial das cadeias | **continua aberto** (plano oficial do area_41: 3 OK + 22 `INTERBLOCK_SOURCE_NOT_LOADED`) | idem |
| F-03 — oracle numérico independente | **parcialmente atendido**: `INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)`. As 20 equações e as 10 agregações do area_41 foram confrontadas com um oracle Python puro, com 5 015 de 5 015 comparações concordando. Valida fidelidade ao workbook A41 v9, **não** correção de negócio. Os demais blocos continuam sem oracle independente completo | `audit/stage4a/oracle/` |
| D-TAX-02 | já estava `CLOSED / APPLIED` antes da 4A (registro mantido) | §4 acima |
| pontos de negócio do area_41 (coluna `OBS` e pontos novos N1..N8) | `REQUIRES_FOLLOWUP` com o cliente; **não bloqueiam** | `STAGE_4A_DECISION_CONTRACT.md` §3.1, §4 |
| F4A-01 — `"F"` vira `NO_APPLICABLE_RULE` com `detail = None` (o prompt 4A esperava `detail = "F"`) | `REQUIRES_FOLLOWUP` (decisão de contrato; exige mudança em `app/`) | `STAGE_4A_DECISION_CONTRACT.md` §6 |
| comparação com a planilha Excel original (aba "Forecast A41") | **aberta**; só o gancho (formato de extrato) foi entregue | `audit/stage4a/oracle/EXCEL_COMPARISON_HOOK.md` |

---

## Adição datada — 2026-10-01: Stage 4B (cobertura anual, virada de ano e ciclos)

Adição append-only. As seções acima não foram reescritas.

| item | estado após a 4B | fonte |
|---|---|---|
| cobertura anual completa (antes YTD parcial de 32 datas; `STAGE_3_FINAL_CLOSURE.md` L4) | **atendida no fixture REAL_DERIVED**: T1 2026-01-01..2027-01-31 (396 datas), T3 2026-01-01..2028-03-02 (792 datas, contexto único), 365 janelas anuais por identidade ao fim de 2026 e de 2027; todas as agregações recalculadas pelo oracle temporal independente | `audit/stage4b/STAGE_4B_FINAL_CLOSURE.md` |
| virada de ano 31/12 → 01/01 | **atendida**: o ano novo nasce com 1 janela; o período encerrado fica imutável (snapshot por hash); entrada anual do ano novo ausente ⇒ falha explícita, sem carry-over | idem, E1/E3/E4 |
| ano bissexto e meses de 28/29/30/31 dias | **atendida**: T2 2028 (29 janelas em fevereiro; 60 janelas anuais em 29/02) | idem, E5 |
| longo prazo (desempenho) | **observado**: cerca de 0,17 → 0,32 s por data ao longo de um ano (cresce com a janela anual e reinicia em 1º de janeiro); 792 datas em cerca de 5 min. Sem degradação acima do limite (3,0) | idem §desempenho |
| ciclo `production ↔ yield` no nível de variável/instância (`STAGE_3_FINAL_CLOSURE.md` L5) | **fechado estruturalmente**: grafo **acíclico** no nível de instância (1 227 nós) e de variável; o ciclo existe só entre blocos; nenhuma defasagem `t-1`. A convergência numérica de um ciclo real continua sem objeto, pois não há ciclo de instância | idem §ciclos |
| política de lacunas | **REQUIRES_FOLLOWUP** (F4B-02): lacuna ⇒ falha explícita (`VariableNotFoundError` genérico). Uma execução não pode começar no meio do mês ou do ano sem o histórico desde o dia 1 / 1º de janeiro. É preciso decidir como carregar o realizado anterior em uso operacional | idem, E2 |
| ano fiscal | **pendência de negócio** (DR-4B-3): a plataforma usa ano-calendário. Confirmar com o cliente se o ano de budget coincide com o calendário | idem |
| F-01 (16 `PENDING_LOAD`) e F-02 (execução oficial) | **continuam abertos** (inalterados pela 4B) | — |
