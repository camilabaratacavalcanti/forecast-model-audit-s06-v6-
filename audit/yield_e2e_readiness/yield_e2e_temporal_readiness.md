# Yield E2E — Prontidão Temporal

## Evidência

```
grep -n "period_id\|TimePeriodResolver" app/engine/*.py app/repositories/*.py
```

- `TimePeriodResolver` (`app/engine/time_period_resolver.py`) existe, gera
  `TimePeriod` diário/mensal a partir de um horizonte de datas.
- `CalculationKey` (`app/engine/calculation_context.py`) tem um campo
  opcional `period_id: str | None = None` — a API contextualizada
  (`get/set_variable_value`, `get/set_parameter_value`) já aceita
  `period_id` como parâmetro.
- **Nenhum ponto do fluxo real usado pelo Yield popula `period_id`.**
  `ForecastEngine.calculate_from_definition_registry` chama
  `calculation_context.set_variable_value(..., scope_type=instance.scope_type,
  scope_value=instance.scope_value)` — sem `period_id` — para as 166
  instances, confirmado por leitura direta do código e por execução (os
  166 resultados foram armazenados com `period_id=None` implícito).
- `TimePeriodResolver` não é importado por `forecast_engine.py`,
  `equation_engine.py` nem `calculation_context.py`.

## Single-period Yield E2E

```
YES
```

Comprovado por execução real (seção 4 do experimento): uma execução de
`calculate_from_definition_registry` produz um snapshot coerente das 166
`EquationInstance`, todas as 106 `EquationDefinition` corretamente
ordenadas e calculadas. Não há necessidade de período para isso — o motor
já opera como "um cálculo == um snapshot".

## Multi-period Yield E2E

```
NO
```

Razões, demonstradas por inspeção (não requer execução, pois é ausência de
código, não comportamento incorreto):

1. `CalculationContext` é um objeto em memória, recriado a cada chamada —
   nada persiste valores de uma execução para reuso em outra.
2. Mesmo que `period_id` fosse passado manualmente pelo chamador (a API
   aceita), `ForecastEngine.calculate_from_definition_registry` não o
   aceita como parâmetro nem o propaga — teria que ser reescrito para
   materializar/armazenar por período.
3. Não existe `CalculationRun` (ou equivalente) para identificar/versionar
   uma execução específica associada a um período.
4. As equações "mensal" (rows 162+ do workbook, ex.: `yield` mensal =
   "Média dos dados entre os dias 01 e 30 ou 31 de cada mês") **não têm
   fórmula matemática representável pelo `ExpressionParser` atual** — são
   texto descritivo, não uma expressão. Isso não foi seedado (ver
   reconciliação anterior) e não haveria como seedá-lo sem: (a) uma função
   de agregação temporal (média sobre N valores diários) que o
   `ExpressionEvaluator` atual não suporta (só `+ - * / ** %`), e (b) uma
   ponte entre `TimePeriodResolver` e o `CalculationContext`/`EquationEngine`.

## Resposta objetiva

```
Yield single-period E2E: YES
Yield multi-period E2E: NO
```

## Impacto

Não bloqueia a execução E2E das 106 `EquationDefinitions` reconciliadas
(todas de frequência `diário`/`anual`, calculadas como snapshot único).
Bloqueia especificamente:
- recálculo automático dia-a-dia com retenção de série histórica;
- as equações de frequência `mensal` do workbook (fora do conjunto de 106
  reconciliadas — nunca foram seedadas, por decisão já registrada na
  Fase 3A).

Ver GAP-01 e GAP-04 em `yield_e2e_gap_register.csv`.
