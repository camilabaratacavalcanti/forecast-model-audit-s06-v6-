# Stage 4B — Fechamento: cobertura temporal anual, virada de ano e ciclos

| campo | valor |
|---|---|
| etapa | 4B (4B.1 contrato → 4B.2 harness temporal → 4B.3a oracle → 4B.3b mutação → 4B.4 fechamento) |
| baseline | `main` = `0a924e66cfd0774a13e46a332b460b770283a554` (4A mergeada) |
| branch | `feature/stage-4b-temporal-annual` (sem push, sem merge) |
| rótulo | `REAL_DERIVED_TEST_RESULT` (fixture REAL_DERIVED de 5 blocos; entradas DR-4A-5) |
| superfície de produção | `git diff --stat 0a924e6 -- app data tools` **vazio** |

---

## 1. Resumo executivo

O grafo integrado de 5 blocos foi executado por:
- **T1**: ano completo e virada 2026 → 2027 (396 datas);
- **T2**: 2028, ano bissexto (62 datas);
- **T3**: 2026-01-01 → 2028-03-02 num **único contexto** (792 datas).

Em todas as datas, alvos, nós, transferências, identidades e janelas estão corretos. Além disso:
- todo mês e todo ano encerrado ficou imutável;
- a reexecução é idempotente;
- uma entrada diferente a montante gera conflito explícito;
- não há carry-over de entrada;
- lacunas falham de forma explícita;
- as 32 primeiras datas são idênticas à 4A.

O oracle temporal independente recalculou **195 156 agregações**, todas iguais bit a bit. O grafo é **acíclico no nível de instância**; o `production ↔ yield` é ciclo só entre blocos. Mutação: 19/19 de evidência e 8/8 de código.

```text
FINAL_STAGE_4B_GATE = READY_FOR_DECISION   (critério 14: ver F4B-06)
```

---

## 2. Baseline (Fase 0)

| verificação | resultado |
|---|---|
| 4A na `main`; hashes `f3b6588`, `7877551`, `8095011` | sim; HASHES_OK |
| árvore | limpa |
| suíte | 1964 passed, 0 failed, 0 skipped |
| `run_integrated_4a.py` / `run_integrated.py` (3.4C) / `reconcile_4a.py` | PASS / PASS / PASS (42/42) |
| `tools.workbook_seed` | `git status` vazio |

---

## 3. Expectativas × observações

Todas as expectativas foram recalculadas por `closure/reconcile_4b.py` (`python -I`, sem `app/`): **52/52 linhas PASS**.

| grandeza | esperado (calendário/seeds) | observado |
|---|---|---|
| datas T1 / T2 / T3 | 396 / 62 / **792** (não 790, F4B-01) | 396 / 62 / 792 |
| por data: alvos / nós / eventos / transferências (eventos) | 446 / 458 / 896 / 13 (67) | idem, em **todas** as 1 250 datas |
| identidades derivadas: mensais / anuais | 324 / 196 | 324 / 196 |
| janelas por identidade mensal | dia do mês (28/29/30/31 no fim do mês) | idem, em todas as datas |
| janelas por identidade anual | dia do ano | idem: **365** em 2026-12-31 e 2027-12-31, **1** em 2027-01-01, **60** em 2028-02-29 |
| crescimento do store por data | 1 227 no primeiro dia; 1 143 no dia 1 do mês; 1 227 em 1º de janeiro; 1 109 nos demais | idem, em todas as datas |
| períodos encerrados (snapshot por hash) | inalterados | T1 13/13, T2 2/2, T3 28/28 |
| store final | — | T1 439 774, T2 68 944, T3 879 498 chaves |

---

## 4. Matriz de evidência

| tema | artefato | resultado |
|---|---|---|
| contrato, mecânica e E1–E5 | `STAGE_4B_DECISION_CONTRACT.md`, `evidence/contract_audit_4b.json`, `contract_expectations_4b.json` | PASS |
| recálculo independente (calendário, identidades, ciclos) | `independent_calendar.py` (`python -I`) | PASS |
| T1 / T2 / T3 | `temporal/evidence/<T>/{temporal_coverage.csv, identities_by_date.csv, period_snapshots.json, performance_profile.csv, temporal_summary.json, reexecution.json}`; `T1/state_scenarios.json` | PASS |
| oracle temporal | `oracle/evidence/oracle_temporal_summary.json` | PASS, 195 156 bit a bit |
| mutação | `mutation/evidence/{mutation_summary.json, mutation_results.csv, code_mutation_results.csv, positive_controls.csv, first_round_analysis.json}` | PASS, 100% |
| reconciliação | `closure/closure_reconciliation_4b.json` | PASS, 52/52 |

---

## 5. Mecânica temporal e colisões

