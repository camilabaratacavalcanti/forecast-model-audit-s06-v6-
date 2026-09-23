"""
Reconciliação permanente entre o workbook `max_ht` v5 e os seeds.

Mesma estrutura de `tests/test_energy_seed_reconciliation.py`: roda o
reconciliador real (`tools/max_ht_reconciliation.py`) contra os seeds
versionados e exige zero divergências, e então PROVA que o
reconciliador detecta cada categoria de divergência, rodando-o contra
cópias deliberadamente corrompidas dos seeds.

Não depende do `.xlsx` nem de `openpyxl`: compara os seeds com
`data/reference/max_ht/max_ht_v5_extract.json`, o snapshot canônico da
planilha (auditada e aprovada como APTO PARA IMPLEMENTAÇÃO),
versionado junto com o código e carimbado com o SHA-256 do arquivo
lido. A regeneração a partir do Excel continua disponível e explícita:

    python -m tools.max_ht_seed_builder --xlsx <caminho do .xlsx>
"""

import json
import shutil
from pathlib import Path

import pytest

from tools.max_ht_reconciliation import reconcile

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "seed" / "max_ht"
SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reference" / "max_ht" / "max_ht_v5_extract.json"
)

EXPECTED_SHA256 = (
    "64363c9409d12092b71f63707aee38e0fd7717463de8a89df9cfc242a804e1aa"
)


@pytest.fixture(scope="module")
def report():
    return reconcile()


def test_snapshot_identifies_the_workbook_it_came_from():
    with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
        snapshot = json.load(handle)

    assert snapshot["source_sha256"] == EXPECTED_SHA256
    assert snapshot["source_file"].endswith("MaxHT_v5.xlsx")
    assert len(snapshot["entities"]) == 152


def test_counts(report):
    assert report["entities"] == (152, 152)
    assert report["variables"] == (148, 148)
    assert report["parameters"] == (4, 4)
    assert report["equations"] == (29, 29)
    assert report["aggregation_rules"] == (110, 110)


def test_no_divergences(report):
    assert report["missing"] == []
    assert report["extra"] == []
    assert report["mismatches"] == []


# ============================================================
# Capacidade de detecção
# ============================================================


@pytest.fixture
def corrupted(tmp_path):
    def run(seed_name, mutate):
        seed_dir = tmp_path / "max_ht"
        shutil.copytree(SEED_DIR, seed_dir)

        path = seed_dir / f"{seed_name}.json"

        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)

        mutate(data)

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)

        return reconcile(
            seed_dir=seed_dir, snapshot_path=SNAPSHOT_PATH,
        )

    return run


def _all_findings(result):
    return result["missing"] + result["extra"] + result["mismatches"]


def test_detects_a_missing_entity(corrupted):
    result = corrupted("variables", lambda data: data.pop(10))

    assert result["missing"], _all_findings(result)


def test_detects_an_extra_entity(corrupted):
    def mutate(data):
        clone = dict(data[0])
        clone["variable_id"] = "VAR13999"
        data.append(clone)

    result = corrupted("variables", mutate)

    assert result["extra"], _all_findings(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "t"),
        ("frequency", "anual"),
        ("scope_type", "planta"),
        ("scope_value", "L4_L5"),
        ("variable_type", "saída"),
        ("variable_name", "outro_nome"),
        ("description", "descrição trocada"),
    ],
)
def test_detects_a_wrong_variable_field(corrupted, field, value):
    def mutate(data):
        data[0][field] = value

    result = corrupted("variables", mutate)

    assert any(
        f".{field}:" in finding for finding in result["mismatches"]
    ), _all_findings(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "t"),
        ("value", 999),
        ("version", 7),
        ("scope_type", "planta"),
    ],
)
def test_detects_a_wrong_parameter_field(corrupted, field, value):
    def mutate(data):
        data[0][field] = value

    result = corrupted("parameters", mutate)

    assert any(
        f".{field}:" in finding for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_missing_equation(corrupted):
    result = corrupted("equations", lambda data: data.pop(3))

    assert result["missing"], _all_findings(result)


def test_detects_a_changed_expression(corrupted):
    def mutate(data):
        data[0]["expression"] = "VAR13001 / 25"

    result = corrupted("equations", mutate)

    assert any(
        ".expression:" in finding for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_rebound_reference(corrupted):
    """
    EQ13001 (refinery, diário) soma `producao` (VAR13001) nas 7
    linhas. Trocar uma referência por outra variável (VAR13011,
    alimentação_evap) mantém a expressão sintaticamente válida; a
    decodificação de volta para nomes revela a troca.
    """

    def mutate(data):
        data[0]["expression"] = data[0]["expression"].replace(
            "VAR13001@L1", "VAR13011@L1", 1
        )

    result = corrupted("equations", mutate)

    assert any(
        ".expression:" in finding for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_equation_scope(corrupted):
    def mutate(data):
        data[0]["scope_type"] = "linha_grupo"
        data[0]["scope_value"] = "L4_L5"

    result = corrupted("equations", mutate)

    assert any(
        ".scope_type:" in finding or ".scope_value:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_missing_aggregation_rule(corrupted):
    result = corrupted(
        "aggregation_rules", lambda data: data.pop(0),
    )

    assert result["missing"], _all_findings(result)


def test_detects_a_wrong_aggregation_type(corrupted):
    def mutate(data):
        data[0]["aggregation_type"] = (
            "AVERAGE" if data[0]["aggregation_type"] == "SUM" else "SUM"
        )

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".aggregation_type:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_aggregation_source(corrupted):
    def mutate(data):
        data[0]["source_variable_id"] = "VAR13011"

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".source_variable_id:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_aggregation_target(corrupted):
    def mutate(data):
        data[0]["target_variable_id"] = "VAR13011"

    result = corrupted("aggregation_rules", mutate)

    assert _all_findings(result)


def test_detects_a_spurious_weight(corrupted):
    """
    O max_ht não usa Média Ponderada: nenhuma AggregationRule deve ter
    `weight_variable_id`.
    """

    def mutate(data):
        data[0]["weight_variable_id"] = "VAR13001"

    result = corrupted("aggregation_rules", mutate)

    assert any(
        "peso declarado" in finding for finding in result["mismatches"]
    ), _all_findings(result)
