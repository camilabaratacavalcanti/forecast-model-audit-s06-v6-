# Etapa 2.5 — Fechamento das decisões contratuais remanescentes

Esta etapa é de análise e especificação. **Nada foi alterado** em workbooks, builders, domínio, validators,
resolver, runtime, seeds ou testes: `git status` mostra apenas `audit/stage2_5_contract_closure/`. Os builders
foram executados só em memória, e a prova de runtime usou uma cópia temporária dos seeds, apagada ao final.

Tudo é reexecutável a partir da raiz do repositório:

```
python audit/stage2_5_contract_closure/evidence/analysis_stage2_5.py
```

## 1. Baseline

| item | valor |
|---|---|
| branch | `feature/area-41-block` |
| HEAD | `6b135e9` (= origin; contém o fechamento da 2.4) |
| árvore | limpa no início |
| suíte | 1409 passed (antes e depois desta etapa) |
| artefatos da 2.4 lidos | REPORT_stage2_4_round2, defect_register, test_coverage_matrix, test_inventory_delta, cross_workbook, pending_contract_decisions |

## 2. Workbooks e SHA-256

| bloco | workbook | SHA-256 | estado |
|---|---|---|---|
| area_41 | A41 v8 | `be2372b4f4f35f5aea720dcc00c680f3e47e359138995dd35a6dcabd3d603528` | aprovado na 2.4, byte-idêntico |
| energy | energy v5 | `34c1c88af318e57026c08c21fd2a1cf308258e575eddbb11d98ba0bba6878047` | aprovado na 2.4, byte-idêntico |
| max_ht | MaxHT v9 | `74d5cbb7624d5c7101b5f25ecd76e156c9d019968c7e5f9af2ed04aa50b27004` | aprovado na 2.4, byte-idêntico |
| yield | yield v9 | `1c7b5684cc49d9498edceb520ced2e8a1f673812057d4094846820074098a76b` | aprovado na 2.4, byte-idêntico |
| production | **production v7** | **`49aa5d38a902c3bb46909094472c07e0b99644529a0d05501255e2a632f7a3af`** | **candidato**; substitui o v6 nesta análise |
| (referência) | production v6 | `17cb83ca15d92c0b3243a606ddfd194a110dcc4f01fb71bf30511a4c6fb07210` | aprovado na 2.4; continua em `data/workbooks/` e nos seeds oficiais |

O v7 foi copiado byte a byte para `evidence/inputs/` para tornar a análise reproduzível. Ele não foi colocado em
`data/workbooks/` e não passou a ser o workbook oficial do builder: aprovar o v7 é uma decisão, e aplicá-la
pertence à etapa de implementação.

## 3. Impacto da substituição production v6 → v7

Comparei as duas planilhas célula a célula (`evidence/production_v6_v7_diff.csv`). Há **uma única diferença**:

| célula | coluna | v6 | v7 |
|---|---|---|---|
| P25 | expression (`desaguamento_oee`) | `100 * (consumo_mpsa / 24) / (desaguamento_produtividade * 13)` | `100 * (consumo_mpsa_grupo / 24) / (desaguamento_produtividade * 13)` |

Efeito do build do v7 (em memória) comparado ao seed oficial construído com o v6:

| aspecto | resultado |
|---|---|
| contagens | idênticas: 65 variáveis, 17 registros de parâmetro, 27 equações, 28 regras |
| IDs | idênticos (a ordem das linhas não mudou) |
| conteúdo | muda só a expressão de `EQ12008` e o `source_reference` que cita o nome do arquivo (v6 → v7) |
| decisões pendentes no manifesto | 1 (R2-A019-UNREACHABLE) → **0** |
| outros quatro blocos | build idêntico aos seeds oficiais |
| validators sobre seeds temporários com o v7 | variable 0 erros (27 avisos D24-11, os mesmos de antes), parameter 0, equation 0, sintaxe 0 |
| RegistryIntegrityValidator | OK |

