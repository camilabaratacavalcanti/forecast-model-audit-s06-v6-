# Stage 3.4D — Mutation & Audit Closure

Auditoria de *mutation resistance* dos mecanismos construídos nas Stages 3.3A–3.4C, atendendo ao prompt da 3.4D e ao contrato aprovado da 3.4A (§19).

| | comando |
|---|---|
| reproduzir as mutações | `python audit/stage3_4/mutation/run_mutation.py` (58 mutações de evidência + 17 mutantes de código; ≈ 8 min) |
| só as mutações de evidência | `python audit/stage3_4/mutation/run_mutation.py --skip-code-mutants --no-write` (≈ 1,5 min) |
| auditoria black-box | `python -I audit/stage3_4/mutation/blackbox_audit.py` |
| sonda dos auditores do baseline | `python audit/stage3_4/mutation/baseline_gap_probe.py` |
| testes | `tests/test_stage3_4d_mutation.py` (14 testes) |

Todo resultado de execução citado aqui é `REAL_DERIVED_TEST_RESULT`.

---

## 1. Baseline (22.1)

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| baseline | `043fe9c36d9d02664db8be7dd29c0fd7014c73f8` — "test(stage3.4c): add integrated four-block regression" |
| árvore inicial | limpa; HEAD = `origin/feature/area-41-block` |
| suíte inicial | **1845 passed, 0 failed, 0 skipped** |
| Python | 3.11.15 |

O baseline reproduziu exatamente o estado esperado. Nenhuma divergência foi encontrada.

## 2. Scope (22.2)

**Contratos auditados:** M1–M10 do prompt, mais os mutantes de código e a auditoria black-box do contrato 3.4A §19.

| família | contrato | mecanismo real auditado |
|---|---|---|
| M1 | target coverage | `observe` + `check_targets` + `check_target_identities` (3.4C) |
| M2 | planner coverage | `check_nodes` (3.4C) e o orquestrador real executando um plano mutilado |
| M3 | interblock integrity | `check_transfers` (consumidor = produtor em value/state/detail; instâncias, blocos e duplicidade do vínculo) |
| M4 | state propagation / isolation | auditores dos cenários SC1 (EQ12012) e SC2 (EQ18003); `check_clean_context`; contrato `Result` do app |
| M5 | state-aware aggregation | auditor do SC3 (regras reais) e composição real do engine (SC4) |
| M6 | temporal identity | `check_temporal` sobre o store real de 32 datas |
| M7 | reexecution | `check_reexecution` sobre FIRST_RUN × REEXECUTION reais; guarda de conflito do resolver |
| M8 | determinism | `check_determinism` sobre fingerprints reais (processo atual, subprocessos com PYTHONHASHSEED 0/4242, ORDER_B) |
| M9 | differential regression | `run_differential.evaluate` + `compare.compare_case`/`coverage` (3.4B) sobre a saída real 7877551 × HEAD |
| M10 | fixture / provenance | `provenance.check_provenance` sobre o registro persistente (bytes do baseline), o registro oficial, o fixture e a evidência |

**Famílias de mutação:**
- **58 mutações de evidência**, IDs `MUT-*`. Cada uma é aplicada depois da produção da evidência real e antes do auditor real.
- **17 mutantes de código**, IDs `CM-*`, pedidos pela 3.4A §19. Cada um é uma substituição única em `app/`, feita somente numa cópia temporária de HEAD.

**Controles positivos:**
- 13 sobre a evidência;
- 1 sobre a árvore de código não mutada, que passa nos três detectores.

## 3. Mutation matrix (22.3)

Evidência completa:
- `audit/stage3_4/mutation/mutation_matrix.csv`: definição, com `mutation_id`, contrato, descrição, ponto, artefato, campo, detecção esperada, mecanismo, caminho real e `production_code_touched`;
- `audit/stage3_4/mutation/mutation_results.csv`: obtido, com antes, depois, detecção obtida, `detected` e `result`.

A coluna "obtido" lista todos os códigos emitidos. A mutação só conta como detectada quando o código **esperado** está entre eles, não basta outro sinal qualquer.

