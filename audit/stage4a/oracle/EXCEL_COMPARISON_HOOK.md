# Gancho de validação contra o Excel original — area_41 (aba "Forecast A41")

| campo | valor |
|---|---|
| estado | **GANCHO APENAS**: a planilha Excel original de forecast não está no repositório; nenhuma comparação foi executada e **nenhum valor foi inventado** |
| etapa | posterior à 4A, quando o extrato for fornecido |
| oracle atual | `INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)`. Compara o engine com o texto do workbook descritivo A41 v9, não com valores calculados pelo Excel |

## 1. O que a comparação futura vai provar

Hoje sabemos que as equações executadas pelo engine são as do workbook descritivo: oracle 4A, 5 015/5 015 comparações.

A comparação com o Excel vai provar outra coisa: que, **com as mesmas entradas**, o engine reproduz os **valores** da aba "Forecast A41" da planilha de operação. Isso valida a transcrição workbook ↔ Excel, que a 4A não cobre.

## 2. Formato de extrato necessário

Um arquivo CSV, UTF-8, com cabeçalho, uma linha por (variável, escopo, data):

```text
variavel,variable_id,scope_type,scope_value,frequencia,data,periodo,valor,estado,celula_origem
```

| coluna | conteúdo | exemplo de formato (não é valor real) |
|---|---|---|
| `variavel` | nome da variável no workbook descritivo | `retirada_condensado_linha` |
| `variable_id` | ID do seed (tabela §3) | `VAR16031` |
| `scope_type` / `scope_value` | escopo da instância | `linha` / `L4` |
| `frequencia` | `diário`, `mensal` ou `anual` | `diário` |
| `data` | data de referência ISO `AAAA-MM-DD`. Para mensal e anual, a data de corte (janela efetiva, D33B-04) | `AAAA-MM-DD` |
| `periodo` | `AAAA-MM-DD` (diário), `AAAA-MM` (mensal), `AAAA` (anual) | `AAAA-MM` |
| `valor` | número com ponto decimal, sem separador de milhar; vazio se a célula exibe `F` | `<número>` |
| `estado` | vazio, ou `F` quando a célula do Excel mostra o literal `F` | `F` |
| `celula_origem` | referência da célula na aba | `Forecast A41!A6` |

Requisitos do extrato:
1. **Entradas e saídas do mesmo dia.**
   - As entradas: `vazao_ltp`, `fator_retirada_cond_corr_lth`, `lth`, `valor_retirada`, `hes`, `desconto_retirada_41c`, `desconto_retirada_41d`.
   - As saídas: todas as calculadas.
   - Sem as entradas, a comparação não é reprodutível.
2. Para `hes`, o texto exato (`Normal`, `LC`, `Overhaul/Parada`, `1 By pass`, `1 By pass e LC`).
3. Pelo menos um mês completo e, se houver, dias com `hes` ≠ `Normal` e um dia com `F`.
4. Valores com a precisão total da célula (não a formatada).

## 3. Variáveis e células de origem (dos seeds; `source_reference`)

| variável (workbook) | ID | freq. | escopo | célula |
|---|---|---|---|---|
| `vazao_ltp` | VAR16001/2/3 | mensal | L1_L3 / L4_L5 / L6_L7 | `Forecast A41!B31` |
| `fator_retirada_cond_corr_lth` | VAR16011/12/13 | mensal | L1_L3 / L4_L5 / L6_L7 | `Forecast A41!D32` |
| `lth` | VAR16007 | diário | L1..L7 | `Forecast A41!B35` |
| `valor_retirada` | VAR16017 | diário | L1..L3 | `Forecast A41!A11` |
| `hes` | VAR16021 | diário | L4 / L5 / L6 / L7 | `A16` / `A17` / `A18` / `A19` |
| `desconto_retirada_41c` | VAR16022 / VAR16023 | diário | L4_L5 / L6_L7 | `C26` / `C28` |
| `desconto_retirada_41d` | VAR16024 | diário | L4_L5 | `C27` |
| `lth_grupo` | VAR16008/9/10 | diário | L1_L3 / L4_L5 / L6_L7 | `B41` / `B50` / `B59` |
| `retirada_cond_corr_ltp` | VAR16004/5/6 | diário | L1_L3 / L4_L5 / L6_L7 | `B42` / `B51` / `B60` |
| `retirada_cond_corr_lth` | VAR16014/15/16 | diário | L1_L3 / L4_L5 / L6_L7 | `B43` / `B52` / `B61` |
| `retirada_condensado_grupo` | VAR16018 / VAR16025 / VAR16028 (diário); VAR16019/26/29 (mensal); VAR16020/27/30 (anual) | — | L1_L3 / L4_L5 / L6_L7 | `A11` / `A12` / `A13` |
| `retirada_condensado_linha` | VAR16031 (diário); VAR16032 (mensal); VAR16033 (anual) | — | L1..L7 | `A3`..`A9` |
| `retirada_condensado_total` | VAR16034 / 35 / 36 | diário / mensal / anual | L1_L7 | `A10` |

**Ponto de atenção** (DOCUMENTATION_ONLY): `valor_retirada` (VAR16017, L1..L3) e `retirada_condensado_grupo` L1_L3 (VAR16018) apontam para a **mesma** célula `Forecast A41!A11`. Confirmar a célula de cada um ao montar o extrato.

## 4. Procedimento previsto (etapa posterior)

1. Versionar o extrato em `audit/<etapa>/excel/forecast_a41_extract.csv`, com o sha256 registrado.
2. Carregar as **entradas** do extrato num contexto do engine (mesmo protocolo de `common.engine_area_41`) e executar as 20 equações e as 10 regras de agregação.
3. Comparar cada saída com o `valor`/`estado` do extrato:
   - `F` ↔ `NO_APPLICABLE_RULE` (value None);
   - tolerância a definir conforme a precisão exportada.
4. Rodar o oracle 4A sobre as mesmas entradas. Três vias (Excel, engine, oracle) devem concordar; uma divergência isolada aponta a camada com defeito.
