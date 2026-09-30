"""
Stage 3.4B — comparador diferencial EXATO (sem importar `app`).

Contrato:
    * igualdade exata da representação (tipo, repr): 10 != 10.0000001,
      1 != 1.0 (int x float), None != 0, 0.0 != nan. Sem tolerância, sem
      arredondamento, sem normalização de tipo.
    * o objeto inteiro é comparado componente a componente:
        EQUATION     retorno do engine, valor no contexto, state, detail
        AGGREGATION  value, identidade (variável, escopo, frequência,
                     period_id), state, detail
    * state/detail: no reference (7877551) não existem ->
      "NOT_APPLICABLE_TO_REFERENCE"; no candidate precisam ser None (o
      caminho sem estado não pode produzir estado). Qualquer outra
      combinação é STATE_DIFFERENCE / DETAIL_DIFFERENCE.
    * EXCEPTION em qualquer lado nunca é "igual": EXCEPTION_DIFFERENCE.
"""

from __future__ import annotations

NA = "NOT_APPLICABLE_TO_REFERENCE"
CASE_KEY_FIELDS = ("block", "operation_type", "instance_id", "input_vector", "run_date")


def case_key(case: dict) -> tuple:
    """ExecutionCaseKey = (block, operation_type, instance_id, input_vector_id, run_date)."""
    return tuple(case[field] for field in CASE_KEY_FIELDS)


def exact_equal(a, b) -> bool:
    """a, b = [tipo, repr]; igualdade exata da representação."""
    return list(a) == list(b)


def compare_case(reference: dict | None, candidate: dict | None) -> list[str]:
    """Lista de diferenças (vazia = MATCH)."""
    if reference is None:
        return ["MISSING_REFERENCE_RESULT"]
    if candidate is None:
        return ["MISSING_CANDIDATE_RESULT"]
    differences = []
    for field in ("block", "operation_type", "instance_id", "definition_id", "target", "scope",
                  "period_id", "aggregation_type", "integration_factor"):
        if reference.get(field) != candidate.get(field):
            differences.append("STRUCTURAL_DIFFERENCE")
            break
    ref, cand = reference["outcome"], candidate["outcome"]
    if ref[0] != "OK" or cand[0] != "OK":
        differences.append("EXCEPTION_DIFFERENCE")
        return differences
    if reference["operation_type"] == "EQUATION":
        _, ref_returned, ref_value, ref_state, ref_detail = ref
        _, cand_returned, cand_value, cand_state, cand_detail = cand
        if not (exact_equal(ref_returned, cand_returned) and exact_equal(ref_value, cand_value)):
            differences.append("VALUE_DIFFERENCE")
    else:
        _, ref_value, ref_identity, ref_state, ref_detail = ref
        _, cand_value, cand_identity, cand_state, cand_detail = cand
        if not exact_equal(ref_value, cand_value):
            differences.append("VALUE_DIFFERENCE")
        if ref_identity != cand_identity:
            differences.append("STRUCTURAL_DIFFERENCE")
    if not _state_ok(ref_state, cand_state):
        differences.append("STATE_DIFFERENCE")
    if not _state_ok(ref_detail, cand_detail):
        differences.append("DETAIL_DIFFERENCE")
    return sorted(set(differences))


def _state_ok(reference, candidate) -> bool:
    # Reference sem Result: o candidate precisa ser o "sem estado" (None).
    if reference == NA:
        return candidate is None
    return reference == candidate


def coverage(cases: list[dict], expected_keys: set[tuple]) -> dict:
    """Duplicados, faltantes e excedentes de um lado, pela ExecutionCaseKey."""
    keys = [case_key(c) for c in cases]
    seen, duplicates = set(), set()
    for key in keys:
        (duplicates if key in seen else seen).add(key)
    return {
        "actual": len(keys),
        "unique": len(seen),
        "duplicates": sorted(duplicates),
        "missing": sorted(expected_keys - seen),
        "unexpected": sorted(seen - expected_keys),
    }
