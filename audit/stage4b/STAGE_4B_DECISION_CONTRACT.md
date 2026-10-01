# Stage 4B — Contrato e auditoria: cobertura temporal anual, virada de ano e ciclos

| campo | valor |
|---|---|
| etapa | 4B.1 — auditoria e contrato (sem código de produção) |
| baseline | `main` = `0a924e66cfd0774a13e46a332b460b770283a554` (Stage 4A mergeada por fast-forward) |
| branch | `feature/stage-4b-temporal-annual` |
| rótulo | `REAL_DERIVED_TEST_RESULT` (fixture REAL_DERIVED de 5 blocos; protocolo de entradas DR-4A-5) |
| superfície de produção | congelada: `app/`, `data/`, `tools/` não são alterados |
| evidência | `audit/stage4b/evidence/contract_audit_4b.json`, `performance_probe.csv`; expectativas em `contract_expectations_4b.json` |

Os números do contrato vêm de dois caminhos, que concordam:
- **empírico** (`derive_4b.py`): engine real, em contextos próprios;
- **independente** (`independent_calendar.py`, `python -I`, sem `app/`): só `datetime`/`calendar`, os JSON dos seeds e um Tarjan próprio.

---

## 0. Baseline (Fase 0)

| verificação | esperado `[ref]` | observado |
|---|---|---|
| `main` contém a 4A | sim | sim (`audit/stage4a/STAGE_4A_FINAL_CLOSURE.md` presente; HEAD `0a924e6`) |
| hashes `f3b6588`, `7877551`, `8095011` | presentes | HASHES_OK |
| árvore | limpa | limpa |
| `python -m pytest -q` | 1964 passed | **1964 passed**, 0 failed, 0 skipped (7 min 05 s) |
| `run_integrated_4a.py --no-write` | PASS | PASS |
| `run_integrated.py --no-write` (3.4C) | PASS | PASS |
| `reconcile_4a.py --no-write` | PASS | PASS, 42/42 |
| `python -m tools.workbook_seed` + `git status` | vazio | vazio |

---

## 1. Mecânica temporal (§3.1)

**Lido no código:**
- `app/engine/time_period_resolver.py`;
- `app/engine/calculation_context.py` (D33B-04);
- `app/engine/temporal_aggregation_service.py`.

**Confirmado por experimento:** `contract_audit_4b.json → mechanics`.

| frequência | `period_id` | janela efetiva em `run_date` | chave no store |
|---|---|---|---|
| diário | `AAAA-MM-DD` (10 caracteres) | `start = end = run_date` | `(var, st, sv, "AAAA-MM-DD", None)` |
| mensal | `AAAA-MM` (7) | 1º do mês → `run_date` | `(var, st, sv, "AAAA-MM", run_date)`, uma chave por janela |
| anual | `AAAA` (4) | 1º de janeiro → `run_date` | `(var, st, sv, "AAAA", run_date)`, uma chave por janela |

**`window_for(period_id, as_of)`.** Preenche `window_end = as_of` só se `as_of` começa com `period_id + "-"`. Resultados medidos:
- `("2026", "2026-01-01")` → `2026-01-01`;
- `("2026-01", "2026-02-01")` → `None`;
- `("2026", "2027-01-01")` → `None`;
- diário → `None`.

Um período encerrado nunca recebe janela de uma data posterior.

**Entradas.** Entradas mensais e anuais são gravadas fora da janela, com `window_end = None`, chave do período inteiro. A leitura procura primeiro a chave com janela e depois a do período. Não existe leitura de outro `period_id`.

**Agregações.** As 207 regras são:

| tipo | regras | origem → destino |
|---|---|---|
| AVERAGE | 166 | diário → mensal (129) / anual (37) |
| SUM | 30 | diário → mensal (15) / anual (15) |
| WEIGHTED_AVERAGE | 9 | diário → mensal (8) / anual (1) |
| MOVING_AVERAGE | 2 | diário → diário |

