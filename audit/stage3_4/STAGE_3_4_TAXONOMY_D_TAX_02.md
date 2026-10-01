# D-TAX-02 — Crosswalk Histórico dos Blocos de Custo e Registro da Duplicação Física da Taxonomia

| campo | valor |
|---|---|
| decisão | **D-TAX-02** |
| status | **APPLIED** |
| posterior a | D-TAX-01 (`d8b5d55810c55a06cfc54e8a2a25ac9f796f08b7`) |
| crosswalk machine-readable | `audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json` |
| registro de decisões | `audit/stage3_4/taxonomy_migration/contract_decisions.csv` |
| dívida arquitetural | `audit/stage3_4/TECH_DEBT_TAXONOMY_DUPLICATION.md` (TD-TAX-01, OPEN) |
| impacto funcional | **nenhum** |

## 1. Decisão normativa

```text
D-TAX-02 — Formalização do Crosswalk Histórico dos Blocos de Custo
```

1. O registro canônico continua sendo a taxonomia D-TAX-01 com 29 blocos.
2. Os nomes atuais `budget_cost`, `budget_forecast_cost` e `actual_forecast_cost` são canônicos.
3. Os nomes `custo_budget`, `custo_forecast_bdgt` e `custo_forecast_real` são **históricos**.
4. Nomes históricos **não** fazem parte da taxonomia operacional atual.
5. Referências históricas devem ser traduzidas exclusivamente pelo crosswalk normativo D-TAX-02.
6. Nenhuma correspondência é inferida por similaridade de nome.
7. O crosswalk não altera faixas de ID, IDs, fórmulas, planner, vínculos ou cálculos.
8. O crosswalk vale para leitura e interpretação de evidências históricas.
9. O crosswalk não autoriza aceitar nomes históricos como blocos operacionais.

Pareamentos (todos **CONFIRMED**, nenhum inferido):

| nome histórico | nome canônico | faixa | status |
|---|---|---|---|
| `custo_budget` | `budget_cost` | 32000–32999 | **CONFIRMED** |
| `custo_forecast_bdgt` | `budget_forecast_cost` | 33000–33999 | **CONFIRMED** |
| `custo_forecast_real` | `actual_forecast_cost` | 34000–34999 | **CONFIRMED** |

## 2. Regra de evidência

Um par só é `CONFIRMED` se houver **evidência explícita de repositório** de que o nome histórico e o canônico designam o mesmo bloco. Semelhança de nome não conta como evidência. Sem essa evidência, o par seria `UNRESOLVED` e a etapa pararia.

Para os três pares, há duas evidências independentes e explícitas:

- **EXPLICIT_RENAME_RECORD** — o commit `1d3276e` (`refactor(ids): update block taxonomy`) registra na própria mensagem, par a par, "12 chaves antes em portugues renomeadas para ingles, mantendo os MESMOS ranges numericos: ... `custo_budget->budget_cost`, `custo_forecast_bdgt->budget_forecast_cost`, `custo_forecast_real->actual_forecast_cost`".
- **SAME_ID_RANGE_ALL_REGISTRIES** — o diff de `1d3276e` substitui cada chave **no mesmo lugar e com a mesma faixa** em `VARIABLE_ID_RANGES`, `PARAMETER_ID_RANGES` e `EQUATION_ID_RANGES`. A comparação foi feita em `1d3276e^` × `1d3276e` nos três arquivos e também nos testes dos três validadores.

A identidade de um bloco na plataforma é a sua faixa de IDs. O mesmo intervalo, nos três registries, no mesmo commit que declara o rename, é prova direta de identidade, e não inferência.

## 3. Matriz de evidência por par

### 3.1 `custo_budget → budget_cost`

| campo | valor |
|---|---|
| historical_name | `custo_budget` |
| canonical_name | `budget_cost` |
| historical_range | 32000–32999 |
| canonical_range | 32000–32999 |
| same_id_range | **true** (nos três registries) |
| semantic_evidence | rename declarado da mesma chave de bloco (identidade = faixa 32000–32999), registrado no momento da mudança; tradução consistente (custo → cost). Não existe entidade nessa faixa, portanto não há conteúdo de dados a comparar |
| repository_evidence | `1d3276e` (mensagem: `custo_budget->budget_cost`; diff: `"custo_budget": (32000, 32999)` → `"budget_cost": (32000, 32999)` nos três registries); `8165b4b`/`c734120` (criação a partir do desmembramento de `costs`) |
| status | **CONFIRMED** |

