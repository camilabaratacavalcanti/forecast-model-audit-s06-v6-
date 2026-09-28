# Etapa 2.5B — Fechamento contratual (area_41 e workbooks relacionados)

Esta etapa é só de auditoria. **Não alterei** workbooks, builders, readers, domínio, validators, resolver,
runtime, seeds oficiais nem testes: `git status` mostra apenas `audit/stage2_5b_contract_decision/`. Os builders
rodaram em memória e a validação com os candidatos usou uma cópia temporária dos seeds, apagada ao final.

Tudo é reexecutável a partir da raiz do repositório:

```
python audit/stage2_5b_contract_decision/evidence/analysis_stage2_5b.py
```

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD | `e6351a3` (Stage 2.5, READY_FOR_DECISION), sobre `6b135e9` (Stage 2.4 R2, PASS) |
| árvore | limpa no início |
| suíte existente | 1409 passed (seeds oficiais inalterados) |
| artefatos da 2.5 lidos | REPORT_stage2_5, contract_decisions, cross_workbook, identity_repeats_cross_block, variable_value_inventory, unreachable_reference_inventory |

O prompt cita `audit/stage2_5_contract_decision/`, mas a pasta da Stage 2.5 no repositório é
`audit/stage2_5_contract_closure/`. Usei essa.

## 2. Workbooks analisados

| bloco | versão | origem | estado |
|---|---|---|---|
| area_41 | v8 | `data/workbooks/` | aprovado na 2.4 |
| energy | v5 | `data/workbooks/` | aprovado na 2.4 |
| max_ht | v9 | `data/workbooks/` | aprovado na 2.4 |
| production | **v8** | `evidence/inputs/` (cópia byte a byte do upload) | candidato corrigido pelo dono (D25-02) |
| yield | **v10** | `evidence/inputs/` (cópia byte a byte do upload) | candidato corrigido pelo dono (D24-12) |

Números com os cinco workbooks: 572 linhas semânticas, 238 equações e 207 agregações, iguais aos da 2.4 e da 2.5.
Detalhe por bloco em `evidence/workbook_integrity.csv`.

## 3. Hashes

| workbook | SHA-256 |
|---|---|
| A41 v8 | `be2372b4f4f35f5aea720dcc00c680f3e47e359138995dd35a6dcabd3d603528` (= 2.4) |
| energy v5 | `34c1c88af318e57026c08c21fd2a1cf308258e575eddbb11d98ba0bba6878047` (= 2.4) |
| MaxHT v9 | `74d5cbb7624d5c7101b5f25ecd76e156c9d019968c7e5f9af2ed04aa50b27004` (= 2.4) |
| production v8 | `3c8b8ce45d82d68106623dea0db33b4acd1ffc626f966192d8b822a02e949ca6` |
| yield v10 | `4948da7f86aa2a2cb6a7e7fb4d7fdabe9896afae3af6109fd6eb4c572089b0a8` |

Comparei célula a célula com as versões anteriores (`evidence/workbook_diffs.csv`). As mudanças são exatamente
as descritas pelo dono, e nenhuma outra célula mudou:

| transição | células alteradas | mudança |
|---|---|---|
| production v7 → v8 | 5 | D48–D49 (`oee`) e D50–D52 (`oee_total`): unit `%` → `-` |
| yield v9 → v10 | 2 | E92 (`value` 273 → vazio) e F92 (`version` 1 → vazio) em `ltp_tc` |

A correção da R2-01 (P25 = `consumo_mpsa_grupo`) continua presente no v8.

Montando em memória com os candidatos:

| verificação | resultado |
|---|---|
| builder nos cinco workbooks | ok |
| decisões pendentes nos manifestos | 0 (sai a D24-12, a R2-01 já tinha saído) |
| validators oficiais | 0 erros (27 avisos de repetição entre blocos; ver D25-01) |
| RegistryIntegrityValidator | OK |
| referências das 238 equações | 1436, das quais 1417 DIRECT, 16 com fallback temporal para período mais amplo (válido), 3 com escopo espacial pai (válido) e **0 inalcançáveis** (`evidence/reference_inventory.csv`) |