Como as janelas são derivadas:
- **AVERAGE, SUM, WEIGHTED_AVERAGE:** janela = período efetivo da frequência de destino (1º do mês ou 1º de janeiro → `run_date`).
- **MOVING_AVERAGE:** sempre 1º do mês → `run_date`, mesmo com destino diário. Reinicia em todo dia 1.
- **Anual:** é o YTD (1º de janeiro → `run_date`).
- **Janela explícita:** nenhuma regra tem `window_start_date`/`window_end_date`.

**Colisões.** Verificadas num store real de 408 722 chaves (2026-01-01..2027-01-03):

| verificação | resultado |
|---|---|
| entidade com mais de um formato de `period_id` | 0 de 508. Cada entidade tem uma única frequência |
| entidade com `period_id` mensal e anual | 0. Mensal e anual de uma mesma grandeza são **variáveis distintas** (ex.: VAR16019 mensal × VAR16020 anual) |
| janela fora do próprio período | 0 |
| mês × ano | `2026-01` (7) ≠ `2026` (4) ≠ `2026-01-01` (10) |
| anos | `2026` ≠ `2027`; as janelas de 2026 terminam em `2026-12-31` |

```text
Colisão de identidade entre frequências, meses e anos: NENHUMA.
```

---

## 2. Experimentos controlados (§3.2)

Todos foram feitos em contextos próprios (engine real, fixture de 5 blocos).

### E1 — virada de mês e de ano (contexto populado até 2026-12-27; 2026-12-28 → 2027-01-03)

| data | período mensal | período anual | janelas de `retirada_condensado_grupo` mensal L1_L3 (VAR16019) | janelas anuais (VAR16020) | eventos (transferências) |
|---|---|---|---|---|---|
| 2026-12-31 | `2026-12` | `2026` | 31 | **365** | 896 (67) |
| 2027-01-01 | `2027-01` | `2027` | **1** | **1** | 896 (67) |
| 2027-01-03 | `2027-01` | `2027` | 3 | 3 | 896 (67) |

- Ao fim de 2026, as **196 identidades anuais têm 365 janelas cada**. Em 2027-01-03, as 196 de 2027 têm 3 janelas.
- **Snapshot de 2026** (405 277 chaves com `period_id` iniciado por `2026`, hash `5d8a789a…`):
  - **idêntico** em 2027-01-01 e depois de 2027-01-03;
  - o mesmo vale para dezembro de 2026.

### E2 — lacunas

| caso | comportamento observado |
|---|---|
| executar 2026-01-01..05, **pular 2026-01-06**, executar 2026-01-07 | **falha explícita**: `VariableNotFoundError` (… `period_id=2026-01-06`) |
| contexto novo começando em 2026-01-10 | falha explícita (`period_id=2026-01-01` ausente) |
| contexto novo começando em 2026-02-01 | falha explícita: a janela anual exige 2026-01-01 |

```text
Política de lacunas observada: EXPLICIT_FAILURE — nenhuma média parcial silenciosa.
```

A falha é o `VariableNotFoundError` genérico do primeiro sub-período ausente, não um código específico de lacuna (F4B-02).

### E3 — entradas do período novo ausentes (cópia do contexto em 2027-01-07)

| entrada removida | resultado |
|---|---|
| anual `lth_meta` (VAR12066) de `2027` | **falha explícita** `VariableNotFoundError` (o valor de 2026 existe e **não** é reaproveitado) |
| mensal `vazao_ltp` (VAR16001) de `2027-01`, lida incondicionalmente | **falha explícita** |
| mensal `fator_ajuste_lth` (VAR12024) de `2027-01`, ramo IF inativo | **sem falha, porque não é lido** (IF causal 3.3B). Prova: trocar o valor por 999 gera 0 diferenças nos resultados |
| a mesma, com o ramo IF forçado (`lth_meta = 0.0001`, como no SC1 da 3.4C) | **falha explícita** |

