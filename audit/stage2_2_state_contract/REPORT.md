# Etapa 2.2 — Fechamento Formal do Contrato de Estados, Resultados Especiais e Fronteira Valor × Estado × Erro

Auditoria **read-only**. Nenhum arquivo de produção (`app/`, `data/`,
`tools/`, `tests/`), builder, seed, workbook ou teste existente foi
alterado. Todos os artefatos desta etapa estão em
`audit/stage2_2_state_contract/`.

Rótulos: **FATO OBSERVADO**, **INFERÊNCIA**, **HIPÓTESE**, **DECISÃO**
(escolha arquitetural fechada nesta etapa, não implementada).

---

## 1. Executive Summary

Esta etapa fecha, sem deixar `OPEN DECISION`/`TBD`, as quatro questões que
a Etapa 2.1 havia deixado como decisões de conteúdo/política:

| decisão | fechamento |
|---|---|
| D1 — mecanismo de declaração | **C (metadata `declared_result_states`) + A (sentinela textual mantido na fórmula)**, tradução pelo builder |
| D2 — escopo da taxonomia | **taxonomia global fixa de 4 rótulos**, cada variável declara o subconjunto que pode produzir |
| D3 — fronteira estado × erro técnico | fronteira lógica mantida (Etapa 2.1 §13); **política de propagação de erro técnico FECHADA**: mesma mecânica de isolamento por alcançabilidade do grafo usada para estado de negócio, nunca convertendo erro técnico em `result_state` |
| D4 — `UNAVAILABLE`/`DATA_NOT_YET_READY` | **excluído da taxonomia agora** (Alternativa B), com regra explícita de extensibilidade futura |

A decisão de D3 exigiu uma correção em relação à Etapa 2.1: a leitura desta
etapa de `app/engine/dependency_graph.py` e `app/engine/dependency_resolver.py`
mostra que **não existe hoje** um índice de descendentes/alcançabilidade
reversa — só a ordem topológica linear e as dependências diretas de cada
nó (arestas para frente). A Etapa 2.1 havia dito "a árvore já conhece os
descendentes"; isso é impreciso. Registrado aqui como
**ARCHITECTURAL GAP** (não implementado nesta etapa; ver §7 e §16).

O contrato resultante é aplicável, sem exceção especial, a `yield`,
`production`, `energy`, `max_ht` e `area_41` (§14). O projeto está apto
para a **Etapa 2.3**.

**Gate: `STAGE_2.3_GATE: READY`.**

---

## 2. Evidence Base

### Consultado nesta etapa (leitura direta, read-only)

| arquivo | trecho | uso |
|---|---|---|
| `audit/stage2_1_result_state_contract/REPORT.md` | integral (20 seções) | evidência histórica primária desta etapa |
| `audit/stage2_1_result_state_contract/evidence/*.csv`, `probes_2_1_results.json` | matrizes completas | base quantitativa das decisões |
| `audit/stage2_typing_contract/stage3-gate.md` | condições do gate `READY_WITH_CONDITIONS` | rastreabilidade da cadeia Etapa 2 → 2.1 → 2.2 |
| `app/engine/forecast_engine.py:375-403` | loop `calculate_from_definition_registry` | reconfirmação do F-001 (fail-fast global, sem try/except por nó) |
| `app/engine/exceptions.py` | 29 classes | reconfirmação da hierarquia única `EvaluationError` |
| `app/engine/dependency_graph.py` | `get_dependencies`, `as_dict`, ausência de método de descendentes | **evidência NOVA**: gap de alcançabilidade reversa |
| `app/engine/dependency_resolver.py` | `resolve()` | **evidência NOVA**: retorna só `tuple[str, ...]` de ordem topológica, nenhum índice de descendentes é mantido |
| `app/engine/expression_parser.py:58,174,233-267` | `ALLOWED_FUNCTIONS` | reconfirmação de que `ast.Call`/`STATE(...)` seria viável mas exigiria migração de sintaxe |
| `app/engine/calculation_context.py:464-500` | `_validate_variable_value` | reconfirmação do gap de `allowed_values` |
| `app/engine/temporal_aggregation_service.py:260-296` | `_require_numeric_series` | reconfirmação da Política B |

### Classificação

- **observed**: comportamento do loop do engine, hierarquia de exceções,
  ausência de índice reverso no grafo de dependências, ausência de
  `allowed_values`, Política B de agregação — todos vistos diretamente no
  código nesta etapa ou na Etapa 2.1 e revalidados por leitura própria.
