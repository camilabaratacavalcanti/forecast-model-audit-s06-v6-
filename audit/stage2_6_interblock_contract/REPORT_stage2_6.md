# Etapa 2.6 — Contrato interbloco declarado em `fonte`

Branch `feature/area-41-block`. Ponto de partida: `a63a214` (fechamento da 2.5B, gate READY_FOR_IMPLEMENTATION),
árvore limpa, **1409 passed**.

| commit | conteúdo |
|---|---|
| `3c75a90` | implementação, testes, workbooks oficiais, seeds regenerados |
| commit seguinte (este relatório) | evidências em `audit/stage2_6_interblock_contract/` |

## 1. Resultado em uma tabela

| medida | por definição (vínculo) | por linha do workbook |
|---|---:|---:|
| `fonte` preenchida | 31 | 34 |
| vínculos válidos (VALID) | **12** | 12 |
| rejeitados | **19** | 22 |
| — SOURCE_NOT_FOUND | 16 | 19 |
| — CONTRACT_MISMATCH | 3 | 3 |
| — AMBIGUOUS / INSTANCE_MISMATCH / CYCLE | 0 / 0 / 0 | 0 / 0 / 0 |

Um vínculo é uma definição do modelo canônico. `area_41.hes` ocupa as linhas 25–28 (L4..L7), mas é uma única
definição: por isso há 34 linhas e 31 vínculos.

Erros emitidos: 21 no total. São 18 `INTERBLOCK_SOURCE_NOT_FOUND` e 3 `INTERBLOCK_CONTRACT_MISMATCH`. Um vínculo pode ter
mais de um erro: `production.fator_mpsa` e `production.fator_mrn` têm dois cada (contexto inválido e bloco fonte não
carregado).

Gate: **READY_FOR_DECISION** (justificativa na §9; linha oficial ao final).

## 2. Workbooks oficiais usados

O texto do pedido lista area_41 v8, energy v5, max_ht v9, production v8 e yield v10. Os anexos da etapa são versões
posteriores desses mesmos arquivos. Comparei os anexos célula a célula com essas versões: **só células da coluna
`fonte` mudam**.
- O prefixo `bloco ` foi removido em todas elas.
- `maintenance_plan` virou `maintenance` (production).
- `área 04_13` foi normalizada para `area_04_13` (energy).

Nas versões listadas no texto, toda `fonte` é `bloco X`. Pela convenção desta etapa (a `fonte` contém apenas o nome do
bloco), nenhuma dessas células resolveria. Por isso usei os anexos, que são a aplicação dessa convenção pelo dono dos
workbooks. Nenhum workbook foi alterado. Os cinco foram copiados byte a byte para `data/workbooks/` e fixados em
`tools/workbook_seed/blocks.py`:

| bloco | versão | SHA-256 |
|---|---|---|
| area_41 | v9 | `36bbae135285ad9b3b88d21ef94e2bc9c92f2ef74736412b66bc62de4dcf3f50` |
| energy | v6 | `cfc46031fc2f3f375b87ebbba58676d23ad92f3ee43fb81b353fe5a8247e1df8` |
| max_ht | v10 | `3e40aab12ec0ec07918c5e358145b09f138663f635ca9e7fc0990d1b765b683b` |
| production | v9 | `3e3024e564ee6f18b82e9771957e61f4940becd1e80db5705143123377956a28` |
| yield | v11 | `639e8b980f19bc20429cf9763157ac1828d9067bdbabea3bf3db0badbc2df931` |

As cópias anteriores em `data/workbooks/` foram removidas do repositório com `git rm` e continuam no histórico:
A41 v8, energy v5, MaxHT v9, production v6 e yield v9. As cópias de production v7/v8 e yield v10 que estão em
`audit/stage2_5*/evidence/inputs/` não foram tocadas.

Consequência: os scripts das etapas 2.4–2.5B resolvem parte dos insumos por `BLOCKS[...].workbook_path`. Eles
reproduzem os próprios resultados nos commits em que foram gravados (`6b135e9`, `e6351a3`, `a63a214`), não em HEAD.
Nenhum artefato dessas etapas foi modificado.

## 3. Contrato implementado

Fluxo: `workbook.fonte` → `source_block` canônico (`CanonicalEntity.source_block`) → validação interbloco
(`tools/workbook_seed/interblock.py`) → seed/manifesto.

1. **`fonte` é intenção explícita de vínculo.**
   - O `source_block` é o texto da célula: sem strip, sem remover prefixo, sem alias.
   - `bloco production`, `production ` e `Production` não resolvem: dão `INTERBLOCK_SOURCE_NOT_FOUND` (teste 03).
   - `source_reference` não participa da resolução (teste 08).
