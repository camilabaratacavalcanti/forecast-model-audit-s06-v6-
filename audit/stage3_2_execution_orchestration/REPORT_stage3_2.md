# Etapa 3.2 — Execução coordenada interbloco em runtime

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` (árvore limpa) |
| HEAD inicial | `8ca9d01` (evidências 3.1, `STAGE_3.1_GATE: PASS`) |
| suíte inicial | **1533 passed** |
| relatório lido | `audit/stage3_1_interblock_runtime/REPORT_stage3_1.md` |
| commits | `11c8931` (orquestrador e testes), `2cfc52a` (teste de reexecução progressiva) e o commit de evidências |
| suíte final | **1570 passed**, 0 failed (1533 + 37) |

## 2. Mapa da arquitetura existente

| pergunta | resposta |
|---|---|
| quem inicia uma execução | o chamador: `TemporalForecastOrchestrator.run_direct` / `run_aggregation*` ou `ForecastEngine.calculate_from_definition_registry` |
| quem executa uma equação | `EquationEngine.calculate_instance`, chamado pelo `ForecastEngine` na ordem do seu `DependencyGraph` |
| onde o período é definido | `ForecastEngine._resolve_instance_period_id`: frequência da variável-alvo + `run_date`, via `TimePeriodResolver.effective_window` |
| onde a instância é definida | `ForecastEngine.materialize_equation` e `ScopeResolver` (definição → instâncias por escopo) |
| onde o resultado é gravado | `CalculationContext.set_variable_value(target, valor, escopo, period_id)`; agregações devolvem `ForecastValue`, e o chamador grava |
| onde chamar a transferência 3.1 | entre a produção do valor do produtor e a primeira leitura do ID do consumidor |
| como saber que o produtor terminou | pela ordem topológica: o nó TRANSFER vem depois de todos os nós que produzem a variável produtora |
| como evitar execução duplicada | cada nó aparece uma vez no plano; uma transferência repetida com o mesmo valor é `UNCHANGED`, e com valor diferente é conflito 3.1 |

Não havia execução por bloco com dependências entre blocos. O `ForecastEngine` executa um registro de equações. As
agregações são executadas à parte, pelo `TemporalForecastOrchestrator`.

## 3. Arquitetura implementada

Novo módulo `app/engine/interblock_orchestrator.py`. O motor, o evaluator, o `CalculationContext` e o resolver da 3.1
não foram alterados.

```
seeds (SeedLoader) + interblock_links.json (InterblockLinkRegistry)
        │ ExecutionCatalog.from_seed_root
        ▼
grafo de execução em nível de DEFINIÇÃO
   EQUATION    EquationDefinition  → ForecastEngine.calculate_from_definition_registry (registro de 1 definição)
   AGGREGATION AggregationRule     → TemporalForecastOrchestrator.run_aggregation_instance (+ gravação no contexto)
   TRANSFER    vínculo canônico    → InterblockValueResolver.transfer (3.1)
        │ plan(targets): fecho de dependências + ordem de Kahn determinística
        ▼
