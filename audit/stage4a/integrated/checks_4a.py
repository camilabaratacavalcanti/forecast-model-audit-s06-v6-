"""
Stage 4A — verificações puras específicas do universo de 5 blocos (sem importar `app`).
Complementam `audit/stage3_4/integrated/checks.py` (importado sem alteração). Toda
função devolve uma lista de problemas; lista vazia = verificação satisfeita.

Formato de resultado: [tipo, repr, state, detail]; chave: (entity_id, scope_type, scope_value, period_id, window_end).
"""

from __future__ import annotations

import hashlib


def check_no_text_in_numeric(store: dict, numeric_variables: set) -> list[str]:
    """§10.5: nenhuma variável `numerico` pode carregar texto no valor (ex.: o literal "F")."""
    bad = sorted((k for k, v in store.items() if k[0] in numeric_variables and v[0] == "str"), key=repr)
    return [f"F_LITERAL_AS_VALUE texto no valor de variável numérica {k}: {store[k][:2]}" for k in bad[:5]] + (
        [f"F_LITERAL_AS_VALUE +{len(bad) - 5} chaves"] if len(bad) > 5 else [])


def check_area_41_determinism(runs: dict) -> list[str]:
    """runs: {label: {area_41_store_sha256, previous_store_sha256}} — todos iguais a RUN_A."""
    problems = []
    reference = runs["RUN_A"]
    for label, run in sorted(runs.items()):
        for field in ("area_41_store_sha256", "previous_store_sha256"):
            if field in run and run[field] != reference[field]:
                problems.append(f"DETERMINISM_FAILURE {label}.{field} != RUN_A")
    return problems


def check_provenance(links_bytes: bytes, expected_sha256: str, official_pending: int, fixture_pending: int,
                     expected_pending: int = 16) -> list[str]:
    """Registro oficial intacto: sha256 de interblock_links.json, 16 PENDING_LOAD oficiais, pending=[] só no fixture."""
    problems = []
    if hashlib.sha256(links_bytes).hexdigest() != expected_sha256:
        problems.append("PROVENANCE_FAILURE interblock_links.json alterado (sha256)")
    if official_pending != expected_pending:
        problems.append(f"PENDING_LINKS_ALTERED {official_pending} != {expected_pending}")
    if fixture_pending != 0:
        problems.append(f"FIXTURE_FAILURE pending no fixture {fixture_pending} != 0")
    return problems
