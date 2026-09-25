# Etapa 2.1 — Fechamento do Contrato Conceitual de Estados, Resultados Heterogêneos e Erros

Auditoria **read-only**. Nenhum arquivo de produção (`app/`, `data/`, `tools/`,
`tests/`), workbook ou teste existente foi alterado. Todos os artefatos desta
etapa estão em `audit/stage2_1_result_state_contract/`.

Rótulos usados: **FATO OBSERVADO** (visto diretamente no código/teste/
workbook), **INFERÊNCIA** (conclusão lógica a partir de fatos), **HIPÓTESE**
(explicação possível, ainda não demonstrada) e **RECOMENDAÇÃO** (decisão
arquitetural proposta, não implementada).

---

## 1. Executive Summary

A hipótese arquitetural de trabalho — `value_type` descreve só o valor
válido; estados de avaliação e erros técnicos vivem fora dele — **é
sustentada pela evidência**, mas o runtime atual **não implementa essa
separação**: ele mistura três conceitos observáveis:

1. um **valor válido** (número ou categoria);
2. um **estado de resultado** de negócio (hoje representado por um único
   sentinela textual, `"F"`, colado ao canal de valor);
3. um **erro técnico** do motor (já corretamente isolado em exceções, mas
   que compartilha a mesma família de exceções que o CONSUMO de `"F"` —
   `EvaluationError` — confundindo os dois no nível de tratamento).

Com evidência NOVA desta etapa (probes read-only sobre fixtures genéricas e
sobre o TEXTO REAL da equação `retirada_condensado_grupo@L4_L5` do A41 v6),
identificamos e demonstramos **3 estados de negócio genuínos e distintos**
(`NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED`) — nenhum deles
específico de A41 — e reproduzimos o F-001 numa forma multi-hop que confirma:
a supressão de resultados independentes é causada pela **ordem topológica de
execução combinada com fail-fast global**, não por tipagem.

O padrão futuro `SE(...;"ERRO!!!";valor)` foi testado concretamente e é
**estruturalmente idêntico** ao padrão A41 `SE(...;valor;"F")`: ambos exigem
a mesma solução (`result_state`), e nenhum dos dois exige `mixed`.

**Decisões fechadas:** taxonomia de estados (3 evidenciados + 1
explicitamente não incluído por falta de evidência), separação valor/estado/
erro, política de agregação (mantida — já correta), matriz de
responsabilidades por componente, generalização transversal confirmada por
inspeção cruzada de todos os blocos e por um segundo caso de estudo
independente.

**Decisões em aberto:** o mecanismo exato de DECLARAÇÃO do estado no
workbook (3 alternativas comparadas, nenhuma escolhida sem confirmação do
modelador), e a política de propagação de ERRO TÉCNICO (abortar vs isolar —
distinta da política de estado, que É fechada: isolar aos descendentes).

**Gate: `CONTRACT CLOSED WITH OPEN ITEMS`.**

---

## 2. Baseline

| item | valor |
|---|---|
| branch | `claude/funny-noether-nbcr7b` |
| HEAD | `196776c682a7ec28546d0f5436de933964cb8779` |
| relação com origin | sincronizado (`git rev-list --left-right --count` = `0 0`) |
| working tree | limpo no início da etapa (`git status --short` vazio) |
| suíte de testes | `python3 -m pytest -q` → **1414 passed, 0 failed, 0 skipped**, ~6,4-6,9s |
| artefato de referência da Etapa 2 | `audit/stage2_typing_contract/` (commit `196776c`), lido integralmente e **revalidado** (não apenas citado) nos pontos críticos: F-001 (código-fonte de `ForecastEngine.calculate_from_definition_registry`, linhas 375-403), hierarquia de exceções (`app/engine/exceptions.py`, todas as 29 classes listadas e confirmadas), contrato `value_type` (`CalculationContext._validate_variable_value`, linhas 464-500) |

Ver `evidence/baseline.txt` para o registro bruto (comando, timestamp,
commit, resultado).

---

## 3. Scope of This Stage

Esta etapa fecha o contrato CONCEITUAL para: taxonomia de estados;
declaração de resultado especial pelo workbook; propagação; agregação;
categorias válidas; fronteira estado × exceção; matriz de responsabilidade;
generalização entre blocos. Não reabre: `value_type` vs `variable_type`
(fechado na Etapa 2), `mixed` como tipo (rejeitado na Etapa 2 e não reaberto
aqui), contrato de `scope_type`/`scope_value` (fechado em
`audit/architecture_scope_contract/`), `@grupo`, `name+frequency+scope`. Não
implementa nada — nenhum arquivo de produção foi tocado (confirmado por
`git status --short` ao final, ver §2 e a confirmação em §20).

---

## 4. Architectural Hypothesis

**Hipótese testada:**

```text
VariableDefinition
    |
    +-- value_type       (domínio do VALOR válido)
    |
    +-- allowed_values    (proposto; só p/ categorical)
    |
    +-- formula

produz, por instância x período:

EvaluationResult
    |
    +-- valid value        (presente sse state = VALID)
    |
    +-- result state        (VALID | estado de negócio)

enquanto erros técnicos permanecem:

Technical Error
    |
    +-- exception (nunca vira dado)
```

