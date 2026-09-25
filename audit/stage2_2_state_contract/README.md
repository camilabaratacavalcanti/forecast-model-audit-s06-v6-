# Fechamento formal do contrato de estados, resultados especiais e fronteira valor × estado × erro (Etapa 2.2)

Artefato de auditoria **read-only**: nenhum arquivo de produção, seed,
workbook, builder ou teste existente foi alterado. Baseline: branch
`claude/funny-noether-nbcr7b`, HEAD `cbe58e67ad60a756f7bd6170859bd2b40483f310`
(ver `evidence/baseline.txt`), suíte em 1414 passed antes e depois desta
etapa. Esta etapa fecha, sem `OPEN DECISION`/`TBD`, as quatro decisões que
a Etapa 2.1 (`audit/stage2_1_result_state_contract/`) havia deixado em
aberto.

## Reprodução

```bash
python3 -m pytest -q   # 1414 passed — nenhuma mudança de código nesta etapa
```

Esta etapa não introduz probes novos: fecha decisões sobre evidência já
produzida na Etapa 2.1, exceto pela leitura direta (nesta etapa) de
`app/engine/dependency_graph.py` e `app/engine/dependency_resolver.py`,
registrada em `evidence/baseline.txt`.

## Conteúdo

| arquivo | conteúdo |
|---|---|
| `REPORT.md` | relatório completo: sumário executivo, base de evidência, escopo, hipótese, comportamento do runtime, fechamento de D1 (mecanismo de declaração), D2 (escopo da taxonomia), D3 (fronteira estado × erro técnico e política de propagação de erro técnico), D4 (`UNAVAILABLE`), matriz de decisão, taxonomia final, contrato value/state/error, contrato de declaração no workbook, contrato de runtime, contrato de propagação, contrato de agregação, contrato de categorias, caso canônico A41, `CONTRACT FOR STAGE 2.3` (com checklist normativa), autocrítica e o bloco `STAGE 2.2 RESULT` |
| `evidence/baseline.txt` | branch, HEAD, sincronização com origin, working tree, cauda do pytest, e a evidência nova de código (ausência de índice reverso de descendentes no grafo de dependências) |
| `evidence/decision_matrix.csv` | matriz D1-D4: alternativas avaliadas, evidência, decisão final, justificativa, impacto na Etapa 3 |

## Decisões fechadas nesta etapa

| decisão | fechamento |
|---|---|
| D1 — mecanismo de declaração | metadata `declared_result_states` na `VariableDefinition` (Alternativa C) + sentinela textual mantido na fórmula (Alternativa A), tradução pelo builder |
| D2 — escopo da taxonomia | taxonomia global fixa de 4 rótulos (`VALID`, `NO_APPLICABLE_RULE`, `INVALID_INPUT`, `VALIDATION_FAILED`); cada variável declara o subconjunto que pode produzir |
| D3 — fronteira estado × erro técnico | erro técnico nunca vira `result_state`; propagação de erro técnico usa a mesma mecânica de isolamento por alcançabilidade do grafo que a de estado de negócio — com `ARCHITECTURAL GAP` explicitamente registrado (índice de descendentes não existe hoje) |
| D4 — `UNAVAILABLE`/`DATA_NOT_YET_READY` | excluído da taxonomia agora (Alternativa B); extensibilidade condicionada a evidência futura real |

## Gate final

**`STAGE_2.3_GATE: READY`** — ver `REPORT.md` §22 para o bloco
`STAGE 2.2 RESULT` completo e a confirmação de que nenhum arquivo de
produção foi alterado.
