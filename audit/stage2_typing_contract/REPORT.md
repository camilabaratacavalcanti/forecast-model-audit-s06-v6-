# Auditoria conceitual de tipagem e resultados heterogêneos

Auditoria read-only. Evidência primária: código de produção,
`probes_typing_contract.py` (fixtures genéricas `VAR96xxx`), workbooks reais
e testes.

Rótulos: **FATO** (observado), **INFERÊNCIA**, **HIPÓTESE**, **RECOMENDAÇÃO**.
Os IDs dos experimentos (P, NT, MT, e as tabelas de F-001, propagação,
agregação e A41) remetem a `evidence/probes_results.json` e aos CSVs deste
diretório.

## 1. EXECUTIVE SUMMARY

- **FATO:** a plataforma tem hoje um único canal de valor,
  `ScalarValue = int | float | str`.
  - O texto é admitido em dois papéis muito diferentes: categoria de domínio
    (quando a variável é `categorical`) e o sentinela `"F"` (em qualquer
    variável).
  - Booleanos e `None` não são valores armazenáveis.
  - Erros técnicos e o estado `"F"` consumido viajam pelo mesmo canal: a
    família de exceções `EvaluationError`.
- **FATO:** `value_type` (`numeric` | `categorical`) só altera um
  comportamento, o gate de armazenamento em `CalculationContext`.
  - O parser, o evaluator, a agregação e os builders não o leem; decidem pelo
    tipo do valor em runtime.
- **INFERÊNCIA:** `"F"` não é um tipo de valor; é um **estado de resultado**
  ("nenhuma regra condicional produziu valor") codificado como texto no canal
  de valor. Isso produz quatro defeitos demonstrados:
  - colisão com categorias legítimas (P14a);
  - dupla semântica de propagação: valor repassado por referência ou IF, e
    exceção em aritmética (P11b);
  - mistura com erros técnicos (NT14);
  - confusão com entrada inválida (MT08: 5 dos 7 `"F"` do A41 vêm de um
    estado digitado errado).
- **FATO:** F-001 foi reproduzido com fixture genérica. Com `"F"` no grupo A,
  o dependente de B (que não depende de A) não é calculado; com `"F"` em B, o
  dependente de A é. É um efeito de ordem topológica e de controle de fluxo
  por exceção (`forecast_engine.py:375-403`), **não de tipagem**.
- **Decisões:**
  - `value_type`: **manter, redefinido** (apenas o domínio do valor normal).
  - `mixed`: **não necessário**.
  - `"F"`: combinação inadequada de conceitos; deve virar **estado de
    resultado**.
  - `result_state`: **necessário**.
  - F-001: **controle de fluxo/propagação**.
- **Gate:** **READY_WITH_CONDITIONS**.

## 2. PRE-FLIGHT

| item | valor |
|---|---|
| repositório | `camilabaratacavalcanti/forecast-model-audit-s06-v6-` |
| BRANCH | `claude/funny-noether-nbcr7b` (sincronizado com `origin`) |
| BASELINE_COMMIT | `978c2d0f2d070735d11d2098f11c1cf05bc3eb26`; merge-base com `main` = `202d4cb` |
| WORKTREE_STATUS | limpo: 0 modificados, 0 staged, 0 untracked |
| TEST_COMMAND | `python3 -m pytest -q` (Python 3.11.15) |
| TEST_RESULT / COUNT / FAILURES | 1414 passed / 1414 / 0 (≈7 s) |
| modo | read-only; artefatos só em `audit/stage2_typing_contract/` |

## 3. CURRENT ARCHITECTURE