Pontos fixados no v6 que a implementação terá de atualizar ao aprovar o v7:

- `tools/workbook_seed/blocks.py:86-87`, com o nome do arquivo e o SHA-256 do v6;
- `tests/test_production_v1.py`, no teste que documenta R2-A019-UNREACHABLE (linhas 1030, 1339, 1364);
- a regeneração de `data/seed/production/`.

## 4. Antiga R2-01 — validação da correção

**PROBLEMA ORIGINAL:** em production v6, `desaguamento_oee` (anual, linha_grupo/L1_L7) escrevia `consumo_mpsa`.
A única definição com esse nome é diária e de escopo linha/L1_L7. A resolução A019 caía no fallback de
frequência (não existe `consumo_mpsa` anual) e ligava a expressão a essa definição, que nenhuma instância do
consumidor alcança: nem no espaço (linha_grupo não alcança linha), nem no tempo (um consumidor anual não lê uma
série diária).

**CORREÇÃO NO PRODUCTION_V7:** P25 passa a usar `consumo_mpsa_grupo`. As linhas 13–17 e 26 do v7 conferem com a
descrição do dono do modelo:

- `consumo_mpsa_grupo` diário, linha_grupo/L1_L7, calculado como `consumo_mpsa@L1 + … + consumo_mpsa@L7`;
- `consumo_mpsa_grupo` mensal, como média mensal;
- `consumo_mpsa_grupo_somatorio` mensal, como somatório mensal (existe no v7 e não estava no resumo recebido);
- `consumo_mpsa_grupo` anual, como somatório anual, em t/ano;
- `desaguamento_produtividade`: parâmetro anual, planta/PLANTA, value 115.

**VERIFICAÇÃO:** evidências em `evidence/production_v7_desaguamento.csv`.

| # | ponto exigido | resultado |
|---|---|---|
| 1 | a referência antiga não existe mais | `consumo_mpsa /` não aparece em P25; nenhuma outra célula mudou |
| 2 | referencia a definição correta | `VAR12015` = `consumo_mpsa_grupo` anual linha_grupo/L1_L7 (linha 17), t/ano, numerico |
| 3 | a definição é alcançável | a instância linha_grupo/L1_L7 do consumidor coincide com a do produtor (OWN_SCOPE) |
| 4 | frequência, escopo, unidade e identidade | anual = anual; linha_grupo/L1_L7 = linha_grupo/L1_L7; value_type numerico dos dois lados. A unidade t/ano é a quantidade anual que a fórmula espera: era a mesma grandeza (consumo anual de MPSA) que a formulação histórica usava. A plataforma não faz álgebra dimensional de equações, então a coerência dimensional da fórmula em si continua sendo responsabilidade do dono |
| 5 | não depende de fallback indevido | existem três definições com o nome (diário, mensal, anual) e a de mesma frequência é única, logo não há fallback de frequência. `desaguamento_produtividade` (planta/PLANTA) é alcançado pela cadeia espacial padrão linha_grupo → planta (Decision E), o mecanismo aprovado para parâmetros de planta. Não é fallback de frequência |
| 6 | nenhuma nova inconsistência | uma só célula alterada; builder sem erros e sem decisões pendentes; validators com 0 erros; inventário de referências com 0 inalcançáveis (§7) |
| 7 | representação coerente no builder e no seed | a produção de `VAR12015` é rastreável (ver cadeia abaixo) |

Cadeia de produção de `VAR12015`:

- a regra `AGR-PRODUCTION-CONSUMO_MPSA_GRUPO-GRUPO-L1_L7-ANUAL-SUM` (SUM, fator 1, t/d → t/ano) agrega `VAR12012`;
- `VAR12012` é `consumo_mpsa_grupo` diário, produzido pela equação `EQ12005`: `VAR12011@L1 + … + VAR12011@L7`;
- `VAR12011` é `consumo_mpsa` diário, e seus termos são instâncias declaradas L1..L7.