- **inferred**: a taxonomia de 4 estados é suficiente e completa (baseada
  nos 5 workbooks + 2º caso de estudo, sem evidência de um 5º estado);
  `mixed` continua desnecessário; o mesmo mecanismo de isolamento serve
  para estado e para erro técnico (consistência arquitetural, não
  observação direta de código já existente).
- **decided**: as quatro decisões D1-D4 desta etapa (§6-§10), e a escolha
  específica de cada alternativa dentro delas.

Nenhuma probe nova foi necessária: as questões desta etapa são de
**fechamento de decisão sobre evidência já produzida na Etapa 2.1**, não
de levantamento de fato novo — exceto a leitura direta do grafo de
dependências, que revelou o gap acima e é tratada como fato observado
nesta etapa (não reexecução do harness de probes da Etapa 2.1).

---

## 3. Scope of This Stage

Fecha D1-D4 (declaração de estado, escopo da taxonomia, fronteira
estado × erro técnico com política de propagação de erro técnico, e
`UNAVAILABLE`). **Não reabre**: `value_type` (Etapa 2, reconfirmado Etapa
2.1), `mixed` (rejeitado, não reaberto), taxonomia de 3 estados de negócio
em si (`NO_APPLICABLE_RULE`/`INVALID_INPUT`/`VALIDATION_FAILED`, já
evidenciada na Etapa 2.1 — aqui só se fecha COMO ela é declarada e
ESCOPADA), `scope_type`/`scope_value`/`@grupo`/`name+frequency+scope`
(fechados em etapas anteriores). Não implementa nada em código de
produção, builders, seeds, parser, evaluator, `ForecastEngine`,
`ScopeResolver`, `CalculationContext`, workbooks ou testes.

---

## 4. Architectural Hypothesis

Hipótese de fechamento: as quatro questões abertas na Etapa 2.1 não são
lacunas de EVIDÊNCIA — são lacunas de DECISÃO sobre evidência já
suficiente. Ou seja, nenhuma delas exige uma nova rodada de probes; exige
escolher, com justificativa, entre alternativas já comparadas (D1, D4) ou
recém-comparadas com evidência de código adicional (D3).

