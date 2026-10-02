# Procedimento de re-baseline (Stage 4C)

Vale para qualquer stage que mude **comportamento** do motor ou dos dados. Exemplos: workbook novo, seed regenerado, unidade nova, correção de fórmula, mudança no `app/`.

Regra de ouro: **evidência histórica nunca é reescrita**. A referência viva muda por uma entrada nova no registro, proposta e aprovada.

## 1. O que é o quê

| classe | onde vive | o que acontece quando o comportamento muda |
|---|---|---|
| H | fechamentos (intervalos fixos, clones nos commits de fechamento) | nada; continua verde para sempre |
| E | evidência versionada de cada stage (`audit/stage*/…`) | nada; sha256 no B0 e `git diff <commit>` vazio |
| R | regressões vivas (3.4C, 4A, 4B) | falham até o re-baseline; depois comparam com a nova referência |
| S | invariantes de ID (sem renumeração, aposentados no `retired`, sem reuso, faixas, append-only) | continuam valendo; violação é defeito real |
| W | árvore intacta pela execução | continuam valendo |
| C | contratos de conteúdo atual (contagens, IDs e literais do workbook vigente) | **a stage que muda o conteúdo os atualiza** (pré-lista da 5A em `STAGE_4C_FINAL_CLOSURE.md`) |

## 2. Passo a passo

1. Fazer a mudança de produção (workbook, `tools.workbook_seed`, `app/`…) e **commitar**.
2. Rodar a suíte. Devem falhar só testes **C** e **R**. Falha H, E, S ou W indica defeito real, não re-baseline: corrigir antes de seguir.
3. Atualizar os testes **C** afetados, com justificativa no relatório da stage, e commitar. Nenhum teste é apagado, pulado ou afrouxado.
4. Com a árvore limpa:
   ```
   python audit/baselines/rebaseline.py --id B<n> --stage <stage> --reason "<motivo objetivo>"
   ```
   O comando:
   - recusa árvore suja, motivo vazio, id repetido ou fora do formato `B<n>[-sufixo]`, proposta pendente e registro inválido;
   - regenera os conjuntos R em `audit/baselines/B<n>/<conjunto>/`, via `--baseline-dir` dos harnesses;
   - verifica com `--no-write` que a execução viva reproduz o que foi gravado, e roda os recálculos independentes da 4A e da 4B;
   - grava `audit/baselines/B<n>/DIFF_REPORT.md`;
   - acrescenta a entrada **PROPOSED**. O `current` não muda.

   Duração: cerca de 25 min (T1/T3 da 4B dominam).
5. **Ler o `DIFF_REPORT.md`**:
   - §1: IDs novos/removidos por bloco, aposentados no ledger, vínculos e workbooks;
   - §2: arquivo a arquivo e expectativas;
   - §3: conjuntos herdados.

   Toda diferença precisa ser explicada pela mudança do passo 1.
6. Commitar a proposta: `audit/baselines/B<n>/` + registro.
7. Aprovar (decisão humana):
   ```
   python audit/baselines/rebaseline.py --approve B<n>
   python audit/baselines/rebaseline.py --check
   ```
   A aprovação grava `APPROVED`, a data e o **selo** (sha256 da entrada), e move o `current`. Editar depois uma entrada APPROVED invalida o selo.
8. Commitar a aprovação e rodar a suíte. Tudo verde.

## 3. O que nunca fazer

- Editar `BASELINE_REGISTRY.json` à mão (o `--check` e o teste do registro detectam: selo, sha256, cadeia, current).
- Regravar evidência de stages anteriores (`audit/stage*/…/evidence`): proteção E.
- Mudar a lógica de um harness para "fazer passar". O único parâmetro aceito é `--baseline-dir`.
- Apontar `current` para entrada PROPOSED.
- Usar `--no-verify`, `-c core.hooksPath=…`, `skip`/`xfail` ou relaxar asserção.

## 4. Referência rápida

| comando | efeito |
|---|---|
| `rebaseline.py --check` | verifica tudo, não escreve; exit 0/1 |
| `rebaseline.py --preflight-only --id … --stage … --reason …` | só as recusas (nada roda nem é escrito) |
| `rebaseline.py --id … --stage … --reason …` | propõe (PROPOSED) |
| `rebaseline.py --approve B<n>` | aprova (APPROVED + selo + current) |
| `python audit/stage4c/b0_reproduction.py` | prova que os harnesses R reproduzem B0 |

Ensaio completo do procedimento: `audit/stage4c/rehearsal/` (R1 com energy v9 / MaxHT v13, R2a, R2b).
