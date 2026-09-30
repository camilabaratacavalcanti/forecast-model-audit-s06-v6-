# Stage 3.4A — Decision & Regression Contract (Closure)

Contrato formal e autocontido da Stage 3.4. Incorpora as decisões DR-1..DR-5 aprovadas pelo responsável e fecha a 3.4A. Etapa exclusivamente documental: nenhum arquivo de `app/`, `data/`, `tools/` ou `tests/` foi alterado.

Legenda: **[fato]** verificado no repositório ou por execução nesta etapa · **[doc]** declarado em relatório versionado · **[decisão]** decisão aprovada (DR-n).

---

## 1. Executive Summary

- **D32-01:** `CLOSED_FOR_STAGE_3_SCOPE` (DR-1). A execução oficial das cadeias com production calculado fica fora da Stage 3. Os 16 vínculos continuam `PENDING_LOAD (normativo)`. Nenhum bloco ausente foi carregado ou simulado.
- **REAL_DERIVED:** `TEST_FIXTURE_ONLY` (DR-2).
- **Regressão numérica:** `DIFFERENTIAL_REGRESSION_ORACLE`, referência `7877551` × candidato HEAD (DR-3).
- **Oracle numérico independente:** `INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE`, limitação conhecida (DR-4).
- **Regressão integrada:** os **421** alvos dos quatro blocos oficiais, em sequência diária a partir de 2026-01-01 (DR-5).
- **Cardinalidades reconciliadas a partir do código:**

| universo | quantidade |
|---|---:|
| alvos de planejamento oficiais (5 blocos) | 446 |
| alvos de regressão integrada (4 blocos) | 421 |
| nós do plano integrado | 427 |
| definições de equação | 218 |
| instâncias de equação | 392 |
| regras de agregação | 197 |
| instâncias de agregação (4 blocos) | 395 |
| instâncias de agregação (+ area_41) | 417 |
| casos de execução do experimento anterior | 834 |

- **Sub-stages seguintes:** 3.4B (diferencial), 3.4C (integrada), 3.4D (mutação e auditoria), 3.4E (fechamento da Stage 3).
- **Gate:** `STAGE_3.4A_GATE: PASS` (§25).

---

## 2. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD / origin antes desta etapa | `f3b6588` / `f3b6588` |
| árvore | limpa, exceto o próprio `audit/stage3_4/` (artefato desta etapa) |
| suíte | **1820 passed**, 0 failed, 0 skipped |
| `git diff 7877551..HEAD -- data tools` | vazio |

---

## 3. Histórico Stage 3.2–3.3C

| stage | commits | gate formal | observação |
|---|---|---|---|
| 3.1 | `e60af19`, `8ca9d01` | PASS | resolver interbloco |
| 3.2 | `11c8931`, `2cfc52a`, `a733487` | **READY_FOR_DECISION** | pendentes D32-01 e D32-02 (§11 do relatório) |
| 3.3A | `472949b`, `eee88d6` | PASS | contrato `Result` |
| 3.3B | `77f58ae`, `06a7907` (READY_FOR_DECISION) → `dd5696d`, `8900984`, `4faf5f1` (PASS) | PASS | D32-02 resolvida (identidade por janela) |
| 3.3C | `f3b6588` | PASS | Policy B |

- **[doc]** Nenhuma etapa posterior decidiu D32-01. A 3.3A §11 e a 3.3B §16 dizem "preservada"; a 3.3C não trata dela.
- **Consequência:** antes desta etapa, o único motivo do gate formal da 3.2 ser `READY_FOR_DECISION` era D32-01.

---

## 4. D32-01 Closure

- **Pergunta original** [doc, 3.2 §11]: como executar as cadeias reais com production calculado. O requisito 8 (cadeia ponta a ponta) e a regra 9 (pendência nunca preenchida) da 3.2 são incompatíveis sem os workbooks ausentes.
- **Alternativas registradas:**
  - (a) carregar maintenance, forecast, temperature_lp, area_04_13 e alumina;
  - (b) modo "entrada de fronteira" com proveniência.
