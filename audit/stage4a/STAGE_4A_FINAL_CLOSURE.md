# Stage 4A — Fechamento: area_41 no universo integrado

| campo | valor |
|---|---|
| etapa | 4A (4A.1 contrato → 4A.2 integrado → 4A.3a oracle → 4A.3b mutação → 4A.4 fechamento) |
| baseline | `main` = `d2847ab36933668bf4a1299b3ffe058827a82037` (fast-forward da `feature/area-41-block`) |
| branch | `feature/stage-4a-area41-integration` (sem push, sem merge) |
| rótulo | `REAL_DERIVED_TEST_RESULT` (fixture REAL_DERIVED, `TEST_FIXTURE_ONLY`) |
| Stage 3 | **CLOSED**. A 4A aponta para a Stage 3, e não o inverso. `STAGE_3_FINAL_CLOSURE.md` não foi alterado |
| superfície de produção | `git diff --stat d2847ab -- app data tools` **vazio** |

---

## 1. Resumo executivo

O `area_41` entrou na regressão integrada. O universo integrado passou de 4 para **5 blocos**:
- **446 alvos**;
- **458 nós** (238 EQUATION, 207 AGGREGATION, 13 TRANSFER);
- 62 entradas;
- 896 eventos por data;
- 32 datas contíguas no mesmo contexto.

Resultados:
- **Não-regressão:** os 421 alvos da 3.4C não mudaram em valor, state, detail nem identidade temporal. São 33 740 chaves comparadas e 0 diferenças; o hash do subconjunto é igual ao `store_sha256` da 3.4C.
- **Oracle:** um oracle Python puro, reescrito do texto do workbook A41 v9, concorda com o engine em **5 015/5 015** comparações. Elas cobrem as 20 equações, as 25 combinações de `hes` por grupo, as falhas explícitas e as agregações.
- **Mutação:** 25/25 mutações de evidência e 11/11 mutantes de código/seed detectados; 9/9 controles positivos aceitos.
- **Bloqueios:** nenhum `BLOCKER` técnico. As pendências de negócio estão registradas e não bloqueiam.

```text
FINAL_STAGE_4A_GATE = PASS
```

---

## 2. Baseline (Fase 0)

Evidência em `audit/stage4a/evidence/baseline_phase0.json`.

| verificação | resultado |
|---|---|
| `main` contém `feature/area-41-block` | OK. O merge foi fast-forward e o HEAD é `d2847ab` |
| hashes históricos `f3b6588`, `7877551`, `8095011` | presentes e ancestrais da `main` (HASHES_OK) |
| árvore | limpa |
| suíte | 1921 passed, 0 failed, 0 skipped |
| 3.4B diferencial / 3.4C integrado / `reconcile.py` / `blackbox_audit.py -I` | PASS / PASS / PASS / PASS |
| `python -m tools.workbook_seed` | `git status` vazio (seeds = workbooks) |

---

## 3. Cardinalidades: esperado × observado

Todas foram derivadas pelo planner/engine (`derive_4a.py`) e recalculadas de forma independente:
- `independent_count.py` (`python -I`, sem `app/`);
- `closure/reconcile_4a.py` (`python -I`, sem `app/`), com **42/42 linhas PASS**.

| grandeza | esperado (contrato 4A) | observado |
|---|---|---|
| alvos oficiais / integrados | 446 / 446 | 446 / 446 |
| alvos por bloco | yield 219, max_ht 109, production 50, energy 43, area_41 25 | idem |
| nós do plano | 458 = 427 + 33 − 2 (união) | 458 |
| EQUATION / AGGREGATION / TRANSFER | 238 / 207 / 13 | 238 / 207 / 13 |
| nós compartilhados com o fecho do area_41 | `EQUATION:EQ12012`, `TRANSFER:VAR11031` | idem |
| vínculos carregados / usados | 13 / 13 (VAR16007 passa a ser usado) | 13 / 13 |
| eventos por data / de transferência | 896 / 67 | 896 / 67 nas 32 datas |
| entradas livres | 62 (51 + 11) | 62 |
| plano oficial do area_41 | 3 OK + 22 `INTERBLOCK_SOURCE_NOT_LOADED` (maintenance) | idem; `plan_evidence.csv` idêntico nas 446 linhas |
| `PENDING_LOAD` | 16 | 16 |
| sha256 de `interblock_links.json` | `8dc6b7c8…cd700` | idem (= baseline) |

