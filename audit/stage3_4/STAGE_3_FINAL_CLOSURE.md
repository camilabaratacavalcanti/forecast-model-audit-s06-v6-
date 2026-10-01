# Stage 3 — Final Closure (Stage 3.4E: Consolidation)

Fechamento formal da Stage 3 do Forecast Platform, conforme o contrato 3.4A §20 ("Stage 3.4E contract — Stage 3 Closure").

A etapa é de **consolidação**, não de implementação:
- nenhum arquivo de `app/`, `data/`, `tools/`, workbooks, seeds ou do registro oficial de vínculos foi alterado;
- nenhum teste existente foi alterado.

**Artefatos novos desta etapa:**
- este documento;
- `audit/stage3_4/closure/reconcile.py`;
- `audit/stage3_4/closure/closure_reconciliation.json`.

**Legenda:**
- **[obs]** valor observado nesta etapa, recalculado a partir do código ou da execução por `reconcile.py`;
- **[evid]** lido da evidência versionada;
- **[contrato]** texto normativo da 3.4A.

Todo resultado de execução citado é `REAL_DERIVED_TEST_RESULT`.

---

## 1. Executive summary

A Stage 3 foi executada dentro do escopo aprovado (DR-1..DR-5 da 3.4A):
- as cardinalidades e as evidências das sub-stages 3.4A–3.4D foram reconciliadas por recálculo independente (`reconcile.py`, 31/31 linhas PASS);
- os mecanismos de auditoria foram testados por mutação (75/75 detectados, 14/14 controles positivos aceitos);
- as fragilidades do auditor da 3.4C (G1–G5) foram encontradas e corrigidas no harness;
- nenhuma mudança funcional de produção foi introduzida pela Stage 3.4;
- as limitações estão explícitas (§17);
- existe uma trilha reproduzível de comandos (§18).

```text
D32-01 = CLOSED_FOR_STAGE_3_SCOPE
FINAL_STAGE_3_GATE = PASS
STAGE 3 = CLOSED
```

Significado das mutações: todos os mutantes introduzidos no escopo do harness de mutação/auditoria produziram uma divergência detectável pelo mecanismo de auditoria correspondente. **Não** são "75 defeitos de produção encontrados".

---

## 2. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| baseline esperado | `80950117eb9881fe635e695dd221bdf0c6147ee5` |
| HEAD inicial | `80950117eb9881fe635e695dd221bdf0c6147ee5` [obs] |
| `origin/feature/area-41-block` | `80950117eb9881fe635e695dd221bdf0c6147ee5` [obs] |
| `origin/HEAD` | referência simbólica não configurada neste clone; a comparação foi feita com a branch remota correspondente, que coincide com HEAD |
| árvore inicial | limpa [obs] |
| suíte inicial | 1859 passed, 0 failed, 0 skipped (fechamento 3.4D, reexecutada nesta etapa: §18) |

**Histórico da Stage 3.4:**

| commit | etapa |
|---|---|
| `f3b6588` | 3.3C, baseline da 3.4A |
| `95e7ade` | 3.4A: contrato |
| `4d54804` | 3.4B: diferencial |
| `043fe9c` | 3.4C: integrada |
| `8095011` | 3.4D: mutação e auditoria |

---

## 3. Stage-by-stage closure

### 3.1 Gates formais de toda a Stage 3

