import json
from pathlib import Path


# ============================================================
# REGRAS DO VARIABLE REGISTRY
# ============================================================

REQUIRED_VARIABLE_FIELDS = [
    "variable_id",
    "variable_name",
    "description",
    "unit",
    "variable_type",
    "frequency",
    "scope_type",
    "scope_value",
    "source_reference",
    "status",
]


VARIABLE_ID_RANGES = {
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


# Valores permitidos para campos enumerados.
#
# Estes conjuntos representam regras estruturais do Registry.
# Caso os valores oficiais do projeto sejam ampliados,
# basta atualizar estas constantes.
ALLOWED_VARIABLE_TYPES = {
    "entrada",
    "entrada_externa",
    "calculado",
    "saída",
}


ALLOWED_FREQUENCIES = {
    "anual",
    "mensal",
    "diário",
}


ALLOWED_SCOPE_TYPES = {
    "linha",
    "linha_grupo",
    # "área",
    "planta",
    "global",
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
}


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
}


# Campos que obrigatoriamente devem conter uma string
# não vazia.
NON_EMPTY_STRING_FIELDS = {
    "variable_id",
    "variable_name",
    "description",
    "unit",
    "source_reference",
}


# Campos que devem ser strings quando preenchidos.
OPTIONAL_STRING_FIELDS = {
    "scope_type",
    "scope_value",
}

# Campos que possuem valores controlados por enum.
ENUM_FIELDS = {
    "variable_type": ALLOWED_VARIABLE_TYPES,
    "frequency": ALLOWED_FREQUENCIES,
    "status": ALLOWED_STATUSES,
    "unit": ALLOWED_UNITS,
    "scope_type": ALLOWED_SCOPE_TYPES,
    "scope_value": ALLOWED_SCOPE_VALUES,
}


# ============================================================
# LEITURA DOS ARQUIVOS
# ============================================================


def load_json(file_path: Path):
    """Carrega um arquivo JSON e retorna seu conteúdo."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON file: {file_path}"
        ) from error


def validate_json_structure(
    data,
    file_path: Path,
) -> list[str]:
    """
    Valida a estrutura básica do conteúdo do variables.json.

    O arquivo deve conter uma lista de objetos/dicionários,
    sendo cada objeto uma variável.
    """
    errors = []

    if not isinstance(data, list):
        errors.append(
            f"Invalid JSON structure in {file_path}: "
            "variables.json must contain a list"
        )
        return errors

    for index, variable in enumerate(data):
        if not isinstance(variable, dict):
            errors.append(
                f"Invalid variable structure in {file_path} "
                f"at index {index}: each variable must be an object"
            )

    return errors


def validate_seed_path(seed_path: Path) -> list[str]:
    """Valida se o caminho do seed existe e é um diretório."""
    errors = []

    if not seed_path.exists():
        errors.append(
            f"Seed directory does not exist: {seed_path}"
        )
        return errors

    if not seed_path.is_dir():
        errors.append(
            f"Seed path is not a directory: {seed_path}"
        )

    return errors


def find_variable_files(seed_path: Path) -> list[Path]:
    """Localiza todos os variables.json dos blocos."""
    variable_files = []

    for block_path in sorted(seed_path.iterdir()):
        if not block_path.is_dir():
            continue

        variables_file = block_path / "variables.json"

        if variables_file.exists():
            variable_files.append(variables_file)

    return variable_files


def load_variables_from_seed(seed_path: Path) -> list[dict]:
    """
    Carrega todas as variáveis existentes nos blocos do seed.

    O nome do bloco é acrescentado internamente em '_block'.
    """
    variables = []

    variable_files = find_variable_files(seed_path)

    for variables_file in variable_files:
        block_name = variables_file.parent.name
        block_variables = load_json(variables_file)

        for variable in block_variables:
            variable_with_block = variable.copy()
            variable_with_block["_block"] = block_name
            variables.append(variable_with_block)

    return variables


# ============================================================
# VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS
# ============================================================


def validate_required_fields(
    variables: list[dict],
) -> list[str]:
    """Verifica a existência de todos os campos obrigatórios."""
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        for field in REQUIRED_VARIABLE_FIELDS:
            if field not in variable:
                errors.append(
                    f"Missing required field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}"
                )

    return errors


# ============================================================
# VALIDAÇÃO DE TIPOS
# ============================================================


def validate_field_types(
    variables: list[dict],
) -> list[str]:
    """
    Valida os tipos básicos dos campos do Variable Registry.

    Regras:
    - campos textuais devem ser str;
    - campos opcionais podem ser None;
    - campos de enum devem ser str quando preenchidos.
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        # Campos obrigatoriamente textuais
        for field in NON_EMPTY_STRING_FIELDS:
            if field not in variable:
                continue

            value = variable[field]

            if not isinstance(value, str):
                errors.append(
                    f"Invalid type for field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}: "
                    "expected string"
                )

        # Campos que podem ser string ou None
        for field in OPTIONAL_STRING_FIELDS:
            if field not in variable:
                continue

            value = variable[field]

            if value is not None and not isinstance(value, str):
                errors.append(
                    f"Invalid type for field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}: "
                    "expected string or null"
                )

    return errors


