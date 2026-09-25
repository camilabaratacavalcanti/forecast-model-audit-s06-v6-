# Fechamento do contrato conceitual de estados, resultados heterogêneos e erros (Etapa 2.1)

Artefato de auditoria **read-only**: nenhum arquivo de produção, seed,
workbook, builder ou teste existente foi alterado. Baseline: branch
`claude/funny-noether-nbcr7b`, HEAD `196776c682a7ec28546d0f5436de933964cb8779`
(ver `evidence/baseline.txt`), suíte em 1414 passed antes e depois desta
etapa. Esta etapa fecha, em nível conceitual, o contrato de
`value_type`/estado especial/erro técnico aberto com gate
`READY_WITH_CONDITIONS` na Etapa 2 (`audit/stage2_typing_contract/`), que é
tratada aqui apenas como evidência histórica, não como base a ser
re-executada indiscriminadamente.

## Reprodução

```bash
python3 audit/stage2_1_result_state_contract/probes/probes_2_1.py   # regrava evidence/probes_2_1_results.json e os CSVs de detalhe
python3 -m pytest -q                                                 # 1414 passed
```

## Conteúdo

| arquivo | conteúdo |
|---|---|
| `REPORT.md` | relatório completo nas 20 seções pedidas: sumário executivo, baseline, escopo, hipótese arquitetural, comportamento atual do runtime, estudo de caso A41 (`retirada_condensado_grupo@L4_L5`), taxonomia de estados, declaração de resultado especial (D2), propagação (D3), agregação (D4), categorias permitidas (D5), contrato de `value_type` (D6/D9), estado vs. exceção (D7), matriz de responsabilidade (D8), generalização transversal (D10, incluindo o caso `"ERRO!!!"`), matriz de cenários C01–C16, decisões abertas, contrato proposto, impacto esperado na Etapa 3, e gate final |
| `probes/probes_2_1.py` | probes independentes desta etapa (fixtures `VAR95xxx`, distintas das `VAR96xxx` da Etapa 2), incluindo a extração e avaliação da fórmula real do workbook v6 (célula M39), o probe de domínio de categoria, a matriz de propagação multi-hop, os probes de agregação espacial vs. temporal, e o estudo de caso `"ERRO!!!"` |
| `evidence/baseline.txt` | branch, HEAD, status do working tree, referência ao artefato da Etapa 2, cauda do pytest |
| `evidence/probes_2_1_results.json` | saída bruta consolidada de todos os probes desta etapa |
| `evidence/state_taxonomy_matrix.csv` | 6 candidatos a estado (VALID, NO_APPLICABLE_RULE, INVALID_INPUT, VALIDATION_FAILED, UNAVAILABLE/DATA_NOT_YET_READY, TECHNICAL_ERROR), cada um classificado como EVIDENCIADO ou NÃO EVIDENCIADO/OPEN DECISION |
| `evidence/value_type_state_matrix.csv` | `value_type` (numeric/categorical) × {resultado válido, estado especial, erro técnico} |
| `evidence/propagation_matrix.csv` | matriz produtor\|estado\|consumidor\|comportamento (8 linhas, reproduz F-001 com o cenário mínimo A→estado, B→valor independente, C depende de A, D depende de B) |
| `evidence/aggregation_matrix.csv` | comparação das 4 políticas de agregação (A=ignorar, B=invalidar, C=parcial sinalizado, D=outra) com o exemplo Dia1=100, Dia2=110, Dia3=estado especial, AVERAGE |
| `evidence/category_contract_matrix.csv` | as questões de D5 respondidas com `hes@L4`/`hes@L5` como caso real |
| `evidence/state_error_matrix.csv` | matriz situação\|value\|state\|exception, com `ln(-10)` como caso obrigatório de erro técnico |
| `evidence/responsibility_matrix.csv` | matriz de responsabilidade (contrato × workbook/engenheiro, builder, parser, evaluator, engine, storage, aggregator) |
| `evidence/scenario_matrix.csv` | matriz de cenários conceituais C01–C16, cada um classificado SUPPORTED/UNSUPPORTED/AMBIGUOUS/OPEN DECISION |
| `evidence/d3_propagation_detail.csv`, `evidence/state_error_boundary.csv`, `evidence/scenario_matrix_detail.csv` | saídas suplementares dos probes desta etapa, base para os CSVs canônicos acima |

## Gate final

**CONTRACT CLOSED WITH OPEN ITEMS** — ver `REPORT.md` §20 para o bloco
`STAGE 2.1 RESULT` completo, os 4 itens em aberto (mecanismo exato de
declaração dentro de D2, rótulos de estado por variável, política de
propagação de erro técnico como distinta da de estado, e o estado
`UNAVAILABLE` explicitamente excluído da taxonomia por falta de evidência) e
a autocrítica de 16 perguntas (§20/§31 do prompt mestre).
