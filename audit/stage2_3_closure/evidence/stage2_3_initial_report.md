# Etapa 2.3 — Auditoria de Conformidade dos Workbooks

```text
Etapa:            2.3 — Auditoria dos workbooks após o fechamento dos contratos transversais
Branch:           feature/area-41-block
HEAD:             4510865f83fd3cf628782ad6a2e3de502aac4e7e
origin/main:      4510865f83fd3cf628782ad6a2e3de502aac4e7e
Working tree:     CLEAN (antes e depois)
Foundation:       4510865f83fd3cf628782ad6a2e3de502aac4e7e
Workbooks:        A41 v7 · energy v3 · MaxHT v6 · production v3 · yield v6
Status:           AUDITORIA CONCLUÍDA
Resultado:        STAGE_2.3_GATE: BLOCKED (inconsistências de workbook em MaxHT v6, production v3 e yield v6)
```

Auditoria read-only. Nenhum `.xlsx`, seed, código, teste ou documento normativo foi alterado; nenhum commit
foi feito. Os artefatos desta etapa estão fora do repositório (scratchpad da sessão), em `evidence/`.

Classificação usada em todos os achados (§29 do prompt):
**A** = erro do workbook · **B** = gap do runtime/plataforma · **C** = decisão conceitual pendente · **D** = diferença legítima.

---

## 1. Pre-flight