2. **Resolução.**
   - O produtor é procurado no bloco indicado, por name + frequency + scope_type + scope_value.
   - A chave é avaliada por instância concreta, com a mesma regra da identidade local (`check_identity`).
   - Cada instância do consumidor precisa existir, com o mesmo scope_value, numa única definição do produtor.
   - Não há fallback temporal nem espacial (teste 03c), nem substituição de L3 por L1 (teste 07).
   - Instâncias do consumidor divididas entre definições distintas do produtor são tratadas como AMBIGUOUS
     (teste 07c).
3. **Contexto do consumidor.** Só uma variável sem expressão própria pode declarar `fonte`. São contexto inválido
   (`INTERBLOCK_CONTRACT_MISMATCH`, dimensão `consumer_context` ou `source_block`, teste 14):
   - linha com expressão: dois produtores para a mesma definição;
   - parâmetro: tem valor próprio;
   - `fonte` igual ao próprio bloco.
4. **Contrato.** Cada dimensão divergente vira um erro próprio:
   - dimensões comparadas: kind (variable/parameter), unit, value_type, allowed_values, declared_result_states e
     instâncias;
   - unidade é comparada como texto exato e nunca convertida (testes 05 e 16).
5. **Ciclos.**
   - O grafo une os vínculos interbloco às dependências intrabloco: referências de equações e origem das agregações,
     tiradas dos seeds.
   - A detecção usa SCC de Tarjan sobre nós ordenados, então o resultado independe da ordem de carga.
   - O ciclo é reportado inteiro, em forma canônica (testes 10 e 10b).
6. **Cadeias.** A validação é feita salto a salto. `chain_status` é VALID ou `BROKEN_AT:<bloco.nome>` (testes 11 e 11b).
7. **Códigos de erro.** `INTERBLOCK_SOURCE_NOT_FOUND`, `INTERBLOCK_SOURCE_AMBIGUOUS`, `INTERBLOCK_CONTRACT_MISMATCH` e
   `INTERBLOCK_CYCLE`.
   - Toda mensagem traz bloco consumidor, linha(s), name, bloco fonte, dimensão divergente, valor do consumidor e valor
     do produtor.
   - A classe INSTANCE_MISMATCH usa o código `INTERBLOCK_CONTRACT_MISMATCH` com a dimensão `instances`.
8. **Nada é corrigido.**
   - Um vínculo inválido não é emitido como vínculo: vai para `rejected` com seus erros.
   - `python -m tools.workbook_seed` grava os seeds e **termina com código 1** enquanto houver vínculo rejeitado.
   - `require_valid()` levanta `InterblockContractError`.
   - Não há warning em lugar de erro.
9. **Representação canônica.**
   - Arquivo: `data/seed/interblock_links.json`.
   - `links` traz, por vínculo válido: `consumer_block`, `consumer_definition`, `consumer_frequency`,
     `consumer_scope`, `source_block`, `source_definition`, `source_frequency`, `source_scope`, `instances` e
     `consumer_rows`.
   - `rejected` traz os erros de cada vínculo rejeitado.
   - O manifesto de cada bloco registra `source_block` na entidade.
   - O `source_block` não entra em `variables.json` nem em `parameters.json` (é interno).
10. **Fora desta etapa.** Nenhuma propagação de valores em runtime (Etapa 3). A identidade continua local ao bloco:
    consumidor e produtor mantêm definições e IDs próprios (teste 09).

## 4. Vínculos válidos (12)

| consumidor (linha) | produtor | unidade | escopo | cadeia |
|---|---|---|---|---|
| area_41.lth (9) | yield.lth — entrada, `fonte=production` | m³/h | diário linha/L1_L7 | area_41.lth → yield.lth → production.lth ✔ |
| energy.producao (3) | production.producao | t/d | diário linha/L1_L7 | ✔ |
| energy.pick_up (7) | production.pick_up | g/l | diário linha/L1_L7 | ✔ |
| energy.pick_up_total (8) | production.pick_up_total | g/l | diário linha_grupo/L1_L7 | ✔ |
| energy.pick_up_total (9) | production.pick_up_total | g/l | mensal linha_grupo/L1_L7 | ✔ |
| energy.lth (10) | production.lth | m³/h | diário linha/L1_L7 | ✔ |
| energy.lth_total (11) | production.lth_total | m³/h | diário linha_grupo/L1_L7 | ✔ |
| energy.lth_total (12) | production.lth_total | m³/h | mensal linha_grupo/L1_L7 | ✔ |
| max_ht.lth (68) | production.lth | m³/h | diário linha/L1_L7 | ✔ |
| max_ht.producao (98) | production.producao | t/d | diário linha/L1_L7 | ✔ |
| production.yield (87) | yield.yield | g/l | diário linha/L1_L7 | ✔ |
| yield.lth (32) | production.lth | m³/h | diário linha/L1_L7 | ✔ |

