"""
Stage 4C — mapa de conjuntos de baseline e resolução do parâmetro `--baseline-dir`.

Um CONJUNTO é a evidência de referência de um harness (arquivos lógicos -> caminho). Em B0 os caminhos
são os históricos, já versionados pelas Stages 3.2–4B (sem cópia). A partir de B1 cada conjunto R
fica em `audit/baselines/B<n>/<conjunto>/<arquivo lógico>`.

Resolução do diretório de baseline (a ÚNICA alteração aceita nos harnesses R):
    1. valor configurado em processo (`configure(dir)`; usado por `tests/conftest.py`);
    2. senão, o valor de `--baseline-dir <dir>` em `sys.argv` (harness chamado como script);
    3. senão, None => caminhos históricos B0 (comportamento idêntico ao anterior à 4C).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_T = "audit/stage4b/temporal/evidence"
_TEMPORAL = {f"{r}/{name}": f"{_T}/{r}/{name}"
             for r, names in (("T1", ("identities_by_date.csv", "performance_profile.csv", "period_snapshots.json",
                                      "reexecution.json", "state_scenarios.json", "temporal_coverage.csv",
                                      "temporal_summary.json")),
                              ("T2", ("identities_by_date.csv", "performance_profile.csv", "period_snapshots.json",
                                      "reexecution.json", "temporal_coverage.csv", "temporal_summary.json")),
                              ("T3", ("identities_by_date.csv", "performance_profile.csv", "period_snapshots.json",
                                      "reexecution.json", "temporal_coverage.csv", "temporal_summary.json")))
             for name in names}

# Conjuntos REGENERADOS pelo re-baseline (classe R), em ordem de dependência.
R_SETS: dict[str, dict[str, str]] = {
    "stage3_2_plan": {
        "plan_evidence.csv": "audit/stage3_2_execution_orchestration/evidence/plan_evidence.csv",
        "transfer_evidence.csv": "audit/stage3_2_execution_orchestration/evidence/transfer_evidence.csv",
        "analysis_summary.json": "audit/stage3_2_execution_orchestration/evidence/analysis_summary.json",
    },
    "stage3_4c_integrated": {name: f"audit/stage3_4/integrated/evidence/{name}" for name in (
        "integrated_summary.json", "targets.csv", "nodes.csv", "transfers.csv", "temporal_coverage.csv")},
    "stage4a_contract": {
        "contract_expectations.json": "audit/stage4a/contract_expectations.json",
        "contract_audit.json": "audit/stage4a/evidence/contract_audit.json",
        "obs_register.csv": "audit/stage4a/evidence/obs_register.csv",
        "hes_decision_matrix.csv": "audit/stage4a/evidence/hes_decision_matrix.csv",
    },
    "stage4a_integrated": {name: f"audit/stage4a/integrated/evidence/{name}" for name in (
        "integrated_summary.json", "non_regression_421.json", "targets.csv", "nodes.csv", "transfers.csv",
        "temporal_coverage.csv")},
    "stage4b_contract": {
        "contract_expectations_4b.json": "audit/stage4b/contract_expectations_4b.json",
        "contract_audit_4b.json": "audit/stage4b/evidence/contract_audit_4b.json",
        "performance_probe.csv": "audit/stage4b/evidence/performance_probe.csv",
    },
    "stage4b_temporal": _TEMPORAL,
}

# Conjuntos HERDADOS (classe H/E): descrevem fechamentos; nunca regenerados, só verificados.
INHERITED_SETS: dict[str, dict[str, str]] = {
    "stage3_4b_differential": {name: f"audit/stage3_4/differential/evidence/{name}" for name in (
        "differential_summary.json", "differential_cases.csv")},
    "stage3_4d_mutation": {name: f"audit/stage3_4/mutation/{name}" for name in (
        "baseline_gap_probe.json", "blackbox_audit.json", "code_mutation_results.csv", "mutation_matrix.csv",
        "mutation_results.csv", "mutation_summary.json", "positive_controls.csv")},
    "stage4a_oracle": {name: f"audit/stage4a/oracle/evidence/{name}" for name in (
        "oracle_cases.csv", "oracle_summary.json")},
    "stage4a_mutation": {name: f"audit/stage4a/mutation/evidence/{name}" for name in (
        "code_mutation_results.csv", "mutation_results.csv", "mutation_summary.json", "positive_controls.csv")},
    "stage4a_closure": {name: f"audit/stage4a/closure/{name}" for name in (
        "closure_reconciliation_4a.json", "evidence_regeneration_report.md")},
    "stage4b_oracle": {"oracle_temporal_summary.json": "audit/stage4b/oracle/evidence/oracle_temporal_summary.json"},
    "stage4b_mutation": {name: f"audit/stage4b/mutation/evidence/{name}" for name in (
        "code_mutation_results.csv", "first_round_analysis.json", "mutation_results.csv", "mutation_summary.json",
        "positive_controls.csv")},
    "stage4b_closure": {"closure_reconciliation_4b.json": "audit/stage4b/closure/closure_reconciliation_4b.json"},
}

# Último commit que gravou a evidência histórica de cada conjunto (proteção E: HEAD x esse commit).
EVIDENCE_COMMITS = {
    "stage3_2_plan": "a733487", "stage3_4b_differential": "4d54804", "stage3_4c_integrated": "043fe9c",
    "stage3_4d_mutation": "d8b5d55", "stage4a_contract": "fdeec18", "stage4a_integrated": "99d5a67",
    "stage4a_oracle": "a34b865", "stage4a_mutation": "99d5a67", "stage4a_closure": "0a924e6",
    "stage4b_contract": "b0c3da3", "stage4b_temporal": "ec6f270", "stage4b_oracle": "d5c37a3",
    "stage4b_mutation": "314224d", "stage4b_closure": "f573c1b",
}

HISTORICAL = {**R_SETS, **INHERITED_SETS}

_configured: list = []          # [] = não configurado; [None] ou [Path] = configurado em processo


def configure(baseline_dir) -> None:
    """Fixa o diretório de baseline do processo (None = caminhos históricos B0)."""
    _configured[:] = [None if baseline_dir is None else Path(baseline_dir).resolve()]


def baseline_dir() -> Path | None:
    if _configured:
        return _configured[0]
    if "--baseline-dir" in sys.argv:
        position = sys.argv.index("--baseline-dir") + 1
        if position >= len(sys.argv):
            raise SystemExit("--baseline-dir exige um diretório")
        return Path(sys.argv[position]).resolve()
    return None


def path(set_name: str, logical: str) -> Path:
    """Caminho do arquivo lógico do conjunto: histórico (B0) ou `<baseline-dir>/<conjunto>/<lógico>`."""
    if set_name not in HISTORICAL or logical not in HISTORICAL[set_name]:
        raise KeyError(f"{set_name}/{logical} não pertence a nenhum conjunto de baseline")
    root = baseline_dir()
    if root is None:
        return REPO / HISTORICAL[set_name][logical]
    if set_name in INHERITED_SETS:          # herdados nunca são regenerados: sempre o histórico
        return REPO / HISTORICAL[set_name][logical]
    return root / set_name / logical


def writable(set_name: str, logical: str) -> Path:
    """Destino de escrita do arquivo lógico (cria o diretório pai quando é um baseline novo)."""
    target = path(set_name, logical)
    if baseline_dir() is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def argv() -> list[str]:
    """Argumentos a repassar a subprocessos do mesmo harness."""
    root = baseline_dir()
    return [] if root is None else ["--baseline-dir", str(root)]


def is_default() -> bool:
    return baseline_dir() is None
