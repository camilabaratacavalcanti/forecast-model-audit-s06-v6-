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

Esta taxonomia não substitui as faixas de ID por bloco
(`app.validation.*_seed_validator.*_ID_RANGES`), que usam os
identificadores de código; as divergências entre as duas listas estão
registradas em PENDING_NAMING_DECISIONS e no relatório da Etapa 2.6B —
nenhuma é normalizada aqui.
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
    "mx_ht",
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

# Identificador de código de um bloco carregado que não coincide com a
# taxonomia. Só informa diagnóstico e relatório: NUNCA é usado para
# resolver `fonte` (não é alias).
PENDING_NAMING_DECISIONS: dict[str, dict] = {
    "max_ht": {
        "decision_id": "D26B-02",
        "taxonomy_candidate": "mx_ht",
        "reason": (
            "workbook 'descritivo_das_variáveis_MaxHT_v10.xlsx' (aba 'MaxHT'), "
            "identificador de código 'max_ht' (BLOCKS, faixas de ID, "
            "data/seed/max_ht) e taxonomia oficial 'mx_ht' divergem; nenhum "
            "workbook declara título de bloco. Aguardando decisão do "
            "proprietário."
        ),
    },
}


def is_official(name) -> bool:
    return isinstance(name, str) and name in OFFICIAL_BLOCKS


__all__ = [
    "BLOCK_TAXONOMY",
    "OFFICIAL_BLOCKS",
    "PENDING_NAMING_DECISIONS",
    "is_official",
]
