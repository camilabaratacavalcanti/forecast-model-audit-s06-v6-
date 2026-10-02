"""
Stage 5A.3 — atribuição das diferenças de valor do B1 (revisão do DIFF_REPORT).

    python audit/stage5a/b1_value_attribution.py [--write]

O fixture 3.4C/4A atribui a cada entrada o valor `1 + 0.01·i + 0.001·k (+ 0.0001·dia)`, onde `i` é a POSIÇÃO
da variável em `plan.required_inputs`. A 5A troca duas entradas (max_ht VAR13003 -> VAR13119, D-5A-3;
energy VAR18031 -> VAR18053, energy v9), o que desloca `i` das entradas seguintes e muda valores por
construção do fixture, não por fórmula.

Prova: executa o motor do HEAD (5A) nas 32 datas da 3.4C com as entradas reindexadas pela ordem de B0
(`e262e03`, clone temporário), por identidade (nome, frequência, escopo); as entradas renomeadas recebem o
índice da antiga. Compara o resultado final em 2026-02-01 com a evidência B0 (`targets.csv` da 3.4C):
    * alvo comum: igualdade EXATA (mesmo encode);
    * alvo novo cuja identidade só mudou de grafia (alimentação_* -> alimentacao_*): igual ao alvo antigo;
    * VAR18031 (agora calculado = VAR18053 / 1): igual à entrada que B0 lhe dava;
    * VAR13123 (lth_total_ag = VAR13063 × 24): soma mensal VAR13067 inalterada (fim do ×24 preserva a aritmética).
Nada no repositório é escrito, exceto `audit/stage5a/evidence/b1_value_attribution.json` com `--write`.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INTEGRATED = REPO / "audit" / "stage3_4" / "integrated"
sys.path.insert(0, str(REPO / "audit" / "baselines"))
sys.path.insert(0, str(INTEGRATED))
sys.path.insert(0, str(REPO))

import historical  # noqa: E402
import fixture  # noqa: E402
import run_integrated as ri  # noqa: E402

from app.engine.scope_resolver import ScopeResolver  # noqa: E402

B0_COMMIT = "e262e03"
B0_TARGETS = REPO / "audit" / "stage3_4" / "integrated" / "evidence" / "targets.csv"
RENAMED_INPUTS = {"VAR13119": "VAR13003", "VAR18053": "VAR18031"}   # novo -> antigo (mesma entrada sintética)

_B0_INPUTS = """
import json, sys
sys.path.insert(0, "audit/stage3_4/integrated"); sys.path.insert(0, ".")
import fixture, run_integrated as ri
o = fixture.build("A")
p = ri.integrated_plan(o)
d = o.catalog.variable_definitions
print(json.dumps([[v, d.get(v).variable_name, d.get(v).frequency, d.get(v).scope_type, d.get(v).scope_value]
                  for v in p.required_inputs]))