| componente | contrato observado (FATO) | evidência |
|---|---|---|
| tipos | `NumericValue = int\|float`, `CategoricalValue = str`, `ScalarValue = NumericValue\|CategoricalValue`, sentinela `CONDITIONAL_FAILURE = "F"` | `app/domain/values.py:21-38` |
| parser | Constantes permitidas: números e textos, estes só como resultado, ramo de IF ou operando de comparação. Rejeita `True`/`False`/`None`. Funções: só `ln`. Sem SUM/AVERAGE/MIN/MAX na DSL. | `expression_parser.py` (`_validate_constants`, `ALLOWED_FUNCTIONS`); P03c, P06a, MT07 |
| evaluator | Opera pelo tipo em runtime. Aritmética só com números; `"F"` → `ConditionalFailureError`; texto → `ExpressionTypeError`; resultado final bool → erro. **Não lê `value_type`.** | `expression_evaluator.py:402-500`; P07/P08/P03a |
| storage | Aceita número; texto só se a variável foi declarada categórica; `"F"` em qualquer variável; rejeita bool e `None`. Parâmetros só numéricos. | `calculation_context.py:467-500`; matriz de compatibilidade |
| engine | Declara as categóricas a partir de `VariableDefinition.is_categorical` (só se receber o registry). Loop sem tratamento por nó: a primeira exceção aborta a rodada. | `forecast_engine.py:313-317, 375-403`; NT11; F-001 |
| erros | `ConditionalFailureError`, `DivisionByZeroError`, `ExpressionTypeError` e `MathDomainError` são todos `EvaluationError`, e todos embrulhados em `EquationEvaluationError` | `exceptions.py:43-104`; `equation_engine.py:126-127` |
| agregação | AVERAGE, SUM, WEIGHTED_AVERAGE, MOVING_AVERAGE. `"F"` → `AggregationFailureError` (com períodos); texto → `NonNumericAggregationError`; dia ausente → `VariableNotFoundError`; nunca parcial; MIN/MAX inexistentes | `temporal_aggregation_service.py:262-300`; `aggregation_matrix.csv` |
| persistência/API/serialização de resultados | **não existem**; `ForecastValue`/`ForecastValueRegistry` só em memória | `app/domain/forecast/collection.py:82` |

## 4. CURRENT `value_type` CONTRACT

| Componente | Lê? | Escreve? | Valida? | Altera comportamento? | Evidência |
|---|---|---|---|---|---|
| Parser | não | não | não | não | grep: 0 ocorrências |
| Builder (energy, max_ht) | não | não | não | não | `tools/*`: 0 ocorrências |
| Loader (`SeedLoader`) | repassa (`Variable(**data)`) | não | indireto | não | `seed_loader.py:142,332` |
| Validator de seed | sim (enum opcional) | não | sim | rejeita valor fora do enum | `variable_seed_validator.py:217` |
| Modelo (`VariableDefinition`) | sim | padrão `numeric` | sim (`__post_init__`) | `mixed`/`string`/`boolean` → `ValueError` | `variables/models.py:67,86`; NT09/NT10 |
| Evaluator | não | não | não | não (decide pelo tipo em runtime) | `expression_evaluator.py` |
| Runtime (`ForecastEngine`) | sim (`is_categorical`) | não | não | declara as categóricas no contexto | `forecast_engine.py:317` |
| Storage (`CalculationContext`) | sim (conjunto de categóricas) | não | sim | **único gate**: texto só em categórica | `calculation_context.py:489` |
| Aggregator | não | não | não | não (checa o tipo em runtime) | `temporal_aggregation_service.py` |
| API / UI / persistência | inexistentes | — | — | — | — |
| Tests | sim | sim | sim | — | `tests/test_dsl_structural_contracts.py` (12 testes de tipo) |

**Valores:**

- **Aceitos:** `numeric` e `categorical`.
- **Rejeitados em `VariableDefinition.__post_init__`:** `string`, `boolean` e `mixed`.
- **Aliases, normalização e valores implícitos:** não há aliases nem normalização; o valor implícito é `numeric`.
- **Uso nos workbooks e seeds:** só o A41 v6 validado declara (`categorical` em `hes_l4..l7`); nenhum seed declara.

**Limites observados:**

- Uma variável `categorical` aceita número (NT08, MT02).
- Não há checagem estática dos ramos de IF contra `value_type` (P05b, MT03).
- Não há checagem estática de uma agregação sobre variável categórica (NT12).
- A aplicação do gate depende de o chamador passar o registry (NT11).

## 5. VALUE VS STATE VS ERROR

| conceito | representação atual (FATO) | separado? |
|---|---|---|
| natureza do valor | `value_type` na definição + tipo Python em runtime | parcialmente: o evaluator e a agregação ignoram a declaração |
| estado do resultado | `"F"` (texto no canal de valor) | **misturado** com valor |
| erro de execução | exceções `EvaluationError` | **misturado** com o consumo de estado (`ConditionalFailureError` na mesma família) |
| indisponibilidade | ausência de chave → `VariableNotFoundError` | separado (canal próprio) |
| condição operacional | categorias (`Normal`, `LC`…) em variáveis `categorical` | separada, mas **sem declaração do domínio**; entrada inválida vira `"F"` (MT08) |

