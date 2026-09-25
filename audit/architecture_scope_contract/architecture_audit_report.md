# Verificação arquitetural — contrato de escopo, identidade e tipos

**Gate: ARCHITECTURE VERIFIED WITH GAPS**

## Pre-flight

| item | valor |
|---|---|
| branch | `claude/funny-noether-nbcr7b` |
| HEAD / commit-base | `5d81b5f` (igual a `origin`); merge-base com `main` = `202d4cb` |
| working tree | limpo antes da etapa |
| timestamp | 2026-09-25T13:11:31Z |
| raiz | `/home/user/forecast-model-audit-s06-v6-` (código `app/`, builders `tools/`, seeds `data/seed/`, testes `tests/`, auditorias `audit/`) |
| workbooks examinados | yield v4 `594ae47b`, production v1 `c21ef206`, energy v2 `347f256b`, MaxHT v5 `64363c94`, A41 v6 validado `4b0c41ae` (cópias em `evidence/workbooks/`) |

Método: sondas executadas diretamente contra o código de produção
(`explore_scope_contract.py`, 68 sondas, 68 consistentes), inspeção de fonte
com arquivo:linha, varredura dos 4 seeds, dos 2 builders e dos 5 workbooks, e
os testes da plataforma (311 testes de contrato e 1414 na suíte). Nenhum
relatório ou harness anterior foi usado como evidência.

Níveis: **OBSERVED** (fato), **DERIVED** (conclusão), **RECOMMENDATION** (futuro).

## B. Respostas às 8 perguntas

| # | Pergunta | Resposta | Evidência | Status |
|---|---|---|---|---|
| 1 | Contrato `scope_type/scope_value` | Há 5 `scope_type`: `linha` (L1..L7 ou `L1_L7`, expandido em uma instância por linha), `linha_grupo` (um dos 4 grupos, **não** expandido), `planta` (`PLANTA`), `área` e `global` (valor `None`). Os três validadores de seed têm enums e regras de combinação idênticos. O `ScopeResolver` é mais permissivo: aceita faixas como `linha/L2_L6`, de forma intencional e testada. | `variable_seed_validator.py:99,175,589`; `parameter_seed_validator.py:149,517`; `equation_seed_validator.py:85,402`; `scope_resolver.py:38-78,232`; `scope_contract_matrix.csv`; `tests/test_fase3a_scope_contract.py::test_scope_resolver_treats_linha_l1_l3_as_a_valid_subrange` | OBSERVED |
| 2 | Parser aceita `name@scope`? | **Em duas camadas.** (a) O runtime (parser) aceita só `ID@escopo` (`VAR#####@Lx`, `@<grupo>`); **nomes são rejeitados**, ou seja, NOT_IMPLEMENTED por desenho (P01/P02). (b) A camada de builder aceita `nome@Lx` e `nome@<grupo>` em `translate_expression`, que traduz para `ID@escopo` e preserva o sufixo (N16). `@` é sintaxe formal: vira `ID__escopo` antes do `ast.parse`, e `@` fora desse padrão é rejeitado (P09–P14). `@L4` e `@L4_L5` passam pelo mesmo código e diferem apenas no `scope_type` derivado. | `scoped_reference.py:32-110`; `expression_parser.py:129,377`; `reference_resolver.py:258`; sondas P01–P16, N16 | OBSERVED |
| 3 | O resolvedor usa name + frequency + scope? | **Sim, na camada de nomes:** `reference_resolver.resolve_reference` filtra por nome, depois frequência, depois escopo explícito ou pela cadeia espacial do consumidor. É determinístico, independe da ordem de inserção, e a ambiguidade gera erro. `hes@L4` nunca resolve para `hes@L5` nem para `hes` sem escopo (N01–N17). **No runtime,** a identidade é `ID + (scope_type, scope_value) + período`. Uma referência explícita só tem fallback temporal (R03/R04); uma implícita sobe linha → grupo → `L1_L7` → planta, nunca de lado nem para dentro (R06/R10). | `reference_resolver.py:59,81,99,192`; `expression_evaluator.py:641-740`; `spatial_candidate_resolver.py:83`; sondas N*, R* | OBSERVED |
| 4 | `@grupo` reutiliza o mecanismo? | **Sim.** A mesma regex e a mesma função (`scope_type_for`) mapeiam `Lx` → `linha` e grupo → `linha_grupo`; a busca usa a mesma `CalculationKey`. Os grupos são um registro estático e imutável (`ScopeResolver.GROUP_MEMBERS`, `LINE_GROUP_SCOPES`), sem recursão. O grupo é um `scope_value` de `scope_type = linha_grupo`. **Porém,** um grupo é uma entidade própria, e não o agregado das linhas: `X@L4_L5` com valores só em L4/L5 → `VariableNotFoundError` (R08, N15). Não há código especial para o A41. | `scoped_reference.py:51`; `scope_resolver.py:69-78,320`; sondas P05–P08, R08, R09, G01–G09 | OBSERVED |
| 5 | O armazenamento diferencia escopos? | **Sim:** `CalculationKey(entity_id, scope_type, scope_value, period_id)` distingue L4 de L5 e período de período (S01/S02). Há assimetria de identidade: uma variável é 1 ID = 1 escopo declarado (S04), enquanto um parâmetro é `(id, versão, escopo)` (S05). Existe um dicionário legado com chave só `entity_id` (S03), usado como **fallback de referência implícita** (R05). | `calculation_context.py:66,130-293`; `variables/registry.py:54`; `parameters/registry.py:74`; `variables/models.py:137`; `storage_identity_matrix.csv` | OBSERVED |
| 6 | Builders e seeds usam o contrato? | **Energy e max_ht:** delegam ao resolvedor central, passando `consumer_scope` e preservando `@`; não geram nomes espacializados nem têm tratamento de A41. O max_ht acrescenta uma política própria de desempate (`prefer_sum_variant`). Nenhum builder lê `value_type`. **Yield e production:** seeds versionados **sem builder** (não é possível regenerá-los a partir do workbook). | `tools/energy_seed_builder.py:161-187,260`; `tools/max_ht_seed_builder.py:188-234,313,356`; `builder_seed_matrix.csv` | OBSERVED |
| 7 | Workbooks anteriores demonstram o padrão? | **Sim, para `@linha` e nome+escopo; não, para `@grupo`.** Yield: 32 de 33 nomes em mais de um escopo e 924 refs `@Lx`. Production: 6 nomes / 94 refs. Energy: 1 / 49. Max_ht: **0** nomes em mais de um escopo (usa nomes espacializados) / 56. `@grupo` aparece **só** no A41 (10 refs); em nenhum workbook ou seed anterior. | `workbook_usage_matrix.csv`; `architecture_contract.json` (`seed_summary`) | OBSERVED |
| 8 | Existem nomes artificialmente espacializados? | **Sim, 25:** max_ht tem 21 (7 radicais × `_l123/_l45/_l67` em `linha_grupo`), A41 tem 4 (`hes_l4..l7` em `linha/L4..L7`). Em todos, o sufixo repete exatamente o escopo declarado. Yield, production e energy têm 0. | `spatialized_name_inventory.csv` | OBSERVED + DERIVED |