### 3.2 `custo_forecast_bdgt → budget_forecast_cost`

| campo | valor |
|---|---|
| historical_name | `custo_forecast_bdgt` |
| canonical_name | `budget_forecast_cost` |
| historical_range | 33000–33999 |
| canonical_range | 33000–33999 |
| same_id_range | **true** (nos três registries) |
| semantic_evidence | rename declarado da mesma chave (identidade = faixa 33000–33999); tradução consistente (custo → cost; forecast_bdgt → budget_forecast). Nenhuma entidade na faixa |
| repository_evidence | `1d3276e` (mensagem: `custo_forecast_bdgt->budget_forecast_cost`; diff com a mesma faixa nos três registries); `8165b4b`/`c734120` |
| status | **CONFIRMED** |

### 3.3 `custo_forecast_real → actual_forecast_cost`

| campo | valor |
|---|---|
| historical_name | `custo_forecast_real` |
| canonical_name | `actual_forecast_cost` |
| historical_range | 34000–34999 |
| canonical_range | 34000–34999 |
| same_id_range | **true** (nos três registries) |
| semantic_evidence | rename declarado da mesma chave (identidade = faixa 34000–34999); tradução consistente (custo → cost; forecast_real → actual_forecast). Nenhuma entidade na faixa |
| repository_evidence | `1d3276e` (mensagem: `custo_forecast_real->actual_forecast_cost`; diff com a mesma faixa nos três registries); `8165b4b`/`c734120` |
| status | **CONFIRMED** |

### 3.4 Linha do tempo dos nomes

| commit | evento |
|---|---|
| `8165b4b` | `costs` desmembrado em `custo_budget` / `custo_forecast_bdgt` / `custo_forecast_real` (32000–34999) em `VARIABLE_ID_RANGES` |
| `c734120` | as mesmas chaves e faixas em `PARAMETER_ID_RANGES` e `EQUATION_ID_RANGES` |
| `1d3276e` | rename explícito para `budget_cost` / `budget_forecast_cost` / `actual_forecast_cost`, mesmas faixas |
| `5e681dc` | a lista D26-01 da Stage 2.6B ainda usa os títulos históricos (`custo_*`) |
| `d8b5d55` | D-TAX-01: a lista canônica única de 29 blocos usa os nomes atuais |

**Limitação de escopo semântico.** Nenhuma variável, parâmetro ou equação existe hoje nas faixas 32000–34999. A evidência prova a identidade dos **blocos** (chave e faixa), não a equivalência de conteúdo de negócio, porque esse conteúdo ainda não existe.

### 3.5 Correção do relatório D-TAX-01

O relatório D-TAX-01 (`STAGE_3_4_TAXONOMY_MIGRATION.md`, nota ¹ do §4 e limitação 2 do §18) descreveu o pareamento como "inferido por nome" e afirmou que "não há registro explícito anterior".

A investigação desta etapa encontrou esse registro: o commit `1d3276e`. A afirmação foi corrigida por adendo append-only naquele relatório, sem reescrever o texto original. **Nenhum dos três pareamentos permanece inferido.**

## 4. Crosswalk machine-readable

`audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json`:
- `decision = "D-TAX-02"`, `status = "APPLIED"`;
- `historical_names_are_operational = false`, `inference_by_name_allowed = false`;
- por par: `canonical`, `historical_range`, `canonical_range`, `same_id_range`, `status`, `inferred_only = false`, `evidence_class`, `repository_evidence`, `semantic_evidence`.

O **oráculo escrito** é `taxonomy_guard.COST_CROSSWALK`. `taxonomy_guard.check_crosswalk` exige que o JSON seja igual ao oráculo e falha em qualquer um destes casos:
- par ausente, extra ou alterado;
- faixa alterada;
- faixa canônica divergente da D-TAX-01;
- status implícito ou fora de `CONFIRMED`/`UNRESOLVED`;
- `inferred_only` diferente de `false`;
- `CONFIRMED` sem evidência;
- nome histórico tratado como canônico;
- inferência por nome permitida;
- decisão diferente de D-TAX-02 `APPLIED`.

