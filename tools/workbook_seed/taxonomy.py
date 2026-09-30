"""
Taxonomia oficial de blocos — registro canônico de 29 blocos (D-TAX-01).

Lista normativa dos nomes de bloco, na ordem canônica fixada pelo
proprietário (D-TAX-01, posterior ao fechamento da Stage 3). É a MESMA
lista, na mesma ordem, das faixas de ID por bloco
(`app.validation.*_seed_validator.*_ID_RANGES`): cada bloco tem a sua
faixa de 1000 IDs, de `maintenance` (10000–10999) a `shared`
(38000–38999). A igualdade é verificada por teste
(tests/test_taxonomy_migration_d_tax_01.py).

É independente dos workbooks carregados: um bloco pode ser conhecido e
não estar carregado. Três perguntas distintas:

    1. o nome pertence à taxonomia?        (BLOCK_TAXONOMY)
    2. o workbook do bloco está carregado? (tools.workbook_seed.blocks.BLOCKS)
    3. existe produtor concreto no bloco?  (resolução interbloco)

Os nomes são comparados como texto exato: sem case folding, sem strip,
sem remoção de prefixo, sem alias.

O título canônico de um bloco é o mesmo na taxonomia, no identificador
de código (`tools.workbook_seed.blocks.BLOCKS`), nos seeds/manifestos e
nas células `fonte` (D26B-02, Etapa 2.6C: `max_ht`; `mx_ht` não é
oficial nem sinônimo).

Nota histórica: até D-TAX-01 esta lista era a taxonomia D26-01 (Etapa
2.6B), com 28 nomes em português e ordem própria, distinta das faixas
de ID. O estado normativo atual é o registro de 29 blocos abaixo; a
faixa 30000–30999 chama-se `thickener_flocculant`.
"""

from __future__ import annotations


BLOCK_TAXONOMY: tuple[str, ...] = (
    "maintenance",
    "yield",
    "production",
    "max_ht",
    "alumina",
    "temperature_lp",
    "area_41",
    "area_04_13",
    "energy",
    "boilers",
    "volume",
    "soda",
    "residue_factor",
    "condensate_flow",
    "forecast_volume",
    "full_volume_target",
    "empty_space_target_control",
    "lime",
    "hydrated_flocculant",
    "sludge_flocculant",
    "thickener_flocculant",
    "acid",
    "budget_cost",
    "budget_forecast_cost",
    "actual_forecast_cost",
    "budget",
    "forecast",
    "budget_vs_forecast",
    "shared",
)

OFFICIAL_BLOCKS = frozenset(BLOCK_TAXONOMY)


def is_official(name) -> bool:
    return isinstance(name, str) and name in OFFICIAL_BLOCKS


__all__ = [
    "BLOCK_TAXONOMY",
    "OFFICIAL_BLOCKS",
    "is_official",
]
