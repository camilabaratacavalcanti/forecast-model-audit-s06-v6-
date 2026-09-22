"""
Consistência da taxonomia oficial de blocos entre os três
registries de ID (`VARIABLE_ID_RANGES`, `PARAMETER_ID_RANGES`,
`EQUATION_ID_RANGES`).

O projeto usa a mesma segmentação numérica de blocos nos três
registries -- confirmado empiricamente pelos seeds reais (yield,
production, energy usam a MESMA faixa nos três tipos de entidade).
Este módulo formaliza essa convenção como contrato e prova, com os
IDs reais existentes no repositório, que a expansão da taxonomia
para 28 blocos (introdução de `max_ht`, remoção de `hydrate`/`costs`,
realocação de `shared`) não afetou a classificação de nenhum ID já
existente.

Não depende de seeds sintéticos: lê diretamente `data/seed/`.
"""

import json
from pathlib import Path

from app.validation.equation_seed_validator import EQUATION_ID_RANGES
from app.validation.parameter_seed_validator import (
    PARAMETER_ID_RANGES,
)
from app.validation.variable_seed_validator import VARIABLE_ID_RANGES

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"

# Blocos com seeds reais no repositório no momento desta auditoria.
# Qualquer bloco novo (energy incluído) que ganhe seeds no futuro
# passa a ser coberto automaticamente por este teste, pois a
# descoberta abaixo itera `SEED_ROOT`, não uma lista fixa.


def _numeric_suffix(entity_id: str) -> int:
    digits = "".join(ch for ch in entity_id if ch.isdigit())
    return int(digits)


def _real_blocks_with_seeds():
    return sorted(
        p.name for p in SEED_ROOT.iterdir() if p.is_dir()
    )


def test_at_least_the_three_consolidated_blocks_have_seed_data():
    """
    Pré-condição do teste de compatibilidade abaixo: se yield,
    production e energy deixassem de existir como diretórios de
    seed, o teste de compatibilidade passaria vazio e silenciosamente
    -- o que mascararia uma regressão grave. Esta asserção garante
    que a prova de compatibilidade é exercida de verdade.
    """

    blocks = set(_real_blocks_with_seeds())
    assert {"yield", "production", "energy"} <= blocks


def test_the_three_id_range_registries_are_identical():
    """
    Contrato explícito da convenção descoberta na auditoria: o
    projeto usa a MESMA segmentação de blocos e as MESMAS faixas
    numéricas para VariableId, ParameterId e EquationId. Uma
    divergência futura entre os três catálogos quebra este teste.
    """

    assert VARIABLE_ID_RANGES == PARAMETER_ID_RANGES
    assert PARAMETER_ID_RANGES == EQUATION_ID_RANGES


def test_every_real_variable_id_still_falls_in_its_block_range():
    checked = 0

    for block in _real_blocks_with_seeds():
        path = SEED_ROOT / block / "variables.json"

        if not path.exists():
            continue

        minimum, maximum = VARIABLE_ID_RANGES[block]

        for variable in json.loads(path.read_text(encoding="utf-8")):
            number = _numeric_suffix(variable["variable_id"])
            assert minimum <= number <= maximum, (
                f"{variable['variable_id']} (bloco {block}) fora "
                f"da faixa {minimum}-{maximum}"
            )
            checked += 1

    assert checked > 0


def test_every_real_parameter_id_still_falls_in_its_block_range():
    checked = 0

    for block in _real_blocks_with_seeds():
        path = SEED_ROOT / block / "parameters.json"

        if not path.exists():
            continue

        minimum, maximum = PARAMETER_ID_RANGES[block]

        for parameter in json.loads(path.read_text(encoding="utf-8")):
            number = _numeric_suffix(parameter["parameter_id"])
            assert minimum <= number <= maximum, (
                f"{parameter['parameter_id']} (bloco {block}) fora "
                f"da faixa {minimum}-{maximum}"
            )
            checked += 1

    assert checked > 0


def test_every_real_equation_id_still_falls_in_its_block_range():
    checked = 0

    for block in _real_blocks_with_seeds():
        path = SEED_ROOT / block / "equations.json"

        if not path.exists():
            continue

        minimum, maximum = EQUATION_ID_RANGES[block]

        for equation in json.loads(path.read_text(encoding="utf-8")):
            number = _numeric_suffix(equation["equation_id"])
            assert minimum <= number <= maximum, (
                f"{equation['equation_id']} (bloco {block}) fora "
                f"da faixa {minimum}-{maximum}"
            )
            checked += 1

    assert checked > 0


def test_no_real_id_belongs_to_hydrate_or_costs():
    """
    `hydrate` e `costs` não existem mais como blocos -- nenhum ID
    real pode depender deles. Como nenhum diretório de seed se chama
    `hydrate` ou `costs`, a prova é estrutural: eles simplesmente não
    aparecem em `_real_blocks_with_seeds()`.
    """

    blocks = set(_real_blocks_with_seeds())
    assert "hydrate" not in blocks
    assert "costs" not in blocks


def test_yield_production_energy_ranges_are_unchanged_by_the_migration():
    """
    Os três blocos com implementação consolidada mantiveram
    exatamente as mesmas faixas antes e depois da expansão da
    taxonomia -- nenhuma renumeração foi necessária.
    """

    unchanged = {
        "yield": (11000, 11999),
        "production": (12000, 12999),
        "energy": (18000, 18999),
    }

    for block, expected_range in unchanged.items():
        assert VARIABLE_ID_RANGES[block] == expected_range
        assert PARAMETER_ID_RANGES[block] == expected_range
        assert EQUATION_ID_RANGES[block] == expected_range