Em todos eles, unit, value_type, allowed_values, declared_result_states e instâncias são iguais entre produtor e
consumidor. O detalhe de cada comparação está em `contract_validation.csv`.

## 5. Inconsistências (19 vínculos, 22 linhas)

### 5.1 CONTRACT_MISMATCH — `energy.lth_meta` ← production (linha 13)

| | consumidor energy | produtor production |
|---|---|---|
| natureza | **variable** (entrada) | **parameter** `PARAM12003` (valor fixo por linha, version) |
| frequência / escopo | anual linha/L1_L7 | anual linha/L1_L7 |
| unit / value_type | `-` / numerico | `-` / numerico |

A resolução encontra o produtor, e todas as dimensões coincidem, exceto a natureza. A infraestrutura não converte
parâmetro em variável. Houve relação interrompida e registrada: a incompatibilidade prevista no pedido continua no
workbook.

### 5.2 CONTRACT_MISMATCH — `production.fator_mpsa` (linha 30) e `production.fator_mrn` (linha 32) ← forecast

- As duas são `variable / equation`, `variable_type=calculado`, com expressão própria:
  - `fator_mpsa_kg_t / 1000`;
  - `fator_mrn_kg_t / 1000`.
- Ao mesmo tempo declaram `fonte=forecast`.
- Pela regra desta etapa, toda `fonte` é intenção de vínculo, então a definição tem dois produtores (erro
  `consumer_context`).
- O bloco `forecast` também não tem workbook neste build, o que gera o segundo erro, SOURCE_NOT_FOUND.
- As entradas de que elas dependem, `fator_mpsa_kg_t` (31) e `fator_mrn_kg_t` (33), já declaram `fonte=forecast`.

### 5.3 SOURCE_NOT_FOUND — bloco fonte sem workbook neste build (16 vínculos + os 2 acima = 18 definições, 21 linhas)

Todos os valores de `fonte` pertencem à taxonomia oficial (`VARIABLE_ID_RANGES`). Nenhum está fora dela.

| bloco fonte | consumidores |
|---|---|
| maintenance | area_41.hes (25–28); production.reducao_lth_{calcinacao,clarificacao,digestao,precipitacao} (79–82), production.tempo_{calcinacao,clarificacao,digestao,precipitacao} (83–86) |
| temperature_lp | energy.temperatura_lp diário (14) e mensal (15); energy.temperatura_lp_media (16) |
| area_04_13 | energy.evaporado_total_evaporacao (37, `entrada_externa`) |
| alumina | max_ht.alimentação_evap (5) |
| forecast | production.fator_mpsa_kg_t (31), production.fator_mrn_kg_t (33); + fator_mpsa (30), fator_mrn (32) de 5.2 |

Esses vínculos não são validáveis: o produtor não existe no conjunto carregado. Pelo contrato, “fonte inexistente →
erro”, e eles ficam como erro. Não foram rebaixados a “externo” nem a aviso, porque isso seria decidir o contrato em
nome do dono (ver §9).

### 5.4 Ciclos

- Nenhum ciclo no nível de definição: o grafo une os vínculos às equações e agregações dos cinco blocos.
- No nível de bloco há dependência mútua production ↔ yield:
  - production.yield ← yield.yield;
  - yield.lth ← production.lth.
- Nenhuma cadeia de definições fecha, então a dependência mútua não é um `INTERBLOCK_CYCLE`. Ela está registrada em
  `interblock_graph.csv`.

## 6. Arquivos alterados (commit `3c75a90`)

| arquivo | alteração |
|---|---|
| `tools/workbook_seed/interblock.py` | **novo**: resolução, contrato, contexto, ciclos, cadeias, registros canônicos |
| `tools/workbook_seed/blocks.py` | fixa os cinco novos workbooks (nome, versão, SHA); `build_all`, `BuildAllResult`, `write_interblock_seed`, `read_interblock_seed`, `INTERBLOCK_SEED` |
| `tools/workbook_seed/__main__.py` | builder comum constrói os cinco blocos, valida o contrato interbloco, grava `interblock_links.json`, sai com 1 se houver rejeição |
| `tools/workbook_seed/canonical.py` | propriedade `CanonicalEntity.source_block` (= fonte, sem transformação) |
| `tools/workbook_seed/seeds.py` | manifesto: `source_block` na entidade que declara fonte |
| `data/workbooks/` | + A41 v9, energy v6, MaxHT v10, production v9, yield v11; − A41 v8, energy v5, MaxHT v9, production v6, yield v9 |
| `data/seed/*/{variables,parameters,equations,manifest}.json` | regenerados (ver abaixo) |
| `data/seed/interblock_links.json` | **novo**: 12 vínculos válidos + 19 rejeitados com erros |
| `tests/test_stage2_6_interblock_contract.py` | **novo**: 32 testes (01–17 e variantes, build) |
| `tests/test_production_v1.py`, `tests/test_stage2_4_workbook_contract.py`, `tests/test_yield_v4_l1l7_and_aggregation_rules.py` | expectativas legadas (§7) |

