"""
Registro dos cinco workbooks aprovados na Etapa 2.3 e pipeline comum

    workbook aprovado (SHA-256 conferido)
        -> reader
        -> modelo canônico
        -> seeds (+ manifesto de proveniência)

Os workbooks versionados em `data/workbooks/` são cópias byte a byte
dos arquivos aprovados; o build recusa qualquer arquivo cujo SHA-256
difira do aprovado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tools.workbook_seed.canonical import CanonicalModel, build_canonical_model
from tools.workbook_seed.id_ledger import IdLedger, ledger_path, ledger_payload, load_ledger
from tools.workbook_seed.interblock import (
    InterblockResult,
    interblock_seed,
    seed_dependencies,
    validate_interblock,
)
from tools.workbook_seed.reader import WorkbookData, read_workbook, sha256_of
from tools.workbook_seed.seeds import build_seeds


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_DIR = REPO_ROOT / "data" / "workbooks"
SEED_ROOT = REPO_ROOT / "data" / "seed"
ID_LEDGER_ROOT = REPO_ROOT / "data" / "id_ledger"

SEED_FILES = ("variables", "parameters", "equations", "aggregation_rules", "manifest")
INTERBLOCK_SEED = "interblock_links.json"


class UnapprovedWorkbookError(ValueError):
    """O arquivo não é, byte a byte, o workbook aprovado."""


@dataclass(frozen=True)
class BlockSpec:
    block: str
    sheet: str
    id_base: int
    version: str
    file_name: str
    sha256: str

    @property
    def workbook_path(self) -> Path:
        return WORKBOOK_DIR / self.file_name

    @property
    def seed_dir(self) -> Path:
        return SEED_ROOT / self.block


BLOCKS: dict[str, BlockSpec] = {
    spec.block: spec
    for spec in (
        BlockSpec(
            block="area_41",
            sheet="A41",
            id_base=16000,
            version="v9",
            file_name="descritivo_das_variáveis_A41_v9.xlsx",
            sha256="36bbae135285ad9b3b88d21ef94e2bc9c92f2ef74736412b66bc62de4dcf3f50",
        ),
        BlockSpec(
            block="energy",
            sheet="energy",
            id_base=18000,
            version="v6",
            file_name="descritivo_das_variáveis_energy_v6.xlsx",
            sha256="cfc46031fc2f3f375b87ebbba58676d23ad92f3ee43fb81b353fe5a8247e1df8",
        ),
        BlockSpec(
            block="max_ht",
            sheet="MaxHT",
            id_base=13000,
            version="v10",
            file_name="descritivo_das_variáveis_MaxHT_v10.xlsx",
            sha256="3e40aab12ec0ec07918c5e358145b09f138663f635ca9e7fc0990d1b765b683b",
        ),
        BlockSpec(
            block="production",
            sheet="production",
            id_base=12000,
            version="v10",
            file_name="descritivo_das_variáveis_production_v10.xlsx",
            sha256="302cf18b92ac22c690b3add9bdd1ded0617bfa60636809696d010b8858d72487",
        ),
        BlockSpec(
            block="yield",
            sheet="yield",
            id_base=11000,
            version="v11",
            file_name="descritivo_das_variáveis_yield_v11.xlsx",
            sha256="639e8b980f19bc20429cf9763157ac1828d9067bdbabea3bf3db0badbc2df931",
        ),
    )
}


@dataclass(frozen=True)
class BuildResult:
    spec: BlockSpec
    workbook: WorkbookData
    model: CanonicalModel
    seeds: dict
    id_ledger: IdLedger | None = None


def read_approved_workbook(spec: BlockSpec, path: str | Path | None = None) -> WorkbookData:
    path = Path(path) if path is not None else spec.workbook_path
    digest = sha256_of(path)

    if digest != spec.sha256:
        raise UnapprovedWorkbookError(
            f"{path.name}: SHA-256 {digest} difere do workbook aprovado "
            f"{spec.block} {spec.version} ({spec.sha256})."
        )

    return read_workbook(path, spec.sheet)


def build_block(
    block: str,
    path: str | Path | None = None,
    ledger_root: Path | None = None,
) -> BuildResult:
    """
    IDs: o livro `data/id_ledger/<bloco>.json` fixa o ID de toda
    identidade já emitida (Etapa 2.6B); sem livro, numeração sequencial.
    """

    spec = BLOCKS[block]
    workbook = read_approved_workbook(spec, path)
    id_ledger = load_ledger(ledger_path(ledger_root or ID_LEDGER_ROOT, block))
    model = build_canonical_model(spec.block, workbook, spec.id_base, id_ledger)
    seeds = build_seeds(model, spec.id_base)

    return BuildResult(
        spec=spec, workbook=workbook, model=model, seeds=seeds, id_ledger=id_ledger
    )


def seed_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_seeds(result: BuildResult, seed_dir: Path | None = None) -> None:
    seed_dir = seed_dir or result.spec.seed_dir
    seed_dir.mkdir(parents=True, exist_ok=True)

    for name in SEED_FILES:
        (seed_dir / f"{name}.json").write_text(
            seed_json(result.seeds[name]), encoding="utf-8"
        )


def write_id_ledger(result: BuildResult, ledger_root: Path | None = None) -> Path:
    ledger_root = ledger_root or ID_LEDGER_ROOT
    ledger_root.mkdir(parents=True, exist_ok=True)
    path = ledger_path(ledger_root, result.spec.block)
    path.write_text(
        seed_json(ledger_payload(result.model, result.id_ledger)), encoding="utf-8"
    )

    return path


@dataclass(frozen=True)
class BuildAllResult:
    blocks: dict[str, BuildResult]
    interblock: InterblockResult

    @property
    def interblock_seed(self) -> dict:
        return interblock_seed(
            {block: r.model for block, r in self.blocks.items()}, self.interblock
        )


def build_all(paths: dict[str, str | Path] | None = None) -> BuildAllResult:
    """
    Os cinco blocos e o contrato interbloco declarado em `fonte`:
    resolução do produtor no bloco indicado e validação de contrato,
    instâncias e ciclos sobre o conjunto completo.
    """

    paths = paths or {}
    blocks = {block: build_block(block, paths.get(block)) for block in BLOCKS}
    dependencies = [
        edge
        for block, r in blocks.items()
        for edge in seed_dependencies(block, r.seeds)
    ]
    interblock = validate_interblock(
        {block: r.model for block, r in blocks.items()}, dependencies
    )

    return BuildAllResult(blocks=blocks, interblock=interblock)


def write_interblock_seed(result: BuildAllResult, seed_root: Path | None = None) -> Path:
    seed_root = seed_root or SEED_ROOT
    seed_root.mkdir(parents=True, exist_ok=True)
    path = seed_root / INTERBLOCK_SEED
    path.write_text(seed_json(result.interblock_seed), encoding="utf-8")

    return path


def read_interblock_seed(seed_root: Path | None = None) -> dict:
    seed_root = seed_root or SEED_ROOT
    return json.loads((seed_root / INTERBLOCK_SEED).read_text(encoding="utf-8"))


def read_seed_file(block: str, name: str, seed_root: Path | None = None):
    seed_root = seed_root or SEED_ROOT
    return json.loads((seed_root / block / f"{name}.json").read_text(encoding="utf-8"))