| ID | contrato | mutação | ponto / artefato.campo | detector | esperado | obtido | resultado |
|---|---|---|---|---|---|---|---|
| MUT-T01 | M1 | remove todos os eventos do alvo VAR13001 em 2026-01-15 | trace 2026-01-15.events[VAR13001] | checks.check_targets (observe) | `TARGET_NOT_EXECUTED` | PLANNER_ONLY_NODE, TARGET_NOT_EXECUTED | PASS |
| MUT-T02 | M1 | duplica o evento do alvo VAR12031 linha/L3 em 2026-01-15 | trace 2026-01-15.events[VAR12031 L3] | checks.check_target_identities | `TARGET_DUPLICATED` | NODE_EVENT_COUNT, TARGET_DUPLICATED | PASS |
| MUT-T03 | M1 | alvo mensal VAR13002 linha/L1 em 2026-02-01 registrado no período 2026-01 | trace 2026-02-01.period_id | checks.check_target_identities | `TARGET_WRONG_PERIOD` | ENGINE_FAILURE, TARGET_WRONG_PERIOD | PASS |
| MUT-N01 | M2 | remove da evidência todos os eventos do nó EQUATION:EQ12012 em 2026-01-15 | trace 2026-01-15.events[EQUATION:EQ12012] | checks.check_nodes | `PLANNER_ONLY_NODE` | PLANNER_ONLY_NODE, TARGET_NOT_EXECUTED | PASS |
| MUT-N02 | M2 | acrescenta evento de nó inexistente no plano (EQUATION:EQ_NOT_PLANNED) | trace 2026-01-15.node_id | checks.check_nodes | `ENGINE_ONLY_NODE` | ENGINE_ONLY_NODE, NODE_ORDER_DIFFERS_FROM_PLAN, TARGET_DUPLICATED | PASS |
| MUT-N03 | M2 | repete ao fim do dia todos os eventos do nó EQUATION:EQ12012 | trace 2026-01-15.events[EQUATION:EQ12012] | checks.check_nodes | `NODE_EXECUTED_TWICE` | NODE_EVENT_COUNT, NODE_EXECUTED_TWICE, NODE_ORDER_DIFFERS_FROM_PLAN, TARGET_DUPLICATED | PASS |
| MUT-N04 | M2 | remove um único evento (instância) do nó de agregação que produz VAR13001 | trace 2026-01-15.events[VAR13001 linha/L4] | checks.check_nodes | `NODE_EVENT_COUNT` | NODE_EVENT_COUNT, TARGET_NOT_EXECUTED | PASS |
| MUT-N05 | M2 | o orquestrador real executa um plano sem o último nó (ExecutionPlan em memória) | plan 2026-01-01.steps[-1] | checks.check_nodes | `PLANNER_ONLY_NODE` | INTERBLOCK_FAILURE, PLANNER_ONLY_NODE, TARGET_NOT_EXECUTED | PASS |
| MUT-TX01 | M3 | remove o evento de transferência VAR11031 linha/L2 em 2026-01-15 | trace 2026-01-15.events[TRANSFER:VAR11031 L2] | checks.check_transfers | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE, NODE_EVENT_COUNT, TARGET_NOT_EXECUTED | PASS |
| MUT-TX02 | M3 | valor recebido pela consumidora VAR11031 linha/L2 em 2026-01-15 alterado | context RUN_A.value | checks.check_transfers (consumer == producer) | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE | PASS |
| MUT-TX03 | M3 | state recebido por VAR11031 linha/L3 em 2026-01-10 trocado (value e detail mantidos) | context SC1.state | checks.check_transfers + check_state_diff (SC1 auditor) | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE, STATE_DIFFERENCE | PASS |
| MUT-TX04 | M3 | detail recebido por VAR11031 linha/L3 em 2026-01-10 trocado (value e state mantidos) | context SC1.detail | checks.check_transfers + check_state_diff (SC1 auditor) | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE, STATE_DIFFERENCE | PASS |
| MUT-TX05 | M3 | duplica o evento de transferência VAR18006 em 2026-01-15 | trace 2026-01-15.events[TRANSFER:VAR18006] | checks.check_transfers (duplicidade) | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE, NODE_EVENT_COUNT, TARGET_DUPLICATED | PASS |
| MUT-TX06 | M3 | transferência VAR11031 linha/L2 atribuída ao alvo VAR13062 (bloco consumidor yield mantido) | trace 2026-01-15.node_id | checks.check_transfers (instâncias e bloco do vínculo) | `INTERBLOCK_FAILURE` | INTERBLOCK_FAILURE, NODE_EVENT_COUNT, NODE_EXECUTED_TWICE, NODE_ORDER_DIFFERS_FROM_PLAN, TARGET_DUPLICATED, TARGET_NOT_EXECUTED | PASS |
| MUT-S01 | M4 | descendente de EQ12012 (VAR12031 linha/L3, 2026-01-20) perde o estado propagado | store SC1.state/detail | check_expectations (alcance) do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S02 | M4 | estado INVALID_INPUT/fa aparece num não-descendente (VAR13001 linha/L3, 2026-01-10) | store SC1.state/detail | check_state_diff (vazamento) do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S03 | M4 | resultado com estado do SC1 copiado para o contexto limpo RUN_A | context RUN_A.VAR12031 linha/L3 2026-01-10 | checks.check_clean_context | `STATE_PROPAGATION_FAILURE` | STATE_PROPAGATION_FAILURE | PASS |
| MUT-S04 | M4 | grava Result(value, state=None, detail='fa') pelo contrato real de resultado | Result.detail | app.domain.results.Result | `DETAIL_WITHOUT_STATE` | DETAIL_WITHOUT_STATE | PASS |
| MUT-S05 | M4 | detail sem state na evidência do contexto limpo (VAR12031 linha/L1, 2026-01-10) | store RUN_A.detail | checks.check_result_contract | `DETAIL_WITHOUT_STATE` | DETAIL_WITHOUT_STATE, STATE_PROPAGATION_FAILURE | PASS |
| MUT-S06 | M4 | estado vaza para outra linha não injetada (VAR12031 linha/L1, 2026-01-10) | store SC1.state/detail | check_expectations (plain) do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S07 | M4 | estado de janeiro vaza para 2026-02-01 (VAR12031 linha/L3) | store SC1.state/detail | check_expectations (plain) do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S08 | M4 | detail perdido num descendente transferido (VAR11031 linha/L3, 2026-01-10) | store SC1.detail | check_state_diff do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S09 | M4 | EQ12012: estado atravessa o ramo INATIVO (VAR12031 linha/L4, 2026-01-05) | store SC1.state/detail | check_expectations (plain) do auditor SC1 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S10 | M4 | EQ18003: estado atravessa o ramo INATIVO (VAR18017 linha/L2, 2026-01-03) | store SC2.state/detail | check_expectations (plain) do auditor SC2 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-S11 | M4 | EQ18003: ramo ATIVO não propaga (VAR18017 linha/L1, 2026-01-02 volta ao valor limpo) | store SC2.state/detail | check_expectations (alcance) do auditor SC2 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-A01 | M5 | agregação mensal real de VAR11001 linha/L2 recebe INVALID_INPUT e VALIDATION_FAILED | context SC4.state | compose_states (engine real) | `MULTI_STATE_COMBINATION_UNDEFINED` | MULTI_STATE_COMBINATION_UNDEFINED | PASS |
| MUT-A02 | M5 | agregação mensal real de VAR11001 linha/L2 recebe mesmo state com details diferentes | context SC4.detail | compose_states (engine real) | `MULTI_DETAIL_COMPOSITION_UNDEFINED` | MULTI_DETAIL_COMPOSITION_UNDEFINED | PASS |
| MUT-A03 | M5 | AVERAGE real perde o estado (janela 2026-01-04 volta ao valor limpo) | store SC3.state | check_expectations do auditor SC3 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-A04 | M5 | SUM real perde o detail (janela 2026-01-05) | store SC3.detail | check_state_diff / check_expectations do auditor SC3 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-A05 | M5 | WEIGHTED_AVERAGE real devolve valor junto com o estado (deveria ser state-only) | store SC3.value | check_state_diff (state-only) do auditor SC3 | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-A06 | M5 | MOVING_AVERAGE real com detail sem state (janela 2026-01-04) | store SC3.state | checks.check_result_contract (auditor SC3) | `DETAIL_WITHOUT_STATE` | DETAIL_WITHOUT_STATE, RESULT_CONTRACT_INVALID, STATE_DIFFERENCE | PASS |
| MUT-TM01 | M6 | janelas 2026-01-14 e 2026-01-15 de VAR13002 linha/L1 colapsadas numa só identidade | store RUN_A.window_end | checks.check_temporal | `TEMPORAL_FAILURE` | TEMPORAL_FAILURE | PASS |
| MUT-TM02 | M6 | reexecução de 2026-01-15 cria nova identidade para a mesma janela | store REEXECUTION 2026-01-15.window_end | checks.check_reexecution + checks.check_temporal | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE, TEMPORAL_FAILURE | PASS |
| MUT-TM03 | M6 | resultado de 2026-02-01 contamina a janela 2026-01-10 de VAR13002 linha/L1 | store RUN_A.value | checks.check_temporal (snapshot de janeiro) | `TEMPORAL_FAILURE` | TEMPORAL_FAILURE | PASS |
| MUT-TM04 | M6 | identidade mensal derivada gravada sem janela (window_end None) | store RUN_A.window_end | checks.check_temporal | `TEMPORAL_FAILURE` | TEMPORAL_FAILURE | PASS |
| MUT-TM05 | M6 | janela 2026-02-01 atribuída ao período 2026-01 (identidade temporal incorreta) | store RUN_A.period_id | checks.check_temporal | `TEMPORAL_FAILURE` | TEMPORAL_FAILURE | PASS |
| MUT-R01 | M7 | reexecução REAL de 2026-01-15 com entrada diferente sem transferência a jusante (VAR13003 L1) | context REEXECUTION (deepcopy).input value | checks.check_reexecution | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE | PASS |
| MUT-R06 | M7 | reexecução REAL de 2026-01-15 com entrada diferente a montante de uma transferência (VAR11001 L1 -> yield VAR11226 -> production VAR12062) | context REEXECUTION (deepcopy).input value | InterblockResolver.transfer_result (engine real) | `INTERBLOCK_CONSUMER_VALUE_CONFLICT` | INTERBLOCK_CONSUMER_VALUE_CONFLICT | PASS |
| MUT-R02 | M7 | transferência duplicada na reexecução de 2026-02-01 | events REEXECUTION 2026-02-01.events[TRANSFER:VAR18009] | checks.check_reexecution (duplicidade) | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE | PASS |
| MUT-R03 | M7 | estado residual após a reexecução (VAR12031 linha/L2, 2026-02-01) | store REEXECUTION 2026-02-01.state/detail | checks.check_reexecution | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE | PASS |
| MUT-R04 | M7 | reexecução regrava a transferência (status WRITTEN em vez de UNCHANGED) | events REEXECUTION 2026-01-15.status | checks.check_reexecution | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE | PASS |
| MUT-R05 | M7 | evento da reexecução com valor diferente do FIRST_RUN (store intacto) | events REEXECUTION 2026-01-15.value | checks.check_reexecution | `REEXECUTION_FAILURE` | REEXECUTION_FAILURE | PASS |
| MUT-DT01 | M8 | execução com PYTHONHASHSEED=4242 diverge em um resultado | fingerprint HASH_SEED_B.results_sha256 | checks.check_determinism | `DETERMINISM_FAILURE` | DETERMINISM_FAILURE | PASS |
| MUT-DT02 | M8 | ordem dos blocos ORDER_B altera a ordem do plano (dois nós trocados) | fingerprint RUN_B.plan_order | checks.check_determinism | `DETERMINISM_FAILURE` | DETERMINISM_FAILURE | PASS |
| MUT-DT03 | M8 | ordem dos links ORDER_B com um vínculo divergente (grafo diferente) | fixture ORDER_B.links | fixture.graph_hash + checks.check_determinism | `DETERMINISM_FAILURE` | DETERMINISM_FAILURE | PASS |
| MUT-DT04 | M8 | ordem de inserção equivalente (ORDER_B) com um resultado divergente | fingerprint RUN_B (processo atual).results_sha256 | checks.check_determinism | `DETERMINISM_FAILURE` | DETERMINISM_FAILURE | PASS |
| MUT-D01 | M9 | valor numérico de um caso de equação do candidate alterado | differential candidate.outcome.value | run_differential.evaluate / compare.compare_case | `VALUE_DIFFERENCE` | VALUE_DIFFERENCE | PASS |
| MUT-D02 | M9 | somente o state de um caso do candidate alterado | differential candidate.outcome.state | run_differential.evaluate | `STATE_DIFFERENCE` | STATE_DIFFERENCE | PASS |
| MUT-D03 | M9 | somente o detail de um caso do candidate alterado | differential candidate.outcome.detail | run_differential.evaluate | `DETAIL_DIFFERENCE` | DETAIL_DIFFERENCE | PASS |
| MUT-D04 | M9 | um resultado removido do candidate | differential candidate.cases[i] | run_differential.evaluate / compare.coverage | `MISSING_CANDIDATE_RESULT` | COVERAGE_MISSING, MISSING_CANDIDATE_RESULT | PASS |
| MUT-D05 | M9 | um resultado duplicado no candidate | differential candidate.cases[i] | run_differential.evaluate / compare.coverage | `COVERAGE_DUPLICATES` | COVERAGE_DUPLICATES | PASS |
| MUT-D06 | M9 | identidade (period_id) de um caso de agregação do candidate alterada | differential candidate.period_id | run_differential.evaluate / compare.compare_case | `STRUCTURAL_DIFFERENCE` | STRUCTURAL_DIFFERENCE | PASS |
| MUT-P01 | M10 | evidência do fixture rotulada como resultado operacional | evidence 3.4C.label | provenance.check_provenance | `PROVENANCE_FAILURE` | PROVENANCE_FAILURE | PASS |
| MUT-P02 | M10 | fixture com a representação dos 16 pendentes alterada (15 mascarados, 1 mantido) | fixture ORDER_A.pending | provenance.check_provenance (grafo + pendências do fixture) | `FIXTURE_FAILURE` | FIXTURE_FAILURE | PASS |
| MUT-P03 | M10 | registro oficial em memória com as 16 pendências mascaradas | official registry (memória).pending | provenance.check_provenance | `PENDING_LINKS_ALTERED` | PENDING_LINKS_ALTERED | PASS |
| MUT-P04 | M10 | registro persistente com pending = [] (cópia temporária de data/seed) | data/seed (cópia).pending | provenance.check_provenance (bytes + pendências persistidas) | `PENDING_LINKS_ALTERED` | PENDING_LINKS_ALTERED, PROVENANCE_FAILURE | PASS |
| MUT-P05 | M10 | pendência persistida mascarada como resolvida (resolution_status) na cópia temporária | data/seed (cópia).pending[0].resolution_status | provenance.check_provenance | `PENDING_LINKS_ALTERED` | PENDING_LINKS_ALTERED, PROVENANCE_FAILURE | PASS |
| MUT-P06 | M10 | evidência do fixture reclassificada como OPERATIONAL | evidence 3.4C.classification | provenance.check_provenance | `PROVENANCE_FAILURE` | PROVENANCE_FAILURE | PASS |

