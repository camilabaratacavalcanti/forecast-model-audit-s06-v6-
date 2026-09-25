# Findings — tipagem e resultados heterogêneos

Formato por achado: ID · título · severidade · evidência · componente ·
impacto · causa · risco · recomendação. As evidências (Pxx, NTxx, MTxx, CSVs)
estão em `evidence/probes_results.json` e nos CSVs deste diretório.

### T-01 — `"F"` no canal de valor colide com o domínio categórico · MAJOR

- **Evidência:**
  - P14a e NT13: categoria legítima `"F"` == `"A"` → `ConditionalFailureError`.
  - MT09.
  - `app/domain/values.py:30,37`; `calculation_context.py:485`.
- **Componente:** valores, storage, evaluator.
- **Impacto:** nenhum domínio categórico pode usar o código "F".
- **Causa:** o estado é representado por um valor textual reservado.
- **Risco:** falso positivo de falha em blocos futuros.
- **Recomendação:** estado de resultado em canal próprio (Alternativa D).

### T-02 — F-001: fail-fast global suprime resultados independentes · MAJOR

- **Evidência:**
  - `f001_matrix.csv`: no caso 2, `dep_B` não é calculado; no caso 3, `dep_A`
    é. Assimétrico e idêntico nas 3 ordens.
  - `forecast_engine.py:375-403` (sem tratamento por nó).
  - `dependency_resolver.py:34` (ordem determinística).
- **Componente:** `ForecastEngine` (controle de fluxo).
- **Impacto:** um `"F"` num grupo apaga, no dia, resultados de grupos
  independentes, segundo a posição topológica.
- **Causa:** a propagação do estado é feita por exceção, e a execução não é
  isolada por nó.
- **Risco:** perda silenciosa de resultados válidos. A exceção é levantada,
  mas os resultados colaterais somem.
- **Recomendação:**
  - propagar o estado como dado, só aos descendentes;
  - definir a política para erros técnicos (abortar ou isolar).

### T-03 — Dupla semântica de propagação do estado · MAJOR

- **Evidência:** P11b e `propagation_matrix.csv`. Referência e ramo de IF
  repassam `"F"`; a aritmética levanta exceção.
- **Componente:** evaluator.
- **Impacto:** o resultado de uma cadeia depende da forma sintática da
  expressão, e não da dependência.
- **Causa:** o estado é tratado como valor em uns nós e como erro em outros.
- **Risco:** imprevisibilidade para quem escreve workbooks.
- **Recomendação:** uma única regra, em que qualquer dependência de um valor
  em estado não-VALID resulta no mesmo estado (salvo detecção explícita).

### T-04 — Estado de negócio e erro técnico no mesmo canal · MAJOR

- **Evidência:**
  - NT14: `ConditionalFailureError` e `DivisionByZeroError` são ambos
    `EvaluationError`.
  - `equation_engine.py:126-127` embrulha todos em `EquationEvaluationError`.
- **Componente:** exceções, `EquationEngine`.
- **Impacto:** não é possível distinguir "regra não aplicável" de "defeito de
  cálculo" sem inspecionar a causa.
- **Causa:** não há canal de estado.
- **Risco:** relatórios e observabilidade misturam negócio e defeito.
- **Recomendação:**
  - estado de resultado como dado;
  - exceções reservadas para erros técnicos.

### T-05 — Entrada categórica inválida vira `"F"` · MINOR

- **Evidência:**
  - MT08.
  - `a41_case_study.csv`: 5 dos 7 `"F"` vêm de "Overhaul", que não é um
    estado declarado.
- **Componente:** workbook e contrato de categóricas.
- **Impacto:** erro de entrada fica mascarado como estado de regra.
- **Causa:** as categóricas não declaram o domínio (valores permitidos).
- **Recomendação:** `allowed_values` opcional em variáveis categóricas,
  validado na entrada.

### T-06 — Sem checagem estática de tipo · MINOR

- **Evidência:**
  - P05b e MT03: "ERRO!!!" latente em variável numérica.
  - NT08 e MT02: categórica aceita número.
  - NT12: agregação sobre categórica aceita estaticamente.
- **Componente:** builders e validators.
- **Impacto:** inconsistências só aparecem quando o ramo executa.
- **Causa:** `value_type` só é consumido pelo storage.
- **Recomendação:** validação estática no builder/validator a partir de
  `value_type`.

### T-07 — O gate de `value_type` depende do chamador · MINOR

- **Evidência:**
  - NT11: `ForecastEngine` sem registry rejeita as categóricas.
  - `forecast_engine.py:313`.
- **Componente:** runtime.
- **Recomendação:** as definições carregam `value_type` até o contexto sem
  depender de argumento opcional.

### T-08 — Booleano só intermediário · INFO

- **Evidência:** P03a/b/c.
- **Conclusão:** não há necessidade de `boolean` como `value_type` no
  universo atual.

### T-09 — MIN/MAX inexistentes · INFO

- **Evidência:** `aggregation_matrix.csv` e `ALLOWED_FUNCTIONS`.

### T-10 — Sem persistência, API ou serialização de resultados · INFO

- **Evidência:** `app/domain/forecast/collection.py:82`.
- **Conclusão:** mudar a representação do resultado não tem custo de
  compatibilidade externa hoje.

### T-11 — Ausência é chave ausente · INFO

- **Evidência:** P06a/b e `aggregation_matrix.csv` (série "ausente").
- **Conclusão:** "indisponibilidade" já tem canal próprio
  (`VariableNotFoundError`).

### T-12 — Builders não leem `value_type`; nenhum seed o declara · INFO

- **Evidência:** grep em `tools/` e `data/seed/` (0 ocorrências).

### T-13 — Marcadores de estado futuros ("ERRO!!!") · DEFERRED

- **Evidência:**
  - Não existem em nenhum workbook atual.
  - P05a/c mostram o comportamento que teriam hoje: rejeitado em variável
    numérica e aceito como categoria em categórica.
- **Recomendação:** tratar como estado declarado (ver `conceptual-contract.md`),
  com a semântica confirmada pelo dono do modelo.
