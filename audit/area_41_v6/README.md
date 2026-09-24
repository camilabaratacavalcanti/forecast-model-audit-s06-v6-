STATUS: READY_FOR_THIRD_AUDIT

# A41 v6 — Fechamento da Etapa 2

O v6 **validado** (`descritivo_das_variáveis_A41_v6.xlsx`) é o workbook
submetido à terceira auditoria.

O v6 **recebido** (`…_v6_recebido.xlsx`, cópia byte a byte do anexo) contém a
decisão 41c/41d do usuário. Porém, ele foi derivado do *input* do v5 e perdeu
as duas correções estruturais do v5 (D1 `value_type`, D2 `hes_lN@LN`). No
estado recebido, o harness registra 32 falhas. A correção mínima (§4 do
prompt) foi reaplicar D1 e D2. Com isso, o v6 validado difere do v5 validado
**apenas** nas duas células da decisão 41c/41d.

## Reprodução

```bash
python3 -m pytest audit/area_41_v6/check_a41_v6.py -v            # 46 passed
A41_WORKBOOK="audit/area_41_v6/descritivo_das_variáveis_A41_v6_recebido.xlsx" \
  python3 -m pytest audit/area_41_v6/check_a41_v6.py               # 32 failed (D1/D2)
python3 audit/area_41_v6/check_a41_v6.py                           # regenera evidence/ e change_matrix.csv
python3 -m pytest -q                                               # 1414 passed
```

O harness usa apenas componentes genéricos da plataforma. Os IDs
`VAR99xxx`/`EQ99xxx` são efêmeros, e os valores esperados vêm de fórmulas de
referência independentes.

## 1. Pre-flight — PASS

| item | valor |
|---|---|
| branch / HEAD | `claude/funny-noether-nbcr7b` @ `63576e2`, igual a `origin` (0/0) e 2 commits à frente de `origin/main` |
| working tree | limpo antes da etapa; nenhuma alteração local não relacionada |
| commits | baseline da plataforma `202d4cb`; Etapa 1 `4510865`; Etapa 2/v5 `63576e2` |
| versões localizadas | v3 `59f82304…`; v4 `383c462b…`; input do v5 `ea3d2e51…`; v5 validado `c8be0a3c…`; **v6 recebido `aad9b306…`** |

## 2. Identidade do v6 — PASS

| | v6 recebido | v6 validado |
|---|---|---|
| arquivo | anexo `6acf8593-descritivo_das_vari_veis_A41_v6.xlsx`, copiado para `descritivo_das_variáveis_A41_v6_recebido.xlsx` | `descritivo_das_variáveis_A41_v6.xlsx` |
| sha256 | `aad9b3069069bff47e51ddcd40722a7c3d6ba40a6ccb53fdb732e0bc9613231f` | `4b0c41aef6c56a5b655faa543cf96f33f270cdfad8ecd2b4c6a5e1a09144a352` |
| tamanho | 34 887 bytes | — |
| estrutura | 1 aba `A41`, 308×15; merged `A1:D1 E1:F1 G1:H1 I1:L1`; 54 entidades; sem fórmulas | 1 aba `A41`, 308×16 (coluna P `value_type`); mesmos merged ranges; 54 entidades; sem fórmulas |

## 3. Alterações v5 → v6 — PASS

`change_matrix.csv` tem 53 células, cada uma com os valores no v5, no v6 recebido e no v6 validado, e sua classificação:

| células | natureza | classificação | justificativa |
|---|---|---|---|
| K30, K31 | `source_reference` | **esperada** | Decisão do usuário: 41c@L6_L7 C27→**C28**; 41d@L4_L5 C26→**C27** |
| P1:P56 (49) | `value_type` (D1) | inesperada no v6 recebido; reaplicada | O v6 recebido perdeu a coluna; os valores reaplicados são idênticos aos do v5 |
| M39, M42 | expressão (D2) | inesperada no v6 recebido; reaplicada | O v6 recebido voltou a `hes_lN`; o texto reaplicado é idêntico ao do v5 |

Nenhuma outra célula difere. O v6 recebido é exatamente o input do v5 com K30 e K31 alterados.