**Resultado do teste:** confirmado para D1, D2 e D4 — a evidência da Etapa
2.1 já era suficiente para fechar. Para D3, a hipótese inicial ("o grafo já
conhece os descendentes") precisou de correção após leitura direta de
`dependency_graph.py`/`dependency_resolver.py` nesta etapa (§7) — a
decisão foi fechada mesmo assim, mas com o gap de implementação registrado
explicitamente em vez de presumido como já resolvido.

---

## 5. Existing Runtime Behavior

Reconfirmado sem alteração em relação à Etapa 2.1 (não repetido aqui na
íntegra — ver `audit/stage2_1_result_state_contract/REPORT.md` §5), com um
item adicional:

| componente | comportamento confirmado nesta etapa | evidência |
|---|---|---|
| `DependencyGraph` | mantém só arestas para frente (`node -> suas dependências`); `as_dict()`/`get_dependencies()` não oferecem `descendentes(node)` | `app/engine/dependency_graph.py` (lido integralmente nesta etapa) |
| `DependencyResolver.resolve()` | retorna apenas `tuple[str, ...]` em ordem topológica; nenhum índice reverso é calculado ou armazenado | `app/engine/dependency_resolver.py:11-53` |

---

## 6. D1 — Mecanismo de Declaração de Estado Especial

### 6.1 Onde o estado especial é declarado?

**DECISÃO: C — metadata da `VariableDefinition`**, através de um novo
campo conceitual `declared_result_states` (lista de rótulos da taxonomia
global, §8, que aquela variável pode produzir). **A sintaxe da fórmula não
muda** (Alternativa B, `STATE(...)`, é tecnicamente viável — `ast.Call` já
suportado — mas rejeitada como mecanismo primário porque exigiria migrar
todas as fórmulas condicionais existentes; fica registrada como alternativa
válida para uma eventual Etapa futura, não para a 2.3).

### 6.2 Como o workbook representa o estado?

O workbook continua a escrever o **marcador textual** na fórmula (ex.:
`"F"`, `"ERRO!!!"`), exatamente como hoje — **representação de origem
(source representation)**. A `VariableDefinition` da variável declara
**ambos**: o(s) rótulo(s) semânticos da taxonomia global que ela pode
produzir (`declared_result_states`) e, implicitamente através da fórmula
já escrita, qual literal corresponde a cada rótulo. Ou seja: o workbook
declara o marcador textual (já faz isso); o modelador, ao preencher
`declared_result_states` na definição da variável, declara o(s) rótulo(s)
semânticos que aquele marcador representa.

```text
source representation     "F"                       (na fórmula, no workbook, inalterado)
semantic representation   NO_APPLICABLE_RULE          (em declared_result_states, na definição da variável)
runtime representation    EvaluationResult.result_state = "NO_APPLICABLE_RULE"
                           (produzido pelo evaluator ao reconhecer que o
                            valor calculado é um dos literais declarados)
```

### 6.3 Quem é responsável pela tradução?

```text
Workbook (literal "F" na fórmula)
    ↓
Builder (lê declared_result_states da definição da variável; sabe que,
         PARA ESTA variável, o literal "F" corresponde ao rótulo
         NO_APPLICABLE_RULE — mesma camada que já traduz texto->ID em
         reference_resolver.translate_expression)
    ↓
VariableDefinition (carrega declared_result_states como metadado)
    ↓
Evaluator (ao avaliar a fórmula e obter um literal que bate com um dos
           declared_result_states DA VARIÁVEL ALVO, produz
           result_state=<rótulo> em vez de gravar o literal no canal de
           valor)
    ↓
EvaluationResult (value=None quando result_state != VALID; result_state
                   presente sempre)
```

A tradução ocorre **por variável**, não globalmente — não existe uma
lista única de "palavras reservadas na plataforma inteira". Isso é
condição necessária para 6.4.

### 6.4 Como evitar colisão entre valor legítimo e sentinela?

**DECISÃO:** a colisão é eliminada por construção, não por convenção. Um
literal só é tratado como estado se estiver listado em
`declared_result_states` **daquela variável especificamente**. O contrato
exige uma regra de validação estática no builder:

> Para toda `VariableDefinition`, a interseção entre `allowed_values`
> (domínio de categorias de negócio) e `declared_result_states` (rótulos
> de estado, mapeados aos literais usados na fórmula) deve ser vazia.

Isso é verificável em tempo de build (o builder já teria as duas listas
disponíveis), sem depender de "sabemos que nesse workbook significa isso"
— é uma checagem de conjunto, não conhecimento tácito. Nenhuma variável
que não declara `declared_result_states` para um literal trata esse
literal como estado — ele permanece um valor categórico comum (ou, se
fora do domínio declarado, `INVALID_INPUT`, §9).

---

## 7. D2 — Escopo da Taxonomia de Estados

### 7.1 Separar estado de valor

Formalizado, sem mudança em relação à Etapa 2.1 (reconfirmado):

```text
value           — presente sse result_state == VALID; tipo = value_type
result_state    — VALID | um dos 4 rótulos globais de negócio
technical error — nunca um value nem um result_state; permanece exceção
```

### 7.2 Os estados são globais?

**DECISÃO: sim — taxonomia global fixa de 4 rótulos**
(`VALID`, `NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED`), e
cada variável declara, via `declared_result_states`, quais desses 4
rótulos globais ela é capaz de produzir. O exemplo do prompt é confirmado
como o contrato definitivo:

```text
retirada_condensado_grupo
    value_type = numeric
    declared_result_states: [NO_APPLICABLE_RULE]

hes_l4 / hes_l5 (categóricas de entrada)
    value_type = categorical
    allowed_values: [Normal, LC, Overhaul/Parada, "1 By pass", "1 By pass e LC"]
    declared_result_states: []   (variáveis de ENTRADA não produzem estado —
                                   ver §9; uma entrada fora do domínio é
                                   INVALID_INPUT detectado pelo CONSUMIDOR
                                   ou pela validação de entrada, não uma
                                   auto-declaração da variável hes)
```

Nenhuma variável pode inventar um rótulo fora dos 4 globais — isso é o
que impede a proliferação de "sentinelas locais" que motivou esta etapa.

### 7.3 Não criar estados especulativos

Cada um dos 4 estados globais possui, na taxonomia fechada, definição,
produtor, condição de ocorrência, representação, comportamento, impacto em
dependentes e impacto em agregação — todos já documentados em
`audit/stage2_1_result_state_contract/evidence/state_taxonomy_matrix.csv`
e reconfirmados aqui sem alteração (linhas VALID, NO_APPLICABLE_RULE,
INVALID_INPUT, VALIDATION_FAILED). `UNAVAILABLE` permanece fora — ver §10.

---

## 8. D3 — Fronteira Estado × Erro Técnico

### 8.1 Resultado de domínio (negócio)

`NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED` — pertencem ao
contrato de dados/negócio (`result_state`), nunca a uma exceção Python.

### 8.2 Erro técnico

`ParserError`/`UnsafeExpressionError`, `VariableNotFoundError`,
`DivisionByZeroError`, `MathDomainError`, `ExpressionTypeError` — permanecem
exceções técnicas. **DECISÃO: nunca convertidos em `result_state`** —
resposta explícita à pergunta do prompt ("um erro técnico pode ser
convertido em `result_state`?" → **NÃO**). Misturar as duas categorias
reintroduziria exatamente a ambiguidade que esta etapa existe para
eliminar (uma falha real do motor mascarada como condição de negócio
esperada).

### 9. D3 — Política de Propagação de Erro Técnico

Cenário do prompt:

```text
A → B
C → D
A → TechnicalError
```

**DECISÃO, ponto a ponto:**

- **B deve ser bloqueado?** Sim, se B depende de A (é descendente direto
  de A no grafo). B recebe um resultado `BLOCKED_BY_UPSTREAM_ERROR`
  (categoria nova, distinta de `value` e de `result_state` — não é dado,
  não é estado de negócio, é a marca de "não pôde ser avaliado porque um
  ancestral falhou tecnicamente").
- **C deve continuar?** Sim, se C **não** depende de A (nenhum caminho no
  grafo de C até A) — mesma lógica de isolamento por alcançabilidade
  definida para estado de negócio na Etapa 2.1 §9, agora estendida a erro
  técnico.
- **D deve continuar?** Depende exclusivamente de sua própria cadeia de
  dependência: se D depende de C (que não depende de A), D continua; se D
  depende de B (que depende de A), D também vira `BLOCKED_BY_UPSTREAM_ERROR`.
- **O cálculo global deve abortar?** **Não** — esta é a mudança de decisão
  em relação ao comportamento atual (que aborta tudo, F-001/T-02). A
  rodada continua para todo nó cujo caminho de dependência não passa pelo
  nó que falhou tecnicamente.
- **Como o erro é registrado?** Por nó/período, como hoje já é feito para
  `AggregationFailureError` (payload com identificação da origem): um
  registro `TechnicalError{exception_type, message, context}` associado ao
  nó que efetivamente falhou; nós `BLOCKED_BY_UPSTREAM_ERROR` carregam uma
  referência a esse nó de origem, não uma cópia do erro.
- **Um erro técnico pode ser agregado?** Não como valor — mas um período
  com erro técnico (ou com um nó `BLOCKED_BY_UPSTREAM_ERROR`) invalida o
  agregado da mesma forma que um `result_state` não-`VALID` invalida hoje
  (reuso da Política B já fechada na Etapa 2.1 §10 — não é uma política
  nova, é a MESMA política aplicada a uma terceira categoria de "não é um
  número utilizável").
- **Um erro técnico pode virar `result_state`?** **Não** (§8.2, reafirmado
  aqui de forma explícita e final).

**ARCHITECTURAL GAP (não implementado nesta etapa):** o mecanismo acima
pressupõe a capacidade de determinar, para o nó que falhou, o conjunto de
seus descendentes no grafo. A leitura desta etapa de `dependency_graph.py`
e `dependency_resolver.py` (§5) confirma que essa capacidade **não existe
hoje** — só as dependências diretas de cada nó (arestas para a frente) e a
ordem topológica linear são conhecidas. Construir um índice reverso
(`descendentes(node_id)`, por inversão de `DependencyGraph.as_dict()`) é
tecnicamente simples, mas é trabalho de implementação da **Etapa 3**, não
desta etapa. Este é o único ponto em que a decisão conceitual (§9) excede
o que o código atual já suporta — registrado explicitamente, não
mascarado (regra 18 do prompt: "não faça alterações sob o argumento de
'é apenas para validar o conceito'").

---

## 10. D4 — `UNAVAILABLE` / `DATA_NOT_YET_READY`

**DECISÃO: Alternativa B — excluir da taxonomia atual**, com
extensibilidade futura explícita.

> Ausência de evidência não cria estado implícito.

Nenhum dos 5 workbooks auditados (`yield`, `production`, `energy`,
`max_ht`, `area_41`) nem o código de produção demonstra um caso real em
que "valor de negócio ainda não disponível" precise de uma semântica
distinta de `VariableNotFoundError` (que já cobre, como erro técnico,
"chave ausente no `CalculationContext`" — comportamento atual, sem
reclamação registrada em nenhuma das cinco etapas de auditoria já feitas
neste repositório).

**Procedimento se o requisito aparecer no futuro:** um bloco futuro que
precise expressar "este valor é de negócio legítimo, mas ainda não foi
calculado neste momento do pipeline, e isso não é um erro de busca" deve
apresentar um caso real (não hipotético), percorrer a cadeia
`Evidence → Analysis → Decision → Contract` (regra 20 do prompt), e só
então um 5º rótulo pode ser adicionado à taxonomia global (§7.2). Não deve
ser adicionado preventivamente nesta etapa nem na Etapa 3.

---

## 11. Matriz de Decisão

Ver `evidence/decision_matrix.csv` (5 colunas: alternativas avaliadas,
evidência, decisão final, justificativa, impacto Etapa 3 — para D1-D4).
Resumo:

| decisão | decisão final |
|---|---|
| D1 | C (`declared_result_states` na `VariableDefinition`) + A (sentinela textual mantido), tradução pelo builder |
| D2 | Taxonomia global fixa (4 rótulos); cada variável declara subconjunto via `declared_result_states` |
| D3 | Fronteira mantida (nunca converter erro técnico em `result_state`); propagação de erro técnico usa a MESMA mecânica de isolamento por alcançabilidade que a de estado de negócio — com gap de implementação registrado (índice de descendentes não existe hoje) |
| D4 | Excluir `UNAVAILABLE`/`DATA_NOT_YET_READY` agora (Alternativa B); extensibilidade condicionada a evidência futura |

---

## 12. Final State Taxonomy

| estado | definição | pode ser valor? | pode ser exceção? | quem produz? | propaga? | entra em agregação? |
|---|---|---:|---:|---|---:|---:|
| `VALID` | valor válido presente, dentro do `value_type` declarado | sim | não | qualquer variável, ramo nominal | sim, como dado normal | sim |
| `NO_APPLICABLE_RULE` | entrada(s) válida(s), mas nenhuma regra de negócio cobre a combinação | não | não | variável com fórmula condicional (ex.: `retirada_condensado_grupo`) | sim, aos descendentes alcançáveis, como `result_state` | invalida o agregado do período (Política B) |
| `INVALID_INPUT` | entrada categórica fora do domínio declarado (`allowed_values`) | não | não (hoje: nenhum tratamento — gap) | detectado no consumo de uma variável `categorical` com `allowed_values` | sim, aos descendentes alcançáveis, como `result_state` | invalida o agregado do período (Política B) |
| `VALIDATION_FAILED` | valor CALCULADO com sucesso, rejeitado por regra de negócio secundária (ex.: `"ERRO!!!"`) | não | não | variável com fórmula condicional de validação | sim, aos descendentes alcançáveis, como `result_state` | invalida o agregado do período (Política B) |
| `BLOCKED_BY_UPSTREAM_ERROR` (nova nesta etapa, §9) | nó não avaliado porque um ancestral produziu erro técnico | não | não (não é a exceção em si — é a marca de bloqueio) | qualquer nó descendente de um nó com erro técnico | sim, transitivamente aos seus próprios descendentes | invalida o agregado do período (mesma Política B) |
| `TECHNICAL_ERROR` | falha do motor de cálculo (não do modelo de negócio) | não | sim | qualquer nó, na própria avaliação | não como dado — só como origem de `BLOCKED_BY_UPSTREAM_ERROR` nos descendentes | não aplicável (agregação nunca alcança um valor) |

`UNAVAILABLE`/`DATA_NOT_YET_READY`: **fora da taxonomia** (§10).

---

## 13. Final Value/State/Error Contract

```text
value_type        domínio do VALOR válido (numeric | categorical);
                    declarado pelo modelador; nunca inferido; nunca
                    promovido dinamicamente (Etapa 2/2.1, reconfirmado)

value              presente sse result_state == VALID; tipo = value_type

result_state       VALID | um dos 4 rótulos globais que a variável
                    declara em declared_result_states (D2)

detail             opcional: rótulo de origem / períodos afetados / nó de
                    origem (para BLOCKED_BY_UPSTREAM_ERROR) — mesmo padrão
                    já usado por AggregationFailureError.failed_period_ids

technical exception nunca um value nem um result_state; permanece
                    exceção Python; nunca convertida em result_state (D3)
```

Relação: `value_type` restringe o TIPO do `value` quando `result_state ==
VALID`; fora disso, `value` é ausente e `result_state`/`detail` carregam
toda a informação. `technical exception` é uma categoria disjunta — não
compete com `value_type` nem com `result_state`; sua única interação com o
contrato é produzir, nos descendentes alcançáveis, um `result_state`
degenerado (`BLOCKED_BY_UPSTREAM_ERROR`) que NÃO é um dos 4 rótulos de
negócio, mas segue a mesma mecânica de propagação e agregação.

---

## 14. Workbook Declaration Contract

Conceitual, não implementado:

```text
VariableDefinition
    name
    frequency
    scope
    variable_type
    value_type               (numeric | categorical)
    allowed_values            (opcional; só categorical; domínio de
                                categorias de NEGÓCIO; nunca inclui
                                rótulos de estado — D1.4)
    declared_result_states    (opcional; subconjunto dos 4 rótulos globais
                                de D2 que esta variável pode produzir)
    formula                   (inalterada — continua usando o marcador
                                textual, ex. "F", "ERRO!!!", como hoje)
```

O modelador declara `allowed_values` para toda variável `categorical` cujo
domínio seja fechado (ex.: `hes_l4..l7`, 5 categorias), e
`declared_result_states` para toda variável cuja fórmula produza um
marcador textual reservado (hoje: só `retirada_condensado_grupo`-like no
A41; nenhuma variável de `yield`/`production`/`energy`/`max_ht` precisa
declarar nada aqui, §14 abaixo confirma o no-op).

---

## 15. Runtime Contract

```text
EvaluationResult   (por instância x período)
    value            (tipo = value_type; presente sse result_state=VALID)
    result_state      (VALID | NO_APPLICABLE_RULE | INVALID_INPUT |
                        VALIDATION_FAILED | BLOCKED_BY_UPSTREAM_ERROR)
    detail            (opcional)

TechnicalError     (exceção; nunca um EvaluationResult)
    exception_type
    message
    context
```

Sem mudança em relação à proposta da Etapa 2.1 (§18 daquele relatório),
exceto pela adição formal de `BLOCKED_BY_UPSTREAM_ERROR` como quinto valor
possível de `result_state` — necessário para fechar D3 sem inventar uma
sexta categoria fora do enum.

---

## 16. Propagation Contract

```text
state → dependente alcançável        propaga como dado (result_state),
                                       nunca lança exceção ao ser consumido
state → nó não-alcançável a partir
        do produtor do estado         não é afetado; calculado normalmente

technical error → dependente
        alcançável                    dependente vira BLOCKED_BY_UPSTREAM_ERROR
technical error → nó não-alcançável
        a partir do nó que falhou     não é afetado; calculado normalmente

nó independente                       sempre calculado, independentemente
                                       de qualquer estado ou erro técnico
                                       em outra parte do grafo
```

Exemplos (retomando o cenário canônico da Etapa 2.1 e desta etapa):

```text
A → NO_APPLICABLE_RULE (estado)      C depende de A → result_state herdado
B → valor válido (independente)      D depende de B → valor calculado normalmente

A → TechnicalError (erro técnico)    C depende de A → BLOCKED_BY_UPSTREAM_ERROR
B → valor válido (independente)      D depende de B → valor calculado normalmente
```

**Pré-requisito de implementação (Etapa 3, não desta etapa):** construir o
índice reverso de descendentes a partir de `DependencyGraph.as_dict()`
(§9, gap registrado) — sem ele, `ForecastEngine` não tem como saber quais
nós isolar.

---

## 17. Aggregation Contract

Política B (reconfirmada, Etapa 2.1 §10), agora explicitamente estendida a
`BLOCKED_BY_UPSTREAM_ERROR`:

```text
numeric + numeric + special_state        → agregado inválido, período
                                            listado (result_state != VALID)
numeric + numeric + BLOCKED_BY_UPSTREAM_
    ERROR                                → agregado inválido, período
                                            listado (mesma política B —
                                            não é uma política nova)
```

Erro técnico em si nunca chega à agregação como um valor a ser somado ou
ignorado — o período em que ele ocorreu é sempre listado como afetado,
exatamente como um `result_state` não-`VALID` hoje.

---

## 18. Category Contract

`allowed_values` (domínio de categorias de NEGÓCIO) formalizado, usando
`hes_l4`/`hes_l5` como caso real (reconfirmado da Etapa 2.1 §11, sem
mudança):

```text
hes_l4 / hes_l5
    value_type = categorical
    allowed_values: [Normal, LC, "Overhaul/Parada", "1 By pass",
                      "1 By pass e LC"]
```

- **Categoria inválida** (`INVALID_INPUT`): valor categórico que NÃO
  pertence a `allowed_values` da variável de ENTRADA (ex.: `"Overhaul"`,
  typo de `"Overhaul/Parada"`).
- **Regra não aplicável** (`NO_APPLICABLE_RULE`): TODAS as entradas
  pertencem a seus respectivos `allowed_values`, mas nenhum ramo da
  fórmula consumidora cobre essa combinação (ex.: `hes_l4="Normal"`,
  `hes_l5="1 By pass e LC"` em `retirada_condensado_grupo@L4_L5`).

As duas condições são logicamente distintas e detectáveis
independentemente uma da outra assim que `allowed_values` existir: a
primeira é uma propriedade da ENTRADA (checável antes de qualquer
cálculo); a segunda só é observável DEPOIS de avaliar a fórmula
consumidora contra entradas já válidas.

---

## 19. A41 Canonical Example

`retirada_condensado_grupo@L4_L5`, `frequency=diário`.

### Caso válido

```text
hes_l4@L4 = Normal
hes_l5@L5 = Normal
→ value = 100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2)   [numérico]
→ result_state = VALID
```

### Caso especial (regra não aplicável)

```text
hes_l4@L4 = Normal
hes_l5@L5 = "1 By pass e LC"
→ (nenhum dos 5 ramos da fórmula cobre esta combinação)
→ value = None
→ result_state = NO_APPLICABLE_RULE
```

### Caso inválido

```text
hes_l4@L4 = "Overhaul"   (fora de allowed_values: typo de "Overhaul/Parada")
hes_l5@L5 = Normal
→ value = None
→ result_state = INVALID_INPUT
```

Os três casos são representados por **três combinações diferentes** de
`(value, result_state)`, nunca por três strings distintas no MESMO campo
`value` — o que hoje (`"F"` genérico para os dois primeiros casos, texto
literal absorvido silenciosamente para o terceiro) é exatamente o defeito
que este contrato elimina.

---

## 20. CONTRACT FOR STAGE 2.3

Objetivo: permitir que outro engenheiro revise `yield`, `production`,
`energy`, `max_ht` e `area_41` sem precisar interpretar o relatório
inteiro.

### Checklist normativa

```text
[x] value_type declarado — obrigatório em toda VariableDefinition
    (numeric | categorical; padrão numeric)
[x] value_type representa somente domínio do valor — nunca estado, nunca
    erro técnico, nunca inferido em runtime
[x] categorias explicitamente declaradas quando aplicável — toda variável
    categorical com domínio fechado declara allowed_values
[x] estados especiais explicitamente declarados quando aplicável — toda
    variável cuja fórmula produz marcador textual reservado declara
    declared_result_states (subconjunto de VALID | NO_APPLICABLE_RULE |
    INVALID_INPUT | VALIDATION_FAILED)
[x] sentinelas textuais não confundidas com valores — um literal só é
    estado se estiver em declared_result_states DAQUELA variável; nunca
    global; nunca por convenção tácita
[x] escopos seguem name + frequency + scope — inalterado (fechado em
    etapa anterior, não reaberto)
[x] @scope utilizado corretamente — inalterado (idem)
[x] estado de negócio não modelado como exceção técnica — result_state
    nunca é uma exceção Python
[x] erro técnico não modelado como estado de negócio — technical
    exception nunca vira result_state (D3, §8.2/§9)
[x] equações não usam sentinelas implícitas sem declaração — todo literal
    reservado usado em uma fórmula condicional deve aparecer em
    declared_result_states da variável ALVO, validável estaticamente
    pelo builder (interseção vazia com allowed_values, §6.4)
```

### Resposta objetiva às duas perguntas de fechamento (regra 23 do prompt)

> "Dado este contrato definitivo, como cada variável dos workbooks
> `yield`, `production`, `energy` e `max_ht` deve ser declarada?"

Nenhuma delas produz hoje resultado heterogêneo (Etapa 2.1 §14,
reconfirmado): `yield`/`max_ht` têm zero literais textuais em fórmulas;
`production`/`energy` têm `IF`s com ambos os ramos numéricos. Portanto,
para os quatro blocos, o contrato é aplicado como **no-op**: toda variável
já é declarável hoje com `declared_result_states=[]` (ou campo ausente),
sem nenhuma migração. Se, no futuro, uma dessas variáveis passar a ter uma
fórmula condicional textual, ela seguirá exatamente a mesma regra do A41
— nenhum tratamento especial por bloco.

> "Como o mesmo contrato será aplicado ao `area_41` sem nenhuma regra
> especial para A41?"

`retirada_condensado_grupo` (e qualquer outra variável A41 com o mesmo
padrão) declara `declared_result_states: [NO_APPLICABLE_RULE]` e, quando
aplicável, `[VALIDATION_FAILED]` para o padrão `"ERRO!!!"` — usando os
MESMOS 4 rótulos globais e o MESMO mecanismo (metadata na
`VariableDefinition` + tradução no builder) que qualquer outro bloco
usaria. Nenhuma classe, campo ou caminho de código é exclusivo de A41; o
que hoje é exclusivo de A41 é apenas o FATO de que A41 é, até o momento, o
único bloco cujas fórmulas realmente produzem um marcador textual
reservado — uma propriedade dos DADOS do workbook, não da arquitetura.

A resposta a nenhuma das duas perguntas depende de `"F" significa isso
neste workbook`, de `"ERRO!!!" provavelmente significa aquilo`, de "o
engine decide pelo tipo do resultado", ou de "vamos descobrir durante a
implementação" — as quatro formulações proibidas pelo prompt (§23) são
todas substituídas por regras explícitas nas seções acima.

---

## 21. Self-Audit (checklist §21 do prompt)

```text
[x] D1 fechado (§6, §11)
[x] D2 fechado (§7, §11)
[x] D3 fechado (§8, §9, §11 — com gap de implementação registrado, não
    escondido)
[x] D4 fechado (§10, §11)

[x] value_type fechado (herdado da Etapa 2/2.1, não reaberto; §13)
[x] allowed_values fechado (§18, distinto de declared_result_states)
[x] declared_result_states fechado (§6, §14)
[x] EvaluationResult conceitualmente fechado (§15, incluindo
    BLOCKED_BY_UPSTREAM_ERROR)
[x] propagação fechada (§16, para estado E para erro técnico)
[x] agregação fechada (§17, Política B estendida sem virar política nova)
[x] erro técnico fechado (§8.2/§9 — nunca vira result_state; propagação
    via mesma mecânica de alcançabilidade que estado)
[x] A41 usado como caso canônico (§19)
[x] ERRO!!! analisado (§6.2, §14, §20 — classificado como
    VALIDATION_FAILED, sem presumir equivalência semântica com "F")
[x] nenhum estado especulativo introduzido (§7.3, §10 — UNAVAILABLE
    permanece excluído)
[x] nenhum código de produção alterado (confirmado, §22)
[x] nenhum workbook alterado (confirmado, §22)
[x] testes continuam na baseline (confirmado, §22)
[x] contrato para Etapa 2.3 produzido (§20)
```

---

## 22. STAGE 2.2 RESULT

```text
STAGE 2.2 RESULT

STATE_DECLARATION: CLOSED
STATE_TAXONOMY_SCOPE: CLOSED
STATE_VS_TECHNICAL_ERROR: CLOSED
UNAVAILABLE_STATE: CLOSED

VALUE_TYPE_CONTRACT: CONFIRMED
ALLOWED_VALUES_CONTRACT: CLOSED
PROPAGATION_CONTRACT: CLOSED
AGGREGATION_CONTRACT: CLOSED

PRODUCTION_FILES_CHANGED: NO
WORKBOOKS_CHANGED: NO
EXISTING_TESTS_CHANGED: NO

STAGE_2.3_GATE: READY
```

**Confirmação explícita:** nenhum arquivo de produção, builder, seed,
parser, evaluator, `ForecastEngine`, `ScopeResolver`, `CalculationContext`,
workbook ou teste existente foi alterado nesta etapa. `git status --short`
mostra apenas o diretório novo `audit/stage2_2_state_contract/` como não
rastreado; a suíte de testes permanece em **1414 passed / 0 failed**
(idêntica ao baseline registrado em `evidence/baseline.txt`).

O único ponto em que a decisão conceitual desta etapa excede o que o
código atual já suporta hoje — a necessidade de um índice reverso de
descendentes no grafo de dependências (§9) — foi explicitamente registrado
como `ARCHITECTURAL GAP`, não implementado, e fica delegado à Etapa 3.