| frequência | `period_id` | chave |
|---|---|---|
| diário | `AAAA-MM-DD` (10) | `(var, st, sv, data, None)` |
| mensal | `AAAA-MM` (7) | `(var, st, sv, mês, run_date)`, uma por janela |
| anual | `AAAA` (4) | `(var, st, sv, ano, run_date)`, uma por janela |

- **Colisão: nenhuma.**
  - Cada uma das 508 entidades tem um único formato.
  - Mensal e anual são variáveis distintas.
  - Nenhuma janela fica fora do próprio período.
- `window_for(período, data)` só abre janela quando a data está dentro do período. Um ano encerrado nunca recebe janela de data posterior.
- Entradas mensais e anuais são gravadas por período inteiro, e a leitura nunca cai em outro `period_id`.

---

## 6. Experimentos E1–E5

| experimento | resultado |
|---|---|
| **E1** virada (2026-12-28 → 2027-01-03, contexto de um ano) | 2026-12-31: 31 janelas mensais e 365 anuais. 2027-01-01: 1 e 1. Snapshot de 2026 (405 277 chaves) idêntico antes e depois |
| **E2** lacunas | data pulada, contexto iniciado em 01-10 e em 02-01: **falha explícita** (`VariableNotFoundError` do primeiro sub-período ausente). `EXPLICIT_FAILURE`, sem média parcial silenciosa (F4B-02) |
| **E3** entrada do período novo ausente | anual `lth_meta` e mensal `vazao_ltp`: falha explícita, com o valor anterior existente e **não** reaproveitado. `fator_ajuste_lth` num ramo IF inativo não é lido (trocar por 999 dá 0 diferenças); com o ramo forçado, falha. **Carry-over: nenhum**. Também confirmado no T1 em 2027-01-01 |
| **E4** períodos encerrados | reexecutar 2026-06-15 e 2026-12-31 depois da virada dá 0 chaves novas e 0 alteradas, com 67 transferências `UNCHANGED`. As datas novas não alteram 2026. Generalizado em T1/T3 por snapshot de cada mês e ano |
| **E5** calendário | fevereiro/2026 = 28, abril = 30, julho = 31. 2028: fevereiro = 29, 29/02 presente, 60 janelas anuais em 29/02 |

---

## 7. Análise estrutural de ciclos

| nível | nós | ciclos |
|---|---|---|
| instância (variável × escopo, na mesma data) | 1 227 (2 041 arestas) | **nenhum** |
| variável | 505 | nenhum |
| bloco | 5 | {production, yield} |

- O Tarjan é próprio; referências sem sufixo foram ligadas de forma conservadora a todas as instâncias.
- Não há defasagem `t-1`, agregação sobre a própria saída nem janela explícita.
- O plano de 458 nós está em ordem topológica válida.

```text
production <-> yield: ciclo apenas entre blocos; ACÍCLICO no nível de instância.
```

Não há ciclo de instância, então a convergência numérica (L5 da Stage 3) não tem objeto. Nenhum mecanismo de convergência foi implementado.

---

## 8. Desempenho

| execução | datas | tempo total da sequência | s/data (primeiras 32 → últimas 32) | razão |
|---|---|---|---|---|
| sondagem 2026-01-01..12-27 (Fase 1) | 361 | — | 0,171 → 0,318 | 1,85 |
| T1 | 396 | 138 s | 0,184 → 0,201 | 1,09 |
| T2 | 62 | 15 s | 0,195 → 0,205 | 1,05 |
| T3 | 792 | 322 s | 0,215 → 0,206 | 0,96 |

O custo por data cresce com a janela anual (leitura YTD) e **reinicia em 1º de janeiro**. Nenhuma execução passou o limite de 3,0 (DR-4B-6). T3 foi executada (DR-4B-4).

---

## 9. Estado, reexecução e determinismo

**Estado ao longo do ano** (T1, execução gêmea, `INVALID_INPUT` com o mesmo detail):

| injeção | resultado |
|---|---|
| `valor_retirada@L1` em 2026-03-10 | o mensal de março e o anual de 2026 têm estado **só a partir de 03-10**; abril e o anual de 2027 ficam limpos |
| `hes@L6` em 2026-12-31 | o anual de 2026 de L6_L7 tem estado só em 12-31; 2027 fica limpo |
| `hes@L4` em 2027-01-01 | o 2027 de L4_L5 tem estado; **todas as chaves de 2026 de L4/L5/L4_L5 ficam idênticas** às da execução limpa |

O auditor por diferença dá 0 problemas, com 383 chaves obrigatórias e 960 limpas.

**Reexecução:**
- 2026-02-28, 2026-12-31, 2027-01-01, 2028-02-29 e 2028-03-01 (as que caem em cada intervalo): store idêntico e 67 transferências WRITTEN → UNCHANGED;
- entrada diferente a montante (`VAR12054` → VAR12031 → transferência VAR11031): `INTERBLOCK_CONSUMER_VALUE_CONFLICT`.