- **Contrato já fechado** [doc, `audit/stage2_6c_interblock_final/contract_decisions.csv`, D26B-04]: os 16 vínculos são `PENDING_LOAD (normativo)`, "estado definido por D26-01, não decisão do proprietário".

**Status:** `CLOSED_FOR_STAGE_3_SCOPE` [decisão DR-1].

**Significa:**
- a Stage 3 não implementa a execução operacional das cadeias que dependem dos blocos ausentes;
- `INTERBLOCK_SOURCE_NOT_LOADED` continua sendo o comportamento oficial, no planejamento e com 0 gravações;
- `PENDING_LOAD` é preservado.

**Não significa:**
- que maintenance (ou outro bloco ausente) foi implementado;
- que o modelo operacional completo foi validado.

**Efeito sobre a 3.2:** a pendência que mantinha o gate formal da 3.2 em `READY_FOR_DECISION` está decidida para o escopo da Stage 3. O gate da Stage 3.2 **não é reescrito** neste artefato (documento histórico); a consolidação formal é responsabilidade da 3.4E (§20).

**Alvos oficiais planejáveis** [fato, igual à 3.2 §5 e a `plan_evidence.csv`]:

| bloco | alvos | executáveis | bloqueados | bloqueios por origem (um alvo pode ter vários) |
|---|---:|---:|---:|---|
| production | 50 | 0 | 50 | maintenance 47, forecast 23 |
| yield | 219 | 155 | 64 | maintenance 64 |
| energy | 43 | 1 | 42 | maintenance 37, temperature_lp 30, area_04_13 18 |
| max_ht | 109 | 0 | 109 | maintenance 89, alumina 61 |
| area_41 | 25 | 3 | 22 | maintenance 22 |
| **total** | **446** | **159** | **287** | maintenance 259 |

---

## 5. DR-1 — execução oficial completa

**Decisão:** a execução oficial de cadeias com production calculado permanece fora do escopo da Stage 3.

**Restrições derivadas (vinculantes para 3.4B..3.4E):**
- não carregar maintenance, forecast, temperature_lp, area_04_13 nem alumina;
- não alterar workbooks, seeds, `interblock_links.json` ou ledgers;
- não criar modo operacional de entrada de fronteira;
- não transformar REAL_DERIVED em modo operacional;
- não preencher pendências como se fossem fontes oficiais.

## 6. DR-2 — REAL_DERIVED

**Decisão:** `REAL_DERIVED = TEST_FIXTURE_ONLY`.

## 7. DR-3 — Differential Regression Oracle

**Decisão:**
- `reference_commit = 7877551`;
- `candidate_commit = HEAD da sub-stage que executa o diferencial`;
- `oracle_type = DIFFERENTIAL_REGRESSION_ORACLE`.

## 8. DR-4 — ausência de oracle numérico independente

**Decisão:** `INDEPENDENT_NUMERIC_ORACLE = NOT_AVAILABLE`. É limitação conhecida, não falha da Stage 3.

## 9. DR-5 — 421 alvos

**Decisão:** a regressão integrada usa os **421** alvos, executados em sequência temporal iniciada em 1º de janeiro. A reconciliação está no §14.

---

## 10. REAL_DERIVED contract

**Definição** [fato]:
- `tests/test_stage3_2_execution_orchestration.py::real_derived_orchestrator`, replicada nas sondas das auditorias 3.3B e 3.3C;
- carrega o catálogo oficial e reconstrói **em memória** o `InterblockLinkRegistry` com `pending = []`;
- as variáveis consumidoras dos 16 vínculos pendentes viram `required_inputs` livres, preenchidas pelo teste;
- não existe em `app/`; não altera seeds nem links.

**Classificação:** `TEST_FIXTURE_ONLY`. Não é:
- modo operacional;
- fonte de dados;
- solução de D32-01;
- proveniência operacional;
- representação do modelo completo.