"""


def identity(definition) -> tuple:
    return (definition.variable_name.replace("alimentação", "alimentacao"), definition.frequency,
            definition.scope_type, definition.scope_value)


def main() -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="stage5a_b1attr_") as tmp:
        clone = historical.checkout(B0_COMMIT, Path(tmp) / "tree")
        done = historical.run(clone, "-c", _B0_INPUTS, isolated=True)
        if done.returncode != 0:
            raise SystemExit(done.stderr[-2000:])
        b0_inputs = json.loads(done.stdout)
    b0_index = {v: i for i, (v, *_rest) in enumerate(b0_inputs)}

    orchestrator = fixture.build("A")
    plan = ri.integrated_plan(orchestrator)
    definitions = orchestrator.catalog.variable_definitions
    head_index = {}
    for variable_id in plan.required_inputs:
        old = RENAMED_INPUTS.get(variable_id, variable_id)
        if old not in b0_index:
            problems.append(f"entrada sem correspondente em B0: {variable_id}")
            continue
        head_index[variable_id] = b0_index[old]
    dropped = sorted(set(b0_index) - {RENAMED_INPUTS.get(v, v) for v in plan.required_inputs})

    def seed_inputs_b0(orch, pl, context, day):
        orch.seed_parameters(context)
        for variable_id in pl.required_inputs:
            d = definitions.get(variable_id)
            period = ri.PERIODS.effective_window(d.frequency, day).period_id
            for k, (st, sv) in enumerate(ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)):
                value = d.allowed_values[0] if d.is_categorical else fixture.input_value(
                    head_index[variable_id], k, d.frequency, day)
                context.set_variable_value(variable_id, value, st, sv, period)

    fixture.seed_inputs = seed_inputs_b0
    context, _traces = ri.run_sequence(orchestrator, plan)
    feb1 = ri.END
    targets = orchestrator.targets_of_blocks(fixture.OFFICIAL_BLOCKS)

    def final(variable_id):
        d = definitions.get(variable_id)
        period = ri.PERIODS.effective_window(d.frequency, feb1).period_id
        instances = ScopeResolver().resolve_scopes(d.scope_type, d.scope_value)
        return json.dumps({f"{st}/{sv}": ri.encode(context.get_variable_result(variable_id, st, sv, period,
                                                                                as_of=feb1))
                           for st, sv in sorted(instances)})

    b0 = {r["target"]: r for r in csv.DictReader(B0_TARGETS.open(encoding="utf-8"))}
    b0_by_identity = {}
    raw_b0 = json.loads(subprocess.check_output(["git", "show", f"{B0_COMMIT}:data/seed/max_ht/variables.json"],
                                                cwd=REPO))
    for v in raw_b0:
        b0_by_identity[(v["variable_name"].replace("alimentação", "alimentacao"), v["frequency"], v["scope_type"],
                        v["scope_value"])] = v["variable_id"]

    rows = []
    for t in targets:
        now = final(t)
        if t in b0:
            ref, kind = b0[t]["final_results_2026-02-01"], "COMUM"
        elif t == "VAR18031":
            d = definitions.get(t)
            ref = json.dumps({f"{st}/{sv}": ["float", repr(fixture.input_value(b0_index["VAR18031"], k, d.frequency,
                                                                                 feb1)), None, None]
                              for k, (st, sv) in enumerate(sorted(ScopeResolver().resolve_scopes(d.scope_type,
                                                                                                d.scope_value)))})
            kind = "ENTRADA_B0_AGORA_CALCULADA"
        elif identity(definitions.get(t)) in b0_by_identity and b0_by_identity[identity(definitions.get(t))] in b0:
            ref, kind = b0[b0_by_identity[identity(definitions.get(t))]]["final_results_2026-02-01"], "RENOMEADO"
        else:
            ref, kind = None, "NOVO_SEM_PAR"
        equal = ref is not None and json.loads(now) == json.loads(ref)
        rows.append({"target": t, "kind": kind, "equal_to_b0": equal})
        if ref is not None and not equal:
            problems.append(f"{kind} {t}: B0 {ref[:120]} x 5A {now[:120]}")

    summary = {
        "label": "Stage 5A.3 — atribuição das diferenças de valor do B1",
        "b0_commit": B0_COMMIT, "head_inputs": len(plan.required_inputs), "b0_inputs": len(b0_inputs),
        "renamed_inputs": RENAMED_INPUTS, "b0_inputs_without_head_counterpart": dropped,
        "targets": len(rows),
        "by_kind": {k: f"{sum(r['equal_to_b0'] for r in rows if r['kind'] == k)}/"
                       f"{sum(1 for r in rows if r['kind'] == k)} iguais" for k in sorted({r['kind'] for r in rows})},
        "not_compared": [r["target"] for r in rows if r["kind"] == "NOVO_SEM_PAR"],
        "problems": problems,
    }
    summary["result"] = "PASS" if not problems and not dropped else "FAIL"
    if "--write" in sys.argv[1:]:
        out = HERE / "evidence"
        out.mkdir(exist_ok=True)
        (out / "b1_value_attribution.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
                                                       encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