**RESULTADO:** carreguei, com o SeedLoader, seeds temporários contendo o production v7. O RegistryIntegrityValidator
passou, e a cadeia foi executada de ponta a ponta:

1. `consumo_mpsa@L1..L7` em 3 dias;
2. `EQ12005` (grupo diário);
3. a SUM anual, que deu 882,0 (esperado 882,0);
4. `EQ12008`, que deu 2,4581939799 (esperado `100·(882/24)/(115·13)` = 2,4581939799).

**STATUS: RESOLVED_IN_SOURCE_WORKBOOK**

## 5. D24-11 — ligação entre workbooks

**DECISÃO:** como uma entidade declarada num workbook se liga à mesma entidade produzida por outro workbook.

**ESTADO ATUAL:** cada workbook é construído isoladamente. Uma entidade vinda de outro bloco vira uma definição
local, com ID próprio da faixa do consumidor, `variable_type = entrada` e `fonte` em texto livre
("bloco production"). Nenhum ID é ligado entre blocos. O validator emite 27 avisos rotulados D24-11 (identidade
repetida entre blocos). A ligação production ← yield por ID (`VAR11001@Lx`) existia apenas no seed histórico,
feito à mão, e nunca esteve em workbook aprovado.

**PROBLEMA:** o contrato não diz se a identidade é global ou local. Também não diz como o consumidor aponta o
produtor, quando o vínculo é verificado, nem o que fazer com divergências de tipo, unidade, frequência ou escopo.
Sem essa regra, um bloco consumidor só roda se alguém injetar manualmente os valores do produtor.

**EVIDÊNCIAS:** `evidence/cross_workbook.csv`, `identity_repeats_cross_block.csv`, `external_sources_outside_five.csv`.

- **As 13 relações continuam 13 com o v7.** Todas as definições consumidoras são `variable/entrada`, e todas as
  identidades (nome, frequência, escopo) existem no bloco produtor com unit e value_type iguais.
  - 11 são COMPATÍVEIS.
  - Duas exigem decisão:

    | consumidor | produtor | problema |
    |---|---|---|
    | `area_41.lth` (fonte "bloco yield") | `yield.lth` | é também uma `entrada` (fonte "bloco production"): a fonte declarada não é o produtor real → **D25-03** |
    | `energy.lth_meta`, variável anual linha/L1_L7 | `production.lth_meta` | é **parameter** (anual, 7 valores por linha). Instâncias iguais (L1..L7); tipos diferentes |
  - `energy.pick_up` (uma linha L1_L7) × `production.pick_up` (7 linhas por instância): mesmas instâncias,
    representação diferente. É compatível.
- **O `variable_type` já separa as naturezas nos dados atuais:**

  | `variable_type` | linhas | `fonte` |
  |---|---:|---|
  | `entrada` | 31 | sempre cita um bloco: 13 dentro dos cinco, 18 fora (maintenance, forecast, temperature_lp, alumina, maintenance_plan, area_04_13) |
  | `entrada_externa` | 56 | sem `fonte` em 55; a exceção é energy r37 |
  | `calculado` | 445 | sem `fonte` em 443; as exceções são production r30 e r32 |

  As exceções viram **D25-04**.
- **Há repetições de identidade entre blocos fora das 13 relações** (18 identidades repetidas no total):
  - 6 são as próprias ligações declaradas por `fonte`;
  - 11 identidades são **calculadas em mais de um bloco** → **D25-01**. Exemplos: `lth` mensal (max_ht,
    production, yield); `lth_total` diário (max_ht, production, yield); `oee_total` diário e mensal (production,
    yield); `lth_grupo` diário L1_L3, L4_L5 e L6_L7 (area_41, yield); `producao` mensal (max_ht, production);
  - 1 identidade é **entrada sem fonte** num bloco e calculada em outro (`oee` diário: `entrada_externa` em yield,
    calculado em production), com **unidades diferentes** (`-` × `%`) → **D25-02**.

