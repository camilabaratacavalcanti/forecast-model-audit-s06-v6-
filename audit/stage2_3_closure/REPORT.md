# Fechamento da Etapa 2.3 — herança de estados, vocabulário `numerico/categorico` e reauditoria

```text
Branch:        feature/area-41-block
Base:          4510865f83fd3cf628782ad6a2e3de502aac4e7e (== origin/main)
Resultado:     STAGE_2.3_GATE: BLOCKED
Motivo único:  as versões corrigidas dos workbooks não estão disponíveis nesta sessão;
               os arquivos presentes são byte a byte os mesmos auditados em 2026-09-25.
```

Atividades A (refinamento R1) e B (migração do vocabulário) concluídas. Atividade C executada sobre os
únicos arquivos disponíveis. Nada da Stage 3 foi implementado. Nenhum workbook foi alterado.

## 1. Pre-flight

| item | resultado |
|---|---|
| branch | `feature/area-41-block` |
| HEAD | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` |
| origin/main | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` |
| working tree antes | limpo |
| suíte antes | 1414 passed |
| workbooks | os cinco oficiais, uma cópia de cada; SHA-256 **idênticos** aos da auditoria inicial (tabela abaixo); nenhum `.xlsx` mais novo em todo o disco |

| arquivo | SHA-256 (hoje = 2026-09-25) |
|---|---|
| A41_v7 | `0fe3f1ff…3c1517` |
| energy_v3 | `9b73daaf…7a4e5` |
| MaxHT_v6 | `e6bffc02…15d4` |
| production_v3 | `25b90405…bc2dc5` |
| yield_v6 | `be2f1758…810ee05` |

```text
PRE-FLIGHT: PASS (código) · PENDENTE (workbooks corrigidos não recebidos)
```

## 2. Arquivos modificados

| arquivo | blob antes | natureza |
|---|---|---|
| `app/domain/values.py` | `c3242294` | constantes do contrato + docstring |
| `app/domain/variables/models.py` | `8ff53973` | comentários que citam os valores |
| `app/engine/calculation_context.py` | `21b8561d` | docstrings que citam os valores |
| `app/validation/variable_seed_validator.py` | `5a8a340c` | comentário do default |
| `tests/test_dsl_structural_contracts.py` | `beaddd2c` | literais de teste + asserções de não-alias |
| `audit/structural_corrections/platform_contracts.md` | — | documentação do contrato E |

Novos: `audit/stage2_3_closure/` (este relatório, `DECISION_REFINEMENT_R1_declared_result_states.md`, `evidence/`).
Reversão: `git checkout -- <arquivos>` (nada foi commitado). Terminações de linha preservadas (CRLF onde havia).

## 3. Diff conceitual

```text
NUMERIC     = "numeric"      →  "numerico"
CATEGORICAL = "categorical"  →  "categorico"
VALUE_TYPES = {"numerico", "categorico"}     (único vocabulário aceito)
```

Todo o resto do código já referenciava `NUMERIC`, `CATEGORICAL` ou `VALUE_TYPES`
(`VariableDefinition` default e `__post_init__`, `is_categorical`, `ENUM_FIELDS["value_type"]`,
`ForecastEngine` → `declare_categorical_variables`), então passou a usar o vocabulário novo sem outra mudança.
Nenhuma camada de normalização, nenhum alias, nenhuma aceitação dupla.

## 4. Ocorrências de `numeric`/`categorical` encontradas

Busca `git grep -i "numeric|categorical"` em `app/`, `tools/`, `data/`, `tests/`, `audit/`:

| classe (§15) | ocorrências | onde |
|---|---|---|
| 1–3. valor de `value_type` / enum / constante | 2 | `values.py:25-26` |
| 4. validação | 0 literais (usa `VALUE_TYPES`) | `models.py:86`, `variable_seed_validator.py:217` |
| 5. schema / 9. seed | 0 | nenhum seed tem campo `value_type` (default) |
| 6–8. parser / evaluator / resolver | 0 literais | usam `is_numeric()` (checagem de tipo Python, não do contrato) |
| 10–11. teste / fixture | 6 literais | `test_dsl_structural_contracts.py:64, 330, 332, 345, 358, 367` |
| 12–13. documentação / comentário que cita o valor | 7 | `values.py:8-9`; `models.py:39-40, 65-66`; `calculation_context.py:17, 161`; `variable_seed_validator.py:216`; `platform_contracts.md:12` |
| 14. sem relação com o contrato | ~70 | identificadores Python (`is_numeric`, `NumericValue`, `CategoricalValue`, `is_categorical`, `declare_categorical_variables`, `_categorical_variable_ids`, `_require_numeric*`, `NonNumericAggregationError`, `numeric_part`, `numeric_id`), comentários "ranges numericos", mensagens "valores não numéricos" |

