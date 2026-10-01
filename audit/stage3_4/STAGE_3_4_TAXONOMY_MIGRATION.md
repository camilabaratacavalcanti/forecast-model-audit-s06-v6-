# D-TAX-01 — Canonicalização da taxonomia oficial (29 blocos) e rename `thickener_flocculant`

Decisão normativa **posterior ao fechamento da Stage 3** (`547b920`).

A mudança é exclusivamente taxonômica e nomenclatural:
- nenhuma fórmula, cálculo, regra de agregação, planner, engine ou comportamento funcional foi alterado;
- a reconciliação antes/depois está em `audit/stage3_4/taxonomy_migration/evidence/`.

---

## 1. Motivo da mudança

Até aqui o repositório tinha **dois registros de blocos**:

| registro | onde | nº | nomes |
|---|---|---:|---|
| taxonomia D26-01 (2.6B) | `tools/workbook_seed/taxonomy.py`, cópia em `data/seed/interblock_links.json` | 28 | títulos em português (`acido`, `premissas_ppt_mensal`, …), ordem própria |
| faixas de ID | `app/validation/{variable,parameter,equation}_seed_validator.py` | 29 | identificadores em inglês, com `budget_vs_forecast`; a faixa 30000–30999 era `monthly_ppt_assumptions` |

O comentário das faixas chamava-as de "Taxonomia oficial de 29 blocos", em conflito com a D26-01.

O proprietário decidiu:
- a lista de 29 é a **única** lista canônica em todas as fontes;
- a faixa 30000–30999 passa a se chamar `thickener_flocculant`.

## 2. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD inicial | `547b9202f5f17fb57034624d7f4c94b0618854e1` (3.4E), igual a origin, árvore limpa |
| commits da Stage 3.4 | `95e7ade` (3.4A), `4d54804` (3.4B), `043fe9c` (3.4C), `8095011` (3.4D), `547b920` (3.4E) |
| suíte inicial | **1859 passed**, 0 failed, 0 skipped |
| snapshot semântico "antes" | `taxonomy_migration/evidence/before_snapshot.json`, tirado em `547b920` antes de qualquer edição |

**Origem da taxonomia antes da mudança:**
- `tools/workbook_seed/taxonomy.py::BLOCK_TAXONOMY` (28);
- copiada por `tools/workbook_seed/interblock.py` (`write_interblock_seed`) para `data/seed/interblock_links.json → taxonomy.official_blocks`, que o `InterblockLinkRegistry` lê.

**Faixas:** três dicionários literais idênticos nos validadores (igualdade exigida por `tests/test_id_ranges_taxonomy_consistency.py`).

## 3. Decisão normativa — D-TAX-01

```text
D-TAX-01 (status: APROVADA pelo proprietário; aplicada neste commit)
1. O registro canônico de blocos tem EXATAMENTE 29 blocos, na ordem abaixo.
2. A faixa de cada bloco faz parte da identidade do bloco e não muda.
3. thickener_flocculant é o nome canônico da faixa 30000–30999 (antes monthly_ppt_assumptions).
4. budget_vs_forecast é bloco oficial.
5. BLOCK_TAXONOMY, a taxonomia do seed interbloco e VARIABLE/PARAMETER/EQUATION_ID_RANGES
   são semanticamente idênticos (mesmos nomes, mesma ordem).
6. A lista D26-01 de 28 nomes pertence ao estado anterior; não é mais normativa.
```

A regra de classificação da D26-01 continua valendo. É o mecanismo das três perguntas:
1. o nome pertence à taxonomia? (se não, `SOURCE_BLOCK_UNKNOWN`);
2. o workbook do bloco está carregado? (se não, `SOURCE_BLOCK_NOT_LOADED`);
3. existe produtor?

A D-TAX-01 substitui só a **lista**.

## 4. Os 29 blocos (ordem canônica) e 5. correspondência das faixas