**Determinismo:**
- T2: ORDER_A, ORDER_B, `PYTHONHASHSEED` 0 e 4242;
- T1: ORDER_A e ORDER_B.

`results_sha256`, `store_sha256` e ordem do plano são idênticos.

**Invariante de prefixo:**
- T1 e T3 nas 32 primeiras datas são idênticos à evidência 4A: 0 diferenças em 35 640 chaves;
- o hash do subconjunto é igual ao `store_sha256` versionado da 4A.

---

## 10. Oracle temporal independente

`oracle/oracle_temporal.py` é Python puro (`datetime`, `calendar`), sem `app/` (verificado por AST e `python -I`). Ele recalcula janelas e **todas** as agregações a partir dos diários brutos:

| intervalo | agregações comparadas | concordam | bit a bit |
|---|---|---|---|
| T1 (207 regras, 417 instâncias × 396 datas) | 165 132 | 165 132 | 165 132 |
| T2 (× 62 datas) | 25 854 | 25 854 | 25 854 |
| execução curta com estado (Policy B; 104 resultados com estado) | 4 170 | 4 170 | 4 170 |

- Os tipos cobertos são AVERAGE, SUM (com `integration_factor`), WEIGHTED_AVERAGE e MOVING_AVERAGE.
- Divergências de calendário: 0 em 5 772 identidades com janela.
- Tolerância declarada: 1e-12 (DR-4B-8).

**Limitação:** o oracle valida coerência temporal e aritmética de agregação, **não correção de negócio**. Os diários que alimentam as agregações vêm do próprio engine.

---

## 11. Mutação

| tipo | resultado |
|---|---|
| mutações de evidência (identidades por data, crescimento, janelas, MOVING_AVERAGE, snapshots, períodos encerrados, agregação, estado, reexecução, conflito/E3, determinismo, prefixo 4A, cobertura, proveniência) | **19/19** |
| controles positivos | 12/12 + CM4B-00 ACCEPT |
| mutantes de código (cópia temporária) | **8/8**. Por detector: ORACLE_T 7, TEMPORAL_T2 6, TURN_E1_E5 3 |
| `git status -- app data tools` | vazio antes e depois |

Mutantes:
- **CM4B-01** YTD no dia errado;
- **CM4B-02** off-by-one mensal;
- **CM4B-03** `period_id` anual com o mês;
- **CM4B-04** 29/02 ignorado;
- **CM4B-05** MOVING_AVERAGE sem reinício;
- **CM4B-06** snapshot do ano anterior sobrescrito;
- **CM4B-07** carry-over de entrada anual;
- **CM4B-08** perda de estado no anual.

**Rodada 1** (`mutation/evidence/first_round_analysis.json`):
- os 8 mutantes foram detectados, mas o detector `TEMPORAL_T2` não viu CM4B-01/02/04;
- esses mutantes mudam o **conteúdo** da janela sem mudar a identidade dela;
- não são mutantes equivalentes (o oracle os detecta): era uma lacuna do detector.

**Correção:** o harness passou a comparar, com `--no-write`, `results_sha256` e `store_sha256` com a evidência 4B versionada (`EVIDENCE_REGRESSION`). Na rodada 2, todos os detectores esperados dispararam.

---

## 12. Findings

| id | severidade | finding |
|---|---|---|
| F4B-01 | DOCUMENTATION_ONLY | T3 tem 792 datas, não 790 `[ref]` |
| F4B-02 | **REQUIRES_FOLLOWUP** | lacuna ⇒ `VariableNotFoundError` genérico, sem código de lacuna. Uma execução não pode começar no meio do mês ou do ano sem o histórico desde o dia 1 / 1º de janeiro. É preciso decidir como carregar o realizado anterior em uso operacional |
| F4B-03 | DOCUMENTATION_ONLY | entrada lida só num ramo IF inativo: a ausência só é detectada quando o ramo é ativado (IF causal) |
| F4B-04 | DOCUMENTATION_ONLY | o custo por data cresce com a janela anual (até cerca de 1,85× em dezembro) e reinicia em 1º de janeiro; dentro do limite |
| F4B-05 | DOCUMENTATION_ONLY | o detector temporal estrutural foi reforçado com regressão de conteúdo (§11), após a análise da rodada 1 |
| F4B-06 | **decisão técnica UNRESOLVED** | o teste 4A `test_production_surface_and_stage_3_closure_untouched` exige que, desde `d2847ab`, nada fora de `audit/stage4a/` e `tests/test_stage4a_*` mude além de `PLATFORM_PENDING_ITEMS.md`. Qualquer stage posterior o quebra; falha desde o 1º commit da 4B (`b0c3da3`). Não é defeito de produção. Corrigir exige editar um teste da 4A (proibido pela regra 4) |