Mudanças de conteúdo nos seeds, além da proveniência (nome do workbook em `source_reference` e `file_name`/`sha256`
no manifesto):

- `production.desaguamento_oee`: passa a referenciar `consumo_mpsa_grupo` anual linha_grupo (`VAR12015`) em vez de
  `VAR12011`. A pendência `R2-A019-UNREACHABLE` saiu do manifesto. É o efeito de production v7+ (R2-01 resolvido na
  fonte).
- `yield`: 5 unidades `%` → `-` (D25-02, yield v10+). A pendência `D24-12` (`ltp_tc`) saiu do manifesto (célula
  vazia desde yield v10).
- Os manifestos ganham `source_block` nas 31 entidades com `fonte`.
- Nenhum ID de variável, parâmetro, equação ou regra mudou de identidade.

Não alterados: `app/`, os workbooks (apenas copiados), nomes, unidades, e as regras D24-11, D24-12 e A019. Não há
alias, conversão, fusão de identidade nem restauração de IDs históricos.

## 7. LEGACY_TEST_EXPECTATION

Com os novos workbooks, 5 testes falharam por fixarem o estado anterior. São os mesmos pontos listados na 2.5B §12.
Cada um foi atualizado e documentado no próprio docstring; nenhum foi removido.

| teste | antes | agora |
|---|---|---|
| `test_production_v1.py::test_desaguamento_oee_reference_to_consumo_mpsa_is_a_recorded_pending_decision` | exigia a pendência R2-A019-UNREACHABLE | renomeado para `test_desaguamento_oee_references_annual_consumo_mpsa_grupo`: exige a referência a `consumo_mpsa_grupo` anual e nenhuma pendência |
| `test_production_v1.py::test_desaguamento_oee_formula_produces_expected_percentage` | valor em `consumo_mpsa` diário | valor em `consumo_mpsa_grupo` anual linha_grupo |
| `test_production_v1.py::test_desaguamento_oee_resolves_cross_scope_reference_via_decision_e` | idem | idem |
| `test_stage2_4_workbook_contract.py::test_t24_16_value_on_a_variable_row_is_recorded_not_dropped` | exigia D24-12 pendente para `ltp_tc` | exige nenhuma pendência D24-12 em nenhum bloco; `value` continua fora do domínio |
| `test_yield_v4_l1l7_and_aggregation_rules.py::test_12_...` | `source_reference` = yield v9 | yield v11 |

Mantidos sem alteração, com o motivo registrado:

- `test_production_v1.py::test_production_integration_chain_inputs_to_producao_planta`: continua excluindo
  `desaguamento_oee` e cita R2-01 no docstring. A exclusão ainda é válida e o teste passa. Incluí-lo seria ampliar
  cobertura, não corrigir uma expectativa.
- Os 27 avisos D24-11 do validador (repetição de nome entre blocos): a 2.5B indicou relatório informativo. Mudar isso
  é outra regra, fora desta etapa.
- T24-16 não passou a exigir rejeição de value/version numa variável. É a regra D24-12, não relacionada a `fonte`, e o
  pedido proíbe alterar regras não relacionadas.

## 8. Testes

