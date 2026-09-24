# Terceira auditoria independente — A41 v6

**STATUS: CONDITIONAL**

Nenhum achado BLOCKING. O v6 validado está correto contra todos os contratos
que puderam ser verificados: 91 verificações independentes com 0 falhas,
1292 comparações spec × texto × runtime iguais e 6 de 6 mutações detectadas.

Mesmo assim, ele **não** pode ser classificado como `READY_FOR_IMPLEMENTATION`,
por três motivos:

- o critério de aprovação 20 (Forecast A41 validado) está **NOT VERIFIED**,
  porque a fonte não está disponível (F-002);
- há um achado MAJOR de política de falha na plataforma (F-001);
- há um achado MAJOR de proveniência da cópia mestre (F-004).

## 1. Objeto auditado

| item | valor |
|---|---|
| arquivo | `audit/area_41_v6/descritivo_das_variáveis_A41_v6.xlsx` |
| sha256 | `4b0c41aef6c56a5b655faa543cf96f33f270cdfad8ecd2b4c6a5e1a09144a352` |
| estrutura | 1 aba `A41`; 308×16; merged `A1:D1 E1:F1 G1:H1 I1:L1`; sem fórmulas; valores em cache = valores armazenados; 54 entidades (linhas 3–56); nada preenchido depois da linha 56 |
| commit da auditoria (base) | `498022d` (branch `claude/funny-noether-nbcr7b`, sincronizada com `origin`, 3 commits à frente de `main` `202d4cb`) |
| Etapa 1 / Etapa 2 | `4510865` / `63576e2`, `498022d` |

## 2. Cadeia de proveniência (comparação efetiva de arquivos: `change_matrix.csv`, 265 linhas)

| transição | sha antes → depois | alterações | esperada? |
|---|---|---|---|
| v3 → v4 | `59f82304` → `383c462b` | 47 mudanças de identidade/campo (duplicatas Somatório/Média removidas, `lth` unificado, A020 média, `ln(lth_grupo·fator)`, PLANTA canônico, OBS 41c/41d) | sim |
| v4 → v5_input | → `ea3d2e51` | 61 células: 54 descrições + 7 denominadores §7 | sim |
| v5_input → v5_validado | → `c8be0a3c` | 51 células: coluna P `value_type` (D1) + M39/M42 `hes_lN@LN` (D2) | sim |
| v5_validado → v6_recebido | → `aad9b306` | 53 células: K30, K31 (decisão) + **D1/D2 ausentes** | K30/K31 sim; ausências → F-004 |
| v6_recebido → v6_validado | → `4b0c41ae` | 51 células: D1/D2 reaplicados | sim |
| **v5_validado → v6_validado** | | **somente K30 (C27→C28) e K31 (C26→C27)** | sim |

Nenhuma alteração da cadeia ficou sem previsão.

## 3. Metodologia

- **Verificação:** o script `third_audit_a41_v6.py` não importa o harness da
  Etapa 2. Ele reimplementa:
  - a leitura do xlsx;
  - a resolução de referências a partir do contrato de grupos;
  - o DAG por instância concreta;
  - um interpretador próprio do **texto** das expressões;
  - fórmulas de especificação escritas à mão (A020, §7, §10, §12);
  - uma álgebra de unidades.

  A plataforma entra apenas como runtime auditado, e cada resultado é
  comparado com duas fontes independentes (spec e texto).
- **Evidência:** CSVs e `evidence/`, com comando, SHA e timestamp.
- **Controle de falso positivo:** 6 workbooks mutantes (lth_grupo como soma,
  41c/41d trocados, sem `value_type`, `hes` sem escopo, agregação SUM, rateio
  no grupo errado) são **todos** detectados pelas verificações específicas
  (`evidence/mutation_tests.txt`).
- **Harness da Etapa 2:** 46 passed. Usado só como evidência de regressão e de
  suporte; não diverge da auditoria independente.

## 4. Matriz de gates

