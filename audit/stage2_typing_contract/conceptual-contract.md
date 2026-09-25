# Contrato conceitual proposto: valor, estado, erro

> PROPOSTA ARQUITETURAL. Não é instrução de implementação nesta etapa.
> Cada item deriva de um achado (`findings.md`).

## Estrutura

```text
VariableDefinition
 ├── identity        name + frequency + scope (inalterado)
 ├── variable_type   papel: entrada | entrada_externa | calculado | saída (inalterado)
 ├── value_type      domínio do valor VÁLIDO: numeric | categorical
 └── allowed_values  (opcional, só categorical) domínio de categorias            ← T-05

EvaluationResult (por instância × período)
 ├── state   VALID | CONDITIONAL_FAILURE | <estados de negócio declarados>       ← T-01, T-03, T-13
 ├── value   presente somente quando state = VALID; tipo = value_type
 └── detail  opcional (rótulo de origem, p.ex. "F", "ERRO!!!"; períodos afetados)

Erro técnico (parse, tipo, divisão por zero, domínio de ln, entrada ausente)
 └── continua sendo EXCEÇÃO; nunca é gravado como valor nem como estado       ← T-04
```

## `value_type`: manter, redefinido

| pergunta | resposta |
|---|---|
| o que significa | Natureza do valor **válido** da variável. Não descreve estados nem erros. |
| quem declara | o workbook/seed (campo opcional; ausente = `numeric`) |
| quem valida | carga da definição (enum); builder/validator, de forma estática (ramos de IF, agregação só sobre `numeric`, aritmética sobre `categorical`) → T-06 |
| quem consome | storage (gate), validação estática, serialização futura de resultados |
| valores permitidos | `numeric`, `categorical` (sem `string`: não há texto livre no domínio atual; sem `boolean`: T-08; sem `mixed`: §14 do relatório) |
| obrigatório | sim, com padrão `numeric` |
| persistido | sim, na definição |
| altera runtime | só o gate de armazenamento e a validação; o evaluator não precisa conhecê-lo antes da execução |

## `"F"`: estado de resultado

- **Onde deve existir:** como `state = CONDITIONAL_FAILURE` do resultado. No
  workbook, `"F"` pode continuar sendo a notação, que o builder mapeia para o
  estado.
- **Onde não deve existir:** no canal de valor, nem como categoria.
- **Propagação:** um consumidor que depende de um resultado não-VALID produz o
  mesmo estado, sem exceção. Isso vale só para os **descendentes**, e os nós
  independentes são calculados normalmente (resolve T-02/F-001 e T-03). A
  detecção explícita (`x == "F"`) passa a ser um predicado de estado.
- **Agregação:** manter a semântica atual. Um período com estado não-VALID
  invalida o agregado, e o resultado agregado leva `state = CONDITIONAL_FAILURE`
  com os períodos afetados em `detail`. Não há parcial silencioso.
- **Persistência:** `state` + `value = ausente` + `detail`.
- **Apresentação:** o rótulo de origem ("F") ou a descrição do estado.

## Futuro `SE(condição;"ERRO!!!";valor)`

| pergunta | resposta derivada da arquitetura |
|---|---|
| representa `mixed`? | não |
| `numeric + result_state`? | **sim**: valor numérico quando válido; `"ERRO!!!"` é um estado de negócio declarado |
| erro de execução? | não: a fórmula executa corretamente |
| erro de negócio? | sim: estado de negócio, distinto de `CONDITIONAL_FAILURE` se o dono assim declarar |
| permitido? | sim, **se declarado** como marcador de estado; um literal textual não declarado em variável `numeric` deve ser rejeitado estaticamente |
| resultado estruturado? | sim (`EvaluationResult`) |
| interromper a cadeia? | só a cadeia dependente (descendentes), não a rodada |
| armazenar? | sim, como estado |
| exibir? | sim, com o rótulo declarado |

## Erros técnicos

Continuam como exceções, que não são estado de negócio. A política de
execução (abortar a rodada ou isolar o nó) é uma decisão explícita da Etapa 3;
recomenda-se isolar e reportar.