## 4. Decisões anteriores

| id | estado recebido | tratamento nesta etapa |
|---|---|---|
| R2-01 | RESOLVED_IN_SOURCE_WORKBOOK (2.5) | mantida no v8 |
| D25-02 | decidida pelo dono (unit `-`) | verificada como regra |
| D24-12 | decidida pelo dono (value/version só em parameter) | verificada como regra |
| D25-01, D25-03, D25-04, D24-11 | abertas na 2.5 | fechadas abaixo |

## 5. D25-01 — Identidade calculada em mais de um bloco

**Evidência** (`cross_workbook_evidence.csv`): 19 identidades aparecem em mais de um bloco (as 18 variáveis da 2.5 mais `lth_meta`, que envolve um parâmetro).

| classe | identidades | leitura |
|---|---:|---|
| mesma identidade, mesma frequência e escopo, calculada em 2–3 blocos com **fórmula textualmente idêntica** | 9: `lth` mensal (max_ht, production, yield); `lth_grupo` diário L1_L3, L4_L5, L6_L7 (area_41, yield); `lth_total` anual e mensal; `oee` mensal; `oee_total` mensal; `producao` mensal | cálculo local sobre a cópia local da variável-base; não é conflito |
| mesma identidade calculada com **fórmulas diferentes** | 2: `lth_total` diário (soma simples em max_ht e production × média ponderada por `oee` em yield); `oee_total` diário (ponderado por `lth_meta` em production × por `ltp_lth` em yield) | semanticamente são **variáveis distintas** em cada contexto; um namespace global as fundiria erradamente |
| entrada local de identidade calculada em outro bloco | 7 (`lth`, `pick_up`, `pick_up_total` diário e mensal, `producao` diário, `yield` diário, `oee` diário) | consumidor com cópia local de entrada |

Esses 7 mais `lth_meta` (parâmetro em production, entrada em energy) completam as 19.

**Decisão (regra implementável):**

| regra | enunciado |
|---|---|
| I1 | **Identidade é local ao bloco**: (bloco, name, frequency, scope_type, scope_value). Não existe namespace global: os dados mostram identidades homônimas com semântica diferente (duas fórmulas distintas) |
| I2 | **Unicidade** é obrigatória somente dentro do bloco, por instância concreta. É erro (já implementado no builder e nos validators) |
| I3 | **Definições locais independentes** com o mesmo name, frequency e escopo em blocos diferentes são **permitidas**. São definições distintas, com IDs distintos, mesmo quando a fórmula é idêntica |
| I4 | **Múltiplos produtores** só existem (a) dentro de um bloco, o que já é erro, ou (b) quando um vínculo `source_block` encontra mais de uma definição no bloco produtor, o que é erro; por I2 isso não acontece em workbook válido |
| I5 | A repetição entre blocos **não é violação nem aviso contratual**. Hoje o validator emite 27 avisos D24-11 para isso; a implementação passa a tratá-la como relatório informativo, sem erro e sem aviso de contrato |
| I6 | `source_block` **não é obrigatório** para identidades repetidas. Só existe quando o engenheiro do workbook declara um vínculo (D24-11) |

**Testes:** duas definições iguais em blocos diferentes = válido; duas no mesmo bloco = erro; nenhum aviso
contratual para repetição entre blocos; o inventário informativo lista as 19 identidades.

## 6. D25-02 — `oee` / `oee_total` (regra confirmada)

**Regra:** `oee` e `oee_total` têm unidade canônica `-`. Declarar a unidade correta cabe ao engenheiro do
workbook. A infraestrutura transporta, valida e rejeita divergências contratuais. Ela **nunca** corrige nem
converte, e `%` e `-` não são equivalentes.

**Verificação** (`unit_evidence.csv`):

