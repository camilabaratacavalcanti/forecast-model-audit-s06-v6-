"""
Projeção do modelo canônico nos seeds da plataforma.

    variables.json          uma definição por entidade (instâncias
                            declaradas em `instances` quando a
                            definição agrupa linhas do workbook)
    parameters.json         um registro por linha do workbook (mesmo
                            parameter_id para as instâncias por linha —
                            modelo da chave composta do
                            ParameterDefinitionRegistry)
    equations.json          uma equação por linha com expressão
                            executável, no escopo da própria linha
    aggregation_rules.json  uma regra por linha com agregação textual
    manifest.json           proveniência: workbook lido (nome, SHA-256,
                            aba, cabeçalho), linhas de cada entidade e
                            decisões contratuais pendentes

Nomes nas expressões são traduzidos para IDs pela resolução da
plataforma (`app.engine.reference_resolver`: nome + frequência +
escopo, instância a instância). Não há desempate próprio do builder:
toda ambiguidade é erro.
"""

from __future__ import annotations

import re

from app.domain.units import required_sum_factor
from app.engine import reference_resolver
from app.engine.scope_resolver import ScopeResolver
from app.engine.scoped_reference import scope_type_for
from app.engine.spatial_candidate_resolver import get_spatial_candidates

from tools.workbook_seed.canonical import (
    CanonicalEntity,
    CanonicalModel,
    CanonicalModelError,
    PendingDecision,
)


SCOPE_LABELS = {
    "linha": "LINHA",
    "linha_grupo": "GRUPO",
    "planta": "PLANTA",
    "área": "AREA",
    "global": "GLOBAL",
}

FREQUENCY_LABELS = {
    "diário": "DIARIO",
    "mensal": "MENSAL",
    "anual": "ANUAL",
}


def source_reference_of(value, model: CanonicalModel) -> str:
    """
    `source_reference` do seed: o valor da célula do workbook quando
    preenchida; vazia, o nome do workbook efetivamente lido.
    """

    return value if value is not None else model.workbook.file_name


def _common(values):
    return values[0] if len(set(values)) == 1 else None


def build_variables(model: CanonicalModel) -> list[dict]:
    variables = []

    for entity in model.entities:
        if entity.kind != "variable":
            continue

        descriptions = [r.description for r in entity.rows]
        references = [r.source_reference for r in entity.rows]

        record = {
            "variable_id": entity.entity_id,
            "variable_name": entity.name,
            "description": _common(descriptions),
            "unit": entity.unit,
            "variable_type": entity.variable_type,
            "frequency": entity.frequency,
            "scope_type": entity.scope_type,
            "scope_value": entity.scope_value,
            "source_reference": source_reference_of(_common(references), model),
            "status": entity.status,
            "value_type": entity.value_type,
        }

        if entity.allowed_values is not None:
            record["allowed_values"] = list(entity.allowed_values)

        if entity.declared_result_states is not None:
            record["declared_result_states"] = [
                {"state": s.state, "literal": s.literal}
                for s in entity.declared_result_states
            ]

        if entity.grouped:
            record["instances"] = [
                {
                    "scope_value": r.scope_value,
                    "description": r.description,
                    "source_reference": source_reference_of(
                        r.source_reference, model
                    ),
                }
                for r in entity.rows
            ]

        variables.append(record)

    return variables


def build_parameters(model: CanonicalModel) -> list[dict]:
    parameters = []

    for entity in model.entities:
        if entity.kind != "parameter":
            continue

        for r in entity.rows:
            parameters.append(
                {
                    "parameter_id": entity.entity_id,
                    "parameter_name": entity.name,
                    "description": r.description,
                    "unit": entity.unit,
                    "value": r.value,
                    "version": r.version,
                    "frequency": entity.frequency,
                    "scope_type": entity.scope_type,
                    "scope_value": r.scope_value,
                    "source_reference": source_reference_of(
                        r.source_reference, model
                    ),
                    "status": entity.status,
                    "value_type": entity.value_type,
                }
            )

    return parameters


def _index(model: CanonicalModel) -> dict:
    return reference_resolver.build_name_index(
        [entity.as_index_entry() for entity in model.entities]
    )


_REFERENCE = re.compile(r"\b(VAR\d+|PARAM\d+)(?:@(L[1-7](?:_L[1-7])?))?")