**ALTERNATIVAS:**

| critério | A1 — identidade local + vínculo explícito (`source_block` [+ `source_name`]) resolvido no build | A2 — identidade global (um namespace para todos os blocos; consumidor referencia o ID do produtor) | A3 — mapeamento implícito em runtime por nome | A4 — usar `source_reference` como vínculo |
|---|---|---|---|---|
| semântica | cada bloco possui as suas definições; um consumidor declara de quem recebe o valor | a identidade (nome+freq+escopo) é única na plataforma | o orquestrador copia valores por nome | o texto de proveniência vira ponteiro |
| vantagens | blocos continuam versionáveis de forma independente; o vínculo é explícito, verificável no build e auditável; nenhuma colisão com D25-01; migração só nas 13 linhas | um valor, um ID; sem cópia em runtime; restaura o estilo do seed histórico (`VAR11001@Lx`) | nenhuma mudança de workbook | nenhuma coluna nova |
| riscos | colunas novas no workbook; um passo de build que envolve vários blocos; cópia ou alias de valor em runtime | colide com D25-01 (11 identidades calculadas em vários blocos) e D25-02 (unidades); nomes iguais com significados diferentes em blocos futuros; todo bloco depende do build conjunto; IDs de consumidores desaparecem | vínculo invisível e não verificável no build; ambiguidades só aparecem em execução; viola "nenhuma camada inventa semântica" | `source_reference` hoje guarda referências à planilha legada ("Yield!E7:AI7") e nomes de arquivo; sobrecarregá-lo é proibido pelo prompt |
| domínio | novo `SourceBinding(consumer_id, producer_block, producer_id)` ou campo `source_binding` na VariableDefinition | a VariableDefinition do consumidor deixa de existir; o registry passa a ser global | nenhum | nenhum |
| workbooks | `source_block` (obrigatório em `entrada`) e `source_name` (opcional, só quando o nome difere) | linhas de consumidor removidas ou marcadas como alias; decisão de dono para as 11 réplicas | nenhum | reescrever `source_reference` |
| builder | um passo de cross-build carrega os cinco modelos canônicos e resolve e valida os vínculos | build único de todos os blocos; resolução global de nomes | nenhum | parse de texto |
| seeds | `data/seed/bindings.json` (ou `bindings` por bloco) com consumidor → produtor por instância | expressões do consumidor passam a citar IDs de outro bloco; seeds interdependentes | nenhum | nenhum |
| registry | registro de vínculos; a validação de integridade inclui vínculos | registry único obrigatório | — | — |
| resolver | inalterado (a A019 continua local ao bloco) | resolução passa a ser global (risco de ambiguidade entre blocos) | — | — |
| runtime | o orquestrador ordena os blocos pelo grafo de vínculos e propaga o valor do produtor para o ID do consumidor por instância e período; valor ausente = erro explícito | o grafo global de dependências já liga os IDs | cópia por nome | — |
| migração | preencher `source_block` nas 13 linhas; nas 18 linhas cuja fonte está fora dos cinco blocos, o vínculo fica em estado declarado-não-resolvido até o bloco existir | renumerar e fundir; decidir as 11 réplicas; resolver unidades antes | — | — |
| testabilidade / auditabilidade | alta: cada vínculo é uma linha verificável com erro nomeado | média: colisões aparecem como erros globais difíceis de atribuir | baixa | baixa |

**RECOMENDAÇÃO:** A1. Especificação normativa proposta, a ser aprovada; não foi implementada:

| norma | regra |
|---|---|
| N1 | Identidade é **local ao bloco**: (bloco, name, frequency, scope_type, scope_value). A unicidade dentro do bloco continua obrigatória (já implementado) |
| N2 | O consumo entre blocos só acontece por **vínculo explícito** declarado no workbook consumidor: coluna `source_block` (nome canônico do bloco) e coluna opcional `source_name`, usada só quando o nome no produtor difere. A frequência e o escopo do vínculo são os da própria linha consumidora. **Não há conversão** de frequência nem de escopo num vínculo |
| N3 | `variable_type = entrada` **exige** `source_block`. `entrada_externa` e `calculado` **não podem** tê-lo. `fonte` passa a ser documental |
| N4 | `source_reference` é **apenas proveniência** (célula da planilha de origem ou arquivo lido). Nunca participa do vínculo |
| N5 | O vínculo é resolvido **no build**, depois que os modelos canônicos de todos os blocos citados estão prontos. O resultado é uma tabela de vínculos versionada no seed, com consumidor, produtor e instâncias |
| N6 | Erros no build: produtor inexistente; produtor ambíguo; produtor que é ele mesmo um vínculo (salvo decisão D25-03); unit diferente; value_type diferente; frequency diferente; conjunto de instâncias do consumidor não contido no do produtor; allowed_values diferentes |
| N7 | **Tipos diferentes:** variável ← variável (calculada ou agregada) é permitido. Variável ← parâmetro só é permitido se o consumidor for anual e as instâncias coincidirem: o valor do parâmetro (constante do ano) é o valor da instância no período `YYYY`, escolhido pela versão ativa. Qualquer outra combinação é erro. Alternativa, se o dono preferir: exigir `Type=parameter` também no consumidor, sem `value` próprio |
| N8 | Uma `entrada` cujo `source_block` ainda não existe na plataforma (os 18 casos: maintenance, forecast etc.) é aceita com vínculo **declarado e não resolvido**. O runtime exige o valor externo e dá erro explícito na falta. O vínculo passa a ser verificado quando o bloco produtor for incorporado |
| N9 | No **runtime**, o orquestrador executa o produtor antes do consumidor (ordem pelo grafo de vínculos) e disponibiliza o valor da instância e do período do produtor sob o ID do consumidor. Sem valor, erro explícito; nenhum default |
| N10 | **Réplicas (D25-01):** uma identidade calculada em mais de um bloco precisa ser declarada pelo dono como réplica local (cada bloco calcula a sua) ou convertida em `entrada` com vínculo ao produtor canônico. A norma só impõe que o build liste todas as réplicas; a escolha por identidade é do dono |
| N11 | **Compatibilidade com os cinco workbooks atuais:** as 11 relações compatíveis ganham `source_block` sem outra alteração. As duas incompatíveis dependem de N7 (`lth_meta`) e de D25-03 (`area_41.lth`) |
| N12 | **Blocos novos:** entram com o seu próprio namespace (N1). Os vínculos são declarados por eles. Os vínculos pendentes (N8) que apontam para o bloco novo passam a ser resolvidos no build seguinte |

**JUSTIFICATIVA:**

- A A1 é a única alternativa que não exige resolver antes D25-01 e D25-02.
- Preserva o que a 2.4 já garante: identidade no bloco, builder por workbook e A019 local.
- Torna o vínculo verificável no build, com um erro nomeado por relação.
- Os dados atuais já seguem a separação `entrada` × `entrada_externa` em 31 de 31 linhas `entrada`.
- A A2 exigiria fundir 11 identidades calculadas em vários blocos e reconciliar unidades antes de funcionar.
- A A3 e a A4 introduzem semântica implícita.

**IMPACTO NO WORKBOOK:** nova coluna `source_block` (e `source_name` opcional). Preencher 13 linhas nos blocos
atuais e 18 com blocos externos, com vínculo pendente (N8). Decisões D25-01..04.

**IMPACTO NO SEED:** tabela de vínculos (`bindings.json`); o manifesto registra vínculos pendentes. IDs e demais
arquivos inalterados.

**IMPACTO NO DOMÍNIO:** novo tipo `SourceBinding` (ou campo `source_binding` na VariableDefinition) e registro de
vínculos.