| stage | commits | gate formal | status consolidado nesta etapa |
|---|---|---|---|
| 3.1 | `e60af19`, `8ca9d01` | PASS | PASS |
| 3.2 | `11c8931`, `2cfc52a`, `a733487` | READY_FOR_DECISION (pendências D32-01 e D32-02) | **fechada**: D32-01 `CLOSED_FOR_STAGE_3_SCOPE` (DR-1, 3.4A) e D32-02 resolvida na 3.3B (identidade por janela, `8900984`). O relatório histórico da 3.2 não foi reescrito (3.4A §24 #1) |
| 3.3A | `472949b`, `eee88d6` | PASS | PASS |
| 3.3B | `77f58ae`, `06a7907` → `dd5696d`, `8900984`, `4faf5f1` | PASS (closure) | PASS; a 1ª rodada READY_FOR_DECISION foi superada (3.4A §24 #3) |
| 3.3C | `f3b6588` | PASS | PASS |
| 3.4A | `95e7ade` | PASS | PASS |
| 3.4B | `4d54804` | PASS | PASS |
| 3.4C | `043fe9c` | PASS | PASS |
| 3.4D | `8095011` | PASS | PASS |
| 3.4E | este commit | — | **FINAL_STAGE_3_GATE = PASS** |

### 3.2 Final evidence matrix

| Stage | Purpose | Evidence | Result | Production changes |
|---|---|---|---|---|
| 3.4A | Decision / scope closure | `STAGE_3_4A_DECISION_CONTRACT.md` (`95e7ade`) | PASS | 0 |
| 3.4B | Differential regression | `STAGE_3_4B_DIFFERENTIAL_REGRESSION.md`, `differential/evidence/*` (`4d54804`) | PASS, 4722/4722 | 0 |
| 3.4C | Integrated regression | `STAGE_3_4C_INTEGRATED_REGRESSION.md`, `integrated/evidence/*` (`043fe9c`) | PASS, 421/421, 427/427, 1920/1920, 32 datas | 0 |
| 3.4D | Mutation / audit closure | `STAGE_3_4D_MUTATION_AUDIT_CLOSURE.md`, `mutation/*` (`8095011`) | PASS, 75/75, 14/14 | 0 (harness da 3.4 reforçado; §13) |
| 3.4E | Final consolidation | este documento, `closure/reconcile.py`, `closure/closure_reconciliation.json` | PASS | 0 |

"Production changes" é a contagem de arquivos alterados em `app/`, `data/` e `tools/` por cada sub-stage [obs, §16]. As mudanças funcionais de `app/` da Stage 3 ocorreram antes da 3.4, em 3.1–3.3C, e são justamente o objeto das regressões 3.4B/3.4C.

### 3.3 Reconciliação da 3.4A

| item | observado |
|---|---|
| baseline registrado | `f3b6588`, 1820 passed [evid] |
| decisões | DR-1 (execução oficial fora do escopo), DR-2 (REAL_DERIVED = TEST_FIXTURE_ONLY), DR-3 (diferencial, referência `7877551`), DR-4 (sem oracle numérico independente), DR-5 (421 alvos) [contrato] |
| cardinalidades | todas confirmadas por recálculo (§4) |
| protocolo temporal | 2026-01-01 → 2026-02-01, 32 datas, mesmo contexto; YTD parcial [contrato §15; obs §8] |
| D32-01 | `CLOSED_FOR_STAGE_3_SCOPE` [contrato §4; §15 deste documento] |
| oracle | `INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE` [contrato §8] |
| proteção | `app/`, `data/`, `tools/` inalterados desde `f3b6588` [obs, §16] |

---

## 4. Contract cardinalities

Final contract matrix: cada valor "Observed" foi recalculado por `reconcile.py` a partir do catálogo, do planner, do engine e de uma execução real de 32 datas, ou lido da evidência versionada quando indicado.

| Contract area | Expected | Observed | Evidence | Status |
|---|---:|---:|---|---|
| Planning targets | 446 | 446 | planner (5 blocos) = `plan_evidence.csv` (446 linhas: 159 OK, 287 bloqueados) | PASS |
| Integrated targets | 421 | 421 | `targets_of_blocks(yield, production, energy, max_ht)` | PASS |
| Excluded (only area_41) | 25 | 25 | 446 − 421; blocos dos excluídos = {area_41} | PASS |
| Planner nodes | 427 | 427 | `plan(421).steps` | PASS |
| Equation / aggregation / transfer nodes | 218 / 197 / 12 | 218 / 197 / 12 | plan steps | PASS |
| VAR12041 equation definitions | 7 | 7 | `equations.json`; 7 nós produzem VAR12041 | PASS |
| Equation target variables | 212 | 212 | 218 definições → 212 variáveis | PASS |
| Equation definitions | 218 | 218 | `equations.json` (4 blocos) | PASS |
| Equation instances | 392 | 392 | `ForecastEngine.materialize_equation` | PASS |
| Aggregation rules | 197 | 197 | `SeedLoader` | PASS |
| Aggregation instances | 395 | 395 | `SeedLoader` (4 blocos) | PASS |
| Aggregation incl. area_41 | 417 | 417 | 395 + 22 | PASS |
| Historical "834" | 417 × 2 casos | 417 × 2 = 834 | casos de execução, **não** instâncias | PASS |
| Transfers | 12 | 12 | plan steps; `transfers.csv` | PASS |
| Transfer events | 1920 | 1920 (execução) / 1920 verificados (evidência) | execução real 32 datas; `transfers.csv` | PASS |
| Execution dates | 32 | 32 | 2026-01-01 → 2026-02-01 | PASS |
| Pending links | 16 | 16 `PENDING_LOAD` | registro oficial + `interblock_links.json` | PASS |
| Annual rules | 48 | 48 (max_ht 39, production 9) | `target_frequency = anual` | PASS |
| Monthly identities (jan / fev) | 313 / 313 | 313 / 313 | `check_temporal` | PASS |
| Windows per January monthly identity | 31 | 31 | store real | PASS |
| Annual identities | 185 | 185 | `check_temporal` | PASS |
| Windows per annual identity (YTD) | 32 | 32 | store real | PASS |
| Differential cases (3.4B) | 4722 | 4722 MATCH | `differential_cases.csv` | PASS |
| Mutation evidence | 58 | 58 detectadas | `mutation_results.csv` | PASS |
| Code mutants | 17 | 17 detectados | `code_mutation_results.csv` | PASS |
| Mutation detection | 100% | 100% (75/75) | idem | PASS |
| Positive controls | 14 | 14 (13 + CM-00) | `positive_controls.csv`, `mutation_summary.json` | PASS |
| Full tests | 1859 baseline | 1859 passed, 0 failed, 0 skipped | `pytest -q` nesta etapa | PASS |

**Por que 427 ≠ 421:** a variável VAR12041 (production `pick_up`) tem 7 definições de equação, uma por linha. São 7 nós EQUATION para um alvo, portanto 427 − 421 = 6. Não é erro.

**Distribuição por bloco** [obs]:

| bloco | alvos | EQUATION | AGGREGATION | TRANSFER | nós |
|---|---:|---:|---:|---:|---:|
| yield | 219 | 138 | 80 | 1 | 219 |
| production | 50 | 27 | 28 | 1 | 56 |
| energy | 43 | 24 | 11 | 8 | 43 |
| max_ht | 109 | 29 | 78 | 2 | 109 |
| **total** | **421** | **218** | **197** | **12** | **427** |

- 219 + 50 + 43 + 109 = 421 alvos; 219 + 56 + 43 + 109 = 427 nós.
- Os nós de production (56) diferem dos alvos (50) pelas 6 definições extras de VAR12041.

**Instâncias versus casos de execução:**
- instância = definição ou regra materializada num escopo concreto (392 de equação; 395 de agregação, 417 com area_41);
- caso de execução = instância × entrada × data. Na 3.4B: 392 × 3 × 2 = 2352 e 395 × 3 × 2 = 2370.
- O número histórico **834** é 417 instâncias de agregação × 2 datas de um experimento de discovery, **não** 834 instâncias (3.4A §13 e §24 #4, confirmado).

---

## 5. Differential regression (3.4B)

| item | observado [evid, `differential_summary.json` / `differential_cases.csv`] |
|---|---|
| oracle | `DIFFERENTIAL_REGRESSION_ORACLE` |
| reference | `7877551fd9f63a2d137ac6da7507afe6cbffd297` |
| candidate registrado | `95e7adeffe43ff5b098289ae59a360c1009d9ff9`, o HEAD em que o diferencial foi executado |
| equações | 392/392 instâncias × 3 vetores × 2 datas = 2352 casos |
| agregações | 395/395 instâncias × 3 × 2 = 2370 casos (AVERAGE 342, SUM 42, WEIGHTED_AVERAGE 9, MOVING_AVERAGE 2) |
| total | **4722/4722 MATCH**, chaves únicas |
| diferenças | 0 de valor, 0 de state, 0 de detail, 0 estruturais, 0 exceções (`difference_types = {}`) |
| REAL_DERIVED | **não usado** na 3.4B: cada bloco roda isolado pela API pública comum às duas versões |
| reexecução nesta etapa | `run_differential.py --no-write` → PASS, 0 diferenças, 2352 + 2370 = 4722 MATCH |

**Candidate registrado:**
- a evidência registra `95e7ade` porque o diferencial foi executado sobre aquele HEAD;
- o commit de fechamento `4d54804` só adicionou `audit/stage3_4/` e `tests/`, então o `app/` comparado é o mesmo.

**Mudança posterior no harness:** na 3.4D, `run_differential.py` foi dividido em `produce()` (pré-condições e execução isolada) e `evaluate()` (universo, cobertura e comparação exata), sem mudar a lógica. Isso permitiu reaplicar o comparador real a cópias mutadas. A reexecução do diferencial não mutado continua 4722/4722.

**Limitação:** o diferencial demonstra **equivalência** entre as versões comparadas nos cenários executados. Não é oráculo independente de correção de negócio.

---

## 6. Integrated regression (3.4C)

| item | observado |
|---|---|
| alvos | **421/421** executados em todas as datas [evid; recalculado: §4] |
| nós | **427/427**, ordem igual à do plano; 0 planner-only, 0 engine-only |
| transferências | **12/12**; **1920/1920** eventos verificados (consumidor = produtor em value, state e detail) |
| datas | **32**, 2026-01-01 → 2026-02-01, contíguas, no mesmo contexto |
| orquestrador × engine | 12 544 comparações de equações, 0 diferenças; ambos usam o mesmo engine (L3) |
| ciclo production ↔ yield | só entre blocos; todos os nós produtores precedem os consumidores no plano |
| evidência | `integrated/evidence/*` **inalterada desde `043fe9c`** [obs: `git diff 043fe9c -- audit/stage3_4/integrated/evidence` vazio] |
| reexecução do harness nesta etapa | `run_integrated.py --no-write` → PASS, 421/421 alvos, 427/427 nós, 0 problemas |

---

## 7. State coverage

Todos os estados nos quatro blocos são **injetados** no fixture (3.4A §16). A execução real usa execuções gêmeas com oráculo de diferença.

| caso | evidência [evid, `integrated_summary.json` → `state`] |
|---|---|
| propagação | SC1: VAR12024 com `INVALID_INPUT/"fa"` em janeiro. Chegam ao estado 6452 chaves, todas descendentes, nos 4 blocos (production 1901, yield 1240, energy 1395, max_ht 1914) |
| isolamento | outras linhas (L1), o ramo inativo (L4) e fevereiro sem estado; contexto limpo com 0 estados |
| EQ12012 | ramo ativo (L3) propaga pelo produtor e por 3 transferências (VAR11031, VAR13062, VAR18008); ramo inativo (L4) não propaga |
| EQ18003, ramo ativo | L1 = `["NoneType","None","VALIDATION_FAILED","t"]`: `VALIDATION_FAILED` com detail `"t"` propaga a 19 variáveis de energy |
| EQ18003, ramo inativo | L2 = `["float","1.4509999999999998",null,null]`: sem vazamento |
| transferências com estado | 11/12 transferências carregam estado no SC1, com state e detail idênticos ao produtor. A exceção, VAR18011, tem como origem uma entrada |
| agregação: state e detail | SC3: AVERAGE, SUM (mensal e anual), WEIGHTED_AVERAGE e MOVING_AVERAGE reais; sem estado antes da injeção; `INVALID_INPUT/"agg"` com value None depois (Policy B) |
| composições | `MULTI_STATE_COMBINATION_UNDEFINED`, `MULTI_DETAIL_COMPOSITION_UNDEFINED` e `DETAIL_WITHOUT_STATE` |

**Contrato inalterado:** o estado afeta só descendentes da execução que o originou, ramos independentes ficam isolados e o detail acompanha o estado. Nenhuma interpretação nova foi introduzida nesta etapa.

---

## 8. Temporal coverage

| item | observado |
|---|---|
| datas | 32 (2026-01-01 → 2026-02-01) |
| identidades mensais | 313 em janeiro, cada uma com exatamente 31 janelas (`window_end` 01..31); 313 em fevereiro, janela única 2026-02-01 |
| identidades anuais | 185 (das 48 regras anuais), cada uma com 32 janelas |
| chaves diárias | sem `window_end` |
| janeiro após 2026-02-01 | inalterado (snapshot) |
| classificação | **`YEAR_TO_DATE_PARTIAL_COVERAGE`**. **Não** é cobertura anual completa |

**Identity ≠ window:** a identidade temporal é `(entidade, escopo, period_id)`; `window_end` distingue as janelas efetivas de uma mesma identidade de período. Janelas diferentes geram chaves diferentes, e a mesma janela gera a mesma chave (§9).

---

## 9. Reexecution

| data | FIRST_RUN | REEXECUTION | store | chaves novas | estados residuais |
|---|---|---|---|---:|---:|
| 2026-01-15 | 60 transferências `WRITTEN` | 60 `UNCHANGED` | idêntico | 0 | 0 |
| 2026-02-01 | 60 `WRITTEN` | 60 `UNCHANGED` | idêntico | 0 | 0 |

- Os eventos da reexecução são iguais aos da primeira execução; só o status das transferências muda.
- A mesma identidade temporal não cria identidade nova.
- Uma reexecução com entrada **diferente** a montante de uma transferência é barrada pelo próprio engine com `INTERBLOCK_CONSUMER_VALUE_CONFLICT` (3.4D MUT-R06).

---

## 10. Determinism

| execução | configuração | results_sha256 | store_sha256 |
|---|---|---|---|
| RUN_A | processo atual, ORDER_A | `d4de1aea…e10d` | `619b4abd…730c` |
| RUN_B | ORDER_B (catálogo, blocos e vínculos em ordem inversa), seed 0 | `d4de1aea…e10d` | `619b4abd…730c` |
| HASH_SEED_A | ORDER_A, PYTHONHASHSEED=0 | `d4de1aea…e10d` | `619b4abd…730c` |
| HASH_SEED_B | ORDER_A, PYTHONHASHSEED=4242 | `d4de1aea…e10d` | `619b4abd…730c` |
| REEXECUTION | store após as reexecuções | — | `619b4abd…730c` |

- Graph hash idêntico em todas as execuções: `e372425d…d1ff`.
- A ordem do plano é canônica nas duas ordens de entrada.

---

## 11. Mutation / audit closure (3.4D)

**Contagens:**

```text
58 evidence mutations + 17 code mutants = 75 mutations
75 / 75 detected (100%)
14 positive controls accepted = 13 evidence controls + 1 unmutated code control (CM-00)
```

**Decomposição das 58 mutações de evidência** [obs, `mutation_results.csv`]:

| grupo | contrato | mutações | detectadas |
|---|---|---:|---:|
| M1 | target | 3 | 3 |
| M2 | planner | 5 | 5 |
| M3 | interblock | 6 | 6 |
| M4 | state | 11 | 11 |
| M5 | aggregation | 6 | 6 |
| M6 | temporal | 5 | 5 |
| M7 | reexecution | 6 | 6 |
| M8 | determinism | 4 | 4 |
| M9 | differential | 6 | 6 |
| M10 | provenance | 6 | 6 |
| **total** | | **58** | **58** |

3 + 5 + 6 + 11 + 6 + 5 + 6 + 4 + 6 + 6 = 58.

**O que cada mutação de evidência registra:**
- evidência real de origem, com o caminho real correspondente;
- ponto de mutação, artefato e campo;
- valor antes e depois;
- código esperado e códigos obtidos.

**Cobertura por família de caminho real:**
- 3.4C trace, estado, temporal, reexecução e fingerprints: 43;
- saída real do diferencial 3.4B: 6;
- contrato real do app: 3;
- fixture e registro em cópia temporária: 6;
- somente sintéticas: 0.

**Os 17 mutantes de código** (contrato 3.4A §19; `code_mutation_results.csv`):

| ID | alvo §19 |
|---|---|
| CM-01 | AVERAGE (e MOVING, mesma aritmética) |
| CM-02 | SUM |
| CM-03 | integration_factor |
| CM-04 | WEIGHTED (peso) |
| CM-05 | MOVING (janela) |
| CM-06 | window_end |
| CM-07 | janela efetiva |
| CM-08 | interbloco, instância errada |
| CM-09 | interbloco, produtor errado |
| CM-10 | descarte de estado (equação) |
| CM-11 | descarte de estado (agregação) |
| CM-12 | escolha de estado |
| CM-13 | composição de detail |
| CM-14 | seleção de ramo IF |
| CM-15 | propagação estrutural do IF inativo |
| CM-16 | ordenação |
| CM-17 | determinismo (hash) |

**Metodologia, com precisão:**
- **CM-00** é o controle positivo: a árvore **não mutada**, aceita pelos três detectores.
- **CM-01 … CM-17** são 17 mutantes, cada um uma substituição textual única num arquivo de `app/`. Esta é uma correção à numeração "CM-01 … CM-16" do enunciado da 3.4E: são 17 mutantes.
  - Cada um foi aplicado **somente** a uma cópia temporária: `git clone --shared` de HEAD mais o harness atual, em `tempfile.TemporaryDirectory`.
  - `git status -- app data tools` do repositório ficou vazio antes e depois.
- No `run_mutation.py` completo (execução da 3.4D, repetida nesta etapa, §18), **os 17 mutantes foram executados** contra três detectores:
  1. a suíte existente de testes, exceto os três testes de harness da 3.4;
  2. a sonda integrada com os auditores da 3.4C (`mutant_probe.py`);
  3. o diferencial 3.4B.
- **Resultado:**
  - TESTS matou 17/17 e INTEGRATED 17/17;
  - DIFFERENTIAL matou 7/7 dos mutantes no caminho sem estado; os outros 10 estão fora do diferencial por construção (L6).
  - Alguns mutantes foram mortos por exceção do engine mutado: CM-06, CM-09, CM-10 e CM-11.
- **Dentro de `pytest`** (`tests/test_stage3_4d_mutation.py`), só **um** mutante de código (CM-13) roda ao vivo. Os outros 16 são verificados pela evidência versionada (`code_mutation_results.csv`) e pela auditoria black-box.
  - Formulação correta: todos os 17 mutantes foram executados em cópias temporárias e detectados pelo mecanismo de mutação e auditoria; apenas CM-13 roda diretamente no caminho de teste ao vivo.
  - Os mutantes **não** foram exercitados por uma "suíte de integração de produção".

---

## 12. G1–G5 findings

Durante a 3.4D, a sonda `mutation/baseline_gap_probe.py` extraiu, com `git archive`, o `audit/stage3_4/integrated` do commit **`043fe9c`** e aplicou mutações ao auditor **original** da 3.4C. É reproduzível: `python audit/stage3_4/mutation/baseline_gap_probe.py --no-write`. Evidência em `mutation/baseline_gap_probe.json`.

| gap | mutação | auditor original de 043fe9c | classificação |
|---|---|---|---|
| G1 | descendente perde o estado numa data não nomeada (só 2026-01-10 era conferida) | **não detectado (silencioso)** | fragilidade do auditor |
| G2 | valor presente junto com o estado propagado (o oráculo comparava só state/detail) | **não detectado (silencioso)** | fragilidade do auditor |
| G3 | transferência duplicada | não detectada pelo verificador interbloco; **detectada indiretamente** pelos contadores de nó (`NODE_EVENT_COUNT`) | fragilidade do auditor |
| G4 | transferência atribuída a outro alvo com o mesmo produtor | não detectada pelo verificador interbloco; **detectada indiretamente** pelos contadores de nó | fragilidade do auditor |
| G5 | identidade mensal derivada sem janela (filtro `None not in v`) | **não detectado (silencioso)**; registrado por inspeção do código de 043fe9c | fragilidade do auditor |

- **Detecção indireta de G3/G4:** a sonda confirma que o verificador interbloco original não reclama. O sinal indireto vem de `check_nodes`, cujo corpo é **byte a byte idêntico** ao de 043fe9c [obs]. Nas mutações MUT-TX05 e MUT-TX06 ele emite `NODE_EVENT_COUNT` (e mais sinais de nó em TX06).
- **Natureza:** as cinco são **fragilidades do harness de auditoria, não defeitos de correção de produção**. A execução real nunca produziu esses casos, e a evidência funcional da 3.4C continua verdadeira.
- **Relevância:** a descoberta não é irrelevante. Um auditor com G1/G2/G5 teria aceitado regressões reais de propagação de estado e de identidade temporal. Ela faz parte do histórico formal deste fechamento.

---

## 13. Strengthened auditor

**Arquivos do harness alterados na 3.4D** (`8095011`), todos em `audit/stage3_4/`:
- `integrated/checks.py`:
  - `check_state_diff` exige resultado state-only (G2);
  - `check_transfers` passa a conferir duplicidade, instâncias por data e blocos do vínculo (G3/G4);
  - funções novas `check_target_identities`, `check_temporal` (inclui G5: identidade derivada sem janela, janela fora do período, conjunto exato de janelas, snapshot de janeiro), `check_reexecution`, `check_determinism`, `check_clean_context` e `check_result_contract`.
- `integrated/run_integrated.py`:
  - expectativas de alcance dos cenários em **todas** as datas (G1);
  - cenários extraídos em funções reutilizáveis;
  - `node_expectations`, `transfer_expectations`, `expected_periods`, `target_records` e `derived_variables`;
  - gancho `--mutate-one-result`, usado só no modo fingerprint da 3.4D.
- `differential/run_differential.py`: `produce(mutate)` / `evaluate()` (§5).

**Execução original da 3.4C versus auditor reforçado:**
- A **execução e a evidência funcional originais da 3.4C** (`043fe9c`) não foram apagadas nem reescritas.
- O harness **não mutado** foi reexecutado com o auditor reforçado. A evidência regenerada saiu **byte a byte idêntica** [obs: `git diff 043fe9c -- audit/stage3_4/integrated/evidence` vazio], com 421/421, 427/427, 12/12, 32 datas e 0 problemas.
- O auditor reforçado é mais estrito e aceita a mesma execução.
- O comportamento de produção não mudou: `app/` é idêntico desde `f3b6588` (§16).
- O relatório da 3.4C não foi reescrito. A 3.4D é o registro canônico do reforço.

**Auditoria black-box** (`mutation/blackbox_audit.py`, contrato 3.4A §19):
- não importa `app/` nem os harnesses;
- confronta a evidência versionada da 3.4B, 3.4C e 3.4D com um oráculo escrito a partir do contrato;
- como processo **standalone isolado** (`python -I`), termina exigindo que nenhum `app.*` esteja em `sys.modules`: **PASS**, `imports_app = false` [obs].

**Ambiente in-process versus subprocesso isolado:**
- Chamada **dentro** do processo do pytest, a verificação de import dava falso positivo, porque outros testes já tinham importado `app`.
- Por isso ela vale só na execução isolada. In-process, os testes usam `check_imports=False` e testam a sensibilidade a seis corrupções de evidência.
- A propriedade "não importa app" é provada pelo subprocesso `python -I`.

---

## 14. REAL_DERIVED fixture

| item | observado |
|---|---|
| classificação | `REAL_DERIVED = TEST_FIXTURE_ONLY` (DR-2) |
| graph hash oficial | `e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff` [obs, recalculado] |
| construção | catálogo oficial dos seeds; registro de vínculos reconstruído **em memória** a partir de `interblock_links.json` |
| pendências | `pending = []` **somente** no fixture (0); registro oficial com **16** `PENDING_LOAD` [obs] |
| `interblock_links.json` | byte a byte igual a `7877551` e a `f3b6588` [obs]; sha256 `e96ff489…b697` |
| vínculos carregados | 13; 12 usados pelos quatro blocos; `yield.VAR11031 → area_41.VAR16007` fora do universo integrado |
| promoção a produção | nenhuma: o fixture não existe em `app/`, e nenhum resultado REAL_DERIVED é proveniência operacional |

As mutações M10 (3.4D) provam que o auditor detecta:
- rotulagem ou classificação operacional;
- pendências alteradas no fixture;
- registro oficial mascarado em memória;
- registro persistente alterado ou mascarado (numa cópia temporária de `data/seed`).

---

## 15. D32-01

```text
D32-01 = CLOSED_FOR_STAGE_3_SCOPE
```

| aspecto | situação |
|---|---|
| validado | engine, planner, os 13 vínculos carregados, cálculo, agregação, estados, temporalidade, reexecução e determinismo, **sobre o grafo carregado**, em REAL_DERIVED, e o planejamento oficial (446 planos iguais a `plan_evidence.csv`, com as 287 recusas `INTERBLOCK_SOURCE_NOT_LOADED`) |
| deliberadamente não implementado | execução oficial das cadeias com production calculado; carregamento de maintenance, forecast, temperature_lp, area_04_13 e alumina; modo operacional de entrada de fronteira |
| vínculos pendentes | continuam **16 `PENDING_LOAD`**: maintenance 9, temperature_lp 3, forecast 2, area_04_13 1, alumina 1 [obs] |
| REAL_DERIVED | não altera o registro oficial |
| workarounds | nenhum mecanismo de fixture foi promovido a produção |

D32-01 **não** está "implementado"; está **fechado para o escopo da Stage 3** (DR-1). D32-02 está resolvida na 3.3B (identidade temporal por janela efetiva).

---

## 16. Production-surface protection

[obs] Verificado por `reconcile.py` e pelos comandos abaixo.

```text
git diff --stat 7877551 -- data tools             -> vazio   (invariante da referência do diferencial)
git diff --stat f3b6588 -- app data tools         -> vazio   (baseline da 3.4A: nenhuma mudança na 3.4)
git diff --stat 8095011 -- app data tools         -> vazio   (nesta etapa)
git status --porcelain -- app data tools          -> vazio
git diff --name-only f3b6588 8095011              -> somente audit/stage3_4/** e tests/test_stage3_4*.py
data/seed/interblock_links.json                   -> byte a byte igual a 7877551 e f3b6588
```

| artefato | situação |
|---|---|
| `app/` | inalterado desde `f3b6588` |
| `data/seed/` (seeds, manifests, `interblock_links.json`) | inalterado desde `7877551` |
| `data/workbooks/` (7 arquivos, sha256 registrados em `closure_reconciliation.json`) | inalterado |
| `data/id_ledger/` | inalterado |
| `tools/` | inalterado desde `7877551` |
| testes e auditorias anteriores à 3.4 | inalterados; a 3.4 só adicionou `audit/stage3_4/**` e `tests/test_stage3_4*.py` (contrato 3.4A §22) |

As alterações de harness da 3.4D (§13) atingiram apenas artefatos **da própria Stage 3.4**. Nenhum teste ou auditoria anterior à 3.4 foi alterado.

**Findings desta etapa:**

| # | finding | classificação |
|---|---|---|
| F1 | o enunciado da 3.4E numera os mutantes como "CM-01 … CM-16"; a evidência tem 17 mutantes, CM-01 … CM-17, mais o controle CM-00 | DOCUMENTATION_ONLY (registrado aqui) |
| F2 | a evidência da 3.4B registra o candidate `95e7ade`, não `4d54804`; os dois têm o mesmo `app/` | DOCUMENTATION_ONLY (registrado no §5) |
| F3 | `origin/HEAD` não configurado no clone; a verificação usou `origin/feature/area-41-block` | DOCUMENTATION_ONLY |

Nenhum finding é BLOCKER ou REQUIRES_FOLLOWUP.

---

## 17. Limitations

| # | limitação |
|---|---|
| L1 | **Sem oracle numérico independente completo** (`INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE`). O diferencial demonstra equivalência, não correção de negócio absoluta. O oracle Python do energy cobre só 23 equações diárias e não foi usado na 3.4C |
| L2 | **REAL_DERIVED é fixture sintético** derivado dos artefatos reais, com entradas de fronteira arbitrárias. Não representa carregamento operacional dos workbooks ausentes |
| L3 | **Engine compartilhado:** a comparação orquestrador × engine e partes da validação integrada usam os mesmos componentes de execução, o que limita a independência do oráculo |
| L4 | **YTD parcial:** 32 datas; janelas anuais só até 32 dias; a virada de ano não é exercitada. Não há cobertura de ano fiscal completo |
| L5 | **Ciclo interbloco:** production ↔ yield foi exercitado no nível de bloco; não é prova de convergência variável a variável de um ciclo operacional completo |
| L6 | **Diferencial sem estado:** a 3.4B não valida estado, detail, janelas nem orquestração. Mutantes dessas áreas são detectados pelos testes e pela auditoria integrada |
| L7 | **Mutação de código verificada por evidência no pytest:** os 17 mutantes foram executados em cópias temporárias pelo driver completo; dentro do `pytest` só CM-13 roda ao vivo (§11) |
| L8 | **Regeneração de evidência:** a regressão integrada compara com a evidência versionada da 3.4C. Mudanças intencionais futuras de comportamento exigirão regenerar e reaprovar essa evidência |
| L9 | Sem execução oficial das cadeias com production calculado: 287 dos 446 alvos oficiais continuam bloqueados (DR-1) |
| L10 | Os quatro blocos não têm fonte nativa de estado; a cobertura de estado é por injeção |

---

## 18. Reproducibility commands

Executados nesta etapa, a partir de uma árvore limpa em `8095011` com os artefatos da 3.4E:

| # | comando | resultado nesta etapa | tempo aprox. |
|---|---|---|---|
| 1 | `python -m pytest -q` | **1859 passed**, 0 failed, 0 skipped (≈ 7 min nesta máquina) | 5 min |
| 2 | `python audit/stage3_4/differential/run_differential.py --no-write` | PASS, 0 diferenças, 2352 + 2370 = 4722 MATCH | 20 s |
| 3 | `python audit/stage3_4/integrated/run_integrated.py --no-write` | PASS, 421/421 alvos, 427/427 nós, 0 problemas | 70 s |
| 4 | `python audit/stage3_4/mutation/run_mutation.py --no-write` | PASS, 58/58 mutações detectadas, 17/17 mutantes mortos, 0 sobreviventes, CM-00 ACCEPT, 13/13 controles de evidência ACCEPT | 8 min |
| 4b | `python audit/stage3_4/mutation/run_mutation.py --no-write --skip-code-mutants` | variante rápida sem os mutantes de código | 1,5 min |
| 5 | `python -I audit/stage3_4/mutation/blackbox_audit.py --no-write` | PASS, `imports_app = false` | < 1 s |
| 6 | `python audit/stage3_4/mutation/baseline_gap_probe.py --no-write` | reproduz G1–G5 contra 043fe9c | 15 s |
| 7 | `python audit/stage3_4/closure/reconcile.py --no-write` | PASS, 31/31 linhas, 0 problemas | 15 s |
| 8 | `git diff --stat f3b6588 -- app data tools` e `git diff --stat 7877551 -- data tools` | vazios | — |

**Flags:**
- `--no-write` não altera nenhum arquivo versionado.
- Sem `--no-write`:
  - os scripts 2–4 e 7 regeneram a própria evidência;
  - o 2 regista o HEAD atual como candidate;
  - por isso a evidência histórica foi mantida e as reexecuções desta etapa usaram `--no-write`.

---

## 19. Final gate

| # | critério | resultado |
|---|---|---|
| 1 | baseline reconciliado | PASS (`8095011` = origin, árvore limpa) |
| 2 | evidência 3.4A reconciliada | PASS (§3.3) |
| 3 | evidência 3.4B reconciliada | PASS (4722/4722; §5) |
| 4 | evidência 3.4C reconciliada | PASS (421/427/12/1920/32; §6) |
| 5 | evidência 3.4D reconciliada | PASS (§11) |
| 6 | cardinalidades reconciliadas | PASS (31/31 linhas, `closure_reconciliation.json`) |
| 7 | G1–G5 documentados | PASS (§12) |
| 8 | auditor reforçado documentado | PASS (§13) |
| 9 | 58 mutações de evidência reconciliadas | PASS |
| 10 | 17 mutantes de código reconciliados | PASS |
| 11 | 75/75 detecção | PASS |
| 12 | 14 controles positivos | PASS |
| 13 | suíte completa verde | PASS (1859 passed, 0 failed, 0 skipped) |
| 14 | superfície de produção intacta | PASS (§16) |
| 15 | registro oficial intacto | PASS |
| 16 | vínculos pendentes continuam pendentes | PASS (16 `PENDING_LOAD`) |
| 17 | D32-01 = `CLOSED_FOR_STAGE_3_SCOPE` | PASS |
| 18 | limitações documentadas | PASS (§17) |
| 19 | comandos de reprodução documentados | PASS (§18) |
| 20 | nenhuma alteração funcional de produção no fechamento | PASS |

```text
FINAL_STAGE_3_GATE = PASS
STAGE 3 = CLOSED
```

---

## 20. Final Stage-3 scope boundary

**O que a Stage 3 FECHOU:**
- contrato global de resultado (value, state, detail; taxonomia de estados; `DETAIL_WITHOUT_STATE`) — 3.3A/3.3B;
- propagação causal de estados e isolamento, incluindo o IF causal — 3.3B, validados na 3.4C e 3.4D;
- planner e orquestração interbloco: plano, ordem canônica, ciclo de bloco, recusas `INTERBLOCK_SOURCE_NOT_LOADED` — 3.1/3.2;
- equações (392 instâncias) e agregações (395 instâncias; AVERAGE, SUM, ×24, WEIGHTED_AVERAGE, MOVING_AVERAGE) com a Policy B — 3.3C;
- identidade temporal por janela efetiva e reexecução idempotente (D32-02) — 3.3B;
- regressão integrada interbloco dos 421 alvos no grafo carregado (REAL_DERIVED) — 3.4C;
- determinismo (hash seeds, ordens de blocos e de vínculos) — 3.4C;
- regressão diferencial `7877551 × HEAD` no caminho sem estado — 3.4B;
- cobertura de mutação e auditoria (75/75), controles positivos e auditoria black-box — 3.4D;
- proveniência: REAL_DERIVED só como fixture; registro oficial intacto — 3.4A/3.4D;
- D32-01 `CLOSED_FOR_STAGE_3_SCOPE` — 3.4A, consolidado aqui.

**O que NÃO foi implementado na Stage 3** (fora do escopo aprovado, não pendência obrigatória):
- carregamento operacional dos 16 vínculos `PENDING_LOAD`;
- os workbooks ausentes (maintenance, forecast, temperature_lp, area_04_13, alumina);
- execução oficial das cadeias fora do conjunto carregado;
- oracle numérico independente completo;
- convergência variável a variável do ciclo production ↔ yield;
- cobertura temporal anual completa.

**Condição de saída para o próximo estágio:**
- a Stage 3 está fechada;
- qualquer trabalho sobre os itens "não implementados" exige nova decisão e novo contrato, e não reabre os gates da Stage 3;
- uma mudança intencional de comportamento exige regenerar e reaprovar a evidência versionada das 3.4B/3.4C (L8).

---

## Historical note — D-TAX-01 (posterior a este fechamento)

Depois do fechamento acima (`547b920`), o proprietário tomou uma decisão normativa nova, **D-TAX-01**:
- o registro canônico de blocos passou a ter **29 blocos**, na ordem das faixas de ID, incluindo `budget_vs_forecast`;
- a faixa 30000–30999 passou a se chamar `thickener_flocculant` (antes `monthly_ppt_assumptions`).

A mudança é exclusivamente de nomenclatura:
- IDs, fórmulas, vínculos, os 16 `PENDING_LOAD`, cardinalidades (446/421/427, 218/392, 197/395, 12, 32 datas, 313/313/185), fingerprints e o hash do grafo REAL_DERIVED são idênticos;
- a prova está em `audit/stage3_4/taxonomy_migration/evidence/migration_reconciliation.json`.

Os guardas da Stage 3 passaram a aceitar **somente** esse diff, provado arquivo a arquivo por `audit/stage3_4/taxonomy_migration/taxonomy_guard.py`. Qualquer outra alteração em `app/`, `data/` ou `tools/` continua falhando.

Os fatos e números deste documento descrevem o estado em `547b920` e **não** foram reescritos. O gate da Stage 3 não é reaberto. Ver `audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md`.

---

## Historical note — taxonomy decisions after Stage 3 closure (append-only)

```text
D-TAX-01  Canonical 29-block taxonomy            Status: APPLIED
D-TAX-02  Historical cost-block crosswalk        Status: APPLIED
Known architectural debt: two physical taxonomy projections remain (TD-TAX-01, OPEN)
```

- **D-TAX-02** formaliza `custo_budget → budget_cost`, `custo_forecast_bdgt → budget_forecast_cost` e `custo_forecast_real → actual_forecast_cost`:
  - os três são **CONFIRMED** por registro explícito de rename (commit `1d3276e`) e pela mesma faixa nos três registries;
  - os nomes históricos não são operacionais;
  - a tradução é feita só pelo crosswalk `taxonomy_migration/cost_crosswalk_d_tax_02.json`.
- **TD-TAX-01**: a taxonomia canônica é única, mas fisicamente tem duas implementações (`app/validation` e `tools/workbook_seed/taxonomy.py`), porque `app/` não importa `tools/`.
  - A equivalência das 5 projeções é imposta por `taxonomy_guard.check_projections` e por testes.
  - Não é bloqueador funcional.
  - Ver `TECH_DEBT_TAXONOMY_DUPLICATION.md`.
- Pendências atualizadas em `PLATFORM_PENDING_ITEMS.md`. Os 16 vínculos continuam `PENDING_LOAD`.
- Nenhuma alteração funcional:
  - IDs, faixas, fórmulas, planner, vínculos e cardinalidades estão iguais;
  - `app/` só teve comentários trocados, com AST idêntico.

Os fatos e números deste documento continuam descrevendo `547b920`. `FINAL_STAGE_3_GATE` permanece **CLOSED**, e as 3.4A–3.4E não foram reabertas.
