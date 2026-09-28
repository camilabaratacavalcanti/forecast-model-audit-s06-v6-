"""
Modelo canônico: linhas do workbook -> definições com instâncias.

Regras (contrato aprovado na Etapa 2.3):

1. Type: `variable` (sem expressão), `variable / equation` (com
   expressão) ou `parameter` (sem expressão). Outra combinação é erro.

2. Definição com instâncias por escopo. Linhas com o mesmo
   (tipo, name, frequency, scope_type="linha") e scope_value atômico
   (L1..L7) são UMA definição com uma instância por linha — nunca
   N definições distintas. O escopo declarado da definição é a faixa
   contígua coberta (L1..L7 -> "L1_L7"; L4..L7 -> "L4_L7"); linhas
   não contíguas são erro. Os atributos da definição (unit,
   variable_type, value_type, allowed_values, declared_result_states,
   status, fonte) têm de ser iguais em todas as linhas; description,
   source_reference, expressão e valor são por instância.

3. Identidade = name + frequency + scope_type + scope_value, avaliada
   por instância concreta (ScopeResolver). Duas definições que
   materializam a mesma identidade no mesmo workbook são erro.

4. value_type é obrigatório e pertence a {numerico, categorico}, sem
   alias. allowed_values só em categórica. declared_result_states
   (R1) é local: cada literal declarado precisa aparecer na expressão
   da própria linha.

5. Parâmetro: value numérico físico (int/float, nunca bool ou texto)
   e version inteiro — nada é convertido.

6. `value`/`version` preenchidos numa linha Type=variable não têm
   significado definido no contrato (D24-12): não são transportados
   para o domínio nem descartados em silêncio — ficam registrados como
   decisão contratual pendente no manifesto do seed.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from app.domain.values import (
    CATEGORICAL,
    NUMERIC,
    RESULT_STATE_TAXONOMY,
    VALUE_TYPES,
)
from app.engine.scope_resolver import ScopeResolver

from tools.workbook_seed.aggregation_dsl import (
    AggregationSpec,
    looks_like_aggregation,
    parse_aggregation,
)
from tools.workbook_seed.id_ledger import IdLedger, identity_key
from tools.workbook_seed.reader import WorkbookData, WorkbookRow


TYPE_VARIABLE = "variable"
TYPE_EQUATION = "variable / equation"
TYPE_PARAMETER = "parameter"
ROW_TYPES = (TYPE_VARIABLE, TYPE_EQUATION, TYPE_PARAMETER)

LINE_VALUES = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")

# Atributos que definem a definição: iguais em todas as instâncias.
VARIABLE_DEFINITION_FIELDS = (
    "unit",
    "variable_type",
    "value_type",
    "allowed_values",
    "declared_result_states",
    "status",
    "fonte",
)
PARAMETER_DEFINITION_FIELDS = (
    "unit",
    "value_type",
    "status",
    "fonte",
)

STATE_ARROW = " → "


class CanonicalModelError(ValueError):
    """O workbook não pode ser representado sem violar o contrato."""


class IdentityCollisionError(CanonicalModelError):
    """Duas definições materializam a mesma identidade."""


@dataclass(frozen=True)
class DeclaredState:
    state: str
    literal: str


@dataclass(frozen=True)
class CanonicalRow:
    row: int
    scope_value: str
    description: str | None
    source_reference: str | None
    expression: str | None
    value: object
    version: object
    aggregation: AggregationSpec | None


@dataclass(frozen=True)
class CanonicalEntity:
    kind: str  # "variable" | "parameter"
    entity_id: str
    name: str
    frequency: str | None
    scope_type: str
    scope_value: str
    grouped: bool
    unit: str
    variable_type: str | None
    value_type: str
    allowed_values: tuple[str, ...] | None
    declared_result_states: tuple[DeclaredState, ...] | None
    status: str
    fonte: str | None
    rows: tuple[CanonicalRow, ...]

    @property
    def first_row(self) -> int:
        return self.rows[0].row

    @property
    def source_block(self):
        """
        Bloco produtor canônico declarado em `fonte` (Etapa 2.6): o
        texto da célula, sem strip, prefixo removido ou alias. A
        resolução e a validação ficam em `tools.workbook_seed.interblock`.
        """

        return self.fonte

    def as_index_entry(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind,
            "name": self.name,
            "frequency": self.frequency,
            "scope_type": self.scope_type,
            "scope_value": self.scope_value,
        }


@dataclass(frozen=True)
class PendingDecision:
    decision_id: str
    row: int
    name: str
    fields: dict
    reason: str


@dataclass
class CanonicalModel:
    block: str
    workbook: WorkbookData
    entities: list[CanonicalEntity] = field(default_factory=list)
    pending_decisions: list[PendingDecision] = field(default_factory=list)

    def by_id(self) -> dict[str, CanonicalEntity]:
        return {entity.entity_id: entity for entity in self.entities}


# ------------------------------------------------------------
# Células com formato próprio
# ------------------------------------------------------------

def parse_allowed_values(raw, where: str) -> tuple[str, ...] | None:
    """Uma opção por linha da célula; sem strip, sem duplicatas."""

    if raw is None:
        return None

    if not isinstance(raw, str):
        raise CanonicalModelError(
            f"{where}: allowed_values deve ser texto, recebido "
            f"{type(raw).__name__} {raw!r}."
        )

    options = tuple(raw.split("\n"))

    for option in options:
        if not option or option != option.strip():
            raise CanonicalModelError(
                f"{where}: allowed_values com opção vazia ou com espaços "
                f"nas pontas: {option!r} (célula {raw!r})."
            )

    if len(set(options)) != len(options):
        raise CanonicalModelError(
            f"{where}: allowed_values com opção repetida: {raw!r}."
        )

    return options


def parse_declared_result_states(
    raw,
    where: str,
) -> tuple[DeclaredState, ...] | None:
    """Uma declaração por linha: `ESTADO → "literal"`."""

    if raw is None:
        return None

    if not isinstance(raw, str):
        raise CanonicalModelError(
            f"{where}: declared_result_states deve ser texto, recebido "
            f"{type(raw).__name__} {raw!r}."
        )

    states = []

    for line in raw.split("\n"):
        state, arrow, literal = line.partition(STATE_ARROW)

        if (
            not arrow
            or state not in RESULT_STATE_TAXONOMY
            or len(literal) < 3
            or literal[0] != '"'
            or literal[-1] != '"'
            or '"' in literal[1:-1]
        ):
            raise CanonicalModelError(
                f"{where}: declared_result_states fora do formato "
                f"'ESTADO{STATE_ARROW}\"literal\"' com ESTADO em "
                f"{sorted(RESULT_STATE_TAXONOMY)}: {line!r}."
            )

        states.append(DeclaredState(state=state, literal=literal[1:-1]))

    if len({s.state for s in states}) != len(states):
        raise CanonicalModelError(
            f"{where}: estado declarado mais de uma vez: {raw!r}."
        )

    return tuple(states)


def _where(workbook: WorkbookData, row: WorkbookRow) -> str:
    return f"{workbook.file_name}/{workbook.sheet} linha {row.row}"


def _check_row(workbook: WorkbookData, row: WorkbookRow) -> None:
    where = _where(workbook, row)
    row_type = row.get("Type")
    expression = row.get("expression")

    if row_type not in ROW_TYPES:
        raise CanonicalModelError(
            f"{where}: Type {row_type!r} fora do vocabulário {ROW_TYPES}."
        )

    if row_type == TYPE_EQUATION and expression is None:
        raise CanonicalModelError(
            f"{where}: Type '{TYPE_EQUATION}' sem expressão."
        )

    if row_type in (TYPE_VARIABLE, TYPE_PARAMETER) and expression is not None:
        raise CanonicalModelError(
            f"{where}: Type '{row_type}' não pode ter expressão "
            f"({expression!r})."
        )

    if expression is not None and not isinstance(expression, str):
        raise CanonicalModelError(
            f"{where}: expressão deve ser texto, recebido {expression!r}."
        )

    value_type = row.get("value_type")

    if value_type not in VALUE_TYPES:
        raise CanonicalModelError(
            f"{where}: value_type {value_type!r} inválido ou ausente "
            f"(permitidos: {sorted(VALUE_TYPES)}; sem alias, sem padrão)."
        )

    if row_type == TYPE_PARAMETER:
        value = row.get("value")
        version = row.get("version")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CanonicalModelError(
                f"{where}: parâmetro com value não numérico "
                f"{type(value).__name__} {value!r} — não é convertido."
            )

        if isinstance(version, bool) or not isinstance(version, int):
            raise CanonicalModelError(
                f"{where}: parâmetro com version não inteiro {version!r}."
            )

        if value_type != NUMERIC:
            raise CanonicalModelError(
                f"{where}: parâmetro numérico com value_type {value_type!r}."
            )


def _definition_key(row: WorkbookRow) -> tuple:
    kind = "parameter" if row.get("Type") == TYPE_PARAMETER else "variable"
    scope_value = row.get("scope_value")

    if row.get("scope_type") == "linha" and scope_value in LINE_VALUES:
        # Candidata a instância de uma definição por linha.
        return (kind, row.get("name"), row.get("frequency"), "linha", "*")

    return (
        kind,
        row.get("name"),
        row.get("frequency"),
        row.get("scope_type"),
        scope_value,
    )


def _line_range(lines: list[str], where: str) -> str:
    numbers = sorted(int(line[1:]) for line in lines)

    if len(set(numbers)) != len(numbers):
        raise IdentityCollisionError(
            f"{where}: a mesma linha aparece mais de uma vez: {lines}."
        )

    if numbers != list(range(numbers[0], numbers[-1] + 1)):
        raise CanonicalModelError(
            f"{where}: instâncias por linha não contíguas {lines}: não "
            "há escopo declarável que as represente como uma definição."
        )

    if len(numbers) == 1:
        return f"L{numbers[0]}"

    return f"L{numbers[0]}_L{numbers[-1]}"


def _single(values: list, field_name: str, where: str):
    distinct = {repr(v) for v in values}

    if len(distinct) > 1:
        raise CanonicalModelError(
            f"{where}: instâncias da mesma definição divergem em "
            f"'{field_name}': {sorted(distinct)}."
        )

    return values[0]


def build_canonical_model(
    block: str,
    workbook: WorkbookData,
    id_base: int,
    id_ledger: IdLedger | None = None,
) -> CanonicalModel:
    model = CanonicalModel(block=block, workbook=workbook)

    for row in workbook.rows:
        _check_row(workbook, row)

    groups: dict[tuple, list[WorkbookRow]] = {}

    for row in workbook.rows:
        groups.setdefault(_definition_key(row), []).append(row)

    next_id = {"variable": id_base + 1, "parameter": id_base + 1}
    prefix = {"variable": "VAR", "parameter": "PARAM"}

    for key, rows in groups.items():
        kind = key[0]
        where = f"{workbook.file_name}/{workbook.sheet} linhas {[r.row for r in rows]} ({key[1]})"
        per_line = key[4] == "*"

        if per_line:
            scope_value = _line_range([r.get("scope_value") for r in rows], where)
        else:
            if len(rows) > 1:
                raise IdentityCollisionError(
                    f"{where}: {len(rows)} linhas com a mesma identidade "
                    f"{key[1:]}."
                )
            scope_value = rows[0].get("scope_value")

        definition_fields = (
            VARIABLE_DEFINITION_FIELDS
            if kind == "variable"
            else PARAMETER_DEFINITION_FIELDS
        )
        common = {
            name: _single([r.get(name) for r in rows], name, where)
            for name in definition_fields
        }

        allowed_values = parse_allowed_values(common.get("allowed_values"), where)
        declared_states = parse_declared_result_states(
            common.get("declared_result_states"), where
        )

        if allowed_values is not None and common["value_type"] != CATEGORICAL:
            raise CanonicalModelError(
                f"{where}: allowed_values só se aplica a value_type "
                f"'{CATEGORICAL}' (value_type {common['value_type']!r})."
            )

        canonical_rows = []

        for r in rows:
            expression = r.get("expression")
            aggregation = parse_aggregation(expression)

            if declared_states:
                for declared in declared_states:
                    if f'"{declared.literal}"' not in (expression or ""):
                        raise CanonicalModelError(
                            f"{_where(workbook, r)}: literal declarado "
                            f"\"{declared.literal}\" ({declared.state}) não "
                            "aparece na expressão da própria linha (R1/D1)."
                        )

            if kind == "variable" and (
                r.get("value") is not None or r.get("version") is not None
            ):
                model.pending_decisions.append(
                    PendingDecision(
                        decision_id="D24-12",
                        row=r.row,
                        name=r.get("name"),
                        fields={
                            "value": r.get("value"),
                            "version": r.get("version"),
                        },
                        reason=(
                            "value/version preenchidos em Type=variable: o "
                            "contrato não define o significado; não "
                            "transportado para o domínio, aguardando decisão."
                        ),
                    )
                )

            canonical_rows.append(
                CanonicalRow(
                    row=r.row,
                    scope_value=r.get("scope_value"),
                    description=r.get("description"),
                    source_reference=r.get("source_reference"),
                    expression=expression,
                    value=r.get("value") if kind == "parameter" else None,
                    version=r.get("version") if kind == "parameter" else None,
                    aggregation=aggregation,
                )
            )

        if per_line and len(rows) > 1 and any(
            cr.aggregation is not None for cr in canonical_rows
        ):
            raise CanonicalModelError(
                f"{where}: agregação temporal declarada linha a linha numa "
                "definição por linha não é suportada pelo contrato atual."
            )

        if id_ledger is None:
            entity_id = f"{prefix[kind]}{next_id[kind]}"
            next_id[kind] += 1
        else:
            # Atribuído depois do laço: livro primeiro, novos em seguida.
            entity_id = None

        model.entities.append(
            CanonicalEntity(
                kind=kind,
                entity_id=entity_id,
                name=key[1],
                frequency=key[2],
                scope_type=key[3],
                scope_value=scope_value,
                grouped=per_line and len(rows) > 1,
                unit=common["unit"],
                variable_type=common.get("variable_type"),
                value_type=common["value_type"],
                allowed_values=allowed_values,
                declared_result_states=declared_states,
                status=common["status"],
                fonte=common.get("fonte"),
                rows=tuple(canonical_rows),
            )
        )

    if id_ledger is not None:
        _assign_ledger_ids(model, id_ledger, id_base, next_id, prefix)

    for limit_kind in next_id:
        if next_id[limit_kind] - 1 > id_base + 999:
            raise CanonicalModelError(
                f"{block}: faixa de IDs {id_base}-{id_base + 999} esgotada."
            )

    check_identity(model)

    return model


def _assign_ledger_ids(
    model: CanonicalModel,
    id_ledger: IdLedger,
    id_base: int,
    next_id: dict,
    prefix: dict,
) -> None:
    """
    IDs do livro para identidades conhecidas; identidades novas recebem,
    em ordem de linha, o número seguinte ao maior já emitido (ativos ou
    aposentados) para a mesma natureza. Nada é renumerado.
    """

    for kind in next_id:
        next_id[kind] = max(id_base, id_ledger.highest(kind)) + 1

    assigned = []

    for entity in model.entities:
        key = identity_key(
            entity.kind, entity.name, entity.frequency, entity.scope_type, entity.scope_value
        )
        entity_id = id_ledger.entries.get(key)

        if entity_id is None:
            entity_id = f"{prefix[entity.kind]}{next_id[entity.kind]}"
            next_id[entity.kind] += 1

        assigned.append(dataclasses.replace(entity, entity_id=entity_id))

    model.entities[:] = assigned


def check_identity(model: CanonicalModel, scope_resolver: ScopeResolver | None = None) -> None:
    """
    Identidade = name + frequency + scope_type + scope_value, avaliada
    por instância concreta. Colisão é erro, nunca aviso.
    """

    scope_resolver = scope_resolver or ScopeResolver()
    seen: dict[tuple, CanonicalEntity] = {}

    for entity in model.entities:
        for scope_type, scope_value in scope_resolver.resolve_scopes(
            entity.scope_type, entity.scope_value
        ):
            key = (entity.name, entity.frequency, scope_type, scope_value)

            if key in seen:
                other = seen[key]
                raise IdentityCollisionError(
                    f"{model.workbook.file_name}: identidade {key} "
                    f"materializada por {other.entity_id} (linha "
                    f"{other.first_row}) e {entity.entity_id} (linha "
                    f"{entity.first_row})."
                )

            seen[key] = entity


__all__ = [
    "CanonicalEntity",
    "CanonicalModel",
    "CanonicalModelError",
    "CanonicalRow",
    "DeclaredState",
    "IdentityCollisionError",
    "PendingDecision",
    "build_canonical_model",
    "check_identity",
    "looks_like_aggregation",
    "parse_allowed_values",
    "parse_declared_result_states",
]
