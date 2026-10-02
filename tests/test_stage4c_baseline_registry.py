"""
Stage 4C — registro de baseline e re-baseline governado.

Provam:
    * o registro é íntegro (`rebaseline.py --check`): cadeia, selos, current APPROVED, sha256 de todo arquivo;
    * B0 aponta para a evidência histórica, sem cópia, e cada arquivo é IMUTÁVEL (classe E): sha256 igual
      ao registrado e `git diff <commit que gravou a evidência> -- arquivo` vazio;
    * as referências derivadas de B0 são IGUAIS aos literais históricos que os testes R usavam
      (a conversão R não perde poder de detecção em B0);
    * o verificador rejeita sha alterado, entrada APPROVED editada, current em PROPOSED e cadeia quebrada;
    * o re-baseline recusa árvore suja, motivo ausente e id repetido (num clone temporário);
    * `--baseline-dir` só troca a fonte (default = caminhos históricos; herdados nunca mudam).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BASELINES = REPO / "audit" / "baselines"
sys.path.insert(0, str(BASELINES))

import baseline_paths as bp  # noqa: E402
import baseline_registry as reg  # noqa: E402
import historical  # noqa: E402

REGISTRY = reg.load()
B0 = reg.entry(REGISTRY, "B0")


def git(*args, cwd=REPO) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


# ------------------------------------------------------------ integridade

def test_registry_check_passes_without_writing():
    before = git("status", "--porcelain", "--untracked-files=all").stdout
    done = subprocess.run([sys.executable, str(BASELINES / "rebaseline.py"), "--check"], cwd=REPO,
                          capture_output=True, text=True)
    out = json.loads(done.stdout)
    assert done.returncode == 0 and out["result"] == "PASS", out["problems"]
    assert git("status", "--porcelain", "--untracked-files=all").stdout == before


def test_b0_is_the_approved_root_pointing_to_historical_evidence_without_copies():
    assert REGISTRY["entries"][0] is B0 or REGISTRY["entries"][0]["id"] == "B0"
    assert B0["anterior"] is None and B0["status"] == "APPROVED" and B0["layout"] == "historico"
    assert B0["commit_comportamento"] == "f573c1b6cb9365b4669ec6af688f0ada36ad438d"
    assert B0["selo"] == reg.seal(B0)
    assert set(B0["conjuntos"]) == set(bp.HISTORICAL)
    for set_name, set_def in B0["conjuntos"].items():
        assert {k: v["caminho"] for k, v in set_def["arquivos"].items()} == bp.HISTORICAL[set_name]
        assert set_def["classe"] == reg.SET_CLASSES[set_name]
        assert not any(v["caminho"].startswith("audit/baselines/") for v in set_def["arquivos"].values())
    for stage in ("stage3_4b", "stage3_4c", "stage3_4d", "stage4a", "stage4b"):
        assert any(name.startswith(stage) for name in B0["conjuntos"]), stage
    assert not [p for p in BASELINES.iterdir() if p.is_dir() and p.name == "B0"]


def test_current_is_approved_and_resolves_the_harness_arguments():
    current = reg.current(REGISTRY)
    assert current["status"] == "APPROVED"
    root = reg.baseline_dir(REGISTRY)
    assert bp.baseline_dir() == root                                  # conftest configurou o processo
    assert reg.harness_args(REGISTRY) == ([] if root is None else ["--baseline-dir", str(root)])


@pytest.mark.parametrize("set_name", sorted(bp.HISTORICAL))
def test_b0_historical_evidence_is_immutable(set_name):
    """Classe E: sha256 registrado e nenhum byte mudou desde o commit que gravou a evidência."""
    set_def = B0["conjuntos"][set_name]
    commit = set_def["commit_evidencia_historica"]
    assert commit == bp.EVIDENCE_COMMITS[set_name]
    for logical, meta in set_def["arquivos"].items():
        assert reg.sha256_file(REPO / meta["caminho"]) == meta["sha256"], logical
        done = git("diff", "--quiet", commit, "--", meta["caminho"])
        assert done.returncode == 0, (logical, commit)
        assert git("ls-files", "--error-unmatch", meta["caminho"]).returncode == 0


# ------------------------------------------------------------ B0 == literais históricos

def test_b0_reference_values_equal_the_historical_literals_of_the_r_tests():
    e = {name: B0["conjuntos"][name]["expectativas"] for name in bp.R_SETS}
    c = e["stage3_4c_integrated"]
    assert {k: v for k, v in c["universe"].items() if k != "required_inputs"} == {
        "official_targets": 446, "area_41_excluded": 25, "integrated_targets": 421, "planner_nodes": 427,
        "nodes_by_kind": {"EQUATION": 218, "AGGREGATION": 197, "TRANSFER": 12}, "pending_blockers": 0}
    assert (c["targets_executed"], c["nodes_executed"], c["transfers"], c["dates"]) == (421, 427, 12, 32)
    assert c["per_date"] == [["421", "427", "60", "0"]]
    assert c["store_sha256_RUN_A"].startswith("619b4abd")
    a = e["stage4a_contract"]
    assert (a["integrated"]["integrated_targets"], a["integrated"]["official_targets"],
            a["integrated"]["planner_nodes"]) == (446, 446, 458)
    assert a["integrated"]["nodes_by_kind"] == {"EQUATION": 238, "AGGREGATION": 207, "TRANSFER": 13}
    assert len(a["integrated"]["transfers"]) == 13 and "TRANSFER:VAR16007" in a["integrated"]["transfers"]
    assert (a["integrated"]["previous_targets"], a["integrated"]["previous_nodes"]) == (421, 427)
    ind = a["independent"]
    assert (ind["universe_5.targets"], ind["universe_5.nodes"], ind["universe_5.required_inputs"],
            ind["universe_5.events_per_date"], ind["universe_4.nodes"]) == (446, 458, 62, 896, 427)
    assert ind["union.shared"] == ["EQUATION:EQ12012", "TRANSFER:VAR11031"]
    assert ind["official_plan.area_41"] == {"OK": 3, "INTERBLOCK_SOURCE_NOT_LOADED": 22}
    assert ind["official_plan.pending_links"] == 16
    i = e["stage4a_integrated"]
    assert (i["targets_executed"], i["nodes_executed"], i["transfers"]) == (446, 458, 13)
    assert i["previous_store_sha256"] == c["store_sha256_RUN_A"]
    b = e["stage4b_contract"]
    assert (b["temporal"]["targets"], b["temporal"]["planner_nodes"], b["temporal"]["events_per_date"],
            b["temporal"]["transfer_events_per_date"]) == (446, 458, 896, 67)
    assert (b["independent"]["identity_profile"]["derived_mensal"],
            b["independent"]["identity_profile"]["derived_anual"]) == (324, 196)
    t = e["stage4b_temporal"]
    assert [t[r]["dates"]["count"] for r in ("T1", "T2", "T3")] == [396, 62, 792]
    assert all(t[r]["per_date"] == {"targets": [446], "nodes": [458], "events": [896], "transfer_events": [67]}
               for r in ("T1", "T2", "T3"))
    p = e["stage3_2_plan"]
    assert p["official_targets"] == 446


# ------------------------------------------------------------ verificador (negativos em cópia)

def tampered(fn):
    registry = copy.deepcopy(REGISTRY)
    fn(registry)
    return reg.verify(registry)


def test_verifier_accepts_the_real_registry():
    assert reg.verify(copy.deepcopy(REGISTRY)) == []


def test_verifier_rejects_a_changed_b0_sha256():
    def fn(r):
        meta = r["entries"][0]["conjuntos"]["stage3_4c_integrated"]["arquivos"]["targets.csv"]
        meta["sha256"] = "0" * 64
    assert any("SHA256_DIVERGENTE" in p or "SELO_INVALIDO" in p for p in tampered(fn))


def test_verifier_rejects_an_edited_approved_entry():
    def fn(r):
        r["entries"][0]["motivo"] = r["entries"][0]["motivo"] + " (editado)"
    assert any("SELO_INVALIDO" in p for p in tampered(fn))


def test_verifier_rejects_current_pointing_to_a_proposed_entry():
    def fn(r):
        proposed = copy.deepcopy(r["entries"][-1])
        proposed.update({"id": "B99", "anterior": r["entries"][-1]["id"], "status": "PROPOSED",
                         "layout": "audit/baselines/B99"})
        proposed.pop("selo", None)
        r["entries"].append(proposed)
        r["current"] = "B99"
    assert any("CURRENT_NAO_APROVADO" in p for p in tampered(fn))


def test_verifier_rejects_a_broken_chain_and_missing_reason():
    def fn(r):
        extra = copy.deepcopy(r["entries"][-1])
        extra.update({"id": "B98", "anterior": "B77", "status": "PROPOSED", "motivo": " ",
                      "layout": "audit/baselines/B98"})
        r["entries"].append(extra)
    problems = tampered(fn)
    assert any("CADEIA" in p for p in problems) and any("MOTIVO_AUSENTE" in p for p in problems)


# ------------------------------------------------------------ re-baseline recusa (clone temporário)

@pytest.fixture(scope="module")
def clone(tmp_path_factory):
    return historical.checkout("HEAD", tmp_path_factory.mktemp("stage4c_rebaseline") / "tree")


def _next_free_id() -> str:
    # Stage 5A (F5A-07): o próximo ID livre vem do registro do HEAD (o clone é o HEAD). Antes era o literal "B1",
    # válido só enquanto B1 não existia; com B1 aprovado na 5A, o controle positivo e as recusas passariam a
    # testar "já existe"/"proposta pendente" em vez do que dizem testar. Nenhuma asserção muda.
    head = json.loads(git("show", "HEAD:audit/baselines/BASELINE_REGISTRY.json").stdout)
    return f"B{max(int(e['id'][1:].split('-')[0]) for e in head['entries']) + 1}"


NEXT = _next_free_id()


def rebaseline(root, *args):
    done = subprocess.run([sys.executable, "audit/baselines/rebaseline.py", *args], cwd=root,
                          capture_output=True, text=True, env=historical.clean_env())
    return done.returncode, json.loads(done.stdout)


def test_preflight_accepts_a_valid_request_on_a_clean_tree(clone):
    """Controle positivo: as recusas abaixo não são vacuamente verdes."""
    assert git("status", "--porcelain", "--untracked-files=all", cwd=clone).stdout == ""
    code, out = rebaseline(clone, "--preflight-only", "--id", NEXT, "--stage", "x", "--reason", "controle")
    assert code == 0 and out["result"] == "PREFLIGHT_OK"


@pytest.mark.parametrize("args, reason", [
    (["--id", NEXT, "--stage", "x"], "motivo"),
    (["--id", NEXT, "--stage", "x", "--reason", "   "], "motivo"),
    (["--id", "B0", "--stage", "x", "--reason", "repetido"], "já existe"),
    (["--id", "Bx", "--stage", "x", "--reason", "id ruim"], "id inválido"),
])
@pytest.mark.parametrize("mode", [[], ["--preflight-only"]])
def test_rebaseline_refuses_invalid_requests(clone, args, reason, mode):
    code, out = rebaseline(clone, *mode, *args)
    assert code == 2 and out["result"] == "REFUSED" and reason in out["reason"]
    assert not (clone / "audit" / "baselines" / NEXT).exists()


def test_rebaseline_refuses_a_dirty_tree(clone):
    marker = clone / "audit" / "stage4c" / "dirty.txt"
    marker.write_text("sujo\n", encoding="utf-8")
    try:
        code, out = rebaseline(clone, "--preflight-only", "--id", NEXT, "--stage", "x", "--reason", "árvore suja")
    finally:
        marker.unlink()
    assert code == 2 and "árvore suja" in out["reason"]
    assert git("diff", "--quiet", "HEAD", "--", "audit/baselines/BASELINE_REGISTRY.json", cwd=clone).returncode == 0


def test_approve_refuses_an_unknown_or_already_approved_entry(clone):
    code, out = rebaseline(clone, "--approve", "B0")
    assert code == 2 and "não PROPOSED" in out["reason"]
    code, out = rebaseline(clone, "--approve", "B42")
    assert code == 2 and "B42" in out["reason"]


# ------------------------------------------------------------ parâmetro de diretório

def test_baseline_dir_only_changes_the_source(tmp_path):
    saved = list(bp._configured)
    try:
        bp.configure(None)
        assert bp.path("stage3_4c_integrated", "targets.csv") == REPO / "audit/stage3_4/integrated/evidence/targets.csv"
        assert bp.argv() == [] and bp.is_default()
        bp.configure(tmp_path)
        assert bp.path("stage3_4c_integrated", "targets.csv") == tmp_path / "stage3_4c_integrated" / "targets.csv"
        assert bp.path("stage3_4b_differential", "differential_summary.json") == \
            REPO / "audit/stage3_4/differential/evidence/differential_summary.json"           # herdado
        assert bp.argv() == ["--baseline-dir", str(tmp_path)]
        with pytest.raises(KeyError):
            bp.path("stage3_4c_integrated", "inexistente.csv")
    finally:
        bp._configured[:] = saved