| # | bloco | faixa | nome anterior na D26-01 |
|---:|---|---|---|
| 1 | maintenance | 10000–10999 | maintenance |
| 2 | yield | 11000–11999 | yield |
| 3 | production | 12000–12999 | production |
| 4 | max_ht | 13000–13999 | max_ht |
| 5 | alumina | 14000–14999 | alumina |
| 6 | temperature_lp | 15000–15999 | temperature_lp |
| 7 | area_41 | 16000–16999 | area_41 |
| 8 | area_04_13 | 17000–17999 | area_04_13 |
| 9 | energy | 18000–18999 | energy |
| 10 | boilers | 19000–19999 | boilers |
| 11 | volume | 20000–20999 | volume |
| 12 | soda | 21000–21999 | soda |
| 13 | residue_factor | 22000–22999 | fator_residuo |
| 14 | condensate_flow | 23000–23999 | vazao_condensado |
| 15 | forecast_volume | 24000–24999 | forecast_volume |
| 16 | full_volume_target | 25000–25999 | meta_volume_cheio |
| 17 | empty_space_target_control | 26000–26999 | controle_espaco_vazio_meta |
| 18 | lime | 27000–27999 | lime_dia |
| 19 | hydrated_flocculant | 28000–28999 | floculante_hidrato_2026 |
| 20 | sludge_flocculant | 29000–29999 | floculante_lama_dia |
| 21 | **thickener_flocculant** | 30000–30999 | premissas_ppt_mensal (faixa `monthly_ppt_assumptions` até D-TAX-01) |
| 22 | acid | 31000–31999 | acido |
| 23 | budget_cost | 32000–32999 | custo_budget¹ |
| 24 | budget_forecast_cost | 33000–33999 | custo_forecast_bdgt¹ |
| 25 | actual_forecast_cost | 34000–34999 | custo_forecast_real¹ |
| 26 | budget | 35000–35999 | budget |
| 27 | forecast | 36000–36999 | forecast |
| 28 | **budget_vs_forecast** | 37000–37999 | — (sem correspondente na D26-01) |
| 29 | shared | 38000–38999 | shared |

¹ Correspondência por nome; o comentário histórico das faixas diz só que "costs" foi desmembrado.

**Os blocos da Stage 3 mantêm a identidade:**
- os cinco carregados (yield, production, energy, max_ht, area_41);
- os cinco produtores dos 16 vínculos pendentes (maintenance, temperature_lp, forecast, area_04_13, alumina).

Todos têm o mesmo nome e a mesma faixa nos dois registros antigos e no novo.

## 6. Rename realizado

`monthly_ppt_assumptions` → `thickener_flocculant`, só nas ocorrências que são o **nome do bloco**. As 9 ocorrências existentes foram todas analisadas:

| arquivo | ocorrência | tipo | ação |
|---|---|---|---|
| `app/validation/variable_seed_validator.py` | chave das faixas; comentário normativo | código de produção | renomeada (chave e comentário) |
| `app/validation/parameter_seed_validator.py` | idem | código de produção | renomeada |
| `app/validation/equation_seed_validator.py` | idem | código de produção | renomeada |
| `tests/test_{variable,parameter,equation}_seed_validator.py` | chave nos dicionários esperados | teste | renomeada |

Nenhum seed, workbook, fixture, CSV, JSON, manifest ou mensagem de erro continha o identificador. Nenhum bloco tem workbook ou IDs nessa faixa. O rename não move nenhum ID.

## 7. Arquivos e fontes atualizados

**Fontes normativas e código:**
- `tools/workbook_seed/taxonomy.py`: `BLOCK_TAXONOMY` = 29 canônicos. A docstring declara que é a mesma lista das faixas e traz uma nota histórica sobre a D26-01.
- `tools/workbook_seed/interblock.py`: rótulo `taxonomy.decision` do seed `"D26-01"` → `"D-TAX-01"`.
- `data/seed/interblock_links.json`: **regenerado pela ferramenta oficial** (`build_all()` + `write_interblock_seed()`, com a permissão do proprietário). O diff é só a seção `taxonomy` (`decision` e `official_blocks`).
- `app/validation/*_seed_validator.py`: rename e nota D-TAX-01 nos comentários.