# ============================================================
# VALIDAÇÃO DE VALORES VAZIOS
# ============================================================


def validate_non_empty_values(
    variables: list[dict],
) -> list[str]:
    """
    Verifica se campos obrigatórios de texto não estão vazios.

    Strings vazias ou contendo apenas espaços são consideradas
    inválidas.
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        for field in NON_EMPTY_STRING_FIELDS:
            if field not in variable:
                continue

            value = variable[field]

            # O tipo será tratado por validate_field_types().
            # Portanto, só aplicamos strip() quando o valor é str.
            if isinstance(value, str) and not value.strip():
                errors.append(
                    f"Empty value for field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}"
                )

    return errors


# ============================================================
# VALIDAÇÃO DE ENUMS
# ============================================================


def validate_enum_values(
    variables: list[dict],
) -> list[str]:
    """
    Valida os valores dos campos enumerados.

    Um campo enum:
    - deve conter um valor permitido;
    - não pode conter valor desconhecido;
    - scope_type e scope_value podem ser None,
    desde que ambos sejam None;
    - unit deve conter uma unidade previamente cadastrada;
    - scope_value deve conter um valor de escopo previamente cadastrado.
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        for field, allowed_values in ENUM_FIELDS.items():
            if field not in variable:
                continue

            value = variable[field]

            # scope_type e scope_value podem ser None.
            # A relação entre os dois campos é validada
            # separadamente por validate_scope_consistency().
            if field in {"scope_type", "scope_value"} and value is None:
                continue

            # Nenhum campo enum pode receber um tipo diferente
            # de string, exceto os casos None tratados acima.
            if not isinstance(value, str):
                errors.append(
                    f"Invalid type for field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}: "
                    f"value must be a string or null"
                )
                continue

            # Verifica se o valor pertence ao conjunto permitido.
            if value not in allowed_values:
                allowed = ", ".join(
                    sorted(allowed_values)
                )

                errors.append(
                    f"Invalid value '{value}' for field "
                    f"'{field}' in {block}/variables.json "
                    f"for variable {variable_id}: "
                    f"allowed values: {allowed}"
                )

    return errors


# ============================================================
# VALIDAÇÃO DE SCOPE
# ============================================================


def validate_scope_consistency(
    variables: list[dict],
) -> list[str]:
    """
    Valida a consistência entre scope_type e scope_value.

    Regra:
    - ambos None; ou
    - ambos preenchidos.
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        scope_type = variable.get("scope_type")
        scope_value = variable.get("scope_value")

        if (scope_type is None) != (scope_value is None):
            errors.append(
                f"Invalid scope for variable {variable_id} "
                f"in {block}/variables.json: "
                "scope_type and scope_value must both be "
                "null or both be filled"
            )

    return errors


def validate_scope_values(
    variables: list[dict],
) -> list[str]:
    """
    Verifica se scope_type e scope_value, quando preenchidos,
    não são strings vazias.
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        for field in ("scope_type", "scope_value"):
            value = variable.get(field)

            if isinstance(value, str) and not value.strip():
                errors.append(
                    f"Empty value for field '{field}' "
                    f"in {block}/variables.json "
                    f"for variable {variable_id}"
                )

    return errors


# ============================================================
# VALIDAÇÃO DE VARIABLE ID
# ============================================================