## 5. Dívida arquitetural registrada (TD-TAX-01)

```text
TECH-DEBT — Duplicação Física da Taxonomia Canônica
Status: OPEN  (não é bloqueador funcional)
```

- A taxonomia canônica é conceitualmente única (D-TAX-01), mas tem duas implementações físicas:
  - `app/validation` (três dicionários de faixas);
  - `tools/workbook_seed/taxonomy.py` (`BLOCK_TAXONOMY`), de onde se gera a projeção `data/seed/interblock_links.json → taxonomy.official_blocks`.
- **Motivo, verificado no código:**
  - `tools/` importa `app/`;
  - `app/` não importa `tools/` (teste `test_tax_02_arch_app_does_not_import_tools`);
  - inverter a dependência criaria um ciclo.
- **Risco:** divergência futura entre as projeções.
- **Mitigação:** `taxonomy_guard.check_projections` mais os testes D-TAX-01 e D-TAX-02.
- **Solução futura, não implementada:** "Evaluate a shared dependency-free canonical taxonomy representation compatible with the app/tools architectural boundary."

Detalhes em `TECH_DEBT_TAXONOMY_DUPLICATION.md`. Nenhuma refatoração foi feita: não há dependência `app → tools` e a taxonomia não foi movida.

## 6. Guard reforçado (`taxonomy_guard.py`)

O guard ganhou dois controles permanentes. Nenhum controle anterior foi enfraquecido.

| controle | falha quando |
|---|---|
| `check_projections(physical_projections())` | alguma das 5 projeções (`VARIABLE_ID_RANGES`, `PARAMETER_ID_RANGES`, `EQUATION_ID_RANGES`, `BLOCK_TAXONOMY`, `interblock_links.taxonomy`) difere do canônico D-TAX-01: bloco some ou aparece, nome muda, faixa muda, ordem muda |
| `check_crosswalk(json)` | o crosswalk persistido difere dos pareamentos documentados (§4) |
| `check_current_registry()` | soma dos dois; precisa retornar `[]` |

Generalização de `classify`:
- antes, a base de comparação tinha de ser **pré-migração** (nomes antigos);
- agora, também é aceita uma base **já migrada**.

Em ambos os casos, a exigência continua sendo igualdade **exata** de AST. Isso permite que comparações contra `d8b5d55` aceitem um diff só de comentários, e nada além. Os testes negativos da D-TAX-01 continuam passando.

## 7. Arquivos alterados

| arquivo | mudança |
|---|---|
| `audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json` | novo — crosswalk normativo |
| `audit/stage3_4/taxonomy_migration/contract_decisions.csv` | novo — D-TAX-01 APPLIED, D-TAX-02 APPLIED, TD-TAX-01 OPEN |
| `audit/stage3_4/taxonomy_migration/taxonomy_guard.py` | guardas D-TAX-02 e base já migrada aceita (AST exato) |
| `audit/stage3_4/taxonomy_migration/d_tax_02_inventory.py` | novo — inventário classificado das ocorrências |
| `audit/stage3_4/taxonomy_migration/evidence/d_tax_02_occurrences.csv` | novo — evidência do inventário |
| `audit/stage3_4/STAGE_3_4_TAXONOMY_D_TAX_02.md` | este documento |
| `audit/stage3_4/TECH_DEBT_TAXONOMY_DUPLICATION.md` | novo — TD-TAX-01 |
| `audit/stage3_4/PLATFORM_PENDING_ITEMS.md` | novo — lista mestre de pendências |
| `audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md` | adendo append-only (correção da nota "inferido") |
| `audit/stage3_4/STAGE_3_FINAL_CLOSURE.md` | adendo append-only (D-TAX-01, D-TAX-02 e dívida conhecida) |
| `app/validation/variable_seed_validator.py`, `parameter_seed_validator.py` | **somente comentário**: a lista de nomes antigos foi trocada por uma referência ao crosswalk. AST idêntico; CRLF preservado |
| `tests/test_taxonomy_d_tax_02.py` | novo — TAX-02-01..08, arquitetura e negativos |

**Por que os comentários de `app/` mudaram.** O D-TAX-02 proíbe nomes históricos em código operacional. O AST desses arquivos é idêntico ao de `d8b5d55` (provado por `test_tax_02_07`), então nenhum ID, faixa ou comportamento mudou.