**INFERÊNCIA:** os conceitos estão **parcialmente misturados**. A
indisponibilidade e a condição operacional já têm canal próprio. O estado de
resultado não tem canal próprio e usa o canal de valor. O consumo de estado e
o erro técnico compartilham o canal de exceção.

## 6. `"F"` ANALYSIS

**Onde `"F"` aparece:**

| aspecto | observado (FATO) |
|---|---|
| criação | Só por literal no ramo `else` de IFs de workbook: A41 (2 equações). Nenhum outro bloco usa texto em expressões computacionais (varredura dos 5 workbooks). |
| comparação | `x == "F"` / `!= "F"` contra o literal é a única leitura permitida; comparar `"F"` com qualquer outra coisa → `ConditionalFailureError` |
| armazenamento | aceito em qualquer variável, ignorando `value_type` (P04) |
| propagação | referência e ramo de IF **repassam como valor**; aritmética, `ln`, ordenação, condição e and/or **viram exceção** (matriz de propagação, P11b) |
| conversão | nunca é convertido para 0, `None` ou `False` (NT01) |
| agregação | `AggregationFailureError` com os períodos afetados (P09) |
| descarte | nunca; a rodada inteira aborta (F-001) |

**Em que condições `"F"` é produzido no A41:** o texto real de M39 foi avaliado
em 49 combinações de estados (`a41_case_study.csv`):

- 30 dão número;
- 7 dão `"F"`: 2 são combinações válidas não cobertas
  (Normal/"1 By pass e LC") e **5 são estados inválidos** ("Overhaul");
- 12 dão `VariableNotFoundError` (entrada ausente).

**Hipóteses e classificação:**

| hipótese | resultado |
|---|---|
| valor | refutada (o storage trata `"F"` como exceção ao `value_type`; a agregação trata como falha) |
| categoria | refutada (colide com categorias; P14a) |
| erro técnico | refutada (a fórmula executou corretamente) |
| condição operacional | refutada (não descreve operação; descreve a ausência de regra aplicável) |
| sentinela | confirmada como **representação** |
| estado de resultado | confirmada como **semântica** |

**Classificação:** "F" é uma **combinação inadequada de conceitos**: um estado
de resultado representado por um sentinela no canal de valor.

## 7. F-001 ANALYSIS

Reprodução genérica (`f001_matrix.csv`; 4 casos × 3 ordens de registro):

- dois grupos, A e B;
- `dep_A` depende só de A; `dep_B` depende só de B;
- `agregador = A + B`.

| caso | A | B | dep_A | dep_B | agregador | erro |
|---|---|---|---|---|---|---|
| 1 num/num | 1.0 | 2.0 | 2.0 | 4.0 | 3.0 | — |
| 2 F/num | F | 2.0 | — | **— (colateral)** | — | ConditionalFailureError |
| 3 num/F | 1.0 | F | 2.0 | — | — | ConditionalFailureError |
| 4 F/F | F | F | — | — | — | ConditionalFailureError |

O resultado é idêntico nas 3 ordens de registro: o resolvedor ordena
(`dependency_resolver.py:34`).

- **FATO:**
  - a falha ocorre na **avaliação** do primeiro consumidor de `"F"` (não na
    agregação nem na persistência);
  - ela é **global** para a rodada do dia (`forecast_engine.py:375-403` não
    trata exceção por nó);
  - quais resultados independentes sobrevivem depende da **posição
    topológica** (casos 2 × 3 são assimétricos).
- **Classificação:**
  - é consequência de uma decisão arquitetural (fail-fast por exceção);
  - é um **problema de controle de fluxo e propagação**, não de tipagem;
  - quanto ao isolamento entre grupos, o comportamento é **incorreto**: o
    resultado depende da ordem e não da semântica;
  - não está documentado como contrato (só apareceu como risco em relatórios).

## 8. EXPERIMENTAL PROBES

Comando: `python3 audit/stage2_typing_contract/probes_typing_contract.py`.
Ambiente: commit `978c2d0`, Python 3.11.15. Saída em
`evidence/probes_run.txt`.