## C. Contrato arquitetural efetivamente implementado

```text
WORKBOOK / BUILDER (nomes)                RUNTIME (IDs)
name [@Lx | @grupo]                       VAR#####[@Lx | @grupo]
   │  reference_resolver                     │ scoped_reference.to_internal → VAR__escopo
   │  (nome → frequência → escopo)           │ parser (allowlist) → evaluator
   ▼                                         ▼
VAR#####[@escopo] ─────────────────────▶  CalculationKey(ID, scope_type, scope_value, period)
                                            explícita: só aquele escopo (+ fallback temporal)
                                            implícita: consumidor → grupo → L1_L7 → planta → [legado sem escopo]
```

- **Identidade de definição:**
  - variável: `variable_definition_id`, com 1 escopo declarado;
  - parâmetro: `(id, versão, scope_type, scope_value)`;
  - no workbook: nome + frequência + escopo, resolvido pelo builder.
- **Identidade de valor:** `(ID, scope_type, scope_value, period_id)`.
- **Grupo:** `scope_type = linha_grupo`, com `scope_value` num registro
  estático de 4 grupos. Materializa **uma** instância e não é um agregado das
  linhas.
- **Frase `L1_L7`:** em `linha/L1_L7`, significa 7 instâncias; em `@L1_L7`,
  significa a entidade `linha_grupo/L1_L7`.
- **Validação de seed:** `variable_id` único é **erro**. Assinatura (nome,
  unidade, variable_type, frequência, escopo) duplicada é apenas **warning**
  (`variable_seed_validator.py:774,915`).

## D. Divergências (OBSERVED)