**Testes e auditoria viva:**
- `tests/test_stage2_6b_interblock_closure.py`: a lista do proprietário passa a ser `D_TAX_01_TAXONOMY` (29). A D26-01 fica em comentário, como registro.
- `tests/test_stage2_6c_interblock_final.py`: 28 → 29.
- `tests/test_{variable,parameter,equation}_seed_validator.py`: chave renomeada.
- `tests/test_id_ranges_taxonomy_consistency.py`: nota D-TAX-01 na docstring.
- `audit/stage2_6c_interblock_final/evidence/analysis_stage2_6c.py`: executado **ao vivo** pelo `test_17`, então é referência normativa atual. O oráculo `TAXONOMY` passa a ser a lista D-TAX-01, e a D26-01 fica como `TAXONOMY_D26_01` (registro). A evidência versionada da 2.6C (`validation_results.json`) **não** foi regenerada.

**Guardas da Stage 3 (§16):**
- `audit/stage3_4/differential/run_differential.py`;
- `audit/stage3_4/mutation/{run_mutation,provenance,code_mutants}.py`;
- `audit/stage3_4/closure/reconcile.py`;
- `tests/test_stage3_4b_differential.py`, `tests/test_stage3_4d_mutation.py`.

**Novos:**
- `audit/stage3_4/taxonomy_migration/{taxonomy_guard,snapshot,migration_compare}.py` e `evidence/`;
- `tests/test_taxonomy_migration_d_tax_01.py`;
- este relatório.

## 8. Arquivos históricos deliberadamente não alterados

| ocorrência | classificação | tratamento |
|---|---|---|
| `audit/stage2_6b_interblock_closure/{REPORT_stage2_6b.md, contract_decisions.csv, interblock_links.csv, evidence/*}` (lista D26-01, `premissas_ppt_mensal`) | HISTORICAL_REFERENCE | preservados; só uma *Historical note* no §4 do relatório |
| `audit/stage2_6c_interblock_final/{REPORT_stage2_6c.md, evidence/validation_results.json, *.csv}` | HISTORICAL_REFERENCE | preservados; *Historical note* no §6 do relatório |
| `audit/stage2_6b_interblock_closure/evidence/analysis_stage2_6b.py` (oráculo D26-01) | HISTORICAL_REFERENCE | não é executado por nenhum teste; preservado |
| `audit/stage2_6_interblock_contract/*` | HISTORICAL_REFERENCE | preservados |
| relatórios das Stages 3.1–3.3C e 3.4A–3.4E | HISTORICAL_REFERENCE | preservados. Notas só no §22 da 3.4A (a "nova decisão" prevista) e no fim do `STAGE_3_FINAL_CLOSURE.md` |
| evidência versionada da 3.4B/3.4C/3.4D/3.4E (`differential_summary.json`, `integrated_summary.json`, `mutation_summary.json`, `closure_reconciliation.json`) | HISTORICAL_REFERENCE | **não regenerada**: registra o estado da época |
| `tools/workbook_seed/interblock.py` e `app/engine/exceptions.py`: citações "(D26-01)" na regra de classificação | CURRENT_NORMATIVE_REFERENCE (a regra continua sendo a da D26-01) | inalteradas: a D-TAX-01 muda a lista, não a regra |
| `.pyc` versionados em `app/**/__pycache__` (cpython-314, antigos) | artefato espúrio pré-existente | não contêm nenhum dos dois nomes; não alterados |

Nenhuma ocorrência ficou `AMBIGUOUS_REFERENCE`.

## 9. Reconciliação antes/depois

Fonte: `evidence/migration_reconciliation.json`, gerado por `migration_compare.py` a partir de `before_snapshot.json` (`547b920`) e `after_snapshot.json`.

| item | antes | depois |
|---|---:|---:|
| `BLOCK_TAXONOMY` | 28 (D26-01) | **29** |
| taxonomia do seed interbloco | 28, `decision: D26-01` | **29**, `decision: D-TAX-01` |
| VARIABLE / PARAMETER / EQUATION ranges | 29 / 29 / 29 | 29 / 29 / 29 (mesmas faixas; nome da 30000–30999 atualizado) |
| as quatro fontes com a mesma lista e a mesma ordem | não | **sim** |

Seções que precisavam ficar **idênticas**, e ficaram (`invariant_sections_identical` todas `true`):
- sha256 de todos os arquivos de `data/seed/<bloco>/`, `data/id_ledger/` e `data/workbooks/`;
- IDs de variáveis, parâmetros, equações e regras por bloco;
- hash das expressões das equações;
- vínculos interbloco;
- cardinalidades;
- execução de 32 datas;
- hash do grafo REAL_DERIVED.

