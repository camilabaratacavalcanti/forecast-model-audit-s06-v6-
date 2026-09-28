"""
Taxonomia oficial de blocos (D26-01, Etapa 2.6B).

Lista normativa dos títulos/nomes de bloco fornecida pelo proprietário.
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

Esta taxonomia não substitui as faixas de ID por bloco
(`app.validation.*_seed_validator.*_ID_RANGES`), que são outro registro
e não são alteradas aqui.
"""

from __future__ import annotations


BLOCK_TAXONOMY: tuple[str, ...] = (
    "maintenance",
    "area_04_13",
    "forecast_volume",
    "acido",
    "yield",
    "energy",
    "meta_volume_cheio",
    "custo_budget",
    "production",
    "boilers",
    "controle_espaco_vazio_meta",
    "custo_forecast_bdgt",
    "max_ht",
    "volume",
    "lime_dia",
    "custo_forecast_real",
    "alumina",
    "soda",
    "floculante_hidrato_2026",
    "budget",
    "temperature_lp",
    "fator_residuo",
    "floculante_lama_dia",
    "forecast",
    "area_41",
    "vazao_condensado",
    "premissas_ppt_mensal",
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