| probe | entrada | esperado | observado | interpretação |
|---|---|---|---|---|
| P01 | numeric → numeric | 10 | 10.0 | nominal |
| P02 | categorical → categorical | "ALTO" | "ALTO" | texto de domínio legítimo |
| P03a/b/c | bool como resultado / entrada / literal | rejeitado | ExpressionTypeError / CalculationValueError / UnsafeExpressionError | bool só é intermediário |
| P04 | numeric → "F" | armazenado | `"F"` em variável numeric | estado atravessa o gate de tipo |
| P05a | numeric → "ERRO!!!" (ramo executado) | rejeitado | CalculationValueError no storage | detecção só em runtime |
| P05b | idem, ramo não executado | — | 3.0, sem erro | defeito latente, não detectado |
| P05c | categorical → "ERRO!!!" | ? | armazenado como categoria | erro de negócio indistinguível de domínio |
| P06a/b | None na DSL / no storage | rejeitado | UnsafeExpressionError / CalculationValueError | ausência ≠ valor |
| P07 | 2 + 3 | 5 | 5.0 | nominal |
| P08 | 2 + "F" | falha | ConditionalFailureError | consumo de estado = exceção |
| P09a/b | AVERAGE/SUM com "F" | falha | AggregationFailureError(['2026-03-02']) | nunca parcial |
| P10a/b/c | IF num/num, num/str, str/str | — | 1 / "X" / "B" | o tipo do resultado depende do ramo; o evaluator não sabe o tipo declarado |
| P11a | A="F" → B=A·2 → C → D | — | nada calculado; exceção | a aritmética interrompe |
| P11b | A="F" → B=A → C=(B if k>0 else 0) → D=C+1 | — | B="F", C="F", D falha | **dupla semântica de propagação** |
| P12 | F-001 | — | ver §7 | controle de fluxo |
| P13 | categoria "LC" == "LC" | 1 | 1 | nominal |
| P14a | categoria legítima "F" == "A" | 0 | **ConditionalFailureError** | colisão sentinela × domínio |
| P14b | "ERRO!!!" em categorical == "ERRO!!!" | — | 1 | erro tratado como categoria |

## 9. NEGATIVE TESTS (`negative_tests.csv`)

| id | caso | observado | classe |
|---|---|---|---|
| NT01 | "F" convertido implicitamente | ConditionalFailureError | SAFE |
| NT02/03 | string somada / tratada como zero | ExpressionTypeError | SAFE |
| NT04 | bool convertido em número | ExpressionTypeError | SAFE |
| NT05 | número como condição de IF | aceito (legado: ≠ 0) | DEFINED |
| NT06 | None ignorado | CalculationValueError | SAFE |
| NT07 | texto em variável não categórica | CalculationValueError | SAFE |
| NT08 | número em categorical | aceito | AMBIGUOUS |
| NT09/10 | `mixed` / `string` | ValueError | SAFE |
| NT11 | engine sem registry | categóricas rejeitadas | AMBIGUOUS |
| NT12 | regra de agregação sobre categorical | aceita estaticamente | AMBIGUOUS |
| NT13 | categoria "F" | tratada como falha | **UNSAFE** |
| NT14 | estado × erro técnico | mesma família (`EvaluationError`) | AMBIGUOUS |
| F-001 | resultado independente suprimido | depende da ordem topológica | **BUG** (propagação) |

## 10. MUTATION TESTS (`mutation_tests.csv`, padrão A41 em fixture genérica)

| id | corrupção | detectada? | quando |
|---|---|---|---|
| MT01 | estados declarados numeric | sim | runtime, ao gravar a entrada |
| MT02 | resultado numérico declarado categorical | **não** | — |
| MT03 | "F" → "ERRO!!!" (ramo não executado) | **não** | latente |
| MT04 | idem, ramo executado | sim | runtime (storage) |
| MT05 | `mixed` | sim | carga da definição |
| MT06 | resultado booleano | sim | runtime (evaluator) |
| MT07 | "100" em aritmética | sim | estático (parser) |
| MT08 | estado com erro de digitação | **mascarada**: vira `"F"` | runtime, como estado errado |
| MT09 | categoria legítima "F" | detectada como falha | falso positivo |

**INFERÊNCIA:** os contratos atuais pegam quase tudo o que é sintático e
dinâmico. O que escapa, ou é mal classificado, é o que depende de distinguir
tipo, estado e domínio (MT02, MT03, MT08, MT09).

## 11. AGGREGATION SEMANTICS (`aggregation_matrix.csv`)