| # | ponto | resultado |
|---|---|---|
| 1 | production v8 | `oee` diário e mensal e `oee_total` diário, mensal e anual (r48–r52) = `-` |
| 2 | yield v10 | `oee` diário e mensal e `oee_total` diário e mensal (r122, r123, r127, r131) = `-` |
| 3 | produtores e consumidores | as 9 linhas `oee`/`oee_total` = `-`. As 19 identidades repetidas entre blocos têm a mesma unidade em todos os blocos (0 divergências) |
| 4 | ocorrências conflitantes | **0 CONTRACT_VIOLATION** |
| 5 | conversão implícita de escala | os consumidores de `oee` (yield r37 `lth_total`, r124–r126 `oee_grupo`, r127 `oee_total`; production r50 `oee_total`) usam `oee` só como fator ou peso, sem `*100` nem `/100`; `app/domain/units.py` só trata base temporal de SUM (h/d), sem conversão `%` ↔ `-` |

**Impacto na implementação:** validar igualdade de `unit` em todo vínculo `source_block` (L8). Não criar tabela de
conversão.

## 7. D25-03 — `fonte` × produtor/dependência

**Evidência:**
- `area_41` r9 `lth` declara fonte "bloco yield"; `yield` r32 `lth` é `entrada` com fonte "bloco production".
- 34 linhas têm fonte: 13 citam um dos cinco blocos e 21 citam blocos fora da plataforma (maintenance,
  maintenance_plan, forecast, temperature_lp, alumina, area_04_13).

A fonte descreve origem conceitual. Ela não é um apontamento operacional verificável: pode citar um intermediário
(yield, no caso da A41) ou um bloco inexistente na plataforma.

**Decisão:** `fonte` é **proveniência documental** (texto livre sobre a origem conceitual da informação).

```
fonte NÃO cria dependency graph
fonte NÃO determina producer
fonte NÃO substitui source_block
fonte NÃO é mecanismo de resolução no build nem no runtime
```

A infraestrutura transporta `fonte` sem interpretá-la: não faz parse, não valida o bloco citado e não infere
vínculo. O caso area_41 → yield → production **não é violação**.

**Testes:** alterar o texto de `fonte` não muda nenhum vínculo, dependência ou resultado; nenhum código lê `fonte`
para resolver nada.

## 8. D25-04 — `fonte` × `variable_type`

**Evidência** (`evidence/fonte_inventory.csv`): das 34 linhas com fonte, 31 são `entrada`. As outras 3:

| linha | variable_type | fonte |
|---|---|---|
| energy r37 `evaporado_total_evaporacao` | `entrada_externa` | "bloco area_04_13 (Forecast A4 e A13)" |
| production r30 `fator_mpsa` | `calculado` | "bloco forecast" |
| production r32 `fator_mrn` | `calculado` | "bloco forecast" |

**Decisão:** `fonte` e `variable_type` são **dimensões independentes**. A presença de `fonte` não determina
`variable_type`, e `variable_type` não exige nem proíbe `fonte`. As três linhas acima são válidas e não há
exceções a documentar. A única regra que liga natureza da linha e vínculo é sobre `source_block` (L4), nunca sobre
`fonte`.

**Testes:** workbook com fonte em `calculado` e em `entrada_externa` é aceito; nenhuma validação cruza os dois
campos.

## 9. D24-11 — Ligação entre workbooks

**É a solução adequada?** Sim, como mecanismo **opcional e único**:
- identidade local (D25-01) implica que nada liga blocos implicitamente;
- `fonte` é documental (D25-03);
- sem um campo explícito, a dependência de runtime entre blocos simplesmente não pode ser declarada.

A alternativa "nenhuma ligação; o orquestrador injeta entradas" continua sendo o comportamento quando
`source_block` estiver ausente, então as duas convivem.

Especificação normativa (não implementada nesta etapa):

