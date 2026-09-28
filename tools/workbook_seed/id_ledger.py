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
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


PREFIX = {"variable": "VAR", "parameter": "PARAM"}
KEY_FIELDS = ("kind", "name", "frequency", "scope_type", "scope_value")


class IdLedgerError(ValueError):
    """O livro de IDs é inconsistente."""


def identity_key(kind, name, frequency, scope_type, scope_value) -> tuple:
    return (kind, name, frequency, scope_type, scope_value)


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

    def highest(self, kind: str) -> int:
        numbers = [id_number(i, kind) for k, i in self.entries.items() if k[0] == kind]
        numbers += [
            id_number(r["entity_id"], kind) for r in self.retired if r["kind"] == kind
        ]
        return max(numbers, default=0)

    def retired_ids(self) -> set[str]:
        return {r["entity_id"] for r in self.retired}


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

    return {
        "block": model.block,
        "entries": [
            {"entity_id": entity_id, **dict(zip(KEY_FIELDS, key))}
            for key, entity_id in current.items()
        ],
        "retired": retired,
    }


__all__ = [
    "IdLedger",
    "IdLedgerError",
    "identity_key",
    "ledger_path",
    "ledger_payload",
    "load_ledger",
]