## 4. Contrato `value_type` / `variable_type` — PASS

| Campo | Significado | Valores aceitos | Entidades | Evidência |
|---|---|---|---|---|
| `variable_type` | papel da variável no modelo | `entrada`, `entrada_externa`, `calculado`, `saída` | toda variável (obrigatório); não se aplica a parâmetros | `ALLOWED_VARIABLE_TYPES` (`app/validation/variable_seed_validator.py:84`); campo obrigatório de `Variable`/`VariableDefinition` (`app/domain/variables/models.py:33,59`); builders |
| `value_type` | tipo do valor armazenado | `numeric` (padrão), `categorical` | variáveis (opcional; ausente = `numeric`). Parâmetros não têm o campo e são sempre numéricos | `VALUE_TYPES` (`app/domain/values.py:28`); validação em `VariableDefinition` (`models.py:67,86`); enum no validador de seed (`:217`); `ForecastEngine` declara as categóricas (`forecast_engine.py:317`); `CalculationContext` rejeita texto fora delas; `ForecastValue.value: ScalarValue` |

Respostas às perguntas do §3:

- **3.1 Tipo do valor armazenado:** `value_type`.
- **3.2 Papel da entidade:** `variable_type`.
- **3.3 `variable_type`:** entrada, entrada externa, calculado ou saída.
- **3.4 `value_type`:** numeric ou categorical.
- **3.5 Combinações permitidas:** os dois campos são independentes; qualquer `variable_type` combina com qualquer `value_type`. `"F"` é aceito em qualquer variável.
- **3.6 Campos no workbook:** o A41 deve ter **os dois**.
- **3.7 Origem do campo:** `value_type` foi introduzido na Etapa 1 (`4510865`). A única ocorrência anterior, em `3fc95d5`, é um parâmetro local homônimo, sem relação com o campo.
- **3.8 Testes unitários:** 12 testes em `tests/test_dsl_structural_contracts.py`, incluindo `test_value_type_is_declared_on_definition`, `test_seed_validator_checks_value_type_enum` e `test_parameters_remain_numeric_only`.
- **3.9 Testes de integração:** `test_engine_declares_categorical_variables_from_definitions` e `test_text_result_into_numeric_variable_is_rejected`.

Workbook: `hes_l4..l7` = `categorical`; as outras 43 variáveis = `numeric`; os 7 parâmetros ficam em branco. Não há texto em variável numérica. Os literais de texto do workbook são os 5 estados e `"F"`.

## 5–11. Contratos

Todos os itens abaixo são **PASS**.

- **A019:** 59 de 59 referências foram resolvidas de forma determinística por nome + frequência + escopo, sem nenhuma ambiguidade (`evidence/scope_matrix.csv`).
- **A021:** `retirada_condensado_linha` tem 7 instâncias mensais e 7 anuais (L1..L7), e os grupos e o total têm 1 cada. São 22 instâncias no total, todas **AVERAGE**, que é a agregação declarada no workbook.
- **@grupo:** o vínculo L1/L2/L3→L1_L3, L4/L5→L4_L5 e L6/L7→L6_L7 foi verificado (`test_line_to_group_bindings`). A referência explícita só tem fallback temporal. O grafo produz o mesmo resultado com o registry em ordem inversa.
- **ln():** os testes da plataforma passam (34), incluindo `ln(1)=0`, `ln(e)≈1`, `ln(0)` e `ln(<0)` → `MathDomainError`, texto e categórica → erro, e allowlist fechada. As 6 equações do A41 batem com a referência.
- **Texto e booleano:** passam 38 testes da plataforma e 16 casos de ramos do A41, cobrindo os 5 estados, `and`/`or` e a precedência LC > Overhaul > By pass.
- **"F":** 6 combinações não cobertas produzem `"F"`, que é gravado sem conversão, e quem o consome falha com `ConditionalFailureError`. Na agregação, um dia com `"F"` faz a média mensal do grupo falhar com `AggregationFailureError(["2026-03-02"])`. Passam também 25 testes da plataforma.
- **41c/41d:** C26→41c@L4_L5, C28→41c@L6_L7 e C27→41d@L4_L5. Não existe `41d@L6_L7` e não há célula compartilhada. Cada desconto chega ao ramo previsto (`test_discounts_reach_the_intended_branches`).