| norma | regra |
|---|---|
| L1 — semântica | `source_block = B` numa linha do workbook consumidor declara: "o valor desta definição, em cada instância e período, é o valor da definição de mesma identidade no bloco B". **Não significa**: cópia de fórmula, conversão, alias de nome, herança de metadados ou relação documental (essa é a `fonte`) |
| L2 — opcional | a coluna é opcional; ausente ou vazia = definição local sem vínculo (o estado de todos os workbooks atuais, que continuam válidos) |
| L3 — valores | `source_block` ∈ blocos da plataforma (os cinco hoje) e ≠ o próprio bloco. Bloco inexistente ou o próprio bloco = erro |
| L4 — onde pode aparecer | somente em `Type=variable` (sem expressão, sem agregação). Em `parameter` ou `variable / equation` = erro (a definição teria dois produtores) |
| L5 — resolução | produtor = definição no bloco B com o mesmo name, frequency, scope_type e scope_value do consumidor. Não há renomeação (`source_name` não é adotado) |
| L6 — existência / ambiguidade | nenhuma definição = erro "produtor inexistente"; mais de uma = erro "produtor ambíguo" (impossível num bloco válido por I2, mas verificado) |
| L7 — tipo | o produtor tem de ser `variable` (calculada, agregada ou entrada). Produtor `parameter` = erro (ex.: energy `lth_meta` × production `lth_meta` **não é vinculável** como está; se o dono quiser o vínculo, precisa remodelar) |
| L8 — compatibilidade | unit, value_type e allowed_values iguais; frequency, scope_type e scope_value iguais (é a própria chave de L5); conjunto de instâncias do consumidor = o do produtor. Qualquer diferença = erro nomeado. **Sem conversão** |
| L9 — cadeia | se o produtor for, ele mesmo, uma definição com `source_block`, a resolução segue a cadeia até a definição terminal, que é o produtor efetivo. Uma entrada sem vínculo no fim da cadeia é aceita (é entrada daquele bloco) |
| L10 — ciclos | grafo com nós = (bloco, definição) e arestas = vínculos + dependências de equação e agregação intra-bloco. Um ciclo que atravessa blocos = erro no build |
| L11 — momento | a resolução e todas as validações ocorrem **no build** (cross-build depois dos modelos canônicos de todos os blocos). O resultado é uma tabela de vínculos versionada no seed |
| L12 — fallback temporal | um vínculo exige frequency igual (L8). As referências de **expressão** continuam regidas pela A019: consumidor diário lendo definição mensal ou anual do próprio bloco segue válido (os 16 casos da 2.5, `reference_inventory.csv`). Um vínculo não cria nem remove fallback |
| L13 — fallback espacial | um vínculo exige escopo igual. A resolução por escopo pai (Decision E, os 3 casos válidos) continua valendo só nas referências de expressão dentro do bloco |
| L14 — `fonte` | **não participa** de L1–L13 e nunca é usada para preencher `source_block` |

Runtime (implementação da Etapa 3): o orquestrador executa o produtor efetivo antes do consumidor e disponibiliza
o valor sob o ID do consumidor, por instância e período. Sem valor, erro explícito; nenhum default.

**Estado atual dos workbooks:** nenhum declara `source_block`, então as 13 relações descritas por `fonte`
continuam como entradas locais válidas. Transformá-las em vínculos é decisão e manutenção do dono do workbook
(preencher a coluna), nunca inferência do implementador.

**Testes:** um teste por regra L3–L10 com mensagem nomeada; um workbook sem a coluna gera seeds idênticos aos
atuais; um vínculo válido produz a tabela; a cadeia A → B → C é resolvida; um ciclo é rejeitado; alterar `fonte` não
muda vínculos.

## 10. D24-12 — `value` / `version` (regra confirmada)

**Regra:**

| Type | value / version |
|---|---|
| `parameter` | pode ter (e hoje exige valor numérico físico) |
| `variable` | **proibido** |
| `variable / equation`, inclusive as linhas de agregação | **proibido** |

A planilha não tem um `Type=aggregation` literal: agregações são linhas `variable / equation` com expressão de
agregação, e a regra se aplica a elas.

