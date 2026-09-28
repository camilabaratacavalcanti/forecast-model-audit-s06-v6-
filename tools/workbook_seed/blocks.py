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
from tools.workbook_seed.reader import WorkbookData, read_workbook, sha256_of
from tools.workbook_seed.seeds import build_seeds


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_DIR = REPO_ROOT / "data" / "workbooks"
SEED_ROOT = REPO_ROOT / "data" / "seed"

SEED_FILES = ("variables", "parameters", "equations", "aggregation_rules", "manifest")


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
            version="v8",
            file_name="descritivo_das_variáveis_A41_v8.xlsx",
            sha256="be2372b4f4f35f5aea720dcc00c680f3e47e359138995dd35a6dcabd3d603528",
        ),
        BlockSpec(
            block="energy",
            sheet="energy",
            id_base=18000,
            version="v5",
            file_name="descritivo_das_variáveis_energy_v5.xlsx",
            sha256="34c1c88af318e57026c08c21fd2a1cf308258e575eddbb11d98ba0bba6878047",
        ),
        BlockSpec(
            block="max_ht",
            sheet="MaxHT",
            id_base=13000,
            version="v9",
            file_name="descritivo_das_variáveis_MaxHT_v9.xlsx",
            sha256="74d5cbb7624d5c7101b5f25ecd76e156c9d019968c7e5f9af2ed04aa50b27004",
        ),
        BlockSpec(
            block="production",
            sheet="production",
            id_base=12000,
            version="v6",
            file_name="descritivo_das_variáveis_production_v6.xlsx",
            sha256="17cb83ca15d92c0b3243a606ddfd194a110dcc4f01fb71bf30511a4c6fb07210",
        ),
        BlockSpec(
            block="yield",
            sheet="yield",
            id_base=11000,
            version="v9",
            file_name="descritivo_das_variáveis_yield_v9.xlsx",
            sha256="1c7b5684cc49d9498edceb520ced2e8a1f673812057d4094846820074098a76b",
        ),
    )
}


@dataclass(frozen=True)
class BuildResult:
    spec: BlockSpec
    workbook: WorkbookData
    model: CanonicalModel
    seeds: dict


def read_approved_workbook(spec: BlockSpec, path: str | Path | None = None) -> WorkbookData:
    path = Path(path) if path is not None else spec.workbook_path
    digest = sha256_of(path)

    if digest != spec.sha256:
        raise UnapprovedWorkbookError(
            f"{path.name}: SHA-256 {digest} difere do workbook aprovado "
            f"{spec.block} {spec.version} ({spec.sha256})."
        )

    return read_workbook(path, spec.sheet)


def build_block(block: str, path: str | Path | None = None) -> BuildResult:
    spec = BLOCKS[block]
    workbook = read_approved_workbook(spec, path)
    model = build_canonical_model(spec.block, workbook, spec.id_base)
    seeds = build_seeds(model, spec.id_base)

    return BuildResult(spec=spec, workbook=workbook, model=model, seeds=seeds)


def seed_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_seeds(result: BuildResult, seed_dir: Path | None = None) -> None:
    seed_dir = seed_dir or result.spec.seed_dir
    seed_dir.mkdir(parents=True, exist_ok=True)

    for name in SEED_FILES:
        (seed_dir / f"{name}.json").write_text(
            seed_json(result.seeds[name]), encoding="utf-8"
        )


def read_seed_file(block: str, name: str, seed_root: Path | None = None):
    seed_root = seed_root or SEED_ROOT
    return json.loads((seed_root / block / f"{name}.json").read_text(encoding="utf-8"))