---

## 4. Matriz de evidência

| tema | artefato | resultado |
|---|---|---|
| contrato e auditoria | `STAGE_4A_DECISION_CONTRACT.md`, `evidence/contract_audit.json`, `contract_expectations.json` | PASS (40 campos derivado × independente) |
| `OBS` do workbook | `evidence/obs_register.csv` | 26 linhas: 21 `REQUIRES_FOLLOWUP`, 5 `DOCUMENTATION_ONLY` |
| árvore de `hes` | `evidence/hes_decision_matrix.csv` | engine = texto literal do workbook em 50/50 |
| integrado de 5 blocos | `integrated/evidence/{integrated_summary.json, targets.csv, nodes.csv, transfers.csv, temporal_coverage.csv}` | PASS |
| não-regressão dos 421 | `integrated/evidence/non_regression_421.json` | PASS, 0 diferenças |
| oracle | `oracle/evidence/{oracle_summary.json, oracle_cases.csv}` | PASS, 5 015/5 015 |
| mutação | `mutation/evidence/{mutation_summary.json, mutation_results.csv, code_mutation_results.csv, positive_controls.csv}` | PASS, 100% |
| reconciliação e L8 | `closure/closure_reconciliation_4a.json`, `closure/evidence_regeneration_report.md` | PASS, 42/42 |
| gancho do Excel | `oracle/EXCEL_COMPARISON_HOOK.md` | formato de extrato definido; sem valores |

---

## 5. Não-regressão dos 421 alvos

| verificação | resultado |
|---|---|
| hash do subconjunto sem area_41 (função `store_sha` da 3.4C) | `619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c`, igual ao `store_sha256` versionado da 3.4C |
| execução dos 4 blocos isolados × 5 blocos, chave a chave | 33 740 chaves, 0 só de um lado, 0 diferentes (value, state, detail, `window_end`) |
| resultado final dos 421 alvos (`targets.csv` 3.4C × 4A) | 421 idênticos |
| protocolo de entradas | DR-4A-5: as entradas dos 4 blocos mantêm o índice da 3.4C. O teste negativo prova que o índice ingênuo mudaria os 421 alvos por artefato do fixture |

---

## 6. Estado (area_41)

Execuções gêmeas + auditor por diferença (`checks.check_state_diff`) + casos nomeados.

| cenário | origem | prova |
|---|---|---|
| SA1 | `INVALID_INPUT` em `VAR12024` (production, L3), janeiro inteiro | chega ao area_41 **pela transferência** `lth` (VAR16007@L3) e alcança `lth_grupo`, `retirada_cond_corr_lth`, `retirada_condensado_grupo` e `retirada_condensado_linha` de L1_L3, além do total. Também as agregações: o anual YTD continua com estado em 02-01. L4..L7 ficam isolados |
| SA2 | estado em `hes@L4` (operando da condição) | `retirada_condensado_grupo` L4_L5, linhas L4/L5, total e as agregações herdam. L1_L3 e L6_L7 ficam isolados |
| SA3a / SA3b | estado em `desconto_retirada_41c` (fronteira) | **IF causal**. Com `hes` Normal, o ramo não é executado e **nada propaga** (só a origem difere). Com (`1 By pass e LC`, `1 By pass e LC`), propaga |
| SA4 | estado em `vazao_ltp` L1_L3 (fronteira mensal) | só o grupo L1_L3 e o total; L4_L5 e L6_L7 isolados |
| SA5 | `"F"`: (`Normal`, `1 By pass e LC`) em L4/L5 e (`1 By pass e LC`, `Normal`) em L6/L7 | `NO_APPLICABLE_RULE`, value None, detail None, nos grupos, linhas e total. **Policy B** nas agregações mensais e anuais (incluindo as 7 instâncias por linha); L1_L3 isolado |
| SA6 | composições indefinidas | equação (total com dois estados) e janela de agregação (dois estados; mesmo estado com dois details) levantam `MULTI_STATE_COMBINATION_UNDEFINED` / `MULTI_DETAIL_COMPOSITION_UNDEFINED` |