| série | SUM | AVERAGE | MIN/MAX |
|---|---|---|---|
| numeric+numeric | 4.0 | 2.0 | não suportado (`InvalidAggregationRuleError`) |
| numeric+"F" | AggregationFailureError | AggregationFailureError | não suportado |
| numeric+string / string+string | NonNumericAggregationError | NonNumericAggregationError | não suportado |
| numeric+ausente | VariableNotFoundError | VariableNotFoundError | não suportado |

**FATO:** `"F"` nunca é ignorado, convertido ou tratado como zero, e nunca há
resultado parcial. A agregação já trata `"F"` como **estado que invalida o
período agregado**, reportado com os períodos. É o comportamento mais próximo
de um contrato de estado que existe hoje.

## 12. PROPAGATION SEMANTICS (`propagation_matrix.csv`)

| Operação | Entrada `"F"` | Resultado atual | Esperado pelo contrato atual? |
|---|---|---|---|
| comparação `== 0` / `> 0` | F | ConditionalFailureError | sim |
| comparação `== "F"` | F | 1 (detecção) | sim |
| soma, multiplicação, divisão | F | ConditionalFailureError | sim |
| média (agregação) | F | AggregationFailureError | sim |
| `ln()` | F | ConditionalFailureError | sim |
| IF (condição) | F | ConditionalFailureError | sim |
| IF (ramo devolvido) | F | `"F"` (valor) | sim ("repassar sem alteração") |
| referência | F | `"F"` (valor) | sim |
| and/or | F | ConditionalFailureError | sim |

**INFERÊNCIA:** o contrato atual é internamente coerente, mas define **duas
semânticas de propagação**: o estado se propaga como valor pelo caminho
estrutural e como exceção pelo caminho computacional. Na cadeia A→B→C→D, o
estado vira **ausência** (nada gravado) mais uma exceção que aborta a rodada.

## 13. WORKBOOK EVIDENCE

Varredura de A41 v6 validado, yield v4, production v1, energy v2 e MaxHT v5
(cópias com SHA em `audit/architecture_scope_contract/evidence/workbooks/`):

- **FATO:**
  - Texto em expressões computacionais só no A41: 5 estados, comparados em
    `hes_l4..l7`, e `"F"` em 2 ramos `else`.
  - Energy e production têm 1 IF cada, com ramos numéricos.
  - Nenhum workbook tem `"ERRO!!!"`, `"N/A"`, `""` ou literais booleanos.
- **INFERÊNCIA:**
  - No universo atual, a heterogeneidade de resultado vem de um único padrão:
    IF com ramo `else "F"`.
  - O A41 revela a necessidade de um **canal de estado**, não de um tipo
    `mixed`.

## 14. `MIXED` ANALYSIS

**FATO:** `mixed` é rejeitado hoje (NT09/MT05) e não aparece em nenhum
workbook.

**INFERÊNCIA:** declarar `retirada_condensado_grupo` como `mixed`:

- não resolveria nenhum dos defeitos observados: a colisão P14a, a dupla
  propagação P11b, o F-001 e o MT08 continuariam;
- **eliminaria** a única validação útil de tipo (o gate que rejeita
  "ERRO!!!"/texto em variável numérica, P05a);
- deixaria a agregação sem garantia estática;
- tornaria o tipo de cada resultado dependente do ramo executado.

`mixed` mascara a falta de um canal de estado. **Decisão: não necessário.**

## 15. ALTERNATIVES

- **A — `value_type` obrigatório (domínio do valor normal), estados fora do
  tipo.** Coerente com o storage atual. Sozinha, não resolve o `"F"`.
- **B — `value_type` descreve todos os valores possíveis (`mixed`).**
  Enfraquece a validação, pois todo resultado com IF poderia virar `mixed`. A
  agregação passa a depender do runtime. Colide com o estado. Rejeitada.
- **C — remover `value_type`.**
  - O runtime passaria a aceitar qualquer texto em qualquer variável: P05a
    ("ERRO!!!" em numérica) deixaria de ser detectado.
  - Perde-se o esquema para validação estática futura (agregação só sobre
    numérico; aritmética sobre categórica).
  - Ganho: nenhum atributo a declarar.
  - Prejudicial. Rejeitada.
- **D — `value_type` + `result_state`.** O valor tem o tipo declarado; o
  estado (`VALID`, `CONDITIONAL_FAILURE`, …) vai em canal próprio. Resolve:
  - P14a/MT09: o domínio fica livre para usar "F";
  - P11b: uma única semântica de propagação;
  - F-001: o estado vira dado, não exceção, e o isolamento fica possível;
  - NT14: o estado se separa do erro técnico;
  - acomoda "ERRO!!!" sem `mixed`.
