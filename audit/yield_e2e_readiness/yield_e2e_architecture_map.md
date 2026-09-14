# Yield E2E — Mapa de Arquitetura Real

Fluxo auditado, com o veredito de cada transição, evidência e componente
responsável. Todas as transições foram exercitadas por execução real
(script `audit/yield_e2e_readiness/tests/yield_e2e_readiness_tests.py`),
exceto onde indicado.

| # | Transição | Status | Componente | Evidência |
|---|---|---|---|---|
| 1 | INPUT VALUES → Seed/Input Data | SUPPORTED | `data/seed/yield/*.json` | 245 variables, 9 parameters, 106 equations carregados |
| 2 | Seed → Variable/ParameterDefinitions | SUPPORTED | `SeedLoader.load_variable_definitions/load_parameter_definitions` + validators | 239 `VariableDefinition`, 9 `ParameterDefinition` (execução real) |
| 3 | Definitions → Variable/ParameterInstances | SUPPORTED | `SeedLoader.load_variable_instances/load_parameter_instances` + `ScopeResolver` | 521 `VariableInstance`, 21 `ParameterInstance` (execução real) |
| 4 | Seed → EquationDefinitions | SUPPORTED | `SeedLoader.load_equation_definitions` | 106/106, status 100% `PUBLISHED` |
| 5 | EquationDefinitions → EquationInstances | SUPPORTED | `ForecastEngine.materialize_equation` → `ScopeResolver.resolve_equation` | 166 instances (70 de `linha/L1_L7`×7 + 96 de `linha_grupo`×1) |
| 6 | EquationInstances → DependencyGraph | SUPPORTED | `DependencyGraph.add_instance` | 166 nós, 168 arestas, construído sem exceção |
| 7 | DependencyGraph → DependencyResolver (ordem) | SUPPORTED | `DependencyResolver.resolve` | ordem topológica de 166 nós, determinística (2 execuções idênticas), 0 ciclos |
| 8 | Ordem → ScopeResolver (materialização) | SUPPORTED | já coberto na transição 5 | — |
| 9 | Execução → CalculationContext (armazenamento/leitura) | SUPPORTED | `CalculationContext.set/get_variable_value` | usado em todas as 166 avaliações |
| 10 | Expressão → ExpressionParser/Evaluator | SUPPORTED | `ExpressionParser.parse` + `ExpressionEvaluator.evaluate` | 166/166 expressões avaliadas sem erro de parsing |
| 11 | Avaliação → EquationEngine | SUPPORTED | `EquationEngine.calculate_instance` | usado para as 166 instances |
| 12 | EquationEngine → Calculated VariableInstances | SUPPORTED | `ForecastEngine.calculate_from_definition_registry` (`set_variable_value` por instance) | 166 valores calculados e recuperáveis via `CalculationContext.get_variable_value` |
| 13 | Calculated Instances → Intermediate Results (próxima equação) | SUPPORTED | `DependencyGraph` + ordem topológica | cadeia real comprovada: `n_ppt`→`ratio_spent`→`yield` (linha L4) |
| 14 | Intermediate → Final Yield Outputs | SUPPORTED | ver seção "Outputs" abaixo | `yield@L1_L3`/`L4_L5`/`L6_L7` nunca são dependência de outra equação — são folhas de saída |
| 15 | Final Outputs → Aggregations (linha_grupo) | SUPPORTED | equações `linha_grupo` reais (96/106) | `yield@L1_L3` calculado a partir de `yield@L1/L2/L3` + `ltp@L1/L2/L3` (peso) |
| 15b | Aggregations → planta inteira (`linha_grupo/L1_L7`) | NOT_SUPPORTED | — | nenhuma `EquationDefinition` nesse scope (0/106); decisão da Fase 3A de não seedar (anomalia na fonte) — ver GAP-06 |
| 16 | Resultado → Time Period | NOT_SUPPORTED | `TimePeriodResolver` existe mas não é chamado por `ForecastEngine`/`EquationEngine`/`CalculationContext` em nenhum ponto do fluxo real | `grep period_id app/engine/forecast_engine.py` → 0 ocorrências; ver GAP-01 |
| 17 | Resultado → Forecast Result persistido | NOT_SUPPORTED | nenhum repository grava `VariableInstance`/resultado calculado | inspeção de `app/repositories/` (só `seed_loader.py`); ver GAP-02 |

## Caminho de execução de alto nível (Engine)

| Método | Nível | Filtra status? | Usado para o Yield? |
|---|---|---|---|
| `EquationEngine.calculate_instance` | baixo (avalia 1 instance) | n/a | Sim, internamente |
| `ForecastEngine.calculate` | baixo (recebe lista já selecionada) | NÃO (deliberado, documentado) | Não usado diretamente para Yield |
| `ForecastEngine.calculate_from_registry` | alto (fluxo legado `Equation`/`EquationRegistry`) | SIM (`EquationSelector.ACTIVE_STATUSES`) | Não — Yield usa o fluxo de Definition/Instance |
| `ForecastEngine.calculate_from_definition_registry` | alto (fluxo `EquationDefinition`/`EquationInstance`) | SIM (`EquationSelector.ACTIVE_STATUSES`) | **Sim — é o método real usado nesta auditoria e o único apto para as 106 `EquationDefinitions`** |

`EquationSelector.select_definition()` existe como utilitário de seleção
por escopo/versão, mas **não é chamado** por
`calculate_from_definition_registry` — o filtro de status ali é aplicado
diretamente sobre `equation_definition_registry.all()`. Isso é consistente
com o que a Fase 3A implementou e testou; não é um gap (comportamento
correto e comprovado, ver `tests/test_fase3a_status_filtering.py`).

## Outputs

| Variável | Papel | Produzida por | Escopo | Consumida por outra equação? |
|---|---|---|---|---|
| `n_ppt` (VAR11012) | INTERMEDIATE | EQ11004 | linha/L1_L7 | Sim (EQ11006 `ratio_spent`, e agregações `linha_grupo`) |
| `ratio_spent` (VAR11008) | INTERMEDIATE | EQ11006 | linha/L1_L7 | Sim (EQ11001 `yield`, e agregações `linha_grupo`) |
| `yield` (VAR11001) | INTERMEDIATE (por linha) | EQ11001 | linha/L1_L7 | Sim (as 3 agregações `linha_grupo` de `yield`) |
| `yield` (VAR11016/11032/11048) | **FINAL_OUTPUT** | EQ11011/EQ11027/EQ11043 | linha_grupo/L1_L3, L4_L5, L6_L7 | **Não — comprovado programaticamente (nenhuma das 106 expressões referencia essas 3 variáveis)** |

Onde o valor fica armazenado: no objeto `CalculationContext` passado pelo
chamador de `calculate_from_definition_registry` (em memória, ver GAP-02
para persistência). Outra parte da plataforma recupera o valor chamando
`calculation_context.get_variable_value(variable_id=..., scope_type=...,
scope_value=...)` enquanto o mesmo processo/objeto estiver vivo.