## 10. Diff semântico dos vínculos interbloco

- `data/seed/interblock_links.json` antes × depois, fora da seção `taxonomy`: **idêntico**, com as seções `contract`, `workbooks`, `links`, `pending` e `rejected` iguais.
- `taxonomy.loaded_blocks`: idêntico.
- Chave estrutural dos 13 vínculos válidos (consumidor, definição, bloco-fonte, definição-fonte, validação, resolução): idêntica.
- Todo `source_block` pertence aos 29.
- Nenhum vínculo criado, removido ou reclassificado.

## 11. Os 16 `PENDING_LOAD`

- Mesmos 16 consumidores, mesmo `resolution_status = PENDING_LOAD` e mesmo `validation_status`.
- Mesmos produtores: maintenance 9, temperature_lp 3, forecast 2, area_04_13 1, alumina 1.
- Nenhuma pendência preenchida ou removida.
- REAL_DERIVED continua `TEST_FIXTURE_ONLY`, e D32-01 continua `CLOSED_FOR_STAGE_3_SCOPE`.

## 12–15. Cálculos, IDs, planner e cardinalidades

| item | antes = depois |
|---|---|
| official planning targets | 446 |
| integrated targets | 421 |
| planner nodes | 427 (218 EQUATION + 197 AGGREGATION + 12 TRANSFER); sha256 da ordem do plano igual |
| equation definitions / instances | 218 / 392 |
| aggregation rules / instances | 197 / 395 |
| transfers | 12 |
| pending links | 16 (oficial); 0 no fixture |
| datas | 32 |
| identidades temporais | 313 (jan) / 313 (fev) / 185 anuais |
| fingerprint de resultados (RUN_A, 32 datas) | `d4de1aea…e10d` = evidência da 3.4C |
| fingerprint do store | `619b4abd…730c` = evidência da 3.4C |
| hash do grafo REAL_DERIVED | `e372425d…d1ff` |
| IDs e fórmulas | idênticos (TAX-06, TAX-07) |

## 16. Impacto sobre os guardas da Stage 3

**Os guardas não foram relaxados nem tiveram o baseline trocado.** A referência do diferencial continua `7877551`, e o diferencial continua sendo `7877551 × HEAD`. A novidade é uma exceção explícita, auditável e testada, com uma única fonte de verdade: `audit/stage3_4/taxonomy_migration/taxonomy_guard.py`.

```text
artefato protegido da Stage 3 + migração D-TAX-01 = permitido SOMENTE se o diff é provadamente taxonômico
```

**Arquivos que o guard admite, e o que exige de cada um:**
- `app/validation/*_seed_validator.py`: o AST é idêntico ao da base depois de mapear `thickener_flocculant` → `monthly_ppt_assumptions`, e o dicionário tem de ser exatamente os 29 canônicos. Comentários não entram no AST.
- `tools/workbook_seed/taxonomy.py`: o AST é idêntico, exceto a docstring e o valor de `BLOCK_TAXONOMY`, que tem de ser os 29 canônicos (e o da base, a D26-01).
- `tools/workbook_seed/interblock.py`: o AST é idêntico depois de mapear `D-TAX-01` → `D26-01`.
- `data/seed/interblock_links.json`: o JSON é idêntico fora de `taxonomy`, e `taxonomy` é exatamente `{D-TAX-01, 29 canônicos, loaded_blocks da base}`.

Qualquer outro arquivo, criação, remoção ou diferença é `NON_TAXONOMIC_CHANGE`.

**Onde a exceção é aplicada:**

