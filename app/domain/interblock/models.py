"""
Vínculos interbloco canônicos (Etapa 3.1).

Representação em runtime dos registros de `data/seed/interblock_links.json`,
o artefato gerado e validado no build (Etapas 2.6–2.6C). O runtime não
lê XLSX nem a coluna `fonte`: consome apenas este contrato.

    InterblockLink          vínculo resolvido (seção `links`)
    PendingInterblockLink   vínculo para bloco oficial ainda não
                            carregado (seção `pending`): sem produtor
    RejectedInterblockLink  vínculo reprovado no build (seção `rejected`)

A identidade continua local ao bloco (D25-01): consumidor e produtor
mantêm seus próprios IDs; o vínculo apenas declara a relação.
"""

from __future__ import annotations

from dataclasses import dataclass


Instance = tuple[str, str | None]  # (scope_type, scope_value)


@dataclass(frozen=True)
class InterblockLink:
    consumer_block: str
    consumer_definition_id: str
    consumer_frequency: str
    consumer_scope_type: str
    consumer_scope_value: str | None
    source_block: str
    source_definition_id: str
    source_frequency: str
    source_scope_type: str
    source_scope_value: str | None
    instances: tuple[Instance, ...]
    unit: str
    consumer_rows: tuple[int, ...] = ()

    @property
    def frequency(self) -> str:
        # Validado no carregamento: consumidor e produtor têm a mesma
        # frequência (sem conversão entre blocos).
        return self.consumer_frequency

    def declares(self, scope_type: str, scope_value: str | None) -> bool:
        return (scope_type, scope_value) in self.instances


@dataclass(frozen=True)
class PendingInterblockLink:
    consumer_block: str
    consumer_definition_id: str
    consumer_name: str
    consumer_frequency: str
    consumer_scope_type: str
    consumer_scope_value: str | None
    source_block: str
    instances: tuple[Instance, ...]
    consumer_rows: tuple[int, ...] = ()


@dataclass(frozen=True)
class RejectedInterblockLink:
    consumer_block: str
    consumer_definition_id: str
    source_block: object
    error_codes: tuple[str, ...]


__all__ = [
    "Instance",
    "InterblockLink",
    "PendingInterblockLink",
    "RejectedInterblockLink",
]
