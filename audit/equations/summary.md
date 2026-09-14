# Reconciliação funcional — 106 EquationDefinitions do Yield

Auditoria executada em `claude/funny-noether-nbcr7b`, sem alterações ao produto.
Script gerador: `audit/equations/reconcile.py` (reprodutível — lê apenas o seed
real e o workbook funcional, escreve apenas em `audit/equations/`).

## Baseline confirmado

```
python -m pytest -q  →  740 passed, 0 failed, 0 skipped, 0 errors
```

Sem alterações prévias não documentadas. Repositório limpo antes e depois da auditoria.

## Inventário

- **106 EquationDefinitions** confirmadas em `data/seed/yield/equations.json`
  (`len(equations) == 106`, checado programaticamente).
- **166 EquationInstances** materializadas via `SeedLoader` real (10 definições
  `linha/L1_L7` × 7 linhas = 70, + 96 definições `linha_grupo` × 1 instance = 96).
- **100% status PUBLISHED** — nenhuma DRAFT/PENDING/REJECTED no seed atual.

## Distribuição scope_type/scope_value

| scope_type | scope_value | quantidade |
|---|---|---:|
| linha | L1_L7 | 10 |
| linha_grupo | L1_L3 | 32 |
| linha_grupo | L4_L5 | 32 |
| linha_grupo | L6_L7 | 32 |

Nenhuma equação em `linha_grupo/L1_L7` (agregação de toda a planta) —
consistente com a decisão registrada na Fase 3A de não seedar esse grupo
(anomalia de encadeamento de pesos identificada na fonte). Nenhuma equação
`área`/`global` no bloco Yield.

## Resultado da reconciliação (classificação principal)

| Classificação | Quantidade |
|---|---:|
| MATCH | 105 |
| SEMANTIC_MATCH | 1 |
| NORMALIZED_MATCH | 0 |
| FORMULA_DISCREPANCY | 0 |
| SCOPE_DISCREPANCY | 0 |
| TARGET_DISCREPANCY | 0 |
| DEPENDENCY_DISCREPANCY | 0 |
| CONSTANT_DISCREPANCY | 0 |
| AGGREGATION_DISCREPANCY | 0 |
| MATERIALIZATION_DISCREPANCY | 0 |
| STATUS_DISCREPANCY | 0 |
| MISSING_IN_PLATFORM | 0 |
| EXTRA_IN_PLATFORM | 0 |
| SOURCE_UNCLEAR | 0 |
| **Total** | **106** |

A classificação principal soma exatamente 106.

## Severidade

| Severidade | Quantidade |
|---|---:|
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |
| P3 | 0 |
| INFO | 106 |

Nenhum P0/P1/P2/P3 identificado nas 106 equações. Duas notas INFO
(`historical/source note`) documentadas abaixo — não são correções
pendentes.

## As duas equações com nota INFO

### EQ11004 — `n_ppt` (linha/L1_L7) — SEMANTIC_MATCH

Fonte (linha 14 do workbook): `tanque_base_L1@ - tanque_L1@` (notação
current-line, seção 15 desta auditoria). Plataforma:
`PARAM11003 - VAR11239` (= `tanque_base - tanque` em nomes), referência
sem escopo, resolvida contextualmente pela `EquationInstance` — a forma
que a seção 16 determina como correta. Equivalência comprovada por
execução real (`test_fase3a_contextual_resolution_integration.py::
test_c5_n_ppt_full_stack_all_lines`), não apenas por leitura estática, para
as 7 linhas.

### EQ11006 — `ratio_spent` (linha/L1_L7) — MATCH (vs Nível 1) + nota histórica

A fórmula implementada é **idêntica, termo a termo**, à regra de negócio
aprovada (seção 4.1), incluindo o coeficiente `0.0007`. Comparada contra o
workbook (Nível 2), 5 dos 7 termos são idênticos; 2 termos (`LTP` e
`SSAmedia`) têm **sinal invertido** entre a regra aprovada e o workbook —
já identificado e resolvido em fases anteriores desta auditoria, registrado
aqui apenas como nota histórica, não como pendência (ver seção 4.1: a regra
aprovada prevalece).

## Tanque / tanque_base

- `tanque`: **uma única** `VariableDefinition` (`VAR11239`, `linha/L1_L7`),
  materializada em 7 `VariableInstance` (`VAR11239@L1`...`@L7`) — não
  existem `tanque_L1`...`tanque_L7` como definições distintas no seed atual
  (removidas na Fase 3A). A fonte usa 7 linhas nomeadas `tanque_L1`...`tanque_L7`
  (linhas 249–255); a modelagem única é a representação funcional
  equivalente, por decisão explícita (seção 5).
- `tanque_base`: **um único** `parameter_definition_id` (`PARAM11003`),
  com 7 `ParameterDefinition` (uma por linha) e valores
  `14, 14, 16, 18, 18, 18, 18` — idênticos aos das 7 linhas
  `tanque_L1_base`...`tanque_L7_base` do workbook (linhas 242–248).
  Confirmado valor a valor.

## Agregações de planta/área investigadas

| Conceito | Encontrado na fonte | Encontrado na plataforma | Nota |
|---|---|---|---|
| Weighted EOC temperature | Sim (`eoc_temp`, 10 linhas) | Sim (3 EquationDefinitions, uma por grupo) | Só existe como agregação `linha_grupo`; não há equação "diária/linha única" própria (eoc_temp é entrada externa por linha) |
| Weighted EOC solids | Sim (`eoc_solids`, 10 linhas) | Sim (3 EquationDefinitions) | Idem |
| Base production sum | Sim (`producao_base_ppt`, 10 linhas) | Sim (4 EquationDefinitions: 1 diária linha única + 3 grupos) | Soma simples nos grupos, conforme fonte |
| Tank sum | **Não** | — | Nenhuma linha do workbook do Yield usa esse nome/conceito |
| Ratio DBO Planta | **Não** | — | Nenhuma linha do workbook do Yield usa esse nome/conceito |

"Tank sum" e "Ratio DBO Planta" não têm nenhuma evidência de existirem no
workbook funcional do Yield — não classificados como `MISSING_IN_PLATFORM`
por ausência de evidência de que sejam regras reais desta fonte (seção 52:
não adivinhar).

## Instances (materialização)

166/166 instances esperadas foram materializadas (ver `instances_matrix.csv`).
Nenhuma definição com contagem de instances divergente do esperado pelo
`scope_type`/`scope_value` declarado.

## Testes

```
Targeted:
  audit/equations/reconcile.py → 106/106 processadas, sem exceções
  tests/test_yield_seed_integration.py → 10 passed
  tests/test_fase3a_contextual_resolution_integration.py → 14 passed

Full suite:
  python -m pytest -q → 740 passed, 0 failed, 0 skipped, 0 errors
```

Nenhuma alteração foi feita a testes, seeds, código de produto ou
contratos arquiteturais durante esta auditoria.