| guarda | antes | agora |
|---|---|---|
| 3.4B `REFERENCE_DATA_TOOLS_INVARIANT` (`git diff 7877551..HEAD -- data tools`) | `PASS` só se vazio | `PASS` se vazio; `PASS_AUTHORIZED_TAXONOMY_MIGRATION_D-TAX-01` se o guard provar taxonomy-only; senão `FAIL` |
| 3.4D superfície protegida (`app data tools` vs `043fe9c`) | `NO PRODUCTION CHANGES` só se vazia | idem, ou `AUTHORIZED TAXONOMY MIGRATION (D-TAX-01)`; qualquer outra → `PRODUCTION CHANGED` |
| 3.4D proveniência (bytes de `interblock_links.json` = `043fe9c`) | igualdade de bytes | igualdade, ou diff só na seção `taxonomy`. Pendências mascaradas, `pending = []` etc. continuam `PROVENANCE_FAILURE` + `PENDING_LINKS_ALTERED` (testado) |
| 3.4E `reconcile.py` (vs `7877551`, `f3b6588`, `547b920`) | diffs vazios | `UNCHANGED` ou `AUTHORIZED_TAXONOMY_MIGRATION` |
| teste 3.4D `test_no_production_artifact_changed_since_baseline` | diff vazio | `unchanged` ou `taxonomy_only` pelo guard |
| mutantes de código (`repository_untouched`) | `git status` vazio antes e depois | o mesmo estado antes e depois: a execução dos mutantes não toca o repositório |

**Precondição preservada:** o diferencial exige `app/` do working tree = HEAD, porque testa o `app/` **commitado** via `git archive`. Por isso a validação completa foi feita sobre o commit final, num clone temporário (§17).

## 17. Testes

**Novos** (`tests/test_taxonomy_migration_d_tax_01.py`, 25 testes):

| teste | verifica |
|---|---|
| TAX-01 | exatamente 29 blocos em taxonomia, seed e três faixas |
| TAX-02 | ordem canônica exata em todas as fontes |
| TAX-03 | faixas exatas, contínuas, 1000 IDs, sem sobreposição; `budget_vs_forecast` |
| TAX-04 | `thickener_flocculant` = 30000–30999 nos três registros |
| TAX-05 | nome aposentado ausente de `app/`, `tools/` e `data/` (inclusive dentro dos `.xlsx`); D26-01 não normativa |
| TAX-06 | IDs e sha256 de todos os seeds e ledgers idênticos; faixas iguais salvo o nome |
| TAX-07 | fórmulas idênticas |
| TAX-08 | vínculos semanticamente idênticos; JSON igual fora de `taxonomy` |
| TAX-09 | os 16 `PENDING_LOAD` idênticos, com os 5 produtores |
| cardinalidades | 446/427 etc., execução de 32 datas, fingerprints, grafo e os 5 blocos carregados iguais |
| TAX-10 | a mudança é classificada `taxonomy_only` contra `547b920`, `7877551`, `f3b6588` e `043fe9c` |
| negativos (12 + 2) | o guard **rejeita**: mudança de fórmula, de valor, de faixa, código extra no validador, vínculo removido, `PENDING_LOAD` alterado, pendência removida, taxonomia com 28, alteração do `interblock_links.json` fora da seção autorizada, ordem da taxonomia trocada, código do engine, variável de seed removida, arquivo protegido criado ou removido; a proveniência 3.4D continua rejeitando pendências mascaradas |

**Resultados:**

A validação foi feita sobre o **commit final**, num clone temporário (`git clone --shared` + o mesmo change set commitado). O diferencial exige `app/` = HEAD.

| verificação | resultado |
|---|---|
| suíte antes (`547b920`) | 1859 passed, 0 failed, 0 skipped |
| suíte depois | **1884 passed**, 0 failed, 0 skipped (+25 de `test_taxonomy_migration_d_tax_01.py`; nenhum teste removido) |
| 3.4B `run_differential.py --no-write` | PASS, `REFERENCE_DATA_TOOLS_INVARIANT = PASS_AUTHORIZED_TAXONOMY_MIGRATION_D-TAX-01`, 0 diferenças, 2352 + 2370 = 4722 MATCH |
| 3.4C `run_integrated.py --no-write` | PASS, 421/421 alvos, 427/427 nós, fingerprint RUN_A `d4de1aea…` (= evidência da 3.4C), 0 problemas |
| 3.4D `run_mutation.py --no-write` (inclui os 17 mutantes de código) | PASS: 58/58 mutações detectadas, 0 perdidas, 13/13 controles de evidência ACCEPT; 17/17 mutantes mortos, 0 sobreviventes, CM-00 ACCEPT; superfície protegida `AUTHORIZED TAXONOMY MIGRATION (D-TAX-01)` |
| auditoria black-box (`python -I`) | PASS, `imports_app = false` |
| 3.4E `reconcile.py --no-write` | PASS, 31/31 linhas |
| `migration_compare.py --no-write` | PASS, 0 problemas |