```text
Carry-over de entrada entre períodos: NENHUM.
```

### E4 — períodos encerrados

Depois da virada:
- reexecutar 2026-06-15 e 2026-12-31 dá **0 chaves novas**, **0 chaves alteradas** e 67 transferências `UNCHANGED`;
- executar 2027-01-04..06 depois disso mantém o snapshot de 2026 **idêntico** (`5d8a789a…`).

### E5 — calendário

| caso | resultado |
|---|---|
| fevereiro de 2026 (28 dias), abril (30), julho (31) | janelas mensais por identidade = 28 / 30 / 31 |
| 2028 (bissexto), de 2028-01-01 a 2028-03-02 | fevereiro com **29** janelas; 2028-02-29 diário presente; março com 2 janelas; anual com **62** janelas nas 196 identidades |

---

## 3. Análise estrutural de ciclos (§3.3)

O grafo foi construído com um algoritmo independente (`independent_calendar.cycle_analysis`): Tarjan iterativo próprio, sem o `DependencyGraph` do engine, a partir das equações, regras e vínculos dos 5 blocos.

| nível | nós / arestas | componentes cíclicos |
|---|---|---|
| **instância** (variável × escopo, na mesma data) | 1 227 / 2 041 | **nenhum** |
| variável | 505 | nenhum |
| bloco | 5 | **{production, yield}**, só entre blocos |

Detalhes:
- **Construção conservadora.** Uma referência sem sufixo a uma variável sem a mesma instância é ligada a **todas** as instâncias dela. Mesmo assim o grafo é acíclico.
- **Defasagem.** Nenhuma referência a período anterior (`t-1`, `[n]`, `lag(` …) existe nas expressões, nenhuma agregação lê a própria saída e nenhuma regra tem janela explícita. A única dependência temporal é agregação → sub-períodos ≤ `run_date` da variável-fonte.
- **Verificação empírica.** O plano de 458 nós está em ordem topológica válida (todo produtor antes do consumidor).

```text
production <-> yield: ciclo apenas no nível de bloco; ACÍCLICO no nível de instância.
```

---

## 4. Desempenho e tamanho (§3.4)

Perfil de 361 datas (2026-01-01..2026-12-27) em `evidence/performance_probe.csv`:

| grandeza | valor |
|---|---|
| tempo médio por data, primeiras 32 | 0,171 s |
| tempo médio por data, datas 330–361 | 0,318 s |
| razão final/início | **1,85×** (crescimento ≈ linear com o store; leitura das janelas anuais) |
| crescimento do store | +1 109 chaves por data e +1 143 no dia 1 de cada mês. **Igual** ao previsto de forma independente pelas identidades dos seeds: 376 diárias derivadas + 324 mensais + 196 anuais + 213 entradas diárias, mais 34 entradas mensais no dia 1 |
| store após 361 datas | 400 841 chaves |
| estimativa T1 (396) / T2 (62) / T3 (792) | ≈ 126 s / 20 s / 377 s (com folga de 1,5× em T3) |

**Limite (DR-4B-6):** a razão entre o tempo médio das últimas 32 datas e o das primeiras 32 de uma execução não pode passar de **3,0**. Acima disso, registrar como `REQUIRES_FOLLOWUP`.

---

## 5. Planejamento das execuções (§3.5)

| execução | intervalo | datas | decisão |
|---|---|---|---|
| **T1** | 2026-01-01 → 2027-01-31, contexto único | **396** | obrigatória |
| **T2** | 2028-01-01 → 2028-03-02, contexto novo (bissexto) | **62** | obrigatória |
| **T3** | 2026-01-01 → 2028-03-02, contexto único | **792** (não 790, ver F4B-01) | **executar**: a estimativa de cerca de 6 min é ≤ 2 h |