`BLOCKER`: **nenhum**. Decisão técnica `UNRESOLVED`: **F4B-06**.

**Para o engenheiro de processo e o cliente:**
- ano fiscal × ano-calendário (DR-4B-3);
- carga do histórico/realizado antes da data de início do forecast (F4B-02).

---

## 13. Limitações

| # | limitação |
|---|---|
| L4B-1 | as entradas são do fixture (arbitrárias); as diárias repetem o padrão por dia do ano (DR-4B-5). Não é dado operacional |
| L4B-2 | o oracle temporal recalcula as agregações a partir dos diários do engine: valida a aritmética e o calendário, não as equações diárias (essas foram cobertas, para o area_41, pelo oracle 4A) |
| L4B-3 | os cenários de estado ao longo do ano rodaram só em T1 (execução gêmea); T2/T3 cobrem estrutura, snapshots e reexecução |
| L4B-4 | determinismo com `PYTHONHASHSEED` 0/4242 em T2. Em T1, ORDER_A/B; em T3, uma configuração |
| L4B-5 | ano fiscal fora de escopo (ano-calendário) |
| L4B-6 | os mutantes de código não rodam dentro do `pytest` (cerca de 20 min); a evidência versionada é verificada |

---

## 14. Comandos de reprodução

| # | comando | resultado nesta etapa |
|---|---|---|
| 1 | `python -m pytest -q` | ver §15, critério 14 |
| 2 | `python audit/stage4b/temporal/run_temporal_4b.py --range T1 --no-write` (também `T2` e `T3`) | PASS (cerca de 10 / 1 / 10 min com as verificações extras) |
| 3 | `python audit/stage4b/oracle/run_oracle_4b.py --no-write` | PASS, 195 156 bit a bit (cerca de 2 min) |
| 4 | `python audit/stage4b/mutation/run_mutation_4b.py --no-write` | PASS, 19/19 + 8/8 (cerca de 20 min; `--skip-code-mutants` leva cerca de 1 min) |
| 5 | `python audit/stage4b/derive_4b.py --no-write` e `python -I audit/stage4b/independent_calendar.py --check` | PASS |
| 6 | `python -I audit/stage4b/closure/reconcile_4b.py --no-write` | PASS, 52/52 |
| 7 | `python audit/stage4a/integrated/run_integrated_4a.py --no-write` e `python audit/stage3_4/integrated/run_integrated.py --no-write` | PASS (inalterados) |
| 8 | `python -I audit/stage3_4/mutation/blackbox_audit.py --no-write` | PASS |
| 9 | `git diff --stat 0a924e6 -- app data tools` | vazio |

---

## 15. Gate final

| # | critério | resultado |
|---|---|---|
| 1 | pré-requisitos e baseline (4A na `main`, hashes, árvore limpa, 1964 passed) | PASS |
| 2 | mecânica temporal documentada, sem colisão entre frequências, meses e anos | PASS |
| 3 | E1–E5 executados e registrados (lacunas e entrada ausente documentadas) | PASS |
| 4 | T1 completa: janelas e identidades corretas em todos os fins de mês e na virada; 365 janelas anuais ao fim de 2026; 2027 nasce com 1 | PASS |
| 5 | períodos encerrados imutáveis (snapshot por hash) | PASS (13 + 2 + 28) |
| 6 | T2 (bissexto) completa; T3 executada | PASS (62; 792) |
| 7 | invariante de prefixo: 0 diferenças contra a 4A nas 32 primeiras datas | PASS (T1 e T3) |
| 8 | estado ao longo do ano e isolamento entre anos | PASS |
| 9 | reexecução idempotente e conflito de entrada detectado | PASS |
| 10 | determinismo nas configurações definidas | PASS |
| 11 | oracle: janelas e todas as agregações concordam | PASS (195 156 bit a bit) |
| 12 | análise de ciclos no nível de instância concluída | PASS (acíclico) |
| 13 | mutação 100%; controles aceitos; 0 sobreviventes sem análise | PASS (19/19 + 8/8; rodada 1 analisada) |
| 14 | suíte completa verde; testes e evidências 2.x–4A inalterados | **PENDENTE DE DECISÃO**: suíte **2004 passed, 1 failed** (`tests/test_stage4a_closure.py::test_production_surface_and_stage_3_closure_untouched`, F4B-06); testes e evidências 2.x–4A inalterados |
| 15 | `app/`, `data/`, `tools/` inalterados | PASS |
| 16 | findings classificados; nenhum `BLOCKER`; limitações e comandos documentados | PASS |

```text
FINAL_STAGE_4B_GATE = READY_FOR_DECISION   (critério 14: ver F4B-06)
```