| camada | divergência | evidência | classificação |
|---|---|---|---|
| runtime | Referência **implícita** cai no valor legado sem escopo quando o valor escopado não existe | R05; `expression_evaluator.py:717-720` | LEGACY (risco de fallback silencioso se algo gravar na API legada) |
| parser | Não há referência explícita a `planta`, `área` ou `global` (`@PLANTA` é rejeitado); só por referência implícita | P12 | gap de expressividade |
| resolver/runtime | `@grupo` não agrega as linhas; exige uma entidade no grupo | R08, N15 | por desenho; precisa estar documentado |
| ScopeResolver × validadores | O `ScopeResolver` aceita `linha/L1_L3`, `linha/L2_L6`; os validadores rejeitam | `scope_contract_matrix.csv`; teste que documenta | intencional (validadores são o gate) |
| validadores | Enums e regras de escopo **triplicados** (variável, parâmetro, equação), consistentes entre si | `*_seed_validator.py` | DUPLICATED |
| armazenamento | Assimetria de identidade: variável = 1 ID/1 escopo; parâmetro = ID × N escopos | S04/S05 | assimetria de contrato |
| validação | Nome+frequência+escopo duplicado é só warning | `variable_seed_validator.py:774,915` | gap (a ambiguidade só aparece se a entidade for referenciada) |
| builders | Dois pipelines quase idênticos (`extract_rows`/`build_*`) em energy e max_ht; nenhum lê `value_type` | `tools/*_seed_builder.py` | DUPLICATED + gap para blocos com categóricas |
| seeds | Yield e production sem builder | `builder_seed_matrix.csv` | LEGACY |
| workbooks | Max_ht (21) e A41 (4) usam nomes espacializados; yield usa nome+escopo | `spatialized_name_inventory.csv` | convenções divergentes entre blocos |

### Transversalidade

| mecanismo | classificação |
|---|---|
| `scoped_reference` (@linha/@grupo), `ScopeResolver`, `GROUP_MEMBERS`, `spatial_candidate_resolver` | TRANSVERSAL |
| `reference_resolver` (nome + frequência + escopo) | TRANSVERSAL (usado pelos 2 builders) |
| `value_type`, sentinela `"F"` | TRANSVERSAL |
| `prefer_sum_variant` (max_ht) | especialização legítima do bloco (hook genérico de `tie_breaker`) |
| API legada sem escopo em `CalculationContext` e fallback do evaluator | LEGACY |
| enums e regras de escopo nos 3 validadores | DUPLICATED |
| builders energy/max_ht | DUPLICATED |
| código de produção específico do A41 | **nenhum**; a única menção é a faixa de IDs `area_41: (16000, 16999)` na taxonomia (`variable_seed_validator.py:53`) |

### `hes_l4..l7`

- **OBSERVED:**
  - as 4 entidades têm unidade `-`, `entrada_externa`, `diário` e `categorical`;
  - a descrição segue o mesmo modelo ("Estado operacional da linha Lx");
  - o escopo é `linha/Lx`, idêntico ao sufixo do nome;
  - as equações comparam as 4 ao mesmo domínio de 5 estados.
- **DERIVED:** conceitualmente, é **uma** variável (`hes`) em 4 escopos,
  espacializada no nome (categoria 2).
- **Sondas N01–N06/N14:**
  - `hes` com 4 definições `linha/L4..L7` já é representável pelo contrato,
    sem colisão, via `hes@L4`;
  - `hes_l4` e `hes@L4` podem coexistir sem colidir;
  - nenhuma das duas formas é "canônica" no runtime, que só conhece IDs.
- **Restrição:** `hes linha/L4_L7` não é aceita pelos validadores; seriam 4
  definições `linha/Lx`, ou `linha/L1_L7`.

## E. `value_type`

Ver `value_type_contract.md`. Em resumo:

- `numeric` (padrão) e `categorical` são os valores suportados.
- `"F"` é um sentinela ortogonal a `value_type`, aceito em variáveis de
  qualquer tipo e nunca em parâmetros.
- Consumir `"F"` gera `ConditionalFailureError`; agregar uma série com `"F"`
  gera `AggregationFailureError`.
- `mixed` é rejeitado.
- Nenhum seed de produção declara `value_type`.

## F. Recomendações (não aplicadas)

1. Remover ou isolar o fallback legado sem escopo para referências implícitas
   (R05), ou torná-lo explícito e opt-in.
2. Centralizar enums e regras de escopo numa única fonte (por exemplo,
   `ScopeResolver`) consumida pelos 3 validadores.
3. Promover a duplicidade nome+frequência+escopo de warning para erro, ou
   exigir resolução sem ambiguidade no builder.
4. Decidir e documentar a semântica de `@grupo`: entidade própria (atual) ou
   agregado declarado.
5. Decidir se `@PLANTA` (e `área`/`global`) devem ser referenciáveis
   explicitamente.
6. Unificar os builders num pipeline genérico que leia `value_type` e resolva
   origens de agregação por instância concreta.
7. Padronizar a convenção de nomes entre blocos: nome + escopo, como no yield,
   em vez de sufixos (`hes_l4`, `a18_l45`), numa migração explícita e fora
   desta etapa.
8. Criar builders para yield e production, para permitir a regeneração a
   partir do workbook.

## G. Gate

**ARCHITECTURE VERIFIED WITH GAPS**

O contrato de escopo, identidade e tipos está implementado de forma
transversal e consistente nas camadas examinadas, e é demonstrável por sondas.
As lacunas são as listadas em D; nenhuma delas é contradição do contrato.
Esta verificação **não** declara a arquitetura "correta" nem "pronta para
implementação".
