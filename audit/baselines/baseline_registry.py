"""
Stage 4C — registro de baselines: leitura, selo, verificação e resolução do `current`.

O registro (`BASELINE_REGISTRY.json`) é uma lista encadeada de entradas (`anterior`) e um ponteiro
`current`. Só entradas APPROVED podem ser `current`; o selo (sha256 da entrada canônica sem o campo
`selo`) é gravado na aprovação, e editar uma entrada APPROVED o invalida. Os arquivos de cada conjunto
têm sha256 registrado. Os testes R resolvem a referência pelo `current` (`configure_current`,
`harness_args`, `path`); o harness só recebe o diretório.

Não importa app/ nem tools/ (usável sob `python -I`).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import baseline_paths as bp  # noqa: E402

SET_CLASSES = {**{name: "R" for name in bp.R_SETS},
               "stage3_4b_differential": "H", "stage3_4d_mutation": "H", "stage4a_closure": "H", "stage4b_closure": "H",
               "stage4a_oracle": "E", "stage4a_mutation": "E", "stage4b_oracle": "E", "stage4b_mutation": "E"}

REGISTRY = HERE / "BASELINE_REGISTRY.json"
SCHEMA = "forecast-baseline-registry/1"
STATUSES = ("PROPOSED", "APPROVED")
ENTRY_FIELDS = ("id", "commit_comportamento", "stage", "motivo", "data", "anterior", "status", "layout", "conjuntos")


# ------------------------------------------------------------------ leitura e selo
def load(path: Path = REGISTRY) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(registry: dict, path: Path = REGISTRY) -> None:
    Path(path).write_text(json.dumps(registry, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def seal(entry: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in entry.items() if k != "selo"}).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry(registry: dict, entry_id: str) -> dict:
    found = [e for e in registry["entries"] if e["id"] == entry_id]
    if len(found) != 1:
        raise KeyError(f"entrada {entry_id!r} ausente ou duplicada")
    return found[0]


def current(registry: dict | None = None) -> dict:
    registry = registry or load()
    return entry(registry, registry["current"])


# ------------------------------------------------------------------ resolução para os testes
def baseline_dir(registry: dict | None = None) -> Path | None:
    """None = layout histórico (B0); senão o diretório `audit/baselines/B<n>` do current."""
    layout = current(registry)["layout"]
    return None if layout == "historico" else REPO / layout


def configure_current(registry: dict | None = None) -> Path | None:
    """Configura `baseline_paths` no processo com o current (uso em processo pelos testes)."""
    root = baseline_dir(registry)
    bp.configure(root)
    return root


def harness_args(registry: dict | None = None) -> list[str]:
    """Argumentos para um harness R chamado em subprocesso: [] em B0, `--baseline-dir <dir>` depois."""
    root = baseline_dir(registry)
    return [] if root is None else ["--baseline-dir", str(root)]


def path(set_name: str, logical: str, registry: dict | None = None) -> Path:
    """Arquivo de referência do conjunto no current (pelo caminho registrado)."""
    return REPO / current(registry)["conjuntos"][set_name]["arquivos"][logical]["caminho"]


def load_json(set_name: str, logical: str, registry: dict | None = None):
    return json.loads(path(set_name, logical, registry).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ expectativas derivadas dos arquivos
def _rows(file: Path) -> list[dict]:
    with Path(file).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def derive_expectations(set_name: str, files: dict[str, Path]) -> dict:
    """Valores de referência de um conjunto R, recalculados só dos seus arquivos."""
    def js(name):
        return json.loads(files[name].read_text(encoding="utf-8"))
    if set_name == "stage3_2_plan":
        rows = _rows(files["plan_evidence.csv"])
        by = {}
        for r in rows:
            by[r["observed"]] = by.get(r["observed"], 0) + 1
        return {"official_targets": len(rows), "by_observed": dict(sorted(by.items())),
                "transfer_rows": len(_rows(files["transfer_evidence.csv"]))}
    if set_name == "stage3_4c_integrated":
        s = js("integrated_summary.json")
        coverage = _rows(files["temporal_coverage.csv"])
        return {"universe": {k: v for k, v in s["universe"].items()}, "targets_executed": s["targets_executed"],
                "nodes_executed": s["nodes_executed"], "transfers": len(_rows(files["transfers.csv"])),
                "dates": len(coverage),
                "per_date": sorted({(r["targets"], r["nodes"], r["transfer_events"], r["errors"]) for r in coverage}),
                "results_sha256_RUN_A": s["determinism"]["RUN_A"]["results_sha256"],
                "store_sha256_RUN_A": s["determinism"]["RUN_A"]["store_sha256"], "result": s["result"]}
    if set_name == "stage4a_contract":
        e = js("contract_expectations.json")
        return {"integrated": e["integrated"], "independent": e["independent"]}
    if set_name == "stage4a_integrated":
        s = js("integrated_summary.json")
        return {"universe": s["universe"], "targets_executed": s["targets_executed"],
                "nodes_executed": s["nodes_executed"], "transfers": len(_rows(files["transfers.csv"])),
                "results_sha256_RUN_A": s["determinism"]["RUN_A"]["results_sha256"],
                "store_sha256_RUN_A": s["determinism"]["RUN_A"]["store_sha256"],
                "previous_store_sha256": js("non_regression_421.json")["reference_store_sha256"],
                "result": s["result"]}
    if set_name == "stage4b_contract":
        e = js("contract_expectations_4b.json")
        return {"temporal": e["temporal"], "independent": e["independent"]}
    if set_name == "stage4b_temporal":
        out = {}
        for label in ("T1", "T2", "T3"):
            s = js(f"{label}/temporal_summary.json")
            out[label] = {"dates": s["dates"], "per_date": s["per_date"], "identities": s["identities"],
                          "results_sha256": s["fingerprint"]["results_sha256"],
                          "store_sha256": s["fingerprint"]["store_sha256"], "result": s["result"]}
        return out
    return {}


def set_files(set_def: dict) -> dict[str, Path]:
    return {logical: REPO / meta["caminho"] for logical, meta in set_def["arquivos"].items()}


# ------------------------------------------------------------------ verificação (sem escrita)
def verify(registry: dict) -> list[str]:
    problems: list[str] = []
    if registry.get("schema") != SCHEMA:
        problems.append(f"SCHEMA {registry.get('schema')!r} != {SCHEMA}")
    entries = registry.get("entries", [])
    ids = [e.get("id") for e in entries]
    if len(ids) != len(set(ids)):
        problems.append(f"IDS_DUPLICADOS {ids}")
    by_id = {e.get("id"): e for e in entries}
    if registry.get("current") not in by_id:
        problems.append(f"CURRENT_INEXISTENTE {registry.get('current')!r}")
    elif by_id[registry["current"]].get("status") != "APPROVED":
        problems.append(f"CURRENT_NAO_APROVADO {registry['current']} está {by_id[registry['current']].get('status')}")
    roots = [e for e in entries if e.get("anterior") is None]
    if len(roots) != 1 or (entries and entries[0].get("anterior") is not None):
        problems.append("CADEIA exatamente uma raiz (B0), na primeira posição")
    for position, e in enumerate(entries):
        missing = [f for f in ENTRY_FIELDS if f not in e]
        if missing:
            problems.append(f"{e.get('id')}: CAMPOS_AUSENTES {missing}")
            continue
        if e["status"] not in STATUSES:
            problems.append(f"{e['id']}: STATUS_INVALIDO {e['status']}")
        if e["anterior"] is not None:
            if position == 0 or entries[position - 1]["id"] != e["anterior"]:
                problems.append(f"{e['id']}: CADEIA anterior {e['anterior']} não é a entrada imediatamente anterior")
            elif by_id[e["anterior"]].get("status") != "APPROVED":
                problems.append(f"{e['id']}: CADEIA anterior {e['anterior']} não aprovado")
        if not str(e.get("motivo") or "").strip():
            problems.append(f"{e['id']}: MOTIVO_AUSENTE")
        if e["status"] == "APPROVED":
            if e.get("selo") != seal(e):
                problems.append(f"{e['id']}: SELO_INVALIDO entrada APPROVED editada")
        expected_layout = "historico" if e["anterior"] is None else f"audit/baselines/{e['id']}"
        if e["layout"] != expected_layout:
            problems.append(f"{e['id']}: LAYOUT {e['layout']} != {expected_layout}")
        if set(e["conjuntos"]) != set(bp.HISTORICAL):
            problems.append(f"{e['id']}: CONJUNTOS {sorted(e['conjuntos'])} != {sorted(bp.HISTORICAL)}")
            continue
        for set_name, set_def in e["conjuntos"].items():
            inherited = set_name in bp.INHERITED_SETS
            if set(set_def["arquivos"]) != set(bp.HISTORICAL[set_name]):
                problems.append(f"{e['id']}/{set_name}: ARQUIVOS_LOGICOS divergentes")
                continue
            for logical, meta in set_def["arquivos"].items():
                expected_path = (bp.HISTORICAL[set_name][logical] if (inherited or e["layout"] == "historico")
                                 else f"{e['layout']}/{set_name}/{logical}")
                if meta["caminho"] != expected_path:
                    problems.append(f"{e['id']}/{set_name}/{logical}: CAMINHO {meta['caminho']} != {expected_path}")
                file = REPO / meta["caminho"]
                if not file.exists():
                    problems.append(f"{e['id']}/{set_name}/{logical}: ARQUIVO_AUSENTE {meta['caminho']}")
                elif sha256_file(file) != meta["sha256"]:
                    problems.append(f"{e['id']}/{set_name}/{logical}: SHA256_DIVERGENTE {meta['caminho']}")
            if inherited and e["anterior"] is not None and (
                    set_def["arquivos"] != by_id[ids[0]]["conjuntos"][set_name]["arquivos"]
                    or set_def.get("herdado_de") != ids[0]):
                problems.append(f"{e['id']}/{set_name}: HERDADO diferente do B0")
            if not inherited and all((REPO / m["caminho"]).exists() for m in set_def["arquivos"].values()):
                derived = json.loads(json.dumps(derive_expectations(set_name, set_files(set_def))))
                if derived != set_def.get("expectativas"):
                    problems.append(f"{e['id']}/{set_name}: EXPECTATIVAS registradas != recalculadas dos arquivos")
    return problems


def build_set(set_name: str, layout: str, classe: str) -> dict:
    """Conjunto com sha256 e expectativas recalculados dos arquivos (layout histórico ou B<n>)."""
    inherited = set_name in bp.INHERITED_SETS
    files = {}
    for logical, historical in bp.HISTORICAL[set_name].items():
        caminho = historical if (inherited or layout == "historico") else f"{layout}/{set_name}/{logical}"
        files[logical] = {"caminho": caminho, "sha256": sha256_file(REPO / caminho)}
    out = {"classe": classe, "herdado_de": ("B0" if inherited and layout != "historico" else None), "arquivos": files,
           "commit_evidencia_historica": bp.EVIDENCE_COMMITS[set_name]}
    out["expectativas"] = (json.loads(json.dumps(derive_expectations(set_name, set_files(out))))
                           if not inherited else {})
    return out