Expectativas por data, derivadas e recalculadas de forma independente:
- alvos **446**, nós **458**, **13** transferências (nós) e **67** eventos de transferência, **896** eventos;
- identidades derivadas: **376** instâncias diárias, **324** identidades mensais e **196** anuais;
- janelas por identidade mensal = dia do mês; em fim de mês, os dias do mês (28/29/30/31);
- janelas por identidade anual = dia do ano: **365** em 2026-12-31 e 2027-12-31, **1** em 2027-01-01, **60** em 2028-02-29.

Determinismo:

| execução | configurações | hashes comparados |
|---|---|---|
| T2 | ORDER_A, ORDER_B, `PYTHONHASHSEED` 0 e 4242 | resultados + store |
| T1 | ORDER_A e ORDER_B | resultados + store |

---

## 6. Decisões (§3.6)

As decisões são técnicas e foram aceitas por padrão: não há `BLOCKER` nem decisão técnica `UNRESOLVED`.

| id | decisão | recomendação | estado |
|---|---|---|---|
| DR-4B-1 | **invariante de prefixo**: as chaves de T1 das 32 primeiras datas são **idênticas** à evidência da 4A (valor, state, detail, identidade e janela). Subconjunto: diárias ≤ 2026-02-01; janelas ≤ 2026-02-01; entradas de período inteiro de `2026-01`, `2026-02` e `2026`. Hash igual ao `store_sha256` versionado da 4A | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4B-2 | **política de lacunas**: só registro. O comportamento atual é falha explícita (E2) e não é alterado | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4B-3 | **ano fiscal**: fora de escopo. Assume-se ano-calendário (YTD a partir de 1º de janeiro). Confirmar com o cliente se o ano de budget coincide com o calendário | registrar | `PROPOSED_ACCEPTED_BY_DEFAULT` (pendência de negócio) |
| DR-4B-4 | **T3 executada** (estimativa de cerca de 6 min) | executar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4B-5 | **entradas**: protocolo DR-4A-5. As entradas diárias variam com o dia do ano (`tm_yday`), então 2027 repete o padrão de 2026. Mensais e anuais são gravadas por período (sem carry-over) | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4B-6 | **limite de desempenho**: razão ≤ 3,0 (§4) | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4B-7 | **critérios do gate**: os 16 do §7 do prompt, todos PASS, com as expectativas congeladas em `contract_expectations_4b.json` | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |

---

## 7. Findings da Fase 1

| id | severidade | finding | evidência |
|---|---|---|---|
| F4B-01 | DOCUMENTATION_ONLY | o intervalo de T3 tem **792** datas, não 790 `[ref]` (365 + 365 + 31 + 29 + 2) | `independent_calendar.py` |
| F4B-02 | REQUIRES_FOLLOWUP | uma lacuna falha com o `VariableNotFoundError` genérico do primeiro sub-período ausente, sem código próprio. Uma execução **não pode começar no meio do ano**: as janelas anuais exigem todas as datas desde 1º de janeiro, e as mensais desde o dia 1. Para uso operacional (forecast a partir de uma data com realizado anterior), é preciso decidir como carregar o histórico. Decisão dos engenheiros; comportamento coerente com o contrato vigente | E2 |
| F4B-03 | DOCUMENTATION_ONLY | a ausência de uma entrada lida só num ramo IF inativo não é detectada até o ramo ser ativado (IF causal 3.3B). Não há carry-over | E3 |
| F4B-04 | DOCUMENTATION_ONLY | o tempo por data cresce cerca de 1,85× ao longo do ano (≈ linear com o store), dentro do limite de 3,0 | §4 |

```text
BLOCKER técnico: 0    decisão técnica UNRESOLVED: 0   => prossegue para a Fase 2.
```

---

## 8. Reprodução

```text
python -I audit/stage4b/independent_calendar.py --check
python audit/stage4b/derive_4b.py --no-write          # cerca de 3,5 min
python -m pytest -q tests/test_stage4b_contract.py
```
