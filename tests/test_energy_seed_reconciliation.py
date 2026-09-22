"""
Reconciliação permanente entre o workbook `energy` v2 e os seeds.

A suíte roda o reconciliador real (`tools/energy_reconciliation.py`)
contra os seeds versionados e exige zero divergências — e, em seguida,
PROVA que o reconciliador detecta cada categoria de divergência,
rodando-o contra cópias deliberadamente corrompidas dos seeds. Sem
essa segunda metade, um reconciliador que não olhasse nada passaria.

Dependência do `.xlsx`
----------------------
Estes testes não dependem do arquivo Excel nem de `openpyxl`. Eles
comparam os seeds com
`data/reference/energy/energy_v2_extract.json`, o snapshot canônico da
planilha, versionado junto com o código e carimbado com o SHA-256 do
arquivo lido.

A escolha é deliberada: o `.xlsx` é um insumo externo (um upload), não
um artefato do repositório. Uma suíte que dependesse dele seria
inexecutável em qualquer ambiente sem esse upload — ou, pior, passaria
a "pular" silenciosamente. O snapshot preserva a rastreabilidade sem a
dependência. A regeneração a partir do Excel continua disponível e
explícita:

    python -m tools.energy_seed_builder --xlsx <caminho do .xlsx>

que reescreve o snapshot e os quatro seeds; qualquer divergência
introduzida nesse caminho aparece no `git diff` e nesta suíte.
"""

import json
import shutil
from pathlib import Path

import pytest

from tools.energy_reconciliation import reconcile

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "seed" / "energy"
SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reference" / "energy" / "energy_v2_extract.json"
)

EXPECTED_SHA256 = (
    "347f256b59df2278b90db8c37513d95677bd453456349a42eba6a37a77f9da7c"
)


@pytest.fixture(scope="module")
def report():
    return reconcile()


def test_snapshot_identifies_the_workbook_it_came_from():
    with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
        snapshot = json.load(handle)

    assert snapshot["source_sha256"] == EXPECTED_SHA256
    assert snapshot["source_file"].endswith("energy_v2.xlsx")
    assert len(snapshot["entities"]) == 56


def test_counts(report):
    assert report["entities"] == (56, 56)
    assert report["variables"] == (52, 52)
    assert report["parameters"] == (4, 4)
    assert report["equations"] == (24, 24)
    assert report["aggregation_rules"] == (11, 11)


def test_no_divergences(report):
    assert report["missing"] == []
    assert report["extra"] == []
    assert report["mismatches"] == []


# ============================================================
# Capacidade de detecção
# ============================================================


@pytest.fixture
def corrupted(tmp_path):
    """
    Devolve uma função que aplica uma mutação a uma cópia dos seeds e
    roda o reconciliador contra ela.
    """

    def run(seed_name, mutate):
        seed_dir = tmp_path / "energy"
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
    result = corrupted(
        "variables",
        lambda data: data.pop(10),
    )

    assert result["missing"], _all_findings(result)


def test_detects_an_extra_entity(corrupted):
    def mutate(data):
        clone = dict(data[0])
        clone["variable_id"] = "VAR18999"
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
        f".{field}:" in finding
        for finding in result["mismatches"]
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
        f".{field}:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_missing_equation(corrupted):
    result = corrupted("equations", lambda data: data.pop(3))

    assert result["missing"], _all_findings(result)


def test_detects_a_changed_expression(corrupted):
    def mutate(data):
        data[0]["expression"] = "VAR18001 / 25"

    result = corrupted("equations", mutate)

    assert any(
        ".expression:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_rebound_reference(corrupted):
    """
    Trocar VAR18001 (producao) por VAR18008 (lth) em EQ18001 mantém a
    expressão sintaticamente válida; a decodificação de volta para
    nomes revela a troca.
    """

    def mutate(data):
        data[0]["expression"] = "VAR18008 / 24"

    result = corrupted("equations", mutate)

    assert any(
        ".expression:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_frequency_binding(corrupted):
    """
    EQ18020 (energia_media_frct, mensal) deve consumir os IDs MENSAIS.
    Trocá-los pelos diários mantém os NOMES idênticos — só a restrição
    de frequência pega o erro.
    """

    def mutate(data):
        for equation in data:
            if equation["equation_id"] == "EQ18020":
                equation["expression"] = "VAR18027 + VAR18040"

    result = corrupted("equations", mutate)

    assert any(
        "existindo alternativa de mesma frequência" in finding
        for finding in result["mismatches"]
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
        for rule in data:
            if rule["aggregation_type"] == "WEIGHTED_AVERAGE":
                rule["aggregation_type"] = "AVERAGE"
                rule.pop("weight_variable_id", None)
                break

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".aggregation_type:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_aggregation_source(corrupted):
    def mutate(data):
        data[1]["source_variable_id"] = "VAR18022"

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".source_variable_id:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_wrong_aggregation_target(corrupted):
    def mutate(data):
        data[1]["target_variable_id"] = "VAR18023"

    result = corrupted("aggregation_rules", mutate)

    assert _all_findings(result)


def test_detects_a_substituted_weight(corrupted):
    """
    O peso de toda média ponderada é producao_planta_t_h (VAR18003).
    Trocá-lo por outra grandeza diária é detectado.
    """

    def mutate(data):
        for rule in data:
            if rule.get("weight_variable_id"):
                rule["weight_variable_id"] = "VAR18020"
                break

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".weight_variable_id:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)


def test_detects_a_dropped_weight(corrupted):
    def mutate(data):
        for rule in data:
            if rule.get("weight_variable_id"):
                rule["weight_variable_id"] = None
                break

    result = corrupted("aggregation_rules", mutate)

    assert any(
        ".weight_variable_id:" in finding
        for finding in result["mismatches"]
    ), _all_findings(result)
