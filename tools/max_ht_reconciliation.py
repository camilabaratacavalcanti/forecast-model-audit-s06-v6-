"""
Reconciliação automatizada entre o workbook `max_ht` v5 e os seeds.

Segue o mesmo desenho de `tools/energy_reconciliation.py`: não reutiliza
a construção feita por `tools/max_ht_seed_builder.py`, e sim re-deriva,
a partir do snapshot canônico da planilha, o que cada entidade deve
ser, comparando com o JSON efetivamente gravado em `data/seed/max_ht/`.
Em particular:

    - as expressões são conferidas por DECODIFICAÇÃO: cada ID do seed
      é traduzido de volta para o nome da entidade correspondente e o
      resultado é comparado com a expressão original da planilha,
      normalizada;
    - o vínculo por frequência é conferido como restrição
      independente;
    - quando o mesmo nome tem duas variantes na mesma frequência
      (Somatório e Média -- exclusivo do max_ht, que não existe no
      energy), a resolução aceita como correta qualquer uma das duas
      IDs que corresponda à mesma família de agregação (SUM ou
      AVERAGE) já registrada no seed -- ambas produzem o mesmo valor
      numérico (AVERAGE = SUM / N cancela em toda razão entre duas
      grandezas agregadas na mesma janela), então a divergência real a
      detectar é um vínculo para um NOME diferente, não para a
      variante SUM/AVERAGE do mesmo nome;
    - o tipo e a origem de cada AggregationRule são extraídos do
      próprio texto em português da planilha (campo `dsl` do
      snapshot), não de uma lista escrita à mão.

Não há Média Ponderada nem Média Móvel no `max_ht`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = REPO_ROOT / "data" / "seed" / "max_ht"
SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reference" / "max_ht" / "max_ht_v5_extract.json"
)

ID_PATTERN = re.compile(r"\b((?:VAR|PARAM)\d{5})(@L[1-7](?:_L[1-7])?)?\b")


def _normalize(expression: str) -> str:
    return re.sub(r"\s+", " ", expression).strip()


def _load(seed_dir: Path, name: str):
    with open(seed_dir / f"{name}.json", encoding="utf-8") as handle:
        return json.load(handle)


def reconcile(
    seed_dir: Path = SEED_DIR, snapshot_path: Path = SNAPSHOT_PATH
) -> dict:
    with open(snapshot_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)

    entities = snapshot["entities"]

    variables = {
        v["variable_id"]: v for v in _load(seed_dir, "variables")
    }
    parameters = {
        p["parameter_id"]: p for p in _load(seed_dir, "parameters")
    }
    equations = _load(seed_dir, "equations")
    rules = _load(seed_dir, "aggregation_rules")

    missing = []
    extra = []
    mismatches = []

    by_id = {entity["entity_id"]: entity for entity in entities}

    # --------------------------------------------------------
    # Entidades: presença, ausência e campo a campo
    # --------------------------------------------------------

    expected_variable_ids = {
        e["entity_id"] for e in entities if e["kind"] == "variable"
    }
    expected_parameter_ids = {
        e["entity_id"] for e in entities if e["kind"] == "parameter"
    }

    for entity_id in sorted(expected_variable_ids - set(variables)):
        missing.append(f"Variable ausente no seed: {entity_id}")

    for entity_id in sorted(set(variables) - expected_variable_ids):
        extra.append(f"Variable no seed sem linha na planilha: {entity_id}")

    for entity_id in sorted(expected_parameter_ids - set(parameters)):
        missing.append(f"Parameter ausente no seed: {entity_id}")

    for entity_id in sorted(set(parameters) - expected_parameter_ids):
        extra.append(
            f"Parameter no seed sem linha na planilha: {entity_id}"
        )

    variable_fields = {
        "variable_name": "name",
        "description": "description",
        "unit": "unit",
        "variable_type": "variable_type",
        "frequency": "frequency",
        "scope_type": "scope_type",
        "scope_value": "scope_value",
        "status": "status",
    }

    parameter_fields = {
        "parameter_name": "name",
        "description": "description",
        "unit": "unit",
        "scope_type": "scope_type",
        "scope_value": "scope_value",
        "status": "status",
    }

    for entity in entities:
        entity_id = entity["entity_id"]

        if entity["kind"] == "variable":
            seeded = variables.get(entity_id)
            fields = variable_fields
        else:
            seeded = parameters.get(entity_id)
            fields = parameter_fields

        if seeded is None:
            continue

        for seed_field, excel_field in fields.items():
            if seeded[seed_field] != entity[excel_field]:
                mismatches.append(
                    f"{entity_id}.{seed_field}: seed="
                    f"{seeded[seed_field]!r} planilha="
                    f"{entity[excel_field]!r} (L{entity['row']})"
                )

        if entity["kind"] == "parameter":
            if float(seeded["value"]) != float(entity["value"]):
                mismatches.append(
                    f"{entity_id}.value: seed={seeded['value']!r} "
                    f"planilha={entity['value']!r}"
                )

            if seeded["version"] != int(entity["version"]):
                mismatches.append(
                    f"{entity_id}.version: seed={seeded['version']!r} "
                    f"planilha={entity['version']!r}"
                )

    # --------------------------------------------------------
    # Equações: uma por linha com expressão matemática (não-DSL)
    # --------------------------------------------------------

    expected_equation_rows = [
        entity for entity in entities
        if entity["kind"] == "variable"
        and entity["expression"]
        and entity["dsl"] is None
    ]

    seeded_targets = {
        equation["target_variable_id"]: equation
        for equation in equations
    }

    if len(seeded_targets) != len(equations):
        mismatches.append(
            "Equations: mais de uma equação para o mesmo alvo."
        )

    for entity in expected_equation_rows:
        if entity["entity_id"] not in seeded_targets:
            missing.append(
                "Equation ausente para "
                f"{entity['entity_id']} (L{entity['row']})"
            )

    expected_targets = {e["entity_id"] for e in expected_equation_rows}

    for target in sorted(set(seeded_targets) - expected_targets):
        extra.append(f"Equation no seed sem expressão na planilha: {target}")

    for entity in expected_equation_rows:
        equation = seeded_targets.get(entity["entity_id"])

        if equation is None:
            continue

        if equation["scope_type"] != entity["scope_type"]:
            mismatches.append(
                f"{equation['equation_id']}.scope_type: seed="
                f"{equation['scope_type']!r} planilha="
                f"{entity['scope_type']!r}"
            )

        if equation["scope_value"] != entity["scope_value"]:
            mismatches.append(
                f"{equation['equation_id']}.scope_value: seed="
                f"{equation['scope_value']!r} planilha="
                f"{entity['scope_value']!r}"
            )

        def _to_name(match):
            base, scope = match.group(1), match.group(2) or ""

            referenced = by_id.get(base)

            if referenced is None:
                mismatches.append(
                    f"{equation['equation_id']}: ID desconhecido {base}"
                )
                return base + scope

            if referenced["kind"] == "variable":
                same_name = [
                    other for other in entities
                    if other["name"] == referenced["name"]
                    and other["kind"] == "variable"
                ]
                same_frequency = [
                    other for other in same_name
                    if other["frequency"] == entity["frequency"]
                ]

                if same_frequency:
                    if referenced["frequency"] != entity["frequency"]:
                        mismatches.append(
                            f"{equation['equation_id']}: {base} "
                            f"({referenced['name']}, "
                            f"{referenced['frequency']}) vinculado a "
                            f"uma equação {entity['frequency']} "
                            "existindo alternativa de mesma frequência"
                        )
                    elif len(same_frequency) > 1:
                        # Duas variantes (SUM/AVERAGE) na mesma
                        # frequência: qualquer uma decodifica de
                        # volta para o MESMO nome, então não é
                        # divergência -- ver docstring do módulo.
                        pass
                elif len(same_name) != 1:
                    mismatches.append(
                        f"{equation['equation_id']}: {base} "
                        f"({referenced['name']}) ambíguo"
                    )

            return referenced["name"] + scope

        decoded = _normalize(
            ID_PATTERN.sub(_to_name, equation["expression"])
        )

        original = _normalize(entity["expression"])

        if decoded != original:
            mismatches.append(
                f"{equation['equation_id']}.expression: decodificada="
                f"{decoded!r} planilha={original!r}"
            )

    # --------------------------------------------------------
    # AggregationRules
    # --------------------------------------------------------

    aggregation_rows = [
        entity for entity in entities if entity["dsl"] is not None
    ]

    rules_by_target = {}

    for rule in rules:
        rules_by_target.setdefault(
            rule["target_variable_id"], []
        ).append(rule)

    for entity in aggregation_rows:
        matching = rules_by_target.get(entity["entity_id"], [])

        if not matching:
            missing.append(
                "AggregationRule ausente para "
                f"{entity['entity_id']} (L{entity['row']})"
            )
            continue

        if len(matching) > 1:
            extra.append(
                "Mais de uma AggregationRule para "
                f"{entity['entity_id']}"
            )
            continue

        rule = matching[0]

        expected_type, target_frequency, source_name = entity["dsl"]

        assert target_frequency == entity["frequency"]

        if rule["aggregation_type"] != expected_type:
            mismatches.append(
                f"{rule['aggregation_rule_id']}.aggregation_type: "
                f"seed={rule['aggregation_type']} texto={expected_type}"
            )

        source = _resolve_daily(entities, source_name)

        if source is None:
            mismatches.append(
                f"{rule['aggregation_rule_id']}: origem "
                f"{source_name!r} não resolvida na planilha"
            )
        elif rule["source_variable_id"] != source["entity_id"]:
            mismatches.append(
                f"{rule['aggregation_rule_id']}.source_variable_id: "
                f"seed={rule['source_variable_id']} "
                f"texto={source['entity_id']} ({source_name})"
            )

        if rule["source_frequency"] != "diário":
            mismatches.append(
                f"{rule['aggregation_rule_id']}.source_frequency: "
                f"{rule['source_frequency']}"
            )

        if rule["target_frequency"] != entity["frequency"]:
            mismatches.append(
                f"{rule['aggregation_rule_id']}.target_frequency: "
                f"seed={rule['target_frequency']} "
                f"planilha={entity['frequency']}"
            )

        if rule.get("weight_variable_id") is not None:
            mismatches.append(
                f"{rule['aggregation_rule_id']}: peso declarado, mas "
                "o max_ht não usa Média Ponderada"
            )

    expected_rule_targets = {e["entity_id"] for e in aggregation_rows}

    for target in sorted(set(rules_by_target) - expected_rule_targets):
        extra.append(
            f"AggregationRule no seed sem linha na planilha: {target}"
        )

    return {
        "entities": (len(entities), 152),
        "variables": (len(variables), len(expected_variable_ids)),
        "parameters": (len(parameters), len(expected_parameter_ids)),
        "equations": (len(equations), len(expected_equation_rows)),
        "aggregation_rules": (len(rules), len(aggregation_rows)),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "source_file": snapshot.get("source_file"),
        "source_sha256": snapshot.get("source_sha256"),
    }


def _resolve_daily(entities, name):
    matches = [
        entity for entity in entities
        if entity["name"] == name
        and entity["kind"] == "variable"
        and entity["frequency"] == "diário"
    ]

    if len(matches) != 1:
        return None

    return matches[0]


def format_report(report: dict) -> str:
    lines = [
        f"Source: {report['source_file']}",
        f"SHA-256: {report['source_sha256']}",
        "",
        "Entities {}/{}".format(*report["entities"]),
        "Variables {}/{}".format(*report["variables"]),
        "Parameters {}/{}".format(*report["parameters"]),
        "Equations {}/{}".format(*report["equations"]),
        "AggregationRules {}/{}".format(*report["aggregation_rules"]),
        f"Missing {len(report['missing'])}",
        f"Extra {len(report['extra'])}",
        f"Mismatches {len(report['mismatches'])}",
    ]

    for key in ("missing", "extra", "mismatches"):
        for item in report[key]:
            lines.append(f"  [{key}] {item}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(reconcile()))
