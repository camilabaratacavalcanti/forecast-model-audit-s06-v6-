# Protocolo L8 — Relatório de regeneração de evidência (3.4C × 4A)

| campo | valor |
|---|---|
| limitação de origem | L8 (`STAGE_3_FINAL_CLOSURE.md` §17): "mudanças intencionais futuras de comportamento exigirão regenerar e reaprovar a evidência" |
| decisão | DR-4A-2 (`STAGE_4A_DECISION_CONTRACT.md` §5) |
| rótulo | `REAL_DERIVED_TEST_RESULT` |
| recálculo | `python -I audit/stage4a/closure/reconcile_4a.py`, sem importar `app/`. Resultado em `closure_reconciliation_4a.json → l8_comparison` |

## 1. Regra adotada

- A evidência da 3.4C (`audit/stage3_4/integrated/evidence/`) é **histórica**: só foi lida e comparada, **nunca sobrescrita**.
  - Verificado por `git diff --name-only d2847ab -- audit/stage3_4 audit/stage3_2_execution_orchestration audit/stage3_3*`.
  - A única exceção é a adição datada, autorizada pelo prompt, em `audit/stage3_4/PLATFORM_PENDING_ITEMS.md`, verificada como append-only.
- A evidência nova da 4A fica **só** em `audit/stage4a/**`.
- O harness da 3.4C continua rodando sem alteração e continua PASS: universo de 4 blocos, 421 alvos e 427 nós.

## 2. O que mudou: só a inclusão do area_41

| grandeza | 3.4C | 4A | diferença |
|---|---|---|---|
| alvos | 421 | 446 | **+25**, todos do area_41 (VAR16004..VAR16036 calculadas, mais `lth` VAR16007) |
| nós do plano | 427 | 458 | **+31**, todos do area_41: 20 EQUATION, 10 AGGREGATION, 1 TRANSFER. Os 2 nós a montante (EQ12012, TRANSFER:VAR11031) já existiam |
| transferências | 12 | 13 | **+`TRANSFER:VAR16007`** (yield.VAR11031 → area_41.VAR16007) |
| eventos por data | 847 | 896 | **+49** (20 instâncias de equação + 22 de agregação + 7 de transferência) |
| entradas livres | 51 | 62 | **+11** do area_41 (índices 51..61, DR-4A-5) |
| identidades mensais de janeiro / anuais | 313 / 185 | 324 / 196 | **+11 / +11** (instâncias mensais e anuais do area_41) |

## 3. O que não mudou: os 421 alvos

| verificação | resultado |
|---|---|
| resultado final de 2026-02-01 dos 421 alvos (`targets.csv` 3.4C × 4A) | **idêntico** nos 421 |
| alvos da 3.4C removidos | nenhum |
| ordem relativa dos 427 nós da 3.4C no plano de 5 blocos | **idêntica** |
| as 12 transferências (fonte, consumidor, instâncias, eventos verificados, valor de 2026-02-01) | **idênticas** |
| store dos 4 blocos nas 32 datas (value, state, detail, identidade temporal) | **idêntico**: hash do subconjunto `619b4abd…e9730c` = `store_sha256` da 3.4C. São 33 740 chaves comparadas uma a uma contra a execução dos 4 blocos isolados, com 0 diferenças |
| hash do grafo do fixture | idêntico (`e372425d…`) |

## 4. Reaprovação

A evidência 4A substitui a 3.4C **como referência viva** apenas para o universo de 5 blocos. A 3.4C continua como referência histórica do universo de 4 blocos e é reconferida em toda execução do harness 4A.

Uma mudança intencional futura no area_41 vai falhar `EVIDENCE_REGRESSION` no `run_integrated_4a.py --no-write` e exigirá:
- nova regeneração da evidência;
- novo relatório L8.

```text
L8 (3.4C x 4A): PASS — mudou só a inclusão do area_41; os 421 alvos não mudaram.
```
