# Contratos da plataforma — correções estruturais pré-A41

Cada contrato abaixo é demonstrado pelos testes indicados. Nenhum é
específico de bloco.

| # | Contrato | Implementação | Testes |
|---|----------|---------------|--------|
| A | Referência por **nome + frequência + escopo**. Uma definição por grupo é vinculada ao escopo do consumidor (linha → grupo que a contém → planta). Um consumidor cujas instâncias veriam definições diferentes, ou duplicatas sem desempate, é **erro explícito**. O sufixo `@escopo` faz parte da identidade. Texto entre aspas não é traduzido. | `app/engine/reference_resolver.py` (usado por `tools/energy_seed_builder.py` e `tools/max_ht_seed_builder.py`) | `tests/test_reference_resolver.py` |
| B | Uma `AggregationRule` gera uma **`AggregationRuleInstance` por escopo concreto** em que alvo, origem e peso existem (`linha/L1_L7` → L1..L7). Cada instância lê e grava apenas o próprio escopo. Uma regra sem nenhum escopo aplicável gera `AggregationScopeMismatchError`. | `ScopeResolver.resolve_aggregation_rule`, `SeedLoader.load_aggregation_rule_instances`, `TemporalForecastOrchestrator.run_aggregation_instance` | `tests/test_aggregation_rule_instances.py` |
| C | `VAR@L1_L3`, `@L4_L5`, `@L6_L7`, `@L1_L7` são **referências espaciais** (`linha_grupo`), nunca o operador `@`. Os escopos aceitos são os do `ScopeResolver`. Uma referência explícita é resolvida só no próprio escopo (fallback apenas temporal). O grafo ordena o produtor do grupo antes do consumidor. | `app/engine/scoped_reference.py`, parser, evaluator, `DependencyExtractor`, `DependencyGraph`, `ForecastEngine._build_instance_variable_producers` | `tests/test_dsl_structural_contracts.py` (Fase C) |
| D | `ln(x)` é a única função da allowlist: chamada pelo nome, 1 argumento posicional. `x <= 0` gera `MathDomainError`, texto gera `ExpressionTypeError` e `"F"` gera `ConditionalFailureError`. Qualquer outra chamada, atributo, lambda ou `*args`/`**kw` é rejeitada na análise (`UnsafeExpressionError`). Nada de eval/exec. | `ALLOWED_FUNCTIONS` (parser), `FUNCTIONS` (evaluator) | Fase D |
| E | Valores: `ScalarValue = int \| float \| str`. Uma variável é `numeric` (padrão) ou `categorical` (`value_type`, opcional no seed). O contexto só aceita texto em variáveis categóricas. Parâmetros são só numéricos. | `app/domain/values.py`, `VariableDefinition.value_type`, `CalculationContext` | Fase E |
| F | Constantes de texto só como resultado, ramo de IF ou operando de comparação. `and`/`or` só entre condições, na condição de um IF, com curto-circuito e a precedência do Python (`and` antes de `or`). `==`/`!=` valem entre texto e texto ou número e número; texto com número é erro. Ordenar texto é erro. Resultado final booleano é erro. `not` continua proibido. | parser, evaluator | Fase F |
| G | `"F"` = falha da rotina IF. Pode ser gravado em qualquer variável e repassado sem alteração. Consumi-lo (aritmética, `ln`, ordenação, condição, `and`/`or`, igualdade com outro valor) gera `ConditionalFailureError`. A única leitura permitida é `x == "F"` / `x != "F"` contra o literal. Uma agregação cuja série contém `"F"` gera `AggregationFailureError`, com os períodos afetados. Texto categórico não é agregável (`NonNumericAggregationError`). | evaluator, `TemporalAggregationService` | Fase G |
| H | `AggregationRule.integration_factor` (padrão 1, só em SUM) converte taxa em quantidade do período. `find_sum_dimension_issues` relata as SUMs dimensionalmente incoerentes. | `app/domain/units.py`, `app/validation/aggregation_dimension_validator.py` | `tests/test_aggregation_dimensions.py` |

## Pendências de dados (não alteradas — decisão do dono do bloco)

- **max_ht, 34 SUMs** de `kg/h`/`m³/h` para `kg|m³/mês|ano`. O workbook
  descreve o destino como "soma dos resultados diários". A correção
  dimensional exige `integration_factor: 24` e a premissa de dia de
  24 h. Nenhum desses destinos é `saída` nem é consumido por equação.
  O teste fixa exatamente esse conjunto e demonstra que o fator 24 o
  resolve.
- **production, 3 SUMs** `tpd → tpd`: é um rótulo de unidade (o destino
  deveria ser `t/mês`/`t/ano`). O fator exigido é 1.
