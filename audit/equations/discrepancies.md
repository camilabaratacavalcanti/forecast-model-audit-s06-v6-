# Divergências — 106 EquationDefinitions do Yield

## P0 (Critical)

Nenhuma.

## P1 (High)

Nenhuma.

## P2 (Medium)

Nenhuma.

## P3 (Low)

Nenhuma.

## INFO (nota histórica / decisão já governada)

### INFO-1 — EQ11004 (`n_ppt`, linha/L1_L7)

- **Categoria:** SEMANTIC_MATCH (representação, não fórmula)
- **Descrição:** fonte usa notação current-line (`tanque_base_L1@ - tanque_L1@`);
  plataforma usa referência sem escopo (`tanque_base - tanque`), resolvida
  contextualmente pela EquationInstance.
- **Evidência:** `audit/equations/reconciliation_106_equations.csv`, linha
  `seq=4`; comprovação executável em
  `tests/test_fase3a_contextual_resolution_integration.py::test_c5_n_ppt_full_stack_all_lines`
  (7 linhas, valores corretos).
- **Ação recomendada:** nenhuma. Este é o comportamento funcional correto
  por decisão arquitetural explícita (seções 15–16 do prompt de auditoria).

### INFO-2 — EQ11006 (`ratio_spent`, linha/L1_L7)

- **Categoria:** MATCH contra a regra de negócio Nível 1; nota histórica
  contra o workbook (Nível 2)
- **Descrição:** 2 dos 7 termos (`LTP`, `SSAmedia`) têm sinal invertido
  entre a fórmula aprovada e o workbook atual. A fórmula implementada
  segue exatamente a regra aprovada.
- **Evidência:** comparação termo a termo em `reconcile.py` (bloco de
  override `EQ11006`); `audit/equations/reconciliation_106_equations.csv`,
  linha `seq=6`.
- **Ação recomendada:** nenhuma — regra de negócio já aprovada e
  registrada como autoridade Nível 1 (seção 4.1). Mantido aqui apenas
  como rastro histórico caso a origem da divergência precise ser
  revisitada no futuro.

## Questões abertas (SOURCE_UNCLEAR)

Nenhuma equação foi classificada como `SOURCE_UNCLEAR` — todas as 106
tiveram uma linha-fonte correspondente localizada e uma fórmula
matemática (não descritiva) comparável.
