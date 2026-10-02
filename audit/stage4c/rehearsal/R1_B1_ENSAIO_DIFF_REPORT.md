# DIFF_REPORT — B1-ensaio (PROPOSED) x B0 (current)

- stage: `ensaio-5A`
- motivo: ensaio 4C
- commit_comportamento: `f573c1b6cb93` → `8b7f89086565`
- data: 2026-10-02

## 1. Conteúdo (seeds, ledger, vínculos) entre os commits de comportamento

| bloco | arquivo | antes | depois | novos | removidos |
|---|---|---|---|---|---|
| yield | variables | 240 | 240 | — | — |
| production | variables | 66 | 66 | — | — |
| energy | variables | 52 | 53 | VAR18053 | — |
| energy | equations | 24 | 25 | EQ18025 | — |
| max_ht | variables | 116 | 117 | VAR13117, VAR13118, VAR13119, VAR13120, VAR13121, VAR13122, VAR13123 | VAR13001, VAR13002, VAR13003, VAR13004, VAR13005, VAR13006 |
| max_ht | equations | 29 | 30 | EQ13030 | — |
| max_ht | aggregation_rules | 78 | 78 | AGR-MAX_HT-ALIMENTACAO_EVAP-LINHA-L1_L7-ANUAL-AVERAGE, AGR-MAX_HT-ALIMENTACAO_EVAP-LINHA-L1_L7-MENSAL-AVERAGE, AGR-MAX_HT-ALIMENTACAO_EVAP_TOTAL-GRUPO-L1_L7-ANUAL-AVERAGE, AGR-MAX_HT-ALIMENTACAO_EVAP_TOTAL-GRUPO-L1_L7-MENSAL-AVERAGE | AGR-MAX_HT-ALIMENTAÇÃO_EVAP-LINHA-L1_L7-ANUAL-AVERAGE, AGR-MAX_HT-ALIMENTAÇÃO_EVAP-LINHA-L1_L7-MENSAL-AVERAGE, AGR-MAX_HT-ALIMENTAÇÃO_EVAP_TOTAL-GRUPO-L1_L7-ANUAL-AVERAGE, AGR-MAX_HT-ALIMENTAÇÃO_EVAP_TOTAL-GRUPO-L1_L7-MENSAL-AVERAGE |
| area_41 | variables | 36 | 36 | — | — |

| bloco | aposentados no ledger (novos) |
|---|---|
| yield | — |
| production | — |
| energy | — |
| max_ht | VAR13001, VAR13002, VAR13003, VAR13004, VAR13005, VAR13006 |
| area_41 | — |

| vínculos | antes | depois |
|---|---|---|
| declared | 29 | 29 |
| valid | 13 | 13 |
| pending | 16 | 16 |
| rejected | 0 | 0 |
| valid_set: acrescentados / removidos | 0 [] | 0 [] |
| pending_set: acrescentados / removidos | 2 ["energy.VAR18053<-area_04_13", "max_ht.VAR13119<-alumina"] | 2 ["energy.VAR18031<-area_04_13", "max_ht.VAR13003<-alumina"] |

| workbook | antes | depois |
|---|---|---|
| energy | descritivo_das_variáveis_energy_v6.xlsx cfc46031fc2f | descritivo_das_variáveis_energy_v9.xlsx 731f71e9ab38 |
| max_ht | descritivo_das_variáveis_MaxHT_v10.xlsx 3e40aab12ec0 | descritivo_das_variáveis_MaxHT_v13.xlsx c9818920b399 |

## 2. Conjuntos R (arquivo a arquivo)

### stage3_2_plan
- `plan_evidence.csv`: ALTERADO (`843bddf7d511` → `1f3dbe8994a6`)
  - linhas 446 → 448; `target` acrescentados 7 ["VAR13117", "VAR13118", "VAR13120", "VAR13121", "VAR13122", "VAR13123", "VAR18031"]; removidos 5 ["VAR13001", "VAR13002", "VAR13004", "VAR13005", "VAR13006"]
  - linhas comuns alteradas: 0 []
- `transfer_evidence.csv`: IGUAL (`cdf522e6badb` → `cdf522e6badb`)
- `analysis_summary.json`: ALTERADO (`0b3c896d14d2` → `4a8bcdf64076`)
  - campos alterados: 4
  - `blocked_by_block.area_04_13`: 18 → 19
  - `blocked_by_block.maintenance`: 259 → 260
  - `targets_blocked_official`: 287 → 289
  - `targets_planned`: 446 → 448
- expectativas alteradas: 2
  - `by_observed.INTERBLOCK_SOURCE_NOT_LOADED`: 287 → 289
  - `official_targets`: 446 → 448