def validate_variable_id_ranges(
    variables: list[dict],
) -> list[str]:
    """Valida formato e faixa do variable_id."""
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id")

        if variable_id is None:
            continue

        if block not in VARIABLE_ID_RANGES:
            errors.append(
                f"Unknown block '{block}' for variable "
                f"{variable_id}: no variable_id range is defined"
            )
            continue

        if not isinstance(variable_id, str):
            errors.append(
                f"Invalid variable_id '{variable_id}' "
                f"in {block}/variables.json: "
                "variable_id must have format VAR followed by digits"
            )
            continue

        if not variable_id.startswith("VAR"):
            errors.append(
                f"Invalid variable_id '{variable_id}' "
                f"in {block}/variables.json: "
                "variable_id must have format VAR followed by digits"
            )
            continue

        numeric_part = variable_id[3:]

        if not numeric_part.isdigit():
            errors.append(
                f"Invalid variable_id '{variable_id}' "
                f"in {block}/variables.json: "
                "variable_id must have format VAR followed by digits"
            )
            continue

        variable_number = int(numeric_part)

        minimum, maximum = VARIABLE_ID_RANGES[block]

        if not minimum <= variable_number <= maximum:
            errors.append(
                f"Variable_id out of range: "
                f"{variable_id} in {block}/variables.json | "
                f"allowed range: VAR{minimum}–VAR{maximum}"
            )

    return errors


def build_variable_signature(
    variable: dict,
) -> tuple:
    """Constrói assinatura usada para detectar possíveis duplicidades."""
    return (
        variable["variable_name"],
        variable["unit"],
        variable["variable_type"],
        variable["frequency"],
        variable["scope_type"],
        variable["scope_value"],
    )


def validate_variable_ids(
    variables: list[dict],
) -> list[str]:
    """Detecta variable_ids duplicados."""
    errors = []
    seen_ids = {}

    for variable in variables:
        if "variable_id" not in variable:
            continue

        variable_id = variable["variable_id"]

        if variable_id in seen_ids:
            previous_variable = seen_ids[variable_id]

            errors.append(
                "Duplicate variable_id: "
                f"{variable_id} | "
                f"first occurrence: "
                f"{previous_variable.get('_block', 'unknown')}/"
                "variables.json | "
                f"duplicate occurrence: "
                f"{variable.get('_block', 'unknown')}/"
                "variables.json"
            )
        else:
            seen_ids[variable_id] = variable

    return errors


def validate_variable_signatures(
    variables: list[dict],
) -> list[str]:
    """Detecta possíveis variáveis duplicadas semanticamente."""
    warnings = []

    signatures = {}

    required_fields = [
        "variable_name",
        "unit",
        "variable_type",
        "frequency",
        "scope_type",
        "scope_value",
        "source_reference",
    ]

    for variable in variables:
        if not all(
            field in variable
            for field in required_fields
        ):
            continue

        signature = build_variable_signature(variable)

        if signature in signatures:
            previous_variable = signatures[signature]

            warnings.append(
                "Possible duplicate variable: "
                f"{previous_variable.get('variable_id', 'unknown')} "
                f"({previous_variable.get('_block', 'unknown')}/"
                "variables.json) and "
                f"{variable.get('variable_id', 'unknown')} "
                f"({variable.get('_block', 'unknown')}/"
                "variables.json) | "
                "source_reference: "
                f"{previous_variable.get('source_reference')} | "
                f"{variable.get('source_reference')}"
            )
        else:
            signatures[signature] = variable

    return warnings


# ============================================================
# VALIDAÇÃO PRINCIPAL
# ============================================================


def validate_seed(seed_path: Path) -> dict:
    """
    Executa todas as validações estruturais do Variable Registry.
    """

    path_errors = validate_seed_path(seed_path)

    if path_errors:
        return {
            "errors": path_errors,
            "warnings": [],
            "is_valid": False,
        }

    variables = []

    errors = []

    variable_files = find_variable_files(seed_path)

    for variables_file in variable_files:
        block_name = variables_file.parent.name

        try:
            data = load_json(variables_file)
        except ValueError as error:
            errors.append(str(error))
            continue

        structure_errors = validate_json_structure(
            data,
            variables_file,
        )

        errors.extend(structure_errors)

        if structure_errors:
            continue

        for variable in data:
            variable_with_block = variable.copy()
            variable_with_block["_block"] = block_name
            variables.append(variable_with_block)

    # --------------------------------------------------------
    # Validações estruturais
    # --------------------------------------------------------

    errors.extend(
        validate_required_fields(variables)
    )

    errors.extend(
        validate_field_types(variables)
    )

    errors.extend(
        validate_non_empty_values(variables)
    )

    errors.extend(
        validate_enum_values(variables)
    )

    errors.extend(
        validate_scope_consistency(variables)
    )

    errors.extend(
        validate_scope_values(variables)
    )

    errors.extend(
        validate_variable_id_ranges(variables)
    )

    errors.extend(
        validate_variable_ids(variables)
    )

    warnings = validate_variable_signatures(
        variables
    )

    return {
        "errors": errors,
        "warnings": warnings,
        "is_valid": len(errors) == 0,
    }