**Resultado do teste:** a hipótese é **coerente e suficiente** para
representar todos os casos observados nos 5 workbooks e no segundo caso de
estudo, mas requer uma quarta peça não prevista na formulação original — um
domínio de categorias válidas (`allowed_values`) — para que `INVALID_INPUT`
seja sequer DETECTÁVEL (sem ele, uma entrada categórica malformada é
indistinguível de uma entrada válida sem regra aplicável). Ver §11.

---

## 5. Existing Runtime Behavior

Re-verificado nesta etapa por leitura direta de código (não apenas citação
da Etapa 2):

| componente | comportamento confirmado | evidência |
|---|---|---|
| `ForecastEngine.calculate_from_definition_registry` | `for node_id in execution_order:` sem `try/except` por nó; a primeira `EquationEvaluationError` propaga e aborta o `for` inteiro | `app/engine/forecast_engine.py:375-403` (lido nesta etapa) |
| hierarquia de exceções | `ConditionalFailureError`, `DivisionByZeroError`, `MathDomainError`, `ExpressionTypeError` são todas subclasses diretas de `EvaluationError` — nenhuma distinção estrutural entre "estado de negócio consumido" e "erro técnico do motor" | `app/engine/exceptions.py` (29 classes listadas nesta etapa) |
| `CalculationContext._validate_variable_value` | número: sempre aceito; texto: aceito só se a variável foi declarada `categorical`, **sem checagem contra nenhum conjunto de valores permitidos**; `"F"` aceito em qualquer variável, numeric ou categorical | `app/engine/calculation_context.py:464-500` (lido nesta etapa) |
| `AggregationRule` | é **exclusivamente temporal** (`source_frequency -> target_frequency`); não existe um conceito de agregação espacial na plataforma | `app/domain/forecast/aggregation.py:32-44`, docstring: "Regra de agregação **temporal**..." |
| "agregação espacial" (grupo/total) no A41 | **não é um `AggregationRule`** — é uma `EquationDefinition` comum que soma/computa valores `@grupo` referenciados explicitamente | confirmado por leitura direta da equação `retirada_condensado_total@L1_L7 diário` = `retirada_condensado_grupo@L1_L3 + retirada_condensado_grupo@L4_L5 + retirada_condensado_grupo@L6_L7` (§6) |
| `TemporalAggregationService._require_numeric_series` | um único período com `"F"` invalida TODO o agregado, listando os períodos afetados; nunca ignora, nunca trata como zero, nunca produz parcial | `app/engine/temporal_aggregation_service.py:260-296`, docstring confirmada nesta etapa: *"não é ignorado nem tratado como 0: a agregação inteira falha"* |
| parser — chamadas de função | `ast.Call` já é um nó suportado, com allowlist por nome e aridade (`ALLOWED_FUNCTIONS = {"ln": 1}`) | `app/engine/expression_parser.py:58,174,233-267` — relevante para §8 (Alternativa B) |
| domínio de categorias | **nenhum campo `allowed_values` existe** em `VariableDefinition`; as únicas ocorrências de `allowed_values` no repositório são variáveis locais de `ENUM_FIELDS` nos `*_seed_validator.py`, que validam METADADOS de campo (`variable_type`, `frequency`, `scope_type`), não o domínio de VALORES de uma variável `categorical` | grep completo em `app/`, `tools/`, `data/` (0 ocorrências fora desse padrão) |

---

## 6. A41 Case Study

Caso principal: `retirada_condensado_grupo`, `frequency=diário`,
`scope_type=linha_grupo`, `scope_value=L4_L5`.

**FATO OBSERVADO** — a equação real, extraída do workbook v6 validado
(`audit/area_41_v6/descritivo_das_variáveis_A41_v6.xlsx`, célula M39, sem
alteração do arquivo):

```text
(100 - ((retirada_cond_corr_ltp - retirada_cond_corr_lth) * 2))
  if hes_l4@L4 == "Normal" and hes_l5@L5 == "Normal"
  else (... ramo LC ...)
       if hes_l4@L4 == "LC" or hes_l5@L5 == "LC"
       else (... ramo Overhaul/Parada ...)
            if hes_l4@L4 == "Overhaul/Parada" or hes_l5@L5 == "Overhaul/Parada"
            else (... ramo 1 By pass ...)
                 if hes_l4@L4 == "1 By pass" or hes_l5@L5 == "1 By pass"
                 else (... ramo 1 By pass e LC ...)
                      if hes_l4@L4 == "1 By pass e LC" and hes_l5@L5 == "1 By pass e LC"
                      else "F"
```

Domínio de categorias efetivamente usado (extraído por varredura de TODAS
as comparações `hes_lN@LX == "..."` em TODAS as equações do workbook):
`{Normal, LC, Overhaul/Parada, 1 By pass, 1 By pass e LC}` — exatamente 5,
confirmando a Etapa 2 por caminho independente (`d5_category_domain()`).

Respostas às 11 perguntas, com exemplos concretos de `hes@L4`/`hes@L5`:

1. **`value_type` correto de `retirada_condensado_grupo`?** `numeric` — é o
   valor declarado no workbook (`value_type: 'numeric'`, coluna P) e é
   consistente: TODOS os 5 ramos que produzem valor produzem um número; só
   o `else` final produz texto.
2. **O número é um valor?** Sim, sem ambiguidade — é o resultado normal de
   uma fórmula aritmética sobre `retirada_cond_corr_ltp`/`retirada_cond_corr_lth`.
