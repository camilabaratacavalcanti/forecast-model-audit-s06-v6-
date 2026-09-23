"""
Extração canônica do workbook `max_ht` (v5) e construção dos seeds.

Este módulo é a ÚNICA fonte da tradução

    planilha `MaxHT` (152 linhas de dados, L3..L154)
    ↓
    modelo canônico
    ↓
    data/seed/max_ht/{variables,parameters,equations,aggregation_rules}.json

Segue exatamente o padrão estabelecido por `tools/energy_seed_builder.py`:

1. Geração/regeneração dos seeds e do snapshot canônico
   (`python -m tools.max_ht_seed_builder --xlsx <path>`), que exige
   `openpyxl` e o arquivo `.xlsx`;

2. Reconciliação permanente (`tests/test_max_ht_seed_reconciliation.py`),
   que NÃO depende do `.xlsx` nem de `openpyxl`: compara os seeds contra
   `data/reference/max_ht/max_ht_v5_extract.json`, o snapshot versionado
   da planilha.

Diferença em relação ao energy_seed_builder: a planilha `MaxHT` (a partir
do v5, já auditado como APTO PARA IMPLEMENTAÇÃO) descreve as agregações
temporais textualmente de forma regular e não ambígua --

    "Somatório <mensal|anual> de todos os resultados diários de '<nome>'"
    "Média <mensal|anual> de todos os resultados diários de '<nome>'"

-- então a detecção de agregação é feita por regex sobre esse padrão, em
vez de uma tabela manual de linhas (`AGGREGATION_SPECS`) como no energy.
Não há `Média Ponderada` no `max_ht`, logo nenhuma regra usa
`weight_variable_id`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


SHEET_NAME = "MaxHT"
HEADER_ROW = 2
FIRST_DATA_ROW = 3
LAST_DATA_ROW = 154

SOURCE_REFERENCE = "descritivo_das_variáveis_MaxHT_v5.xlsx"

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = REPO_ROOT / "data" / "seed" / "max_ht"
SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reference" / "max_ht" / "max_ht_v5_extract.json"
)

DSL_PATTERN = re.compile(
    r"^(Somatório|Média) (mensal|anual) de todos os resultados "
    r"diários de '([^']+)'$"
)

DSL_OPERATION_TO_AGGREGATION_TYPE = {
    "Somatório": "SUM",
    "Média": "AVERAGE",
}


# ============================================================
# 1. Extração
# ============================================================

def extract_rows(xlsx_path: str | Path) -> list[dict]:
    """Lê programaticamente as 152 linhas de dados da aba `MaxHT`."""

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


def parse_dsl(expression) -> tuple[str, str, str] | None:
    """
    Reconhece o padrão DSL de agregação temporal.

    Retorna (aggregation_type, target_frequency, source_name) ou None
    se a expressão não for uma agregação DSL.
    """

    if not expression:
        return None

    match = DSL_PATTERN.match(expression)

    if not match:
        return None

    operation, frequency, source_name = match.groups()

    return (
        DSL_OPERATION_TO_AGGREGATION_TYPE[operation],
        frequency,
        source_name,
    )


# ============================================================
# 2. Modelo canônico
# ============================================================

def build_canonical_model(rows: list[dict]) -> dict:
    """
    Converte as linhas brutas no modelo canônico, atribuindo os IDs
    da faixa reservada ao bloco max_ht (13000-13999) na ordem das
    linhas da planilha.
    """

    entities = []

    next_variable = 13001
    next_parameter = 13001

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

        dsl = parse_dsl(row["expression"])

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
                "dsl": dsl,
            }
        )

    return {"entities": entities}


# ============================================================
# 3. Resolução de nomes -> IDs
# ============================================================

def build_name_index(entities: list[dict]) -> dict:
    """
    Indexa as entidades por nome. Um mesmo `name` pode aparecer em
    várias linhas (frequências diferentes) -- por isso o índice guarda
    a LISTA de entidades, nunca uma só.
    """

    index: dict[str, list[dict]] = {}

    for entity in entities:
        index.setdefault(entity["name"], []).append(entity)

    return index


def resolve_reference(name: str, index: dict, frequency: str) -> str:
    """
    Resolve um nome referenciado por uma equação para o ID da entidade
    correspondente, igual ao energy_seed_builder: o vínculo é feito por
    ID, nunca por nome, e a frequência da equação é decisiva.
    """

    candidates = index.get(name)

    if not candidates:
        raise KeyError(f"Referência não encontrada na planilha: {name}")

    parameters = [c for c in candidates if c["kind"] == "parameter"]

    if parameters:
        if len(parameters) > 1:
            raise ValueError(f"Parâmetro ambíguo: {name}")

        return parameters[0]["entity_id"]

    same_frequency = [c for c in candidates if c["frequency"] == frequency]

    pool = same_frequency or candidates

    if len(pool) > 1:
        # Famílias mensal/anual do max_ht têm DUAS variantes na mesma
        # frequência: a de Somatório (total do período) e a de Média
        # (taxa média do período). Como AVERAGE = SUM / N para a MESMA
        # janela em ambos os operandos de uma razão, SUM/SUM e AVG/AVG
        # produzem o MESMO resultado numérico (o N cancela) -- portanto
        # a escolha entre as duas não altera o valor calculado. Para
        # tornar a tradução determinística, prefere-se a variante SUM
        # (o "total do período"), por ser a leitura mais direta de uma
        # razão período-a-período (ex.: massa total / produção total).
        sums = [c for c in pool if c.get("dsl") and c["dsl"][0] == "SUM"]

        if len(sums) == 1:
            return sums[0]["entity_id"]

        raise ValueError(
            f"Referência ambígua ({name}, frequência {frequency}): "
            + ", ".join(entity["entity_id"] for entity in pool)
        )

    return pool[0]["entity_id"]


def translate_expression(expression: str, index: dict, frequency: str) -> str:
    """
    Reescreve a expressão da planilha (escrita em nomes) para a
    expressão do seed (escrita em IDs), preservando a sintaxe `@Lx`.

    Os nomes são substituídos do mais longo para o mais curto para que
    `a18_l123` não seja quebrado pela substituição de `a18` (não
    existente aqui, mas a mesma proteção do energy_seed_builder).
    """

    translated = expression

    for name in sorted(index, key=len, reverse=True):
        pattern = re.compile(rf"(?<![\w@]){re.escape(name)}\b")

        if not pattern.search(translated):
            continue

        entity_id = resolve_reference(name, index, frequency)

        translated = pattern.sub(entity_id, translated)

    return re.sub(r"\s+", " ", translated).strip()


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
    # A célula `value` do workbook v5 guarda "1.05" como texto (não
    # numérico) nas 4 linhas de parâmetro -- confirmado lendo o tipo
    # bruto da célula via openpyxl. O contrato do seed exige um valor
    # numérico (mesmo tratamento já dado a `version`, também lido como
    # texto e convertido para int); converter para float aqui não
    # altera o dado, apenas sua representação de tipo.
    return [
        {
            "parameter_id": entity["entity_id"],
            "parameter_name": entity["name"],
            "description": entity["description"],
            "unit": entity["unit"],
            "value": float(entity["value"]),
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
    next_equation = 13001

    for entity in entities:
        if entity["kind"] != "variable":
            continue

        if not entity["expression"]:
            continue

        if entity["dsl"] is not None:
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
                ),
                "source_reference": SOURCE_REFERENCE,
                "status": "PUBLISHED",
            }
        )

        next_equation += 1

    return equations


def build_aggregation_rules(entities: list[dict]) -> list[dict]:
    """
    Constrói uma AggregationRule para cada linha cuja expressão é uma
    agregação DSL (`dsl` != None), resolvendo a variável de origem pelo
    `source_name` extraído do texto e pela frequência diária -- a
    frequência-base de toda agregação temporal do bloco.
    """

    index = build_name_index(entities)

    rules = []

    for entity in entities:
        if entity["kind"] != "variable" or entity["dsl"] is None:
            continue

        aggregation_type, target_frequency, source_name = entity["dsl"]

        assert target_frequency == entity["frequency"], (
            entity["name"],
            target_frequency,
            entity["frequency"],
        )

        source_id = resolve_reference(source_name, index, "diário")

        scope_label = (
            "GRUPO" if entity["scope_type"] == "linha_grupo" else "LINHA"
        )

        rule_id = (
            "AGR-MAX_HT-"
            f"{entity['name'].upper()}-"
            f"{scope_label}-{entity['scope_value']}-"
            f"{'MENSAL' if target_frequency == 'mensal' else 'ANUAL'}-"
            f"{aggregation_type}"
        )

        rules.append(
            {
                "aggregation_rule_id": rule_id,
                "source_variable_id": source_id,
                "source_frequency": "diário",
                "target_variable_id": entity["entity_id"],
                "target_frequency": target_frequency,
                "aggregation_type": aggregation_type,
            }
        )

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
        description="Gera os seeds do bloco max_ht a partir do workbook v5.",
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
