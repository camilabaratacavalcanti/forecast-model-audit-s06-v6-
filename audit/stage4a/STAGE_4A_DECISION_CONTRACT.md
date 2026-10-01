# Stage 4A — Contrato e auditoria: area_41 no universo integrado

| campo | valor |
|---|---|
| etapa | 4A.1 — auditoria e contrato (sem código de produção) |
| baseline | `main` = `d2847ab36933668bf4a1299b3ffe058827a82037` (merge fast-forward da `feature/area-41-block`) |
| branch | `feature/stage-4a-area41-integration` |
| rótulo das execuções | `REAL_DERIVED_TEST_RESULT` (fixture REAL_DERIVED, `TEST_FIXTURE_ONLY`) |
| superfície de produção | congelada: `app/`, `data/`, `tools/` não são alterados |
| Stage 3 | **CLOSED**; nada das 2.x–3.4 é editado. A 3.4C é importada, não modificada |

Toda cardinalidade deste contrato foi:
1. **derivada empiricamente** por `audit/stage4a/derive_4a.py` (planner, engine e seeds);
2. **confirmada por recálculo independente** em `audit/stage4a/independent_count.py`.

O recálculo roda com `python -I`, não importa `app/`, `tools/` nem os harnesses da Stage 3 (o próprio script verifica `sys.modules`), e reescreve as regras de escopo, fecho e status do plano a partir dos contratos 3.1/3.2. Os dois caminhos foram confrontados em **40 campos**, com 0 divergências.

As expectativas congeladas estão em `audit/stage4a/contract_expectations.json`. A evidência fica em `audit/stage4a/evidence/`:
- `contract_audit.json`
- `obs_register.csv`
- `hes_decision_matrix.csv`
- `baseline_phase0.json`

---

## 0. Baseline (Fase 0)

Resultados em `evidence/baseline_phase0.json`, com o rótulo `REAL_DERIVED_TEST_RESULT`.

| verificação | esperado `[ref]` | observado |
|---|---|---|
| `main` contém `feature/area-41-block` | OK | **OK** (`merge-base --is-ancestor`) |
| hashes `f3b6588`, `7877551`, `8095011` | presentes | **HASHES_OK** (os três são ancestrais da `main`) |
| HEAD | `d2847ab` (fast-forward) | `d2847ab` (fast-forward; não há merge commit) |
| árvore | limpa | limpa |
| `python -m pytest -q` | 1921 passed | **1921 passed**, 0 failed, 0 skipped (5 min 09 s) |
| diferencial 3.4B | PASS | PASS, 0 diferenças, 4722 casos |
| integrado 3.4C | PASS | PASS, 421 alvos, 427 nós (218/197/12), 51 entradas |
| `reconcile.py` | PASS | PASS, 0 problemas |
| `blackbox_audit.py` (`-I`) | PASS | PASS |
| `python -m tools.workbook_seed` | árvore limpa | rc=0, `git status --porcelain` vazio |

---

## 1. Universo integrado de 5 blocos (§3.1)

### 1.1 Fixture

O fixture é o mesmo da 3.4C (`audit/stage3_4/integrated/fixture.py`, importado sem alteração):
- catálogo oficial dos 5 blocos carregado dos seeds;
- registro de vínculos reconstruído **em memória** com `pending = []` (só no fixture).

Os consumidores dos 16 vínculos pendentes viram entradas livres. Nada é gravado em seeds ou vínculos, e nenhum bloco ausente é carregado.

### 1.2 Cardinalidades

Cada linha é derivada (planner/engine) e recalculada de forma independente (`python -I`), com resultado idêntico nos dois caminhos.

| grandeza | 4 blocos (3.4C) | area_41 isolado | **5 blocos (4A)** |
|---|---|---|---|
| alvos | 421 | 25 | **446** (yield 219, max_ht 109, production 50, energy 43, area_41 25) |
| nós do plano | 427 | 33 | **458** |
| EQUATION | 218 | 21 (20 do area_41 + EQ12012) | **238** |
| AGGREGATION | 197 | 10 | **207** |
| TRANSFER | 12 | 2 (VAR16007, VAR11031) | **13** |
| instâncias de equação | 392 | 27 | **412** |
| instâncias de agregação | 395 | 22 | **417** |
| instâncias de transferência por data | 60 | 14 | **67** |
| eventos por data | 847 | 63 | **896** (= 412 + 417 + 67; observado numa execução real: 896) |
| entradas livres (`required_inputs`) | 51 | 21 | **62** (51 + 11 do area_41) |
| `pending_blockers` | 0 | 0 | **0** |