**Uso permitido:** validar engine, planner, os 13 links carregados, cálculo, agregação, estados, temporalidade, determinismo e reexecução — sempre **sobre o grafo carregado**.

**Rotulagem obrigatória:** todo resultado obtido com o fixture deve ser identificado como "REAL_DERIVED (fixture de teste; entradas de fronteira arbitrárias; grafo carregado)", em testes, auditorias e relatórios.

---

## 11. Differential Oracle contract

**Validade da referência** [fato]:
- `7877551` tem `app/`, `data/` e `tools/` idênticos a `68cb5a1` (fechamento 2.6C);
- a primeira mudança da Stage 3 em `app/` é `e60af19`;
- `git diff 7877551..HEAD -- data tools` está vazio.

**Pergunta respondida:** "A implementação atual produz resultados diferentes do baseline pré-Stage-3 para os mesmos inputs?"

**Não responde:** "O resultado atual está absolutamente correto?"

**Limitações:**
1. erro comum às duas versões fica invisível;
2. mesmo parser;
3. mesma aritmética e mesma interpretação de escopo e período;
4. não há saídas operacionais independentes;
5. só vale enquanto `git diff 7877551..HEAD -- data tools` for vazio. Qualquer mudança posterior nessas áreas invalida a comparação das entidades afetadas;
6. cobre apenas o caminho numérico **sem estado**: `7877551` não tem `Result`, estado, detail, janela nem orquestrador.

**Procedimento obrigatório:**
- referência extraída por `git archive 7877551 app` em diretório temporário, fora do repositório;
- cada versão executada em subprocesso próprio, com os mesmos `data/seed` e as mesmas entradas;
- comparação por chave `(entidade, scope_type, scope_value, period_id)`;
- igualdade exata (`==`; floats bit a bit).

---

## 12. Independent Oracle limitation

- **[fato]** Os workbooks `descritivo_das_variáveis_*` são descritores (fórmulas, parâmetros, metadados) sem saídas calculadas.
- **[fato]** `source_reference` aponta para planilhas operacionais (`Forecast A41!…`, `Yield!…`) que não estão no repositório.

**Evidência combinada da Stage 3** [DR-4]:
1. auditorias estruturais 2.x (workbook ↔ seed ↔ links);
2. oracle Python existente do energy (`tests/test_energy_runtime_contract.py`, 23 equações diárias recalculadas à mão);
3. diferencial `7877551 × HEAD`;
4. testes e auditorias semânticas 3.3A–3.3C;
5. testes integrados da 3.4;
6. testes de mutação.

**Proibido:**
- criar oracle artificial;
- reconstruir saídas históricas inexistentes;
- alterar workbooks para produzir oracle.

---

## 13. Cardinality reconciliation

Todas as quantidades abaixo foram obtidas nesta etapa a partir de `ExecutionCatalog.from_seed_root("data/seed")`, `InterblockExecutionOrchestrator.targets_of_blocks`, `plan()` e `audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv`.

| Unidade | Universo | Quantidade | Definição |
|---|---|---:|---|
| official planning targets | Stage 3.2 (5 blocos carregados) | **446** | variáveis distintas produzidas por algum nó do planner (EQUATION, AGGREGATION ou TRANSFER) de production, yield, energy, max_ht e area_41. Cada uma é um alvo com um plano próprio em `plan_evidence.csv` (446 linhas): 159 OK, 287 `INTERBLOCK_SOURCE_NOT_LOADED` |
| integrated regression targets | Stage 3.4C (4 blocos) | **421** | `targets_of_blocks(["production","yield","energy","max_ht"])`; ver §14 |
| plan steps | plano integrado de 421 alvos (REAL_DERIVED) | **427** | nós de definição executados: 218 EQUATION + 197 AGGREGATION + 12 TRANSFER. Um nó por definição de equação, por regra de agregação ou por vínculo, não por escopo |
| equation definitions | 4 blocos | **218** | registros de `equations.json`: yield 138, production 27, energy 24, max_ht 29 |
| equation instances | 4 blocos | **392** | definição materializada em escopo concreto (`ScopeResolver`): 198, 81, 72, 41 |
| aggregation rules | 4 blocos | **197** | registros de `aggregation_rules.json`: yield 80, production 28, energy 11, max_ht 78 |
| aggregation instances | 4 blocos | **395** | `AggregationRuleInstance` = regra × escopo concreto da variável de origem: 176, 52, 17, 150 |
| aggregation instances | 4 blocos + area_41 | **417** | 395 + 22 (area_41: 10 regras → 22 instâncias) |
| execution cases (histórico) | experimento de discovery, não versionado | **834** | 417 instâncias de agregação × 2 `run_date` (2026-09-03 e 2026-12-31). **Não** é contagem de instâncias. Nos quatro blocos seriam 395 × 2 = 790 |