Duas falhas encontradas durante a validação, ambas corrigidas **no harness** (nenhuma em produção):
1. **Sombreamento de módulo.** Os módulos novos chamavam-se `guard.py` e `compare.py`, e o segundo sombreava o comparador `compare` da 3.4B.
   - Correção: foram renomeados para `taxonomy_guard.py` e `migration_compare.py`, e o diretório entra no fim do `sys.path`.
2. **Controle CM-00 rejeitado.** O controle positivo dos mutantes de código (a árvore sem mutação) foi rejeitado porque a árvore temporária não copiava `taxonomy_migration/evidence/`.
   - Correção: a cópia foi incluída em `build_tree`.
   - O controle positivo funcionou como deveria.

## 18. Limitações

1. **Duas fontes físicas, uma lista.** O registro canônico continua fisicamente em duas fontes: os dicionários literais de `app/validation` (as faixas) e a tupla literal de `tools/workbook_seed/taxonomy.py`. O seed interbloco é gerado a partir desta última.
   - A arquitetura existente foi preservada: `app/` não importa `tools/`.
   - A identidade semântica entre elas é imposta por teste (TAX-01..TAX-03) e pelo guard.
2. **Correspondência dos custos inferida.** Os três blocos de custo são pareados com os nomes da D26-01 por nome (nota ¹ do §4); não há registro explícito anterior.
3. **Evidência histórica não regenerada.** A evidência das Stages 2.6B/2.6C e 3.4B–3.4E continua descrevendo o estado da época, com a lista D26-01 e os bytes antigos do seed interbloco. Os guardas reconhecem a migração explicitamente, em vez de sobrescrever essa evidência.
4. **Exceção nomeada.** O guard é específico da D-TAX-01. Qualquer migração futura exige nova decisão e nova exceção.

## 19. Decisão formal

**D-TAX-01**:
- canonicalização do registro de blocos para 29 blocos, na ordem das faixas de ID;
- rename da faixa 30000–30999 para `thickener_flocculant`.

Status: **APLICADA**. Decisão posterior ao fechamento da Stage 3; não reabre o `FINAL_STAGE_3_GATE`.

## 20. Hash final

O commit que contém este relatório é o commit único da migração: `chore(taxonomy): canonicalize 29 blocks and rename thickener flocculant`. O hash é o `HEAD` resultante, registrado na resposta final da execução e no `git log`. Um arquivo não pode conter o hash do próprio commit.

```text
TAXONOMY_MIGRATION_GATE: PASS
```

---

## Adendo D-TAX-02 — correção da nota sobre o pareamento dos custos (append-only)

A nota ¹ do §4 e a limitação 2 do §18 deste relatório dizem que os três blocos de custo foram pareados "por nome" e que "não há registro explícito anterior". **Essa afirmação estava incorreta.**

O registro explícito existe. O commit `1d3276e` (`refactor(ids): update block taxonomy`) declara na mensagem `custo_budget->budget_cost`, `custo_forecast_bdgt->budget_forecast_cost` e `custo_forecast_real->actual_forecast_cost`, "mantendo os MESMOS ranges numericos". O diff desse commit troca cada chave no mesmo lugar e com a mesma faixa nos três registries.

A decisão **D-TAX-02** formalizou os três pares como crosswalk normativo:
- status **CONFIRMED**;
- `inferred_only = false`;
- protegidos por `taxonomy_guard.check_crosswalk` e por `tests/test_taxonomy_d_tax_02.py`.

Ver `STAGE_3_4_TAXONOMY_D_TAX_02.md`. A limitação 2 deixa de valer, e **nenhum pareamento permanece inferido**.

O texto original acima não foi reescrito. Nada da D-TAX-01 mudou: nomes, faixas, ordem, IDs e o gate `TAXONOMY_MIGRATION_GATE: PASS` continuam iguais.