3. **`"F"` é valor ou estado?** **Estado.** Não representa uma grandeza
   física (a variável é `m³/h`); representa "a avaliação não encontrou uma
   regra de negócio aplicável a este par de entradas".
4. **Se for estado, qual a semântica exata?** Depende do PAR de entradas
   (ver casos A e B abaixo) — há DUAS semânticas distintas colapsadas no
   mesmo sentinela:
   - **Caso A** — `hes_l4="Normal"`, `hes_l5="1 By pass e LC"`: ambas as
     categorias pertencem ao domínio declarado; nenhum dos 5 ramos cobre
     esta combinação → `NO_APPLICABLE_RULE`.
   - **Caso B** — `hes_l4="Overhaul"` (typo de `"Overhaul/Parada"`),
     `hes_l5="Normal"`: `"Overhaul"` NÃO pertence ao domínio declarado →
     deveria ser `INVALID_INPUT`.
   - **Resultado observado (probe `d1_1_no_rule_vs_invalid_input()`,
     executado sobre a expressão REAL traduzida):** ambos os casos produzem
     exatamente `('F', str)` — **indistinguíveis** no runtime atual.
5. **Como deveria ser representado?** Como um campo `state` explícito do
   resultado da avaliação, separado do `value` (proposta em §18), com um
   rótulo que preserve a origem (`NO_APPLICABLE_RULE` para o Caso A;
   `INVALID_INPUT` para o Caso B).
6. **O estado deve possuir payload?** Sim — no mínimo, o(s) período(s) e/ou
   a(s) entrada(s) que causaram o estado (mesmo padrão já usado por
   `AggregationFailureError.failed_period_ids`, que já existe e funciona).
7. **O valor deve ser `null` quando houver estado especial?** Sim — o
   modelo atual já faz algo equivalente para "indisponibilidade"
   (`VariableNotFoundError`: chave ausente = nenhum valor gravado); a
   proposta estende esse padrão para estados de negócio.
8. **Como um consumidor deve enxergar o resultado?** Deve poder (a)
   detectar explicitamente o estado (`state != VALID`, equivalente ao
   `== "F"` de hoje) e (b) herdar o mesmo estado ao consumi-lo
   implicitamente, SEM que isso aborte a avaliação de ramos independentes
   da árvore de dependências (corrige F-001, ver §9).
9. **Como uma agregação temporal deve tratar isso?** Exatamente como hoje —
   a Política B já implementada (invalidar o agregado do período, listando
   os dias afetados) está correta e não muda (`AggregationFailureError` já
   demonstrado nesta etapa como o comportamento vigente e correto).
10. **Como uma variável independente é afetada?** NÃO deveria ser afetada.
    Hoje É afetada de forma **assimétrica**, dependendo da ordem em que o
    resolvedor de dependências visita os nós — demonstrado com uma fixture
    genérica de dois grupos independentes A e B (`f001_matrix.csv`, Etapa
    2, e `d3_propagation_matrix()`, nesta etapa): quando A="F", o
    dependente exclusivo de B às vezes não é calculado mesmo não
    dependendo de A.
11. **Como um dependente direto é afetado?** Hoje, dois comportamentos
    coexistem para o MESMO tipo de dependência direta, dependendo da forma
    sintática: uma referência simples (`B = A`) repassa `"F"` como valor;
    uma operação aritmética (`C = A + 1`) levanta exceção. Isso é a
    "dupla semântica de propagação" (T-03, Etapa 2), reconfirmada nesta
    etapa com a fixture multi-hop (§9).

---

## 7. State Taxonomy

Ver `evidence/state_taxonomy_matrix.csv` (matriz completa com as 9 colunas
exigidas). Resumo:

| estado candidato | evidenciado? | classificação |
|---|---|---|
| `VALID` | sim (baseline) | não é um "estado especial" — ausência de estado |
| `NO_APPLICABLE_RULE` | **sim** — A41, caso A | estado de resultado genuíno |
| `INVALID_INPUT` | **sim** — A41, caso B + `input_domain_gap()` | estado de resultado genuíno, hoje **sem qualquer tratamento** (nem erro, nem estado — silenciosamente absorvido) |
| `VALIDATION_FAILED` | **sim** — caso de estudo `"ERRO!!!"` (§14) | estado de resultado genuíno, estruturalmente análogo a `NO_APPLICABLE_RULE` mas com semântica distinta (há um valor calculado, rejeitado por uma checagem) |
| `UNAVAILABLE`/`DATA_NOT_YET_READY` | **NÃO** — nenhuma evidência em nenhum dos 5 workbooks nem no código | **NÃO incluído na taxonomia** — `VariableNotFoundError` já cobre "indisponibilidade" como erro técnico; nenhum caso real demonstra necessidade de uma semântica de negócio separada |
| `TECHNICAL_ERROR` | sim (já implementado) | não é estado — é exceção; não deve ser confundido com os três acima |

**INFERÊNCIA:** a taxonomia necessária, com base em evidência (não em
hipótese), tem **3 estados de negócio** além de `VALID`. Introduzir mais
estados sem um quarto caso real observado violaria a regra 32
("não introduzir estados sem evidência").

---

## 8. Special Result Declaration

Como o workbook deve declarar que um resultado é estado, não valor.
Comparação das 3 alternativas do prompt + confirmação do que já existe:

| alternativa | compatibilidade DSL/parser | legibilidade do workbook | capacidade de validação | risco de colisão | impacto em builders | impacto em agregadores |
|---|---|---|---|---|---|---|
| **A — sentinela textual** (`"F"`, e futuramente outro literal por estado) | JÁ funciona — é o mecanismo atual | alta (é só um literal na fórmula, familiar a quem já usa Excel) | nenhuma — o parser não sabe que é um sentinela; é indistinguível de uma string de negócio | **alto** — qualquer categoria de negócio que coincida com o literal reservado colide (P14a) | precisaria manter uma lista fixa de literais reservados e traduzi-los para `state` na tradução builder→ID (reference_resolver já faz tradução de texto→ID; adicionar tradução de literal→state é do mesmo tipo de trabalho) | nenhum — já funciona hoje |
| **B — construto explícito** `STATE(...)` | **viável a baixo custo**: `ast.Call` já é suportado pelo parser, com allowlist por nome/aridade (`ALLOWED_FUNCTIONS`); adicionar `STATE` seguiria o mesmo padrão de `ln` | média — exige que o modelador aprenda uma nova sintaxe, mas é auto-descritiva (não há ambiguidade sobre a intenção) | alta — o parser pode validar estaticamente que o argumento é um dos estados declarados | nenhum — `STATE("NO_APPLICABLE_RULE")` não pode colidir com uma categoria de texto comum | precisaria reconhecer a chamada e traduzir para o campo `state`, sem ambiguidade | nenhum |
| **C — declaração na definição** (`result_states = [...]` na `VariableDefinition`) | não exige mudança de sintaxe da EXPRESSÃO; só metadado da variável | alta para quem já lê a definição da variável (mesmo padrão de `value_type`) — mas a fórmula em si continua usando algum literal, então ainda precisa de A ou B para o CORPO da expressão | alta — permite ao builder validar que todo literal-estado usado na fórmula está na lista declarada | depende de combinar com A ou B | seria um campo adicional na definição, análogo a `value_type`/`allowed_values` (mesma classe de mudança) | nenhum |
| **D — mecanismo já existente** | `AggregationFailureError` já é, de fato, um "estado" representado como exceção com payload (`failed_period_ids`) — é o único precedente de "estado com payload" na plataforma hoje | n/a (é uma exceção interna, não uma sintaxe de workbook) | já validado (é código, não texto livre) | n/a | n/a | é o próprio padrão a generalizar |

**RECOMMENDED CONCEPT:** **C (declaração na definição) combinada com A
(sentinela textual mantido na fórmula, mas agora TRADUZIDO pelo builder a
partir da lista declarada em C)** — preserva 100% de compatibilidade com o
workbook A41 existente (nenhuma mudança na fórmula), resolve a colisão (T-01)
porque o builder só trata como estado os literais que estão na lista
declarada, e generaliza para o caso `"ERRO!!!"` sem exigir sintaxe nova. A
Alternativa B (`STATE(...)`) fica registrada como alternativa
tecnicamente viável (parser já suporta o padrão de `Call`), mas não
recomendada como PRIMEIRA escolha por exigir migração de sintaxe nos
workbooks existentes.

**OPEN DECISION:** a lista exata de literais reservados por variável
(Alternativa C) exige confirmação do modelador de negócio — isso não é uma
lacuna arquitetural, é uma decisão de conteúdo que só o dono do modelo pode
tomar.

---

## 9. State Propagation

Reavaliação formal do F-001 com uma fixture multi-hop NOVA desta etapa
(`d3_propagation_matrix()`), incluindo tipos de consumidor que a Etapa 2
não havia isolado individualmente. Matriz completa em
`evidence/propagation_matrix.csv` (formato `Produtor | Estado | Consumidor |
Comportamento`, como exigido).

Cenário mínimo pedido pelo prompt, com resultado real:

```text
A → "F"                         (estado)
B → valor válido (independente) (VAR95108=5.0)
C depende de A (direto: C=A)
D depende de B (D=B*10)
```

**Resultado observado:** `D` (dependente de B, valor independente) foi
calculado corretamente (`50.0`) — quando não há OUTRO consumidor de A
posicionado antes na ordem de resolução. Mas ao adicionar um consumidor
ARITMÉTICO de A (`C=B+1`, onde B repassa "F"), a rodada inteira aborta
antes de alcançar QUALQUER outro nó, incluindo consumidores que TRATARIAM
o estado corretamente:

- `d3_isolated_comparison_consumer()` (SEM o consumidor aritmético
  concorrente): a comparação `1 if B=="F" else 2` funciona perfeitamente,
  produz `1` — confirma que a detecção explícita de estado NÃO é
  defeituosa em si.
- `d3_propagation_matrix()` (COM o consumidor aritmético presente): a
  mesma comparação nunca é sequer avaliada, porque a exceção do nó
  aritmético aborta o laço do `ForecastEngine` inteiro antes de chegar lá.

**INFERÊNCIA:** o comportamento correto é `A → estado; C(direto) →
estado; B(independente) → valor; D(indireto de B) → valor`, **sem que A
impeça B/D** — e isso já é estruturalmente possível: o `DependencyResolver`
já calcula a ordem topológica completa (é dela que vem a ordem
determinística observada nas 3 execuções embaralhadas do F-001, Etapa 2);
o defeito não está na resolução de dependências, está em `ForecastEngine`
tratar QUALQUER exceção do loop como fatal para TODOS os nós restantes, em
vez de isolar a falha aos descendentes do nó que falhou (que o grafo já
conhece).