**Relações:**
- **218 → 392:** uma definição com escopo agregado (ex.: `linha`/`L1_L7`) materializa várias instâncias (7 linhas); definições de escopo único materializam 1.
- **197 → 395:** uma regra semântica gera uma instância por escopo concreto da origem (ex.: regra sobre `linha`/`L1_L7` gera 7 instâncias).
- **Instâncias de agregação por tipo** (4 blocos): AVERAGE 342, SUM 42 (40 simples + 2 com `integration_factor = 24`), WEIGHTED_AVERAGE 9, MOVING_AVERAGE 2 (total 395).
- **Regras por frequência de destino** (4 blocos): mensal 147 (yield 80, max_ht 39, production 18, energy 10), anual 48 (max_ht 39, production 9), diária 2 (as 2 MOVING_AVERAGE).
- Nenhuma regra usa janela explícita.

**Uso obrigatório nas próximas sub-stages:**
- "100% das equações" = **392/392 instâncias** (implica 218/218 definições);
- "100% das agregações" = **395/395 instâncias** (implica 197/197 regras);
- "834" não pode ser usado como sinônimo de instâncias.

---

## 14. 421-target reconciliation

**Derivação** [fato]:

```text
446  official planning targets (5 blocos carregados; plan_evidence.csv)
- 25 targets de area_41 (fora dos quatro blocos oficiais da regressão integrada)
= 421 integrated regression targets (production 50 + yield 219 + energy 43 + max_ht 109)
```

**Exclusões:** apenas uma categoria, **area_41 (25 alvos)**.

**Não são excluídos:**
- os alvos bloqueados oficialmente. Dos 421, 156 são executáveis oficialmente (yield 155, energy 1) e **265 estão bloqueados** por blocos ausentes. Eles entram nos 421 porque a 3.4C executa em REAL_DERIVED (DR-2), onde os 265 são executáveis como fixture;
- nenhuma normalização adicional.

**Composição dos 421 por nó produtor** [fato]:

| produtor | alvos | observação |
|---|---:|---|
| EQUATION | 212 | 218 definições → 212 variáveis distintas: VAR12041 (production `pick_up`) é produzida por 7 definições (uma por linha); as demais, por 1 |
| AGGREGATION | 197 | uma variável destino por regra |
| TRANSFER | 12 | consumidores de vínculo com produtor nos quatro blocos: VAR11031, VAR12062, VAR13062, VAR13092, VAR18001, VAR18005, VAR18006, VAR18007, VAR18008, VAR18009, VAR18010, VAR18011 |
| **total** | **421** | |

**427 passos × 421 alvos:**
- 427 − 421 = **6**, exatamente as 6 definições extras de VAR12041 (7 nós para 1 alvo).
- Não há alvo sem nó nem nó compartilhado entre alvos distintos.
- O plano integrado de 421 alvos tem **0 pendências** em REAL_DERIVED e 12 TRANSFER: dos 13 vínculos carregados, o `yield.VAR11031 → area_41.VAR16007` pertence a area_41 e fica fora.

**Final count:** **421**.

---

