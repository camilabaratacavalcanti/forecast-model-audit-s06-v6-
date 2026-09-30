"""
Stage 3.4B — Differential Regression (DIFFERENTIAL_REGRESSION_ORACLE).

    python audit/stage3_4/differential/run_differential.py [--no-write]

REFERENCE = 7877551 (runtime pré-Stage-3)    CANDIDATE = HEAD
Classificação: DIFFERENTIAL_REGRESSION_ORACLE — mostra que, para os mesmos
inputs, o candidate produz resultados iguais aos do reference; NÃO prova
correção absoluta (ver STAGE_3_4B_DIFFERENTIAL_REGRESSION.md).

Passos:
  1. pré-condições: `git diff 7877551..HEAD -- data tools` vazio
     (REFERENCE_DATA_TOOLS_INVARIANT) — ou, desde D-TAX-01, provadamente só a
     migração taxonômica autorizada (PASS_AUTHORIZED_TAXONOMY_MIGRATION_D-TAX-01,
     verificado por audit/stage3_4/taxonomy_migration/taxonomy_guard.py) — e `app/` do
     working tree == HEAD;
  2. `git archive <commit> app` de cada versão para um diretório temporário
     (nenhum checkout; o repositório não é tocado);
  3. `runner.py` em subprocesso `python -I` por versão, com o MESMO
     `data/seed`, as mesmas entradas e PYTHONHASHSEED=0; cada versão roda
     de novo com PYTHONHASHSEED=4242 e a saída tem de ser byte a byte igual
     (determinismo do harness);
  4. universo esperado reconstruído a partir dos seeds + contrato 3.4A
     (392 instâncias de equação, 395 de agregação, 3 vetores, 2 datas);
  5. cobertura (faltantes, duplicados, excedentes) por lado e comparação
     exata caso a caso (`compare.py`);
  6. evidência em `evidence/` e código de saída 0 somente se tudo casar.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "taxonomy_migration"))
import taxonomy_guard  # noqa: E402
from compare import CASE_KEY_FIELDS, case_key, compare_case, coverage  # noqa: E402

REFERENCE = "7877551"
EXPECTED = {"EQUATION": 392, "AGGREGATION": 395}          # contrato 3.4A §13
EXPECTED_BY_BLOCK = {
    "EQUATION": {"yield": 198, "production": 81, "energy": 72, "max_ht": 41},
    "AGGREGATION": {"yield": 176, "production": 52, "energy": 17, "max_ht": 150},
}
EXPECTED_AGG_TYPES = {"AVERAGE": 342, "SUM": 42, "WEIGHTED_AVERAGE": 9, "MOVING_AVERAGE": 2}
MIN_VECTORS, MIN_DATES = 3, 2
AUTHORIZED_INVARIANT = "PASS_AUTHORIZED_TAXONOMY_MIGRATION_D-TAX-01"
WRITE = "--no-write" not in sys.argv[1:]


def git(*args, binary=False):
    completed = subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True)
    return completed.stdout if binary else completed.stdout.decode()


def extract(commit: str, root: Path) -> None:
    root.mkdir(parents=True)
    archive = git("archive", commit, "app", binary=True)
    subprocess.run(["tar", "-x", "-C", str(root)], input=archive, check=True)


def run(root: Path, out: Path, seed: str) -> bytes:
    subprocess.run(
        [sys.executable, "-I", str(HERE / "runner.py"), str(root), str(REPO / "data" / "seed"), str(out)],
        cwd=root, check=True, env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": seed},
    )
    return out.read_bytes()


def produce(mutate=None) -> dict:
    """
    Passos 1–3: pré-condições e execução isolada das duas versões (evidência real).
    `mutate` (só Stage 3.4D): função aplicada ao `app/` EXTRAÍDO do candidate, no diretório
    temporário, antes da execução — mutante de código que nunca toca o repositório.
    """
    problems: list[str] = []

    # 1. pré-condições -------------------------------------------------------
    invariant_diff = git("diff", f"{REFERENCE}..HEAD", "--", "data", "tools")
    if invariant_diff == "":
        invariant = "PASS"
    else:
        # D-TAX-01: única exceção autorizada — diff provadamente taxonômico (nomes de
        # blocos), sem efeito em seeds de cálculo. Qualquer outra mudança continua FAIL.
        taxonomy = taxonomy_guard.classify_git(REFERENCE, "HEAD", ("data", "tools"))
        invariant = AUTHORIZED_INVARIANT if taxonomy["taxonomy_only"] else "FAIL"
        if invariant == "FAIL":
            problems += taxonomy["problems"][:5]
    if invariant not in ("PASS", AUTHORIZED_INVARIANT):
        problems.append("REFERENCE_DATA_TOOLS_INVARIANT = FAIL")
    candidate_commit = git("rev-parse", "HEAD").strip()
    reference_commit = git("rev-parse", REFERENCE).strip()
    app_dirty = git("status", "--porcelain", "--", "app")
    if app_dirty:
        problems.append(f"app/ do working tree difere de HEAD: {app_dirty!r}")

    # 2+3. execução isolada --------------------------------------------------
    with tempfile.TemporaryDirectory(prefix="stage3_4b_") as tmp:
        tmp = Path(tmp)
        extract(REFERENCE, tmp / "reference")
        extract("HEAD", tmp / "candidate")
        if mutate is not None:
            mutate(tmp / "candidate")
        raw = {}
        for side in ("reference", "candidate"):
            first = run(tmp / side, tmp / f"{side}_0.json", "0")
            second = run(tmp / side, tmp / f"{side}_4242.json", "4242")
            if first != second:
                problems.append(f"harness não determinístico em {side} (PYTHONHASHSEED 0 x 4242)")
            raw[side] = first
    reference, candidate = (json.loads(raw[s]) for s in ("reference", "candidate"))
    digests = {s: hashlib.sha256(raw[s]).hexdigest() for s in raw}
    for side, payload in (("reference", reference), ("candidate", candidate)):
        if payload["foreign_modules"]:
            problems.append(f"{side} carregou módulos de fora do seu app/: {payload['foreign_modules'][:3]}")
    if reference["app_sha256"] == candidate["app_sha256"]:
        problems.append("reference e candidate carregaram o mesmo código (fingerprint igual)")
    return {"problems": problems, "invariant": invariant, "candidate_commit": candidate_commit,
            "reference_commit": reference_commit, "reference": reference, "candidate": candidate,
            "digests": digests}


def evaluate(reference: dict, candidate: dict) -> dict:
    """
    Passos 4–5: universo esperado, cobertura por lado e comparação exata caso a caso.
    É o detector da regressão diferencial; a Stage 3.4D o reaplica a cópias mutadas
    da evidência real produzida por `produce()`.
    """
    problems: list[str] = []
    # 4. universo esperado -----------------------------------------------------
    vectors, dates = candidate["vectors"], candidate["dates"]
    if reference["vectors"] != vectors or reference["dates"] != dates:
        problems.append("matriz de entradas diferente entre os lados")
    if len(set(vectors)) < MIN_VECTORS or len(set(dates)) < MIN_DATES:
        problems.append(f"matriz insuficiente: {vectors} x {dates}")
    instances = {}
    for payload in (reference, candidate):
        for case in payload["cases"]:
            instances.setdefault((case["block"], case["operation_type"], case["instance_id"]), case)
    expected_keys = {(b, op, i, v, d) for (b, op, i) in instances for v in vectors for d in dates}
    by_op = Counter(op for (_b, op, _i) in instances)
    by_block = Counter((op, b) for (b, op, _i) in instances)
    agg_types = Counter(c.get("aggregation_type") for c in instances.values() if c["operation_type"] == "AGGREGATION")
    if dict(by_op) != EXPECTED:
        problems.append(f"cardinalidade de instâncias {dict(by_op)} != contrato 3.4A {EXPECTED}")
    for op, blocks in EXPECTED_BY_BLOCK.items():
        for block, n in blocks.items():
            if by_block[(op, block)] != n:
                problems.append(f"{op} {block}: {by_block[(op, block)]} != {n}")
    if dict(agg_types) != EXPECTED_AGG_TYPES:
        problems.append(f"tipos de agregação {dict(agg_types)} != {EXPECTED_AGG_TYPES}")

    # 5. cobertura e comparação ----------------------------------------------
    cov = {side: coverage(payload["cases"], expected_keys) for side, payload in
           (("reference", reference), ("candidate", candidate))}
    for side, c in cov.items():
        for kind in ("duplicates", "missing", "unexpected"):
            if c[kind]:
                problems.append(f"{side}: {len(c[kind])} {kind}, ex. {c[kind][0]}")
    ref_by_key = {case_key(c): c for c in reference["cases"]}
    cand_by_key = {case_key(c): c for c in candidate["cases"]}
    rows, differences = [], []
    matched = Counter()
    for key in sorted(expected_keys):
        ref, cand = ref_by_key.get(key), cand_by_key.get(key)
        diff = compare_case(ref, cand)
        base = ref or cand
        if diff:
            differences.append((key, diff))
        else:
            matched[(key[1], key[0])] += 1
        rows.append({
            **dict(zip(CASE_KEY_FIELDS, key)),
            "definition_id": base["definition_id"], "aggregation_type": base.get("aggregation_type", ""),
            "scope": "/".join(str(x) for x in base["scope"]), "period_id": base.get("period_id", ""),
            "reference": json.dumps(ref["outcome"][1:] if ref else None),
            "candidate": json.dumps(cand["outcome"][1:] if cand else None),
            "comparison": "MATCH" if not diff else "|".join(diff),
        })
    if differences:
        problems.append(f"{len(differences)} casos com diferença")

    return {"problems": problems, "vectors": vectors, "dates": dates, "by_op": by_op, "by_block": by_block,
            "agg_types": agg_types, "cov": cov, "rows": rows, "differences": differences, "matched": matched}


def main() -> int:
    produced = produce()
    reference, candidate = produced["reference"], produced["candidate"]
    evaluated = evaluate(reference, candidate)
    problems = produced["problems"] + evaluated["problems"]
    invariant, digests = produced["invariant"], produced["digests"]
    candidate_commit, reference_commit = produced["candidate_commit"], produced["reference_commit"]
    vectors, dates, by_op, by_block = (evaluated[k] for k in ("vectors", "dates", "by_op", "by_block"))
    agg_types, cov, rows = evaluated["agg_types"], evaluated["cov"], evaluated["rows"]
    differences, matched = evaluated["differences"], evaluated["matched"]

    # 6. evidência -------------------------------------------------------------
    table = {}
    for op in ("EQUATION", "AGGREGATION"):
        expected_cases = EXPECTED[op] * len(vectors) * len(dates)
        actual = sum(1 for c in candidate["cases"] if c["operation_type"] == op)
        table[op] = {"instances": by_op[op], "vectors": len(vectors), "dates": len(dates),
                     "expected_cases": expected_cases, "actual_cases": actual,
                     "matched": sum(v for (o, _b), v in matched.items() if o == op),
                     "by_block": {b: {"instances": by_block[(op, b)],
                                      "matched": matched[(op, b)]} for b in sorted(EXPECTED_BY_BLOCK[op])}}
    summary = {
        "oracle_type": "DIFFERENTIAL_REGRESSION_ORACLE",
        "reference_commit": reference_commit, "candidate_commit": candidate_commit,
        "REFERENCE_DATA_TOOLS_INVARIANT": invariant,
        "isolation": {"mechanism": "git archive <commit> app -> tempdir; python -I subprocess per side",
                      "reference_app_sha256": reference["app_sha256"],
                      "candidate_app_sha256": candidate["app_sha256"],
                      "reference_foreign_modules": reference["foreign_modules"],
                      "candidate_foreign_modules": candidate["foreign_modules"],
                      "python": [reference["python"], candidate["python"]]},
        "harness_determinism": {"hash_seeds": ["0", "4242"], "runner_output_sha256": digests},
        "vectors": vectors, "dates": dates,
        "coverage": table, "aggregation_types": dict(agg_types),
        "side_coverage": {s: {k: (len(v) if isinstance(v, list) else v) for k, v in c.items()} for s, c in cov.items()},
        "differences": len(differences),
        "difference_types": dict(Counter(t for _k, d in differences for t in d)),
        "problems": problems,
        "result": "PASS" if not problems else "FAIL",
    }
    if WRITE:
        evidence = HERE / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "differential_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (evidence / "differential_cases.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        if differences:
            (evidence / "DIFFERENCES_FOUND.json").write_text(
                json.dumps([{"key": list(k), "types": d} for k, d in differences], indent=1) + "\n",
                encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("reference_commit", "candidate_commit",
                                             "REFERENCE_DATA_TOOLS_INVARIANT", "coverage", "aggregation_types",
                                             "differences", "problems", "result")}, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