**IMPACTO NO BUILDER:** leitura de `source_block`/`source_name`; passo de cross-build com as validações de N6/N7;
regra N3.

**IMPACTO NO RESOLVER:** nenhum. A A019 continua local; o vínculo não é resolução de nome em expressão.

**IMPACTO NO RUNTIME:** ordenação entre blocos e propagação por instância e período (N9). Pertence ao orquestrador
da Etapa 3.

**TESTES NECESSÁRIOS:**

- 13 vínculos resolvidos no build;
- um erro nomeado para cada caso de N6 (produtor inexistente, ambíguo, unit, value_type, frequency, instâncias,
  produtor-vínculo);
- parameter → variable anual aceito e não-anual rejeitado (N7);
- `entrada` sem `source_block` = erro; `entrada_externa` ou `calculado` com `source_block` = erro;
- vínculo pendente (N8) aceito no build e erro em runtime sem valor;
- propagação em runtime por instância, com cruzamento de linha detectável;
- `source_reference` alterado não muda nenhum vínculo;
- réplicas D25-01 listadas pelo build.

## 6. D24-12 — `value` e `version` em Type=variable

**DECISÃO:** se uma linha `Type=variable` pode trazer `value` e `version`, e com que significado.

**ESTADO ATUAL:** a rodada 2 não transporta o valor para o domínio (VariableDefinition não tem `value`) e o
registra em `data/seed/yield/manifest.json` → `pending_contract_decisions`.

**PROBLEMA:** o contrato não dá significado a esses campos em variáveis. Qualquer uso deles seria semântica
inventada.

**EVIDÊNCIAS:** varri as 572 linhas dos cinco workbooks, com production v7 (`evidence/variable_value_inventory.csv`).
Há **uma ocorrência**:

| workbook | linha | name | frequency | escopo | value | version | value_type | variable_type | status |
|---|---:|---|---|---|---:|---:|---|---|---|
| yield v9 | 92 | `ltp_tc` | diário | linha/L1_L7 | 273 (int) | 1 | numerico | entrada_externa | ativo |

O parâmetro correlato aprovado é `ltp_tc_base` = **274** (yield v9 r102). 273 é o valor histórico de `ltp_tc_base`
no yield v4, época em que `ltp_tc` ainda era parâmetro. A 2.3 (NB-1) já registrou o 273 como resquício.

**ALTERNATIVAS:**

| alternativa | significado | avaliação |
|---|---|---|
| B1 — rejeitar | variável não tem value nem version | nenhuma semântica nova; alinhado ao domínio atual |
| B2 — default / fallback de entrada | 273 usado quando a entrada falta | introduz valor implícito; mascara entrada ausente (contra D3: erro técnico nunca vira valor); conflita com `ltp_tc_base` 274 |
| B3 — valor inicial de série | primeiro período | não existe conceito de estado ou carry-over no contrato; valor diário por linha não teria um único inicial |
| B4 — documental | transportado como metadado sem efeito | cria um campo sem consumidor; um valor visível e ignorado confunde; se desejado, o lugar é a coluna OBS |
| B5 — tratar como parâmetro | promover a linha a parâmetro | contradiz o `Type=variable` e o `variable_type=entrada_externa` aprovados |

**RECOMENDAÇÃO:** B1, como regra geral para todos os blocos:

- **R1:** `value` e `version` são **exclusivos** de `Type=parameter`. Numa linha `variable` ou
  `variable / equation`, ambos devem estar vazios.
- **R2:** o builder dá erro de contrato, e o seed validator rejeita `value` ou `version` num registro de
  variável (hoje já rejeita campos desconhecidos).
- **R3:** o runtime nunca usa valor declarado em variável. Toda entrada vem do contexto de execução (ou de um
  vínculo, conforme D24-11); ausência = erro explícito.
- **R4:** `version` não tem significado operacional para variáveis. Para parâmetros continua compondo a chave do
  `ParameterDefinitionRegistry`.