## 15. Temporal Protocol

**Motivo** [fato]: as agregações mensais e anuais usam janela progressiva (1º do mês ou 1º de janeiro até `run_date`) e exigem o resultado diário de **todos** os dias da janela.
- Executar o plano integrado com um único `run_date` no meio do ano falha por construção: `VariableNotFoundError` para VAR13003 em 2026-01-01, verificado na 3.4A.
- Não é defeito do engine.
- Um `run_date` isolado no meio do ano não pode ser tratado como se o histórico existisse.

| item | contrato |
|---|---|
| **start_date** | `2026-01-01` (formato ISO `YYYY-MM-DD`, o `period_id` diário do projeto) |
| **progressão** | um `run_date` por dia, contíguo, no **mesmo** `CalculationContext`, pelo `InterblockExecutionOrchestrator.execute` existente (granularidade diária). Nenhum mecanismo temporal novo |
| **virada de mês** | término mínimo **`2026-02-01`** (32 execuções): 2026-01-31 fecha a janela de janeiro completa e 2026-02-01 abre a de fevereiro. Cobre fechamento, continuidade e nova janela |
| **2ª virada (opcional)** | se um teste exigir a transição fevereiro→março, a sequência se estende até `2026-03-01`; a sub-stage que o fizer deve declarar isso como requisito adicional |
| **janelas anuais** | 48 regras anuais (max_ht 39, production 9) dependem do histórico acumulado desde 1º de janeiro. Na sequência até 2026-02-01 elas são exercitadas como **janelas parciais year-to-date de até 32 dias**; o ano completo **não** é exercitado e não pode ser declarado coberto |
| **janelas mensais** | 147 regras mensais: janela completa de janeiro (até 31) e janela parcial de fevereiro (dia 1) |
| **reexecução** | (1) execução original; (2) mesma data de novo; (3) comparação do contexto completo; (4) nenhuma chave nova e nenhuma duplicação; (5) transferências `UNCHANGED`; (6) janelas anteriores intactas |
| **determinismo** | mesma entrada e mesmo histórico, com ≥ 2 `PYTHONHASHSEED`, ≥ 2 ordens de blocos e ≥ 2 ordens de links. Saída comparada byte a byte sobre o contexto serializado com a identidade completa (`entity_id`, `scope_type`, `scope_value`, `period_id`, `window_end`, value, state, detail) |

**Verificação de viabilidade** [fato, nesta etapa, em memória]:
- a sequência 2026-01-01 → 2026-02-01 do plano de 421 alvos executa sem erro (≈ 6,6 s; 33 740 resultados);
- janelas de 2026-01, 2026-02 e 2026 coexistem;
- a reexecução do último dia dá 60/60 transferências `UNCHANGED`.

---

## 16. State Coverage Contract

Os contratos fundamentais já estão fechados e **não** serão reimplementados: `Result`, Policy B, composição de estados e details, `CalculationKey`, identidade temporal, propagação causal de IF.

**Origem de estados** [fato]:
- nenhum estado nasce nos quatro blocos: não há literal, `declared_result_states` nem `allowed_values`;
- estados nascem só em area_41, que não alimenta os quatro blocos;
- todo estado nos quatro blocos é **estado injetado** em entradas do fixture e deve ser rotulado assim.

| Caso | Situação atual | Contrato 3.4 |
|---|---|---|
| EQ18003 — ramo inativo com estado | não coberto | **testar** (3.4C; §16.1) |
| estado → production → yield | parcial (3.3B, REAL_DERIVED, VAR12066) | **testar** |
| estado → production → energy | parcial (3.3B S8 oficial com entrada; 3.3C VAR18010) | **testar** com produtor calculado |
| estado → production → max_ht | parcial (só auditoria 3.3B S3) | **testar** |
| estado + AVERAGE | coberto (3.3C real VAR18010; 3.3B S7 VAR12002) | **testar** na integração |
| estado + SUM (inclui ×24) | só sintético (3.3C) | **testar** em regra real |
| estado + WEIGHTED_AVERAGE | só sintético | **testar** em regra real |
| estado + MOVING_AVERAGE | só sintético | **testar** em regra real |
| janela mensal | coberto (VAR18010) | **testar** na integração |
| janela anual | não coberto com agregação real | **testar** como YTD parcial (§15) |
| reexecução | coberto (VAR18010) | **testar** na integração |