O contexto limpo fica sem estado: 0 resultados com state/detail. Nenhuma variável `numerico` tem texto no valor (`checks_4a.check_no_text_in_numeric`).

---

## 7. Temporal, reexecução e determinismo

| tema | resultado |
|---|---|
| datas | 32 contíguas (2026-01-01..2026-02-01), no mesmo contexto |
| identidades mensais de janeiro | 324 (313 da 3.4C + 11 do area_41), todas com as 31 janelas; janelas de janeiro inalteradas depois de 02-01 |
| identidades anuais (YTD parcial) | 196 (185 + 11), todas com as 32 janelas; `YEAR_TO_DATE_PARTIAL_COVERAGE` |
| reexecução (2026-01-15 e 2026-02-01) | store idêntico, 0 chaves novas, 67 transferências WRITTEN → UNCHANGED, 0 estado residual |
| determinismo | RUN_A, RUN_B (ORDER_B), HASH_SEED 0 e 4242: `results_sha256`, `store_sha256`, hash do area_41, ordem do plano e grafo idênticos |
| orquestrador × engine | 13 184 comparações (640 do area_41), 0 diferenças |

---

## 8. Oracle de fidelidade ao workbook

```text
INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)
```

| modo | comparações | concordam (exatas) |
|---|---|---|
| equação isolada (20/20; grade de magnitudes; `ln` ≤ 0 e divisão por zero) | 902 | 902 (902) |
| cadeia do dia (as 25 combinações de `hes` por grupo; `NO_APPLICABLE_RULE` só em 2/25) | 2 601 | 2 601 (2 601) |
| integrado: diários do area_41 nas 32 datas | 640 | 640 (640) |
| integrado: agregações mensais/anuais (352 + 352 janelas; média manual + `statistics.fmean`) | 704 | 704 (704) |
| trecho com `"F"` (diários + Policy B) | 168 | 168 (168) |
| **total** | **5 015** | **5 015 (5 015)** |

Detalhes:
- **Falhas previstas.** O oracle prevê e o engine executa:
  - `ln` fora do domínio → `MathDomainError` (via `EquationEvaluationError`);
  - denominador zero → `DivisionByZeroError`.
- **Tolerância** (DR-4A-7): `rel_tol = abs_tol = 1e-12`. Na prática, todas as comparações foram bit a bit iguais.
- **Guardas:**
  - o texto transcrito no oracle é relido do workbook e falha se divergir;
  - o módulo do oracle não importa `app/` (AST + `python -I`);
  - testes negativos provam que um desvio é detectado.

**Limitações declaradas:**
1. O oracle valida **fidelidade ao workbook**, não correção de negócio.
2. O oracle **compartilha com o engine a leitura do workbook**: o mesmo texto é a fonte dos dois. O mapeamento nome@escopo → ID vem dos seeds.
3. A comparação com a planilha Excel original não foi feita: o arquivo não está no repositório. Só o gancho foi entregue (`oracle/EXCEL_COMPARISON_HOOK.md`).

---

## 9. Mutação

| tipo | resultado |
|---|---|
| mutações de evidência (alvos, nós, transferência VAR16007, identidade, estado/Policy B do `"F"`, contrato de resultado, temporal, reexecução, determinismo, não-regressão, proveniência) | **25/25 detectadas** |
| controles positivos | 8/8 auditores aceitam a evidência real; CM4A-00 (árvore sem mutação) ACCEPT |
| mutantes de código/seed em cópia temporária (`git clone --shared` + `tempfile`) | **11/11 detectados**, 0 sobreviventes, 0 detectores esperados ausentes |
| por detector | ORACLE 10, INTEGRATED_4A 9, CONTRACT_4A 7, TESTS 11 |
| `git status -- app data tools` | vazio antes e depois |

