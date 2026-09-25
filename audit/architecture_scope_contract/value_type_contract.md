# Contrato `value_type` / `variable_type` / `"F"`

Níveis: **OBSERVED** = lido no código ou executado; **DERIVED** = conclusão
lógica tirada do observado; **RECOMMENDATION** = sugestão para uma etapa
futura. As sondas citadas (Txx) estão em `negative_tests_results.json`.

## OBSERVED

| item | evidência |
|---|---|
| `VALUE_TYPES = {"numeric", "categorical"}` e `CONDITIONAL_FAILURE = "F"` | `app/domain/values.py:28`, `:30`; sonda T09 |
| `VariableDefinition.value_type` (padrão `"numeric"`), validado em `__post_init__`; qualquer outro valor → `ValueError` | `app/domain/variables/models.py:67,86`; sonda T01 (`'mixed'` rejeitado) |
| `Variable.value_type` (modelo legado), repassado por `from_variable` | `app/domain/variables/models.py:41,82` |
| Validador de seed: `value_type` é campo **opcional**, com enum `VALUE_TYPES` | `app/validation/variable_seed_validator.py:217` (`ENUM_FIELDS`) |
| `ParameterDefinition` não tem `value_type`; parâmetros são só numéricos, e `"F"` em parâmetro → `CalculationValueError` | `app/engine/calculation_context.py` (`set_parameter` → `_validate_single_value`); sonda T05 |
| `CalculationContext` aceita texto apenas em variáveis declaradas categóricas | `_validate_variable_value`; sondas T02/T03 |
| O `ForecastEngine` declara as categóricas a partir de `VariableDefinition.is_categorical` | `app/engine/forecast_engine.py:317` |
| `"F"` é aceito como valor de **qualquer** variável, inclusive numérica | `_validate_variable_value` (`is_conditional_failure`); sonda T04 |
| Consumir `"F"` (aritmética, `ln`, ordenação, condição, igualdade com outro valor) → `ConditionalFailureError`; a única leitura permitida é a comparação com o literal `== "F"` | `app/engine/expression_evaluator.py` (`_require_numeric`, `_compare`); sondas T06/T07 |
| Agregação de série com `"F"` → `AggregationFailureError`, listando os períodos | `app/engine/temporal_aggregation_service.py` (`_require_numeric_series`); sonda T08 |
| `ForecastValue.value: ScalarValue` (= `int \| float \| str`) | `app/domain/forecast/models.py:53` |
| `variable_type` ∈ {`entrada`, `entrada_externa`, `calculado`, `saída`}, campo obrigatório | `app/validation/variable_seed_validator.py:84` (`ALLOWED_VARIABLE_TYPES`), `REQUIRED_VARIABLE_FIELDS` |
| Nenhum seed de produção declara `value_type`; todos usam o padrão `numeric` | varredura de `data/seed/*/variables.json`: 0 ocorrências |

## DERIVED

- `variable_type` e `value_type` são dimensões **ortogonais**:
  - `variable_type` diz o papel da variável no modelo (de onde vem o valor);
  - `value_type` diz o tipo do valor normal.
  - Seus conjuntos de valores são disjuntos, e o código não usa um no lugar do outro.
- `"F"` **não** é um terceiro `value_type`. É um sentinela de estado
  excepcional (falha da rotina IF), ortogonal a `value_type`. Exemplo:
  `retirada_condensado_grupo`, com `value_type = numeric`, tem resultado normal
  numérico e resultado excepcional `"F"`. A arquitetura atual já representa
  esse caso sem um tipo `mixed`, e `mixed` é rejeitado (T01).
- A taxonomia suportada hoje tem exatamente 2 tipos (`numeric`,
  `categorical`), mais o sentinela `"F"`.
- `value_type` é um mecanismo **transversal** (domínio, validador, contexto e
  engine), e não específico do A41.

## RECOMMENDATION (não aplicada)

- Ao adicionar `value_type` aos workbooks:
  - declarar `categorical` apenas nas variáveis cujo valor **normal** é texto;
  - **não** criar `mixed` para variáveis que podem resultar em `"F"`.
- Parâmetros categóricos não são suportados. Se forem necessários, isso é uma
  extensão de contrato, a ser decidida explicitamente.
