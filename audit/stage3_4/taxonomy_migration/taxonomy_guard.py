"""
D-TAX-01 — guarda "taxonomy-only" para os artefatos protegidos da Stage 3.

Regra (exceção auditável, extremamente restrita):

    artefato protegido da Stage 3 (app/, data/, tools/)
    + migração taxonômica autorizada D-TAX-01
    = permitido SOMENTE quando o diff é provadamente taxonômico.

Um diff entre uma base e o alvo é aceito apenas se TODO arquivo alterado é
um dos seis abaixo e a alteração é exatamente a da decisão:

  * app/validation/{variable,parameter,equation}_seed_validator.py:
    AST idêntico ao da base depois de mapear o literal "thickener_flocculant"
    de volta para "monthly_ppt_assumptions" (comentários não entram no AST);
    o dicionário de faixas precisa ser exatamente CANONICAL (29 blocos, ordem
    e faixas);
  * tools/workbook_seed/taxonomy.py: AST idêntico ao da base exceto a
    docstring do módulo e o valor de BLOCK_TAXONOMY, que precisa ser
    exatamente os 29 nomes canônicos (e o da base, a lista D26-01 de 28);
  * tools/workbook_seed/interblock.py: AST idêntico ao da base depois de
    mapear "D-TAX-01" -> "D26-01" (rótulo da decisão no seed);
  * data/seed/interblock_links.json: JSON idêntico ao da base fora de
    `taxonomy`; `taxonomy` = {decision: "D-TAX-01", official_blocks: 29
    canônicos, loaded_blocks: iguais aos da base}.

A base pode ser pré-migração (D26-01) ou já migrada (D-TAX-01): o diff é aceito
se for exatamente o rename ou nenhuma mudança de AST (ex.: só comentários, D-TAX-02).

D-TAX-02 acrescenta dois guardas permanentes do estado atual (`check_current_registry`):
  * `check_projections`: o canônico D-TAX-01 == toda projeção física (três faixas,
    BLOCK_TAXONOMY, taxonomia do seed) em nomes, ordem, quantidade e faixas;
  * `check_crosswalk`: o crosswalk persistido dos blocos de custo == os três pares
    documentados, com faixas e status explícitos (nunca inferido por nome).

Qualquer outro arquivo alterado, criado ou removido em app/, data/ ou tools/
— fórmula, valor, faixa, vínculo, pendência, cardinalidade, código do engine
— é NON_TAXONOMIC_CHANGE. Não importa `app`: é um verificador de artefatos.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DECISION = "D-TAX-01"
OLD_NAME, NEW_NAME = "monthly_ppt_assumptions", "thickener_flocculant"

# Registro canônico (D-TAX-01): nome, faixa. Ordem normativa.
CANONICAL = (
    ("maintenance", 10000, 10999), ("yield", 11000, 11999), ("production", 12000, 12999),
    ("max_ht", 13000, 13999), ("alumina", 14000, 14999), ("temperature_lp", 15000, 15999),
    ("area_41", 16000, 16999), ("area_04_13", 17000, 17999), ("energy", 18000, 18999),
    ("boilers", 19000, 19999), ("volume", 20000, 20999), ("soda", 21000, 21999),
    ("residue_factor", 22000, 22999), ("condensate_flow", 23000, 23999), ("forecast_volume", 24000, 24999),
    ("full_volume_target", 25000, 25999), ("empty_space_target_control", 26000, 26999), ("lime", 27000, 27999),
    ("hydrated_flocculant", 28000, 28999), ("sludge_flocculant", 29000, 29999),
    ("thickener_flocculant", 30000, 30999), ("acid", 31000, 31999), ("budget_cost", 32000, 32999),
    ("budget_forecast_cost", 33000, 33999), ("actual_forecast_cost", 34000, 34999), ("budget", 35000, 35999),
    ("forecast", 36000, 36999), ("budget_vs_forecast", 37000, 37999), ("shared", 38000, 38999),
)
CANONICAL_NAMES = tuple(name for name, _lo, _hi in CANONICAL)
# Lista histórica D26-01 (Etapa 2.6B), substituída por D-TAX-01.
D26_01 = (
    "maintenance", "area_04_13", "forecast_volume", "acido", "yield", "energy", "meta_volume_cheio",
    "custo_budget", "production", "boilers", "controle_espaco_vazio_meta", "custo_forecast_bdgt", "max_ht",
    "volume", "lime_dia", "custo_forecast_real", "alumina", "soda", "floculante_hidrato_2026", "budget",
    "temperature_lp", "fator_residuo", "floculante_lama_dia", "forecast", "area_41", "vazao_condensado",
    "premissas_ppt_mensal", "shared",
)
VALIDATORS = {
    "app/validation/variable_seed_validator.py": "VARIABLE_ID_RANGES",
    "app/validation/parameter_seed_validator.py": "PARAMETER_ID_RANGES",
    "app/validation/equation_seed_validator.py": "EQUATION_ID_RANGES",
}
TAXONOMY_PY = "tools/workbook_seed/taxonomy.py"
INTERBLOCK_PY = "tools/workbook_seed/interblock.py"
LINKS_JSON = "data/seed/interblock_links.json"
AUTHORIZED = (*VALIDATORS, TAXONOMY_PY, INTERBLOCK_PY, LINKS_JSON)
PROTECTED = ("app", "data", "tools")


class _Rename(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value in self.mapping:
            return ast.copy_location(ast.Constant(self.mapping[node.value]), node)
        return node


def _assigned(tree: ast.Module, name: str):
    for node in tree.body:
        targets = [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return node
    return None


def _without_docstring(tree: ast.Module) -> ast.Module:
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return ast.Module(body=body, type_ignores=[])


def _check_validator(path: str, old: bytes, new: bytes) -> list[str]:
    old_tree, new_tree = ast.parse(old), ast.parse(new)
    problems = []
    # base pré-migração (nome antigo) ou já migrada (D-TAX-02 em diante): o AST tem de ser
    # idêntico, a menos exatamente do rename; comentários não entram no AST.
    if ast.dump(old_tree) not in (ast.dump(_Rename({NEW_NAME: OLD_NAME}).visit(ast.parse(new))), ast.dump(new_tree)):
        problems.append(f"NON_TAXONOMIC_CHANGE {path}: código difere além do rename {OLD_NAME} -> {NEW_NAME}")
    name = VALIDATORS[path]
    node = _assigned(new_tree, name)
    ranges = ast.literal_eval(node.value) if node is not None else None
    expected = {n: (lo, hi) for n, lo, hi in CANONICAL}
    if ranges != expected or list(ranges) != list(CANONICAL_NAMES):
        problems.append(f"NON_TAXONOMIC_CHANGE {path}: {name} != registro canônico de 29 blocos")
    old_node = _assigned(old_tree, name)
    old_ranges = ast.literal_eval(old_node.value) if old_node is not None else None
    if old_ranges is not None and [(k, v) for k, v in old_ranges.items()] not in (
            [(OLD_NAME if k == NEW_NAME else k, v) for k, v in expected.items()], list(expected.items())):
        problems.append(f"NON_TAXONOMIC_CHANGE {path}: faixas da base diferem do registro (além do nome)")
    return problems


def _check_taxonomy(old: bytes, new: bytes) -> list[str]:
    old_tree, new_tree = _without_docstring(ast.parse(old)), _without_docstring(ast.parse(new))
    problems = []
    old_node, new_node = _assigned(old_tree, "BLOCK_TAXONOMY"), _assigned(new_tree, "BLOCK_TAXONOMY")
    if old_node is None or new_node is None:
        return [f"NON_TAXONOMIC_CHANGE {TAXONOMY_PY}: BLOCK_TAXONOMY ausente"]
    old_value, new_value = ast.literal_eval(old_node.value), ast.literal_eval(new_node.value)
    if tuple(new_value) != CANONICAL_NAMES:
        problems.append(f"NON_TAXONOMIC_CHANGE {TAXONOMY_PY}: BLOCK_TAXONOMY != 29 nomes canônicos")
    if tuple(old_value) not in (D26_01, CANONICAL_NAMES):
        problems.append(f"NON_TAXONOMIC_CHANGE {TAXONOMY_PY}: base não é D26-01")
    old_node.value = new_node.value = ast.Constant(None)
    if ast.dump(old_tree) != ast.dump(new_tree):
        problems.append(f"NON_TAXONOMIC_CHANGE {TAXONOMY_PY}: código difere além da lista")
    return problems


def _check_interblock_py(old: bytes, new: bytes) -> list[str]:
    if new.count(DECISION.encode()) != 1:
        return [f"NON_TAXONOMIC_CHANGE {INTERBLOCK_PY}: rótulo {DECISION} ausente ou repetido"]
    if ast.dump(ast.parse(old)) not in (ast.dump(_Rename({DECISION: "D26-01"}).visit(ast.parse(new))),
                                        ast.dump(ast.parse(new))):
        return [f"NON_TAXONOMIC_CHANGE {INTERBLOCK_PY}: código difere além do rótulo da decisão"]
    return []


def _check_links(old: bytes, new: bytes) -> list[str]:
    old_json, new_json = json.loads(old), json.loads(new)
    problems = []
    if set(old_json) != set(new_json):
        problems.append(f"NON_TAXONOMIC_CHANGE {LINKS_JSON}: seções diferentes")
    for key in sorted(set(old_json) | set(new_json)):
        if key != "taxonomy" and old_json.get(key) != new_json.get(key):
            problems.append(f"NON_TAXONOMIC_CHANGE {LINKS_JSON}: seção '{key}' alterada")
    old_tax, new_tax = old_json.get("taxonomy", {}), new_json.get("taxonomy", {})
    expected = {"decision": DECISION, "official_blocks": list(CANONICAL_NAMES),
                "loaded_blocks": old_tax.get("loaded_blocks")}
    if new_tax != expected:
        problems.append(f"NON_TAXONOMIC_CHANGE {LINKS_JSON}: taxonomy != registro canônico D-TAX-01")
    if old_tax.get("official_blocks") not in (list(D26_01), list(CANONICAL_NAMES)):
        problems.append(f"NON_TAXONOMIC_CHANGE {LINKS_JSON}: taxonomia da base não é D26-01")
    return problems


def classify(changes: dict) -> dict:
    """
    changes: {caminho relativo: (bytes da base | None, bytes do alvo | None)} para os
    arquivos alterados. Devolve {"taxonomy_only": bool, "problems": [...], "files": [...]}.
    Nenhuma alteração = taxonomy_only False e sem problemas ("unchanged").
    """
    problems = []
    for path, (old, new) in sorted(changes.items()):
        if path not in AUTHORIZED:
            problems.append(f"NON_TAXONOMIC_CHANGE {path}: arquivo fora da migração autorizada")
        elif old is None or new is None:
            problems.append(f"NON_TAXONOMIC_CHANGE {path}: criado ou removido")
        else:
            try:
                if path in VALIDATORS:
                    problems += _check_validator(path, old, new)
                elif path == TAXONOMY_PY:
                    problems += _check_taxonomy(old, new)
                elif path == INTERBLOCK_PY:
                    problems += _check_interblock_py(old, new)
                else:
                    problems += _check_links(old, new)
            except (SyntaxError, ValueError) as exc:
                problems.append(f"NON_TAXONOMIC_CHANGE {path}: ilegível ({exc})")
    return {"decision": DECISION, "files": sorted(changes), "problems": problems,
            "taxonomy_only": bool(changes) and not problems, "unchanged": not changes}


def _git(*args, check=True) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=check).stdout


def changes_between(base: str, target: str | None = None, paths=PROTECTED) -> dict:
    """Arquivos alterados entre `base` e `target` (commit) ou a árvore de trabalho (None)."""
    rev = [base] if target is None else [base, target]
    names = _git("diff", "--name-only", *rev, "--", *paths).decode().split()
    if target is None:
        names += _git("ls-files", "--others", "--exclude-standard", "--", *paths).decode().split()
    changes = {}
    for name in sorted(set(names)):
        old = subprocess.run(["git", "show", f"{base}:{name}"], cwd=REPO, capture_output=True)
        if target is None:
            path = REPO / name
            new = path.read_bytes() if path.exists() else None
        else:
            shown = subprocess.run(["git", "show", f"{target}:{name}"], cwd=REPO, capture_output=True)
            new = shown.stdout if shown.returncode == 0 else None
        changes[name] = (old.stdout if old.returncode == 0 else None, new)
    return changes


def classify_git(base: str, target: str | None = None, paths=PROTECTED) -> dict:
    return classify(changes_between(base, target, paths))


def protected_status(base: str, target: str | None = None, paths=PROTECTED) -> str:
    """UNCHANGED | AUTHORIZED_TAXONOMY_MIGRATION | NON_TAXONOMIC_CHANGE."""
    result = classify_git(base, target, paths)
    if result["unchanged"]:
        return "UNCHANGED"
    return "AUTHORIZED_TAXONOMY_MIGRATION" if result["taxonomy_only"] else "NON_TAXONOMIC_CHANGE"


# ============================================================== D-TAX-02
# Crosswalk histórico normativo dos três blocos de custo (oráculo escrito da decisão).
# Fonte machine-readable: audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json.
D_TAX_02 = "D-TAX-02"
COST_CROSSWALK = {
    "custo_budget": ("budget_cost", 32000, 32999),
    "custo_forecast_bdgt": ("budget_forecast_cost", 33000, 33999),
    "custo_forecast_real": ("actual_forecast_cost", 34000, 34999),
}
CROSSWALK_JSON = "audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json"
EXPLICIT_STATUSES = ("CONFIRMED", "UNRESOLVED")


def physical_projections(repo: Path = REPO) -> dict:
    """
    As projeções físicas da taxonomia canônica, lidas dos artefatos (sem importar app/tools):
    {nome: [(bloco, lo, hi) | (bloco, None, None)]}. As faixas não existem na taxonomia nem no seed.
    """
    out = {}
    for path, name in VALIDATORS.items():
        node = _assigned(ast.parse((repo / path).read_bytes()), name)
        out[name] = [(k, lo, hi) for k, (lo, hi) in ast.literal_eval(node.value).items()]
    node = _assigned(ast.parse((repo / TAXONOMY_PY).read_bytes()), "BLOCK_TAXONOMY")
    out["BLOCK_TAXONOMY"] = [(k, None, None) for k in ast.literal_eval(node.value)]
    seed = json.loads((repo / LINKS_JSON).read_bytes())
    out["interblock_links.taxonomy"] = [(k, None, None) for k in seed["taxonomy"]["official_blocks"]]
    return out


def check_projections(projections: dict) -> list[str]:
    """D-TAX-01 canônico == toda projeção física (nomes, ordem, quantidade e, onde existem, faixas)."""
    problems = []
    for source, rows in sorted(projections.items()):
        names = tuple(row[0] for row in rows)
        if len(rows) != len(CANONICAL):
            problems.append(f"PROJECTION_DIVERGENCE {source}: {len(rows)} blocos != {len(CANONICAL)}")
        missing, extra = set(CANONICAL_NAMES) - set(names), set(names) - set(CANONICAL_NAMES)
        if missing or extra:
            problems.append(f"PROJECTION_DIVERGENCE {source}: faltam {sorted(missing)} sobram {sorted(extra)}")
        elif names != CANONICAL_NAMES:
            problems.append(f"PROJECTION_DIVERGENCE {source}: ordem diferente da canônica")
        if rows and rows[0][1] is not None:
            ranges = {name: (lo, hi) for name, lo, hi in rows}
            for name, lo, hi in CANONICAL:
                if name in ranges and ranges[name] != (lo, hi):
                    problems.append(f"PROJECTION_DIVERGENCE {source}: faixa de {name} {ranges[name]} != {(lo, hi)}")
    return problems


def check_crosswalk(payload: dict) -> list[str]:
    """D-TAX-02: o crosswalk persistido == os pareamentos documentados, todos explícitos."""
    problems = []
    if payload.get("decision") != D_TAX_02 or payload.get("status") != "APPLIED":
        problems.append("CROSSWALK_DIVERGENCE decisão/status != D-TAX-02 APPLIED")
    if payload.get("inference_by_name_allowed") is not False or payload.get("historical_names_are_operational") is not False:
        problems.append("CROSSWALK_DIVERGENCE inferência por nome ou nome histórico operacional permitido")
    mapping = payload.get("historical_to_canonical", {})
    if set(mapping) != set(COST_CROSSWALK):
        problems.append(f"CROSSWALK_DIVERGENCE pares {sorted(mapping)} != {sorted(COST_CROSSWALK)}")
    canonical_ranges = {name: (lo, hi) for name, lo, hi in CANONICAL}
    for historical, (canonical, lo, hi) in COST_CROSSWALK.items():
        entry = mapping.get(historical)
        if entry is None:
            continue
        if entry.get("canonical") != canonical:
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: {entry.get('canonical')} != {canonical}")
        for field in ("historical_range", "canonical_range"):
            if tuple(entry.get(field) or ()) != (lo, hi):
                problems.append(f"CROSSWALK_DIVERGENCE {historical}: {field} {entry.get(field)} != {[lo, hi]}")
        if canonical_ranges.get(canonical) != (lo, hi):
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: faixa canônica de {canonical} diverge de D-TAX-01")
        if entry.get("status") not in EXPLICIT_STATUSES:
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: status implícito/inválido {entry.get('status')!r}")
        if entry.get("inferred_only") is not False or entry.get("same_id_range") is not True:
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: inferred_only/same_id_range inválidos")
        if entry.get("status") == "CONFIRMED" and not entry.get("repository_evidence"):
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: CONFIRMED sem evidência")
        if historical in CANONICAL_NAMES:
            problems.append(f"CROSSWALK_DIVERGENCE {historical}: nome histórico é canônico")
    return problems


def check_current_registry(repo: Path = REPO) -> list[str]:
    """Os dois guardas permanentes: projeções físicas (D-TAX-01) e crosswalk (D-TAX-02)."""
    crosswalk = json.loads((repo / CROSSWALK_JSON).read_text(encoding="utf-8"))
    return check_projections(physical_projections(repo)) + check_crosswalk(crosswalk)