**Verificação** (`value_version_evidence.csv`): nos cinco workbooks há 40 linhas com value ou version, **todas
parameter**. Há 0 em `variable` e 0 em agregação. A antiga yield r92 (`ltp_tc`) está limpa no v10.

**Impacto na implementação:**
- builder: substituir o registro pendente D24-12 do manifesto por erro de contrato;
- validator: já rejeita `value`/`version` em registro de variável (campos desconhecidos);
- testes: T24-16 passa a exigir rejeição.

## 11. Regras de responsabilidade

| engenheiro do workbook / modelo | infraestrutura |
|---|---|
| semântica do modelo, fórmulas, tipos, escopos, frequências | parsing e canonicalização determinísticos |
| unidades corretas e coerentes entre produtor e consumidor (ex.: `oee` = `-`) | transporte fiel de todos os metadados (unit, value_type, allowed_values, declared_result_states, fonte) |
| declarar `source_block` quando quiser um vínculo; manter `fonte` como documentação | validação do contrato e resolução estritamente conforme as regras (A019, L1–L14) |
| corrigir o workbook quando a validação apontar violação | detectar e **rejeitar** violações com erro nomeado; construir o modelo de forma determinística |

A infraestrutura **não**:
- corrige workbook, fórmula ou metadado;
- infere intenção (ex.: vínculo a partir de `fonte`);
- converte unidade ou escala sem regra contratual explícita;
- escolhe produtor quando houver ambiguidade.

Workbook incorreto → validação → **CONTRACT_VIOLATION**, nunca correção silenciosa.

## 12. Inconsistências encontradas

**Nenhuma CONTRACT_VIOLATION** nos cinco workbooks para as regras fechadas:

| regra | violações |
|---|---:|
| value/version fora de parameter | 0 |
| `oee`/`oee_total` com unit ≠ `-` | 0 |
| unidade divergente em identidades repetidas | 0 |
| referências inalcançáveis | 0 |
| identidade duplicada dentro de um bloco | 0 |

**LEGACY_TEST_EXPECTATION.** São testes que passam hoje, porque os seeds oficiais ainda são production v6 e yield
v9, mas documentam o estado anterior e terão de mudar quando a implementação adotar production v8 e yield v10.
Nenhum foi alterado nesta etapa.

| teste / ponto | expectativa atual | mudança necessária |
|---|---|---|
| `tools/workbook_seed/blocks.py:86-94` | SHA e nome de production v6 e yield v9 | registrar v8 e v10 |
| `tests/test_production_v1.py::test_desaguamento_oee_reference_to_consumo_mpsa_is_a_recorded_pending_decision` | pendência R2-A019-UNREACHABLE | referência resolvida para `consumo_mpsa_grupo` |
| `tests/test_production_v1.py::test_production_integration_chain_inputs_to_producao_planta` | exclui `desaguamento_oee` citando R2-01 | pode incluí-lo |
| `tests/test_stage2_4_workbook_contract.py::test_t24_16_value_on_a_variable_row_is_recorded_not_dropped` | D24-12 pendente no manifesto | exigir rejeição |
| `tests/test_yield_v4_l1l7_and_aggregation_rules.py:792` | `source_reference` = nome do arquivo yield v9 | v10 |
| `tests/test_stage2_4_workbook_contract.py` (T24-01, T24-14) | seeds e hashes de v6/v9 | regenerar seeds; comparação automática |
| validator: 27 avisos D24-11 | repetição entre blocos como aviso contratual | relatório informativo (I5) |

`test_allowed_units_production_audit.py:31` menciona `%` para `oee` só em comentário; o conjunto testado continua
válido (`%` segue em uso por `consumo_*_percentual`). Não é expectativa funcional.

## 13. Evidências

Na raiz de `audit/stage2_5b_contract_decision/`:

| arquivo | conteúdo |
|---|---|
| `contract_decisions.csv` | decisões e regras |
| `cross_workbook_evidence.csv` | 19 identidades repetidas, por bloco, com tipo de produtor, fonte, unidade, instâncias e fórmula |
| `unit_evidence.csv` | `oee`/`oee_total` e unidades das identidades repetidas |
| `value_version_evidence.csv` | as 40 ocorrências, todas parameter |

Em `evidence/`:

| arquivo | conteúdo |
|---|---|
| `analysis_stage2_5b.py` | script reexecutável |
| `workbooks_sha256.txt` | hashes |
| `workbook_diffs.csv` | diffs célula a célula |
| `workbook_integrity.csv` | integridade por bloco |
| `reference_inventory.csv` | 1436 referências |
| `fonte_inventory.csv` | 34 linhas com fonte |
| `summary.json` | resumo |
| `inputs/` | production v8 e yield v10, byte a byte |

## 14. Decisões finais

| id | decisão | status | regra contratual | evidência | impacto para implementação |
|---|---|---|---|---|---|
| D25-01 | identidade calculada em vários blocos | **RESOLVED** | I1–I6: identidade local; unicidade intra-bloco; definições locais independentes permitidas; múltiplos produtores só intra-bloco ou em vínculo (erro) | 19 repetidas; 9 réplicas idênticas; 2 fórmulas diferentes | aviso D24-11 → relatório informativo; manter erro intra-bloco |
| D25-02 | `oee`/`oee_total` | **CONFIRMED_RULE** | unit = `-`; infraestrutura valida e rejeita, nunca converte | 9 linhas `-`; 0 divergências; 0 fatores de escala | validar unit em vínculos; adotar production v8 |
| D25-03 | `fonte` × produtor | **RESOLVED** | fonte é documental; não cria dependência, produtor ou resolução | area_41 → yield → production; 21 fontes fora da plataforma | nenhum uso de fonte em resolução; teste de não interferência |
| D25-04 | `fonte` × `variable_type` | **RESOLVED** | dimensões independentes; sem regra cruzada | 31 entrada, 1 entrada_externa, 2 calculado com fonte | nenhuma validação cruzada |
| D24-11 | ligação entre workbooks | **RESOLVED** | L1–L14: `source_block` opcional e único mecanismo; resolução e validação no build; fonte excluída; fallbacks só em expressões | nenhum `source_block` hoje; 13 relações são entradas locais válidas | coluna opcional no reader; cross-build; tabela de vínculos; propagação na Etapa 3 |
| D24-12 | value/version | **CONFIRMED_RULE** | exclusivos de parameter; variable e agregação = violação | 40/40 em parameter; yield r92 limpo | erro no builder; T24-16 |
| R2-01 | desaguamento_oee | RESOLVED_IN_SOURCE_WORKBOOK | — | mantida no v8; 0 inalcançáveis | adotar production v8 |

## 15. Pontos pendentes

Nenhuma decisão contratual pendente. Ficam **ações do dono do modelo**, que não bloqueiam a implementação e não
exigem interpretação do implementador:

- aprovar production v8 e yield v10 como oficiais, com os SHA-256 da §3;
- declarar `source_block` nas linhas em que quiser um vínculo real. Até lá, as entradas continuam locais, conforme
  L2.

## 16. Conclusão do gate

Os 10 critérios são atendidos:

1. D25-01, D25-03, D25-04 e D24-11 estão formalmente resolvidos por regras determinísticas.
2. D25-02 e D24-12 estão confirmados como regras, com 0 violações.
3. Não há ambiguidade crítica nem violação não classificada.
4. As expectativas antigas de teste estão classificadas como LEGACY_TEST_EXPECTATION.
5. Toda decisão se traduz em validação ou teste.

Push: o hook de encerramento deste ambiente exige que não fiquem commits locais sem push. O commit desta etapa
contém só `audit/stage2_5b_contract_decision/`.

STAGE_2.5B_CONTRACT_GATE: READY_FOR_IMPLEMENTATION