- **R5 (transição):** até o dono publicar o yield corrigido (limpando E92/F92, por exemplo num yield v10), o builder
  mantém o comportamento atual: não transporta o valor e o registra no manifesto. Aplicar R2 antes disso bloquearia
  o build do yield.

Diferença entre os casos perguntados:

| caso | de onde vem o valor |
|---|---|
| variável com `value` | inválido (R1) |
| parâmetro com `value` | constante declarada, por escopo e versão |
| variável produzida por equação | valor vem da equação |
| variável de entrada externa | valor vem do contexto em runtime, sem default |

O caso `ltp_tc = 273` **não é válido** pelo contrato recomendado e deve ser corrigido no workbook, sem virar
exceção.

**JUSTIFICATIVA:** a B1 não inventa semântica e mantém uma única fonte para cada tipo de valor. Também elimina o
risco de 273 ser usado no lugar do 274 aprovado.

**IMPACTO NO WORKBOOK:** yield r92: limpar E92 e F92 (decisão e ação do dono).

**IMPACTO NO SEED:** nenhum (o valor já não é transportado); o registro pendente do manifesto some com o workbook
corrigido.

**IMPACTO NO DOMÍNIO:** nenhum. VariableDefinition continua sem `value`.

**IMPACTO NO BUILDER:** a regra de registro pendente vira erro de contrato após a transição (R2, R5).

**IMPACTO NO RESOLVER:** nenhum.

**IMPACTO NO RUNTIME:** nenhum.

**TESTES NECESSÁRIOS:**

- `value` ou `version` em variável = erro no builder e no validator (após a transição);
- inventário dos workbooks = 0 ocorrências após a correção;
- o parâmetro continua exigindo `value` e `version`;
- T24-16 atualizado de "registrado" para "rejeitado".

## 7. Novos achados

**Inventário de referências** (`evidence/unreachable_reference_inventory.csv`): as 238 equações dos cinco
workbooks (production v7) somam 1436 referências.

| classificação | quantidade | detalhe |
|---|---:|---|
| DIRECT | 1417 | mesma frequência, próprio escopo |
| RESOLVED_BY_FREQUENCY_FALLBACK | 16 | todos são consumidores diários lendo entradas mensais ou anuais sem homônimo diário: area_41 r6–r8 e r16–r18 (`vazao_ltp`, `fator_retirada_cond_corr_lth`), energy r21 e r36 (`temperatura_lp_ref_*`, `economicidade_evaporacao_ref`), production r35 (`fator_ajuste_lth`), yield r152 (6 variáveis `_base`). É o fallback temporal aprovado do runtime (dia → mês → ano, BD-02): referência mais grossa, sempre alcançável |
| RESOLVED_BY_SPATIAL_PARENT | 3 | production r25 → `desaguamento_produtividade` (planta), r30 e r32 → `fator_mpsa_kg_t` / `fator_mrn_kg_t` (grupo L1_L7 lido por linha): Decision E |
| UNREACHABLE | **0** | |

**0 referências inalcançáveis adicionais.** Com o v6, o único caso era R2-01, agora resolvido.

Achados contratuais registrados (todos CONTRACT_GAP, não implementados; ver `contract_decisions.csv`):

| id | achado | por que precisa de decisão antes da Etapa 3 |
|---|---|---|
| D25-01 | 11 identidades são **calculadas em mais de um bloco** (`identity_repeats_cross_block.csv`) | a Etapa 3 vai orquestrar blocos juntos: é preciso saber se são réplicas locais ou se devem ser vinculadas a um produtor canônico (N10), senão duas execuções podem produzir valores divergentes para a mesma identidade |
| D25-02 | `oee`/`oee_total` (diário e mensal): unidade `%` em production e `-` em yield; `yield.oee` diário é `entrada_externa` sem fonte, mas production o calcula | risco de escala (0,9 × 90); nenhum vínculo pode ser validado (N6) sem unidade canônica |
| D25-03 | `area_41.lth` declara `fonte` "bloco yield", mas `yield.lth` é ele mesmo uma entrada vinda de production | define se o vínculo aponta só o produtor real (um salto) ou se cadeias são permitidas |
| D25-04 | `fonte` fora de `entrada`: energy r37 (`entrada_externa` com fonte de bloco) e production r30/r32 (`calculado` com fonte "bloco forecast") | N3 depende de `fonte`/`source_block` só existirem em `entrada`; esses três casos precisam ser reclassificados ou ter o significado da fonte definido |

