# TECH-DEBT TD-TAX-01 — Duplicação Física da Taxonomia Canônica

| campo | valor |
|---|---|
| id | `TD-TAX-01` |
| tipo | dívida arquitetural (não funcional) |
| status | **OPEN** |
| registrada em | D-TAX-02 (posterior a D-TAX-01, `d8b5d55`) |
| bloqueador funcional | **não** |
| registro | `audit/stage3_4/taxonomy_migration/contract_decisions.csv` |

Esta dívida **não** é uma falha da migração D-TAX-01. É uma consequência conhecida e controlada das fronteiras atuais do código.

## 1. Estado atual

A taxonomia canônica é **conceitualmente única**: os 29 blocos da decisão D-TAX-01, na ordem das faixas de ID.

Ela existe **fisicamente** em duas implementações, que servem de base para cinco projeções:

| implementação | arquivos | projeções | consumida por |
|---|---|---|---|
| **app** | `app/validation/variable_seed_validator.py` (`VARIABLE_ID_RANGES`), `parameter_seed_validator.py` (`PARAMETER_ID_RANGES`), `equation_seed_validator.py` (`EQUATION_ID_RANGES`) | 3 dicionários literais nome → faixa | validação de seeds (faixa do ID por bloco) |
| **tools** | `tools/workbook_seed/taxonomy.py` (`BLOCK_TAXONOMY`) | 1 tupla literal de nomes | validação de `fonte` dos workbooks e geração de `data/seed/interblock_links.json → taxonomy.official_blocks` (5ª projeção, gerada), lida pelo `InterblockLinkRegistry` |

## 2. Fonte conceitual

A fonte normativa é a **decisão D-TAX-01** (`audit/stage3_4/STAGE_3_4_TAXONOMY_MIGRATION.md`).

As projeções físicas são apenas materializações exigidas pelas fronteiras arquiteturais atuais. **Nenhuma delas está autorizada a evoluir independentemente.**

## 3. Motivo da duplicação (verificado no código)

- `tools/` **importa** `app/`: `tools/workbook_seed/canonical.py`, `interblock.py` e `seeds.py` importam `app.domain`, `app.engine` etc.
- `app/` **não importa** `tools/`: nenhum `import tools` / `from tools` em `app/`. Isso é verificado por teste (`TAX-02-ARCH`).
- Logo, a única direção de dependência existente é `tools → app`.
  - Fazer `app/` ler `BLOCK_TAXONOMY` criaria o ciclo `app ↔ tools`.
  - Fazer `tools/` ler as faixas de `app/validation` seria possível, mas mudaria a arquitetura da taxonomia, o que está fora do escopo de D-TAX-01/D-TAX-02.
- Não há regra arquitetural escrita nem teste anterior que proíba `app → tools`. O motivo registrado aqui é o que o código mostra: a direção de dependência estabelecida e o ciclo que a inversão criaria.

## 4. Risco

**Divergência futura entre as representações físicas.** Exemplos:
- um bloco é renomeado, incluído ou removido em uma projeção e não na outra;
- uma faixa muda num registry;
- a ordem diverge.

A consequência seria a validação de seeds e a validação de `fonte` dos workbooks discordarem sobre quais blocos existem.

## 5. Mitigação atual

| controle | o que garante |
|---|---|
| `taxonomy_guard.check_projections` (D-TAX-02) | o canônico D-TAX-01 é igual às cinco projeções (três faixas, `BLOCK_TAXONOMY` e a taxonomia do seed) em quantidade (29), nomes, ordem e faixas. Falha se um bloco some ou aparece, se um nome muda, se uma faixa muda ou se a ordem diverge |
| `tests/test_taxonomy_migration_d_tax_01.py` (TAX-01..TAX-03) | 29 blocos, ordem e faixas exatas em todas as fontes |
| `tests/test_taxonomy_d_tax_02.py` | executa `check_current_registry` e prova, com projeções mutadas, que cada tipo de divergência é rejeitado |
| `tests/test_id_ranges_taxonomy_consistency.py` | os três registries de faixas são idênticos entre si |
| `taxonomy_guard.classify` (D-TAX-01) | qualquer mudança nesses arquivos contra os baselines da Stage 3 só é aceita se for provadamente a migração autorizada |

## 6. Solução futura (não implementada)

> Evaluate a shared dependency-free canonical taxonomy representation compatible with the app/tools architectural boundary.

Exemplo de direção possível, a decidir: um artefato de dados neutro (ex.: JSON versionado), lido por `app/` e por `tools/`, sem dependência `app → tools`.

Exige **decisão arquitetural própria**, porque muda a fonte física da taxonomia e os pontos de carga. **Não implementar** sem ela.

## 7. Status

```text
TD-TAX-01: OPEN — dívida arquitetural conhecida e controlada; não bloqueia funcionalidade.
```