Mutantes:
- **CM4A-01** `or` → `and` no ramo LC;
- **CM4A-02** `"F"` → `0`;
- **CM4A-03** `math.log` → `math.log10` no engine;
- **CM4A-04** `/2` → `/3` em EQ16006;
- **CM4A-05** `@L5` → `@L4` em EQ16005;
- **CM4A-06** vínculo VAR16007 removido;
- **CM4A-07** 41d → 41c;
- **CM4A-08** `/ 24` → `/ 23`;
- **CM4A-09** tradução do literal desligada;
- **CM4A-10** AVERAGE → SUM;
- **CM4A-11** escopo da equação trocado.

---

## 10. Observações `OBS`, pontos novos e findings

**`OBS` do workbook (26 linhas, §3.1 do contrato):**
- `REQUIRES_FOLLOWUP`, para o cliente e sem bloquear:
  - `vazao_ltp` (origem yield? LTP 1067? LTH 1100/970);
  - `fator_retirada_cond_corr_lth` (1.15 não usado);
  - `valor_retirada` (significado e nome);
  - descontos 41c/41d (Plano de Manutenção?);
  - 7 parâmetros não usados;
  - inconsistência 41c/41d nos ramos de L4_L5 × L6_L7, e a equação precisará ser atualizada após o bloco maintenance.
- `DOCUMENTATION_ONLY`: origem do `lth`; domínio de `hes`.

**Pontos que NÃO constam em `OBS`** (contrato §4). Todos foram implementados literalmente:

| # | ponto | classificação |
|---|---|---|
| N1 | precedência LC > Overhaul/Parada > 1 By pass > 1 By pass e LC quando as linhas diferem | REQUIRES_FOLLOWUP |
| N2 | `"F"` só em 2/25 combinações; `1 By pass e LC` exige as duas linhas nesse estado | REQUIRES_FOLLOWUP |
| N3 | constantes 100, 50, 14, 10, 24, 2 embutidas no texto | REQUIRES_FOLLOWUP |
| N4 | L1_L3 sem ramos por `hes` e com forma diferente (`Σ valor_retirada − 3·d`) | REQUIRES_FOLLOWUP |
| N5 | `retirada_condensado_total` vira `NO_APPLICABLE_RULE` se qualquer grupo der `"F"` | REQUIRES_FOLLOWUP |
| N6 | soma de `lth` do grupo igual a zero ⇒ `DivisionByZeroError` (sem estado declarado) | REQUIRES_FOLLOWUP |
| N7 | `ln` fora do domínio ⇒ `MathDomainError` explícito | DOCUMENTATION_ONLY |
| N8 | entradas mensais (`vazao_ltp`, `fator`) consumidas por equações diárias | DOCUMENTATION_ONLY |
| N9 | `valor_retirada` (VAR16017) e `retirada_condensado_grupo` L1_L3 (VAR16018) com a mesma célula de origem `Forecast A41!A11` | DOCUMENTATION_ONLY |

**Findings técnicos:**

| id | severidade | finding |
|---|---|---|
| F4A-01 | REQUIRES_FOLLOWUP | o `"F"` vira `NO_APPLICABLE_RULE` com value None e **`detail = None`**, conforme o contrato 3.3B (D1/R1). O §10.5 do prompt esperava `detail = "F"`. Não há texto no valor (propriedade essencial atendida). Mudar o detail exigiria alterar `app/` (DR-4A-6) |
| F4A-02 | DOCUMENTATION_ONLY | o prompt nomeia EQ16004/EQ16006 como `retirada_condensado_grupo`. Nos seeds são `lth_grupo`; a 4A usa os IDs reais |
| F4A-03 | DOCUMENTATION_ONLY | o vínculo `VAR16007` passa a ser usado (12 → 13) |

`BLOCKER`: **nenhum**.

---

## 11. Limitações

