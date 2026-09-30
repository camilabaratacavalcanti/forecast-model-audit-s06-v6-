# Stage 3.4B — Differential Regression

Execução do contrato diferencial da Stage 3.4A (`STAGE_3_4A_DECISION_CONTRACT.md` §11, §13 e §17).

- **Reproduzir:** `python audit/stage3_4/differential/run_differential.py`
- **Testes:** `tests/test_stage3_4b_differential.py`

---

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD inicial / origin | `95e7ade` / `95e7ade` (Stage 3.4A Closure) |
| árvore inicial | limpa |
| suíte inicial | 1820 passed |
| REFERENCE | `7877551fd9f63a2d137ac6da7507afe6cbffd297` |
| CANDIDATE | `95e7adeffe43ff5b098289ae59a360c1009d9ff9` (o commit desta etapa só adiciona `audit/stage3_4/` e `tests/`; `app/` é idêntico) |

## 2. Invariância de dados e ferramentas

```text
git diff 7877551..HEAD -- data tools   -> vazio (0 bytes)
git diff 7877551..HEAD -- data/        -> vazio
git diff 7877551..HEAD -- tools/       -> vazio
REFERENCE_DATA_TOOLS_INVARIANT = PASS
```

A pré-condição é verificada pelo próprio `run_differential.py` a cada execução, que também exige `app/` do working tree igual a HEAD. Foi verificada de novo após a execução.

## 3. Oracle

```text
oracle_type = DIFFERENTIAL_REGRESSION_ORACLE
reference   = 7877551
```

- **Demonstra:** para os mesmos inputs, o candidate produz resultados iguais aos do reference.
- **Não demonstra:** que ambos estão corretos. Não é `INDEPENDENT_NUMERIC_ORACLE`, `GROUND_TRUTH` nem `ABSOLUTE_CORRECTNESS_ORACLE`.

**Limitações (preservadas da 3.4A):**
1. reference e candidate podem compartilhar defeitos;
2. compartilham parser e aritmética;
3. não há saídas operacionais independentes;
4. a validade depende da invariância de `data/` e `tools/`;
5. a cobertura é o caminho comum às duas versões: engine por bloco e serviço de agregação, sem orquestrador e sem vínculos;
6. estados, details, janelas (`window_end`) e orquestração introduzidos pela Stage 3 não fazem parte do diferencial. Ficam para a 3.4C e a 3.4D.

## 4. Isolamento

| requisito | como |
|---|---|
| sem checkout no working tree | `git archive <commit> app` extrai cada versão para um diretório temporário (`tempfile.TemporaryDirectory`, apagado ao fim) |
| cada processo só com seu `app/` | `runner.py` roda em `python -I` (ignora `PYTHONPATH`, site do usuário e diretório corrente), com `cwd` no diretório extraído e o `app/` extraído como `sys.path[0]` |
| prova | o runner lista o `__file__` de cada módulo `app.*` carregado: **0 módulos fora** do próprio diretório em cada lado; fingerprints de código diferentes (reference `a3cc3c50d152…`, candidate `7c67071932f9…`) |
| mesmos dados | os dois lados leem o mesmo `data/seed` do repositório (invariante, §2) |
| mesmas entradas | o mesmo `runner.py` gera as entradas de forma determinística nos dois lados |
| ambiente | Python 3.11.15 nos dois lados |

Nenhum arquivo de `app/`, `data/`, `tools/` ou dos testes existentes foi alterado para executar o reference.

## 5. Input matrix

**Datas:**
- `run_date_1 = 2026-09-03`: meio de mês e ano parcial. Janela mensal de 3 dias e anual de 246 dias.
- `run_date_2 = 2026-12-31`: fim de mês e de ano. Janela mensal completa e anual de 365 dias.

**Vetores de entrada das equações:**
- Variáveis externas de cada bloco, em ordem alfabética (índice `i`), por escopo concreto (índice `k`), com `doy` = dia do ano do `run_date`. São gravadas no período da frequência da variável; os parâmetros vêm dos seeds.
  - `VECTOR_A` (nominal): `1.5 + 0.013·i + 0.0007·k + 0.0001·doy`
  - `VECTOR_B`: `10.0 + 0.37·((7i + 3k) mod 23) + 0.01·(doy mod 7)`
  - `VECTOR_C`: `50.0 + 5.0·((11i + k) mod 17) + (doy mod 3)`
- **EQ18003 (IF):** VAR18012 fica abaixo de 72 em A e B (ramo `else`) e entre 75 e 105 em C (ramo `then`). Os dois ramos são exercitados.