## 12–14. Equações, agregações e reconciliações — PASS

Cenário determinístico, com LTH L1..L7 = 10/20/30/40/60/70/30 (§21):

- `lth_grupo`: 20 / 50 / 50 (média).
- `retirada_cond_corr_ltp` e `retirada_cond_corr_lth`: iguais à referência.
- Grupos: todos os ramos batem com a referência.
- Rateio: a soma das linhas é igual ao grupo em L1_L3, L4_L5 e L6_L7.
- Total: igual à soma dos três grupos.
- Agregações em 33 dias: mensal e anual = média dos diários para linha, grupo e total.

Não há SUM e não há fator ×24/×720/×8760: `find_sum_dimension_issues` retorna vazio, e a unidade de origem é igual à de destino em todas as regras.

## 15–16. Harness e matriz de escopo — PASS

- Harness: 46 passed, 0 failed, 0 BLOCKING.
- Matriz de escopo: 59 de 59 PASS, sem ambiguidade, órfão ou produtor inexistente.
- Rastreabilidade das 54 entidades: `evidence/traceability_matrix.csv`.

## 17. Regressão — PASS

1414 passed, 0 failed, 0 skipped em cerca de 6 s, idêntico ao baseline da Etapa 1.

## 18. max_ht — DEFERRED

A regra de saneamento, aplicada somente à identificação:

> "identificar e excluir variáveis calculadas cuja única finalidade seja transformar uma soma temporal de taxa (`/h`) em um acumulado mensal (`/mês`) ou anual (`/ano`) sem que exista uma duração operacional explicitamente definida no modelo."

Foram identificadas as mesmas 34 variáveis da Etapa 2 (lista em `audit/area_41_v5/README.md` §5). A fixação delas continua passando (`test_max_ht_hourly_sums_are_the_pinned_pending_set`).

- Nenhuma variável foi removida.
- Nenhum fator foi introduzido: todas as regras mantêm `integration_factor = 1.0`.
- Nenhum seed foi alterado.

## 19. Diff review — PASS

Só existe o diretório novo `audit/area_41_v6/`:

- os dois workbooks;
- o harness;
- `change_matrix.csv`;
- `evidence/`;
- este README.

`app/`, `data/`, `tools/` e `tests/` estão sem diff. Não há código específico do A41. `git diff --check` está limpo.

## 20. Critérios de aceite

Todos os critérios estão **PASS**, exceto max_ht, que está **DEFERRED** como exigido.

- **Workbook:**
  - v6 identificado, com SHA-256 registrado;
  - v5→v6 auditado;
  - 41c/41d confirmado;
  - contrato determinado pelo código, e workbook compatível com ele.
- **Contratos:** A019, A021, @grupo, ln, texto/categórico, booleano e "F".
- **Resolução:** referências determinísticas e matriz de escopo sem falhas.
- **Agregações e equações:**
  - materialização;
  - equações, rateios, grupos e total;
  - agregações mensais e anuais.
- **Estrutura e harness:** validação estrutural e harness sem BLOCKING.
- **Regressão e diff:** regressão, `diff --check` e revisão do diff.
- **Escopo:** plataforma intocada e nenhum código específico do A41.
- **Evidências:** reproduzíveis e armazenadas.

## 21. Artefatos

| arquivo | conteúdo |
|---|---|
| `descritivo_das_variáveis_A41_v6.xlsx` | workbook validado (sha `4b0c41ae…`) |
| `descritivo_das_variáveis_A41_v6_recebido.xlsx` | anexo original, intocado (sha `aad9b306…`) |
| `change_matrix.csv` | v5 → v6 recebido → v6 validado, célula a célula |
| `evidence/scope_matrix.csv` | 59 referências |
| `evidence/traceability_matrix.csv` | 54 entidades |
| `evidence/a41_v6_evidence.json` | contrato, reconciliações, instâncias e 41c/41d |
| `check_a41_v6.py` | harness reprodutível |