| item | resultado |
|---|---|
| branch | `feature/area-41-block` |
| HEAD | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` |
| origin/main | `4510865f83fd3cf628782ad6a2e3de502aac4e7e` (após `git fetch --prune`) |
| HEAD == origin/main == SHA esperado | sim (divergência `0 0`) |
| working tree | limpo |
| cinco workbooks identificados | sim, uma cópia de cada, sem versões concorrentes (§2) |
| suíte existente | `python3 -m pytest -q` → **1414 passed**, 0 failed |

```text
PRE-FLIGHT: PASS
```

## 2. Identificação dos cinco workbooks

Todos localizados em `/root/.claude/uploads/afd1cfda-…/` (uploads da sessão). Nenhum está no repositório.
Busca em todo o disco: uma única cópia de cada nome; nenhuma ambiguidade.

| bloco | arquivo | tamanho | modificado (UTC) | abas | aba oficial | dimensão |
|---|---|---:|---|---|---|---|
| area_41 | `descritivo_das_variáveis_A41_v7.xlsx` | 38 409 B | 2026-09-25 23:39:50 | 1 (`A41`) | `A41` | A1:R308 |
| energy | `descritivo_das_variáveis_energy_v3.xlsx` | 37 567 B | 2026-09-25 23:39:50 | 1 (`energy`) | `energy` | A1:R307 |
| max_ht | `descritivo_das_variáveis_MaxHT_v6.xlsx` | 46 113 B | 2026-09-25 23:39:50 | 1 (`MaxHT`) | `MaxHT` | A1:S336 |
| production | `descritivo_das_variáveis_production_v3.xlsx` | 36 207 B | 2026-09-25 23:39:50 | 1 (`production`) | `production` | A1:R302 |
| yield | `descritivo_das_variáveis_yield_v6.xlsx` | 40 689 B | 2026-09-25 23:39:50 | 1 (`yield`) | `yield` | A1:R255 |

Nenhuma aba oculta/veryHidden, nenhuma fórmula Excel (`=`), nenhum comentário, nenhum named range, nenhuma tabela.
Células mescladas: só a linha 1 de agrupamento (`A1:D1`, `E1:F1`, `G1:H1`, `I1:L1`) em A41/energy/MaxHT/production;
yield não tem mesclagem e usa cabeçalho de uma linha (linha 1) em vez de duas.
A energy v2 tinha a aba auxiliar `Planilha1`; a v3 não tem mais.

## 3. SHA-256

| bloco | SHA-256 |
|---|---|
| area_41 | `0fe3f1ff5a7f884ec2a279daccd909ad549da6ac87da8f359e33fbdd1a3c1517` |
| energy | `9b73daaf7496440c1211a63c7a3567cfab0ef3caa32376afe6a0828bd5e7a4e5` |
| max_ht | `e6bffc02d41840535e278d0d464598de038976651a3f6814df408ce856c815d4` |
| production | `25b90405ece47e00618e57ce680682073a70059106f9371ce47eabfb29bc2dc5` |
| yield | `be2f1758aab9bb708f4ab71240d693fa6522b17561a567698abaca909810ee05` |

## 4. Baseline D1–D4

Extraído literalmente de `audit/stage2_2_state_contract/evidence/decision_matrix.csv` e `REPORT.md` §20,
commit `5c8dcfc` (branch histórica `claude/funny-noether-nbcr7b`; o artefato não existe em `feature/area-41-block`).

| decisão | contrato fechado (texto do artefato) | implicação para o workbook |
|---|---|---|
| D1 | "C (declaração na VariableDefinition via `declared_result_states`) + A (sentinela textual mantido na fórmula, sem mudança de sintaxe), com tradução feita pelo builder." Builder valida que todo literal-estado da fórmula pertence a `declared_result_states` e que nenhum literal está ao mesmo tempo em `allowed_values` e `declared_result_states`. | Fórmula continua escrevendo `"F"`; a variável-alvo declara o mapeamento rótulo → literal. |
| D2 | "Taxonomia GLOBAL fixa de 4 rótulos (VALID, NO_APPLICABLE_RULE, INVALID_INPUT, VALIDATION_FAILED); cada VariableDefinition declara em `declared_result_states` QUAIS desses rótulos ela pode produzir. Nenhuma variável cria rótulo novo." | Só rótulos globais; `declared_result_states=[]` é no-op para os 4 blocos já implementados. |
| D3 | "Estado de negócio: isolar aos descendentes alcançáveis. Erro técnico: mesma mecânica de isolamento, NUNCA vira `result_state`; terceira categoria por nó: `BLOCKED_BY_UPSTREAM_ERROR`." | Workbook não modela erro técnico; nada a declarar. |
| D4 | "Excluir `UNAVAILABLE`/`DATA_NOT_YET_READY` da taxonomia agora." | Nenhum workbook pode usar esses rótulos. |
| Checklist §20 | "`value_type` declarado — obrigatório em toda VariableDefinition (**numeric \| categorical**; padrão numeric)"; "toda variável categorical com domínio fechado declara `allowed_values`". | Vocabulário do campo é `numeric`/`categorical`. |

### Matriz D1–D4 por workbook

| workbook | D1 | D2 | D3 | D4 | observação |
|---|---|---|---|---|---|
| area_41 | **Conforme** — único literal de resultado (`"F"`) está declarado em r39/r42 (`NO_APPLICABLE_RULE → F`) | **Conforme** — rótulo global; `hes` (entrada) sem estado | **Conforme** — nada de erro técnico modelado como estado | **Conforme** | `value_type` com rótulo fora do vocabulário (WB-AUD-09); propagação a dependentes não declarada (WB-AUD-13, decisão) |
| energy | Conforme (no-op, sem literal de resultado) | Conforme (`declared_result_states` vazio) | Conforme | Conforme | WB-AUD-09 |
| max_ht | Conforme (no-op) | Conforme (vazio) | Conforme | Conforme | WB-AUD-09 |
| production | Conforme (no-op; o `IF` de `lth` tem ramos numéricos) | Conforme (vazio) | Conforme | Conforme | WB-AUD-09 |
| yield | Conforme (no-op) | Conforme (vazio) | Conforme | Conforme | WB-AUD-09 |

Nenhum workbook contém `"ERRO!!!"`, `UNAVAILABLE` ou `DATA_NOT_YET_READY`.

## 5. Contratos transversais (código em `4510865`)

| contrato | implementação lida | comportamento usado nesta auditoria |
|---|---|---|
| A019 | `app/engine/reference_resolver.py` (`resolve_reference`, `translate_expression`) | Cada expressão foi traduzida pelo resolver real, com a frequência e o escopo declarados da linha consumidora. Ambiguidade residual = erro (regra 5). Consumidor com escopo `linha/L1_L7` exige que todas as instâncias apontem para a mesma definição (regra 4). |
| `@Lx` / `@grupo` | `app/engine/scoped_reference.py` (`scope_type_for`, `to_internal`) | `@L1..@L7` → `linha`; `@L1_L3`, `@L4_L5`, `@L6_L7`, `@L1_L7` → `linha_grupo`. Qualquer outro sufixo é `InvalidScopeReferenceError`. |
| escopos | `ScopeResolver.LINE_SCOPES`, `LINE_GROUP_SCOPES`, `CANONICAL_PLANT_SCOPE = ("planta", "PLANTA")`; `ALLOWED_SCOPE_VALUES` | `L6_7` e `planta` (minúsculo) são rejeitados. |
| frequência | `ALLOWED_FREQUENCIES = {diário, mensal, anual}` | — |
| unidades | `ALLOWED_UNITS`, `UNIT_ALIASES = {tph: t/h}` (validator); `app/domain/units.py` `_ALIASES = {tpd: t/d}`, `required_sum_factor` | SUM checada com `required_sum_factor`. |
| `value_type` | `app/domain/values.py` `VALUE_TYPES = {"numeric", "categorical"}`; `VariableDefinition.__post_init__` rejeita outro valor | — |
| `ln()` | `expression_parser.ALLOWED_FUNCTIONS = {"ln": 1}`; `MathDomainError` para x ≤ 0 | — |
| Política B | `TemporalAggregationService._require_numeric_series` | Um período não numérico invalida o agregado inteiro. |
| parser | `ExpressionParser.parse` | Toda expressão traduzida foi parseada; decimal com vírgula vira `Tuple` → `UnsafeExpressionError`. |

`allowed_values`, `declared_result_states`, `EvaluationResult` e `BLOCKED_BY_UPSTREAM_ERROR` **não existem** no código de `4510865`
(confirmado na G1). Tudo o que os workbooks declaram nesses campos é, por definição, **dependência para Stage 3**.

## 6. Inventário físico

| bloco | linhas físicas (max_row) | 1ª linha de dados | última linha semanticamente preenchida | linhas semânticas | linhas vazias no intervalo |
|---|---:|---:|---:|---:|---:|
| area_41 | 308 | 3 | 56 | 54 | 0 |
| energy | 307 | 3 | 58 | 56 | 0 |
| max_ht | 336 | 3 | 122 | 120 | 0 |
| production | 302 | 3 | 90 | 88 | 0 |
| yield | 255 | 2 | 255 | 254 | 0 |

`max_row` inclui linhas só formatadas; a última linha semântica é a última com qualquer célula não vazia.
Colunas (todas as cinco): `Type, name, description, unit, value, version, variable_type, frequency, scope_type, scope_value,
source_reference, status, value_type, allowed_values, declared_result_states, expression, fonte, OBS`.
MaxHT tem uma 19ª coluna sem cabeçalho, vazia em todas as linhas semânticas.

## 7. Inventário semântico

| | area_41 | energy | max_ht | production | yield |
|---|---:|---:|---:|---:|---:|
| linhas | 54 | 56 | 120 | 88 | 254 |
| variáveis | 47 | 52 | 116 | 71 | 246 |
| parâmetros | 7 | 4 | 4 | 17 | 8 |
| equações executáveis | 20 | 24 | 29 | 27 | 138 |
| agregações temporais | 10 | 11 | 78 | 28 | 80 |
| entradas (`entrada`/`entrada_externa`) | 17 | 17 | 9 | 16 | 28 |
| saídas calculadas | 30 | 35 | 107 | 55 | 218 |
| referências resolvidas (IDs) | 107 | 89 | 85 | 122 | 957 |
| `@Lx` | 54 | 49 | 56 | 115 | 924 |
| `@grupo` | 10 | 0 | 1 | 0 | 0 |
| variáveis categóricas | 4 linhas (`hes` × L4–L7) | 0 | 0 | 0 | 0 |
| `allowed_values` | 4 | 0 | 0 | 0 | 0 |
| `declared_result_states` | 2 | 0 | 0 | 0 | 0 |
| `ln()` | 6 | 0 | 0 | 0 | 0 |
| frequências | diário 31, mensal 11, anual 5, —7 (param.) | diário 33, mensal 18, anual 1, —4 | diário 36, mensal 40, anual 44 | diário 42, mensal 19, anual 27 | diário 87, mensal 80, anual 86, —1 |
| escopos | linha, linha_grupo, planta/PLANTA | linha, linha_grupo | linha, linha_grupo | linha, linha_grupo, planta/**planta** | linha, linha_grupo (**L6_7**) |

### O que mudou em relação à versão anterior (diferença estrutural)

| bloco | anterior → atual | mudança |
|---|---|---|
| area_41 | v6 → v7 | `hes_l4..hes_l7` viraram um único nome `hes` com escopo por linha; fórmulas passaram a `hes@L4..@L7`; unidade de `vazao_ltp` `-` → `m³/h`. Nomes espacializados eliminados. |
| energy | v2 → v3 | Só as três colunas novas; nenhuma linha ou expressão alterada; aba `Planilha1` removida. |
| max_ht | v5 → v6 | 152 → 120 linhas. Nomes espacializados (`*_l123/_l45/_l67`) → nomes genéricos com `linha_grupo`; removidas as variantes `Somatório` de fluxos por linha (m³/mês, kg/mês…). **Regressão:** `esp_max_ht_planta` (r120) perdeu `@L4_L5`/`@L6_L7` (WB-AUD-01). Gêmeos Soma/Média nos totais de grupo permanecem (WB-AUD-02). |
| production | v1 → v3 | `lth_alvo` → `lth_meta`; `fator_*` passaram a `linha`; novas entradas `fator_mrn_kg_t`, `fator_mpsa_kg_t`; `desaguamento_oee` ganhou `100 *`; `consumo_bauxita anual` passou a `linha_grupo`; `desaguamento_produtividade` ganhou `scope_value="planta"`. Os fragmentos malformados de `oee_total`/`pick_up_total` **não** foram corrigidos (WB-AUD-04). |
| yield | v4 → v6 | `ltp_tc` de parâmetro → variável diária; corrigidos os índices `@L1` repetidos em `ltp_lth_base` e `eoc_solids_base`. `L6_7` permanece (WB-AUD-07). |

## 8. Auditoria de identidade (`name + frequency + scope`)

Chave usada: `(name, frequency, scope_type, scope_value)`; `unit` e `expression` **não** entram (contrato).

| bloco | colisões | detalhe |
|---|---:|---|
| area_41 | 0 | — |
| energy | 0 | — |
| max_ht | **20 pares** | `producao`, `refinery`, `lth_total`, `massa_total_max_ht` (L1_L3/L4_L5/L6_L7), `producao_grupo` (idem), `massa_total_max_ht_total` — em mensal e anual, cada par = `Somatório` (t/mês, kg/ano…) + `Média` (t/d, kg/d…). WB-AUD-02 |
| production | **5 pares** | `producao_planta`, `consumo_mrn`, `consumo_mpsa`, `consumo_cbg`, `consumo_bauxita` mensal: `Média` + `Somatório`, **ambos com unidade `tpd`** (nem a unidade distingue). WB-AUD-03 |
| yield | 0 | — |

Entidades "uma linha por linha de produção" (mesmo nome e frequência, uma linha do workbook por `L1..L7`):
area_41 `valor_retirada` (L1–L3), `hes` (L4–L7), `retirada_condensado_linha` (L1–L7); production `lth_meta`, `pick_up_yield`, `pick_up`;
yield `tanque_base`, `tanque`. Não são colisões (escopos diferentes). Só geram problema quando consumidas sem `@Lx`
por uma equação de escopo `linha/L1_L7` (WB-AUD-12).

## 9. Auditoria A019

Toda expressão executável foi traduzida por `reference_resolver.translate_expression` sobre um índice construído
**apenas com as linhas do próprio workbook** e depois parseada por `ExpressionParser`.

| bloco | resolvidas | ambíguas/invalidas | não encontradas | não executáveis após resolver |
|---|---:|---:|---:|---:|
| area_41 | 20/20 | 0 | 0 | 0 |
| energy | 24/24 | 0 | 0 | 0 |
| max_ht | 26/29 | 3 (r120, r121, r122) | 0 | 0 |
| production | 23/27 | 4 (r23, r28, r30, r52) | 0 | 1 (r48) |
| yield | 137/138 | 1 (r14) | 0 | 5 com vírgula decimal (r2, r10, r17, r82, r97) |

Classificação das referências:

| classe | onde |
|---|---|
| explicitamente resolvível (`@Lx`/`@grupo`) | todas as 1 198 `@Lx` e 11 `@grupo`, exceto r120 do MaxHT |
| resolvível pelo contexto permitido (mesmo nome, mesma frequência, escopo mais específico) | demais referências, incluindo cruzamento de frequência (`vazao_ltp` mensal → consumidor diário, regra 2) |
| ambígua | MaxHT r120 (três grupos), r121/r122 (gêmeos); production r30 (`lth_meta` sem `@` dentro do fragmento malformado) |
| dependente de comportamento não contratado | production r23, r28, r52; yield r14 — resolver exige uma definição única, workbook declara uma por linha (WB-AUD-12) |
| incompatível | production r48 (`lth (pick_up@L6…` vira chamada de função) |

## 10. Auditoria `@Lx`

Nenhuma confusão entre linha individual e grupo: todo `@L1..@L7` aponta para entidade de `scope_type=linha` declarada com
aquele `scope_value` (ou para uma definição `linha/L1_L7` que materializa aquela instância). Em A41, `hes@L4..@L7` resolve
para as quatro linhas `hes` (r25–r28), uma por linha, sem conhecimento especial de A41.

## 11. Auditoria `@grupo`

| workbook | variável (linha) | referência | grupo | scope do consumidor | frequência | interpretação |
|---|---|---|---|---|---|---|
| area_41 | `retirada_condensado_linha` (r45–r47) | `retirada_condensado_grupo@L1_L3` | L1_L3 | linha/L1..L3 | diário | escopo espacial: rateio do valor de grupo por linha |
| area_41 | `retirada_condensado_linha` (r48–r49) | `retirada_condensado_grupo@L4_L5` | L4_L5 | linha/L4..L5 | diário | idem |
| area_41 | `retirada_condensado_linha` (r50–r51) | `retirada_condensado_grupo@L6_L7` | L6_L7 | linha/L6..L7 | diário | idem |
| area_41 | `retirada_condensado_total` (r54) | `@L1_L3 + @L4_L5 + @L6_L7` | 3 grupos | linha_grupo/L1_L7 | diário | escopo espacial: soma explícita de entidades de grupo já calculadas |
| max_ht | `esp_max_ht_planta` (r120) | `massa_total_max_ht@L1_L3` + 2 termos **sem** sufixo | L1_L3 (+ ?) | linha_grupo/L1_L7 | diário | escopo espacial, **incompleto** (WB-AUD-01) |

Nenhum `@grupo` representa mês, ano, hora ou agregação implícita. Todos referenciam uma entidade de grupo que existe e é calculada
por equação própria.

## 12. Remoção de agrupamentos temporais (`\h`, `\mês`, `\ano`)

Busca por `\`, `@mês`, `@ano`, `@h` e sufixos temporais em `name`, `expression` e `scope_value`: **nenhuma ocorrência** nos cinco workbooks.
As ocorrências textuais restantes são legítimas: `producao_t_h` (conversão t/d → t/h), `total_horas_dia`, `n_dias_ano` (grandezas),
e descrições de agregação ("…de cada mês").

O que ainda carrega a distinção temporal de forma indevida são os **gêmeos Soma/Média** (mesma identidade, só a base temporal da
unidade muda: t/mês × t/d). A v6 do MaxHT removeu esses gêmeos nas grandezas por linha, mas os manteve nos totais de grupo; a v3
de production mantém cinco pares. Classificação: **agrupamento temporal indevido remanescente** → WB-AUD-02, WB-AUD-03.

## 13. Auditoria de frequência

Todas as frequências de variáveis pertencem a `{diário, mensal, anual}`. Parâmetros: sem frequência em A41, energy e yield;
`anual` em MaxHT e production — o contrato A019 ignora frequência para parâmetros (regra 1), então é diferença legítima (D).
Referências entre frequências (ex.: `vazao_ltp` mensal usado por `retirada_cond_corr_ltp` diário; `fator_ajuste_lth` mensal
usado por `lth` diário) resolvem pela regra 2 do A019 sem ambiguidade. Nenhuma mudança de frequência implícita fora das
linhas de agregação.

## 14. Auditoria de scope

| valor | onde | status |
|---|---|---|
| `L6_7` | yield, 48 linhas `linha_grupo` | **não suportado** — fora de `ALLOWED_SCOPE_VALUES`; `ScopeResolver.resolve_scopes` rejeita. WB-AUD-07 |
| `planta` (minúsculo) | production r89 `desaguamento_produtividade` | **não suportado** — forma canônica é `PLANTA`; `ScopeResolver` levanta `Invalid plant scope_value: planta`. WB-AUD-08 |
| `planta/PLANTA` | area_41 r32–r38 | conforme |
| demais | todos | conforme |

## 15. Auditoria `value_type`

- Todas as 572 linhas preenchem `value_type`, com o vocabulário `numerico` (568) e `categorico` (4). O contrato (Etapa 2.2 §20) e o
  código (`VALUE_TYPES`) usam `numeric` e `categorical`. `VariableDefinition` rejeitaria `numerico`. **WB-AUD-09** (A).
- Coerência semântica: correta em todos os blocos. As únicas categóricas são `hes` (L4–L7), usadas apenas em comparações de
  igualdade com literais; nenhuma aritmética sobre elas. Nenhuma variável `numerico` é comparada com texto, exceto o resultado
  `"F"` de `retirada_condensado_grupo` (r39/r42), que é estado declarado e não valor — tratamento correto segundo D1/D2
  (`value_type` continua `numerico`; não é `mixed`).
- Nenhuma expressão produz booleano como resultado final.

## 16. Auditoria `allowed_values`

| variável | linhas | domínio declarado | usado nas expressões | resultado |
|---|---|---|---|---|
| `hes` | area_41 r25–r28 | `Normal`, `LC`, `Overhaul/Parada`, `1 By pass`, `1 By pass e LC` | exatamente os mesmos 5 (r39, r42) | conforme: sem valor usado fora do domínio, sem valor declarado não usado; idêntico nas quatro linhas |

Interseção `allowed_values ∩ literais de estado` (D1 §6.4): vazia. Formato de serialização (valores separados por quebra de linha
na célula) não está definido pelo contrato — WB-AUD-14. Validação runtime: **dependência para Stage 3**.

## 17. Auditoria `declared_result_states`

| variável | linhas | declaração | literal na fórmula | rótulo global? | resultado |
|---|---|---|---|---|---|
| `retirada_condensado_grupo` | area_41 r39 (L4_L5), r42 (L6_L7) | `NO_APPLICABLE_RULE → F` | `else "F"` (ramo final) | sim | conforme D1/D2 |

`retirada_condensado_grupo@L1_L3` (r22) não tem condicional e corretamente não declara estado. A diferença entre os campos está
preservada: `allowed_values` fica na entrada (`hes`), `declared_result_states` na saída; nenhuma variável declara os dois.

Pendência: os **dependentes** de r39/r42 (r48–r51, r54 e os agregados r40, r41, r43, r44, r52, r53, r55, r56) podem receber
`NO_APPLICABLE_RULE` por propagação (D3) e não declaram nada. D1 exige declaração para *literais na fórmula*; D2 fala em
"estados que a variável pode produzir". O contrato não diz se estado herdado precisa ser declarado. **WB-AUD-13** (C).

## 18. Estados × erros técnicos

- Resultado de negócio: só `"F"` → `NO_APPLICABLE_RULE` (A41). Nenhum workbook representa erro técnico como texto.
- Erro técnico possível: `ln(x)` com x ≤ 0 em A41 r6–r8 e r16–r18 (`MathDomainError`). Pelo D3 é erro técnico, nunca estado;
  hoje aborta a rodada (F-001); no contrato, os descendentes viram `BLOCKED_BY_UPSTREAM_ERROR`. **Dependência para Stage 3.**
- `"Normal"`/`"LC"`… são valores válidos da categórica `hes`, não estados nem erros.
- `INVALID_INPUT` (hes fora do domínio) só é detectável com `allowed_values` no runtime. **Dependência para Stage 3.**

## 19. Auditoria de agregações

208 linhas de agregação. Detalhe completo em `evidence/aggregations.csv`.

| bloco | tipos | fonte explícita? | problemas |
|---|---|---|---|
| area_41 | AVERAGE ×10 | sim | 4 agregados com origem que declara `NO_APPLICABLE_RULE` (r40, r41, r43, r44) e 6 com origem que herda o estado (r52, r53, r55, r56) → **Política B** |
| energy | WEIGHTED_AVERAGE ×7, AVERAGE ×3, MOVING_AVERAGE ×1 | sim, exceto r6 (média móvel sem nome de origem) | WB-AUD-15 |
| max_ht | AVERAGE ×58, SUM ×20 | sim | 20 SUMs dimensionalmente coerentes (fator 1 para /d, 24 para m³/h). Gêmeos WB-AUD-02 |
| production | AVERAGE ×15, SUM ×10, WEIGHTED_AVERAGE ×2, MOVING_AVERAGE ×1 | sim | SUMs com unidade de destino `tpd` (WB-AUD-05); `consumo_bauxita` mensal/anual sem origem diária de grupo (WB-AUD-06); gêmeos WB-AUD-03 |
| yield | AVERAGE ×80 (todas mensais) | **não** — "Média dos dados entre os dias 01 e 30 ou 31 de cada mês" | origem implícita = mesmo nome, diário, mesmo escopo (WB-AUD-15) |

Médias ponderadas (energy r32, r34, r45, r47, r49, r54, r58; production r5, r6): peso `producao_planta_t_h` / `producao_planta`, existente
em diário no mesmo escopo; forma `(X * P) / P` mantida como semântica de média ponderada, não simplificada.

**Política B — quem depende:** somente area_41 (r40, r41, r43, r44 diretamente; r52, r53, r55, r56 por propagação). O workbook fornece
informação suficiente (origem, tipo, janela). A regra runtime (estado ≠ VALID invalida o agregado) é **dependência para Stage 3**;
hoje o agregador já falha com `AggregationFailureError` sobre `"F"`.

## 20. Auditoria `ln()`

| linha | variável | argumento | escopo/frequência | domínio | unidade | tipo |
|---|---|---|---|---|---|---|
| r6–r8 | `retirada_cond_corr_ltp` | `vazao_ltp` | linha_grupo L1_L3/L4_L5/L6_L7, diário (argumento mensal) | exige > 0 | argumento m³/h; resultado declarado m³/h (correlação empírica) | numérico |
| r16–r18 | `retirada_cond_corr_lth` | `lth_grupo * fator_retirada_cond_corr_lth` | idem, diário (fator mensal) | exige > 0 | idem | numérico |

Compatível com o contrato de `4510865` (nome na allowlist, aridade 1, argumento numérico). Entrada ≤ 0 → `MathDomainError`
(erro técnico, D3). `ln` de grandeza com dimensão é convenção de correlação empírica, não erro de workbook (D).

## 21. Matriz de dependências (resumo)

| origem | referência | destino | frequência | scope | value_type | resultado |
|---|---|---|---|---|---|---|
| area_41 `retirada_condensado_grupo` L4_L5/L6_L7 | `hes@L4..@L7` | area_41 `hes` | diário | linha/L4..L7 | categórico | OK |
| area_41 `retirada_cond_corr_ltp` | `vazao_ltp` | area_41 `vazao_ltp` (mensal) | diário ← mensal | linha_grupo | numérico | OK (regra 2) |
| area_41 `retirada_condensado_linha` | `retirada_condensado_grupo@grupo` | area_41 | diário | linha ← linha_grupo | numérico | OK; herda estado → Stage 3 |
| area_41 `retirada_condensado_total` | `@L1_L3 + @L4_L5 + @L6_L7` | area_41 | diário | linha_grupo | numérico | OK; herda estado → Stage 3 |
| max_ht `esp_max_ht_planta` diário | `massa_total_max_ht` ×2 sem `@` | max_ht (3 grupos) | diário | linha_grupo/L1_L7 | numérico | **AMBÍGUA** |
| max_ht `esp_max_ht_planta` mensal/anual | `massa_total_max_ht_total` | max_ht (gêmeos) | mensal/anual | linha_grupo/L1_L7 | numérico | **AMBÍGUA** |
| production `lth`, `oee` | `lth_meta` | production (7 linhas) | diário ← anual | linha/L1_L7 | numérico | **GAP DE PLATAFORMA** (WB-AUD-12) |
| production `producao` | `pick_up` | production (7 linhas) | diário | linha/L1_L7 | numérico | **GAP DE PLATAFORMA** (WB-AUD-12) |
| production `oee_total`, `pick_up_total` | fragmento malformado | — | diário | linha_grupo | numérico | **INCOMPATÍVEL** |
| production `consumo_bauxita` mensal/anual | origem diária `linha_grupo` | inexistente | mensal/anual | linha_grupo | numérico | **INCOMPATÍVEL** |
| yield `n_ppt` | `tanque_base`, `tanque` | yield (7 linhas) | diário ← anual | linha/L1_L7 | numérico | **GAP DE PLATAFORMA** (WB-AUD-12) |
| yield linhas `L6_7` | escopo | — | todas | linha_grupo | numérico | **INCOMPATÍVEL** (WB-AUD-07) |
| demais (1 360 referências traduzidas) | — | — | — | — | — | OK |

## 22. Matriz cross-workbook

Detalhe em `evidence/cross_workbook.csv`. Toda entrada com `fonte = bloco X` foi comparada com o produtor pela identidade completa.

| consumidor | entidade | frequência | scope | unit | produtor | resultado |
|---|---|---|---|---|---|---|
| area_41 | `lth` | diário | linha/L1_L7 | m³/h | yield | OK |
| area_41 | `hes` (L4–L7) | diário | linha | - | maintenance (fora dos 5) | não verificável aqui |
| energy | `producao` | diário | linha/L1_L7 | tpd | production | OK |
| energy | `pick_up` | diário | linha/**L1_L7** (1 linha) | g/l | production declara **7 linhas** (L1…L7) | divergência de representação (WB-AUD-12) |
| energy | `lth_meta` | anual | linha/**L1_L7** (1 linha) | - | production declara **7 linhas** | divergência de representação (WB-AUD-12) |
| energy | `pick_up_total` diário/mensal, `lth`, `lth_total` diário/mensal | — | — | — | production | OK |
| energy | `temperatura_lp`, `temperatura_lp_media`, `evaporado_total_evaporacao` | — | — | — | temperature_lp / area_04_13 (fora dos 5) | não verificável aqui |
| max_ht | `producao` | diário | linha/L1_L7 | **t/d** | production (`tpd`) | identidade OK; grafia de unidade diferente (WB-AUD-16) |
| max_ht | `lth` | diário | linha/L1_L7 | m³/h | production | OK |
| max_ht | `alimentação_evap` | diário | linha/L1_L7 | m³/h | alumina (fora dos 5) | não verificável aqui |
| production | `yield` | diário | linha/L1_L7 | g/l | yield | OK |
| production | 8 entradas `maintenance_plan`, 4 entradas `forecast` | diário | linha / linha_grupo | — | fora dos 5 | não verificável aqui |
| yield | `lth` | diário | linha/L1_L7 | m³/h | production | OK |

Divergências cross-workbook: **3** (`pick_up`, `lth_meta`, grafia `tpd`/`t/d`). Nenhuma colisão de identidade entre workbooks
com significado diferente; nenhum conflito de `value_type` entre produtor e consumidor.
As referências entre blocos são **documentais** (`fonte`); o runtime atual não liga IDs entre blocos (cada seed declara sua própria
entrada) — tema de 2.4.

## 23. Achados (divergências)

Ordenados por severidade. Severidade: **BLOCKER** impede resolução de identidade/referência ou execução correta da especificação;
**HIGH** especificação incorreta com efeito semântico, precisa corrigir antes de 2.4; **MEDIUM** inconsistência com correção
mecânica e sem ambiguidade semântica; **LOW** padronização/rastreabilidade; **INFO** registro.

| ID | bloco | severidade | categoria | classe | bloqueia 2.3? | bloqueia A41? | resumo |
|---|---|---|---|---|---|---|---|
| WB-AUD-01 | max_ht | BLOCKER | @grupo / A019 | A | sim | não | `esp_max_ht_planta` diário (r120): dois termos sem `@L4_L5`/`@L6_L7` → referência ambígua a três grupos; regressão da v6 |
| WB-AUD-02 | max_ht | HIGH | identidade / temporal | A | sim | não | 20 pares Soma/Média com a mesma `name+frequency+scope`; torna r121/r122 ambíguos |
| WB-AUD-03 | production | HIGH | identidade / temporal | A | sim | não | 5 pares Média/Somatório com mesma identidade **e** mesma unidade `tpd` |
| WB-AUD-04 | production | HIGH | expressão | A | sim | não | `oee_total` (r30) e `pick_up_total` (r48) contêm fragmentos soltos (`+ lth / lth_meta (…`, `+ lth (…`) — não executáveis; presentes desde a v1 |
| WB-AUD-05 | production | HIGH | unidade / SUM | A | sim | não | SUMs mensais/anuais mantêm unidade `tpd` (r56, r57, r78, r80, r82, r84–r88); já marcado como pendente no teste `test_production_tpd_sums_are_the_pinned_pending_set` |
| WB-AUD-06 | production | HIGH | agregação / scope | A | sim | não | `consumo_bauxita` mensal/anual (r83, r84, r88) em `linha_grupo` sem origem diária `linha_grupo` → agregação espacial implícita |
| WB-AUD-07 | yield | HIGH | scope | A | sim | não | `scope_value = L6_7` em 48 linhas; não suportado pelo contrato |
| WB-AUD-08 | production | MEDIUM | scope | A | não | não | `scope_value = planta` (r89); canônico é `PLANTA` |
| WB-AUD-09 | todos | MEDIUM | value_type | A | não | não | vocabulário `numerico`/`categorico` em vez de `numeric`/`categorical` (572 linhas) |
| WB-AUD-10 | yield, production | MEDIUM | expressão | A | não | não | vírgula decimal (`0,654`, `1,0902`) em 6 expressões; o parser rejeita (Tuple) |
| WB-AUD-11 | yield | LOW | unidade | A | não | não | `tanque` (r249–r255) sem unidade |
| WB-AUD-12 | production, yield, energy | MEDIUM | A019 | B | não | não | entidade declarada uma linha por linha de produção e consumida por equação `linha/L1_L7` sem `@`; o runtime já suporta (um ID com instância por linha, ex.: `PARAM12001`), o resolver de build não agrupa |
| WB-AUD-13 | area_41 | MEDIUM | declared_result_states | C | não | **sim, antes da Stage 3** | contrato não define se dependentes/agregados que herdam `NO_APPLICABLE_RULE` precisam declará-lo |
| WB-AUD-14 | area_41 | LOW | serialização | C | não | não | formato de `allowed_values` (quebra de linha) e de `declared_result_states` (`RÓTULO → literal`, literal sem aspas, uma entrada) não especificados |
| WB-AUD-15 | yield, energy | LOW | agregação | A | não | não | origem implícita: 80 agregações do yield e a média móvel do energy (r6) não nomeiam a variável de origem |
| WB-AUD-16 | max_ht/production/energy | LOW | unidade | D (+B menor) | não | não | `producao` é `tpd` em production/energy e `t/d` em max_ht; ambos aceitos; `UNIT_ALIASES` do validator (`tph`) e `_ALIASES` de `units.py` (`tpd`) divergem |
| WB-AUD-17 | area_41, energy | INFO | cobertura | D | não | não | declarados e nunca consumidos: A41 `retirada_meta_41a/b/c/d/x`, `retirada_performance_41c`, `retirada_manobra_linha_41a`; energy `lth_meta`, `lth_total`, `pick_up`, `pick_up_total`, `delta_t_vapor_vivo_maximo`, `temperatura_lp_media` |

## 24. Classificação workbook × runtime × decisão

| classe | achados |
|---|---|
| A — erro do workbook | WB-AUD-01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 15 |
| B — gap do runtime/plataforma | WB-AUD-12 (resolver de build); parte de WB-AUD-16 (tabelas de alias) |
| C — decisão conceitual pendente | WB-AUD-13, WB-AUD-14 |
| D — diferença legítima | WB-AUD-16 (sinônimos de unidade), WB-AUD-17; frequência de parâmetros (`anual` vs vazio); rateio assimétrico `desconto_retirada_41d` (L4_L5) × `41c` (L6_L7) já decidido em etapas anteriores e não reaberto; `retirada_condensado_grupo@L1_L3` sem condicional |

## 25. Correções necessárias (não aplicadas)

| ID | arquivo | aba | linha | coluna | valor atual | valor proposto | motivo | contrato |
|---|---|---|---|---|---|---|---|---|
| WB-AUD-01 | MaxHT_v6 | MaxHT | 120 | P `expression` | `(massa_total_max_ht@L1_L3 + massa_total_max_ht + massa_total_max_ht)/refinery` | `(massa_total_max_ht@L1_L3 + massa_total_max_ht@L4_L5 + massa_total_max_ht@L6_L7)/refinery` | referência ambígua | A019 regra 5; `@grupo` |
| WB-AUD-02 | MaxHT_v6 | MaxHT | 4/6, 5/7, 9/11, 10/12, 23/25, 24/26, 53/55, 54/56, 58/60, 59/61, 77/79, 78/80, 82/84, 83/85, 101/103, 102/104, 106/108, 107/109, 116/118, 117/119 | B `name` | mesmo nome nas duas variantes | nomes distintos para a variante Soma e a variante Média (ex.: sufixo explícito), ou remover a variante que não é consumida; `esp_max_ht_planta` mensal/anual não muda de valor com qualquer escolha consistente (razão de agregados da mesma janela) | identidade duplicada | A019 (`name + frequency + scope`) |
| WB-AUD-03 | production_v3 | production | 55/56, 77/78, 79/80, 81/82, 83/84 | B `name` (e D `unit` da Soma, ver WB-AUD-05) | mesmo nome e unidade | idem WB-AUD-02 | identidade duplicada | A019 |
| WB-AUD-04 | production_v3 | production | 30 | P | `… + (oee@L5 * lth_meta@L5) + lth / lth_meta (oee@L6 * lth_meta@L6) + …` | `… + (oee@L5 * lth_meta@L5) + (oee@L6 * lth_meta@L6) + …` | fragmento solto | parser |
| WB-AUD-04 | production_v3 | production | 48 | P | `… + (pick_up@L5 * lth@L5) + lth (pick_up@L6 * lth@L6) + …` | `… + (pick_up@L5 * lth@L5) + (pick_up@L6 * lth@L6) + …` | fragmento solto | parser |
| WB-AUD-05 | production_v3 | production | 56, 78, 80, 82, 84 / 57, 85, 86, 87, 88 | D `unit` | `tpd` | `t/mês` (mensal) / `t/ano` (anual) — unidade já aceita pela plataforma | SUM de taxa diária é quantidade do período | `required_sum_factor` |
| WB-AUD-06 | production_v3 | production | nova linha (entre 76 e 77) | — | inexistente | `variable / equation`, `consumo_bauxita`, `diário`, `linha_grupo`, `L1_L7`, `tpd`, expressão `consumo_bauxita@L1 + … + consumo_bauxita@L7` (padrão de `consumo_mrn` r73) — alternativa: mudar r83/r84/r88 para `linha` | agregação temporal não pode mudar escopo | `AggregationRule` temporal, escopo igual |
| WB-AUD-07 | yield_v6 | yield | 48 linhas com `L6_7` | J `scope_value` | `L6_7` | `L6_L7` | valor fora do contrato | `ALLOWED_SCOPE_VALUES`, `ScopeResolver` |
| WB-AUD-08 | production_v3 | production | 89 | J | `planta` | `PLANTA` | forma canônica | `CANONICAL_PLANT_SCOPE` |
| WB-AUD-09 | todos | todas | todas as linhas | M `value_type` | `numerico` / `categorico` | `numeric` / `categorical` | vocabulário do contrato | Etapa 2.2 §20; `VALUE_TYPES` |
| WB-AUD-10 | yield_v6 | yield | 2, 10, 17, 82, 97 | P | `0,654`, `0,97`, `0,005`, `0,0017`, `0,0007`, `0,004`, `0,002` | ponto decimal (`0.654` …) | não parseável | parser |
| WB-AUD-10 | production_v3 | production | 52 | P | `1,0902` | `1.0902` | idem | parser |
| WB-AUD-11 | yield_v6 | yield | 249–255 | D `unit` | vazio | unidade de `tanque` (a definir pelo dono do bloco; o seed atual `VAR11239` usa `-`) | campo obrigatório | `NON_EMPTY_STRING_FIELDS` |
| WB-AUD-15 | yield_v6 / energy_v3 | yield / energy | yield r162–r241 (80 linhas); energy r6 | P | descrição sem nome de origem | incluir `de '<origem>'` como nos demais workbooks | rastreabilidade | padrão das demais planilhas |

## 26. Gaps para Stage 3

| gap | workbooks dependentes |
|---|---|
| `EvaluationResult` (`value`, `result_state`, `detail`) e tradução `"F"` → `NO_APPLICABLE_RULE` pelo builder | area_41 (r39, r42) |
| validação runtime de `allowed_values` e produção de `INVALID_INPUT` | area_41 (`hes`) |
| propagação de estado isolada por alcançabilidade (F-001) | area_41 (r48–r51, r54) |
| agregação state-aware (Política B com estado) | area_41 (r40, r41, r43, r44, r52, r53, r55, r56) |
| `BLOCKED_BY_UPSTREAM_ERROR` para erro técnico (`ln` ≤ 0) | area_41 (dependentes de r6–r8, r16–r18) |
| aceitar/validar as colunas `value_type`, `allowed_values`, `declared_result_states` no builder e no seed | todos (hoje só `value_type`, com vocabulário inglês) |

Os quatro blocos já implementados não dependem de nenhuma capacidade de Stage 3 (`declared_result_states` vazio, sem categóricas).

## 27. Riscos para a Etapa 2.4

1. **Seeds × workbooks:** os seeds atuais foram gerados de versões anteriores (yield v4, production v1, energy v2, MaxHT v5). Com as
   versões novas, 2.4 vai encontrar diferenças esperadas (nomes espacializados do MaxHT, `ltp_tc`, `lth_meta`) e as correções acima.
2. **Rastreabilidade de yield e production:** não há builder nem snapshot com SHA-256 no repositório para esses dois blocos
   (energy e MaxHT têm). A reconciliação em 2.4 depende de construir essa trilha.
3. **WB-AUD-12:** o modelo "uma linha do workbook por linha de produção" precisa de uma regra de agrupamento no builder, senão A019
   continuará rejeitando `lth`, `oee`, `producao`, `n_ppt`.
4. **`prefer_sum_variant`:** enquanto WB-AUD-02 existir, MaxHT depende de um desempate específico do bloco.
5. **Vínculo entre blocos:** as dependências cross-block são só documentais (`fonte`); o runtime não liga IDs entre blocos.
6. **Produtores fora do escopo:** `hes` (maintenance), `temperatura_lp`, `alimentação_evap`, entradas `maintenance_plan`/`forecast`
   não puderam ser verificados contra o produtor.

## 28. Cobertura

```text
Workbooks auditados: 5/5
A41:        descritivo_das_variáveis_A41_v7.xlsx
Energy:     descritivo_das_variáveis_energy_v3.xlsx
Max HT:     descritivo_das_variáveis_MaxHT_v6.xlsx
Production: descritivo_das_variáveis_production_v3.xlsx
Yield:      descritivo_das_variáveis_yield_v6.xlsx
```

| indicador | total |
|---|---:|
| linhas semânticas auditadas | 572 / 572 (100%) |
| variáveis | 532 |
| parâmetros | 40 |
| equações executáveis traduzidas e parseadas | 238 |
| referências resolvidas | 1 360 |
| `@Lx` | 1 198 |
| `@grupo` | 11 |
| variáveis categóricas (linhas) | 4 (1 nome: `hes`) |
| `allowed_values` | 4 |
| `declared_result_states` | 2 |
| agregações temporais | 208 |
| divergências cross-workbook | 3 |
| achados | 17 (1 BLOCKER, 6 HIGH, 5 MEDIUM, 4 LOW, 1 INFO) |

Matriz linha a linha: `evidence/coverage_<bloco>.csv` (colunas: linha, identidade, classe da expressão, resultado A019, contratos
verificados, achados).

## 29. Status individual

| workbook | status | motivo |
|---|---|---|
| A41 v7 | **CONFORME COM PENDÊNCIAS NÃO BLOQUEANTES** | Todas as 20 expressões resolvem; `hes@Lx`, grupos, `allowed_values` e `declared_result_states` conformes a D1–D4. Pendências: WB-AUD-09, WB-AUD-13 (decidir antes da Stage 3), WB-AUD-14, WB-AUD-17 |
| energy v3 | **CONFORME COM PENDÊNCIAS NÃO BLOQUEANTES** | 24/24 expressões resolvem. Pendências: WB-AUD-09, 12 (representação de `pick_up`/`lth_meta`), 15, 16, 17 |
| MaxHT v6 | **BLOQUEADO POR INCONSISTÊNCIA DO WORKBOOK** | WB-AUD-01, WB-AUD-02 |
| production v3 | **BLOQUEADO POR INCONSISTÊNCIA DO WORKBOOK** | WB-AUD-03, 04, 05, 06 (+ 08, 09, 10, 12) |
| yield v6 | **BLOQUEADO POR INCONSISTÊNCIA DO WORKBOOK** | WB-AUD-07 (+ 09, 10, 11, 12, 15) |

## 30. STAGE_2.3_GATE

```text
STAGE_2.3_GATE: BLOCKED
```

**Causa exata:** existem inconsistências bloqueantes de workbook (classe A) em três dos cinco arquivos —
MaxHT v6 (WB-AUD-01 referência de grupo ambígua; WB-AUD-02 identidade duplicada), production v3 (WB-AUD-03 identidade duplicada;
WB-AUD-04 expressões não executáveis; WB-AUD-05 SUM com unidade incoerente; WB-AUD-06 agregação com mudança implícita de escopo)
e yield v6 (WB-AUD-07 escopo `L6_7` fora do contrato). Todas têm correção objetiva descrita no §25; nenhuma exige decisão de negócio
nova nem reabre D1–D4.

Os cinco workbooks foram identificados sem ambiguidade e D1–D4 foram aplicadas: A41 v7 — o workbook que servirá à implementação do
A41 — representa o contrato fechado de forma explícita e suficiente, restando uma decisão (WB-AUD-13) que precisa ser tomada antes da
Stage 3, não antes da 2.4. Os gaps restantes pertencem à Stage 3 (§26) ou à 2.4 (WB-AUD-12, §27).

Resposta à pergunta central (§38): **para A41 v7 e energy v3, sim; para MaxHT v6, production v3 e yield v6, ainda não** — as correções
do §25 são necessárias para que a 2.4 compare workbook × código sem reinterpretar semântica.
