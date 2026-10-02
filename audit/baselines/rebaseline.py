"""
Stage 4C — re-baseline governado.

    python audit/baselines/rebaseline.py --id B<n> --stage <stage> --reason "<motivo>"
    python audit/baselines/rebaseline.py --approve B<n>
    python audit/baselines/rebaseline.py --check
    python audit/baselines/rebaseline.py --init-b0        (uma única vez: cria o registro com B0)

Proposta (`--id`):
  * recusa árvore suja (`git status --porcelain --untracked-files=all` não vazio), motivo ausente/vazio,
    id inválido ou já existente, diretório já existente e `current` não APPROVED;
  * regenera cada conjunto R, em ordem de dependência, com `--baseline-dir audit/baselines/B<n>`
    (os harnesses só recebem o diretório);
  * VERIFICA em seguida, com `--no-write --baseline-dir`, que a execução viva reproduz o que foi gravado
    (e os recálculos independentes `--check` da 4A e da 4B);
  * escreve SÓ em `audit/baselines/B<n>/` (conjuntos + DIFF_REPORT.md) e acrescenta a entrada PROPOSED
    ao registro; o `current` não muda. Qualquer falha remove `audit/baselines/B<n>/` e não toca o registro.
Aprovação (`--approve`): entrada PROPOSED cujo `anterior` é o current e cujos arquivos conferem ->
APPROVED + selo; o `current` passa a ser ela.
Verificação (`--check`): nada é escrito; exit 0 só sem problemas.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import baseline_paths as bp  # noqa: E402
import baseline_registry as reg  # noqa: E402

BLOCKS = ("yield", "production", "energy", "max_ht", "area_41")
SEED_FILES = {"variables": "variable_id", "parameters": "parameter_id", "equations": "equation_id",
              "aggregation_rules": "aggregation_rule_id"}

# (rótulo, argumentos, isolado) — regeneração e verificação, em ordem de dependência.
GENERATION = [
    ("stage3_2_plan", ["audit/stage3_2_execution_orchestration/evidence/analysis_stage3_2.py"], False),
    ("stage3_4c_integrated", ["audit/stage3_4/integrated/run_integrated.py"], False),
    ("stage4a_contract", ["audit/stage4a/derive_4a.py"], False),
    ("stage4a_integrated", ["audit/stage4a/integrated/run_integrated_4a.py"], False),
    ("stage4b_contract", ["audit/stage4b/derive_4b.py"], False),
    ("stage4b_temporal T2", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T2"], False),
    ("stage4b_temporal T1", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T1"], False),
    ("stage4b_temporal T3", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T3"], False),
]
VERIFICATION = [
    ("3.4C x referência", ["audit/stage3_4/integrated/run_integrated.py", "--no-write"], False),
    ("4A recálculo independente", ["audit/stage4a/independent_count.py", "--check"], True),
    ("4A expectativas", ["audit/stage4a/derive_4a.py", "--no-write"], False),
    ("4A integrado x referência", ["audit/stage4a/integrated/run_integrated_4a.py", "--no-write"], False),
    ("4B recálculo independente", ["audit/stage4b/independent_calendar.py", "--check"], True),
    ("4B expectativas", ["audit/stage4b/derive_4b.py", "--no-write"], False),
    ("4B T2 x referência", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T2", "--no-write"], False),
    ("4B T1 x referência", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T1", "--no-write",
                            "--skip-extras"], False),
    ("4B T3 x referência", ["audit/stage4b/temporal/run_temporal_4b.py", "--range", "T3", "--no-write",
                            "--skip-extras"], False),
]


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def git_bytes(spec: str) -> bytes | None:
    done = subprocess.run(["git", "show", spec], cwd=REPO, capture_output=True)
    return done.stdout if done.returncode == 0 else None


def clean_env() -> dict:
    # As evidências B0 foram geradas sem PYTHONHASHSEED no ambiente (o RUN_A registra esse valor).
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}


def run_step(label: str, args: list[str], isolated: bool, baseline: Path) -> dict:
    command = [sys.executable, *(["-I"] if isolated else []), *args, "--baseline-dir", str(baseline)]
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True, env=clean_env())
    problems = []
    try:
        problems = json.loads(done.stdout).get("problems", [])
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"label": label, "command": " ".join(command[1:]).replace(str(REPO) + "/", ""),
            "returncode": done.returncode, "problems": problems[:10], "stderr_tail": done.stderr.strip()[-1500:]}


def fail(message: str) -> int:
    print(json.dumps({"result": "REFUSED", "reason": message}, ensure_ascii=False, indent=1))
    return 2


# ------------------------------------------------------------------ DIFF_REPORT
def seed_snapshot(commit: str | None) -> dict:
    """{bloco: {arquivo: {id}}}, ledger aposentado, vínculos e workbooks — num commit ou na árvore (None)."""
    def read(relative):
        if commit is None:
            file = REPO / relative
            return json.loads(file.read_text(encoding="utf-8")) if file.exists() else None
        raw = git_bytes(f"{commit}:{relative}")
        return json.loads(raw) if raw is not None else None
    out = {"blocks": {}, "retired": {}, "links": None}
    for block in BLOCKS:
        out["blocks"][block] = {name: sorted(r[key] for r in (read(f"data/seed/{block}/{name}.json") or []))
                                for name, key in SEED_FILES.items()}
        ledger = read(f"data/id_ledger/{block}.json") or {"retired": []}
        out["retired"][block] = sorted(r["entity_id"] for r in ledger.get("retired", []))
    links = read("data/seed/interblock_links.json")
    out["links"] = {
        "declared": len(links["links"]) + len(links["pending"]) + len(links["rejected"]),
        "valid": len(links["links"]), "pending": len(links["pending"]), "rejected": len(links["rejected"]),
        "valid_set": sorted(f"{x['consumer_block']}.{x['consumer_definition']}<-{x['source_block']}."
                            f"{x['source_definition']}" for x in links["links"]),
        "pending_set": sorted(f"{x['consumer_block']}.{x['consumer_definition']}<-{x['source_block']}"
                              for x in links["pending"]),
        "workbooks": {b: w["file_name"] + " " + w["sha256"][:12] for b, w in sorted(links["workbooks"].items())},
    }
    return out


def flatten(obj, prefix="") -> dict:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    return {prefix: obj}


def short(value, limit=120) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def file_diff(old: Path, new: Path) -> list[str]:
    if not old.exists() or not new.exists():
        return [f"arquivo {'novo' if not old.exists() else 'removido'}"]
    if old.read_bytes() == new.read_bytes():
        return []
    lines = []
    if old.suffix == ".csv":
        a = list(csv.DictReader(io.StringIO(old.read_text(encoding="utf-8"))))
        b = list(csv.DictReader(io.StringIO(new.read_text(encoding="utf-8"))))
        key = (list(a[0]) if a else list(b[0]))[0]
        ka, kb = [r[key] for r in a], [r[key] for r in b]
        lines.append(f"linhas {len(a)} → {len(b)}; `{key}` acrescentados {len(set(kb) - set(ka))} "
                     f"{short(sorted(set(kb) - set(ka))[:12])}; removidos {len(set(ka) - set(kb))} "
                     f"{short(sorted(set(ka) - set(kb))[:12])}")
        common = set(ka) & set(kb)
        changed = sorted(k for k in common if {r[key]: r for r in a}[k] != {r[key]: r for r in b}[k])
        lines.append(f"linhas comuns alteradas: {len(changed)} {short(changed[:8])}")
    elif old.suffix == ".json":
        fa = flatten(json.loads(old.read_text(encoding="utf-8")))
        fb = flatten(json.loads(new.read_text(encoding="utf-8")))
        keys = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
        lines.append(f"campos alterados: {len(keys)}")
        lines += [f"`{k}`: {short(fa.get(k), 80)} → {short(fb.get(k), 80)}" for k in keys[:25]]
        if len(keys) > 25:
            lines.append(f"… +{len(keys) - 25} campos")
    else:
        lines.append("conteúdo alterado")
    return lines


def diff_report(new_entry: dict, previous: dict) -> str:
    out = [f"# DIFF_REPORT — {new_entry['id']} (PROPOSED) x {previous['id']} (current)", "",
           f"- stage: `{new_entry['stage']}`", f"- motivo: {new_entry['motivo']}",
           f"- commit_comportamento: `{previous['commit_comportamento'][:12]}` → `{new_entry['commit_comportamento'][:12]}`",
           f"- data: {new_entry['data']}", "",
           "## 1. Conteúdo (seeds, ledger, vínculos) entre os commits de comportamento", ""]
    before, after = seed_snapshot(previous["commit_comportamento"]), seed_snapshot(None)
    out += ["| bloco | arquivo | antes | depois | novos | removidos |", "|---|---|---|---|---|---|"]
    for block in BLOCKS:
        for name in SEED_FILES:
            a, b = set(before["blocks"][block][name]), set(after["blocks"][block][name])
            if a != b or name == "variables":
                out.append(f"| {block} | {name} | {len(a)} | {len(b)} | {', '.join(sorted(b - a)) or '—'} | "
                           f"{', '.join(sorted(a - b)) or '—'} |")
    out += ["", "| bloco | aposentados no ledger (novos) |", "|---|---|"]
    for block in BLOCKS:
        new_retired = sorted(set(after["retired"][block]) - set(before["retired"][block]))
        out.append(f"| {block} | {', '.join(new_retired) or '—'} |")
    la, lb = before["links"], after["links"]
    out += ["", "| vínculos | antes | depois |", "|---|---|---|"]
    for k in ("declared", "valid", "pending", "rejected"):
        out.append(f"| {k} | {la[k]} | {lb[k]} |")
    for k in ("valid_set", "pending_set"):
        added, removed = sorted(set(lb[k]) - set(la[k])), sorted(set(la[k]) - set(lb[k]))
        out.append(f"| {k}: acrescentados / removidos | {len(added)} {short(added, 400)} | "
                   f"{len(removed)} {short(removed, 400)} |")
    out += ["", "| workbook | antes | depois |", "|---|---|---|"]
    for block in sorted(set(la["workbooks"]) | set(lb["workbooks"])):
        if la["workbooks"].get(block) != lb["workbooks"].get(block):
            out.append(f"| {block} | {la['workbooks'].get(block)} | {lb['workbooks'].get(block)} |")
    out += ["", "## 2. Conjuntos R (arquivo a arquivo)", ""]
    for set_name in bp.R_SETS:
        old_set, new_set = previous["conjuntos"][set_name], new_entry["conjuntos"][set_name]
        out.append(f"### {set_name}")
        for logical in bp.R_SETS[set_name]:
            a, b = old_set["arquivos"][logical], new_set["arquivos"][logical]
            status = "IGUAL" if a["sha256"] == b["sha256"] else "ALTERADO"
            out.append(f"- `{logical}`: {status} (`{a['sha256'][:12]}` → `{b['sha256'][:12]}`)")
            for line in file_diff(REPO / a["caminho"], REPO / b["caminho"]):
                out.append(f"  - {line}")
        ea, eb = flatten(old_set["expectativas"]), flatten(new_set["expectativas"])
        changed = sorted(k for k in set(ea) | set(eb) if ea.get(k) != eb.get(k))
        out.append(f"- expectativas alteradas: {len(changed)}")
        out += [f"  - `{k}`: {short(ea.get(k), 90)} → {short(eb.get(k), 90)}" for k in changed[:30]]
        out.append("")
    out += ["## 3. Conjuntos herdados (H/E)", "",
            "Não regenerados: " + ", ".join(f"`{s}`" for s in bp.INHERITED_SETS) + " (iguais a B0).", ""]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ comandos
def propose(entry_id: str, stage: str, reason: str) -> int:
    if not reason or not reason.strip():
        return fail("motivo (--reason) ausente ou vazio")
    registry = reg.load()
    if any(e["id"] == entry_id for e in registry["entries"]):
        return fail(f"id {entry_id} já existe no registro")
    if not re.fullmatch(r"B[1-9][0-9]*(-[a-z0-9]+)?", entry_id or ""):
        return fail(f"id inválido {entry_id!r} (esperado B<n> ou B<n>-<sufixo>)")
    if not stage or not stage.strip():
        return fail("stage (--stage) ausente ou vazio")
    dirty = git("status", "--porcelain", "--untracked-files=all")
    if dirty:
        return fail(f"árvore suja: {dirty.splitlines()[:5]}")
    if registry["entries"][-1]["status"] != "APPROVED":
        return fail(f"há proposta pendente: {registry['entries'][-1]['id']}")
    problems = reg.verify(registry)
    if problems:
        return fail(f"registro inválido antes da proposta: {problems[:5]}")
    target = HERE / entry_id
    if target.exists():
        return fail(f"{target.relative_to(REPO)} já existe")
    previous = reg.current(registry)
    steps = []
    try:
        for label, args, isolated in GENERATION:
            steps.append(run_step(label, args, isolated, target))
            if steps[-1]["returncode"] != 0:
                raise RuntimeError(f"regeneração falhou em {label}")
        for label, args, isolated in VERIFICATION:
            steps.append(run_step(label, args, isolated, target))
            if steps[-1]["returncode"] != 0:
                raise RuntimeError(f"verificação falhou em {label}")
        expected = {f"{s}/{logical}" for s in bp.R_SETS for logical in bp.R_SETS[s]}
        written = {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}
        if written != expected:
            raise RuntimeError(f"arquivos fora do esperado: extra {sorted(written - expected)[:5]}, "
                               f"faltando {sorted(expected - written)[:5]}")
    except RuntimeError as error:
        shutil.rmtree(target, ignore_errors=True)
        print(json.dumps({"result": "FAILED", "reason": str(error), "steps": steps}, ensure_ascii=False, indent=1))
        return 1
    layout = f"audit/baselines/{entry_id}"
    entry = {"id": entry_id, "commit_comportamento": git("rev-parse", "HEAD").strip(), "stage": stage.strip(),
             "motivo": reason.strip(), "data": date.today().isoformat(), "anterior": previous["id"],
             "status": "PROPOSED", "layout": layout,
             "conjuntos": {name: reg.build_set(name, layout, reg.SET_CLASSES[name]) for name in bp.HISTORICAL},
             "execucao": [{k: s[k] for k in ("label", "command", "returncode")} for s in steps]}
    (target / "DIFF_REPORT.md").write_text(diff_report(entry, previous), encoding="utf-8")
    registry["entries"].append(entry)
    reg.dump(registry)
    print(json.dumps({"result": "PROPOSED", "id": entry_id, "current": registry["current"],
                      "diff_report": f"{layout}/DIFF_REPORT.md", "steps": [s["label"] for s in steps]},
                     ensure_ascii=False, indent=1))
    return 0


def approve(entry_id: str) -> int:
    registry = reg.load()
    try:
        entry = reg.entry(registry, entry_id)
    except KeyError as error:
        return fail(str(error))
    if entry["status"] != "PROPOSED":
        return fail(f"{entry_id} está {entry['status']}, não PROPOSED")
    if entry["anterior"] != registry["current"]:
        return fail(f"{entry_id}.anterior = {entry['anterior']} != current {registry['current']}")
    entry["status"] = "APPROVED"
    entry["aprovado_em"] = date.today().isoformat()
    candidate = {**registry, "current": entry_id}
    problems = [p for p in reg.verify(candidate) if not p.startswith(f"{entry_id}: SELO")]
    if problems:
        return fail(f"verificação falhou: {problems[:5]}")
    entry["selo"] = reg.seal(entry)
    registry["current"] = entry_id
    reg.dump(registry)
    print(json.dumps({"result": "APPROVED", "id": entry_id, "current": entry_id, "selo": entry["selo"]},
                     ensure_ascii=False, indent=1))
    return 0


def check() -> int:
    registry = reg.load()
    problems = reg.verify(registry)
    for e in registry["entries"]:
        if e["layout"] != "historico":
            root = REPO / e["layout"]
            registered = {f"{s}/{logical}" for s in bp.R_SETS for logical in bp.R_SETS[s]} | {"DIFF_REPORT.md"}
            present = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} if root.exists() else set()
            if present != registered:
                problems.append(f"{e['id']}: ARQUIVOS_NAO_REGISTRADOS {sorted(present ^ registered)[:5]}")
    print(json.dumps({"current": registry.get("current"), "entries": [(e["id"], e["status"]) for e in
                                                                      registry["entries"]],
                      "problems": problems, "result": "PASS" if not problems else "FAIL"},
                     ensure_ascii=False, indent=1))
    return 0 if not problems else 1


def init_b0() -> int:
    if reg.REGISTRY.exists():
        return fail("o registro já existe; B0 só é criado uma vez")
    entry = {"id": "B0", "commit_comportamento": git("rev-parse", "f573c1b").strip(), "stage": "4C",
             "motivo": "baseline inicial: evidência existente das Stages 3.2–4B (sem cópia), "
                       "reproduzida integralmente na Fase 0 da 4C",
             "data": date.today().isoformat(), "anterior": None, "status": "APPROVED", "layout": "historico",
             "conjuntos": {name: reg.build_set(name, "historico", reg.SET_CLASSES[name]) for name in bp.HISTORICAL},
             "aprovado_em": date.today().isoformat()}
    entry["selo"] = reg.seal(entry)
    reg.dump({"schema": reg.SCHEMA, "current": "B0", "entries": [entry]})
    return check()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id")
    parser.add_argument("--stage")
    parser.add_argument("--reason")
    parser.add_argument("--approve")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--init-b0", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.init_b0:
        return init_b0()
    if args.approve:
        return approve(args.approve)
    if args.id is not None or args.reason is not None or args.stage is not None:
        return propose(args.id, args.stage, args.reason)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
