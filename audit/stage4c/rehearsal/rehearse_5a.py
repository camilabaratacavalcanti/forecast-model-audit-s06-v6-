"""
Stage 4C.3 — ensaio da próxima stage (5A) e prova de obrigatoriedade do re-baseline.

    python audit/stage4c/rehearsal/rehearse_5a.py --scenario R1 --energy <xlsx> --maxht <xlsx> [--write]
    python audit/stage4c/rehearsal/rehearse_5a.py --scenario R2a|R2b [--write]

Tudo acontece numa CÓPIA TEMPORÁRIA (`git clone --shared` do HEAD + árvore atual de audit/, tests/,
em `tempfile.TemporaryDirectory`); a árvore de trabalho nunca é tocada e os workbooks anexos nunca
entram no repositório. A saída é relatório (JSON) em stdout; com `--write` grava em
`audit/stage4c/rehearsal/` só listas e resumos (`<cenário>_report.json`; no R1 também o DIFF_REPORT
do B1-ensaio). Cada falha é classificada pela classe do inventário 4C (guard_inventory.json + adendo).

  R1  ensaio real da 5A: copia os workbooks energy v9 e MaxHT v13 para data/workbooks/ do clone,
      atualiza BlockSpec (versão, arquivo, sha256), acrescenta 5 unidades ao enum (variáveis e
      parâmetros), regenera seeds/ledger/vínculos (`python -m tools.workbook_seed`) e roda a suíte:
        fase "antes":  suíte sem re-baseline -> falhas por classe;
        rebaseline:    `audit/baselines/rebaseline.py --id B1-ensaio ...` + aprovação no clone;
        fase "depois": suíte de novo -> deve restar só classe C.
  R2a mudança em app/ sem efeito de comportamento (comentário + unidade nova no enum) -> suíte.
  R2b mudança de comportamento SEM re-baseline (coeficiente de equação num seed) -> testes R falham.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NEW_UNITS = ("kWh/tv", "tv/MWh", "tv/t carvão", "GJ/d", "m³/d")
UNIT_FILES = ("app/validation/variable_seed_validator.py", "app/validation/parameter_seed_validator.py")


def sh(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, check=check)


def clean_env() -> dict:
    # mesmo ambiente da evidência histórica e do rebaseline.py: sem PYTHONHASHSEED/PYTHONPATH
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}


RECLASSIFIED = {"tests/test_stage4b_oracle.py::test_live_oracle_t2_and_stated_run": "C"}   # F4C-05


def classify(test_id: str) -> str:
    inventory = json.loads((REPO / "audit/stage4c/inventory/guard_inventory.json").read_text(encoding="utf-8"))
    classes = {e["test"]: e["class"] for e in inventory["entries"]}
    classes.update(RECLASSIFIED)
    return classes.get(test_id.split("[")[0], "FORA_DO_INVENTARIO")


def by_class(failed: list[str]) -> dict:
    out = {}
    for test_id in failed:
        out.setdefault(classify(test_id), []).append(test_id)
    return {k: sorted(v) for k, v in sorted(out.items())}


def build_tree(root: Path) -> None:
    head = sh(["git", "rev-parse", "HEAD"], REPO).stdout.strip()
    sh(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(root)], REPO)
    sh(["git", "checkout", "-q", head], root)
    # árvore atual (inclui trabalho ainda não commitado da 4C) de audit/ e tests/
    for name in ("audit", "tests"):
        shutil.rmtree(root / name, ignore_errors=True)
        shutil.copytree(REPO / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    sh(["git", "add", "-A"], root)
    sh(["git", "-c", "user.name=ensaio", "-c", "user.email=ensaio@local", "commit", "-q", "--allow-empty",
        "-m", "ensaio: árvore atual de audit/ e tests/"], root)


def add_units(root: Path, units=NEW_UNITS) -> None:
    for relative in UNIT_FILES:
        path = root / relative
        data = path.read_bytes()
        eol = b"\r\n" if b"\r\n" in data else b"\n"
        anchor = b"ALLOWED_UNITS = {" + eol
        assert data.count(anchor) == 1, relative
        extra = b"".join(b'    "' + u.encode() + b'",' + eol for u in units)
        path.write_bytes(data.replace(anchor, anchor + extra))


def update_block_spec(root: Path, block: str, version: str, file_name: str, digest: str) -> None:
    path = root / "tools/workbook_seed/blocks.py"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'(block="' + block + r'",.*?version=")[^"]+(",\s*file_name=")[^"]+(",\s*sha256=")[0-9a-f]+(")',
                         re.S)
    new, n = pattern.subn(lambda m: m.group(1) + version + m.group(2) + file_name + m.group(3) + digest + m.group(4), text)
    assert n == 1, block
    path.write_text(new, encoding="utf-8")


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_suite(root: Path) -> dict:
    done = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", "--tb=no"], root,
              env=clean_env(), check=False)
    failed = sorted({line.split(" ", 1)[1].split(" - ")[0] for line in done.stdout.splitlines()
                     if line.startswith(("FAILED ", "ERROR "))})
    summary = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    return {"returncode": done.returncode, "summary": summary, "failed": failed, "by_class": by_class(failed),
            "failure_lines": [line[:400] for line in done.stdout.splitlines() if line.startswith(("FAILED ", "ERROR "))]}


def commit_all(root: Path, message: str) -> None:
    sh(["git", "add", "-A"], root)
    sh(["git", "-c", "user.name=ensaio", "-c", "user.email=ensaio@local", "commit", "-q", "-m", message], root)


def scenario_r1(root: Path, energy: Path, maxht: Path) -> dict:
    out = {"scenario": "R1"}
    workbooks = root / "data" / "workbooks"
    for block, src, version, name in (("energy", energy, "v9", "descritivo_das_variáveis_energy_v9.xlsx"),
                                      ("max_ht", maxht, "v13", "descritivo_das_variáveis_MaxHT_v13.xlsx")):
        shutil.copy2(src, workbooks / name)
        update_block_spec(root, block, version, name, sha256(workbooks / name))
        out[f"{block}_workbook"] = {"file": name, "sha256": sha256(workbooks / name)}
    add_units(root)
    seed = sh([sys.executable, "-m", "tools.workbook_seed"], root, env=clean_env(), check=False)
    out["workbook_seed"] = {"returncode": seed.returncode, "tail": seed.stdout.strip().splitlines()[-8:],
                            "stderr_tail": seed.stderr.strip().splitlines()[-5:]}
    if seed.returncode != 0:
        return out
    commit_all(root, "ensaio 5A: energy v9, MaxHT v13, 5 unidades, seeds regenerados")
    out["before_rebaseline"] = run_suite(root)
    rb = root / "audit/baselines/rebaseline.py"
    if rb.exists():
        done = sh([sys.executable, str(rb), "--id", "B1-ensaio", "--stage", "ensaio-5A", "--reason", "ensaio 4C"],
                  root, env=clean_env(), check=False)
        out["rebaseline"] = {"returncode": done.returncode, "stdout_tail": done.stdout.strip().splitlines()[-30:],
                             "stderr_tail": done.stderr.strip().splitlines()[-5:]}
        report = root / "audit/baselines/B1-ensaio/DIFF_REPORT.md"
        out["diff_report"] = report.read_text(encoding="utf-8") if report.exists() else None
        if done.returncode == 0:
            approve = sh([sys.executable, str(rb), "--approve", "B1-ensaio"], root, env=clean_env(), check=False)
            out["approve"] = {"returncode": approve.returncode, "stdout_tail": approve.stdout.strip().splitlines()[-5:]}
            commit_all(root, "ensaio 5A: re-baseline B1-ensaio aprovado")
            out["after_rebaseline"] = run_suite(root)
    return out


def scenario_r2a(root: Path) -> dict:
    path = root / UNIT_FILES[0]
    data = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    path.write_bytes(b"# ensaio R2a: comentario sem efeito de comportamento" + eol + data)
    add_units(root, ("kWh/tv",))
    commit_all(root, "ensaio R2a: comentário + unidade nova")
    return {"scenario": "R2a", "suite": run_suite(root)}


def scenario_r2b(root: Path) -> dict:
    path = root / "data/seed/area_41/equations.json"
    text = path.read_text(encoding="utf-8")
    assert text.count("19.475*ln(VAR16001) - 85.999") == 1
    path.write_text(text.replace("19.475*ln(VAR16001) - 85.999", "19.476*ln(VAR16001) - 85.999"), encoding="utf-8")
    commit_all(root, "ensaio R2b: coeficiente de EQ16001 alterado sem re-baseline")
    return {"scenario": "R2b", "changed": "EQ16001: 19.475 -> 19.476 (data/seed/area_41/equations.json)",
            "suite": run_suite(root)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=("R1", "R2a", "R2b"))
    parser.add_argument("--energy")
    parser.add_argument("--maxht")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before = sh(["git", "status", "--porcelain", "--", "app", "data", "tools"], REPO).stdout
    with tempfile.TemporaryDirectory(prefix=f"stage4c_{args.scenario}_") as tmp:
        root = Path(tmp) / "tree"
        build_tree(root)
        if args.scenario == "R1":
            out = scenario_r1(root, Path(args.energy), Path(args.maxht))
        elif args.scenario == "R2a":
            out = scenario_r2a(root)
        else:
            out = scenario_r2b(root)
    after = sh(["git", "status", "--porcelain", "--", "app", "data", "tools"], REPO).stdout
    out["working_tree_untouched"] = before == after == ""
    if args.write:
        report = dict(out)
        diff = report.pop("diff_report", None)
        (HERE / f"{args.scenario}_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
        if diff:
            (HERE / "R1_B1_ENSAIO_DIFF_REPORT.md").write_text(diff, encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