| Gate | Resultado | Evidência | Blocking? |
|---|---|---|---|
| identidade do workbook | PASS | SHA dos 6 arquivos da cadeia; `evidence/checks.json` identity | Não |
| cadeia de proveniência | PASS (com F-004 MAJOR) | `change_matrix.csv` | Não |
| integridade estrutural | PASS | cabeçalho 15+1, merged, sem fórmulas, sem linhas órfãs | Não |
| `value_type` / `variable_type` | PASS | `value_type_matrix.csv`: 54/54 válidos; conjuntos de valores disjuntos; as variáveis comparadas a texto são exatamente `hes_l4..l7` = `categorical` | Não |
| A019 | PASS | `scope_matrix.csv`: 59/59 determinísticas; independente = resolvedor da plataforma; invariante à ordem (3 embaralhamentos) | Não |
| A020 | PASS | `lth_grupo` = 20/50/50 com 10..70 (média); 5 conjuntos de valores iguais nas 3 fontes | Não |
| A021 | PASS (F-008 INFO) | `aggregation_matrix.csv`: linha 7+7, grupos 3+3, total 1+1 = 22 | Não |
| `@grupo` | PASS | L1..L3→L1_L3, L4/L5→L4_L5, L6/L7→L6_L7; as 41 referências explícitas (de 59; 18 implícitas) leem exatamente o escopo declarado; total lê os 3 grupos | Não |
| `ln()` | PASS | 6 ocorrências com 1 argumento; `ln(1)=0`, `ln(e)=1`; `ln(0)`, `ln(<0)` → `MathDomainError`; `ln(categorical)` → `ExpressionTypeError`; allowlist fechada | Não |
| texto/booleano | PASS | 60 combinações de estados (30 por grupo) iguais nas 3 fontes; precedência LC > Overhaul > By pass > By pass e LC > F demonstrada | Não |
| `"F"` | PASS (contrato) / F-001 MAJOR | `"F"` gravado como texto exato; consumo → `ConditionalFailureError`; média com um dia F → `AggregationFailureError(['2026-03-02'])` | Não |
| 41c/41d | PASS contra a decisão; **NOT VERIFIED** contra o Forecast | C26→41c@L4_L5, C28→41c@L6_L7, C27→41d@L4_L5; sem 41d@L6_L7; sem célula compartilhada; C26/C27 corroboradas pelos parâmetros, C28 não (F-003) | Não |
| equações | PASS | `equation_validation.csv`: 1292 PASS, 8 NAO_CALCULADO (fail-fast, F-001), 0 FAIL | Não |
| rateio | PASS | Σ linhas = grupo em 5 conjuntos (iguais, diferentes, assimétricos, próximos de zero, §21); Σ lth = 0 → falha explícita (F-012) | Não |
| total | PASS | total = Σ grupos (diário); mensal/anual = Σ das médias dos grupos | Não |
| agregações | PASS | 22 instâncias = média independente de 40 dias; só AVERAGE; sem fator | Não |
| unidades | PASS (F-006 MINOR, F-009 INFO) | `dimensional_validation.csv`: nenhuma soma incompatível; unidade calculada = declarada | Não |
| dependências | PASS | `dependency_matrix.csv` (81 arestas); DAG acíclico; só os 7 parâmetros documentados sem uso | Não |
| isolamento de escopo | PASS em operação normal; F-001 sob falha | perturbar `lth` de uma linha só afeta o próprio grupo e o total | Não |
| teste de ordem | PASS | `order_invariance_results.csv`: 5 ordens × 2 cenários idênticos | Não |
| teste de perturbação | PASS | `perturbation_results.csv`: 11 perturbações com afetados = descendentes do DAG; desconto com ramo inativo não altera nada | Não |
| Forecast A41 | **NOT VERIFIED** | `forecast_reconciliation.csv`: 54/54 sem fonte (F-002) | Não, mas impede READY (critério 20) |
| regressão | PASS | `evidence/pytest_full.txt`: 1414 passed, 0 failed, 0 skipped, 0 errors, ~6 s | Não |
| segurança DSL | PASS | nenhuma das construções `eval`, `exec`, `__import__`, `open`, `getattr`, `lambda`, atributo, subscrição ou argumento nomeado; o parser da plataforma aceita as 20 equações | Não |
| max_ht | DEFERRED | 34 SUMs `/h`→`/mês`\|`/ano` identificadas; `integration_factor` = 1.0 em todos os seeds | Não |
| diff | PASS | só `audit/area_41_v6_third_audit/`; `app/`, `data/`, `tools/`, `tests/` e o workbook intocados | Não |