def unreachable_references(
    model: CanonicalModel,
    expression: str,
    consumer_scope: tuple[str, str],
) -> list[dict]:
    """
    Referências já traduzidas que o runtime não alcança a partir de
    alguma instância do consumidor (nenhuma instância da definição
    referenciada na cadeia espacial linha -> grupo -> planta, ou o
    escopo explícito `@` inexistente). A resolução A019 devolve o único
    candidato por nome mesmo quando nenhum é alcançável; o builder não
    esconde isso: registra a referência como decisão pendente.
    """

    resolver = ScopeResolver()
    by_id = model.by_id()
    problems = []

    for match in _REFERENCE.finditer(expression):
        entity = by_id[match.group(1)]
        explicit = match.group(2)
        instances = set(resolver.resolve_scopes(entity.scope_type, entity.scope_value))

        for consumer_instance in resolver.resolve_scopes(*consumer_scope):
            if explicit:
                reachable = (scope_type_for(explicit), explicit) in instances
            else:
                reachable = any(
                    tuple(candidate) in instances
                    for candidate in get_spatial_candidates(*consumer_instance)
                )

            if not reachable:
                problems.append(
                    {
                        "reference": match.group(0),
                        "name": entity.name,
                        "frequency": entity.frequency,
                        "scope": f"{entity.scope_type}/{entity.scope_value}",
                        "consumer_instance": "/".join(consumer_instance),
                    }
                )
                break

    return problems


def build_equations(model: CanonicalModel, id_base: int) -> tuple[list[dict], list[dict]]:
    index = _index(model)
    equations = []
    provenance = []
    next_id = id_base + 1

    for entity in model.entities:
        if entity.kind != "variable":
            continue

        for r in entity.rows:
            if r.expression is None or r.aggregation is not None:
                continue

            try:
                expression = reference_resolver.translate_expression(
                    r.expression,
                    index,
                    entity.frequency,
                    consumer_scope=(entity.scope_type, r.scope_value),
                )
            except reference_resolver.ReferenceResolutionError as error:
                raise CanonicalModelError(
                    f"{model.workbook.file_name} linha {r.row} "
                    f"({entity.name}): {error}"
                ) from error

            equation_id = f"EQ{next_id}"
            next_id += 1

            for problem in unreachable_references(
                model, expression, (entity.scope_type, r.scope_value)
            ):
                model.pending_decisions.append(
                    PendingDecision(
                        decision_id="R2-A019-UNREACHABLE",
                        row=r.row,
                        name=entity.name,
                        fields={
                            "equation_id": equation_id,
                            "consumer": (
                                f"{entity.name} {entity.frequency} "
                                f"{entity.scope_type}/{r.scope_value}"
                            ),
                            **problem,
                        },
                        reason=(
                            "a resolução nome+frequência+escopo só encontra "
                            "uma definição que nenhuma instância do "
                            "consumidor alcança em runtime; a equação é "
                            "gravada como escrita no workbook e falha de "
                            "forma explícita ao ser avaliada. Requer decisão "
                            "do dono do workbook."
                        ),
                    )
                )

            equations.append(
                {
                    "equation_id": equation_id,
                    "target_variable_id": entity.entity_id,
                    "version": 1,
                    "scope_type": entity.scope_type,
                    "scope_value": r.scope_value,
                    "expression": expression,
                    "source_reference": model.workbook.file_name,
                    "status": "PUBLISHED",
                }
            )
            provenance.append({"equation_id": equation_id, "row": r.row})

    if next_id - 1 > id_base + 999:
        raise CanonicalModelError(f"{model.block}: faixa de EQ esgotada.")

    return equations, provenance


def _resolve_daily(
    model: CanonicalModel,
    index: dict,
    name: str,
    target: CanonicalEntity,
    row: int,
    role: str,
) -> CanonicalEntity:
    try:
        entity_id = reference_resolver.resolve_reference(
            name,
            index,
            "diário",
            consumer_scope=(target.scope_type, target.scope_value),
        )
    except reference_resolver.ReferenceResolutionError as error:
        raise CanonicalModelError(
            f"{model.workbook.file_name} linha {row}: {role} '{name}': {error}"
        ) from error

    entity = model.by_id()[entity_id]

    if entity.kind != "variable" or entity.frequency != "diário":
        raise CanonicalModelError(
            f"{model.workbook.file_name} linha {row}: {role} '{name}' "
            f"resolveu para {entity_id} ({entity.kind}, "
            f"{entity.frequency}); uma agregação temporal exige uma "
            "variável diária."
        )

    return entity