## 5. Pontos alterados

Classes 1–3 (2), 10–11 (6) e 12–13 (7). Mais duas asserções novas dentro de testes existentes (sem novo teste):
`VariableDefinition(..., "numeric"|"categorical")` levanta `ValueError`, e `validate_enum_values` rejeita
`"numeric"`/`"categorical"`.

## 6. Pontos deliberadamente não alterados

Classe 14 inteira: são nomes de funções, tipos e exceções que descrevem a natureza Python do valor, não o rótulo do
contrato. Renomeá-los mudaria API interna sem ganho de contrato e está fora do que foi autorizado.

## 7. Testes

| | antes | depois | diferença |
|---|---:|---:|---:|
| `python3 -m pytest -q` | 1414 passed | 1414 passed | 0 |
| failed / errors | 0 / 0 | 0 / 0 | 0 |

Verificação direta: `VALUE_TYPES = ['categorico', 'numerico']`, default `numerico`; `numerico`/`categorico` aceitos;
`numeric`/`categorical` rejeitados.

## 8. Decisão sobre `declared_result_states`

Registrada em `DECISION_REFINEMENT_R1_declared_result_states.md` como **refinamento R1 de D1/D2** (não D5):

1. `declared_result_states` é local — estados que a própria variável produz pela sua própria regra;
2. estados herdados não são redeclarados; a lista não é transitiva;
3. estado efetivo (próprio, herdado ou de agregação state-aware) é responsabilidade do runtime;
4. propagação pertence à Stage 3 (3.1–3.3);
5. agregação state-aware pertence à Stage 3.4;
6. `NO_APPLICABLE_RULE` é estado de negócio, nunca exceção, erro, `None` ou `NaN`.

Fecha WB-AUD-13 da auditoria inicial.

## 9. Análise de `NO_APPLICABLE_RULE` (A41 v7, grafo real)

| papel | linhas | declara? |
|---|---|---|
| produtor local (`else "F"`) | r39 `retirada_condensado_grupo` L4_L5, r42 L6_L7 | sim — `NO_APPLICABLE_RULE → F` |
| herdeiro por equação | r48–r51 `retirada_condensado_linha` L4–L7; r54 `retirada_condensado_total` | não (correto por R1) |
| herdeiro por agregação temporal | r40, r41, r43, r44 (grupo mensal/anual); r52, r53 (linha); r55, r56 (total) | não (correto por R1) |
| consumido em | somente dentro do A41; nenhum outro workbook consome variáveis do A41 | — |

Correção factual ao exemplo do prompt (§8): em A41 v7 `hes` **não** produz `NO_APPLICABLE_RULE`. É entrada categórica
e só pode resultar em `INVALID_INPUT` (fora de `allowed_values`). Quem produz `NO_APPLICABLE_RULE` é
`retirada_condensado_grupo`, quando nenhum ramo cobre a combinação de `hes@L4/@L5` (ou `@L6/@L7`). A regra R1 se
aplica igualmente.

## 10. Reauditoria dos cinco workbooks

Probe da auditoria inicial reexecutado com o código migrado (`evidence/probe_rerun.txt`).

| item | resultado |
|---|---|
| A019 | A41 20/20 e energy 24/24 resolvidos; **max_ht 3, production 4 (+1 não executável), yield 1 ambíguos** — iguais à auditoria inicial |
| name + frequency + scope | **max_ht 20 pares, production 5 pares com a mesma identidade** — evidência concreta, iguais à inicial |
| @Lx | conforme (1 198 referências) |
| @grupo | conforme, exceto **MaxHT r120** ainda `(massa_total_max_ht@L1_L3 + massa_total_max_ht + massa_total_max_ht)/refinery` |
| frequency | conforme |
| scope | **yield `L6_7` em 48 linhas; production r89 `planta`** — ainda presentes |
| value_type | **conforme** — 572/572 células em `{numerico, categorico}` = enum do código (resolvido nesta execução) |
| allowed_values | conforme (`hes`, 5 valores = literais usados) |
| declared_result_states | conforme (r39, r42) e, por R1, nenhum herdeiro precisa declarar |
| NO_APPLICABLE_RULE | conceitualmente fechado (R1) |
| cross-workbook | inalterado: 9 vínculos OK; 3 divergências de representação/grafia (WB-AUD-12, WB-AUD-16), não bloqueantes |
| MaxHT | **bloqueado** — WB-AUD-01, WB-AUD-02 presentes |
| Production | **bloqueado** — WB-AUD-03, 04 (`oee_total` r30, `pick_up_total` r48), 05 (SUM em `tpd`), 06 (`consumo_bauxita`), 08, 10 (r52 `1,0902`) presentes |
| Yield | **bloqueado** — WB-AUD-07 (`L6_7`), 10 (r2, r10, r17, r82, r97), 11 presentes |
| Energy | conforme com pendências não bloqueantes |
| A41 | conforme com pendências não bloqueantes (WB-AUD-14 formato de serialização) |