Nós do area_41 no plano de 5 blocos: 20 EQUATION, 10 AGGREGATION e 1 TRANSFER (`VAR16007`).

### 1.3 Por que os nós são a união, não a soma

Planejar só os 25 alvos do area_41 puxa dois nós a montante que **já estão** no plano de 4 blocos:

| nó compartilhado | bloco | por quê |
|---|---|---|
| `EQUATION:EQ12012` | production | produz `VAR12031`, origem da transferência para o yield |
| `TRANSFER:VAR11031` | yield | `lth` do yield, origem do vínculo `yield.VAR11031 → area_41.VAR16007` |

A conta é: **nós(5) = |nós(4) ∪ nós(area_41)| = 427 + 33 − 2 = 458**. Isso foi verificado nos dois caminhos (`union_equals_5 = true`).

O planner deduplica esses nós. A ordem relativa dos 427 nós da 3.4C é preservada no plano de 5 blocos (`plan4_relative_order_preserved_in_5 = true`).

### 1.4 Vínculos usados

- Carregados: **13**.
- Usados no plano de 5 blocos: **13**. O vínculo `yield.VAR11031 → area_41.VAR16007` (`lth`, 7 instâncias L1..L7, diário) **passa a ser usado**. Na 3.4C não era usado (12/13).
- Eventos de transferência por data: **67** (60 da 3.4C + 7 do `VAR16007`).

### 1.5 Plano oficial (sem fixture): inalterado

| verificação | esperado `[ref]` | observado |
|---|---|---|
| alvos oficiais | 446 | 446 |
| plano por alvo x `plan_evidence.csv` (3.2) | idêntico | **idêntico** nas 446 linhas (status, blocos pendentes, nº de passos). Verificado pelo planner e pelo recálculo independente |
| area_41 | 3 OK + 22 `INTERBLOCK_SOURCE_NOT_LOADED` (maintenance) | **3 OK** (`retirada_cond_corr_ltp` VAR16004/5/6) + **22** `INTERBLOCK_SOURCE_NOT_LOADED`, bloco pendente `maintenance` |
| vínculos `PENDING_LOAD` | 16 | **16** por bloco-fonte: maintenance 9, temperature_lp 3, forecast 2, area_04_13 1, alumina 1. Por consumidor: production 10, energy 4, max_ht 1, area_41 1 (`hes`) |
| `interblock_links.json` sha256 | inalterado | `8dc6b7c8927393096dfe75f04bc37cf81848e9d5f485f1c83945fd5d520cd700` = sha256 em `d2847ab` |

**Por que 22 alvos do area_41 estão bloqueados por `maintenance`.** No plano oficial, o `lth` (VAR16007) depende, via `yield.VAR11031`, da cadeia de production. Essa cadeia consome os vínculos pendentes de `maintenance`. O `hes` (VAR16021) é ele próprio um vínculo pendente de `maintenance`.

---

## 2. Invariante de não-regressão (§3.2)

**Invariante:** incluir o area_41 no grafo não muda valor, state, detail nem identidade temporal de nenhuma chave de resultado dos 4 blocos anteriores, em nenhuma das 32 datas (2026-01-01..2026-02-01).

### 2.1 Protocolo de entradas

O fixture da 3.4C atribui a cada entrada livre o valor `input_value(i, k, …)`, onde `i` é a posição da variável em `plan.required_inputs`.

No plano de 5 blocos, as 11 entradas do area_41 entram **intercaladas** nessa tupla (posições 44..54). Com o índice ingênuo, 7 entradas dos 4 blocos mudariam de índice e de valor. Isso alteraria os 421 alvos por um **artefato do fixture**, e não por regressão do engine.

Regra adotada (`audit/stage4a/common.py`):
- cada entrada dos 4 blocos mantém o índice da 3.4C (verificado: `plan4_inputs_keep_3_4c_index = true`);
- as 11 entradas do area_41 recebem os índices 51..61, na ordem do plano de 5 blocos.

