# Auditoria conceitual de tipagem e resultados heterogêneos (Etapa 2)

Este é um artefato de auditoria **read-only**: nenhum arquivo de produção,
seed, workbook ou teste foi alterado. A base é o commit `978c2d0`, com a suíte
em 1414 passed. O diretório se chama `stage2_typing_contract/` para não
colidir com a "Etapa 2" anterior (saneamento do A41).

## Reprodução

```bash
python3 audit/stage2_typing_contract/probes_typing_contract.py   # regrava evidence/probes_results.json e os CSVs
python3 -m pytest -q                                             # 1414 passed
```

## Conteúdo

| arquivo | conteúdo |
|---|---|
| `REPORT.md` | relatório completo nas 20 seções pedidas (inclui architecture, value_type, value × state × error, "F", F-001, probes, negativos, mutação, agregação, propagação, workbooks, mixed, alternativas, trade-offs, impacto) |
| `findings.md` | T-01..T-13 com evidência, causa, risco e recomendação |
| `conceptual-contract.md` | contrato proposto (proposta, não implementação) |
| `stage3-gate.md` | gate e condições |
| `probes_typing_contract.py` | probes reprodutíveis (fixtures genéricas VAR96xxx) |
| `*.csv` | F-001, compatibilidade, propagação, agregação, testes negativos, mutação, estudo de caso A41 |
| `evidence/` | `probes_results.json` e saída da execução (comando, commit, timestamp) |

Os arquivos sugeridos no prompt (`executive-summary.md`,
`architecture-analysis.md`, `value-type-analysis.md`,
`result-state-analysis.md`, `f-analysis.md`, `probes.md`, `mutation-tests.md`,
`aggregation-analysis.md`, `alternatives.md`) correspondem às seções §1, §3,
§4, §5, §6, §8, §10, §11 e §15 de `REPORT.md`. Foram consolidados para evitar
duplicação.
