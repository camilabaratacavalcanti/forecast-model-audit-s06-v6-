"""
Livro de IDs por bloco (Etapa 2.6B): IDs históricos não são renumerados.

A numeração sequencial por ordem de linha (Etapa 2.4) renumera todas as
definições posteriores quando uma definição muda de natureza ou é
inserida no workbook (ex.: D26-02, `production.lth_meta` passa de
parameter a variable). O livro fixa o ID de cada identidade já emitida:

    identidade = (kind, name, frequency, scope_type, scope_value)

1. Identidade presente no livro -> mantém o ID do livro.
2. Identidade nova -> próximo número acima do maior já emitido para a
   mesma natureza (incluindo aposentados), em ordem de linha.
3. Identidade que deixa de existir -> o ID é aposentado e nunca é
   reutilizado. O registro de aposentadoria é permanente: é copiado de
   um build para o seguinte e nunca é removido do livro.
4. Determinismo: o livro depende só do livro anterior versionado e do
   workbook; entradas na ordem das definições do workbook, sem
   timestamp, sem hash aleatório, sem estado fora do repositório. A
   ordem de carga dos blocos não influi (cada bloco tem o seu livro).

O livro é um arquivo versionado (`data/id_ledger/<bloco>.json`),
gravado junto com os seeds. Sem livro, a numeração é a sequencial.

Stage 5A (D-5A-4) — livro de EQUAÇÕES, mesmas regras 1–4:

    identidade = identidade da variável alvo + scope_value da instância
                 (kind, name, frequency, scope_type, scope_value, equation_scope_value)

Mudança de expressão com a mesma identidade mantém o ID. Seções novas e
retrocompatíveis no mesmo arquivo: `equations` e `retired_equations`.
Livro sem a seção `equations` (anterior à 5A) => numeração sequencial,
igual à anterior: a primeira gravação inicializa o livro sem renumerar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


PREFIX = {"variable": "VAR", "parameter": "PARAM", "equation": "EQ"}
KEY_FIELDS = ("kind", "name", "frequency", "scope_type", "scope_value")
EQUATION_KEY_FIELDS = KEY_FIELDS + ("equation_scope_value",)


class IdLedgerError(ValueError):
    """O livro de IDs é inconsistente."""


def identity_key(kind, name, frequency, scope_type, scope_value) -> tuple:
    return (kind, name, frequency, scope_type, scope_value)


def equation_key(target_key: tuple, equation_scope_value) -> tuple:
    """Identidade da equação: identidade da variável alvo + escopo da instância (D-5A-4)."""
    return tuple(target_key) + (equation_scope_value,)


def id_number(entity_id: str, kind: str) -> int:
    prefix = PREFIX[kind]

    if not entity_id.startswith(prefix) or not entity_id[len(prefix):].isdigit():
        raise IdLedgerError(f"ID {entity_id!r} não pertence à natureza {kind!r}.")

    return int(entity_id[len(prefix):])


@dataclass(frozen=True)
class IdLedger:
    block: str
    entries: dict = field(default_factory=dict)  # identity key -> entity_id
    retired: tuple = ()  # dicts com KEY_FIELDS + entity_id + retired_in
    equations: dict | None = None  # equation key -> equation_id; None = livro anterior à 5A
    retired_equations: tuple = ()  # dicts com EQUATION_KEY_FIELDS + equation_id + retired_in

    def __post_init__(self):
        seen = {}

        for key, entity_id in self.entries.items():
            if entity_id in seen:
                raise IdLedgerError(
                    f"{self.block}: {entity_id} atribuído a {seen[entity_id]} e {key}."
                )
            id_number(entity_id, key[0])
            seen[entity_id] = key

        for record in self.retired:
            if record["entity_id"] in seen:
                raise IdLedgerError(
                    f"{self.block}: {record['entity_id']} aposentado e ativo ao mesmo tempo."
                )

        seen_eq = {}

        for key, equation_id in (self.equations or {}).items():
            if equation_id in seen_eq:
                raise IdLedgerError(
                    f"{self.block}: {equation_id} atribuído a {seen_eq[equation_id]} e {key}."
                )
            id_number(equation_id, "equation")
            seen_eq[equation_id] = key

        for record in self.retired_equations:
            if record["equation_id"] in seen_eq:
                raise IdLedgerError(
                    f"{self.block}: {record['equation_id']} aposentado e ativo ao mesmo tempo."
                )

    def highest(self, kind: str) -> int:
        numbers = [id_number(i, kind) for k, i in self.entries.items() if k[0] == kind]
        numbers += [
            id_number(r["entity_id"], kind) for r in self.retired if r["kind"] == kind
        ]
        return max(numbers, default=0)

    def retired_ids(self) -> set[str]:
        return {r["entity_id"] for r in self.retired}

    def highest_equation(self) -> int:
        numbers = [id_number(i, "equation") for i in (self.equations or {}).values()]
        numbers += [id_number(r["equation_id"], "equation") for r in self.retired_equations]
        return max(numbers, default=0)


def ledger_path(root: Path, block: str) -> Path:
    return root / f"{block}.json"


def load_ledger(path: Path) -> IdLedger | None:
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))

    return IdLedger(
        block=payload["block"],
        entries={
            identity_key(*(e[f] for f in KEY_FIELDS)): e["entity_id"]
            for e in payload["entries"]
        },
        retired=tuple(payload["retired"]),
        equations=(
            {
                equation_key(tuple(e[f] for f in KEY_FIELDS), e["equation_scope_value"]): e["equation_id"]
                for e in payload["equations"]
            }
            if "equations" in payload
            else None
        ),
        retired_equations=tuple(payload.get("retired_equations", ())),
    )


def ledger_payload(model, previous: IdLedger | None) -> dict:
    """Livro atualizado após o build: ativos do modelo + aposentados."""

    current = {
        identity_key(e.kind, e.name, e.frequency, e.scope_type, e.scope_value): e.entity_id
        for e in model.entities
    }
    retired = list(previous.retired) if previous else []

    if previous:
        for key, entity_id in previous.entries.items():
            if key not in current:
                retired.append({
                    "entity_id": entity_id,
                    **dict(zip(KEY_FIELDS, key)),
                    "retired_in": model.workbook.file_name,
                })

    payload = {
        "block": model.block,
        "entries": [
            {"entity_id": entity_id, **dict(zip(KEY_FIELDS, key))}
            for key, entity_id in current.items()
        ],
        "retired": retired,
    }

    # D-5A-4: atribuições de equação registradas pelo build (seeds.build_equations).
    assignments = getattr(model, "equation_assignments", None)

    if assignments is not None:
        current_eq = dict(assignments)
        retired_eq = list(previous.retired_equations) if previous else []

        if previous and previous.equations:
            for key, equation_id in previous.equations.items():
                if key not in current_eq:
                    retired_eq.append({
                        "equation_id": equation_id,
                        **dict(zip(EQUATION_KEY_FIELDS, key)),
                        "retired_in": model.workbook.file_name,
                    })

        payload["equations"] = [
            {"equation_id": equation_id, **dict(zip(EQUATION_KEY_FIELDS, key))}
            for key, equation_id in sorted(current_eq.items(), key=lambda item: id_number(item[1], "equation"))
        ]
        payload["retired_equations"] = retired_eq

    return payload


__all__ = [
    "EQUATION_KEY_FIELDS",
    "IdLedger",
    "IdLedgerError",
    "equation_key",
    "identity_key",
    "ledger_path",
    "ledger_payload",
    "load_ledger",
]
