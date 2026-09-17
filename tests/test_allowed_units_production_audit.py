"""
Auditoria de unidades do bloco Production
(descritivo_das_variáveis_production_v1.xlsx) contra o contrato
global `ALLOWED_UNITS`.

`ALLOWED_UNITS` é um contrato compartilhado por
`variable_seed_validator` e `parameter_seed_validator` -- os dois
conjuntos precisam permanecer idênticos (nenhuma unificação
genérica foi introduzida; os dois `ALLOWED_UNITS` continuam sendo
dicts/sets independentes, cada um no seu módulo, apenas mantidos em
sincronia manualmente, como já era o caso antes desta tarefa).
"""

from app.validation.parameter_seed_validator import (
    ALLOWED_UNITS as PARAMETER_ALLOWED_UNITS,
)
from app.validation.variable_seed_validator import (
    ALLOWED_UNITS as VARIABLE_ALLOWED_UNITS,
    validate_enum_values,
)


# Unidades efetivamente utilizadas pelo bloco Production, extraídas
# do workbook `descritivo_das_variáveis_production_v1.xlsx` durante a
# auditoria (ver relatório da tarefa anterior). `lth_meta` usa "tpd"
# conforme BD-03 (decisão de negócio), não o "-" do workbook bruto.
PRODUCTION_UNITS = {
    "g/l",       # yield, yield_lth_total, pick_up, pick_up_total, pick_up_yield
    "m³/h",      # reducao_lth_*, lth, lth_total
    "h",         # tempo_*
    "%",         # oee, oee_total, consumo_*_percentual, desaguamento_oee
    "-",         # fator_ajuste_lth, fator_producao, fator_ajuste_mrn, fator_mrn, fator_mpsa, fator_cbg
    "tpd",       # producao, producao_planta, producao_planta_movel, consumo_mrn/mpsa/cbg/bauxita, lth_meta (BD-03)
    "Mtpy",      # producao_planta_mtpy
    "dias",      # n_dias_ano
    "kg/t",      # fator_mrn_kg_t, fator_mpsa_kg_t (BD-10)
}

# "tph" aparecia no workbook para desaguamento_produtividade, mas é a
# mesma grandeza física já coberta por "t/h" (convenção de barra já
# estabelecida pelo contrato) -- não foi adicionada como unidade nova
# para evitar duas grafias distintas para o mesmo conceito.
REJECTED_UNIT_VARIANTS = {"tph"}


def test_all_production_units_are_now_allowed():
    missing = PRODUCTION_UNITS - VARIABLE_ALLOWED_UNITS

    assert missing == set(), (
        f"Unidades do Production ainda ausentes de ALLOWED_UNITS: "
        f"{missing}"
    )


def test_variable_and_parameter_allowed_units_stay_in_sync():
    assert VARIABLE_ALLOWED_UNITS == PARAMETER_ALLOWED_UNITS


def test_rejected_unit_variant_is_not_allowed():
    """
    "tph" não deve ter sido adicionado: a plataforma usa "t/h"
    (convenção com barra) para a mesma grandeza -- evita duas
    grafias para o mesmo conceito físico.
    """

    for rejected in REJECTED_UNIT_VARIANTS:
        assert rejected not in VARIABLE_ALLOWED_UNITS
        assert rejected not in PARAMETER_ALLOWED_UNITS

    assert "t/h" in VARIABLE_ALLOWED_UNITS


def test_yield_units_remain_allowed_after_production_additions():
    """
    Regressão: nenhuma unidade usada pelo bloco Yield foi removida
    ou alterada pela auditoria de Production.
    """

    yield_units = {"-", "g/l", "m²/kg", "m³/h", "t", "°C"}

    assert yield_units.issubset(VARIABLE_ALLOWED_UNITS)


def test_new_production_units_pass_variable_enum_validation():
    for unit in PRODUCTION_UNITS:
        variables = [
            {
                "variable_id": "VAR12001",
                "variable_name": "unidade_de_teste",
                "description": "Teste de unidade do bloco Production.",
                "unit": unit,
                "variable_type": "calculado",
                "frequency": "diário",
                "scope_type": "linha",
                "scope_value": "L1_L7",
                "source_reference": "teste",
                "status": "ativo",
            }
        ]

        errors = validate_enum_values(variables)

        assert errors == [], f"unidade {unit!r} deveria ser válida"