Nenhuma inconsistência nova foi introduzida pelo production v7.

## 8. Alternativas arquiteturais

Resumidas nas tabelas de §5 (A1–A4) e §6 (B1–B5).

## 9. Recomendação

| item | recomendação |
|---|---|
| R2-01 | RESOLVED_IN_SOURCE_WORKBOOK. Aprovar o production v7 como oficial e aplicá-lo na etapa de implementação |
| D24-11 | A1 (identidade local + vínculo explícito `source_block`, resolvido no build e propagado em runtime), normas N1–N12 |
| D24-12 | B1 (variável não tem `value` nem `version`), regras R1–R5, e correção do yield r92 pelo dono |
| D25-01..04 | decisões do dono do modelo; D25-02 e D25-03 bloqueiam a aplicação de D24-11 às relações afetadas |

## 10. Impacto esperado da implementação

- **production v7:** registrar nome e SHA-256 em `blocks.py`, copiar para `data/workbooks/`, regenerar o seed
  production e atualizar o teste de R2-01. O efeito esperado se limita a `EQ12008`, aos `source_reference` com o
  nome do arquivo e ao manifesto sem pendências.
- **D24-11:** nova coluna nos workbooks; `SourceBinding` no domínio; cross-build no builder; `bindings.json` no
  seed; propagação no orquestrador (Etapa 3). Resolver inalterado.
- **D24-12:** uma regra no builder/validator (após o yield corrigido) e ajuste do T24-16.

## 11. Critérios para a etapa de implementação

1. Os workbooks aprovados (com o production v7 e os que o dono publicar para D24-12, D25-02..04) terão SHA-256
   registrados e conferidos pelo builder.
2. builder == seed para todos os blocos; reconciliação linha a linha 100 %.
3. Todo `entrada` de bloco da plataforma tem vínculo resolvido; todo erro de N6 tem teste com mensagem nomeada;
   os vínculos pendentes (N8) ficam listados no manifesto.
4. 0 `value`/`version` em variáveis nos workbooks; o builder e o validator rejeitam.
5. Inventário de referências com 0 UNREACHABLE; fallbacks de frequência só do tipo "referência mais grossa"
   (`unreachable_reference_inventory.csv` reexecutado como teste).
6. Réplicas D25-01 resolvidas conforme a decisão do dono e verificadas pelo build.
7. Suíte completa verde; nenhum default implícito, nenhuma coerção, nenhuma ligação por inferência.

## Conclusão

| item | estado |
|---|---|
| R2-01 | RESOLVED_IN_SOURCE_WORKBOOK |
| D24-11 | especificado (A1, N1–N12); aguarda aprovação |
| D24-12 | especificado (B1, R1–R5); aguarda aprovação e correção do yield r92 |
| D25-01, D25-02, D25-03, D25-04 | CONTRACT_GAP registrados; aguardam decisão do dono |
| quatro workbooks aprovados | byte-idênticos |
| production v7 | SHA-256 registrado; sem alterações |
| código, seeds e testes | inalterados; suíte com 1409 passed |

Push: o hook de encerramento deste ambiente exige que não fiquem commits locais sem push (o mesmo ocorreu na
2.4). O commit desta etapa contém apenas `audit/stage2_5_contract_closure/` e é publicado por essa exigência do
ambiente, não como mudança funcional.

STAGE_2.5_CONTRACT_GATE: READY_FOR_DECISION