**Localidade (antes → depois, somente o campo mutado):**

| ID | antes | depois |
|---|---|---|
| MUT-T01 | `7 eventos VAR13001` | `0 eventos VAR13001` |
| MUT-T02 | `EQUATION:EQ12012 VAR12031 linha/L3 2026-01-15 x1` | `EQUATION:EQ12012 VAR12031 linha/L3 2026-01-15 x2` |
| MUT-T03 | `2026-02` | `2026-01` |
| MUT-N01 | `7 eventos EQ12012` | `0` |
| MUT-N02 | `sem EQ_NOT_PLANNED` | `EQUATION:EQ_NOT_PLANNED VAR11003 linha_grupo/L1_L3 2026-01-15` |
| MUT-N03 | `EQ12012 x1` | `EQ12012 x2` |
| MUT-N04 | `7 eventos` | `6 eventos` |
| MUT-N05 | `427 nós` | `426 nós (sem TRANSFER:VAR18011)` |
| MUT-TX01 | `7 instâncias` | `6 instâncias (sem linha/L2)` |
| MUT-TX02 | `["float", "1.3468656249999997", null, null]` | `["float", "999.0", null, null]` |
| MUT-TX03 | `["NoneType", "None", "INVALID_INPUT", "fa"]` | `["NoneType", "None", "VALIDATION_FAILED", "fa"]` |
| MUT-TX04 | `["NoneType", "None", "INVALID_INPUT", "fa"]` | `["NoneType", "None", "INVALID_INPUT", "fb"]` |
| MUT-TX05 | `1 evento` | `2 eventos` |
| MUT-TX06 | `TRANSFER:VAR11031 -> yield` | `TRANSFER:VAR13062 (block yield)` |
| MUT-S01 | `["NoneType", "None", "INVALID_INPUT", "fa"]` | `["float", "0.3601700847", null, null]` |
| MUT-S02 | `["float", "1.37255", null, null]` | `["NoneType", "None", "INVALID_INPUT", "fa"]` |
| MUT-S03 | `["float", "1.3477488333333332", null, null]` | `["NoneType", "None", "INVALID_INPUT", "fa"]` |
| MUT-S04 | `Result(1.25, None, None)` | `Result(1.25, None, 'fa')` |
| MUT-S05 | `["float", "1.3457701666666664", null, null]` | `["float", "1.3457701666666664", null, "fa"]` |
| MUT-S06 | `["float", "1.3457701666666664", null, null]` | `["NoneType", "None", "INVALID_INPUT", "fa"]` |
| MUT-S07 | `["float", "0.36082563714000004", null, null]` | `["NoneType", "None", "INVALID_INPUT", "fa"]` |
| MUT-S08 | `["NoneType", "None", "INVALID_INPUT", "fa"]` | `["NoneType", "None", "INVALID_INPUT", null]` |
| MUT-S09 | `["float", "776916.9563612082", null, null]` | `["NoneType", "None", "INVALID_INPUT", "fa"]` |
| MUT-S10 | `["float", "1.4509999999999998", null, null]` | `["NoneType", "None", "VALIDATION_FAILED", "t"]` |
| MUT-S11 | `["NoneType", "None", "VALIDATION_FAILED", "t"]` | `["float", "1.46", null, null]` |
| MUT-A01 | `INVALID_INPUT/x + INVALID_INPUT/x` | `INVALID_INPUT/x + VALIDATION_FAILED/x` |
| MUT-A02 | `INVALID_INPUT/x + INVALID_INPUT/x` | `INVALID_INPUT/x + INVALID_INPUT/y` |
| MUT-A03 | `["NoneType", "None", "INVALID_INPUT", "agg"]` | `["float", "1.00025", null, null]` |
| MUT-A04 | `["NoneType", "None", "INVALID_INPUT", "agg"]` | `["NoneType", "None", "INVALID_INPUT", null]` |
| MUT-A05 | `["NoneType", "None", "INVALID_INPUT", "agg"]` | `["float", "11.884293149167227", "INVALID_INPUT", "agg"]` |
| MUT-A06 | `["NoneType", "None", "INVALID_INPUT", "agg"]` | `["NoneType", "None", null, "agg"]` |
| MUT-TM01 | `window_end 2026-01-14 e 2026-01-15` | `window_end 2026-01-14 (valor da 15)` |
| MUT-TM02 | `1 identidade (window 2026-01-15)` | `2 identidades (2026-01-15, 2026-01-15T00:00:00)` |
| MUT-TM03 | `["float", "1.3705500000000002", null, null]` | `["float", "1.3732000000000002", null, null]` |
| MUT-TM04 | `31 janelas` | `31 janelas + window None` |
| MUT-TM05 | `period 2026-02` | `period 2026-01` |
| MUT-R01 | `["float", "1.3715000000000002", null, null]` | `["float", "7.0", null, null]` |
| MUT-R06 | `["float", "1.0015", null, null]` | `["float", "7.0", null, null]` |
| MUT-R02 | `1 evento` | `2 eventos` |
| MUT-R03 | `["float", "1.3472270733333334", null, null]` | `["NoneType", "None", "INVALID_INPUT", "residual"]` |
| MUT-R04 | `UNCHANGED` | `WRITTEN` |
| MUT-R05 | `1.0025000000000002` | `0.0` |
| MUT-DT01 | `d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d` | `a122e4333f0926435e405301c32b4de2164aea088f02a35fce0e0f44e6aeb88c` |
| MUT-DT02 | `AGGREGATION:AGR-MAX_HT-ALIMENTAÇÃO_EVAP-LINHA-L1_L7-ANUAL-AVERAGE ... ` | `TRANSFER:VAR18011 ... AGGREGATION:AGR-MAX_HT-ALIMENTAÇÃO_EVAP-LINHA-L1` |
| MUT-DT03 | `e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff` | `6eebe2d3e6d39a992657422693d738d59905a88f11cf1a7d3b3ffd17c8d44b5a (sem ` |
| MUT-DT04 | `d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d` | `a122e4333f0926435e405301c32b4de2164aea088f02a35fce0e0f44e6aeb88c` |
| MUT-D01 | `["float", "0.063525"]` | `["float", "0.063525001"]` |
| MUT-D02 | `null` | `INVALID_INPUT` |
| MUT-D03 | `null` | `x` |
| MUT-D04 | `AGR-ENERGY-ENERGIA_BAYER-GRUPO-L1_L7-MENSAL-WEIGHTED_AVERAGE@L1_L7` | `ausente` |
| MUT-D05 | `1 caso` | `2 casos` |
| MUT-D06 | `2026-09` | `1999` |
| MUT-P01 | `REAL_DERIVED_TEST_RESULT` | `OPERATIONAL_RESULT` |
| MUT-P02 | `fixture pending = 0` | `fixture pending = 1` |
| MUT-P03 | `16 pendências` | `0 pendências` |
| MUT-P04 | `16 pendências persistidas` | `0 pendências persistidas` |
| MUT-P05 | `PENDING_LOAD` | `RESOLVED_BY_FIXTURE` |
| MUT-P06 | `TEST_FIXTURE_ONLY (implícito)` | `OPERATIONAL` |

