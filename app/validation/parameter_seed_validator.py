import json
from pathlib import Path


# ============================================================
# REGRAS DO PARAMETER REGISTRY
# ============================================================

REQUIRED_PARAMETER_FIELDS = [
    "parameter_id",
    "parameter_name",
    "description",
    "unit",
    "value",
    "scope_type",
    "scope_value",
    "source_reference",
    "status",
]


PARAMETER_ID_RANGES = {
    "maintenance": (10000, 10999),
    "yield": (11000, 11999),
    "production": (12000, 12999),
    "hydrate": (13000, 13999),
    "alumina": (14000, 14999),
    "temperature_lp": (15000, 15999),
    "area_41": (16000, 16999),
    "area_04_13": (17000, 17999),
    "energy": (18000, 18999),
    "boilers": (19000, 19999),
    "volume": (20000, 20999),
    "soda": (21000, 21999),
    "costs": (22000, 22999),
    "shared": (23000, 23999),
}


ALLOWED_STATUSES = {
    "draft",
    "ativo",
    "inativo",
}


ALLOWED_UNITS = {
    "t",
    "kg",
    "g/l",
    "m³",
    "m³/h",
    "m²/h",
    "m²/kg",
    "t/h",
    "%",
    "°C",
    "kWh",
    "MWh",
    "GWh",
    "MW",
    "MWm",
    "R$",
    "$",
    "-",
    # Bloco Production (auditoria descritivo_das_variáveis_production_v1.xlsx):
    "h",
    "tpd",
    "Mtpy",
    "dias",
    "kg/t",
    # Bloco Energy (auditoria descritivo_das_variaveis_energy_v2.xlsx):
    "GJ/t",
}


# Aliases de unidade que representam a MESMA grandeza física que uma
# unidade já canônica em ALLOWED_UNITS, apenas com grafia diferente
# na fonte (workbook). Normalizados para a forma canônica no
# carregamento do seed (`load_parameters_from_seed`), antes de
# qualquer validação -- não é uma conversão numérica (nenhum fator
# multiplicativo), apenas troca de rótulo textual.
UNIT_ALIASES = {
    "tph": "t/h",
}


def normalize_unit(unit):
    """Normaliza um alias de unidade para sua forma canônica."""
    return UNIT_ALIASES.get(unit, unit)


ALLOWED_SCOPE_TYPES = {
    "linha",
    "linha_grupo",
    "área",
    "planta",
    "global",
}


# scope_types cujo scope_value concreto é sempre None: não
# materializam por linha/grupo/planta, e essa ausência de valor não
# é um erro (ver contrato de scope da plataforma).
SCOPELESS_SCOPE_TYPES = {"área", "global"}


ALLOWED_SCOPE_VALUES = {
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "L7",
    "L1_L3",
    "L4_L5",
    "L6_L7",
    "L1_L7",
    "PLANTA",
}


NON_EMPTY_PARAMETER_STRING_FIELDS = {
    "parameter_id",
    "parameter_name",
    "description",
    "unit",
    "source_reference",
}


OPTIONAL_PARAMETER_STRING_FIELDS = {
    "scope_type",
    "scope_value",
}


ENUM_FIELDS = {
    "status": ALLOWED_STATUSES,
    "unit": ALLOWED_UNITS,
    "scope_type": ALLOWED_SCOPE_TYPES,
    "scope_value": ALLOWED_SCOPE_VALUES,
}


# ============================================================
# LEITURA DO JSON
# ============================================================

