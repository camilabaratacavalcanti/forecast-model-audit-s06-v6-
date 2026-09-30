"""
Stage 3.4D — detector de isolamento do fixture e de proveniência (M10).

REAL_DERIVED = TEST_FIXTURE_ONLY (DR-2, contrato 3.4A). O detector confirma:
  * o arquivo persistente `interblock_links.json` é byte a byte o do baseline, ou
    difere dele SOMENTE pela migração taxonômica autorizada D-TAX-01;
  * os 16 vínculos pendentes reais continuam pendentes (mesmos consumidores,
    `resolution_status = PENDING_LOAD`) no dado persistente e no registro
    oficial carregado dele;
  * o fixture existe só em memória: pendências vazias SOMENTE nele, grafo
    igual ao hash registrado na 3.4C;
  * a evidência do fixture é rotulada REAL_DERIVED_TEST_RESULT e nunca como
    resultado operacional.
Não escreve nada; recebe o diretório de seeds a auditar (o real ou uma cópia).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "taxonomy_migration"))
import taxonomy_guard  # noqa: E402

LABEL = "REAL_DERIVED_TEST_RESULT"
CLASSIFICATION = "TEST_FIXTURE_ONLY"
OPERATIONAL_MARKERS = ("OPERATIONAL", "PRODUCTION", "OFFICIAL_RESULT")


def pending_ids(payload: dict) -> list[str]:
    return sorted(p["consumer_definition"] for p in payload["pending"])


def check_provenance(seed_root: Path, baseline_links: bytes, *, official_registry=None, fixture_registry=None,
                     fixture_hash: str | None = None, expected_fixture_hash: str | None = None,
                     evidence: dict | None = None) -> list[str]:
    problems = []
    baseline = json.loads(baseline_links)
    expected_pending = pending_ids(baseline)
    persisted = (Path(seed_root) / "interblock_links.json").read_bytes()
    if persisted != baseline_links:
        # D-TAX-01: a única diferença aceita é a seção `taxonomy` migrada (taxonomy_guard.py);
        # links, pending, rejected e demais seções continuam exigindo igualdade.
        taxonomy_problems = taxonomy_guard.classify({"data/seed/interblock_links.json":
                                                     (baseline_links, persisted)})["problems"]
        if taxonomy_problems:
            problems.append("PROVENANCE_FAILURE registro persistente interblock_links.json alterado")
    payload = json.loads(persisted)
    if pending_ids(payload) != expected_pending:
        problems.append(f"PENDING_LINKS_ALTERED persistente: {len(payload['pending'])} pendências "
                        f"!= {len(expected_pending)} do baseline")
    not_pending = sorted(p["consumer_definition"] for p in payload["pending"]
                         if p.get("resolution_status") != "PENDING_LOAD")
    if not_pending:
        problems.append(f"PENDING_LINKS_ALTERED persistente: pendências mascaradas {not_pending}")
    if official_registry is not None:
        loaded = sorted(p.consumer_definition_id for p in official_registry.pending())
        if loaded != expected_pending:
            problems.append(f"PENDING_LINKS_ALTERED registro oficial em memória: {len(loaded)} pendências")
    if fixture_registry is not None and fixture_registry.pending():
        problems.append(f"FIXTURE_FAILURE fixture com {len(fixture_registry.pending())} pendências (esperado 0)")
    if expected_fixture_hash is not None and fixture_hash != expected_fixture_hash:
        problems.append("FIXTURE_FAILURE grafo do fixture diferente do registrado na 3.4C")
    if evidence is not None:
        if evidence.get("label") != LABEL:
            problems.append(f"PROVENANCE_FAILURE evidência rotulada {evidence.get('label')!r} != {LABEL}")
        if evidence.get("classification", CLASSIFICATION) != CLASSIFICATION:
            problems.append(f"PROVENANCE_FAILURE classificação {evidence.get('classification')!r} != {CLASSIFICATION}")
        text = json.dumps({k: evidence.get(k) for k in ("label", "classification", "provenance", "mode")})
        if any(marker in text for marker in OPERATIONAL_MARKERS):
            problems.append("PROVENANCE_FAILURE execução de fixture marcada como operacional")
    return problems
