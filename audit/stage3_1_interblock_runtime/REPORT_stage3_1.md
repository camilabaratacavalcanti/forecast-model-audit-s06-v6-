# Etapa 3.1 — Integração interbloco no runtime

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` (worktree único) |
| HEAD inicial | `7877551` (evidências 2.6C, `STAGE_2.6C_GATE: PASS`) sobre `68cb5a1` |
| árvore | limpa |
| suíte inicial | **1496 passed** |
| workbooks oficiais | area_41 v9, energy v6, max_ht v10, production v11, yield v11 (não alterados) |
| commit de implementação | `e60af19` |
| commit de evidências | o seguinte a `e60af19` (contém este relatório) |
| suíte final | **1533 passed**, 0 failed |

## 2. Arquitetura do runtime encontrada

| pergunta | resposta |
|---|---|
| armazenamento de definições | `VariableDefinitionRegistry`, `ParameterDefinitionRegistry`, `EquationDefinitionRegistry`, `AggregationRuleRegistry`, carregados pelo `SeedLoader` a partir de `data/seed/*/…json` |
| resolução de referência em equação | build: `reference_resolver` (A019, nome → ID). Runtime: `ExpressionEvaluator` lê o ID no `CalculationContext` com fallback **temporal** (dia → mês → ano → sem período) e **espacial** (Decision E), só intrabloco |
| instância concreta | `VariableInstance` / `EquationInstance` = definição + (`scope_type`, `scope_value`), materializadas pelo `ScopeResolver` (ex.: linha/L1_L7 → L1..L7) |
| frequência e período | a frequência está na `VariableDefinition`; o `period_id` segue a convenção `YYYY-MM-DD` / `YYYY-MM` / `YYYY` (`TimePeriodResolver`, `ExpressionEvaluator`) |
| escopo | par `scope_type` / `scope_value` concreto |
| valor calculado | `CalculationContext`, chave `CalculationKey(entity_id, scope_type, scope_value, period_id)`; o `ForecastEngine` grava o resultado de cada `EquationInstance` nessa chave |
| contexto de bloco | **não existe** no runtime; a separação por bloco é garantida pelas faixas de ID (`VAR11xxx` yield, `VAR12xxx` production etc.) |
| injeção de entradas | `CalculationContext.set_variable_value(...)` pelo chamador |
| vínculo interbloco | **não existia** |
| testes de resolução | `test_expression_evaluator`, `test_decision_e_spatial_temporal_resolution`, `test_stage2_4_workbook_contract` (A019), testes por bloco |

**Decisão.** A abstração de valores já adequada é o `CalculationContext`, e ela foi reutilizada: o valor do produtor é
lido na chave do produtor e gravado na chave do consumidor. O `ForecastEngine`, o `ExpressionEvaluator`, o
`EquationEngine` e o `reference_resolver` **não foram alterados**. As equações do consumidor continuam lendo o ID do
próprio consumidor. Os fallbacks temporal e espacial do evaluator continuam restritos às referências intrabloco;
o transporte interbloco não passa por eles.

## 3. Componentes alterados e não alterados

Alterados ou criados (commit `e60af19`):

| arquivo | alteração |
|---|---|
| `app/domain/interblock/models.py` | **novo**: `InterblockLink`, `PendingInterblockLink`, `RejectedInterblockLink` |
| `app/domain/interblock/registry.py` | **novo**: `InterblockLinkRegistry` (carga e conferência do artefato canônico, ordem topológica, ciclo) |
| `app/engine/interblock_resolver.py` | **novo**: `InterblockValueResolver` (`resolve`, `transfer`, `transfer_link`, `transfer_all`) |
| `app/engine/exceptions.py` | + hierarquia `InterblockRuntimeError`, com códigos `INTERBLOCK_*` (somente acréscimo) |
| `app/repositories/seed_loader.py` | + `SeedLoader.load_interblock_links()` (somente acréscimo; não entra na tupla de `load_all_definitions_and_instances`) |
| `tests/test_stage3_1_interblock_runtime.py` | **novo**: 37 testes |

Não alterados:
- no runtime: `forecast_engine.py`, `expression_evaluator.py`, `equation_engine.py`, `calculation_context.py`,
  `reference_resolver.py`, `scope_resolver.py`, `temporal_*`, `dependency_*` e os validators;
- `tools/` (builder), `data/seed/**` (seeds e `interblock_links.json`), `data/id_ledger/**` e `data/workbooks/**`;
- todos os testes existentes;
- as evidências de auditoria anteriores.

`git diff --stat 7877551 e60af19` fora de `audit/`: 7 arquivos, 1349 inserções, **0 remoções**. Os finais de linha
CRLF de `exceptions.py` e `seed_loader.py` foram preservados.

## 4. Mecanismo de resolução

```
data/seed/interblock_links.json  +  data/seed/<bloco>/variables.json
        │ InterblockLinkRegistry.from_seed_root (SeedLoader.load_interblock_links)
        ▼
vínculos canônicos conferidos, em ordem topológica (produtor antes)
        │ InterblockValueResolver(registry, CalculationContext)
        ▼
resolve(consumidor, scope_type, scope_value, period_id)
   → CalculationContext.get_variable_value(source_definition_id, mesma instância, mesmo período)
transfer(...) → set_variable_value(consumer_definition_id, mesmo valor, mesma instância, mesmo período)
```

**Carga (registry).** Nenhum registro é aceito sem as conferências abaixo, feitas contra os seeds dos blocos
carregados. Um registro corrompido faz a carga falhar com `INTERBLOCK_SEED_INVALID`.

- campos obrigatórios presentes;
- consumidor e produtor em blocos distintos e carregados;
- cada ID pertence ao seed do bloco declarado;
- frequência e escopo do registro iguais aos da definição;
- mesma frequência no consumidor e no produtor;
- mesma `unit` e mesmo `value_type`;
- instâncias não vazias, sem repetição, existentes no consumidor e no produtor;
- cada consumidor aparece no máximo uma vez entre `links`, `pending` e `rejected`;
- em `pending`: bloco oficial (taxonomia do artefato), não carregado e sem produtor.

Ciclos resultam em `INTERBLOCK_CYCLE`, com o caminho completo, **antes** de qualquer execução.

**Lookup (resolver).** Nunca lê o valor do próprio consumidor. Cada vínculo segue estes passos:

1. Pede ao produtor exatamente a instância solicitada, que precisa estar entre as instâncias do vínculo; caso
   contrário, `INTERBLOCK_INSTANCE_NOT_DECLARED`.
2. Usa exatamente o `period_id` pedido, com a granularidade da frequência do vínculo; caso contrário,
   `INTERBLOCK_PERIOD_FREQUENCY_MISMATCH`. `None` é aceito como modo *snapshot* já existente no runtime.
3. Se o produtor não tem valor, `INTERBLOCK_SOURCE_VALUE_NOT_FOUND`. Não há fallback temporal nem espacial.
4. O valor é transportado sem conversão: o mesmo objeto numérico, com o mesmo tipo.
5. Em `transfer`, um valor local diferente já presente no consumidor resulta em
   `INTERBLOCK_CONSUMER_VALUE_CONFLICT`. Nada é sobrescrito em silêncio.

**Identidade.** O consumidor mantém o próprio ID (ex.: `energy.lth` VAR18008) e o produtor também (production.lth
VAR12031). O vínculo não cria alias, não funde IDs e não faz o consumidor executar a fórmula do produtor.

## 5. Vínculos pendentes

Os 16 vínculos de `pending` apontam para maintenance, temperature_lp, area_04_13, alumina e forecast. Consumir
qualquer um deles gera **`InterblockSourceNotLoadedError`**, código **`INTERBLOCK_SOURCE_NOT_LOADED`**.

- O erro traz bloco consumidor, ID e nome do consumidor, bloco produtor, frequência e escopo.
- Nenhum valor é gravado: não há zero, `None`, valor local, outro bloco nem `source_reference`.
- Vínculos rejeitados geram `INTERBLOCK_LINK_REJECTED` (hoje não há nenhum).
- Um ID sem vínculo gera `INTERBLOCK_LINK_NOT_FOUND`.
- Há os testes `test_13_6`, `test_13_7b` e `test_14_real_pending_links_raise`, e a auditoria sondou os 16 pendentes.

## 6. Cadeias

O registry ordena os vínculos topologicamente, com o produtor antes do consumidor e desempate por ID; o resultado
independe da ordem do artefato. O `transfer_all` percorre essa ordem. A cadeia real funciona assim:

1. `production.lth` (VAR12031) tem o valor;
2. `transfer` grava esse valor em `yield.lth` (VAR11031);
3. `transfer` lê **`yield.lth`**, não o produtor final, e grava em `area_41.lth` (VAR16007).

Os três níveis são verificados em `test_14_real_chain_three_levels`. Sem o salto intermediário, o último salto gera
`INTERBLOCK_SOURCE_VALUE_NOT_FOUND`, sem atalho para o produtor final. A cadeia vem do artefato canônico; o runtime
não lê `fonte`.

## 7. Testes

`tests/test_stage3_1_interblock_runtime.py` tem 37 testes:

| exigido | teste |
|---|---|
| 13.1 lookup simples | `test_13_1_simple_lookup` |
| 13.2 identidade local | `test_13_2_local_identity_is_preserved` |
| 13.3 instância | `test_13_3_instance_is_exact` (L3 recebe só L3; L1 e L1_L7 não servem) |
| 13.4 frequência | `test_13_4_frequency_is_never_substituted` |
| 13.5 cadeia A→B→C | `test_13_5_chain_a_b_c` |
| 13.6 vínculo pendente | `test_13_6_pending_link_is_an_explicit_error` |
| 13.7 seed corrompido | `test_13_7_corrupted_seed_is_not_a_valid_link` (19 corrupções) + `test_13_7b` (rejeitado e inexistente) |
| 13.8 unidade | `test_13_8_no_unit_conversion` (valor e tipo idênticos; unidade divergente rejeitada em 13.7) |
| 13.9 identidade duplicada | `test_13_9_same_name_in_two_blocks_stays_two_entities` |
| 13.10 determinismo | `test_13_10_order_does_not_change_the_result` (ordem de links e blocos embaralhada, 4 sementes) |
| 13.11 ciclo | `test_13_11_cycle_is_rejected_before_execution` |
| 13.12 sem fallback | `test_13_12_no_fallback_of_any_kind` (`source_reference`, outro bloco, outra instância, outra frequência, sem período, valor local) |
| runtime não lê XLSX/`fonte` | `test_runtime_does_not_read_workbooks_or_fonte` (análise AST do código dos três módulos) |
| 14 vínculos reais | `test_14_all_13_real_links_are_consumable`, `test_14_real_chain_three_levels`, `test_14_real_pending_links_raise`, `test_14_real_registry_matches_seed_file`, `test_14_consumer_equation_runs_on_transferred_value` (energy EQ18001 `VAR18001 / 24` executada pelo `EquationEngine` sobre o valor transferido de production.producao: 4800 → 200) |

**LEGACY_TEST_EXPECTATION: nenhum.** Nenhum teste existente falhou nem foi alterado.

Suíte completa: **1533 passed** (1496 + 37).

## 8. Auditoria independente

`evidence/analysis_stage3_1.py` **não importa `app/` nem `tools/`**. O script:

1. **Reconstrói** os 29 vínculos a partir dos manifestos (`source_block`) e das definições do produtor (mesmo nome,
   frequência, tipo de escopo e instâncias). O resultado bate com o artefato: 13 `links` e 16 `pending`, com mesmos
   produtores, instâncias, frequências e unidades.
2. **Observa o runtime como caixa-preta.** `evidence/runtime_probe.py` roda em subprocesso:
   - grava 6462 números **únicos**, um por chave (variável não consumidora × instância × período), incluindo iscas
     em outros períodos (dia vizinho, mês, ano, ano anterior, sem período);
   - executa `transfer_all`;
   - devolve o que cada consumidor recebeu.

   A análise decodifica cada número recebido na chave que o runtime realmente leu.
3. **Resultado:**
   - 67 de 67 transferências por instância leram exatamente a chave esperada: produtor raiz, mesma instância, mesmo
     período;
   - 0 leituras de isca, de outro bloco, de outra instância ou de outra frequência;
   - 16 de 16 pendentes resultaram em `INTERBLOCK_SOURCE_NOT_LOADED`;
   - **0 divergências**.

A evidência por instância está em `evidence/runtime_link_evidence.csv`, e as pendências em
`evidence/runtime_pending_evidence.csv`.

## 9. Determinismo

- A ordem dos vínculos vem de ordenação topológica com desempate por ID. Nenhum dicionário não ordenado, timestamp ou
  aleatoriedade entra no resultado.
- `test_13_10`: artefato e blocos embaralhados com 4 sementes dão a mesma ordem e as mesmas transferências.
- `evidence/determinism_check.txt`: a auditoria completa com `PYTHONHASHSEED` 0, 424242 e 7 produz resumo com o
  mesmo SHA-256.

## 10. Critérios de aceite

| # | critério | situação |
|---|---|---|
| 1 | 13 vínculos consumíveis | sim (teste 14 e auditoria 67/67) |
| 2 | pendentes sem valor fictício | sim (erro explícito, nada gravado) |
| 3 | cadeias | sim (3 níveis reais) |
| 4 | identidades distintas | sim |
| 5 | IDs inalterados | sim (seeds e livro de IDs intocados) |
| 6 | sem conversão de unidade | sim |
| 7 | sem fallback temporal/espacial interbloco | sim (testes 13.3, 13.4, 13.12; iscas da auditoria) |
| 8 | runtime não consulta XLSX | sim (verificação AST) |
| 9 | runtime não resolve `fonte` | sim (consome só o artefato canônico) |
| 10 | contrato canônico | sim |
| 11 | testes unitários e de integração | 37 passed |
| 12 | suíte completa | 1533 passed |
| 13 | auditoria sem divergências | 0 divergências |
| 14 | determinismo | sim |
| 15 | nenhum código de `app/` não relacionado alterado | sim (só acréscimos em exceptions/seed_loader e módulos novos) |
| 16 | nenhum workbook alterado | sim |
| 17 | nenhum contrato reaberto | sim (D24-11/12, D25-01..04, D26-01..03 e o livro de IDs intocados) |

**Fronteira desta etapa, que não é pendência.** O transporte é uma API explícita (`transfer`, `transfer_link`,
`transfer_all`) chamada pelo orquestrador. A execução multibloco coordenada ainda não foi feita:

1. equações do produtor;
2. transferência;
3. equações do consumidor, por período.

Isso fica para a próxima subetapa, que não foi iniciada. O `ForecastEngine` não foi alterado.

## 11. Push

Os commits `e60af19` e o de evidências são enviados com `git push -u origin feature/area-41-block`. Nenhum PR foi
criado.

STAGE_3.1_GATE: PASS