execute(plan, CalculationContext, run_date) → ExecutionTrace (eventos WRITTEN/UNCHANGED, fonte de cada transferência)
```

Arestas, sempre produtor → consumidor:
- equação → variáveis referenciadas na expressão;
- agregação → origem e peso;
- transferência → variável produtora do vínculo;
- uma variável consumidora de vínculo é produzida **somente** pelo seu nó TRANSFER. Se também tiver produtor local, o
  plano falha com `INTERBLOCK_EXECUTION_PLAN_INVALID`.

**Decisão arquitetural 1: grafo por definição, não por bloco.** production e yield dependem um do outro como blocos:
`production.yield ← yield.yield` e `yield.lth ← production.lth`. Entre definições, porém, não há ciclo (Etapa 2.6).
Ordenar por bloco criaria um ciclo falso; ordenar por definição respeita todas as dependências.

**Decisão 2: planejamento antes da execução.** Um alvo cujo fecho alcança uma variável consumidora de vínculo
**pendente** falha com `INTERBLOCK_SOURCE_NOT_LOADED` antes de qualquer cálculo. Nada é executado parcialmente e nada é
gravado. O modo `plan(..., on_pending="report")` é só diagnóstico: devolve a ordem completa e os bloqueios
(`pending_blockers`), e `execute` recusa esse plano.

**Decisão 3: ordem determinística.** Kahn com fila ordenada pela chave do nó (`KIND:ID`). A ordem independe da carga
dos blocos, da ordem dos vínculos e de `PYTHONHASHSEED`. Um ciclo gera `INTERBLOCK_EXECUTION_CYCLE`, com o caminho
completo e os blocos envolvidos.

**Decisão 4: período e instância.**
- Equações: o período vem da regra existente (frequência do alvo + `run_date`).
- Transferências: `period_id = TimePeriodResolver.effective_window(frequência do vínculo, run_date)`, para exatamente as
  instâncias do vínculo.
- O resolver da 3.1 rejeita outro período ou outra granularidade e não faz fallback nem substituição.

**Decisão 5: entradas.**
- Entradas livres (sem equação, sem agregação e sem vínculo) e parâmetros são fornecidos pelo chamador, como no
  runtime existente. O plano lista as entradas em `required_inputs`.
- `seed_parameters()` carrega os valores de parâmetros do seed.
- Variáveis consumidoras de vínculo **não** são entradas.

**Preparação para a Etapa 3.3, sem implementá-la.** Os nós carregam só identidade e dependências. Valores ficam no
`CalculationContext` e eventos no `ExecutionTrace`. Um valor enriquecido (`value`/`state`/`detail`) pode entrar no
contexto e no trace sem alterar planejamento, ordem ou nós. Nada de estados, `allowed_values` em runtime ou agregação
state-aware foi implementado.

## 4. Ordem de execução das cadeias reais

| cadeia | ordem planejada (nós) |
|---|---|
| production → yield → area_41 (alvo `area_41` VAR16008) | `EQUATION:EQ12012` (production.lth) → `TRANSFER:VAR11031` (yield.lth ← production.lth) → `TRANSFER:VAR16007` (area_41.lth ← **yield**.lth) → `EQUATION:EQ16004` (area_41) |
| production → energy (alvo energy VAR18002, EQ18001 = VAR18001/24) | EQ12012 → TRANSFER VAR11031 → equações de yield → TRANSFER VAR12062 (production.yield ← yield.yield) → equações de production → TRANSFER VAR18001 (energy.producao ← production.producao) → EQ18001 (20 passos) |
| production → max_ht (alvo max_ht VAR13039, EQ13014) | EQ12012 → `TRANSFER:VAR13062` (max_ht.lth ← production.lth) → EQ13014 |
| production → energy, oficial | `TRANSFER:VAR18011` (energy.lth_meta ← production.lth_meta) |

Em nenhuma cadeia existe transferência `production → area_41`. O salto de area_41 lê `yield.VAR11031`.

## 5. Achado principal: a configuração oficial bloqueia as cadeias exigidas

Na configuração oficial (29 vínculos: 13 válidos e 16 pendentes), o orquestrador aplica a regra de pendência de forma
estrita:

| bloco | alvos executáveis hoje | alvos bloqueados | causa |
|---|---:|---:|---|
| production | 0 | 50 | todo valor calculado depende de `lth`, que depende de `reducao_lth_*`/`tempo_*` ← **maintenance** (pendente); também forecast (`fator_*_kg_t`) |
| max_ht | 0 | 109 | depende de production.lth/producao (maintenance) e de `alimentação_evap` ← alumina |
| energy | 1 | 42 | idem; só `lth_meta` ← production.lth_meta (entrada externa) é executável |
| area_41 | 3 | 22 | area_41.lth ← yield.lth ← production.lth (maintenance); hes ← maintenance |
| yield | 155 | 64 | o que não passa por yield.lth |

A auditoria independente conta 446 alvos: 159 executáveis e 287 bloqueados. Um alvo pode ter mais de um bloco
pendente; as contagens por bloco são maintenance 259, alumina 61, temperature_lp 30, forecast 23 e area_04_13 18.

Consequências:
- As cadeias `production → yield → area_41`, `production → energy` e `production → max_ht`, **com production
  calculado**, são corretamente **recusadas** com `INTERBLOCK_SOURCE_NOT_LOADED` (`source_block = maintenance`). Não
  entra valor fictício, zero, default nem outro bloco.
- A única cadeia interbloco executável oficialmente é `production.lth_meta → energy.lth_meta`. Ela executa ponta a
  ponta, mas o produtor é uma entrada externa, não um valor calculado.
- A mecânica das três cadeias reais foi comprovada com as **equações, IDs e vínculos reais** no cenário
  **REAL_DERIVED**. Esse cenário é sintético e está documentado: só nos testes e na sonda, os registros `pending` são
  tratados como entradas livres fornecidas pelo teste. Não é comportamento do runtime.

O requisito 8 (cadeia real ponta a ponta com production calculado) e a regra 9 (pendência nunca preenchida) são
**incompatíveis** na configuração atual dos workbooks. Isso depende de decisão (§11, D32-01).

## 6. Testes (`tests/test_stage3_2_execution_orchestration.py`, 37)

Cenários: **OFFICIAL** (seeds oficiais), **REAL_DERIVED** (sintético documentado, §5) e **SYNTHETIC** (catálogo mínimo
em memória: production/yield/area_41/energy com equação, agregação mensal, entrada anual, vínculo `linha_grupo` e
vínculo pendente).

| # | exigido | teste | cenário |
|---|---|---|---|
| 1–3 | produtor antes, transferência entre, valor correto | `test_01_03_*` | SYNTHETIC |
| 4 | cadeia de três blocos | `test_04_three_block_chain_without_shortcut` | SYNTHETIC |
| 5 | cadeia quebrada | `test_05_broken_chain_fails` | SYNTHETIC |
| 6 | produtor não executado | `test_06_producer_not_executed_fails` | SYNTHETIC |
| 7 | vínculo pendente | `test_07_pending_link_fails_before_any_execution` (nenhuma chave gravada) | SYNTHETIC |
| 8 | diário → diário | `test_08` | SYNTHETIC |
| 9 | mensal → mensal | `test_09` (3 dias, agregação AVERAGE, transferência `2026-09`) | SYNTHETIC |
| 10 | anual → anual | `test_10` | SYNTHETIC |
| 11 | frequência incompatível | `test_11` (vínculo diário × mensal rejeitado na carga) | SYNTHETIC |
| 12 | período incompatível | `test_12` (valor em outra granularidade não serve; sem fallback) | SYNTHETIC |
| 13 | mesma instância | `test_13` | SYNTHETIC |
| 14 | instância inexistente | `test_14` | SYNTHETIC |
| 15 | L3 não substitui L1 | `test_15` | SYNTHETIC |
| 16 | linha não substitui linha_grupo | `test_16` | SYNTHETIC |
| 17 | execuções iguais | `test_17` | SYNTHETIC |
| 18 | ordem dos blocos | `test_18` | SYNTHETIC |
| 19 | ordem dos vínculos | `test_19` | SYNTHETIC |
| 20 | hash seed | `test_20` (3 `PYTHONHASHSEED`, cenário sintético e REAL_DERIVED) | ambos |
| 21 | sem contaminação entre blocos | `test_21` | SYNTHETIC |
| 22 | períodos isolados | `test_22` | SYNTHETIC |
| 23 | reexecução sem duplicar | `test_23` (`UNCHANGED`; valor divergente leva a conflito 3.1, sem overwrite) | SYNTHETIC |
| — | ciclo | `test_cycle_fails_with_the_full_cycle` | SYNTHETIC |
| 24–27 | blocos isolados | `test_24_27_isolated_block_behaves_as_the_existing_engine` [production, yield, energy, max_ht]: equações reais do bloco pelo orquestrador × `ForecastEngine` direto, com mesmas entradas, dão **contexto idêntico**; `test_yield_official_execution_matches_existing_engine`; `test_24_27_official_block_plans_report_the_pending_boundary` | REAL_DERIVED / OFFICIAL |
| 28 | production → yield → area_41 | `test_28_real_derived_chain_production_yield_area_41` (ordem exata, fontes lidas, valores nos três níveis, média de EQ16004); `test_28_official_*_blocked_by_maintenance` | REAL_DERIVED / OFFICIAL |
| 29 | production → energy | `test_29_real_derived_chain_production_energy`; `test_29_official_chain_production_lth_meta_to_energy` | REAL_DERIVED / OFFICIAL |
| 30 | production → max_ht | `test_30_real_derived_chain_production_max_ht`; `test_30_official_max_ht_is_blocked_by_maintenance` | REAL_DERIVED / OFFICIAL |
| — | contrato | `test_orchestrator_uses_only_canonical_artifacts` (AST: sem openpyxl/tools/fonte/source_reference); `test_pending_boundary_is_never_filled`; `test_progressive_period_rerun_in_same_context_is_an_explicit_conflict` | — |

Nenhum teste existente foi alterado. **LEGACY_TEST_EXPECTATION: nenhum.**

## 7. Auditoria independente

`evidence/analysis_stage3_2.py` **não importa `app/` nem `tools/`**. O script:
- reconstrói o grafo a partir dos seeds;
- calcula fechos, bloqueios e restrições de ordem;
- observa o orquestrador como caixa-preta pela sonda `evidence/runtime_probe.py`, executada em subprocesso.

| verificação | resultado |
|---|---|
| planos dos 446 alvos (oficial): estado, bloco pendente, fecho, entradas | iguais ao esperado |
| 19 execuções bloqueadas (16 pendentes + 3 cadeias): erro `INTERBLOCK_SOURCE_NOT_LOADED` e 0 chaves gravadas | ok |
| 1 execução oficial (lth_meta) + 16 REAL_DERIVED (3 cadeias + 13 consumidores): passos = fecho, ordem, 200 eventos de transferência conferidos contra o contexto | ok |
| cadeia production → yield → area_41 na ordem exata | ok |
| determinismo: sonda com `PYTHONHASHSEED` 0 × 424242 | idêntica |

| contador | valor |
|---|---:|
| divergências | **0** |
| transferências fora do contrato | **0** |
| atalhos | **0** |
| execuções fora da ordem | **0** |
| valores fictícios | **0** |

Evidências:
- `evidence/plan_evidence.csv`: 446 alvos;
- `evidence/transfer_evidence.csv`: 200 eventos;
- `evidence/analysis_summary.json`;
- `evidence/determinism_check.txt`: análise com 3 `PYTHONHASHSEED`, mesmo SHA-256;
- `evidence/test_output.txt`.

## 8. Arquivos alterados

`git diff --stat 8ca9d01 HEAD` fora de `audit/`: 3 arquivos, 1368 inserções, **0 remoções**.

| arquivo | alteração |
|---|---|
| `app/engine/interblock_orchestrator.py` | **novo**: `ExecutionCatalog`, `ExecutionPlan`, `PendingBlocker`, `ExecutionNode`, `ExecutionTrace`, `InterblockExecutionOrchestrator` |
| `app/engine/exceptions.py` | + `InterblockExecutionPlanError`, `InterblockExecutionCycleError` (somente acréscimo; CRLF preservado) |
| `tests/test_stage3_2_execution_orchestration.py` | **novo** |

Não alterados:
- `ForecastEngine`, `ExpressionEvaluator`, `EquationEngine`, `CalculationContext`, `TemporalForecastOrchestrator`;
- `interblock_resolver.py` e `app/domain/interblock/*` (contrato 3.1);
- `SeedLoader`, os validators e `tools/`;
- `data/seed/**`, `data/id_ledger/**` e `data/workbooks/**`;
- `fonte`, `source_block` e a taxonomia;
- os testes existentes e as evidências anteriores.

## 9. Critérios de aceite

| critério | situação |
|---|---|
| testes existentes passam | sim (1533 → 1570, nenhum alterado) |
| novos testes passam | 37 passed |
| quatro blocos funcionando | sim: execução isolada idêntica ao caminho existente (testes 24–27); o caminho existente não mudou |
| cadeia real production → yield → area_41 ponta a ponta | **não na configuração oficial** (bloqueada por maintenance, §5); comprovada só em REAL_DERIVED |
| sem execução fora da ordem | sim (0) |
| sem fallback interbloco | sim |
| sem conversão de frequência ou instância | sim |
| pendentes falham explicitamente | sim (antes de executar, 0 gravações) |
| determinismo | sim |
| auditoria com 0 divergências | sim |
| nada alterado em workbooks, IDs ou seeds | sim |

## 10. Limitações

1. **Cadeias reais com production calculado estão bloqueadas pela pendência de maintenance** (§5).
2. **Reexecução progressiva no mesmo contexto.**
   - Um `period_id` mensal ou anual (ex.: `2026-09`) tem valor efetivo diferente a cada `run_date` (janela truncada).
   - No mesmo contexto, a nova transferência encontra o valor anterior no consumidor e falha com
     `INTERBLOCK_CONSUMER_VALUE_CONFLICT` (regra 3.1). Isso está registrado em teste.
   - Com um contexto por `run_date` não há conflito.
   - As equações e agregações existentes sobrescrevem o próprio alvo (comportamento anterior, inalterado); só a
     transferência é estrita.
3. **Planos por definição.** O executor chama o `ForecastEngine` uma vez por definição de equação. O resultado é
   idêntico ao da execução em lote (testes 24–27). O custo é maior, o que é irrelevante neste volume.
4. **Agregações sobre janelas.** Exigem no contexto os valores diários de toda a janela até `run_date`. A falta de um
   dia é erro explícito do serviço existente.

## 11. Decisões pendentes

| ID | tema | opções |
|---|---|---|
| **D32-01** | executar as cadeias reais com production calculado | (a) carregar o workbook de **maintenance** (e forecast, alumina, temperature_lp e area_04_13 para os demais alvos), o que transforma pendências em vínculos válidos pelo fluxo da Etapa 2.6; (b) aprovar um modo explícito de **entrada de fronteira** para variáveis de vínculo pendente, com valor fornecido pelo chamador, proveniência marcada no trace e desligado por padrão. A opção (b) contraria a regra 9 como escrita, então não foi implementada. |
| **D32-02** | reexecução progressiva de períodos mensais/anuais no mesmo contexto | (a) manter a regra 3.1 (conflito) e exigir um contexto por `run_date`; (b) versionar o valor transferido por execução ou `run_date`, candidato a entrar junto do modelo value/state/detail da Etapa 3.3. |

A implementação não depende da escolha: nenhuma das opções exige mudar o planejamento, a ordem ou os nós do
orquestrador.

## 12. Push

Os commits da etapa são enviados com `git push -u origin feature/area-41-block`. Nenhum PR foi criado.

STAGE_3.2_GATE: READY_FOR_DECISION