### 2.2 Método

1. Executar o grafo de 5 blocos nas 32 datas, no mesmo contexto (como a 3.4C).
2. Restringir o store final às chaves cuja entidade **não** é do area_41.
3. Calcular o hash com a **mesma função** da 3.4C:
   ```text
   sha256(json.dumps(sorted([list(chave), [tipo, repr(valor), state, detail]]), sort_keys=True))
   ```
   A chave é `(entity_id, scope_type, scope_value, period_id, window_end)`.
4. Exigir que esse hash seja **igual** ao `store_sha256` versionado da 3.4C (`audit/stage3_4/integrated/evidence/integrated_summary.json → determinism.RUN_A.store_sha256`).
5. Confirmar chave a chave contra uma execução dos 4 blocos isolados, no mesmo processo:
   - mesmas chaves;
   - mesmos `[tipo, repr, state, detail]`;
   - mesmos `window_end`.
6. Comparar também os `final_results_2026-02-01` de `targets.csv` da 3.4C, alvo a alvo.

Sondagem desta auditoria (`REAL_DERIVED_TEST_RESULT`):
- hash do subconjunto não-area_41 = `619b4abd…e9730c` = `store_sha256` da 3.4C;
- store de 5 blocos com 35 640 chaves, das quais 1 900 são do area_41.

A prova completa (32 datas, chave a chave e por alvo) é entregue pelo harness da Fase 2 (`non_regression_421.json`).

---

## 3. Auditoria específica do area_41 (§3.3)

### 3.1 Coluna `OBS` do workbook A41 v9

Lida diretamente com `openpyxl`, aba `A41`, coluna R. São **26 linhas com observação** e 9 textos distintos. Registro completo em `evidence/obs_register.csv`. Classificação:
- `REQUIRES_FOLLOWUP`: confirmação do cliente; **não bloqueia** (§10.1);
- `DOCUMENTATION_ONLY`: rastreabilidade ou descrição.

| linhas | variável / parâmetro | observação (resumo fiel) | classificação |
|---|---|---|---|
| 3–5 | `vazao_ltp` (VAR16001/2/3) | valor de julho/2026 = 1320. Verificar: (i) por que não usar o valor do bloco yield; (ii) por que não usar LTP = 1067; (iii) valores de LTH = 1100 e 970 não usados na planilha | REQUIRES_FOLLOWUP |
| 9 | `lth` (VAR16007) | origem `Yield 2026!E4:OB4`, `E20:OB20`, `E36:OB36` | DOCUMENTATION_ONLY |
| 13–15 | `fator_retirada_cond_corr_lth` (VAR16011/2/3) | valor de julho/2026 = 1.1; existe o valor 1.15 na planilha não utilizado | REQUIRES_FOLLOWUP |
| 19–21 | `valor_retirada` (VAR16017 L1/L2/L3) | julho/2026 = 47 / 47 / 48; verificar o significado e ajustar a nomenclatura | REQUIRES_FOLLOWUP |
| 25–28 | `hes` (VAR16021 L4..L7) | recebem strings como "Normal", "LC", "Overhaul/Parada" | DOCUMENTATION_ONLY |
| 29–31 | `desconto_retirada_41c` (VAR16022/23), `desconto_retirada_41d` (VAR16024) | verificar se pode vir do Plano de Manutenção | REQUIRES_FOLLOWUP |
| 32–38 | parâmetros `retirada_meta_41a/41b/41x/41c/41d`, `retirada_performance_41c`, `retirada_manobra_linha_41a` | não utilizados na planilha; avaliar a necessidade de inseri-los | REQUIRES_FOLLOWUP |
| 39, 42 | `retirada_condensado_grupo` diário L4_L5 (VAR16025) e L6_L7 (VAR16028) | referências de 41c/41d inconsistentes nos ramos `1 By pass` e `1 By pass e LC` (L4_L5 usa 41c/41d; L6_L7 só 41c); confirmar o desconto por grupo e condição; **a equação precisará ser atualizada após o bloco maintenance** | REQUIRES_FOLLOWUP |