**Vetores de entrada das agregações:**
- Série diária da origem (e do peso) de 1º de janeiro até o `run_date`, no escopo da instância; `d` = dia da janela, `n` = ordinal da instância.
  - `VECTOR_A`: origem `2.0 + 0.01·((7d + n) mod 97)`; peso `+0.5`
  - `VECTOR_B`: origem `100.0 + 0.25·((13d + 3n) mod 101)`; peso `1.0 + ((d + n) mod 5)`
  - `VECTOR_C`: origem `0.5 + ((d² + n) mod 53)/7`; peso `0.1 + ((3d + n) mod 11)/4`

**Os vetores e as datas são efetivos:**
- 783/787 instâncias mudam de valor entre vetores;
- 389/392 instâncias de equação e 395/395 de agregação mudam entre datas;
- as únicas constantes nos seis casos são EQ11055, EQ11056 e EQ11057 (yield), cujas expressões só usam `PARAM11001`. Isso é legítimo e não configura exceção: elas foram executadas e comparadas.

## 6. Identidade do caso

```text
ExecutionCaseKey = (block, operation_type, instance_id, input_vector_id, run_date)
operation_type ∈ {EQUATION, AGGREGATION}
```

- `instance_id` = `equation_instance_id` (ex.: `EQ18003@v1@L1`) ou `aggregation_rule_instance_id`.
- Faltantes, duplicados e excedentes são detectados por lado, contra o universo esperado. O universo vem da enumeração das duas versões e é conferido com as cardinalidades do contrato 3.4A.

## 7. Cobertura

| Tipo | Instances | Vectors | Dates | Expected Cases | Actual Cases | Matched |
|---|---:|---:|---:|---:|---:|---:|
| EQUATION | 392 | 3 | 2 | 2352 | 2352 | 2352 |
| AGGREGATION | 395 | 3 | 2 | 2370 | 2370 | 2370 |
| **TOTAL** | **787** | 3 | 2 | **4722** | **4722** | **4722** |

**Definições:** 218 definições de equação (todas as instâncias de cada uma avaliadas) e 197 regras de agregação.

**Por bloco (area_41 fora do universo obrigatório, conforme 3.4A):**

| bloco | inst. equação | casos eq. | inst. agregação | casos agr. | total de casos | matched |
|---|---:|---:|---:|---:|---:|---:|
| yield | 198 | 1188 | 176 | 1056 | 2244 | 2244 |
| production | 81 | 486 | 52 | 312 | 798 | 798 |
| energy | 72 | 432 | 17 | 102 | 534 | 534 |
| max_ht | 41 | 246 | 150 | 900 | 1146 | 1146 |

**Por tipo de agregação:**

| tipo | instâncias | casos | matched |
|---|---:|---:|---:|
| AVERAGE | 342 | 2052 | 2052 |
| SUM | 42 (2 com `integration_factor = 24`) | 252 | 252 |
| WEIGHTED_AVERAGE | 9 | 54 | 54 |
| MOVING_AVERAGE | 2 | 12 | 12 |

Cardinalidades idênticas às do contrato 3.4A (§13): sem discrepância.

**Lados:** reference e candidate têm 4722 casos cada, 0 duplicados, 0 faltantes, 0 excedentes.

## 8. Comparação

**Modo:** igualdade exata da representação `(tipo, repr)`.
- `repr` de float é round-trip exato.
- Sem tolerância, arredondamento ou normalização de tipo.
- `1 ≠ 1.0`; `None ≠ 0`; `0.0 ≠ nan`; `-0.0 ≠ 0.0`.

**Componentes comparados:**
- **EQUATION:** valor retornado pelo engine para a instância e valor gravado no contexto no `period_id` do alvo, além de `state` e `detail`.
- **AGGREGATION:** value, identidade do `ForecastValue` (variável, escopo, frequência, `period_id`), `state` e `detail`.
- **Estrutura:** bloco, definição, alvo, escopo, `period_id`, tipo e `integration_factor`.

**State/detail:**
- no reference não existem, e ficam registrados como `NOT_APPLICABLE_TO_REFERENCE`;
- no candidate precisam ser `None`, porque o caminho sem estado não pode produzir estado;
- qualquer outro valor é `STATE_DIFFERENCE` ou `DETAIL_DIFFERENCE`. Não há falso positivo por ausência.

**Resultado:**

| categoria | casos |
|---|---:|
| VALUE_DIFFERENCE | 0 |
| STATE_DIFFERENCE | 0 |
| DETAIL_DIFFERENCE | 0 |
| STRUCTURAL_DIFFERENCE | 0 |
| EXCEPTION_DIFFERENCE | 0 |
| MISSING_REFERENCE_RESULT / MISSING_CANDIDATE_RESULT | 0 |
| **MATCH** | **4722** |