### 3.1 Mutantes de código (contrato 3.4A §19)

**Como cada mutante roda:**
- Árvore temporária: `git clone --shared` de HEAD. O clone lê os objetos do repositório e não escreve nele. Alguns testes existentes leem o histórico git.
- Sobre ela entram o harness atual da Stage 3.4 e a substituição textual, que precisa ser única no arquivo; arquivos CRLF são preservados.

**Detectores** (nenhum conhece o mutante):
- **TESTS:** a suíte existente, exceto os três testes de harness da 3.4B/3.4C/3.4D, executados abaixo como auditoria.
- **INTEGRATED:** `mutant_probe.py`, com os auditores da 3.4C e regressão contra `integrated_summary.json` e `nodes.csv` versionados.
  - Roda sob `python -I`.
  - Carregou 0 módulos `app` fora da árvore.
- **DIFFERENTIAL:** `run_differential.produce(mutate)` mais `evaluate`, com 7877551 × candidate mutado.

| ID | contrato 3.4A §19 | mutação (arquivo) | detectores esperados | detectado por | resultado |
|---|---|---|---|---|---|
| CM-01 | aggregator arithmetic: AVERAGE (e MOVING, mesma aritmética) | média divide por n+1 (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-02 | aggregator arithmetic: SUM | SUM descarta o primeiro sub-período (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-03 | aggregator arithmetic: integration_factor | integration_factor ignorado (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-04 | aggregator arithmetic: WEIGHTED_AVERAGE (peso) | peso ignorado no numerador (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-05 | aggregator window: MOVING_AVERAGE (janela) | janela móvel reduzida ao último dia (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-06 | window_end | window_end nunca preenchido (janelas colapsam na identidade do período) (`app/engine/calculation_context.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-07 | janela efetiva | janela efetiva de agregação reduzida ao último dia (`app/engine/temporal_aggregation_service.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-08 | leitura interbloco: instância errada | produtor lido sempre na primeira instância do vínculo (`app/engine/interblock_resolver.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-09 | leitura interbloco: produtor errado | produtor lido de outro vínculo (`app/engine/interblock_resolver.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-10 | propagação de estado: descarte (equação) | estado herdado das dependências descartado (`app/domain/state_propagation.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-11 | propagação de estado: descarte (agregação) | Policy B não compõe o estado dos componentes (`app/domain/state_propagation.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-12 | composição de state: escolha de estado | estados diferentes: escolhe o primeiro em vez do erro (`app/domain/state_propagation.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-13 | composição de detail | details diferentes: escolhe o primeiro em vez do erro (`app/domain/state_propagation.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-14 | seleção de ramo IF | condição do IF invertida (`app/engine/expression_evaluator.py`) | TESTS, INTEGRATED, DIFFERENTIAL | DIFFERENTIAL, INTEGRATED, TESTS | PASS |
| CM-15 | IF: propagação estrutural | estado do ramo INATIVO propagado (avaliação especulativa) (`app/engine/expression_evaluator.py`) | TESTS, INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-16 | ordenação do plano | fila de prontos LIFO em vez de heap canônico (`app/engine/interblock_orchestrator.py`) | INTEGRATED | INTEGRATED, TESTS | PASS |
| CM-17 | determinismo | escolha do próximo nó dependente de hash() (PYTHONHASHSEED) (`app/engine/interblock_orchestrator.py`) | INTEGRATED | INTEGRATED, TESTS | PASS |

- **Contagem:** 17 introduzidos, **17 detectados, 0 sobreviventes**.
- **Por detector:** TESTS 17/17, INTEGRATED 17/17, DIFFERENTIAL 7/7 dos mutantes no caminho sem estado.
- **Controle `CM-00`** (árvore sem mutação): aceito pelos três detectores, com `detected_by` vazio.
- **Repositório:** `git status -- app data tools` vazio antes e depois.

Alguns mutantes são mortos por exceção do engine mutado, e isso conta como detecção:
- CM-06: `INTERBLOCK_CONSUMER_VALUE_CONFLICT`;
- CM-09: `INTERBLOCK_SOURCE_VALUE_NOT_FOUND`;
- CM-10: `CalculationValueError`;
- CM-11: `RESULT_CONTRACT_INVALID`.

## 4. Mutation coverage (22.4)

| | mutações de evidência | mutantes de código |
|---|---:|---:|
| defined / introduced | 58 | 17 |
| executed | 58 | 17 |
| detected | 58 | 17 |
| missed / surviving | **0** | **0** |
| detection rate | **100%** | **100%** |

Por contrato (definidas = detectadas): M1 3, M2 5, M3 6, M4 11, M5 6, M6 5, M7 6, M8 4, M9 6, M10 6.

As 27 mutações obrigatórias do §6 do prompt estão presentes, com os IDs pedidos:

```text
T01 T02  N01 N02 N03  TX01 TX02 TX03 TX04  S01 S02 S03 S04  A01 A02 A03
TM01 TM02  R01 R02  D01 D02 D03 D04 D05  P01 P02
```

As outras 31 ampliam a cobertura de cada contrato.

## 5. Positive controls (22.5)

`audit/stage3_4/mutation/positive_controls.csv`: a mesma evidência, **sem** mutação, passa pelos mesmos auditores.

| controle | família | resultado |
|---|---|---|
| PC-TARGET-NODE-TRANSFER (32 datas) | M1/M2/M3 | ACCEPT |
| PC-STATE-SC1 (EQ12012 + cadeia interbloco) | M3/M4 | ACCEPT |
| PC-STATE-SC2 (EQ18003) | M4 | ACCEPT |
| PC-AGGREGATION-SC3 (4 tipos reais) | M5 | ACCEPT |
| PC-AGGREGATION-SAME-STATE-SAME-DETAIL | M5 | ACCEPT |
| PC-RESULT-CONTRACT (combinações válidas de `Result`) | M4/M5 | ACCEPT |
| PC-CLEAN-CONTEXT | M4 | ACCEPT |
| PC-TEMPORAL | M6 | ACCEPT |
| PC-REEXECUTION-2026-01-15 / -2026-02-01 | M7 | ACCEPT / ACCEPT |
| PC-DETERMINISM | M8 | ACCEPT |
| PC-DIFFERENTIAL (4722 casos, 7877551 × HEAD) | M9 | ACCEPT |
| PC-PROVENANCE | M10 | ACCEPT |
| CM-00 (árvore de código sem mutação) | §19 | ACCEPT |

**Aceitos: 14/14; rejeitados inesperadamente: 0.** Nenhum auditor "rejeita tudo".

A auditoria black-box também tem controle: a cópia não corrompida é aceita antes de cada corrupção nos testes.

## 6. Real-path evidence (22.6)

| caminho real | mutações |
|---|---:|
| 3.4C: trace real de planner + orquestrador + engine | 11 |
| 3.4C: orquestrador real executando plano mutilado | 1 |
| 3.4C: cenários de estado reais (execuções gêmeas) | 16 |
| 3.4C: store temporal real | 4 |
| 3.4C: FIRST_RUN × REEXECUTION reais | 5 |
| 3.4C: reexecução real numa cópia do contexto | 2 |
| 3.4C: fingerprints reais (subprocessos / ORDER_B) | 4 |
| 3.4B: saída real dos runners 7877551 × HEAD | 6 |
| contrato real do app (Result / composição do engine) | 3 |
| fixture REAL_DERIVED + registro persistido (cópia temporária) | 6 |
| **synthetic-only** | **0** |

**Real path, sem helper sintético:**
- Toda mutação parte de evidência produzida pela execução real: fixture REAL_DERIVED, planner, orquestrador e engine reais; runtime 7877551 × HEAD no diferencial.
- A mutação é aplicada a uma cópia: lista de eventos, store, contexto trocado temporariamente e restaurado, JSON do candidate, ou cópia de `data/seed` em diretório temporário.
- O julgamento é do **mesmo** auditor usado pelo `run_integrated.py` / `run_differential.py`.

**Mutações que exercitam o engine real diretamente:**
- MUT-N05: o orquestrador executa um `ExecutionPlan` sem o último nó.
- MUT-R01 e MUT-R06: reexecução real de 2026-01-15 com entrada alterada.
- MUT-A01 e MUT-A02: a agregação mensal real de VAR11001 compõe estados e details conflitantes.
- MUT-DT01: subprocesso real com PYTHONHASHSEED=4242.

**Reuso da infraestrutura 3.4B/3.4C:**
- **3.4B:** `run_differential.py` foi dividido em `produce()` (passos 1–3) e `evaluate()` (passos 4–5), sem mudar a lógica. `main()` compõe os dois.
  - A 3.4D reaplica `evaluate()`, o comparador da regressão diferencial, a cópias mutadas da saída real.
  - Não há comparador novo.
- **3.4C:** os cenários SC1/SC2/SC3 e SC4 foram extraídos para funções que devolvem a evidência real e o seu auditor (`scenario_sc1` … `composition_run`).
  - `node_expectations`, `transfer_expectations`, `expected_periods`, `target_records` e `derived_variables` saíram do `main()`.
  - O `main()` da 3.4C passa a chamar exatamente essas funções. A 3.4D importa as mesmas.

## 7. Contract audit M1–M10 (22.7)

**M1 — target coverage.**
- Detectam-se:
  - alvo omitido (T01): `TARGET_NOT_EXECUTED`;
  - alvo duplicado (T02): `TARGET_DUPLICATED`;
  - alvo gravado na identidade temporal errada (T03): `TARGET_WRONG_PERIOD`.
- "Alvo não executado" é o mesmo sinal de T01, aplicado por data e por instância.

**M2 — planner coverage.**
- `PLANNER_ONLY_NODE` (N01, N05 com execução real), `ENGINE_ONLY_NODE` (N02), `NODE_EXECUTED_TWICE` (N03) e `NODE_EVENT_COUNT` (N04, nó × eventos produzidos).

**M3 — interblock.**
- Remoção (TX01), valor (TX02), state (TX03, só o state muda), detail (TX04, só o detail muda), duplicidade (TX05) e alvo/bloco errado (TX06): todos `INTERBLOCK_FAILURE`.
- TX03/TX04 usam a evidência real com estado do SC1, em que a consumidora VAR11031 recebeu `INVALID_INPUT/"fa"` pela transferência.

**M4 — state.**
- Alcance quebrado:
  - descendente real de EQ12012 (S01, VAR12031 L3 em 2026-01-20);
  - ramo ativo de EQ18003 (S11).
- Vazamentos:
  - para não descendente (S02);
  - para outro contexto (S03);
  - para outra linha (S06);
  - para outra data (S07).
- Detail perdido (S08).
- Detail sem state, pelo contrato real `Result` (S04) e na evidência (S05): `DETAIL_WITHOUT_STATE`.
- Estado atravessando o ramo **inativo** de EQ12012 (S09) e de EQ18003 (S10).

**M5 — aggregation.**
- `MULTI_STATE_COMBINATION_UNDEFINED` (A01) e `MULTI_DETAIL_COMPOSITION_UNDEFINED` (A02), levantados pela composição real do engine.
- Perda de state (A03, AVERAGE) e perda de detail (A04, SUM).
- Valor devolvido junto com o estado quando o resultado deve ser state-only (A05, WEIGHTED_AVERAGE).
- Detail sem state (A06, MOVING_AVERAGE).
- Todos sobre regras reais do SC3.

**M6 — temporal.**
- Duas janelas colapsadas numa identidade (TM01).
- Nova identidade para a mesma janela na reexecução (TM02).
- Contaminação de uma janela de janeiro pelo resultado de fevereiro (TM03).
- Identidade mensal sem janela (TM04).
- Janela atribuída ao período errado (TM05).
- **Controle:** mesma janela → mesma identidade (reexecuções de 2026-01-15 e 2026-02-01); janelas diferentes → identidades diferentes (31 janelas por identidade mensal de janeiro, 32 por identidade anual).

**M7 — reexecution.**
- Resultado diferente (R01, execução real).
- Transferência duplicada (R02).
- Estado residual (R03).
- Transferência regravada (R04).
- Evento divergente com o store intacto (R05).
- R06: uma reexecução real com entrada diferente **a montante de uma transferência** é barrada pelo próprio engine com `INTERBLOCK_CONSUMER_VALUE_CONFLICT`, antes do auditor.
  - É a guarda D33B-04 do resolver: resultado diferente na mesma identidade nunca é sobrescrito.
  - Por isso R01 usa uma entrada sem transferência a jusante (VAR13003), para exercitar também o auditor.

**M8 — determinism.**
- Divergência sob hash seed (DT01, subprocesso real com PYTHONHASHSEED=4242 e um resultado alterado antes do hash).
- Ordem de blocos que altera a ordem do plano (DT02).
- Ordem de vínculos com grafo divergente (DT03, registro ORDER_B reconstruído em memória).
- Ordem de inserção equivalente (ORDER_B) com resultado divergente (DT04).
- Todas geram `DETERMINISM_FAILURE`.
- Entre os mutantes de código: CM-16 (fila LIFO) e CM-17 (escolha dependente de `hash()`) são mortos pela regressão da ordem do plano e pelo teste existente `test_20_hash_seed_does_not_matter`.

**M9 — differential.**
- Detectados pelo comparador da 3.4B:
  - `VALUE_DIFFERENCE` (D01, +1e-9 num valor);
  - `STATE_DIFFERENCE` (D02);
  - `DETAIL_DIFFERENCE` (D03);
  - `MISSING_CANDIDATE_RESULT` com `COVERAGE_MISSING` (D04);
  - `COVERAGE_DUPLICATES` (D05);
  - `STRUCTURAL_DIFFERENCE` (D06).
- Os códigos `COVERAGE_*` são o rótulo, na matriz, das listas `duplicates` e `missing` de `compare.coverage`. Não são códigos novos do comparador.

**M10 — provenance.**
- Detectam-se:
  - fixture rotulado ou classificado como operacional (P01, P06): `PROVENANCE_FAILURE`;
  - fixture com a representação das pendências alterada (P02): `FIXTURE_FAILURE`;
  - registro oficial em memória mascarado (P03): `PENDING_LINKS_ALTERED`;
  - registro persistente alterado ou com pendência mascarada, numa **cópia temporária** de `data/seed` (P04, P05): `PENDING_LINKS_ALTERED` com `PROVENANCE_FAILURE`.

## 8. Fixture / provenance audit (22.8)

```text
REAL_DERIVED                      = TEST_FIXTURE_ONLY
fixture graph hash                = e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff  (= 3.4C)
fixture pending links             = 0   (somente em memória)
official registry pending links   = 16  (PENDING_LOAD)
data/seed/interblock_links.json   = byte a byte igual a 043fe9c
operational provenance mutation   = nenhuma
```

- Nenhum modo operacional REAL_DERIVED foi implementado.
- Nenhum bloco ausente foi carregado. Os 16 vínculos pendentes não foram resolvidos.
- **D32-01 permanece `CLOSED_FOR_STAGE_3_SCOPE`** (3.4A §4). D32-02 continua resolvida na 3.3B.
- As mutações P04/P05 escreveram somente em `tempfile.TemporaryDirectory`, apagado ao fim.

## 9. Documentation reconciliation (22.9)

**Artefatos comparados:**
- 3.4A: `STAGE_3_4A_DECISION_CONTRACT.md`;
- 3.4B: relatório e evidência;
- 3.4C: relatório e evidência;
- 3.4D: este relatório e a evidência.

A auditoria black-box (§11) repete essa conferência mecanicamente.

| item | 3.4A | 3.4B | 3.4C | 3.4D / código | situação |
|---|---|---|---|---|---|
| alvos oficiais / area_41 / integrados | 446 / 25 / 421 | — | 446 / 25 / 421 | 446 / 25 / 421 (plan_evidence.csv, `targets_of_blocks`) | consistente |
| nós do plano | 427 = 218 + 197 + 12 | — | 427 = 218 + 197 + 12 | idem | consistente |
| instâncias de equação / agregação | 392 / 395 | 392 / 395 | 392 + 395 + 60 = 847 eventos por data | idem | consistente |
| tipos de agregação | 342 / 42 / 9 / 2 | 342 / 42 / 9 / 2 | — | idem | consistente |
| regras anuais | 48 (max_ht 39, production 9) | — | 48 | 48 (39 + 9) | consistente |
| transferências | 12 (13 vínculos − area_41) | — | 12 / 12, 1920 eventos | idem | consistente |
| datas | 32 (2026-01-01..2026-02-01) | 2 datas por caso | 32 | 32 | consistente |
| alvos executáveis oficialmente | 156 dos 421 (159 dos 446 − 3 de area_41) | — | — | 159 OK, 3 area_41 (plan_evidence.csv) | consistente |
| pendências | 16 `PENDING_LOAD` | — | 16 oficial / 0 fixture | 16 / 0 | consistente |
| D32-01 / D32-02 | CLOSED_FOR_STAGE_3_SCOPE / resolvida 3.3B | — | não citados | inalterados | consistente |
| identidades temporais | — | — | 313 mensais (jan), 313 (fev), 185 anuais | 313 / 313 / 185 pelo detector reforçado | consistente |

**Divergências encontradas e resolução:**

**1. Capacidade de detecção descrita na 3.4C maior que a implementada.**
- A sonda `baseline_gap_probe.py` extrai, com `git archive`, o `audit/stage3_4/integrated` de **043fe9c**. Contra esse auditor original, reproduziu cinco gaps:
  - **G1:** um descendente que perde o estado numa data não nomeada passava; só 2026-01-10 era conferida.
  - **G2:** valor presente junto com o estado propagado passava; o oráculo comparava só state/detail.
  - **G3:** transferência duplicada não era acusada pelo verificador interbloco, só indiretamente pela contagem de eventos do nó.
  - **G4:** transferência atribuída a outro alvo com o mesmo produtor não era acusada pelo verificador interbloco.
  - **G5:** identidade mensal derivada sem janela era ignorada pelo filtro `None not in v`. Registrado por inspeção do código de 043fe9c.
- **Natureza:** gaps do **harness de auditoria**. Não são defeitos de produção: a execução real nunca produziu esses casos, e a evidência da 3.4C continua verdadeira.
- **Canônico:** o código do auditor.
- **Resolução:**
  - os detectores foram reforçados em `checks.py`:
    - `check_state_diff` exige resultado state-only;
    - `check_transfers` confere duplicidade, instâncias e blocos do vínculo;
    - funções novas `check_target_identities`, `check_temporal`, `check_reexecution`, `check_determinism`, `check_clean_context` e `check_result_contract`;
  - as expectativas dos cenários passaram a cobrir todas as datas;
  - as mutações que antes passavam (S01, A05, TX05, TX06, TM04) agora são detectadas.
- **Verificação do reforço:** o harness 3.4C **não mutado** foi reexecutado depois dele e da refatoração. A evidência versionada da 3.4C saiu **byte a byte idêntica** (`git diff` vazio em `integrated/evidence/`): 421/421, 427/427, 12/12 e 32 datas, com todos os checks PASS.
- O relatório da 3.4C não foi reescrito: este relatório é o registro canônico do reforço.

**2. Escopo da 3.4D: prompt × contrato 3.4A §19.**
- O §19 exige mutantes de **código** (aritmética de cada agregador, `window_end`, leitura interbloco, propagação e escolha de estado, ramo IF, ordenação e determinismo, composição) e uma auditoria **black-box sem importar `app/`**.
- O prompt da 3.4D descreve mutações de evidência.
- **Resolução:** os dois foram executados (§3.1 e §11). As mutações de código ficaram só em cópias temporárias, conforme o §4 do prompt.

**3. Nomenclatura de códigos.**
- Os códigos do contrato de resultado são os existentes (`DETAIL_WITHOUT_STATE`, `RESULT_CONTRACT_INVALID`, `MULTI_STATE_COMBINATION_UNDEFINED`, `MULTI_DETAIL_COMPOSITION_UNDEFINED`, `INTERBLOCK_CONSUMER_VALUE_CONFLICT`). Nenhum código de erro foi criado em `app/`.
- Os rótulos novos são **classificações do harness**, para casos que as classes da 3.4C não distinguiam:
  - `TARGET_DUPLICATED`, `TARGET_WRONG_PERIOD`;
  - `REEXECUTION_FAILURE`, que antes aparecia como `TEMPORAL_FAILURE reexecução`;
  - `PROVENANCE_FAILURE`, `PENDING_LINKS_ALTERED`;
  - `PLANNER_ORDER_REGRESSION`, `INTEGRATED_REGRESSION`;
  - o rótulo `COVERAGE_*`.

Nenhuma outra divergência de números, blocos, datas, status D32 ou classificação REAL_DERIVED foi encontrada.

## 10. Protected artifact audit (22.10)

```text
git diff --stat 043fe9c -- app data tools   -> vazio
git status --porcelain -- app data tools    -> vazio
data/workbooks/, data/seed/, interblock_links.json -> inalterados
NO PRODUCTION CHANGES
```

- **Arquivos alterados pela 3.4D:** apenas harness, testes, evidência e documentação.
- **Harness e evidência:**
  - `audit/stage3_4/integrated/{checks.py, run_integrated.py}`: detectores reforçados, cenários extraídos em funções e o gancho `--mutate-one-result`, usado só pelo modo fingerprint da 3.4D;
  - `audit/stage3_4/differential/run_differential.py`: `produce(mutate)` e `evaluate()`;
  - o diretório novo `audit/stage3_4/mutation/`.
- **Testes e documentação:** `tests/test_stage3_4d_mutation.py` e este relatório.
- Nenhum mutante de código foi persistido. Nenhum commit contém código mutado.

## 11. Black-box audit (contrato 3.4A §19)

`blackbox_audit.py` não importa `app/` nem os harnesses. Ele termina verificando `sys.modules`, e o teste o executa sob `python -I`.

**Entrada:**
- a evidência versionada da 3.4B (`differential_cases.csv`, `differential_summary.json`);
- a evidência da 3.4C (`integrated_summary.json`, `targets.csv`, `nodes.csv`, `transfers.csv`, `temporal_coverage.csv`);
- a evidência da 3.4D (matriz, resultados, controles, mutantes de código, sumário).

**Oráculo:** escrito a partir da 3.4A §13–§19 e dos prompts:
- 446 / 25 / 421 / 427 / 218 / 197 / 12;
- 392 / 395, 4722 casos, 342 / 42 / 9 / 2;
- 32 datas, 847 eventos por data;
- 16 pendências;
- rótulos obrigatórios;
- as 27 mutações obrigatórias, M1..M10 e os tópicos de mutantes do §19.

**Resultado:**
- `PASS`, 0 achados, `imports_app = false` (`blackbox_audit.json`);
- nos testes, ela rejeita seis corrupções de evidência, uma por artefato (3.4B, 3.4C, 3.4D), e aceita a cópia íntegra.

## 12. Full suite (22.11)

| | resultado |
|---|---|
| tests_before | 1845 passed, 0 failed, 0 skipped |
| tests_after | **1859 passed, 0 failed, 0 skipped** (+14 de `tests/test_stage3_4d_mutation.py`) |
| 3.4B / 3.4C | `tests/test_stage3_4b_differential.py` e `tests/test_stage3_4c_integrated.py`: 25 passed com os harnesses refatorados |
| ruff | `audit/stage3_4/` e os testes novos: sem achados |

Nenhum teste foi removido ou enfraquecido.

Na primeira execução da suíte completa, 6 testes novos falharam. O motivo era a verificação "não importou `app`" da auditoria black-box: ela disparava quando a auditoria era chamada dentro do processo do pytest, onde outros testes já tinham importado `app`.
- **Correção:** a verificação passou a valer somente para a execução isolada (`python -I`). É exatamente o que o teste `test_blackbox_audit_passes_without_importing_app` exige.
- **Resultado:** suíte reexecutada, verde.

## 13. Limitations (22.12)

Continuam verdadeiras e explícitas. Nenhuma virou PASS por construção.

1. **Sem oráculo numérico independente** (`INDEPENDENT_ORACLE = NO`; o oracle Python de energy não é usado). As mutações provam que os auditores **detectam regressões**, não que os valores são corretos no negócio.
2. **REAL_DERIVED usa entradas sintéticas.** As 16 consumidoras pendentes são entradas livres do fixture.
3. **A comparação orquestrador × engine compartilha o engine.** Os mutantes aritméticos são detectados pela regressão contra a evidência versionada e pelo diferencial contra 7877551, não por essa comparação.
4. **YTD coverage is partial. Year boundary is not fully exercised** (32 datas).
5. **production ↔ yield não é ciclo de variáveis** que exija convergência. O ciclo é só de bloco.
6. **O diferencial cobre só o caminho sem estado** (DR-3). Mutantes de estado, janela, interbloco e ordenação ficam fora dele por construção (§3.1) e são mortos pelos testes e pela auditoria integrada.
7. **Os detectores de regressão integrada comparam com a evidência versionada da 3.4C.** Uma mudança **intencional** de comportamento exigirá regenerar essa evidência numa etapa própria.
8. **Mutações de evidência operam sobre cópias em memória.** Elas representam a falha que o auditor precisa detectar, não uma falha observada em produção.
9. **O custo:** a matriz completa com mutantes de código leva ≈ 8 min. Os testes executam ao vivo as mutações de evidência e um mutante de código; os outros 16 são validados pela evidência versionada e pela auditoria black-box.

## 14. Final gate

Todos os critérios do §23 do prompt estão satisfeitos:

- **Baseline:** 043fe9c, árvore limpa, 1845 passed.
- **Mutation:** matriz formal; 100% das 58 mutações e dos 17 mutantes detectados; nenhuma aceita em silêncio; 14/14 controles aceitos.
- **Coverage:** M1–M10 auditados.
- **Real path:** 0 mutações só sintéticas.
- **Fixture:** TEST_FIXTURE_ONLY, registro intacto, 16 pendências.
- **Documentation:** reconciliada, com gaps registrados e fechados no harness.
- **Regression:** harness 3.4C não mutado PASS com evidência idêntica; suíte verde, 0 skipped.
- **Integrity:** nenhum artefato de produção alterado.

A Stage 3.4E não foi iniciada.

STAGE_3.4D_GATE: PASS