def build_aggregation_rules(model: CanonicalModel) -> tuple[list[dict], list[dict]]:
    index = _index(model)
    rules = []
    provenance = []

    for target in model.entities:
        for r in target.rows:
            spec = r.aggregation

            if spec is None:
                continue

            where = f"{model.workbook.file_name} linha {r.row} ({target.name})"

            if (
                spec.declared_target_frequency is not None
                and spec.declared_target_frequency != target.frequency
            ):
                raise CanonicalModelError(
                    f"{where}: o texto declara frequência "
                    f"{spec.declared_target_frequency!r}, a linha "
                    f"{target.frequency!r}."
                )

            source = _resolve_daily(
                model, index, spec.source_name, target, r.row, "origem"
            )

            rule = {
                "aggregation_rule_id": (
                    f"AGR-{model.block.upper()}-{target.name.upper()}-"
                    f"{SCOPE_LABELS[target.scope_type]}-{target.scope_value}-"
                    f"{FREQUENCY_LABELS[target.frequency]}-{spec.aggregation_type}"
                ),
                "source_variable_id": source.entity_id,
                "source_frequency": spec.source_frequency,
                "target_variable_id": target.entity_id,
                "target_frequency": target.frequency,
                "aggregation_type": spec.aggregation_type,
            }

            if spec.weight_name is not None:
                weight = _resolve_daily(
                    model, index, spec.weight_name, target, r.row, "peso"
                )
                rule["weight_variable_id"] = weight.entity_id

            if spec.aggregation_type == "SUM":
                factor = required_sum_factor(
                    source.unit, target.unit, target.frequency
                )

                if factor is None:
                    raise CanonicalModelError(
                        f"{where}: SUM de {source.unit} para {target.unit} "
                        f"({target.frequency}) não é dimensionalmente coerente."
                    )

                rule["integration_factor"] = factor

            rules.append(rule)
            provenance.append(
                {"aggregation_rule_id": rule["aggregation_rule_id"], "row": r.row}
            )

    ids = [rule["aggregation_rule_id"] for rule in rules]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})

    if duplicated:
        raise CanonicalModelError(
            f"{model.block}: aggregation_rule_id duplicado: {duplicated}."
        )

    return rules, provenance


def build_manifest(
    model: CanonicalModel,
    equation_rows: list[dict],
    rule_rows: list[dict],
) -> dict:
    workbook = model.workbook

    return {
        "block": model.block,
        "workbook": {
            "file_name": workbook.file_name,
            "sha256": workbook.sha256,
            "sheet": workbook.sheet,
            "header_row": workbook.header_row,
            "data_rows": len(workbook.rows),
            "empty_rows_ignored": len(workbook.empty_rows),
            "last_sheet_row": workbook.last_sheet_row,
        },
        "entities": [
            {
                "entity_id": entity.entity_id,
                "kind": entity.kind,
                "name": entity.name,
                "frequency": entity.frequency,
                "scope_type": entity.scope_type,
                "scope_value": entity.scope_value,
                "rows": [r.row for r in entity.rows],
                **(
                    {"source_block": entity.source_block}
                    if entity.source_block is not None
                    else {}
                ),
            }
            for entity in model.entities
        ],
        "equations": equation_rows,
        "aggregation_rules": rule_rows,
        "pending_contract_decisions": [
            {
                "decision_id": p.decision_id,
                "row": p.row,
                "name": p.name,
                "fields": p.fields,
                "reason": p.reason,
            }
            for p in model.pending_decisions
        ],
    }


def build_seeds(model: CanonicalModel, id_base: int) -> dict:
    equations, equation_rows = build_equations(model, id_base)
    rules, rule_rows = build_aggregation_rules(model)

    return {
        "variables": build_variables(model),
        "parameters": build_parameters(model),
        "equations": equations,
        "aggregation_rules": rules,
        "manifest": build_manifest(model, equation_rows, rule_rows),
    }