`DIFFERENCES_FOUND`: nenhuma.

**Floating point:** nenhuma normalização foi necessária nem aplicada.

## 9. Exceções

Nenhuma: nenhum caso `EXPECTED_REFERENCE_LIMITATION`, `STRUCTURAL_NOT_COMPARABLE`, `ENVIRONMENT_FAILURE` ou `IMPLEMENTATION_FAILURE`. Nenhum caso foi pulado. Os dois engines executaram os 4722 casos sem exceção.

## 10. Sensibilidade do comparador (teste negativo)

`tests/test_stage3_4b_differential.py`, sem alterar o engine:

| caso | resultado |
|---|---|
| reference = `10`, candidate = `10.0000001` (equação e agregação) | `VALUE_DIFFERENCE` |
| `1` × `1.0`; `None` × `0`; `0.0` × `nan`; `0.1+0.2` × `0.3`; `-0.0` × `0.0` | diferença |
| valor retornado igual, valor gravado diferente | `VALUE_DIFFERENCE` |
| estado ou detail no candidate onde o reference não tem | `STATE_DIFFERENCE` / `DETAIL_DIFFERENCE` |
| identidade diferente; exceção (mesmo nos dois lados) | `STRUCTURAL_DIFFERENCE` / `EXCEPTION_DIFFERENCE` |
| lado ausente | `MISSING_*` |
| duplicados, faltantes e excedentes na cobertura | detectados |

Os casos são construídos em memória; nenhuma fixture persiste.

## 11. Determinismo do harness

- Cada lado rodou duas vezes (`PYTHONHASHSEED` 0 e 4242) com saída byte a byte idêntica. SHA-256 da saída: reference `98f02fdd…`, candidate `5ba9d45b…`.
- A ordem é fixa: blocos, definições e instâncias ordenados por ID; vetores e datas em tuplas.
- Nenhuma dependência de iteração de `dict`/`set`, ordem de filesystem, timestamps ou UUIDs para a identidade dos casos.

## 12. Escopo excluído desta etapa

- **REAL_DERIVED:** não usado (`TEST_FIXTURE_ONLY`, DR-2; pertence à 3.4C).
- **Pendências:** nenhum vínculo pendente reconstruído, nenhuma entrada de bloco ausente fabricada, nenhum bloco carregado.
- **Interbloco:** não usado. Cada bloco roda isolado no engine, com as variáveis externas, inclusive as de vínculo, como entradas. É o caminho comum às duas versões; o `7877551` não tem orquestrador interbloco.
- **Estados:** nenhum injetado.

## 13. Artefatos

| caminho | conteúdo |
|---|---|
| `audit/stage3_4/differential/runner.py` | execução de uma versão (API pública real) |
| `audit/stage3_4/differential/compare.py` | comparador exato e cobertura (sem importar `app`) |
| `audit/stage3_4/differential/run_differential.py` | pré-condições, isolamento, execução, comparação, evidência |
| `audit/stage3_4/differential/evidence/differential_cases.csv` | 4722 casos: chave, definição, escopo, período, resultado de cada lado, comparação |
| `audit/stage3_4/differential/evidence/differential_summary.json` | resumo, fingerprints, determinismo, cobertura |
| `tests/test_stage3_4b_differential.py` | 14 testes do contrato: comparador, cobertura, execução real, evidência × universo atual |

## 14. Integridade

- `app/`, `data/` e `tools/` estão inalterados (`git diff` vazio).
- Workbooks, seeds, `interblock_links.json` e ledgers estão inalterados.
- Nenhum teste existente foi alterado.
- Suíte: 1820 → **1834 passed** (+14), 0 failed, 0 skipped.

## 15. Critérios de aceite

| grupo | resultado |
|---|---|
| baseline (HEAD `95e7ade`, reference `7877551`, data/tools invariantes, suíte verde) | ✔ |
| isolamento (reference e candidate isolados, sem checkout, sem código cruzado) | ✔ |
| equações (392/392 instâncias; 3 vetores × 2 datas; 2352/2352) | ✔ |
| agregações (395/395 instâncias; 3 × 2; 2370/2370; quatro tipos) | ✔ |
| comparação (exata, sem tolerância, estrutura comparada, ausências detectadas) | ✔ |
| sensibilidade (teste negativo 10 × 10.0000001 falha) | ✔ |
| resultado (0 diferenças, 0 inexplicados, 0 duplicados, 0 faltantes) | ✔ |
| integridade (produção, dados, tools, workbooks, seeds, links intactos) | ✔ |

## 16. Gate

STAGE_3.4B_GATE: PASS