## 5. Achados (`findings.csv`)

### BLOCKING
Nenhum.

### MAJOR

- **F-001 — fail-fast colateral sob `"F"`.**
  - Quando o grupo L4_L5 resulta em `"F"`, deixam de ser calculadas também
    `retirada_condensado_linha@L6` e `@L7`, que não dependem de L4_L5 (os
    dependentes pelo DAG são apenas L4, L5 e o total).
  - Causa: a plataforma interrompe a rodada do dia na primeira falha.
  - Correção necessária: decidir a política antes de implementar (manter e
    documentar, ou isolar a falha nos descendentes, o que seria uma mudança de
    plataforma).
- **F-002 — Forecast A41 indisponível.**
  - As 54 `source_reference` estão NOT VERIFIED (critério 20).
  - Correção: fornecer a aba e conferir, no mínimo, C26/C27/C28, A11, B31,
    D32, A10–A13, A3–A9, A16–A19 e B41–B61.
- **F-004 — cópia mestre divergente.**
  - O v6 recebido não tem D1/D2 (32 falhas no harness).
  - Correção: adotar o v6 validado (`4b0c41ae…`) como mestre.

### MINOR

- **F-003:** a origem C28 não é corroborada internamente.
- **F-005:** o OBS das linhas 39 e 42 ainda descreve 41c/41d como pendente.
- **F-006:** a unidade de `vazao_ltp` é `-`, embora seja uma vazão.
- **F-007:** o significado de `valor_retirada` está em aberto, e A11 é
  compartilhada entre 3 entradas e a saída do grupo.

### INFORMATIONAL

- **F-008:** o builder do A41 precisa resolver a origem das linhas 52/53 por
  instância concreta.
- **F-009:** `ln` é aplicado a grandezas dimensionais, e há constantes somadas
  a m³/h (modelo empírico).
- **F-010:** 7 parâmetros não são usados (documentado).
- **F-011:** há perguntas abertas sobre a origem de dados de entrada.
- **F-012:** Σ lth = 0 falha explicitamente.
- **F-013:** limite de independência. O mesmo agente reaplicou D1/D2; como
  mitigação, o script é independente e há testes de mutação. Revisão humana é
  recomendada.

### DEFERRED

**max_ht:** 34 variáveis. A regra:

> "identificar e excluir variáveis calculadas cuja única finalidade seja
> transformar uma soma temporal de taxa (`/h`) em um acumulado mensal
> (`/mês`) ou anual (`/ano`) sem que exista uma duração operacional
> explicitamente definida no modelo."

Nenhuma alteração foi feita e nenhum fator foi aplicado. O item fica para
depois da implementação do A41, por decisão do usuário. O impacto é nulo para
o A41, cujas agregações são todas AVERAGE e preservam a unidade.

## 6. Condições para `READY_FOR_IMPLEMENTATION`

1. **F-002:** Forecast A41 conferido nas células listadas (inclui C28 → F-003).
2. **F-001:** política de falha `"F"` decidida e registrada.
3. **F-004:** v6 validado (`4b0c41ae…`) adotado como cópia mestre.

Os MINOR (F-005, F-006, F-007) são recomendados, mas não condicionam a
liberação. Se algum deles for corrigido, será preciso gerar um novo artefato
e reexecutar `third_audit_a41_v6.py`; o SHA mudará.