Distinção por tipo de consumidor (não todos se comportam igual, confirmando
a instrução de não assumir uniformidade):

| tipo de consumidor | comportamento quando ALCANÇADO (isolado) | comportamento hoje quando outro consumidor aritmético aborta primeiro |
|---|---|---|
| referência direta / passthrough | repassa o estado como valor | nunca é alcançado |
| aritmético | levanta exceção corretamente (impede número inválido) | é frequentemente o que CAUSA o abort |
| comparação (`==`/`!=` contra o estado) | detecta corretamente, retorna bool | nunca é alcançado se um aritmético já abortou antes |
| comparação numérica (`>`, `<`) contra estado | levantaria erro de tipo corretamente | nunca é alcançado |
| agregador temporal | invalida corretamente o agregado (Política B) | não é afetado pelo F-001 do MESMO dia (é uma janela de dias, não de nós do grafo) |

**RECOMENDAÇÃO:** a propagação deve seguir a alcançabilidade no
`DependencyGraph` (já calculada), não a ordem sequencial de um loop plano:
um nó cujo caminho de dependência não passa por um estado-produtor deve
ser calculado independentemente do resultado desse produtor.

---

## 10. State Aggregation

Distinção crítica confirmada nesta etapa
(`d4_spatial_vs_temporal_aggregation()`): a plataforma tem **um único**
mecanismo real de agregação — o **temporal** (`AggregationRule`/
`TemporalAggregationService`, com `SUM`/`AVERAGE`/`WEIGHTED_AVERAGE`/
`MOVING_AVERAGE`). O que o prompt chama de "agregação espacial" (grupo,
linha, total) **não existe como mecanismo distinto** — no A41 real,
`retirada_condensado_total@L1_L7 (diário)` é uma `EquationDefinition`
comum somando três referências `@grupo`, sujeita às MESMAS regras de
propagação do §9, não a uma política de agregação separada.

Isso significa que só existe UMA política de agregação a fechar (temporal),
já demonstrada com o exemplo exato pedido pelo prompt:

```text
Dia 1 → 100
Dia 2 → 110
Dia 3 → estado especial ("F")
AVERAGE
```

Comparação das 4 políticas (`evidence/aggregation_matrix.csv`):

| política | resultado do exemplo | risco de ocultar dados | é a política atual? |
|---|---|---|---|
| A — ignorar estados | `AVERAGE(100,110)=105` | **ALTO** — indistinguível de um mês perfeito | **NÃO** — código rejeita explicitamente (docstring) |
| **B — invalidar o agregado** | `state=NO_APPLICABLE_RULE, detail={dia 3}` | **BAIXO** | **SIM**, confirmado por leitura de `_require_numeric_series` |
| C — parcial sinalizado | `value=105, state=PARTIAL, detail={dia 3}` | MÉDIO | não; sem evidência de necessidade em nenhum workbook |
| D — erro técnico interrompe antes | n/a (categoria diferente: falha de leitura, não estado de negócio) | n/a | sim, para essa categoria diferente |

**DECISÃO:** manter a Política B — já correta, já transversal (o serviço
não tem lógica por bloco), e sem nenhuma evidência (em nenhum dos 5
workbooks) que justifique C. Isso NÃO muda na Etapa 3: só a REPRESENTAÇÃO
do estado (de texto "F" para campo `state` estruturado) muda; a política em
si permanece.

---

## 11. Allowed Categories

`hes_l4..l7`: domínio confirmado (`evidence/category_contract_matrix.csv`,
8 perguntas respondidas):

- **5 categorias**, extraídas por varredura de TODAS as comparações no
  workbook: `Normal`, `LC`, `Overhaul/Parada`, `1 By pass`, `1 By pass e LC`.
- **Quem declara hoje:** ninguém, estruturalmente — o domínio só existe
  implícito, espalhado nos literais de cada fórmula consumidora.
- **Entrada desconhecida é erro?** Não — `input_domain_gap()` confirma que
  `"Overhaul"` (typo) e `"qualquer_coisa_arbitraria"` são aceitos sem
  exceção, porque não existe nenhum conjunto contra o qual validar.
- **`"F"` como categoria:** colidiria com o sentinela de estado (P14a,
  Etapa 2) — resolvido automaticamente se o estado deixar de ocupar o
  canal de valor/categoria.

**value_type = categorical COM allowed_values, opcional:** sim, deve ser
suportado. Sem essa peça, `INVALID_INPUT` (§7) não é sequer detectável —
não é uma preferência de design, é uma dependência lógica: não se pode
distinguir "combinação válida sem regra" de "entrada fora do domínio" sem
primeiro saber qual é o domínio.

`allowed_values` **não deve ser confundido com `result_state`**: um é o
domínio de valores de NEGÓCIO válidos (`Normal`, `LC`, ...); o outro é o
canal de estados de AVALIAÇÃO (`NO_APPLICABLE_RULE`, ...). Mantidos como
dois conceitos distintos na proposta (§18).

---

## 12. `value_type` Contract

**Reconfirmado, não reaberto** (decisão já fechada na Etapa 2): `value_type
∈ {numeric, categorical}`, declarado pelo modelador na `VariableDefinition`,
com padrão `numeric`. `mixed` continua **NOT REQUIRED** — nenhuma evidência
nova nesta etapa sugere o contrário; ao contrário, tanto o caso A41 quanto o
caso `"ERRO!!!"` são resolvidos por `result_state` SEPARADO de `value_type`,
reforçando que `mixed` seria a solução errada (confundiria tipo com estado).