Nenhum contrato novo é criado.

---

### 16.1 EQ18003 contract

`EQ18003` (energy): `VAR18017 = (VAR18015 + PARAM18002) if VAR18012 > PARAM18001 else (VAR18016 + PARAM18002)`.

**Verificação** [fato, nesta etapa, em memória]:

| item | resultado |
|---|---|
| entradas | VAR18012 (`temperatura_lp`, diário, **vínculo pendente de temperature_lp**), VAR18015 e VAR18016 (`entrada_externa`, mensal, sem vínculo) |
| bloqueio oficial | temperature_lp (não maintenance). Planejamento oficial → `INTERBLOCK_SOURCE_NOT_LOADED` |
| em REAL_DERIVED | plano `EQUATION:EQ18003`; entradas VAR18012, VAR18015, VAR18016 livres. Não viola DR-1 (fixture, §10) |
| condição alta + estado em VAR18016 (ramo inativo) | `Result(1.01)`, sem estado |
| condição alta + estado em VAR18015 (ramo ativo) | `Result(None, INVALID_INPUT, "inj")` |
| condição baixa + estado em VAR18015 (inativo) | `Result(1.02)`, sem estado |

**Exigido na 3.4C:**
1. estado injetado no ramo inativo não propaga;
2. estado injetado no ramo ativo propaga com o detail;
3. os dois sentidos da condição;
4. rótulo REAL_DERIVED.

**Implementável:** sim.

---

## 17. Stage 3.4B contract — Differential Regression

**Objetivo:** demonstrar 0 diferenças numéricas entre `7877551` e o HEAD da 3.4B no caminho sem estado.

| item | exigência |
|---|---|
| equações | **392/392 instâncias** (218/218 definições), via `ForecastEngine.calculate_from_definition_registry` por bloco |
| agregações | **395/395 instâncias** (197/197 regras), via `TemporalAggregationService.aggregate` |
| entradas | **≥ 3 vetores distintos** e determinísticos, idênticos nas duas versões |
| datas | **≥ 2 `run_date`**; pelo menos uma com janela mensal parcial e uma em fim de ano |
| casos mínimos | equações: 392 × 3 × 2 = 2352 avaliações de instância; agregações: 395 × 3 × 2 = 2370 |
| comparação | §11 (subprocesso por versão, igualdade exata por chave) |
| pré-condição | `git diff 7877551..HEAD -- data tools` vazio, verificado pela própria auditoria |
| saída | auditoria versionada em `audit/stage3_4/` com evidência por unidade; 0 diferenças; determinismo entre hash seeds |
| rotulagem | `DIFFERENTIAL_REGRESSION_ORACLE`, nunca "independente" |

---

## 18. Stage 3.4C contract — Integrated Regression

**Objetivo:** regressão integrada dos 421 alvos em REAL_DERIVED.

1. Plano integrado de `targets_of_blocks(["production","yield","energy","max_ht"])`: 421 alvos, 427 nós, 0 pendências.
2. Fixture REAL_DERIVED, com rotulagem obrigatória (§10).
3. Sequência diária de 2026-01-01 a 2026-02-01 no mesmo contexto (§15).
4. Oráculo de consistência: o resultado do orquestrador é igual ao do engine por bloco com as mesmas entradas, na projeção `(entidade, escopo, period_id)` por janela.
5. Interbloco: os 12 TRANSFER — consumidor igual ao produtor na mesma identidade (período e janela).
6. Estados: os casos do §16 e o EQ18003 (§16.1).
7. Agregações: pelo menos uma regra **real** de cada tipo (AVERAGE, SUM, SUM×24, WEIGHTED_AVERAGE, MOVING_AVERAGE) com estado injetado, conforme a Policy B.
8. Janelas mensais (janeiro completo, fevereiro parcial) e anuais (YTD parcial).
9. Reexecução (§15).
10. Determinismo (§15).
11. Planejamento oficial preservado: os 446 planos iguais a `plan_evidence.csv` (recusas incluídas).