def load_json(file_path: Path):
    """
    Carrega um arquivo JSON e retorna seu conteúdo.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON inválido em {file_path}: {exc}"
        ) from exc

    except OSError as exc:
        raise ValueError(
            f"Não foi possível ler o arquivo {file_path}: {exc}"
        ) from exc


# ============================================================
# VALIDAÇÃO DA ESTRUTURA DO JSON
# ============================================================

def validate_json_structure(data, file_path: Path):
    """
    Valida a estrutura básica do seed JSON.

    O arquivo deve conter uma lista de objetos (dicionários).
    """

    errors = []

    if not isinstance(data, list):
        errors.append(
            f"{file_path}: o conteúdo do JSON deve ser uma lista."
        )
        return errors

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(
                f"{file_path}: item {index} deve ser um objeto JSON."
            )

    return errors


# ============================================================
# VALIDAÇÃO DO CAMINHO DO SEED
# ============================================================

def validate_seed_path(file_path: Path):
    """
    Valida se o arquivo está localizado dentro de um bloco
    conhecido do Parameter Registry.
    """

    errors = []

    parts = file_path.parts

    valid_blocks = set(PARAMETER_ID_RANGES.keys())

    block = None

    for part in parts:
        if part in valid_blocks:
            block = part
            break

    if block is None:
        errors.append(
            f"{file_path}: não foi possível identificar o bloco "
            f"do Parameter Registry."
        )

    return errors


# ============================================================
# LOCALIZAÇÃO DOS ARQUIVOS DE PARAMETERS
# ============================================================

def find_parameter_files(seed_root: Path):
    """
    Localiza todos os arquivos parameters.json dentro da estrutura
    de seed.
    """

    return sorted(seed_root.rglob("parameters.json"))


# ============================================================
# CARREGAMENTO DOS PARAMETERS
# ============================================================

def load_parameters_from_seed(seed_root: Path):
    """
    Carrega todos os Parameters existentes nos arquivos de seed.

    Retorna uma lista de tuplas:
        (parameter, file_path)

    A unidade de cada parâmetro é normalizada (`normalize_unit`)
    neste ponto, antes de qualquer validação ou construção de domain
    object -- ex.: "tph" (grafia do workbook) vira "t/h" (forma
    canônica), sem nenhuma conversão numérica.
    """

    parameters = []
    errors = []

    parameter_files = find_parameter_files(seed_root)

    for file_path in parameter_files:
        try:
            data = load_json(file_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        structure_errors = validate_json_structure(
            data,
            file_path,
        )

        errors.extend(structure_errors)

        if structure_errors:
            continue

        for parameter in data:
            parameter = parameter.copy()
            if "unit" in parameter:
                parameter["unit"] = normalize_unit(parameter["unit"])
            parameters.append((parameter, file_path))

    return parameters, errors


# ============================================================
# CAMPOS OBRIGATÓRIOS
# ============================================================

def validate_required_fields(parameter, file_path):
    """
    Verifica se todos os campos obrigatórios existem.
    """

    errors = []

    for field in REQUIRED_PARAMETER_FIELDS:
        if field not in parameter:
            errors.append(
                f"{file_path}: campo obrigatório ausente: "
                f"{field}."
            )

    return errors


# ============================================================
# TIPOS DOS CAMPOS
# ============================================================

def validate_field_types(parameter, file_path):
    """
    Valida os tipos dos campos do Parameter Registry.
    """

    errors = []

    string_fields = {
        "parameter_id",
        "parameter_name",
        "description",
        "unit",
        "source_reference",
        "status",
    }

    for field in string_fields:
        if field not in parameter:
            continue

        if not isinstance(parameter[field], str):
            errors.append(
                f"{file_path}: campo '{field}' deve ser string."
            )

    for field in OPTIONAL_PARAMETER_STRING_FIELDS:
        if field not in parameter:
            continue

        value = parameter[field]

        if value is not None and not isinstance(value, str):
            errors.append(
                f"{file_path}: campo '{field}' deve ser string "
                f"ou null."
            )

    if "value" in parameter:
        value = parameter["value"]

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            errors.append(
                f"{file_path}: campo 'value' deve ser numérico "
                f"(int ou float), não boolean."
            )

    return errors


# ============================================================
# VALORES NÃO VAZIOS
# ============================================================

def validate_non_empty_values(parameter, file_path):
    """
    Verifica se os campos textuais obrigatórios não estão vazios.
    """

    errors = []

    for field in NON_EMPTY_PARAMETER_STRING_FIELDS:
        if field not in parameter:
            continue

        value = parameter[field]

        if isinstance(value, str) and not value.strip():
            errors.append(
                f"{file_path}: campo '{field}' não pode ser vazio."
            )

    return errors


# ============================================================
# VALORES ENUMERADOS
# ============================================================

def validate_enum_values(parameter, file_path):
    """
    Valida os campos que possuem conjuntos de valores permitidos.
    """

    errors = []

    for field, allowed_values in ENUM_FIELDS.items():
        if field not in parameter:
            continue

        value = parameter[field]

        if value is None and field in OPTIONAL_PARAMETER_STRING_FIELDS:
            continue

        if value not in allowed_values:
            errors.append(
                f"{file_path}: valor inválido para '{field}': "
                f"'{value}'. Valores permitidos: "
                f"{sorted(allowed_values)}."
            )

    return errors


# ============================================================
# CONSISTÊNCIA ENTRE SCOPE_TYPE E SCOPE_VALUE
# ============================================================

def validate_scope_consistency(parameter, file_path):
    """
    Garante que scope_type e scope_value sejam informados de forma
    consistente.

    Ambos podem ser null, mas não é permitido que apenas um deles
    seja null — exceto quando scope_type é "área" ou "global": esses
    escopos são singulares (sem materialização por linha/grupo/
    planta) e seu scope_value concreto é sempre None por definição,
    o que não constitui inconsistência.
    """

    errors = []

    scope_type = parameter.get("scope_type")
    scope_value = parameter.get("scope_value")

    if scope_type in SCOPELESS_SCOPE_TYPES and scope_value is None:
        return errors

    if (scope_type is None) != (scope_value is None):
        errors.append(
            f"{file_path}: 'scope_type' e 'scope_value' devem "
            f"ser ambos informados ou ambos null."
        )

    return errors


# ============================================================
# VALORES DE SCOPE
# ============================================================

def validate_scope_values(parameter, file_path):
    """
    Valida a combinação entre scope_type e scope_value.

    A validação garante que:
        linha       -> L1 ... L7
        linha_grupo -> L1_L3, L4_L5 ou L6_L7
        área/global -> sem valor específico de linha
        planta      -> scope_value deve ser exatamente "PLANTA"
                       (ver ScopeResolver.PLANT_SCOPE)
    """

    errors = []

    scope_type = parameter.get("scope_type")
    scope_value = parameter.get("scope_value")

    if scope_type is None and scope_value is None:
        return errors

    if scope_type == "linha":
        valid_values = {
            "L1",
            "L2",
            "L3",
            "L4",
            "L5",
            "L6",
            "L7",
            "L1_L7",
        }

        if scope_value not in valid_values:
            errors.append(
                f"{file_path}: scope_value '{scope_value}' "
                f"inválido para scope_type 'linha'."
            )

    elif scope_type == "linha_grupo":
        valid_values = {
            "L1_L3",
            "L4_L5",
            "L6_L7",
            "L1_L7",
        }

        if scope_value not in valid_values:
            errors.append(
                f"{file_path}: scope_value '{scope_value}' "
                f"inválido para scope_type 'linha_grupo'."
            )

    elif scope_type in {
        "área",
        "global",
    }:
        if scope_value is not None:
            errors.append(
                f"{file_path}: scope_type '{scope_type}' "
                f"não deve possuir scope_value específico "
                f"de linha."
            )

    elif scope_type == "planta":
        if scope_value != "PLANTA":
            errors.append(
                f"{file_path}: scope_type 'planta' exige "
                f"scope_value 'PLANTA'."
            )

    return errors


# ============================================================
# FAIXAS DE PARAMETER_ID
# ============================================================

def validate_parameter_id_ranges(parameter, file_path):
    """
    Verifica se o Parameter_ID pertence à faixa reservada para
    o bloco em que o seed está localizado.
    """

    errors = []

    parameter_id = parameter.get("parameter_id")

    if not isinstance(parameter_id, str):
        return errors

    if not parameter_id.startswith("PARAM"):
        errors.append(
            f"{file_path}: Parameter_ID inválido: "
            f"'{parameter_id}'. Deve iniciar com 'PARAM'."
        )
        return errors

    numeric_part = parameter_id[5:]

    if not numeric_part.isdigit():
        errors.append(
            f"{file_path}: Parameter_ID inválido: "
            f"'{parameter_id}'. A parte numérica deve conter "
            f"apenas dígitos."
        )
        return errors

    numeric_id = int(numeric_part)

    block = None

    for part in file_path.parts:
        if part in PARAMETER_ID_RANGES:
            block = part
            break

    if block is None:
        return errors

    min_id, max_id = PARAMETER_ID_RANGES[block]

    if not (min_id <= numeric_id <= max_id):
        errors.append(
            f"{file_path}: Parameter_ID '{parameter_id}' "
            f"fora da faixa reservada para o bloco '{block}'. "
            f"Faixa permitida: PARAM{min_id}–PARAM{max_id}."
        )

    return errors


# ============================================================
# ASSINATURA SEMÂNTICA DO PARAMETER
# ============================================================

def build_parameter_signature(parameter):
    """
    Constrói a assinatura semântica de um Parameter.

    O valor atual não participa da assinatura, pois dois registros
    com o mesmo conceito e valores atuais diferentes representam
    o mesmo parâmetro conceitual.
    """

    return (
        parameter["parameter_name"],
        parameter["unit"],
        parameter["scope_type"],
        parameter["scope_value"],
    )


# ============================================================
# VALIDAÇÃO DE PARAMETER_IDs
# ============================================================

def validate_parameter_ids(parameters):
    """
    Verifica duplicidade de Parameter_ID.

    Um mesmo Parameter_ID pode representar legitimamente uma única
    definição lógica materializada por linha (ex.: "tanque_base"),
    com uma ParameterDefinition por linha, cada uma com seu próprio
    scope_value e value — o mesmo modelo já suportado pela chave
    composta do ParameterDefinitionRegistry (id, version, scope_type,
    scope_value). Por isso, a duplicidade é avaliada nessa mesma
    chave composta, e não apenas no Parameter_ID isolado: dois
    registros com o mesmo ID só são duplicados quando também
    coincidem em version, scope_type e scope_value.

    parameters:
        lista de tuplas (parameter, file_path)
    """

    errors = []
    seen = {}

    for parameter, file_path in parameters:
        parameter_id = parameter.get("parameter_id")

        if parameter_id is None:
            continue

        key = (
            parameter_id,
            parameter.get("version"),
            parameter.get("scope_type"),
            parameter.get("scope_value"),
        )

        if key in seen:
            previous_file = seen[key]

            errors.append(
                f"Parameter_ID duplicado: '{parameter_id}'. "
                f"Encontrado em {previous_file} e {file_path}."
            )

        else:
            seen[key] = file_path

    return errors


# ============================================================
# VALIDAÇÃO DE ASSINATURAS
# ============================================================

def validate_parameter_signatures(parameters):
    """
    Identifica Parameters semanticamente duplicados.

    A duplicidade semântica gera warning, e não error, pois pode
    representar uma duplicação conceitual que deverá ser avaliada
    posteriormente.
    """

    warnings = []
    signatures = {}

    for parameter, file_path in parameters:
        required_fields = {
            "parameter_name",
            "unit",
            "scope_type",
            "scope_value",
        }

        if not required_fields.issubset(parameter):
            continue

        signature = build_parameter_signature(parameter)

        if signature in signatures:
            previous_parameter, previous_file = signatures[signature]

            warnings.append(
                "Possível Parameter semanticamente duplicado: "
                f"'{parameter.get('parameter_name')}'. "
                f"Registros encontrados em "
                f"{previous_file} e {file_path}. "
                f"Parameter_IDs: "
                f"{previous_parameter.get('parameter_id')} e "
                f"{parameter.get('parameter_id')}."
            )

        else:
            signatures[signature] = (
                parameter,
                file_path,
            )

    return warnings


# ============================================================
# VALIDAÇÃO COMPLETA
# ============================================================

def validate_seed(seed_root: Path):
    """
    Executa todas as validações do Parameter Registry.

    Retorna:
        errors, warnings
    """

    errors = []
    warnings = []

    seed_root = Path(seed_root)

    if not seed_root.exists():
        errors.append(
            f"Diretório de seed não encontrado: {seed_root}."
        )
        return errors, warnings

    if not seed_root.is_dir():
        errors.append(
            f"O caminho informado não é um diretório: {seed_root}."
        )
        return errors, warnings

    parameter_files = find_parameter_files(seed_root)

    if not parameter_files:
        warnings.append(
            f"Nenhum arquivo 'parameters.json' encontrado "
            f"em {seed_root}."
        )
        return errors, warnings

    # --------------------------------------------------------
    # Validação individual dos arquivos
    # --------------------------------------------------------

    parameters, load_errors = load_parameters_from_seed(
        seed_root
    )

    errors.extend(load_errors)

    for parameter, file_path in parameters:

        errors.extend(
            validate_seed_path(file_path)
        )

        errors.extend(
            validate_required_fields(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_field_types(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_non_empty_values(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_enum_values(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_scope_consistency(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_scope_values(
                parameter,
                file_path,
            )
        )

        errors.extend(
            validate_parameter_id_ranges(
                parameter,
                file_path,
            )
        )

    # --------------------------------------------------------
    # Validações entre registros
    # --------------------------------------------------------

    errors.extend(
        validate_parameter_ids(parameters)
    )

    warnings.extend(
        validate_parameter_signatures(parameters)
    )

    return errors, warnings