| # | limitação |
|---|---|
| L4A-1 | oracle **parcial**: só o area_41, e por fidelidade ao workbook, não correção de negócio. Compartilha com o engine a leitura do workbook |
| L4A-2 | sem comparação com a planilha Excel original (só o gancho) |
| L4A-3 | **L10 mantida**: o area_41 não tem fonte nativa de estado. Estados vêm de injeção, transferência ou do `"F"` |
| L4A-4 | `hes` continua `PENDING_LOAD` (maintenance). No fixture é entrada livre (`Normal` por padrão; os cenários sobrescrevem). As entradas de fronteira são arbitrárias (fixture) |
| L4A-5 | YTD parcial (32 datas); virada de ano e ano completo fora de escopo (herdado de L4) |
| L4A-6 | engine compartilhado entre orquestrador e espelho por bloco (herdado de L3); o oracle 4A reduz essa limitação só para o area_41 |
| L4A-7 | os mutantes de código não rodam dentro do `pytest` (custo de cerca de 10 min); a evidência versionada é verificada pelos testes |

---

## 12. Comandos de reprodução

| # | comando | resultado nesta etapa |
|---|---|---|
| 1 | `python -m pytest -q` | ver §13, critério 9 |
| 2 | `python audit/stage4a/integrated/run_integrated_4a.py --no-write` | PASS (cerca de 90 s) |
| 3 | `python audit/stage3_4/differential/run_differential.py --no-write` | PASS, 0 diferenças (inalterado) |
| 4 | `python audit/stage3_4/integrated/run_integrated.py --no-write` | PASS, 421 / 427 (inalterado) |
| 5 | `python audit/stage4a/mutation/run_mutation_4a.py --no-write` | PASS, 25/25 + 11/11 (cerca de 10 min; `--skip-code-mutants` leva cerca de 50 s) |
| 6 | `python audit/stage4a/oracle/run_oracle.py --no-write` | PASS, 5 015/5 015 |
| 7 | `python -I audit/stage3_4/mutation/blackbox_audit.py --no-write` | PASS |
| 8 | `python -I audit/stage4a/closure/reconcile_4a.py --no-write` | PASS, 42/42 |
| 9 | `python -I audit/stage4a/independent_count.py --check` e `python audit/stage4a/derive_4a.py --no-write` | PASS |
| 10 | `git diff --stat d2847ab -- app data tools` | vazio |

Sem `--no-write`, os scripts regeneram a evidência da 4A. A evidência da 3.4C nunca é escrita pela 4A.

---

## 13. Gate final

| # | critério | resultado |
|---|---|---|
| 1 | pré-requisitos e baseline reconciliados (`main` contém a area-41, hashes históricos presentes, árvore limpa, 1921 passed) | PASS |
| 2 | universo integrado de 5 blocos com cardinalidades derivadas e recalculadas de forma independente | PASS (40 campos; 42/42 linhas) |
| 3 | 0 diferenças nos 421 alvos anteriores (valor, state, detail, identidade temporal) | PASS (33 740 chaves, 421 alvos) |
| 4 | plano oficial inalterado; 16 `PENDING_LOAD` e sha256 de `interblock_links.json` intactos | PASS |
| 5 | estado do area_41: propagação, isolamento, Policy B e `NO_APPLICABLE_RULE` (`"F"`) cobertos | PASS (SA1..SA6) |
| 6 | temporal (32 datas), reexecução e determinismo PASS com os 5 blocos | PASS |
| 7 | oracle de fidelidade: 20/20 equações e as 25 combinações de `hes` por grupo dentro da tolerância | PASS (5 015/5 015) |
| 8 | mutação 100% detectada; controles positivos aceitos; 0 sobreviventes sem análise | PASS (36/36; 9/9 controles) |
| 9 | suíte completa verde; testes, evidências e documentos 2.x–3.4 inalterados | PASS: suíte final **1964 passed**, 0 failed, 0 skipped; `git diff d2847ab` fora de `audit/stage4a/**` e `tests/test_stage4a_*` só na adição datada de `PLATFORM_PENDING_ITEMS.md` |
| 10 | `app/`, `data/`, `tools/` inalterados | PASS (`git diff --stat d2847ab -- app data tools` vazio) |
| 11 | observações `OBS` e pontos novos registrados e classificados; limitações e comandos documentados | PASS (§10–§12) |
| 12 | nenhum `BLOCKER` técnico aberto | PASS |

```text
FINAL_STAGE_4A_GATE = PASS
```