Totais: 21 linhas `REQUIRES_FOLLOWUP` e 5 `DOCUMENTATION_ONLY`. Nenhuma é bloqueio.

### 3.2 Condicionais de `retirada_condensado_grupo` L4_L5 (EQ16011 → VAR16025) e L6_L7 (EQ16012 → VAR16028)

A árvore de decisão foi mapeada nas **25 combinações de `hes`** por grupo, por dois caminhos independentes, que concordaram em **50/50**:
- **engine**: `ForecastEngine` com só a equação;
- **workbook**: `eval` do Python sobre o texto literal da coluna `expression`, com `hes@Lx` trocado por identificadores.

As entradas foram escolhidas para que cada ramo tenha um valor distinto:
- `retirada_cond_corr_ltp − retirada_cond_corr_lth = 1`;
- 41c = 3;
- 41d = 5.

Evidência em `evidence/hes_decision_matrix.csv`.

Ordem dos ramos (cadeia `if/else` avaliada de cima para baixo). Notação: `d = retirada_cond_corr_ltp − retirada_cond_corr_lth`.

| # | condição | valor | L4_L5 | L6_L7 |
|---|---|---|---|---|
| 1 | as duas linhas `Normal` | `100 − 2d` | 1 combinação | 1 |
| 2 | **alguma** linha `LC` | `((100 − 2d)·14 + ((100 − 2d)/2)·10) / 24` | 9 | 9 |
| 3 | **alguma** linha `Overhaul/Parada` | `50 − 2d` | 7 | 7 |
| 4 | **alguma** linha `1 By pass` | `100 − 2d − desconto` | 5, com **41d** (VAR16024) | 5, com **41c** (VAR16023) |
| 5 | **as duas** linhas `1 By pass e LC` | `((100 − 2d)·14 + ((100 − 2d − 41c)/2)·10) / 24` | 1, com 41c (VAR16022) | 1, com 41c (VAR16023) |
| 6 | demais | `"F"` → `NO_APPLICABLE_RULE` | **2** | **2** |

Catálogo (implementado e testado **literalmente**; nada é bloqueio, §10.1):

| item | constatação (recalculada) | consta em `OBS`? |
|---|---|---|
| (i) precedência por ordem dos ramos | quando as linhas têm estados diferentes, vence o primeiro ramo satisfeito: **LC > Overhaul/Parada > 1 By pass > 1 By pass e LC**. Ex.: (`LC`, `Overhaul/Parada`) → LC; (`Overhaul/Parada`, `1 By pass`) → Overhaul; (`1 By pass e LC`, `LC`) → LC; (`1 By pass e LC`, `1 By pass`) → 1 By pass | **não** |
| (ii) `"F"` alcançável | só em **2 das 25** combinações por grupo: (`Normal`, `1 By pass e LC`) e (`1 By pass e LC`, `Normal`). Confirmado por enumeração nos dois grupos e nos dois caminhos | **não** |
| (iii) descontos | ramo `1 By pass`: L4_L5 usa `desconto_retirada_41d` (VAR16024, que só existe em L4_L5); L6_L7 usa `desconto_retirada_41c` (VAR16023). Ramo `1 By pass e LC`: 41c nos dois (VAR16022 em L4_L5, VAR16023 em L6_L7) | **sim** (linhas 39/42) |
| (iv) constantes embutidas | `100`, `50`, `14`, `10`, `24`, `2` no texto da expressão; `14 + 10 = 24` sugere ponderação horária (14 h a pleno, 10 h a meia carga) | **não** |
| (v) L1_L3 sem ramos por estado | `retirada_condensado_grupo` L1_L3 (EQ16010 → VAR16018) é `valor_retirada@L1 + @L2 + @L3 − 3·(retirada_cond_corr_ltp − retirada_cond_corr_lth)`, sem `hes` (não há `hes` para L1..L3) e com forma diferente dos grupos L4_L5/L6_L7 | **não** |

### 3.3 Compatibilidade técnica do retorno `"F"` (§10.5)