- **E — `value_type` + erro separado (`value = null`, `error = …`).**
  Trataria o `"F"` (regra de negócio sem regra aplicável) como erro técnico,
  repetindo a mistura atual (NT14). Adequado só para falhas técnicas.
  Rejeitada como representação de `"F"`.

## 16. TRADE-OFF MATRIX

| critério | A | B (mixed) | C (sem tipo) | **D (tipo + estado)** | E (tipo + erro) |
|---|---|---|---|---|---|
| validação de tipo | ✔ | ✘ | ✘ | ✔ | ✔ |
| resolve colisão "F" × categoria | ✘ | ✘ | ✘ | ✔ | parcial |
| propagação única | ✘ | ✘ | ✘ | ✔ | parcial |
| permite isolar F-001 | ✘ | ✘ | ✘ | ✔ | parcial |
| separa estado de erro técnico | ✘ | ✘ | ✘ | ✔ | ✘ |
| suporta "ERRO!!!" futuro | só como erro dinâmico | ✔ (sem semântica) | ✔ (sem semântica) | ✔ (estado com rótulo) | ✘ (vira erro técnico) |
| agregação previsível | ✔ | ✘ | ✘ | ✔ | ✔ |
| custo de migração | baixo | médio | médio | médio (sem persistência nem API hoje) | médio |

## 17. FINDINGS

Detalhe em `findings.md`.

| ID | título | sev. |
|---|---|---|
| T-01 | `"F"` (estado) no canal de valor colide com o domínio categórico | MAJOR |
| T-02 | F-001: fail-fast global por exceção suprime resultados independentes conforme a ordem topológica | MAJOR |
| T-03 | Dupla semântica de propagação do estado | MAJOR |
| T-04 | Estado de negócio e erro técnico no mesmo canal de exceção | MAJOR |
| T-05 | Entrada categórica inválida vira `"F"` (sem domínio de categorias declarado) | MINOR |
| T-06 | Sem checagem estática de tipo (ramos de IF, categórica aceitando número, agregação sobre categórica) | MINOR |
| T-07 | O gate de `value_type` depende de o chamador passar o registry | MINOR |
| T-08 | Booleano só intermediário, não é tipo de valor | INFO |
| T-09 | MIN/MAX inexistentes (DSL e agregação) | INFO |
| T-10 | Sem persistência, API ou serialização de resultados | INFO |
| T-11 | Ausência = chave ausente (`VariableNotFoundError`); `None` não representável | INFO |
| T-12 | Builders não leem `value_type`; nenhum seed o declara | INFO |
| T-13 | Marcadores de estado futuros ("ERRO!!!"): semântica a confirmar | DEFERRED |

## 18. RECOMMENDED CONCEPTUAL CONTRACT

Ver `conceptual-contract.md`. É uma proposta: nada foi implementado.

## 19. MIGRATION IMPACT

Estimativa; nada foi implementado.

| área | impacto |
|---|---|
| workbooks | nenhum obrigatório: o `"F"` escrito pode continuar como notação e ser mapeado para estado. Declarar categorias (opcional) nos 4 `hes_*`. |
| schema/seeds | `value_type` continua opcional (padrão `numeric`); opcional `allowed_values` para categóricas; marcadores de estado declarados |
| builders | ler `value_type`; mapear literais-marcador para estado; validação estática de ramos e agregação |
| validators | checagens estáticas: IF × `value_type`; agregação só sobre numérico |
| evaluator | resultado = valor + estado; consumir estado → estado (não exceção); `== "F"` → predicado de estado |
| runtime/engine | isolamento por nó: estado propaga só aos descendentes; erros técnicos seguem fail-fast ou isolados, por decisão |
| storage | `CalculationContext` guarda o estado junto do valor; `"F"` deixa de ser texto |
| agregação | já trata `"F"` como estado; troca a checagem de texto pela de estado |
| APIs/persistência/relatórios | inexistentes hoje: custo zero de compatibilidade; definir a serialização de `ForecastValue` com estado |
| testes | 21 itens de teste do contrato `"F"` (12 funções em `tests/test_dsl_structural_contracts.py`) mudam de exceção para estado |
| observabilidade | estados contáveis por período e escopo, em vez de exceções |

## 20. STAGE 3 GATE

**READY_WITH_CONDITIONS**. Ver `stage3-gate.md`.