| # | exigido | teste(s) |
|---|---|---|
| 1 | fonte vazia → nenhum vínculo | `test_01` |
| 2 | fonte válida → vínculo | `test_02` (registro canônico completo) |
| 3 | fonte inexistente → erro | `test_03` (4 variantes: bloco sem workbook, `bloco production`, espaço, maiúscula), `test_03b`, `test_03c` (sem fallback temporal/espacial) |
| 4 | ambíguo → erro | `test_04`, `test_07c` |
| 5 | unidade → erro | `test_05` |
| 6 | value_type → erro | `test_06`, `test_06b` (allowed_values, declared_result_states), `test_06c` (parameter→variable) |
| 7 | instância ausente → erro | `test_07`, `test_07b` |
| 8 | source_reference sem influência | `test_08` |
| 9 | identidade local preservada | `test_09` |
| 10 | ciclo → erro | `test_10` (A→B→C→A, independente da ordem), `test_10b` (ciclo via dependências intrabloco) |
| 11 | cadeia A→B→C | `test_11`, `test_11b` (cadeia quebrada) |
| 12 | mesmo nome sem fonte → nenhum vínculo | `test_12` |
| 13 | trocar fonte troca o produtor | `test_13` |
| 14 | fonte em contexto inválido → erro | `test_14` (expressão própria, parâmetro, próprio bloco) |
| 15 | todos os vínculos reais classificados | `test_15` (34 linhas lidas do workbook = 34 classificadas; 12/16/3; lth_meta; cadeia area_41) |
| 16 | nenhum vínculo por conversão de unidade | `test_16` |
| 17 | sem dependência de IDs históricos | `test_17` (IDs renumerados e ordem invertida → mesma classificação) |
| — | build | `test_interblock_seed_is_the_builder_output`, `test_manifest_records_canonical_source_block`, `test_source_block_is_not_a_seed_or_domain_field`, `test_builder_main_fails_while_links_are_rejected` |

Resultados:
- Suíte completa: **1441 passed**, 0 failed. O baseline era 1409; entram 32 testes novos, e os 5 legados foram
  atualizados.
- Detalhe: `evidence/test_output.txt`.

## 9. Gate

Não é PASS: há 19 vínculos declarados que não satisfazem o contrato, e nenhum foi rebaixado a aviso.

Também não é BLOCKED: a implementação da etapa está completa e testada, e a infraestrutura detecta e rejeita
exatamente essas relações. O que falta é uma decisão ou correção do dono dos workbooks, em três pontos que a
infraestrutura não pode resolver sozinha:

1. **D26-01 — produtores fora do build (18 definições, 21 linhas).** O vínculo para `maintenance`, `temperature_lp`,
   `area_04_13`, `alumina` e `forecast` deve:
   - (a) exigir os workbooks desses blocos no conjunto oficial (os vínculos passam a ser validados); ou
   - (b) ter um estado contratual explícito, distinto de VALID, para produtor ainda não carregado.

   Hoje é erro (`INTERBLOCK_SOURCE_NOT_FOUND`).
2. **D26-02 — `energy.lth_meta` ← `production.lth_meta` (parameter).** Corrigir o workbook (mesma natureza nos dois
   lados) ou aprovar explicitamente o vínculo parâmetro→variável. Hoje é `INTERBLOCK_CONTRACT_MISMATCH` (kind).
3. **D26-03 — `production.fator_mpsa` / `fator_mrn` calculadas com `fonte=forecast`.** Retirar a `fonte` (o valor é
   calculado localmente) ou retirar a expressão (o valor vem de forecast). Hoje é `INTERBLOCK_CONTRACT_MISMATCH`
   (`consumer_context`).

Com essas três decisões aplicadas aos workbooks, o mesmo builder e a mesma suíte reclassificam tudo sem alteração de
código. `python -m tools.workbook_seed` só termina com 0 quando não resta vínculo rejeitado.

## 10. Evidências

| arquivo | conteúdo |
|---|---|
| `interblock_links.csv` | 34 linhas com `fonte`: colunas exigidas + definição, natureza, taxonomia, cadeia, códigos, dimensões, verificação independente |
| `contract_validation.csv` | uma linha por vínculo × dimensão (kind, unit, value_type, allowed_values, declared_result_states, instances) e por erro de contexto/resolução |
| `interblock_graph.csv` | arestas por definição e por bloco (carregado / não carregado, dependência mútua) |
| `evidence/analysis_stage2_6.py` | script reprodutível; reclassifica as 34 linhas a partir do openpyxl cru, com regras reescritas, e compara com o builder (0 divergências) |
| `evidence/workbook_sha256.txt` | SHA-256 dos cinco workbooks |
| `evidence/validation_results.json` | contagens, erros por código/classe, ciclos, divergências, coerência seed × builder |
| `evidence/test_output.txt` | testes 2.6 (verbose), suíte completa, código de saída do builder |

Reproduzir: `python audit/stage2_6_interblock_contract/evidence/analysis_stage2_6.py` (somente leitura).

## 11. Push

Os dois commits (`3c75a90` e o commit de evidências que contém este relatório) são enviados com
`git push -u origin feature/area-41-block`. O que foi alterado está descrito nas §§ 2, 6 e 7. Nenhum pull request foi
criado.

STAGE_2.6_GATE: READY_FOR_DECISION