### stage3_4c_integrated
- `integrated_summary.json`: ALTERADO (`714c156be821` → `ec28bffe15f2`)
  - campos alterados: 35
  - `by_block`: [{"aggregation_nodes": 28, "block": "production", "equation_nodes": 27, "execute… → [{"aggregation_nodes": 28, "block": "production", "equation_nodes": 27, "execute…
  - `determinism.HASH_SEED_A.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.HASH_SEED_A.results_sha256`: "d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d" → "aa723108a51941270d55ccc680f10836bbda6a32e3d7461a67d8735cee15f46a"
  - `determinism.HASH_SEED_A.store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.HASH_SEED_B.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.HASH_SEED_B.results_sha256`: "d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d" → "aa723108a51941270d55ccc680f10836bbda6a32e3d7461a67d8735cee15f46a"
  - `determinism.HASH_SEED_B.store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.REEXECUTION.store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.RUN_A.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.RUN_A.results_sha256`: "d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d" → "aa723108a51941270d55ccc680f10836bbda6a32e3d7461a67d8735cee15f46a"
  - `determinism.RUN_A.store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.RUN_B.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.RUN_B.results_sha256`: "d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d" → "aa723108a51941270d55ccc680f10836bbda6a32e3d7461a67d8735cee15f46a"
  - `determinism.RUN_B.store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `fixture.graph_hashes.A`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.A_rebuilt`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.B`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.tests_fixture`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `graph.production_yield_transfers.TRANSFER:VAR11031.position`: 193 → 194
  - `graph.production_yield_transfers.TRANSFER:VAR12062.position`: 257 → 258
  - `nodes_executed`: 427 → 429
  - `orchestrator_vs_engine.compared`: 12544 → 12800
  - `reexecution.2026-01-15.store_sha256_after`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `reexecution.2026-02-01.store_sha256_after`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `state.SC1_EQ12012_and_chain.descendant_variables`: 260 → 261
  - … +10 campos
- `targets.csv`: ALTERADO (`9514a8810c24` → `a87a2c35c8b0`)
  - linhas 421 → 423; `target` acrescentados 7 ["VAR13117", "VAR13118", "VAR13120", "VAR13121", "VAR13122", "VAR13123", "VAR18031"]; removidos 5 ["VAR13001", "VAR13002", "VAR13004", "VAR13005", "VAR13006"]
  - linhas comuns alteradas: 113 ["VAR13009", "VAR13010", "VAR13011", "VAR13012", "VAR13013", "VAR13014", "VAR13015", "VAR13016"]
- `nodes.csv`: ALTERADO (`6d6349ec80dd` → `70f76a5d8940`)
  - linhas 427 → 429; `order` acrescentados 2 ["427", "428"]; removidos 0 []
  - linhas comuns alteradas: 243 ["0", "1", "160", "170", "171", "172", "173", "191"]
- `transfers.csv`: IGUAL (`bf35efc4b171` → `bf35efc4b171`)
- `temporal_coverage.csv`: ALTERADO (`113c6c5740df` → `3d5ec1a2abb2`)
  - linhas 32 → 32; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 32 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- expectativas alteradas: 9
  - `nodes_executed`: 427 → 429
  - `per_date`: [["421", "427", "60", "0"]] → [["423", "429", "60", "0"]]
  - `results_sha256_RUN_A`: "d4de1aea572ad23a42cf746cee9ff9be357a05d51a5541f29616b4acca66e10d" → "aa723108a51941270d55ccc680f10836bbda6a32e3d7461a67d8735cee15f46a"
  - `store_sha256_RUN_A`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `targets_executed`: 421 → 423
  - `universe.integrated_targets`: 421 → 423
  - `universe.nodes_by_kind.EQUATION`: 218 → 220
  - `universe.official_targets`: 446 → 448
  - `universe.planner_nodes`: 427 → 429

### stage4a_contract
- `contract_expectations.json`: ALTERADO (`9dcfcb86170c` → `18d2cd2ba947`)
  - campos alterados: 15
  - `independent.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `independent.universe_4.nodes`: 427 → 429
  - `independent.universe_5.equation_instances`: 412 → 420
  - `independent.universe_5.events_per_date`: 896 → 904
  - `independent.universe_5.nodes`: 458 → 460
  - `independent.universe_5.nodes_by_kind.EQUATION`: 238 → 240
  - `independent.universe_5.targets`: 446 → 448
  - `integrated.events_per_date`: 896 → 904
  - `integrated.integrated_targets`: 446 → 448
  - `integrated.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `integrated.nodes_by_kind.EQUATION`: 238 → 240
  - `integrated.official_targets`: 446 → 448
  - `integrated.planner_nodes`: 458 → 460
  - `integrated.previous_nodes`: 427 → 429
  - `integrated.previous_targets`: 421 → 423
- `contract_audit.json`: ALTERADO (`caaffc42b6a2` → `5774b60754d8`)
  - campos alterados: 23
  - `observed_events_one_day`: 896 → 904
  - `official_plan.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `official_plan.targets`: 446 → 448
  - `union.nodes_4`: 427 → 429
  - `union.union`: 458 → 460
  - `universe_4.equation_instances`: 392 → 400
  - `universe_4.events_per_date`: 847 → 855
  - `universe_4.nodes`: 427 → 429
  - `universe_4.nodes_by_block.energy.EQUATION`: 24 → 25
  - `universe_4.nodes_by_block.max_ht.EQUATION`: 29 → 30
  - `universe_4.nodes_by_kind.EQUATION`: 218 → 220
  - `universe_4.targets`: 421 → 423
  - `universe_4.targets_by_block.energy`: 43 → 44
  - `universe_4.targets_by_block.max_ht`: 109 → 110
  - `universe_5.equation_instances`: 412 → 420
  - `universe_5.events_per_date`: 896 → 904
  - `universe_5.nodes`: 458 → 460
  - `universe_5.nodes_by_block.energy.EQUATION`: 24 → 25
  - `universe_5.nodes_by_block.max_ht.EQUATION`: 29 → 30
  - `universe_5.nodes_by_kind.EQUATION`: 238 → 240
  - `universe_5.targets`: 446 → 448
  - `universe_5.targets_by_block.energy`: 43 → 44
  - `universe_5.targets_by_block.max_ht`: 109 → 110
- `obs_register.csv`: IGUAL (`e6500c9ea328` → `e6500c9ea328`)
- `hes_decision_matrix.csv`: IGUAL (`620f1818f46c` → `620f1818f46c`)
- expectativas alteradas: 15
  - `independent.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `independent.universe_4.nodes`: 427 → 429
  - `independent.universe_5.equation_instances`: 412 → 420
  - `independent.universe_5.events_per_date`: 896 → 904
  - `independent.universe_5.nodes`: 458 → 460
  - `independent.universe_5.nodes_by_kind.EQUATION`: 238 → 240
  - `independent.universe_5.targets`: 446 → 448
  - `integrated.events_per_date`: 896 → 904
  - `integrated.integrated_targets`: 446 → 448
  - `integrated.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `integrated.nodes_by_kind.EQUATION`: 238 → 240
  - `integrated.official_targets`: 446 → 448
  - `integrated.planner_nodes`: 458 → 460
  - `integrated.previous_nodes`: 427 → 429
  - `integrated.previous_targets`: 421 → 423

### stage4a_integrated
- `integrated_summary.json`: ALTERADO (`a401f3b9b646` → `f031f0d8b001`)
  - campos alterados: 44
  - `by_block`: [{"aggregation_nodes": 28, "block": "production", "equation_nodes": 27, "execute… → [{"aggregation_nodes": 28, "block": "production", "equation_nodes": 27, "execute…
  - `determinism.HASH_SEED_A.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.HASH_SEED_A.previous_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.HASH_SEED_A.results_sha256`: "32d75cc164121c641f4df257adf7978055fea9e6bd6787052373aa7b1eb4ef8b" → "afd2466cb7e1fb567da61520a2cc79439035876a47422b6f567e383929ca8c48"
  - `determinism.HASH_SEED_A.store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `determinism.HASH_SEED_B.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.HASH_SEED_B.previous_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.HASH_SEED_B.results_sha256`: "32d75cc164121c641f4df257adf7978055fea9e6bd6787052373aa7b1eb4ef8b" → "afd2466cb7e1fb567da61520a2cc79439035876a47422b6f567e383929ca8c48"
  - `determinism.HASH_SEED_B.store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `determinism.REEXECUTION.store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `determinism.RUN_A.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.RUN_A.previous_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.RUN_A.results_sha256`: "32d75cc164121c641f4df257adf7978055fea9e6bd6787052373aa7b1eb4ef8b" → "afd2466cb7e1fb567da61520a2cc79439035876a47422b6f567e383929ca8c48"
  - `determinism.RUN_A.store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `determinism.RUN_B.graph_hash`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `determinism.RUN_B.previous_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `determinism.RUN_B.results_sha256`: "32d75cc164121c641f4df257adf7978055fea9e6bd6787052373aa7b1eb4ef8b" → "afd2466cb7e1fb567da61520a2cc79439035876a47422b6f567e383929ca8c48"
  - `determinism.RUN_B.store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `fixture.graph_hashes.A`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.A_rebuilt`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.B`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.graph_hashes.stage_3_4c`: "e372425d9a6f3cbccecfa9ff77c30ddff49be8587da4d567a252fb64d2e3d1ff" → "302fa66869d2e63b74f4caa1d0b905723ce6dbb4f5e3eb07822dc7fd80f33f91"
  - `fixture.interblock_links_sha256`: "8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700" → "b1e683071aeee31476a755b024ba89cc11a7a4965136d767af4ed23e3f191e00"
  - `nodes_executed`: 458 → 460
  - `non_regression_421.keys_compared`: 33740 → 33996
  - … +19 campos
- `non_regression_421.json`: ALTERADO (`39ac06592e82` → `88551dbe14ae`)
  - campos alterados: 6
  - `isolated_4_block_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `keys_by_period_kind.daily`: 17664 → 17920
  - `keys_compared`: 33740 → 33996
  - `reference_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `subset_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `targets_compared`: 421 → 423
- `targets.csv`: ALTERADO (`725d2ff5c384` → `df059b970015`)
  - linhas 446 → 448; `target` acrescentados 7 ["VAR13117", "VAR13118", "VAR13120", "VAR13121", "VAR13122", "VAR13123", "VAR18031"]; removidos 5 ["VAR13001", "VAR13002", "VAR13004", "VAR13005", "VAR13006"]
  - linhas comuns alteradas: 113 ["VAR13009", "VAR13010", "VAR13011", "VAR13012", "VAR13013", "VAR13014", "VAR13015", "VAR13016"]
- `nodes.csv`: ALTERADO (`9bcbdce4864b` → `f1dd34a64365`)
  - linhas 458 → 460; `order` acrescentados 2 ["458", "459"]; removidos 0 []
  - linhas comuns alteradas: 271 ["0", "1", "160", "170", "171", "172", "173", "194"]
- `transfers.csv`: IGUAL (`1872e2297c0f` → `1872e2297c0f`)
- `temporal_coverage.csv`: ALTERADO (`be4f4046f11d` → `931802bd45d7`)
  - linhas 32 → 32; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 32 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- expectativas alteradas: 11
  - `nodes_executed`: 458 → 460
  - `previous_store_sha256`: "619b4abd9e161dccab791978157ec0f62589fa7716ced169b53aea3e90e9730c" → "80b9632533c92f7dc711b18056b6d2b21c1b59132a8d9e7fafbfbb2e3c8cdf5f"
  - `results_sha256_RUN_A`: "32d75cc164121c641f4df257adf7978055fea9e6bd6787052373aa7b1eb4ef8b" → "afd2466cb7e1fb567da61520a2cc79439035876a47422b6f567e383929ca8c48"
  - `store_sha256_RUN_A`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `targets_executed`: 446 → 448
  - `universe.integrated_targets`: 446 → 448
  - `universe.nodes_by_kind.EQUATION`: 238 → 240
  - `universe.official_targets`: 446 → 448
  - `universe.planner_nodes`: 458 → 460
  - `universe.previous_nodes`: 427 → 429
  - `universe.previous_targets`: 421 → 423

### stage4b_contract
- `contract_expectations_4b.json`: ALTERADO (`610fc76bf2c6` → `dd08637f8619`)
  - campos alterados: 8
  - `independent.identity_profile.derived_diário`: 376 → 384
  - `independent.store_growth_first_day`: 1227 → 1235
  - `independent.store_growth_first_of_month`: 1143 → 1151
  - `independent.store_growth_regular_day`: 1109 → 1117
  - `temporal.derived_daily_instances`: 376 → 384
  - `temporal.events_per_date`: 896 → 904
  - `temporal.planner_nodes`: 458 → 460
  - `temporal.targets`: 446 → 448
- `contract_audit_4b.json`: ALTERADO (`dcf5e0a69eef` → `0b454c05a124`)
  - campos alterados: 30
  - `E1_turn_of_year.keys_2026_before_turn`: [400841, "fd39fc66f77e5d3fb520f5b0d655a0879f90cb180d74af4fdd5e89ad4fae68f2"] → [403729, "27a8f77c94210c2536ac7b7aa0f39da5790f2a23ea462ca8284d31211c3a6822"]
  - `E1_turn_of_year.per_date.2026-12-28.events`: 896 → 904
  - `E1_turn_of_year.per_date.2026-12-29.events`: 896 → 904
  - `E1_turn_of_year.per_date.2026-12-30.events`: 896 → 904
  - `E1_turn_of_year.per_date.2026-12-31.events`: 896 → 904
  - `E1_turn_of_year.per_date.2027-01-01.events`: 896 → 904
  - `E1_turn_of_year.per_date.2027-01-02.events`: 896 → 904
  - `E1_turn_of_year.per_date.2027-01-03.events`: 896 → 904
  - `E1_turn_of_year.snapshot_2026_after_2027_01_03`: [405277, "5d8a789a4f085e315ed42ca4c4854b759cbc78b9ecb88a25f72b9fc16af7c696"] → [408197, "b645331b3f26174a77e97d79696eae9f07a62c328136a8ce1a927502e638a1ba"]
  - `E1_turn_of_year.snapshot_2026_at_2027_01_01`: [405277, "5d8a789a4f085e315ed42ca4c4854b759cbc78b9ecb88a25f72b9fc16af7c696"] → [408197, "b645331b3f26174a77e97d79696eae9f07a62c328136a8ce1a927502e638a1ba"]
  - `E2_gaps.fresh_context_starting_2026_01_10.message`: "Valor contextualizado da variável não encontrado: VAR13003, scope_type=linha, s… → "Valor contextualizado da variável não encontrado: VAR13119, scope_type=linha, s…
  - `E2_gaps.fresh_context_starting_2026_02_01.message`: "Valor contextualizado da variável não encontrado: VAR13003, scope_type=linha, s… → "Valor contextualizado da variável não encontrado: VAR13119, scope_type=linha, s…
  - `E2_gaps.skip_2026_01_06_then_run_01_07.message`: "Valor contextualizado da variável não encontrado: VAR13003, scope_type=linha, s… → "Valor contextualizado da variável não encontrado: VAR13119, scope_type=linha, s…
  - `E4_closed_periods.snapshot_2026_after_reexecution_and_new_dates`: [405277, "5d8a789a4f085e315ed42ca4c4854b759cbc78b9ecb88a25f72b9fc16af7c696"] → [408197, "b645331b3f26174a77e97d79696eae9f07a62c328136a8ce1a927502e638a1ba"]
  - `collisions.entities`: 508 → 510
  - `collisions.identities`: 221966 → 224910
  - `collisions.keys`: 408722 → 411666
  - `empirical_acyclicity.plan_nodes`: 458 → 460
  - `independent.cycles.instance_edges`: 2041 → 2049
  - `independent.cycles.instance_nodes`: 1227 → 1235
  - `independent.cycles.variable_nodes`: 505 → 507
  - `performance.estimate_seconds.T1_396`: 126 → 183
  - `performance.estimate_seconds.T2_62`: 20 → 29
  - `performance.estimate_seconds.T3_792`: 377 → 550
  - `performance.first_95`: [["2026-01-01", 0.1388, 1227], ["2026-01-06", 0.1653, 6772], ["2026-01-11", 0.15… → [["2026-01-01", 0.2498, 1235], ["2026-01-06", 0.2181, 6820], ["2026-01-11", 0.26…
  - … +5 campos
- `performance_probe.csv`: ALTERADO (`90d60503d5ac` → `d75842e81e1a`)
  - linhas 361 → 361; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 361 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- expectativas alteradas: 8
  - `independent.identity_profile.derived_diário`: 376 → 384
  - `independent.store_growth_first_day`: 1227 → 1235
  - `independent.store_growth_first_of_month`: 1143 → 1151
  - `independent.store_growth_regular_day`: 1109 → 1117
  - `temporal.derived_daily_instances`: 376 → 384
  - `temporal.events_per_date`: 896 → 904
  - `temporal.planner_nodes`: 458 → 460
  - `temporal.targets`: 446 → 448

### stage4b_temporal
- `T1/identities_by_date.csv`: ALTERADO (`993aa61a9d86` → `7c2090f71e36`)
  - linhas 396 → 396; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 396 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T1/performance_profile.csv`: ALTERADO (`a6f261fdf006` → `703c339a502b`)
  - linhas 396 → 396; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 396 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T1/period_snapshots.json`: ALTERADO (`f38f997336c9` → `eb523a2684a4`)
  - campos alterados: 26
  - `2026-01.at_end`: [28337, "9f70e5d2f355bdb8f57e168a685f153dca6d3cf32b05f77921ec02a897071249"] → [28585, "3cc41b3d16da36d0eef49efd17a1f47b37285deeae213e3bb0580ef2f184e618"]
  - `2026-01.at_turn`: [28337, "9f70e5d2f355bdb8f57e168a685f153dca6d3cf32b05f77921ec02a897071249"] → [28585, "3cc41b3d16da36d0eef49efd17a1f47b37285deeae213e3bb0580ef2f184e618"]
  - `2026-02.at_end`: [25598, "7230d0a6c0debbb3e1b021fa113dcd64df719cc02de25d2d58c76a6124d07560"] → [25822, "f62eebdd28f2f701bc59f4c33e0f0cd8c0c76b78c857b77b3d893a89d82eb7e1"]
  - `2026-02.at_turn`: [25598, "7230d0a6c0debbb3e1b021fa113dcd64df719cc02de25d2d58c76a6124d07560"] → [25822, "f62eebdd28f2f701bc59f4c33e0f0cd8c0c76b78c857b77b3d893a89d82eb7e1"]
  - `2026-03.at_end`: [28337, "3f74671f87b1f28ef3b8cdfa6c568047c7209ea879c61a3e196d13b4d58569d6"] → [28585, "a7d87a168357e55ff5379a49f7fcdff8c18295029b5492b43c4d458db8b64b0b"]
  - `2026-03.at_turn`: [28337, "3f74671f87b1f28ef3b8cdfa6c568047c7209ea879c61a3e196d13b4d58569d6"] → [28585, "a7d87a168357e55ff5379a49f7fcdff8c18295029b5492b43c4d458db8b64b0b"]
  - `2026-04.at_end`: [27424, "1fa35cbdd32a91efdcb9becd9a1eb852b41bfd65490638ac18b47b2baa5d7b63"] → [27664, "5712d8f3d28a0e0418ef540b1c9f53e59370e6187308f9105d9a71127d1598de"]
  - `2026-04.at_turn`: [27424, "1fa35cbdd32a91efdcb9becd9a1eb852b41bfd65490638ac18b47b2baa5d7b63"] → [27664, "5712d8f3d28a0e0418ef540b1c9f53e59370e6187308f9105d9a71127d1598de"]
  - `2026-05.at_end`: [28337, "e80e1c283cc58c7b3682a105cfaf4ac6d9522863aebbc151ac422530ea9a14ab"] → [28585, "77092b153409938febd86843ee9a02f55b6b84a425a5e68e479eb673edf45e2c"]
  - `2026-05.at_turn`: [28337, "e80e1c283cc58c7b3682a105cfaf4ac6d9522863aebbc151ac422530ea9a14ab"] → [28585, "77092b153409938febd86843ee9a02f55b6b84a425a5e68e479eb673edf45e2c"]
  - `2026-06.at_end`: [27424, "281e9b5d9a74206c47c698a25cc0651823db537dbf4f8fb7e802295a3c97fb19"] → [27664, "f6106737f2acfc4a0c0bc594206f7c89b98ee6fd4490e748e996c45c497679a7"]
  - `2026-06.at_turn`: [27424, "281e9b5d9a74206c47c698a25cc0651823db537dbf4f8fb7e802295a3c97fb19"] → [27664, "f6106737f2acfc4a0c0bc594206f7c89b98ee6fd4490e748e996c45c497679a7"]
  - `2026-07.at_end`: [28337, "b28a6ae39d8d510fb6c018c3b7ce09acace3e2109c5eb55eaa84a0cc76a2c70d"] → [28585, "09f5f7e960b5def2240e19a2c6d38b712e2f2b0183552d444f3cd9257760e6d9"]
  - `2026-07.at_turn`: [28337, "b28a6ae39d8d510fb6c018c3b7ce09acace3e2109c5eb55eaa84a0cc76a2c70d"] → [28585, "09f5f7e960b5def2240e19a2c6d38b712e2f2b0183552d444f3cd9257760e6d9"]
  - `2026-08.at_end`: [28337, "5c58dac585b4d5e9147f6c91a61f33cd1361a5abb3004e21428ba3cdb59108a5"] → [28585, "3b3cec9d9f773dbf2196c4f5e5a6ffcdc9330b81506e20bed9e96833d999ff42"]
  - `2026-08.at_turn`: [28337, "5c58dac585b4d5e9147f6c91a61f33cd1361a5abb3004e21428ba3cdb59108a5"] → [28585, "3b3cec9d9f773dbf2196c4f5e5a6ffcdc9330b81506e20bed9e96833d999ff42"]
  - `2026-09.at_end`: [27424, "8caf01f22af46d229983345766cc39cb15b80c94464b5369c1d6e166d5bb39c7"] → [27664, "350e2f3edac299b8fedef22144ca15585be6f7f6ba95535a2ecc88af0122cafd"]
  - `2026-09.at_turn`: [27424, "8caf01f22af46d229983345766cc39cb15b80c94464b5369c1d6e166d5bb39c7"] → [27664, "350e2f3edac299b8fedef22144ca15585be6f7f6ba95535a2ecc88af0122cafd"]
  - `2026-10.at_end`: [28337, "d41ed735f4c8a7eadcbf6bff35915c7bfd578a642f704600aa01a268637405a7"] → [28585, "50d1ac9154c20581c800cc0dc1b41bf313fcd52b6f509dfe1fdfa1bef66b5af3"]
  - `2026-10.at_turn`: [28337, "d41ed735f4c8a7eadcbf6bff35915c7bfd578a642f704600aa01a268637405a7"] → [28585, "50d1ac9154c20581c800cc0dc1b41bf313fcd52b6f509dfe1fdfa1bef66b5af3"]
  - `2026-11.at_end`: [27424, "6295715336e04d7291c9c3d8520ad140a5dfbbce5f17b934c9bffdaba3111b41"] → [27664, "583b5f35d6de6b8d798fc5d478c5fa72bdd8f869eba58291a6b488e2421a043a"]
  - `2026-11.at_turn`: [27424, "6295715336e04d7291c9c3d8520ad140a5dfbbce5f17b934c9bffdaba3111b41"] → [27664, "583b5f35d6de6b8d798fc5d478c5fa72bdd8f869eba58291a6b488e2421a043a"]
  - `2026-12.at_end`: [28337, "15c89d62f39630c845501c610757c0183575d8b1df1dfed42b1e131621982b8c"] → [28585, "0d6178dc11d259d40d6cc08328fa73afc65931333427f34a6408f62ef75b5164"]
  - `2026-12.at_turn`: [28337, "15c89d62f39630c845501c610757c0183575d8b1df1dfed42b1e131621982b8c"] → [28585, "0d6178dc11d259d40d6cc08328fa73afc65931333427f34a6408f62ef75b5164"]
  - `2026.at_end`: [405277, "5d8a789a4f085e315ed42ca4c4854b759cbc78b9ecb88a25f72b9fc16af7c696"] → [408197, "b645331b3f26174a77e97d79696eae9f07a62c328136a8ce1a927502e638a1ba"]
  - … +1 campos
- `T1/reexecution.json`: IGUAL (`1e6a3ef54998` → `1e6a3ef54998`)
- `T1/state_scenarios.json`: IGUAL (`03654ebb5158` → `03654ebb5158`)
- `T1/temporal_coverage.csv`: ALTERADO (`984bccec5a91` → `420bc0dbc71f`)
  - linhas 396 → 396; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 396 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T1/temporal_summary.json`: ALTERADO (`bb69f1b9b3ba` → `2020ec6870cd`)
  - campos alterados: 21
  - `determinism.RUN_A.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.RUN_A.results_sha256`: "5cfaef4650a5f9ffb470215e66abe7a8cc7de30db1e87e703cb6048627984ca0" → "527dca0463592b18c6fd8e275e353bb11725bb0dbc464a09fb09f987942c0336"
  - `determinism.RUN_A.store_sha256`: "a8dc602c49fb8b97eb7456434c50d95c5754bc2d7189e658e95ff2e4386d9ad6" → "decd0f1745eec227ef65f160ea5ce40dee928121921294a2ad996092578e3bc9"
  - `determinism.RUN_B.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.RUN_B.results_sha256`: "5cfaef4650a5f9ffb470215e66abe7a8cc7de30db1e87e703cb6048627984ca0" → "527dca0463592b18c6fd8e275e353bb11725bb0dbc464a09fb09f987942c0336"
  - `determinism.RUN_B.store_sha256`: "a8dc602c49fb8b97eb7456434c50d95c5754bc2d7189e658e95ff2e4386d9ad6" → "decd0f1745eec227ef65f160ea5ce40dee928121921294a2ad996092578e3bc9"
  - `fingerprint.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `fingerprint.results_sha256`: "5cfaef4650a5f9ffb470215e66abe7a8cc7de30db1e87e703cb6048627984ca0" → "527dca0463592b18c6fd8e275e353bb11725bb0dbc464a09fb09f987942c0336"
  - `fingerprint.store_sha256`: "a8dc602c49fb8b97eb7456434c50d95c5754bc2d7189e658e95ff2e4386d9ad6" → "decd0f1745eec227ef65f160ea5ce40dee928121921294a2ad996092578e3bc9"
  - `per_date.events`: [896] → [904]
  - `per_date.nodes`: [458] → [460]
  - `per_date.targets`: [446] → [448]
  - `performance.mean_first_32`: 0.183696875 → 0.25106875
  - `performance.mean_last_32`: 0.200525 → 0.283975
  - `performance.ratio_last_over_first`: 1.0916081179932973 → 1.131064698414279
  - `performance.store_keys_final`: 439774 → 442942
  - `performance.total_seconds`: 138.0 → 187.6
  - `prefix_invariant.keys_compared`: 35640 → 35896
  - `prefix_invariant.prefix_subset_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `prefix_invariant.recomputed_4a_store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `prefix_invariant.reference_4a_store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
- `T2/identities_by_date.csv`: ALTERADO (`3456dffc121a` → `222f0f814bae`)
  - linhas 62 → 62; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 62 ["2028-01-01", "2028-01-02", "2028-01-03", "2028-01-04", "2028-01-05", "2028-01-06", "2028-01-07", "2028-01-08"]
- `T2/performance_profile.csv`: ALTERADO (`7171801549b9` → `987a04ba8321`)
  - linhas 62 → 62; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 62 ["2028-01-01", "2028-01-02", "2028-01-03", "2028-01-04", "2028-01-05", "2028-01-06", "2028-01-07", "2028-01-08"]
- `T2/period_snapshots.json`: ALTERADO (`09754ad4256d` → `4a9cf69c0daf`)
  - campos alterados: 4
  - `2028-01.at_end`: [28337, "0d64c3279abf478693fb08d51f182fe985e43480eaf97e40fbb76ad9bbc625dd"] → [28585, "70e9e0984134742a15bd91b37c9e079838a4fa6ff033eef986b9b0fa0865742a"]
  - `2028-01.at_turn`: [28337, "0d64c3279abf478693fb08d51f182fe985e43480eaf97e40fbb76ad9bbc625dd"] → [28585, "70e9e0984134742a15bd91b37c9e079838a4fa6ff033eef986b9b0fa0865742a"]
  - `2028-02.at_end`: [26511, "4eff2a31b55345c01c8c1cb23df093e24d86321e4a35661291f1352c41d2f028"] → [26743, "3f59a737159f611ce43f1252f5073f603c33e77e2bc7a5f9c9064621d5804fad"]
  - `2028-02.at_turn`: [26511, "4eff2a31b55345c01c8c1cb23df093e24d86321e4a35661291f1352c41d2f028"] → [26743, "3f59a737159f611ce43f1252f5073f603c33e77e2bc7a5f9c9064621d5804fad"]
- `T2/reexecution.json`: IGUAL (`d4e0ff1076ac` → `d4e0ff1076ac`)
- `T2/temporal_coverage.csv`: ALTERADO (`a17e97b1caca` → `bb9844dcc754`)
  - linhas 62 → 62; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 62 ["2028-01-01", "2028-01-02", "2028-01-03", "2028-01-04", "2028-01-05", "2028-01-06", "2028-01-07", "2028-01-08"]
- `T2/temporal_summary.json`: ALTERADO (`747b98f2ce66` → `8204b3f292f9`)
  - campos alterados: 23
  - `determinism.HASH_SEED_A.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.HASH_SEED_A.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `determinism.HASH_SEED_A.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `determinism.HASH_SEED_B.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.HASH_SEED_B.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `determinism.HASH_SEED_B.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `determinism.RUN_A.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.RUN_A.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `determinism.RUN_A.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `determinism.RUN_B.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.RUN_B.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `determinism.RUN_B.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `fingerprint.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `fingerprint.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `fingerprint.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `per_date.events`: [896] → [904]
  - `per_date.nodes`: [458] → [460]
  - `per_date.targets`: [446] → [448]
  - `performance.mean_first_32`: 0.19457500000000003 → 0.27446875000000004
  - `performance.mean_last_32`: 0.20469062500000007 → 0.2825062499999999
  - `performance.ratio_last_over_first`: 1.0519883078504435 → 1.0292838437891376
  - `performance.store_keys_final`: 68944 → 69440
  - `performance.total_seconds`: 14.8 → 21.1
- `T3/identities_by_date.csv`: ALTERADO (`142fa4009b70` → `f062af312b36`)
  - linhas 792 → 792; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 792 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T3/performance_profile.csv`: ALTERADO (`c8144cb32697` → `838ba0ac0b9f`)
  - linhas 792 → 792; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 792 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T3/period_snapshots.json`: ALTERADO (`d32b854ec5a5` → `0db0d4945a99`)
  - campos alterados: 56
  - `2026-01.at_end`: [28337, "9f70e5d2f355bdb8f57e168a685f153dca6d3cf32b05f77921ec02a897071249"] → [28585, "3cc41b3d16da36d0eef49efd17a1f47b37285deeae213e3bb0580ef2f184e618"]
  - `2026-01.at_turn`: [28337, "9f70e5d2f355bdb8f57e168a685f153dca6d3cf32b05f77921ec02a897071249"] → [28585, "3cc41b3d16da36d0eef49efd17a1f47b37285deeae213e3bb0580ef2f184e618"]
  - `2026-02.at_end`: [25598, "7230d0a6c0debbb3e1b021fa113dcd64df719cc02de25d2d58c76a6124d07560"] → [25822, "f62eebdd28f2f701bc59f4c33e0f0cd8c0c76b78c857b77b3d893a89d82eb7e1"]
  - `2026-02.at_turn`: [25598, "7230d0a6c0debbb3e1b021fa113dcd64df719cc02de25d2d58c76a6124d07560"] → [25822, "f62eebdd28f2f701bc59f4c33e0f0cd8c0c76b78c857b77b3d893a89d82eb7e1"]
  - `2026-03.at_end`: [28337, "3f74671f87b1f28ef3b8cdfa6c568047c7209ea879c61a3e196d13b4d58569d6"] → [28585, "a7d87a168357e55ff5379a49f7fcdff8c18295029b5492b43c4d458db8b64b0b"]
  - `2026-03.at_turn`: [28337, "3f74671f87b1f28ef3b8cdfa6c568047c7209ea879c61a3e196d13b4d58569d6"] → [28585, "a7d87a168357e55ff5379a49f7fcdff8c18295029b5492b43c4d458db8b64b0b"]
  - `2026-04.at_end`: [27424, "1fa35cbdd32a91efdcb9becd9a1eb852b41bfd65490638ac18b47b2baa5d7b63"] → [27664, "5712d8f3d28a0e0418ef540b1c9f53e59370e6187308f9105d9a71127d1598de"]
  - `2026-04.at_turn`: [27424, "1fa35cbdd32a91efdcb9becd9a1eb852b41bfd65490638ac18b47b2baa5d7b63"] → [27664, "5712d8f3d28a0e0418ef540b1c9f53e59370e6187308f9105d9a71127d1598de"]
  - `2026-05.at_end`: [28337, "e80e1c283cc58c7b3682a105cfaf4ac6d9522863aebbc151ac422530ea9a14ab"] → [28585, "77092b153409938febd86843ee9a02f55b6b84a425a5e68e479eb673edf45e2c"]
  - `2026-05.at_turn`: [28337, "e80e1c283cc58c7b3682a105cfaf4ac6d9522863aebbc151ac422530ea9a14ab"] → [28585, "77092b153409938febd86843ee9a02f55b6b84a425a5e68e479eb673edf45e2c"]
  - `2026-06.at_end`: [27424, "281e9b5d9a74206c47c698a25cc0651823db537dbf4f8fb7e802295a3c97fb19"] → [27664, "f6106737f2acfc4a0c0bc594206f7c89b98ee6fd4490e748e996c45c497679a7"]
  - `2026-06.at_turn`: [27424, "281e9b5d9a74206c47c698a25cc0651823db537dbf4f8fb7e802295a3c97fb19"] → [27664, "f6106737f2acfc4a0c0bc594206f7c89b98ee6fd4490e748e996c45c497679a7"]
  - `2026-07.at_end`: [28337, "b28a6ae39d8d510fb6c018c3b7ce09acace3e2109c5eb55eaa84a0cc76a2c70d"] → [28585, "09f5f7e960b5def2240e19a2c6d38b712e2f2b0183552d444f3cd9257760e6d9"]
  - `2026-07.at_turn`: [28337, "b28a6ae39d8d510fb6c018c3b7ce09acace3e2109c5eb55eaa84a0cc76a2c70d"] → [28585, "09f5f7e960b5def2240e19a2c6d38b712e2f2b0183552d444f3cd9257760e6d9"]
  - `2026-08.at_end`: [28337, "5c58dac585b4d5e9147f6c91a61f33cd1361a5abb3004e21428ba3cdb59108a5"] → [28585, "3b3cec9d9f773dbf2196c4f5e5a6ffcdc9330b81506e20bed9e96833d999ff42"]
  - `2026-08.at_turn`: [28337, "5c58dac585b4d5e9147f6c91a61f33cd1361a5abb3004e21428ba3cdb59108a5"] → [28585, "3b3cec9d9f773dbf2196c4f5e5a6ffcdc9330b81506e20bed9e96833d999ff42"]
  - `2026-09.at_end`: [27424, "8caf01f22af46d229983345766cc39cb15b80c94464b5369c1d6e166d5bb39c7"] → [27664, "350e2f3edac299b8fedef22144ca15585be6f7f6ba95535a2ecc88af0122cafd"]
  - `2026-09.at_turn`: [27424, "8caf01f22af46d229983345766cc39cb15b80c94464b5369c1d6e166d5bb39c7"] → [27664, "350e2f3edac299b8fedef22144ca15585be6f7f6ba95535a2ecc88af0122cafd"]
  - `2026-10.at_end`: [28337, "d41ed735f4c8a7eadcbf6bff35915c7bfd578a642f704600aa01a268637405a7"] → [28585, "50d1ac9154c20581c800cc0dc1b41bf313fcd52b6f509dfe1fdfa1bef66b5af3"]
  - `2026-10.at_turn`: [28337, "d41ed735f4c8a7eadcbf6bff35915c7bfd578a642f704600aa01a268637405a7"] → [28585, "50d1ac9154c20581c800cc0dc1b41bf313fcd52b6f509dfe1fdfa1bef66b5af3"]
  - `2026-11.at_end`: [27424, "6295715336e04d7291c9c3d8520ad140a5dfbbce5f17b934c9bffdaba3111b41"] → [27664, "583b5f35d6de6b8d798fc5d478c5fa72bdd8f869eba58291a6b488e2421a043a"]
  - `2026-11.at_turn`: [27424, "6295715336e04d7291c9c3d8520ad140a5dfbbce5f17b934c9bffdaba3111b41"] → [27664, "583b5f35d6de6b8d798fc5d478c5fa72bdd8f869eba58291a6b488e2421a043a"]
  - `2026-12.at_end`: [28337, "15c89d62f39630c845501c610757c0183575d8b1df1dfed42b1e131621982b8c"] → [28585, "0d6178dc11d259d40d6cc08328fa73afc65931333427f34a6408f62ef75b5164"]
  - `2026-12.at_turn`: [28337, "15c89d62f39630c845501c610757c0183575d8b1df1dfed42b1e131621982b8c"] → [28585, "0d6178dc11d259d40d6cc08328fa73afc65931333427f34a6408f62ef75b5164"]
  - `2026.at_end`: [405277, "5d8a789a4f085e315ed42ca4c4854b759cbc78b9ecb88a25f72b9fc16af7c696"] → [408197, "b645331b3f26174a77e97d79696eae9f07a62c328136a8ce1a927502e638a1ba"]
  - … +31 campos
- `T3/reexecution.json`: IGUAL (`e828785207c1` → `e828785207c1`)
- `T3/temporal_coverage.csv`: ALTERADO (`96cc24909fff` → `9036f554f437`)
  - linhas 792 → 792; `date` acrescentados 0 []; removidos 0 []
  - linhas comuns alteradas: 792 ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
- `T3/temporal_summary.json`: ALTERADO (`9b0c8b042ad2` → `a2ab9219fcf1`)
  - campos alterados: 18
  - `determinism.RUN_A.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `determinism.RUN_A.results_sha256`: "47f04d071c10d99aaeb0cb515352ef2a0821338c84de5be7bf0f7010acbf69bc" → "2f3ff39017e3df3cffadfc864fd12bf74bb26329a989191ff8e9b4bf256585e4"
  - `determinism.RUN_A.store_sha256`: "62d1b6509b974edd249ab034a74cbee2f1e086348dde4d3aac68f9aa0c7f4dda" → "83e6944b3af0d21d7c54a893115f64ce60ff3f0f1c00876048cfd5a7fe39bccb"
  - `fingerprint.plan_order`: "ec50717ebce1002208aec7e3327e1fab9d311a43a217e00ba70a0dbf24c11d40" → "96b513d977b6a8f4d509c915b0f3b97e572f9c8306347a9bc795041fbc732c08"
  - `fingerprint.results_sha256`: "47f04d071c10d99aaeb0cb515352ef2a0821338c84de5be7bf0f7010acbf69bc" → "2f3ff39017e3df3cffadfc864fd12bf74bb26329a989191ff8e9b4bf256585e4"
  - `fingerprint.store_sha256`: "62d1b6509b974edd249ab034a74cbee2f1e086348dde4d3aac68f9aa0c7f4dda" → "83e6944b3af0d21d7c54a893115f64ce60ff3f0f1c00876048cfd5a7fe39bccb"
  - `per_date.events`: [896] → [904]
  - `per_date.nodes`: [458] → [460]
  - `per_date.targets`: [446] → [448]
  - `performance.mean_first_32`: 0.21482187499999997 → 0.2710281249999999
  - `performance.mean_last_32`: 0.206203125 → 0.269959375
  - `performance.ratio_last_over_first`: 0.9598795513725035 → 0.9960566823092626
  - `performance.store_keys_final`: 879498 → 885834
  - `performance.total_seconds`: 321.5 → 401.3
  - `prefix_invariant.keys_compared`: 35640 → 35896
  - `prefix_invariant.prefix_subset_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `prefix_invariant.recomputed_4a_store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
  - `prefix_invariant.reference_4a_store_sha256`: "6b3e3c9d0e7cd0527e722e9da3e75183fa658de3175f72623371f127e2eeca10" → "57f5192b6b2a7aedbbefe5843d566f3e449903119a16796fa0d87ae0879849d3"
- expectativas alteradas: 15
  - `T1.per_date.events`: [896] → [904]
  - `T1.per_date.nodes`: [458] → [460]
  - `T1.per_date.targets`: [446] → [448]
  - `T1.results_sha256`: "5cfaef4650a5f9ffb470215e66abe7a8cc7de30db1e87e703cb6048627984ca0" → "527dca0463592b18c6fd8e275e353bb11725bb0dbc464a09fb09f987942c0336"
  - `T1.store_sha256`: "a8dc602c49fb8b97eb7456434c50d95c5754bc2d7189e658e95ff2e4386d9ad6" → "decd0f1745eec227ef65f160ea5ce40dee928121921294a2ad996092578e3bc9"
  - `T2.per_date.events`: [896] → [904]
  - `T2.per_date.nodes`: [458] → [460]
  - `T2.per_date.targets`: [446] → [448]
  - `T2.results_sha256`: "f28b5ca85546c690a157af11191db84ee3f1f8389e308f63fac9c69da27fef3f" → "0432da54ed2fdcd1a531623b63ac4384e8ba88f46dc427696863c6a65cab6ed3"
  - `T2.store_sha256`: "61a8242274681766def22d55a771b116f2ee19a97f2a64af5e1f46825bca25cb" → "17504b5b23de2ceb4a5994b671b90b5ded523b1eaf32b99920caa0481421c44b"
  - `T3.per_date.events`: [896] → [904]
  - `T3.per_date.nodes`: [458] → [460]
  - `T3.per_date.targets`: [446] → [448]
  - `T3.results_sha256`: "47f04d071c10d99aaeb0cb515352ef2a0821338c84de5be7bf0f7010acbf69bc" → "2f3ff39017e3df3cffadfc864fd12bf74bb26329a989191ff8e9b4bf256585e4"
  - `T3.store_sha256`: "62d1b6509b974edd249ab034a74cbee2f1e086348dde4d3aac68f9aa0c7f4dda" → "83e6944b3af0d21d7c54a893115f64ce60ff3f0f1c00876048cfd5a7fe39bccb"

## 3. Conjuntos herdados (H/E)

Não regenerados: `stage3_4b_differential`, `stage3_4d_mutation`, `stage4a_oracle`, `stage4a_mutation`, `stage4a_closure`, `stage4b_oracle`, `stage4b_mutation`, `stage4b_closure` (iguais a B0).

