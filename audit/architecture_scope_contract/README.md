# Verificação arquitetural — escopo, identidade e tipos

**Gate: ARCHITECTURE VERIFIED WITH GAPS**. Relatório: `architecture_audit_report.md`.

A verificação é não destrutiva: nenhum arquivo fora deste diretório foi
alterado (código, seeds, builders, testes e workbooks intocados). O commit
base é `5d81b5f`.

## Reprodução

```bash
python3 audit/architecture_scope_contract/explore_scope_contract.py   # 68 sondas; regrava CSV/JSON
python3 -m pytest -q                                                  # 1414 passed (evidence/platform_tests.txt)
```

## Artefatos

| arquivo | conteúdo |
|---|---|
| `architecture_audit_report.md` | respostas às 8 perguntas, contrato real, divergências, transversalidade, recomendações, gate |
| `architecture_contract.json` | contrato em formato máquina + resumo dos seeds e workbooks |
| `scope_contract_matrix.csv` | aceitação de cada `scope_type/scope_value` nos 3 validadores, no `ScopeResolver` e na DSL |
| `reference_resolution_matrix.csv` | sondas nas camadas de nomes, parser, runtime e grupos |
| `storage_identity_matrix.csv` | chaves efetivas de cada estrutura de armazenamento |
| `builder_seed_matrix.csv` | uso do contrato pelos builders e seeds |
| `workbook_usage_matrix.csv` | nome+escopo, `@linha`, `@grupo` e nomes espacializados por workbook e seed |
| `spatialized_name_inventory.csv` | 25 nomes espacializados por workbook (max_ht 21, A41 4; o mesmo conjunto se repete nos seeds), com classificação |
| `value_type_contract.md` | contrato `value_type` / `variable_type` / `"F"` |
| `negative_tests_results.json` | 68 sondas (entrada, esperado, observado, arquivo:linha) |
| `explore_scope_contract.py` | script reprodutível |
| `evidence/` | saída da execução, testes da plataforma, cópias dos workbooks examinados |
