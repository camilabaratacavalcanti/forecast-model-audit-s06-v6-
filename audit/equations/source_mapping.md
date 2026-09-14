# Mapeamento de rastreabilidade — Fonte ↔ Plataforma

Para o mapeamento completo (106 linhas), ver a coluna `source_row` em
`reconciliation_106_equations.csv` — cada linha lista exatamente a linha
do workbook (`row`, 1-indexado, cabeçalho na linha 1) usada como fonte
para aquela `EquationDefinition`.

## Arquivos

```
source_file:   descritivo_das_vari_veis_yield_v3.xlsx
sheet:         yield
source_row:    coluna B = name, H = frequency, I = scope_type,
               J = scope_value, M = expression

platform_file: data/seed/yield/equations.json
platform_record: um objeto JSON por EquationDefinition (equation_id)
```

## Exemplos representativos (um por bloco funcional)

| platform_id | platform_name | platform_scope | source_row | source_expression (raw) |
|---|---|---|---|---|
| EQ11001 | yield | linha/L1_L7 | 2 | `(ltp_a_c - ratio_spent)*ltp_tc - 0,654*sl_solids` |
| EQ11002 | ltp | linha/L1_L7 | 3 | `lth*ltp_lth` |
| EQ11003 | ssa_media | linha/L1_L7 | 13 | `(ssa_sf + ssa_sg)/2` |
| EQ11004 | n_ppt | linha/L1_L7 | 14 | `tanque_base_L1@ - tanque_L1@` (ver nota INFO-1) |
| EQ11005 | producao_base_ppt | linha/L1_L7 | 17 | `(yield*24*ltp*0,97)/1000` |
| EQ11006 | ratio_spent | linha/L1_L7 | 10 | ver nota INFO-2 |
| EQ11007 | yield_base | linha/L1_L7 | 82 | `(ltp_a_c_base - ratio_spent_base)*ltp_tc_base - 0,654*sl_solids_base` |
| EQ11008 | ltp_base | linha/L1_L7 | 83 | `lth_base*ltp_lth_base` |
| EQ11009 | ssa_media_base | linha/L1_L7 | 93 | `(ssa_sf_base + ssa_sg_base)/2` |
| EQ11010 | producao_base_ppt_base | linha/L1_L7 | 97 | `(yield_base*24*30*ltp_base*0,97)/1000` |
| EQ11011 | yield | linha_grupo/L1_L3 | 18 | `( yield@L1*ltp@L1 + yield@L2*ltp@L2 + yield@L3*ltp@L3 ) / ( ltp@L1 + ltp@L2 + ltp@L3 )` |
| EQ11027 | yield | linha_grupo/L4_L5 | 34 | `( yield@L4 * ltp@L4 + yield@L5 * ltp@L5 ) / ( ltp@L4 + ltp@L5 )` |
| EQ11043 | yield | linha_grupo/L6_L7 | 50 | `( yield@L6 * ltp@L6 + yield@L7 * ltp@L7 ) / ( ltp@L6 + ltp@L7 )` |

(O mapeamento completo das 106 linhas está em
`reconciliation_106_equations.csv`, colunas `equation_definition_id`,
`source_row`, `source_expression`.)

## Tanque / tanque_base (não são EquationDefinitions, mas alimentam EQ11004)

```
tanque      → VAR11239 (VariableDefinition, linha/L1_L7)
              fonte: linhas 249-255 (tanque_L1...tanque_L7)

tanque_base → PARAM11003 (7× ParameterDefinition, uma por linha)
              fonte: linhas 242-248 (tanque_L1_base...tanque_L7_base)
```