`value_type` permanece **declarativo**, nunca inferido dinamicamente: mesmo
quando `retirada_condensado_grupo` produz `"F"` em runtime, sua declaração
continua `numeric` — o texto produzido não promove nem realoca o tipo
declarado da variável. Isso é precisamente o que torna a distinção
valor/estado necessária: se o runtime "promovesse" o tipo para acomodar o
resultado observado, estaríamos reintroduzindo `mixed` por trás — a
proposta em §18 EVITA isso ao manter `value_type` como contrato do valor
quando `state=VALID`, nunca como um resumo de "tudo que já saiu dali".

**Matriz completa:** `evidence/value_type_state_matrix.csv`.

---

## 13. State vs Exception

Fronteira objetiva, com evidência de cada linha (`evidence/state_error_matrix.csv`):

| situação | value | state | exception | evidência |
|---|---|---|---|---|
| cálculo válido | sim | VALID | não | `evaluate('2+3')=5.0` |
| nenhuma regra aplicável | não | **NO_APPLICABLE_RULE** | não | `d1_1...` caso A |
| categoria inválida | sim (hoje, incorretamente) | deveria ser **INVALID_INPUT** | não (nenhuma validação existe) | `input_domain_gap()` |
| `ln(-10)` | não | não | **sim** (`MathDomainError`) | `d6_d7_boundary_probes()` |
| variável inexistente | não | não | **sim** (`VariableNotFoundError`) | idem |
| divisão por zero | não | não | **sim** (`DivisionByZeroError`) | idem |
| consumo aritmético de `"F"` | não | deveria continuar sendo estado propagado | **sim, hoje** (`ConditionalFailureError`) — mistura estado com erro técnico | P08 (Etapa 2), T-04 |
| `"ERRO!!!"` (padrão futuro) | depende do `value_type` (não deveria) | deveria ser **VALIDATION_FAILED** | sim, só se `numeric` e o ramo executar | `erro_case_study()` |

**INFERÊNCIA:** a fronteira lógica é clara (falha do MODELO DE NEGÓCIO =
estado; falha do MOTOR DE CÁLCULO = exceção), mas a IMPLEMENTAÇÃO atual
viola essa fronteira num ponto específico: consumir um estado hoje produz
uma exceção (`ConditionalFailureError`), tratando uma condição de negócio
esperada como se fosse uma falha técnica. Essa é a raiz tanto de T-03
quanto de F-001/T-02.

---

## 14. Workbook Evidence

### A41 (caso principal — ver §6)

Confirmado: fórmula real, 5 categorias, 2 origens distintas de `"F"`
demonstradas lado a lado.

### Segundo caso de estudo — `"ERRO!!!"`

Fórmula original:

```excel
=SE(ARRED(D595-D601-D616;10)>ARRED(D61;10);"ERRO!!!";D595-D601-D616)
```

**FATO OBSERVADO:** `ARRED` (ROUND) não existe na allowlist de funções do
parser atual (só `ln`) — fato estrutural preexistente, não avaliado como
mudança nesta etapa. O padrão conceitual equivalente, dentro da DSL já
suportada, foi testado como:

```text
saldo if saldo <= limite else "ERRO!!!"
```

**Resultado testado em DUAS declarações (`erro_case_study()`):**

1. **Destino `numeric`:** ramo não executado (`saldo=3, limite=10`) →
   aceito silenciosamente como `3.0`. Ramo executado (`saldo=15,
   limite=10`) → `"ERRO!!!"` REJEITADO pelo storage
   (`CalculationValueError`) — idêntico ao padrão P05a/P05b da Etapa 2.
2. **Destino `categorical`:** o padrão INVERTE-SE. Agora é o ramo NUMÉRICO
   que é aceito sem checagem (categorical aceita número OU texto — a
   ordem de checagem em `_validate_variable_value` testa `is_numeric()`
   antes de `is_categorical`), e `"ERRO!!!"` é aceito como se fosse uma
   categoria de domínio legítima, tão válida quanto `"Normal"`.

**INFERÊNCIA:** em NENHUMA declaração de `value_type` existe hoje uma forma
de expressar "este ramo textual é uma falha de validação, não um valor nem
uma categoria de negócio". O padrão é **estruturalmente idêntico** ao
padrão A41 (`SE(cond;valor;"F")` vs `SE(cond;"ERRO!!!";valor)` — mesma
forma, ramos trocados) e exige a MESMA solução (`result_state`), não um
mecanismo específico — confirmando a generalização transversal (§15).

### Demais blocos (yield, production, energy, max_ht)

**FATO OBSERVADO**, reconfirmado por leitura dos artefatos já produzidos na
Etapa 2 (varredura de literais textuais e `IF`/`SE` nos 5 workbooks,
`audit/stage2_typing_contract/REPORT.md` §13): yield e max_ht têm ZERO
literais textuais em fórmulas; production e energy têm 1 `IF` cada, com
AMBOS os ramos numéricos (nenhum ramo textual). Nenhum desses blocos produz
hoje qualquer resultado heterogêneo. Isso significa que a proposta em §18
é um **no-op** para eles — nenhuma migração é exigida, confirmando que a
solução não foi desenhada em função do A41.

Nenhuma observação (`OBS`) de nenhum workbook foi usada como evidência de
contrato nesta seção, conforme a regra 17.

