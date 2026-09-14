# Yield E2E — Cadeia Real Executada

Executada em `audit/yield_e2e_readiness/tests/yield_e2e_readiness_tests.py`,
seção 4, usando exclusivamente componentes reais (`SeedLoader`,
`ForecastEngine`, `DependencyGraph`, `EquationEngine`, `CalculationContext`).

## Cadeia

```
PARAM11003 (tanque_base@L4, VALOR REAL do seed: 18)
VAR11239   (tanque@L4, SYNTHETIC TEST VALUE: 12.0)
    ↓
EQ11004 (n_ppt@L4)         expression = "PARAM11003 - VAR11239"
    ↓  n_ppt@L4 = 18 - 12 = 6.0
    ↓
EQ11006 (ratio_spent@L4)   depende de n_ppt@L4, ratio_spent_base, eoc_temp,
                           eoc_solids, ltp_tc, ltp, ssa_media (e seus "_base")
    ↓  ratio_spent@L4 = 0.52  (SYNTHETIC — depende de inputs sintéticos)
    ↓
EQ11001 (yield@L4)         expression = "(ltp_a_c - ratio_spent)*ltp_tc - 0.654*sl_solids"
    ↓  yield@L4 = 175.98  (SYNTHETIC)
    ↓
EQ11011 (yield@L1_L3, agregação)  yield@L1_L3 = 171.43 (SYNTHETIC, agregado de L1/L2/L3)
```

## Por que esta cadeia

Atravessa o maior número de componentes possível dentre as 106 equações:

- um **parâmetro real do seed** (`tanque_base`, 7 `ParameterDefinition`
  materializadas por linha, valores reais 14/14/16/18/18/18/18);
- uma **variável de entrada** (`tanque`, `VariableDefinition` única
  materializada em 7 `VariableInstance`);
- uma equação com **referência sem escopo dupla** (`n_ppt`: `PARAM11003 -
  VAR11239`, ambas resolvidas contextualmente para L4);
- uma equação **intermediária com múltiplas dependências** (`ratio_spent`,
  7 termos, mistura variáveis diárias e anuais "_base");
- o **output funcional por linha** (`yield`);
- a **agregação `linha_grupo`** que produz o output final.

## Inputs (com marcação explícita de origem)

| Identificador | Origem | Valor |
|---|---|---|
| `PARAM11003` (tanque_base, todas as 7 linhas) | **REAL** — `data/seed/yield/parameters.json` | 14, 14, 16, 18, 18, 18, 18 |
| `PARAM11001`/`PARAM11002` (ltp_tc / ltp_tc_base) | **REAL** — seed | 273 (ambos) |
| `VAR11239` (tanque, todas as 7 linhas) | **SYNTHETIC TEST VALUE** — não há leitura diária real disponível nesta auditoria | 12.0 |
| `lth, oee, ltp_lth, ltp_a_c, sl_solids, ssa_sf, ssa_sg, eoc_temp, eoc_solids` (diário) | **SYNTHETIC TEST VALUE** | ver script |
| `*_base` (anual, exceto ltp_tc_base/ratio_spent_base cobertos pelo seed) | **SYNTHETIC TEST VALUE** | ver script |

Nenhum valor sintético é apresentado como resultado funcional do Yield —
servem exclusivamente para provar que a infraestrutura calcula
corretamente a cadeia completa quando os inputs existem.

## Execution order (trecho relevante, ordem topológica real)

```
...
EQ11004@linha:L4          (n_ppt@L4)          — sem dependências (leaf: PARAM/VAR são inputs)
...
EQ11006@linha:L4          (ratio_spent@L4)    — depende de EQ11002@L4, EQ11003@L4, EQ11004@L4, EQ11008@L4, EQ11009@L4
...
EQ11001@linha:L4          (yield@L4)          — depende de EQ11006@L4
...
EQ11011@linha_grupo:L1_L3 (yield@L1_L3)       — depende de EQ11001@L1, EQ11001@L2, EQ11001@L3, EQ11002@L1, EQ11002@L2, EQ11002@L3
```

(ordem completa nas 166 linhas de `yield_e2e_dependency_matrix.csv`,
coluna `execution_order`)

## Resultado

```
PASS — cadeia completa executada sem exceção, valores calculados
       conferidos manualmente (n_ppt@L4 = 18-12 = 6, exato)
```

## Execução do conjunto completo (106 EquationDefinitions / 166 Instances)

```
ForecastEngine.calculate_from_definition_registry(
    equation_definition_registry=<106 EquationDefinitions reais>,
    calculation_context=<inputs reais do seed + SYNTHETIC TEST VALUES>,
)
→ PASS
→ 166/166 resultados retornados (100% das instances esperadas)
→ tempo de execução: ~26ms
→ 0 exceções (VariableNotFoundError, ParameterNotFoundError, DependencyCycleError)
```
