"""
Stage 5A — análise interbloco independente da 2.6C reaplicada ao conteúdo vigente (energy v9, max_ht v13).

    python audit/stage5a/analysis_interblock_5a.py [--no-write]

O script da 2.6C (`audit/stage2_6c_interblock_final/evidence/analysis_stage2_6c.py`) é evidência de
stage anterior e NÃO é alterado. Ele fixa como dado os workbooks oficiais da época (energy v6,
MaxHT v10) e a lista exata de IDs novos/aposentados desde a126e02. Este wrapper lê o texto do script,
troca SOMENTE essas constantes de conteúdo (lista `SUBSTITUTIONS`, cada uma exigida exatamente uma
vez) e executa a mesma lógica — nenhuma verificação é removida ou afrouxada; a lista de IDs novos e
aposentados continua exata (C: conteúdo vigente da 5A, conforme `STAGE_5A_DECISION_CONTRACT.md` §4).

A versão histórica é preservada como H: o script 2.6C original roda num clone em `e262e03`
(teste `test_17b` em `tests/test_stage2_6c_interblock_final.py`).

Sem `--no-write`, as saídas vão para `audit/stage5a/evidence/analysis_interblock_5a/` (nunca para a 2.6C).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ORIGINAL = REPO / "audit" / "stage2_6c_interblock_final" / "evidence" / "analysis_stage2_6c.py"
OUT = HERE / "evidence" / "analysis_interblock_5a"

SUBSTITUTIONS = (
    # D-5A: workbooks oficiais vigentes (blocks.py, Stage 5A.2b).
    ('''    "energy": ("descritivo_das_variáveis_energy_v6.xlsx", "energy",
               "cfc46031fc2f3f375b87ebbba58676d23ad92f3ee43fb81b353fe5a8247e1df8"),''',
     '''    "energy": ("descritivo_das_variáveis_energy_v9.xlsx", "energy",
               "731f71e9ab3850fef29ed384230aef37bc2c08a656cbf441f5eada9900973de2"),'''),
    ('''    "max_ht": ("descritivo_das_variáveis_MaxHT_v10.xlsx", "MaxHT",
               "3e40aab12ec0ec07918c5e358145b09f138663f635ca9e7fc0990d1b765b683b"),''',
     '''    "max_ht": ("descritivo_das_variáveis_MaxHT_v13.xlsx", "MaxHT",
               "c9818920b3994ae6aaeef5f237e59dd94d8e1b8647f0bf64426fb5f3d9f0aa98"),'''),
    # Contrato 5A §4: +VAR18053 (energy), +VAR13117..VAR13123 e VAR13001..VAR13006 aposentados (max_ht).
    ('check(new_ids == [("production", "lth_meta", "VAR12066")], ',
     'check(new_ids == EXPECTED_NEW_5A, '),
    ('check(retired_ids == [("production", "lth_meta", "PARAM12003")], ',
     'check(retired_ids == EXPECTED_RETIRED_5A, '),
    # Saídas da 5A no diretório da 5A (a evidência 2.6C nunca é regravada).
    ('HERE = Path(__file__).resolve().parent\nROOT = HERE.parent\n',
     'HERE = OUT_5A\nROOT = OUT_5A\n'),
    ('REPO = HERE.parents[2]\n', 'REPO = REPO_5A\n'),
)


def source() -> str:
    text = ORIGINAL.read_text(encoding="utf-8")
    for old, new in SUBSTITUTIONS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"substituição 5A não aplicável ({count} ocorrências): {old[:80]!r}")
        text = text.replace(old, new)
    return text


# Ordem = ordem de saída da análise (bloco, depois identidade como texto). Exata: nada a mais, nada a menos.
EXPECTED_NEW_5A = [
    ("energy", "retirada_total_condensado_area13", "VAR18053"),   # energy v9: entrada de area_04_13
    ("max_ht", "alimentacao_evap", "VAR13117"),                   # max_ht v13: renomeação (D-5A-3)
    ("max_ht", "alimentacao_evap", "VAR13119"),
    ("max_ht", "alimentacao_evap", "VAR13118"),
    ("max_ht", "alimentacao_evap_total", "VAR13121"),
    ("max_ht", "alimentacao_evap_total", "VAR13120"),
    ("max_ht", "alimentacao_evap_total", "VAR13122"),
    ("max_ht", "lth_total_ag", "VAR13123"),                       # max_ht v13: origem diária do SUM (D-5A-2)
    ("production", "lth_meta", "VAR12066"),                       # 2.6B (D26-02), inalterado
]
EXPECTED_RETIRED_5A = [
    ("max_ht", "alimentação_evap", "VAR13001"),                   # D-5A-3: nome antigo aposentado
    ("max_ht", "alimentação_evap", "VAR13003"),
    ("max_ht", "alimentação_evap", "VAR13002"),
    ("max_ht", "alimentação_evap_total", "VAR13005"),
    ("max_ht", "alimentação_evap_total", "VAR13004"),
    ("max_ht", "alimentação_evap_total", "VAR13006"),
    ("production", "lth_meta", "PARAM12003"),                     # 2.6B (D26-02), inalterado
]


def main() -> None:
    if "--no-write" not in sys.argv[1:]:
        OUT.mkdir(parents=True, exist_ok=True)
    namespace = {"__name__": "__main__", "__file__": str(ORIGINAL),
                 "OUT_5A": OUT, "REPO_5A": REPO,
                 "EXPECTED_NEW_5A": EXPECTED_NEW_5A, "EXPECTED_RETIRED_5A": EXPECTED_RETIRED_5A}
    exec(compile(source(), str(ORIGINAL), "exec"), namespace)


if __name__ == "__main__":
    main()