---

## 15. `mixed` Analysis

Não reaberto como decisão (Etapa 2 já concluiu `NOT REQUIRED`), mas
REVALIDADO com a evidência nova: tanto o padrão A41 (`"F"`) quanto o
padrão `"ERRO!!!"` (§14) são resolvidos por `result_state`, SEM exigir que
a variável destino aceite "múltiplos tipos de valor legítimos
simultaneamente". A pergunta correta do prompt (§29) — existe algum caso
em que uma variável possua LEGITIMAMENTE múltiplos tipos de valor VÁLIDO
(não estado) simultâneos? — **não tem nenhuma evidência afirmativa** em
nenhum dos 5 workbooks nem no segundo caso de estudo. `mixed` permanece:

```text
mixed = NOT REQUIRED
```

---

## 16. Conceptual Scenario Matrix

C01-C16, com evidência específica para cada linha (`evidence/scenario_matrix.csv`):

| id | cenário | status |
|---|---|---|
| C01 | numeric + valor válido | SUPPORTED |
| C02 | categorical + categoria válida | SUPPORTED |
| C03 | numeric + estado especial | SUPPORTED (mas indistinguível de valor no canal) |
| C04 | categorical + estado especial | AMBIGUOUS (colisão) |
| C05 | categorical + categoria inválida | UNSUPPORTED (não detectado) |
| C06 | numeric + string inesperada | SUPPORTED se o ramo executa; UNSUPPORTED (latente) se não |
| C07 | technical exception | SUPPORTED |
| C08 | estado em A + B independente | UNSUPPORTED (F-001) |
| C09 | estado + consumidor direto | SUPPORTED (repassa como valor) |
| C10 | estado + consumidor indireto | PARTIALLY SUPPORTED (correto isoladamente; abortado se concorrente) |
| C11 | estado + AVERAGE temporal | SUPPORTED |
| C12 | estado + "agregação espacial" | N/A (não existe o mecanismo; ver §10) |
| C13 | estado + total | UNSUPPORTED (mesma classe de C10) |
| C14 | categoria "F" legítima | UNSUPPORTED (colisão) |
| C15 | "F" como estado reservado (uso atual) | SUPPORTED operacionalmente, mal modelado |
| C16 | "ERRO!!!" como saída futura | UNSUPPORTED como conceito distinto hoje |

---

## 17. Open Decisions

Questões genuinamente em aberto — não inventadas para fechar o gate:

1. **Mecanismo exato de declaração de estado no workbook** (§8): recomendei
   C+A, mas a lista exata de literais reservados por variável é decisão de
   conteúdo do modelador, não arquitetural.
2. **Rótulo/label de cada estado específico** por variável de negócio (ex.:
   confirmar se `"F"` do A41 deve virar `NO_APPLICABLE_RULE` no rótulo, ou
   outro nome de domínio) — decisão de nomenclatura de negócio.
3. **Política de propagação de ERRO TÉCNICO** (distinta da política de
   ESTADO, que é fechada: isolar aos descendentes): um erro técnico
   (`MathDomainError` etc.) deve continuar abortando a rodada inteira, ou
   deveria também ser isolado ao nó/descendentes? Isso é uma decisão
   operacional (tolerância a falha parcial do motor) fora do escopo desta
   auditoria conceitual.
4. **`UNAVAILABLE`/dado ainda não disponível**: explicitamente NÃO incluído
   na taxonomia por falta de evidência — se um caso real surgir em um
   bloco futuro, deve ser reavaliado então, não antecipado agora.

Nenhuma dessas 4 questões é uma AMBIGUIDADE CRÍTICA que impeça a Etapa 3 de
avançar sobre o restante do contrato (por isso o gate é `CLOSED WITH OPEN
ITEMS`, não `NOT CLOSED`) — são decisões de CONTEÚDO/POLÍTICA, não de
ARQUITETURA.

---

## 18. Proposed Contract

> PROPOSTA CONCEITUAL — não implementada nesta etapa.

```text
VariableDefinition
  name
  frequency
  scope
  variable_type
  value_type              (numeric | categorical — inalterado, Etapa 2)
  allowed_values           (opcional; só categorical; domínio de categorias
                             de NEGÓCIO — nunca inclui rótulos de estado)
  formula
  declared_result_states   (opcional; lista de rótulos de estado que esta
                             variável pode produzir, ex.: [NO_APPLICABLE_RULE])

EvaluationResult  (por instância x período)
  value            (presente sse state == VALID; tipo = value_type)
  result_state     (VALID | um dos declared_result_states da variável)
  detail           (opcional: rótulo de origem, períodos afetados — mesmo
                     padrão já usado por AggregationFailureError.failed_period_ids)

TechnicalError    (permanece exceção — NUNCA um valor gravável)
  exception_type
  message
  context
```

Responsabilidade por componente: `evidence/responsibility_matrix.csv`
(4 contratos × 6 componentes). Resumo: o workbook/modelador DECLARA
(`value_type`, `allowed_values`, `declared_result_states`); o builder
TRADUZ (literal do workbook → `state`) e pode VALIDAR estaticamente; o
parser continua agnóstico de `value_type`/`state` (só valida sintaxe); o
evaluator PROPAGA estado como dado aos descendentes em vez de lançar
exceção ao consumi-lo; o engine decide a política de propagação (isolar,
não abortar globalmente); o storage grava `(value, state)` em vez de só
`value`; o agregador mantém a Política B já correta, só trocando a
checagem de "é o texto F" por "state != VALID".