| verificação | resultado (`REAL_DERIVED_TEST_RESULT`) |
|---|---|
| o `"F"` vira estado, não texto no valor | **sim**. Nas 4 combinações `F` (2 por grupo): `value = None` (`NoneType`), `state = NO_APPLICABLE_RULE`. Em nenhuma das 50 combinações o valor é texto |
| `detail` | **`None`**, e não `"F"` (ver finding **F4A-01**) |
| mecanismo | `translate_declared_literal` (`app/domain/state_propagation.py`): o literal declarado em `declared_result_states` vira `Result(value=None, state=…)`; contrato 3.3B, D1/R1 (`REPORT_stage3_3B.md` §1) |
| propagação (IF causal 3.3B) | (`Normal`, `1 By pass e LC`) em L4/L5: `VAR16025@L4_L5`, `retirada_condensado_linha` `VAR16031@L4` e `@L5` e `retirada_condensado_total` `VAR16034@L1_L7` herdam `NO_APPLICABLE_RULE` (value None). L1..L3, L6, L7 e os demais 16 resultados ficam sem estado. O espelho em L6/L7 é simétrico |
| agregações (Policy B) | os resultados mensais e anuais das variáveis afetadas herdam o estado pela Policy B. A cobertura integrada (32 datas, Policy B, composição indefinida) é da Fase 2 |

### 3.4 Escopos mistos

Verificado no parser atual, sem presumir:

| sufixo | `scope_type_for` | uso no area_41 |
|---|---|---|
| `@L1`..`@L7` | `linha` | equações `linha_grupo` somam linhas (EQ16004/5/6, EQ16010, EQ16011/12 via `hes`); equações `linha` dividem pelo total do grupo (EQ16013..19) |
| `@L1_L3`, `@L4_L5`, `@L6_L7` | `linha_grupo` | equações `linha` lêem o grupo (EQ16013..19); EQ16020 soma os três grupos |
| `@L1_L7` | `linha_grupo` | aceito pelo parser; não usado no area_41 |
| `@L8`, `@L1_L5`, `@L4_L7`, `@L2_L3` | **rejeitados** (`InvalidScopeReferenceError`) | — |

- As 20 expressões do area_41 são aceitas pelo `ExpressionParser`.
- Em todas, o escopo da equação é igual ao `scope_type` da variável-alvo, e as instâncias da equação estão contidas nas da variável.
- Cada instância de cada variável-alvo é coberta **exatamente uma vez**. Exemplo: `retirada_condensado_linha` (VAR16031, `linha` L1_L7) é coberta por EQ16013..EQ16019, uma por linha.
- A equação `linha_grupo L1_L7` (EQ16020 → `retirada_condensado_total`, VAR16034) soma os três grupos.

### 3.5 Regras de agregação do area_41 (10)

Todas são `AVERAGE`, de `diário` para `mensal`/`anual`, com `integration_factor = 1.0` e sem peso.

| fonte (workbook) | alvo mensal / anual | instâncias |
|---|---|---|
| `retirada_condensado_grupo` L1_L3 (VAR16018) | VAR16019 / VAR16020 | `linha_grupo/L1_L3` |
| `retirada_condensado_grupo` L4_L5 (VAR16025) | VAR16026 / VAR16027 | `linha_grupo/L4_L5` |
| `retirada_condensado_grupo` L6_L7 (VAR16028) | VAR16029 / VAR16030 | `linha_grupo/L6_L7` |
| `retirada_condensado_linha` (VAR16031) | VAR16032 / VAR16033 | **7 instâncias** `linha/L1..L7` (`AGR-AREA_41-RETIRADA_CONDENSADO_LINHA-LINHA-L1_L7-*`) |
| `retirada_condensado_total` (VAR16034) | VAR16035 / VAR16036 | `linha_grupo/L1_L7` |

As regras **anuais** operam como YTD parcial (`YEAR_TO_DATE_PARTIAL_COVERAGE`, como na 3.4C). Sondagem de 3 datas no grafo de 5 blocos:
- o anual `VAR16020@L1_L3` de 2026 tem exatamente as janelas 2026-01-01, 2026-01-02 e 2026-01-03;
- o valor na janela de 2026-01-03 é igual à média dos 3 diários (`23.248822770420873`).

### 3.6 Entradas

