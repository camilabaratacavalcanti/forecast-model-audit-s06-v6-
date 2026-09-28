# Refinamento R1 de D1/D2 — `declared_result_states` é local

Refinamento do contrato fechado na Etapa 2.2 (D1–D4, commit `5c8dcfc`,
`audit/stage2_2_state_contract/` na branch histórica
`claude/funny-noether-nbcr7b`). Não é uma decisão nova (não há D5): fixa
uma leitura que D1 e D2 deixavam aberta e que a Etapa 2.3 registrou como
WB-AUD-13.

## Lacuna que este refinamento fecha

- D1 exige que "todo literal-estado usado na fórmula pertença a
  `declared_result_states`" — regra sobre **literais da própria fórmula**.
- D2 diz que cada variável declara "quais rótulos globais ela pode
  produzir" — lido de forma transitiva, obrigaria todo descendente de um
  produtor de estado a repetir a declaração.
- D3 fixa que o estado propaga aos descendentes alcançáveis.

As três juntas não diziam se um estado **herdado** precisa ser declarado
no herdeiro.

## Regra

1. **`declared_result_states` é local.** Lista apenas os estados que a
   própria variável produz diretamente, como resultado de negócio da sua
   própria regra (hoje: o literal de estado escrito na sua fórmula, D1).
2. **Estado herdado não é redeclarado.** Uma variável que recebe um estado
   de uma dependência não repete esse estado em `declared_result_states`.
   A lista não é o fecho transitivo dos estados dos ancestrais:
   `A → B → C → D` não implica copiar `A.declared_result_states` em B, C, D.
3. **Estado declarado × estado efetivo.**
   - *Estado declarado*: o que a variável pode produzir por conta própria
     (`declared_result_states`, metadado do workbook).
   - *Estado efetivo*: o que a variável apresenta numa execução — produzido
     por ela, herdado de uma dependência, ou definido por uma agregação
     state-aware. É responsabilidade do runtime, nunca do workbook.
4. **Propagação pertence à Stage 3.** Quais operações propagam estado
   (`B = A`, `C = A + 10`, `D = média(A, B, C)`, comparações, ramos de `IF`)
   será definido e implementado nas Etapas 3.1–3.3. A agregação
   state-aware (Política B com estado) pertence à Etapa 3.4.
5. **`NO_APPLICABLE_RULE` é estado de negócio.** Quando produzido pela regra
   de negócio, nunca é convertido em exceção, erro técnico, `None` ou `NaN`
   por ser textual. Continua valendo D3: erro técnico nunca vira estado.
6. **Validação futura no builder (consequência para a Stage 3):** a checagem
   de D1 continua sendo sobre os literais da fórmula da própria variável; o
   builder não deve exigir que herdeiros declarem estados dos ancestrais.

O que não muda: taxonomia global de D2, tradução no builder (D1), D3, D4.

## Aplicação normativa ao A41 v7

Produtores locais (declaram `NO_APPLICABLE_RULE → F`, ramo final `else "F"`):

| linha | variável | escopo |
|---|---|---|
| r39 | `retirada_condensado_grupo` diário | linha_grupo / L4_L5 |
| r42 | `retirada_condensado_grupo` diário | linha_grupo / L6_L7 |

Herdeiros (estado efetivo possível; **não** declaram, e estão corretos assim):

| linha | variável | via |
|---|---|---|
| r48–r51 | `retirada_condensado_linha` diário L4, L5, L6, L7 | equação (`retirada_condensado_grupo@L4_L5` / `@L6_L7`) |
| r54 | `retirada_condensado_total` diário L1_L7 | equação (soma dos três grupos) |
| r40, r41, r43, r44 | `retirada_condensado_grupo` mensal/anual L4_L5, L6_L7 | agregação temporal (Política B) |
| r52, r53 | `retirada_condensado_linha` mensal/anual | agregação temporal (instâncias L4–L7) |
| r55, r56 | `retirada_condensado_total` mensal/anual | agregação temporal |

Sobre `hes`: é entrada categórica (`allowed_values` com 5 valores) e não
produz `NO_APPLICABLE_RULE`. Seu único estado possível é `INVALID_INPUT`,
detectado ao ser consumida fora do domínio (D2; runtime na Stage 3). Não
declara `declared_result_states`. `retirada_condensado_grupo` consome
`hes@L4..@L7`, mas o `NO_APPLICABLE_RULE` que declara nasce da sua própria
regra (nenhum ramo cobre a combinação), não de `hes`.

Os quatro blocos já implementados (yield, production, energy, max_ht) não
produzem nem herdam estados: `declared_result_states` vazio, regra no-op.