---

## 19. Stage 3 Impact

Reconfirmado desta etapa (sem mudança da estimativa da Etapa 2, já que
nenhuma decisão nova exige mecanismos adicionais além dos já mapeados):
builders, validators, evaluator, engine, storage e agregação são afetados;
não existe persistência/API de resultados hoje (custo de migração externa
zero); 21 itens de teste do contrato `"F"` mudam de "exceção" para "estado"
(`tests/test_dsl_structural_contracts.py`, 12 funções — contado na Etapa
2). Nenhuma alteração foi feita nesta etapa a esse número.

**Item NOVO desta etapa:** a introdução de `allowed_values` teria impacto
adicional em `CalculationContext._validate_variable_value` (checagem contra
o domínio) e nos builders (validação estática de que os literais usados nas
fórmulas consumidoras pertencem ao domínio declarado) — mapeado em
`evidence/category_contract_matrix.csv`.

---

## 20. Final Gate

### Auto-crítica (regra 31) — respostas registradas

1. Decisão tomada só para facilitar implementação? **Não** — `UNAVAILABLE`
   foi explicitamente EXCLUÍDO por falta de evidência, mesmo sendo mais
   simples incluí-lo "por precaução".
2. Estado criado sem evidência? **Não** — os 3 estados propostos têm probe
   dedicado cada um; `UNAVAILABLE` foi rejeitado.
3. Erro técnico confundido com estado de negócio? **Não** nesta proposta —
   é precisamente o defeito ATUAL que a proposta corrige (§13).
4. Estado confundido com valor? **Não** — é o defeito atual (`"F"` no
   canal de valor); a proposta separa os dois.
5. `mixed` usado como atalho? **Não** — revalidado como NOT REQUIRED (§15).
6. Solução depende de A41? **Não** — `result_state`/`allowed_values` são
   genéricos; testados também contra um segundo caso de estudo
   independente (`"ERRO!!!"`).
7-10. Funcionaria para yield/production/energy/max_ht? **Sim, como no-op**
   — nenhum desses blocos produz hoje resultado heterogêneo (§14);
   nenhuma mudança seria exigida neles.
11. Funcionaria para `"ERRO!!!"`? **Sim**, demonstrado concretamente
   (§14, `erro_case_study()`).
12. Agregação definida sem considerar temporal × espacial? **Não** — a
   distinção foi feita explicitamente (§10): só existe agregação temporal
   real; "espacial" é propagação comum (§9).
13. Propagação depende da ordem de execução? **Sim, HOJE** (é o próprio
   F-001, T-02) — a proposta corrige isso ao basear a propagação na
   alcançabilidade do grafo, não na ordem sequencial do loop.
14. Workbook continua sendo a fonte declarativa? **Sim** — a proposta só
   adiciona metadados opcionais à definição; não move lógica para fora do
   workbook.
15. Runtime infere semântica que deveria ser declarada? **Não** — a
   proposta EXIGE declaração (`declared_result_states`,
   `allowed_values`); não introduz inferência dinâmica de tipo.
16. Decisão essencial escondida como "detalhe de implementação"? Revisado:
   as únicas questões deixadas para depois são de CONTEÚDO (§17), não de
   arquitetura — nenhuma decisão estrutural foi adiada.

### Critérios de sucesso (§22 do prompt)

| critério | resposta objetiva |
|---|---|
| Quais estados existem? | `NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED` (evidenciados); `UNAVAILABLE` explicitamente não incluído |
| Como uma fórmula declara estado vs valor? | Recomendação C+A (§8); mecanismo exato = OPEN DECISION de conteúdo |
| Até onde o estado se propaga? | Aos descendentes no grafo de dependências, nunca lateralmente a nós independentes (proposta corrige F-001) |
| Como cada agregação trata um estado? | Só existe agregação temporal real; Política B (invalidar, listar períodos) — já correta, mantida |
| Como uma categórica declara seus valores válidos? | `allowed_values` (opcional, proposto) — necessário para detectar `INVALID_INPUT` |
| Como o sistema distingue estado de erro técnico? | Fronteira lógica definida (§13); hoje violada num ponto (consumo de "F" vira exceção); proposta corrige |
| Como `value_type` permanece independente do estado? | `value_type` descreve o valor QUANDO `state=VALID`; nunca promovido/inferido dinamicamente (§12) |
| Qual componente é responsável por cada decisão? | `evidence/responsibility_matrix.csv`, 4 contratos × 6 componentes |

### Gate

```text
CONTRACT CLOSED WITH OPEN ITEMS
```

Todas as decisões ARQUITETURAIS estão fechadas com evidência. As 4 questões
de §17 são decisões de CONTEÚDO/POLÍTICA de negócio (rótulos exatos,
mecanismo sintático final de declaração, tolerância a erro técnico) que
legitimamente pertencem ao dono do modelo ou à implementação detalhada da
Etapa 3 — não representam ambiguidade arquitetural crítica.

**Confirmação explícita:** nenhum arquivo de produção, seed, workbook ou
teste existente foi alterado nesta etapa. `git status --short` mostra
apenas o diretório novo `audit/stage2_1_result_state_contract/` como não
rastreado; a suíte de testes permanece em 1414 passed / 0 failed (idêntica
ao baseline).