A instrução de considerar corrigidos os pares Soma/Média não pôde ser confirmada: nos arquivos disponíveis os pares
continuam com `name + frequency + scope` idênticos (ex.: MaxHT r4/r6 `producao`, mensal, linha/L1_L7). Isto é a mesma
evidência da auditoria inicial, não uma reabertura.

## 11. Matriz cross-workbook

Inalterada (`evidence/cross_workbook.csv`): `lth` (yield→A41, production→energy/max_ht/yield), `producao`
(production→energy/max_ht), `yield` (yield→production), `pick_up_total` e `lth_total` (production→energy) resolvem
por identidade completa. Divergências: `pick_up` e `lth_meta` (energy declara uma linha `linha/L1_L7`, production
declara sete linhas por linha de produção) e grafia `tpd`/`t/d` de `producao`. Nenhuma divergência de `value_type`.

## 12. Blockers

Um único blocker, externo ao código:

```text
BLK-1  As versões corrigidas de MaxHT, production e yield não foram entregues à sessão.
       Os arquivos presentes têm os mesmos SHA-256 da auditoria de 2026-09-25 e ainda contêm
       WB-AUD-01, 02, 03, 04, 05, 06, 07 (bloqueantes) e 08, 10, 11.
       Ação: enviar os arquivos corrigidos; a reauditoria é reexecutável com
       evidence/probes/probe2.py.
```

Não há decisão de negócio pendente: WB-AUD-13 foi fechado por R1 e WB-AUD-09 pela migração.

## 13. Pendências Stage 3

| pendência | etapa | depende |
|---|---|---|
| `EvaluationResult` (`value`, `result_state`, `detail`) e tradução `"F"` → `NO_APPLICABLE_RULE` | 3.1 | A41 r39, r42 |
| propagação e isolamento de estado; cálculo do estado efetivo (R1) | 3.2–3.3 | A41 r48–r51, r54 |
| agregação state-aware (Política B com estado) | 3.4 | A41 r40, r41, r43, r44, r52, r53, r55, r56 |
| `BLOCKED_BY_UPSTREAM_ERROR` (erro técnico, ex.: `ln` ≤ 0) | 3.x | dependentes de A41 r6–r8, r16–r18 |
| validação runtime de `allowed_values` / `INVALID_INPUT` | 3.x | `hes` |
| builder lendo `allowed_values` e `declared_result_states` do workbook | 3.x / 2.4 | todos |
| agrupar linhas por linha de produção numa definição (WB-AUD-12) | 2.4 | production, yield, energy |

## 14. STAGE_2.3_GATE

| critério (§31) | estado |
|---|---|
| 1. cinco workbooks conformes | **não verificável** — correções não recebidas (BLK-1) |
| 2. `numerico/categorico` vocabulário único do código | sim |
| 3. testes passam | sim, 1414 |
| 4. A019 consistente | sim para A41/energy; não nos arquivos disponíveis de max_ht/production/yield |
| 5. sem colisões reais de identidade | não nos arquivos disponíveis (25 pares) |
| 6. `NO_APPLICABLE_RULE` fechado | sim (R1) |
| 7. sem decisão de negócio pendente | sim |
| 8. gaps restantes classificados como Stage 3 | sim (§13) |

```text
STAGE_2.3_GATE: BLOCKED
Blocker: BLK-1 — workbooks corrigidos de MaxHT v6, production v3 e yield v6 não disponíveis na sessão.
```

Recebidos os arquivos corrigidos, só a reauditoria (§10) precisa ser repetida; A e B não mudam.