| variável (workbook) | tipo | freq. | escopo | origem no 4A |
|---|---|---|---|---|
| `lth` (VAR16007) | entrada | diário | linha L1..L7 | **vínculo** `yield.VAR11031` (transferência executada) |
| `hes` (VAR16021) | entrada | diário | linha L4..L7 | **pendente** de `maintenance`. No fixture é entrada livre categórica (`Normal` por padrão; os cenários sobrescrevem) |
| `vazao_ltp` (VAR16001/2/3) | entrada_externa | mensal | grupos | fronteira (valor arbitrário do fixture) |
| `fator_retirada_cond_corr_lth` (VAR16011/2/3) | entrada_externa | mensal | grupos | fronteira |
| `valor_retirada` (VAR16017) | entrada_externa | diário | linha L1..L3 | fronteira |
| `desconto_retirada_41c` (VAR16022/23), `desconto_retirada_41d` (VAR16024) | entrada_externa | diário | L4_L5 / L6_L7 | fronteira |

**Lacuna L10 (mantida):** o area_41 não tem fonte nativa de estado. Estados chegam por:
- injeção nos cenários;
- herança via transferência;
- o literal `"F"`.

### 3.7 Documentação e nomenclatura

| ponto | classificação |
|---|---|
| unidades do area_41 (`m³/h`, `-`) | todas dentro de `ALLOWED_UNITS`; nada a registrar |
| `description` vazia no nível da variável: `valor_retirada` (VAR16017), `hes` (VAR16021), `retirada_condensado_linha` (VAR16031). Descrições existem só por instância | DOCUMENTATION_ONLY |
| `valor_retirada` (VAR16017) declarada `linha` / `L1_L3` (intervalo de linhas como `scope_value` de `linha`); o resolvedor a expande em L1, L2, L3 | DOCUMENTATION_ONLY |
| `valor_retirada`: o próprio `OBS` pede revisão do nome | REQUIRES_FOLLOWUP (já em `OBS`) |

---

## 4. Pontos que NÃO constam em `OBS` (para o engenheiro de processo)

Todos foram implementados **literalmente** como estão no workbook A41 v9. Nenhum bloqueia.

| # | ponto | classificação |
|---|---|---|
| N1 | precedência por ordem dos ramos (LC > Overhaul/Parada > 1 By pass > 1 By pass e LC) quando L4≠L5 ou L6≠L7 | REQUIRES_FOLLOWUP |
| N2 | `"F"` só em 2/25 combinações; o ramo `1 By pass e LC` exige as **duas** linhas nesse estado (`and`). Combinado com `LC`, `Overhaul` ou `1 By pass` na outra linha, cai em outro ramo | REQUIRES_FOLLOWUP |
| N3 | constantes `100`, `50`, `14`, `10`, `24`, `2` embutidas no texto (sem parâmetro) | REQUIRES_FOLLOWUP |
| N4 | L1_L3 sem ramos por `hes` e com forma diferente (`Σ valor_retirada − 3·d`) dos grupos L4_L5/L6_L7 (`100 − 2·d`) | REQUIRES_FOLLOWUP |
| N5 | `retirada_condensado_total` (VAR16034) vira `NO_APPLICABLE_RULE` sempre que **qualquer** grupo cai em `"F"`; o total da planta fica sem valor | REQUIRES_FOLLOWUP |
| N6 | divisão pela soma de `lth` do grupo (EQ16013..19): soma zero ⇒ falha explícita `DivisionByZeroError` (sem estado declarado). Exemplo: linhas paradas com `lth = 0` | REQUIRES_FOLLOWUP |
| N7 | `ln` fora do domínio (`vazao_ltp ≤ 0` ou `lth_grupo · fator ≤ 0`) ⇒ falha explícita `MathDomainError` (via `EquationEvaluationError`) que interrompe a execução | DOCUMENTATION_ONLY (comportamento técnico correto) |
| N8 | `vazao_ltp` e `fator_retirada_cond_corr_lth` são **mensais** e consumidos por equações **diárias**: o mesmo valor do mês vale em todos os dias | DOCUMENTATION_ONLY |

---

## 5. Decisões (§3.4)

As decisões abaixo são técnicas e não há pendência técnica sem resolução, por isso foram aceitas por padrão (§3.5). Pendências de negócio estão nos §3.1 e §4 e não pausam a execução.