---

## 19. Stage 3.4D contract — Mutation & Audit

**Auditoria black-box independente:**
- sem importar `app/`;
- oráculo escrito do contrato;
- cobre 3.4B e 3.4C.

**Mutantes mínimos, cada um detectado pelos testes e pela auditoria:**
- aritmética de cada agregador real: AVERAGE, SUM, `integration_factor`, WEIGHTED (peso), MOVING (janela);
- `window_end` e janela efetiva;
- leitura interbloco (produtor errado ou instância errada);
- propagação de estado (descarte ou escolha de estado);
- seleção de ramo IF (propagação estrutural);
- ordenação e determinismo;
- composição de state/detail.

**Meta:** 0 mutantes sobreviventes, com a contagem registrada (introduzidos, detectados, sobreviventes).

---

## 20. Stage 3.4E contract — Stage 3 Closure

- consolidar auditorias, mutações e regressões da 3.4B–3.4D;
- registrar as limitações do §23;
- verificar os artefatos protegidos (§22) contra `7877551` e `f3b6588`;
- consolidar o status formal da Stage 3.2 à luz de DR-1: D32-01 `CLOSED_FOR_STAGE_3_SCOPE`, D32-02 resolvida na 3.3B;
- produzir o gate final da Stage 3.

---

## 21. Acceptance Criteria

### 3.4A Closure (esta etapa)

| critério | resultado |
|---|---|
| DR-1..DR-5 incorporadas | sim (§5–§9) |
| D32-01 fechado para o escopo da Stage 3, sem implementação artificial, `PENDING_LOAD` preservado | sim (§4) |
| REAL_DERIVED = `TEST_FIXTURE_ONLY`, não operacional | sim (§10) |
| `7877551` registrado; `DIFFERENTIAL_REGRESSION_ORACLE`; limitações | sim (§11) |
| ausência de oracle independente documentada, nada fabricado | sim (§12) |
| 446, 421, 427, 417, 395, 197, 392, 218 reconciliados; 834 explicado | sim (§13–§14) |
| protocolo temporal (início, progressão, virada, anuais, reexecução, determinismo) | sim (§15) |
| contratos 3.4B–3.4E | sim (§17–§20) |
| suíte verde; artefatos protegidos intactos; nenhuma alteração de produção | verificado antes do commit (1820 passed; `git diff -- app data tools tests` vazio) |

### 3.4B–3.4E (mensuráveis)

1. Suíte completa com 0 falhas; contagem antes e depois registrada.
2. 3.4B: 0 diferenças em 392/392 instâncias de equação e 395/395 de agregação; ≥ 3 vetores × ≥ 2 datas; pré-condição de invariância verificada.
3. 3.4C:
   - 421 alvos e 427 nós executados de 2026-01-01 a 2026-02-01;
   - orquestrador igual ao engine por bloco;
   - 12 transfers conferidos;
   - casos do §16 e §16.1;
   - ≥ 1 regra real de cada tipo com estado;
   - reexecução com 0 mudanças;
   - determinismo byte a byte com ≥ 2 hash seeds e ≥ 2 ordens.
4. 3.4D: auditoria PASS; 0 mutantes sobreviventes.
5. 3.4E: artefatos protegidos inalterados; limitações registradas; gate final.

---

## 22. Protected Artifacts

Não podem ser alterados em nenhuma sub-stage da 3.4 sem nova decisão:

- `data/workbooks/**`, `data/seed/**` (inclui `interblock_links.json` e manifests), `data/id_ledger/**`;
- `tools/**` (inclui a taxonomia em `tools/workbook_seed/taxonomy.py`);
- fórmulas, unidades, `fonte` e `source_block`;
- `app/**`: engine, planner/orchestrator, agregadores, contrato de estado, Policy B, `CalculationKey`;
- testes e auditorias existentes. A 3.4 **adiciona** testes e auditorias próprios e não altera os existentes.

> **Historical note (D-TAX-01, posterior ao fechamento da Stage 3):** a "nova decisão" prevista acima foi tomada
> uma vez: a canonicalização da taxonomia para 29 blocos e o rename `monthly_ppt_assumptions` → `thickener_flocculant`
> alteraram `tools/workbook_seed/{taxonomy,interblock}.py`, `data/seed/interblock_links.json` (só a seção `taxonomy`)
> e as faixas de ID em `app/validation/` (só o nome). A exceção é provada arquivo a arquivo por
> `audit/stage3_4/taxonomy_migration/taxonomy_guard.py`; qualquer outra alteração continua proibida. Ver
> `audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md`.

---

## 23. Known Limitations

1. Sem execução oficial das cadeias com production calculado (DR-1); 287 dos 446 alvos são oficialmente bloqueados.
2. Resultados de REAL_DERIVED são de teste, com entradas de fronteira arbitrárias (DR-2).
3. O diferencial detecta regressão, não prova correção, e cobre só o caminho sem estado (DR-3).
4. Não há oracle numérico independente; o oracle Python cobre só as 23 equações diárias do energy (DR-4).
5. Os quatro blocos não têm fonte nativa de estado; a cobertura de estado é por injeção.
6. Janelas anuais só como YTD parcial (até 32 dias) na sequência padrão.

---

## 24. Historical Inconsistencies — INCONSISTENCIES_FOUND

| # | inconsistência | tipo | situação |
|---|---|---|---|
| 1 | Gate formal da Stage 3.2 = `READY_FOR_DECISION` (por D32-01) antes desta decisão | histórica/documental | D32-01 agora `CLOSED_FOR_STAGE_3_SCOPE`; consolidação formal na 3.4E; relatório da 3.2 não reescrito |
| 2 | Tabelas da 3.3B-closure e da 3.3C usam "3.2 PASS" para o sucesso da auditoria (exit 0), não do gate formal | documental | registrada; documentos não alterados |
| 3 | `REPORT_stage3_3B.md` (1ª rodada) descreve D32-02 como aberta/conflito e termina em `READY_FOR_DECISION`; superado por `REPORT_stage3_3B_closure.md` | documental | registrada; documento histórico não anotado |
| 4 | Uso de "834 instâncias de agregação" (discovery, fora do repositório) | documental | corrigido: 834 = casos de execução (417 × 2 datas) |
| 5 | Experimento diferencial anterior usou 1 vetor de entradas por data | documental (evidência insuficiente) | a 3.4B exige ≥ 3 vetores |
| 6 | Execução integrada com `run_date` isolado no meio do ano é inviável por construção | documental (critério anterior mal formulado) | protocolo temporal §15 |
| 7 | EQ18003 bloqueada oficialmente por **temperature_lp**, não por maintenance | documental | §16.1 |
| 8 | Docstring de `tests/test_max_ht_runtime_contract.py` cita `tests/test_max_ht_seed_reconciliation.py`, apagado em `6b135e9` | documental (comentário desatualizado) | registrada; teste não alterado |
| 9 | Diretórios `docs/` e `src/` citados em pedidos anteriores não existem (código em `app/`, decisões em `audit/`) | documental | ainda verdadeiro |

Nenhuma é **defeito de implementação atual**: todas são documentais ou de formulação. Nenhum documento histórico fora deste artefato foi alterado.

---

## 25. Final Gate

Todos os critérios do §21 (3.4A Closure) estão satisfeitos. Não há inconsistência objetiva que impeça a formalização do contrato aprovado.

```text
STAGE_3.4A_GATE: PASS
```
