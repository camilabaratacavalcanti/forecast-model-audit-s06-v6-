# Stage 3 gate

**READY_WITH_CONDITIONS**

## Critérios do gate

| critério | situação |
|---|---|
| significado de `value_type` definido | ✔ domínio do valor válido: `numeric` \| `categorical` |
| significado de `"F"` definido | ✔ estado de resultado (`CONDITIONAL_FAILURE`), hoje codificado como sentinela |
| F-001 classificado | ✔ controle de fluxo/propagação; não é tipagem |
| necessidade de `mixed` decidida | ✔ não necessário |
| boolean / string / categorical definidos | ✔ boolean só intermediário; sem `string` livre; `categorical` = domínio de categorias |
| agregação definida | ✔ um estado não-VALID invalida o agregado (como hoje), agora como estado |
| propagação definida | ✔ o estado propaga só aos descendentes, como dado |
| impacto transversal mapeado | ✔ `REPORT.md` §19 |
| ambiguidade crítica | nenhuma arquitetural; restam decisões de negócio e política (abaixo) |

## Condições (decisões do dono, antes de implementar)

1. **Taxonomia de estados.** Confirmar que `"F"` = `CONDITIONAL_FAILURE`
   ("nenhuma regra aplicável") e decidir se marcadores futuros ("ERRO!!!")
   serão estados declarados por workbook (T-13).
2. **Política de propagação** de estados (isolar aos descendentes,
   recomendado) e de erros técnicos (abortar a rodada ou isolar o nó) (T-02).
3. **Política de agregação** com estados: manter "invalida o agregado com os
   períodos" (recomendado) ou admitir um parcial sinalizado.
4. **Domínio de categorias** (`allowed_values`): adotar para distinguir entrada
   inválida de estado de regra (T-05).

Sem essas decisões, a Etapa 3 implementaria uma escolha de política em nome do
negócio.