| id | decisão | recomendação | estado |
|---|---|---|---|
| DR-4A-1 | **universo integrado 421 → 446**: os 5 blocos carregados (yield, production, energy, max_ht, area_41); 458 nós (238/207/13), 62 entradas, 896 eventos por data, 32 datas | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-2 | **regeneração de evidência (protocolo L8)**: a evidência nova fica **só** em `audit/stage4a/**` (`integrated/evidence/`, `oracle/`, `mutation/`, `closure/`). A evidência da 3.4C é preservada como histórica, comparada e **nunca** sobrescrita. O harness 4A falha se a comparação divergir | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-3 | **oracle**: `INDEPENDENT_NUMERIC_ORACLE = PARTIAL (area_41, fidelidade ao workbook)`. Python puro reescrito do texto do workbook A41 v9, sem importar `app/` no cálculo. Valida fidelidade ao workbook, **não** correção de negócio. Compartilha com o engine a leitura do workbook | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-4 | **critérios do gate**: os 12 critérios do §7 do prompt, todos PASS, com os valores congelados em `contract_expectations.json` | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-5 | **protocolo de entradas** do §2.1 (índice da 3.4C preservado; área 41 em 51..61) | adotar; sem ele a comparação com a 3.4C mede o fixture, não o engine | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-6 | **`"F"` → `NO_APPLICABLE_RULE` com `detail = None`**: a 4A testa o comportamento do contrato 3.3B fechado (value None, state `NO_APPLICABLE_RULE`, detail None). A expectativa "detail `"F"`" do prompt fica registrada como F4A-01. Mudar o detail exigiria alterar `app/`, o que está fora de escopo | manter o contrato 3.3B; decisão futura do cliente/arquitetura | `PROPOSED_ACCEPTED_BY_DEFAULT` |
| DR-4A-7 | **tolerância do oracle**: `math.isclose(rel_tol=1e-12, abs_tol=1e-12)`. O oracle executa as mesmas operações IEEE-754, na mesma ordem do texto, então a expectativa é igualdade exata. A folga cobre só reassociação de somas; `abs_tol` cobre resultados próximos de zero. Estados e falhas comparam por igualdade exata | adotar | `PROPOSED_ACCEPTED_BY_DEFAULT` |

---

## 6. Findings da Fase 1

| id | severidade | finding | evidência |
|---|---|---|---|
| F4A-01 | REQUIRES_FOLLOWUP | o engine traduz `"F"` em `Result(value=None, state=NO_APPLICABLE_RULE, detail=None)`. O §10.5 do prompt esperava `detail = "F"`. O comportamento é o do contrato fechado (3.3B D1/R1; `translate_declared_literal`). **Não há texto no valor** de variável numérica, que é a propriedade técnica essencial. Não é BLOCKER: o contrato de resultado é respeitado | `contract_audit.json → f_literal`; `hes_decision_matrix.csv` |
| F4A-02 | DOCUMENTATION_ONLY | o prompt chama EQ16004 de "equação de `retirada_condensado_grupo` L1_L3" e EQ16006 de "L6_L7 de `retirada_condensado_grupo`". Nos seeds, EQ16004/EQ16006 são `lth_grupo` L1_L3/L6_L7; `retirada_condensado_grupo` L1_L3 é EQ16010 e L6_L7 é EQ16012. A 4A usa os IDs reais, e o mutante "`/2` → `/3` em EQ16006" é aplicado a EQ16006 (`lth_grupo` L6_L7) | `data/seed/area_41/equations.json` |
| F4A-03 | DOCUMENTATION_ONLY | a 3.4C não usava o vínculo `VAR16007` (12/13); a 4A usa os 13 | §1.4 |

`BLOCKER` técnico: **nenhum**. Decisão técnica `UNRESOLVED`: **nenhuma**.

---

## 7. Regra de parada (§3.5)

```text
BLOCKER técnico: 0    decisão técnica UNRESOLVED: 0
=> não há READY_FOR_DECISION; a execução prossegue para a Fase 2.
```

---

## 8. Reprodução

```text
python -I audit/stage4a/independent_count.py --check     # recálculo independente x expectativas
python audit/stage4a/derive_4a.py --no-write             # derivação empírica x expectativas versionadas
python -m pytest -q tests/test_stage4a_contract.py
```