## 8. Busca estrutural (A)

`d_tax_02_inventory.py` classifica **toda** ocorrência dos três nomes históricos e dos três canônicos, em arquivos versionados e novos. A evidência fica em `taxonomy_migration/evidence/d_tax_02_occurrences.csv`.

| classe | significado | nomes históricos permitidos? |
|---|---|---|
| operational | `app/`, `tools/`, `data/` | **não** |
| normative | crosswalk, registro de decisões, guard, inventário, este documento, TD-TAX-01, lista mestre | sim |
| historical | evidência e relatórios das Stages 2.6B/2.6C, relatório D-TAX-01, fechamento da Stage 3 (append-only) | sim |
| evidence | `taxonomy_migration/evidence/` | sim |
| test | `tests/` | só em `tests/test_taxonomy_d_tax_02.py` e `tests/test_stage2_6b_interblock_closure.py` (oráculo histórico D26-01) |

`analysis_stage2_6c.py`, executado ao vivo pelo teste 2.6C:
- nomes canônicos → normative;
- nomes históricos (lista D26-01) → historical.

Resultado: 0 ocorrências não classificadas; **0 nomes históricos em código operacional**. A contagem final está no §10.

## 9. Invariantes (B, C, D)

| invariante | resultado |
|---|---|
| blocos | 29 em todas as 5 projeções |
| nomes | idênticos ao canônico D-TAX-01 |
| faixas | idênticas (10000–38999), três registries iguais |
| ordem | idêntica à ordem das faixas |
| IDs | nenhum alterado; `app/`, `tools/` e `data/` sem mudança de AST nem de dados |
| crosswalk | 3 pares, 3 status explícitos (`CONFIRMED`), 3 faixas, 0 inferidos |
| app → tools | 0 imports |

## 10. Validação

Execução feita sobre uma árvore commitada (clone temporário com as mudanças desta etapa), porque o diferencial 3.4B exige `app/` limpo:

| # | comando | resultado |
|---|---|---|
| 1 | `python -m pytest -q` | **1921 passed**, 0 failed, 0 skipped (baseline `d8b5d55`: 1884; +37 testes D-TAX-02) |
| 2 | `python -m pytest -q tests/test_taxonomy_d_tax_02.py tests/test_taxonomy_migration_d_tax_01.py` | 62 passed (37 D-TAX-02 + 25 D-TAX-01) |
| 3 | `python audit/stage3_4/taxonomy_migration/d_tax_02_inventory.py` | PASS: 243 ocorrências, 0 não classificadas, 0 nomes históricos operacionais |
| 4 | `python audit/stage3_4/taxonomy_migration/migration_compare.py --no-write` | PASS |
| 5 | `python audit/stage3_4/differential/run_differential.py --no-write` | PASS, 0 diferenças, 2352 + 2370 = 4722 MATCH |
| 6 | `python audit/stage3_4/integrated/run_integrated.py --no-write` | PASS, 0 problemas |
| 7 | `python audit/stage3_4/mutation/run_mutation.py --no-write` | PASS, 58/58 mutações, 17/17 mutantes mortos, CM-00 ACCEPT, 13/13 controles |
| 8 | `python -I audit/stage3_4/mutation/blackbox_audit.py --no-write` | PASS |
| 9 | `python audit/stage3_4/closure/reconcile.py --no-write` | PASS, 0 problemas |
| 10 | `taxonomy_guard.check_current_registry()` | `[]` |

## 11. Preservação da Stage 3

- D-TAX-01 continua `APPLIED`.
- `FINAL_STAGE_3_GATE` continua fechado e não foi reaberto.
- Os resultados históricos das 3.4A–3.4E não foram alterados; houve apenas notas append-only.
- Os 16 `PENDING_LOAD` continuam `PENDING_LOAD`.
- Fórmulas, planner, vínculos e cardinalidades não mudaram.

## 12. Status final

```text
D-TAX-02: APPLIED
  custo_budget        -> budget_cost           32000-32999  CONFIRMED
  custo_forecast_bdgt -> budget_forecast_cost  33000-33999  CONFIRMED
  custo_forecast_real -> actual_forecast_cost  34000-34999  CONFIRMED
TD-TAX-01: OPEN (dívida arquitetural conhecida; não bloqueia funcionalidade)
```
