"""
Extração canônica do workbook `energy` (v2) e construção dos seeds.

Este módulo é a ÚNICA fonte da tradução

    planilha `energy` (56 linhas de dados, L3..L58)
    ↓
    modelo canônico
    ↓
    data/seed/energy/{variables,parameters,equations,aggregation_rules}.json

Ele é usado em dois momentos distintos:

1. Geração/regeneração dos seeds e do snapshot canônico
   (`python -m tools.energy_seed_builder --xlsx <path>`), que exige
   `openpyxl` e o arquivo `.xlsx`;

2. Reconciliação permanente (`tests/test_energy_seed_reconciliation.py`),
   que NÃO depende do `.xlsx` nem de `openpyxl`: compara os seeds contra
   `data/reference/energy/energy_v2_extract.json`, o snapshot versionado
   da planilha.

A separação existe porque o `.xlsx` é um insumo externo, não um artefato
do repositório: manter a suíte dependente dele tornaria a reconciliação
inexecutável em qualquer ambiente que não tenha o upload original. O
snapshot preserva a rastreabilidade (inclui o SHA-256 do arquivo lido)
sem essa dependência.

A aba `Planilha1` é auxiliar (descrições propostas) e NÃO gera entidades.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.engine import reference_resolver


SHEET_NAME = "energy"
HEADER_ROW = 2
FIRST_DATA_ROW = 3
LAST_DATA_ROW = 58

SOURCE_REFERENCE = "descritivo_das_variáveis_energy_v2.xlsx"

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = REPO_ROOT / "data" / "seed" / "energy"
SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reference" / "energy" / "energy_v2_extract.json"
)

# Marcador textual das linhas cuja "expressão" é, na verdade, a
# descrição de uma agregação temporal — e não uma expressão executável.
AGGREGATION_MARKERS = (
    "Média móvel",
    "Média mensal",
    "Média Ponderada mensal",
)


# ============================================================
# 1. Extração
# ============================================================

def extract_rows(xlsx_path: str | Path) -> list[dict]:
    """Lê programaticamente as 56 linhas de dados da aba `energy`."""

    import openpyxl

    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = workbook[SHEET_NAME]

    header = [cell.value for cell in sheet[HEADER_ROW]]

    rows = []

    for row_number in range(FIRST_DATA_ROW, LAST_DATA_ROW + 1):
        values = [
            sheet.cell(row=row_number, column=column).value
            for column in range(1, len(header) + 1)
        ]

        row = dict(zip(header, values))
        row["row"] = row_number

        rows.append(row)

    return rows


def is_aggregation_expression(expression) -> bool:
    if not expression:
        return False

    return any(
        marker in expression for marker in AGGREGATION_MARKERS
    )


# ============================================================
# 2. Modelo canônico
# ============================================================

def build_canonical_model(rows: list[dict]) -> dict:
    """
    Converte as linhas brutas no modelo canônico, atribuindo os IDs
    da faixa reservada ao bloco energy (18000-18999) na ordem das
    linhas da planilha.
    """

    entities = []

    next_variable = 18001
    next_parameter = 18001

    for row in rows:
        row_type = (row["Type"] or "").strip()

        if row_type == "parameter":
            entity_id = f"PARAM{next_parameter}"
            next_parameter += 1
            kind = "parameter"
        else:
            entity_id = f"VAR{next_variable}"
            next_variable += 1
            kind = "variable"

        entities.append(
            {
                "row": row["row"],
                "kind": kind,
                "entity_id": entity_id,
                "excel_type": row_type,
                "name": row["name"],
                "description": row["description"],
                "unit": row["unit"],
                "value": row["value"],
                "version": row["version"],
                "variable_type": row["variable_type"],
                "frequency": row["frequency"],
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "status": row["status"],
                "expression": row["expression"],
                "fonte": row["fonte"],
                "is_aggregation": is_aggregation_expression(
                    row["expression"]
                ),
            }
        )

    return {"entities": entities}


# ============================================================
# 3. Resolução de nomes -> IDs
# ============================================================
#
# A resolução é a da plataforma (nome + frequência + escopo, ver
# app/engine/reference_resolver.py) — este builder não mantém uma
# lógica própria de vínculo.


def build_name_index(entities: list[dict]) -> dict:
    return reference_resolver.build_name_index(entities)


def resolve_reference(
    name: str,
    index: dict,
    frequency: str,
    consumer_scope: tuple[str, str | None] | None = None,
) -> str:
    return reference_resolver.resolve_reference(
        name, index, frequency, consumer_scope=consumer_scope,
    )


def translate_expression(
    expression: str,
    index: dict,
    frequency: str,
    consumer_scope: tuple[str, str | None] | None = None,
) -> str:
    return reference_resolver.translate_expression(
        expression, index, frequency, consumer_scope=consumer_scope,
    )


# ============================================================
# 4. Seeds
# ============================================================

def build_variables(entities: list[dict]) -> list[dict]:
    return [
        {
            "variable_id": entity["entity_id"],
            "variable_name": entity["name"],
            "description": entity["description"],
            "unit": entity["unit"],
            "variable_type": entity["variable_type"],
            "frequency": entity["frequency"],
            "scope_type": entity["scope_type"],
            "scope_value": entity["scope_value"],
            "source_reference": SOURCE_REFERENCE,
            "status": entity["status"],
        }
        for entity in entities
        if entity["kind"] == "variable"
    ]


def build_parameters(entities: list[dict]) -> list[dict]:
    return [
        {
            "parameter_id": entity["entity_id"],
            "parameter_name": entity["name"],
            "description": entity["description"],
            "unit": entity["unit"],
            "value": entity["value"],
            "version": int(entity["version"]),
            "scope_type": entity["scope_type"],
            "scope_value": entity["scope_value"],
            "source_reference": SOURCE_REFERENCE,
            "status": entity["status"],
        }
        for entity in entities
        if entity["kind"] == "parameter"
    ]


def build_equations(entities: list[dict]) -> list[dict]:
    index = build_name_index(entities)

    equations = []
    next_equation = 18001

    for entity in entities:
        if entity["kind"] != "variable":
            continue

        if not entity["expression"]:
            continue

        if entity["is_aggregation"]:
            continue

        equations.append(
            {
                "equation_id": f"EQ{next_equation}",
                "target_variable_id": entity["entity_id"],
                "version": 1,
                "scope_type": entity["scope_type"],
                "scope_value": entity["scope_value"],
                "expression": translate_expression(
                    entity["expression"],
                    index,
                    entity["frequency"],
                    consumer_scope=(
                        entity["scope_type"],
                        entity["scope_value"],
                    ),
                ),
                "source_reference": SOURCE_REFERENCE,
                "status": "PUBLISHED",
            }
        )

        next_equation += 1

    return equations


# Agregações temporais declaradas textualmente na planilha.
#
# A planilha descreve a agregação em português; a tradução para
# (source, aggregation_type, weight) é feita aqui, linha a linha, e é
# verificada pela reconciliação. `producao_planta_t_h` é o peso de toda
# média ponderada do bloco — é a produção horária da planta, a grandeza
# pela qual todos os consumos específicos são ponderados.
WEIGHT_NAME = "producao_planta_t_h"

AGGREGATION_SPECS = {
    # target_row: (source_row, aggregation_type, weight_row | None)
    6: (5, "MOVING_AVERAGE", None),
    27: (26, "AVERAGE", None),
    29: (28, "AVERAGE", None),
    32: (31, "WEIGHTED_AVERAGE", 5),
    34: (33, "WEIGHTED_AVERAGE", 5),
    45: (44, "WEIGHTED_AVERAGE", 5),
    47: (46, "WEIGHTED_AVERAGE", 5),
    49: (48, "WEIGHTED_AVERAGE", 5),
    54: (53, "WEIGHTED_AVERAGE", 5),
    57: (56, "AVERAGE", None),
    58: (56, "WEIGHTED_AVERAGE", 5),
}


def build_aggregation_rules(entities: list[dict]) -> list[dict]:
    by_row = {entity["row"]: entity for entity in entities}

    rules = []

    for target_row, spec in sorted(AGGREGATION_SPECS.items()):
        source_row, aggregation_type, weight_row = spec

        target = by_row[target_row]
        source = by_row[source_row]

        scope_label = (
            "GRUPO"
            if target["scope_type"] == "linha_grupo"
            else "LINHA"
        )

        rule = {
            "aggregation_rule_id": (
                "AGR-ENERGY-"
                f"{target['name'].upper()}-"
                f"{scope_label}-{target['scope_value']}-"
                f"{'DIARIO' if target['frequency'] == 'diário' else 'MENSAL'}-"
                f"{aggregation_type}"
            ),
            "source_variable_id": source["entity_id"],
            "source_frequency": source["frequency"],
            "target_variable_id": target["entity_id"],
            "target_frequency": target["frequency"],
            "aggregation_type": aggregation_type,
        }

        if weight_row is not None:
            weight = by_row[weight_row]

            assert weight["name"] == WEIGHT_NAME, weight["name"]

            rule["weight_variable_id"] = weight["entity_id"]

        rules.append(rule)

    return rules


def build_seeds(model: dict) -> dict:
    entities = model["entities"]

    return {
        "variables": build_variables(entities),
        "parameters": build_parameters(entities),
        "equations": build_equations(entities),
        "aggregation_rules": build_aggregation_rules(entities),
    }


# ============================================================
# 5. CLI
# ============================================================

def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv=None) -> int:
    import argparse
    import hashlib

    parser = argparse.ArgumentParser(
        description="Gera os seeds do bloco energy a partir do workbook v2.",
    )
    parser.add_argument("--xlsx", required=True)

    args = parser.parse_args(argv)

    xlsx_path = Path(args.xlsx)

    digest = hashlib.sha256(xlsx_path.read_bytes()).hexdigest()

    rows = extract_rows(xlsx_path)
    model = build_canonical_model(rows)

    model["source_file"] = xlsx_path.name
    model["source_sha256"] = digest

    seeds = build_seeds(model)

    _write_json(SNAPSHOT_PATH, model)

    for name, payload in seeds.items():
        _write_json(SEED_DIR / f"{name}.json", payload)

    print(f"source: {xlsx_path.name}")
    print(f"sha256: {digest}")

    for name, payload in seeds.items():
        print(f"{name}: {len(payload)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
