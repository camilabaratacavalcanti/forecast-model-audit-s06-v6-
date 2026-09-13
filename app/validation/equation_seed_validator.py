import json
from pathlib import Path

from app.engine.exceptions import (
    InvalidExpressionError,
    UnsafeExpressionError,
)
from app.engine.expression_parser import ExpressionParser


# ============================================================
# REGRAS DO EQUATION REGISTRY
# ============================================================

REQUIRED_EQUATION_FIELDS = [
    "equation_id",
    "target_variable_id",
    "version",
    "scope_type",
    "scope_value",
    "expression",
    "source_reference",
    "status",
]


# Faixas reservadas para Equation_ID por bloco.
#
# O sufixo numérico do Equation_ID deve estar dentro
# da faixa correspondente ao bloco.
EQUATION_ID_RANGES = {
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

ALLOWED_SCOPE_TYPES = {
    "linha",
    "linha_grupo",
    "área",
    "planta",
    "global",
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


ALLOWED_STATUSES = {
    "DRAFT",
    "PENDING",
    "APPROVED",
    "PUBLISHED",
    "REJECTED",
}


# Campos string que não podem estar vazios.
NON_EMPTY_EQUATION_STRING_FIELDS = {
    "equation_id",
    "target_variable_id",
    "expression",
    "source_reference",
}


# scope_value é um campo obrigatório no Registry, porém
# seu valor pode ser None quando scope_type = "global".
OPTIONAL_EQUATION_STRING_FIELDS = {
    "scope_value",
}


ENUM_FIELDS = {
    "scope_type": ALLOWED_SCOPE_TYPES,
    "scope_value": ALLOWED_SCOPE_VALUES,
    "status": ALLOWED_STATUSES,
}


# ============================================================
# LEITURA DO JSON
# ============================================================

def load_json(file_path: Path):
    """
    Carrega um arquivo JSON.
    """
    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON inválido em {file_path}: {exc}"
        ) from exc


# ============================================================
# VALIDAÇÃO DA ESTRUTURA DO JSON
# ============================================================

def validate_json_structure(data, file_path: Path):
    """
    Valida a estrutura básica do arquivo JSON.

    O arquivo deve conter uma lista de equações.
    """
    errors = []

    if not isinstance(data, list):
        errors.append(
            f"{file_path}: o conteúdo deve ser uma lista JSON."
        )
        return errors

    for index, equation in enumerate(data):
        if not isinstance(equation, dict):
            errors.append(
                f"{file_path}: item {index} deve ser um objeto JSON."
            )

    return errors


# ============================================================
# VALIDAÇÃO DO CAMINHO DO SEED
# ============================================================

def validate_seed_path(file_path: Path):
    """
    Valida se o arquivo está localizado em uma estrutura
    de seed compatível com o Equation Registry.
    """
    errors = []

    if file_path.name != "equations.json":
        errors.append(
            f"{file_path}: o arquivo deve se chamar equations.json."
        )

    if "seed" not in file_path.parts:
        errors.append(
            f"{file_path}: o arquivo deve estar dentro "
            "de um diretório data/seed."
        )

    return errors


# ============================================================
# LOCALIZAÇÃO DOS ARQUIVOS DE SEED
# ============================================================

def find_equation_files(seed_root: Path):
    """
    Localiza todos os arquivos equations.json abaixo do diretório
    de seed.
    """
    return sorted(seed_root.rglob("equations.json"))


# ============================================================
# CARREGAMENTO DAS EQUAÇÕES
# ============================================================

def load_equations_from_seed(seed_root: Path):
    """
    Carrega todas as equações dos arquivos equations.json
    encontrados no diretório de seed.

    Retorna:
        equations: lista de equações
        errors: lista de erros encontrados durante a leitura
    """
    equations = []
    errors = []

    equation_files = find_equation_files(seed_root)

    for file_path in equation_files:
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

        equations.extend(data)

    return equations, errors


# ============================================================
# CAMPOS OBRIGATÓRIOS
# ============================================================

def validate_required_fields(equations):
    """
    Verifica se todos os campos obrigatórios estão presentes.
    """
    errors = []

    for index, equation in enumerate(equations):
        for field in REQUIRED_EQUATION_FIELDS:
            if field not in equation:
                errors.append(
                    f"Equação no índice {index}: "
                    f"campo obrigatório ausente: {field}"
                )

    return errors


# ============================================================
# TIPOS DOS CAMPOS
# ============================================================

def validate_field_types(equations):
    """
    Valida os tipos dos campos do Equation Registry.
    """
    errors = []

    string_fields = {
        "equation_id",
        "target_variable_id",
        "scope_type",
        "expression",
        "source_reference",
        "status",
    }

    for index, equation in enumerate(equations):

        for field in string_fields:
            if field not in equation:
                continue

            if not isinstance(equation[field], str):
                errors.append(
                    f"Equação no índice {index}: "
                    f"campo '{field}' deve ser string."
                )

        if "scope_value" in equation:
            value = equation["scope_value"]

            if value is not None and not isinstance(value, str):
                errors.append(
                    f"Equação no índice {index}: "
                    "campo 'scope_value' deve ser string ou None."
                )

        if "version" in equation:
            version = equation["version"]

            if isinstance(version, bool) or not isinstance(version, int):
                errors.append(
                    f"Equação no índice {index}: "
                    "campo 'version' deve ser inteiro."
                )

    return errors


# ============================================================
# VALORES NÃO VAZIOS
# ============================================================

def validate_non_empty_values(equations):
    """
    Verifica se os campos string obrigatórios não estão vazios.
    """
    errors = []

    for index, equation in enumerate(equations):

        for field in NON_EMPTY_EQUATION_STRING_FIELDS:

            if field not in equation:
                continue

            value = equation[field]

            if isinstance(value, str) and not value.strip():
                errors.append(
                    f"Equação no índice {index}: "
                    f"campo '{field}' não pode estar vazio."
                )

    return errors


# ============================================================
# VALORES ENUMERADOS
# ============================================================

def validate_enum_values(equations):
    """
    Valida os campos que possuem valores enumerados.
    """
    errors = []

    for index, equation in enumerate(equations):

        for field, allowed_values in ENUM_FIELDS.items():

            if field not in equation:
                continue

            value = equation[field]

            # scope_value pode ser None.
            if field == "scope_value" and value is None:
                continue

            if value not in allowed_values:
                errors.append(
                    f"Equação no índice {index}: "
                    f"valor inválido para '{field}': {value!r}. "
                    f"Valores permitidos: {sorted(allowed_values)}."
                )

    return errors


# ============================================================
# CONSISTÊNCIA DE ESCOPO
# ============================================================

def validate_scope_consistency(equations):
    """
    Valida a relação entre scope_type e scope_value.

    Regras:

    global:
        scope_value deve ser None.

    linha:
        scope_value deve ser L1 ... L7.

    linha_grupo:
        scope_value deve ser L1_L3, L4_L5 ou L6_L7.

    área:
        scope_value deve ser None.

    planta:
        scope_value deve ser None.
    """
    errors = []

    valid_line_values = {
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
        "L1_L7",
    }

    valid_line_group_values = {
        "L1_L3",
        "L4_L5",
        "L6_L7",
        "L1_L7",
    }

    for index, equation in enumerate(equations):

        if "scope_type" not in equation:
            continue

        if "scope_value" not in equation:
            continue

        scope_type = equation["scope_type"]
        scope_value = equation["scope_value"]

        if scope_type == "global":
            if scope_value is not None:
                errors.append(
                    f"{index}: quando scope_type='global', "
                    "scope_value deve ser None."
                )

        elif scope_type == "linha":
            if scope_value not in valid_line_values:
                errors.append(
                    f"{index}: quando scope_type='linha', "
                    "scope_value deve ser L1, L2, L3, L4, "
                    "L5, L6, L7 ou L1_L7."
                )

        elif scope_type == "linha_grupo":
            if scope_value not in valid_line_group_values:
                errors.append(
                    f"{index}: quando scope_type='linha_grupo', "
                    "scope_value deve ser L1_L3, L4_L5, L6_L7 ou L1_L7."
                )

        elif scope_type in {
            "área",
            "planta",
        }:
            if scope_value is not None:
                errors.append(
                    f"{index}: scope_type '{scope_type}' "
                    "não deve possuir scope_value específico."
                )

    return errors


# ============================================================
# VERSÃO
# ============================================================

def validate_versions(equations):
    """
    Valida a versão da equação.

    A versão deve ser um inteiro >= 1.
    """
    errors = []

    for index, equation in enumerate(equations):

        if "version" not in equation:
            continue

        version = equation["version"]

        if isinstance(version, bool):
            errors.append(
                f"Equação no índice {index}: "
                "version não pode ser bool."
            )
            continue

        if not isinstance(version, int):
            continue

        if version < 1:
            errors.append(
                f"Equação no índice {index}: "
                "version deve ser maior ou igual a 1."
            )

    return errors


# ============================================================
# FAIXAS DE EQUATION_ID
# ============================================================

def validate_equation_id_ranges(equations):
    """
    Valida o formato e a faixa numérica dos Equation_IDs.

    Formato esperado:

        EQ + número

    Exemplo:

        EQ12001
    """
    errors = []

    for index, equation in enumerate(equations):

        if "equation_id" not in equation:
            continue

        equation_id = equation["equation_id"]

        if not isinstance(equation_id, str):
            continue

        if not equation_id.startswith("EQ"):
            errors.append(
                f"Equação no índice {index}: "
                f"Equation_ID inválido: {equation_id!r}. "
                "Deve começar com 'EQ'."
            )
            continue

        numeric_part = equation_id[2:]

        if not numeric_part.isdigit():
            errors.append(
                f"Equação no índice {index}: "
                f"Equation_ID inválido: {equation_id!r}. "
                "A parte numérica deve conter apenas dígitos."
            )
            continue

        numeric_id = int(numeric_part)

        belongs_to_range = False

        for block, (minimum, maximum) in EQUATION_ID_RANGES.items():

            if minimum <= numeric_id <= maximum:
                belongs_to_range = True
                break

        if not belongs_to_range:
            errors.append(
                f"Equação no índice {index}: "
                f"Equation_ID {equation_id} "
                "não pertence a nenhuma faixa reservada."
            )

    return errors


# ============================================================
# ASSINATURA SEMÂNTICA
# ============================================================

def build_equation_signature(equation):
    """
    Constrói a assinatura semântica de uma equação.

    Equation_ID e version não fazem parte da assinatura,
    pois representam identidade técnica e versionamento.

    A assinatura representa a regra matemática em si.
    """
    return (
        equation["target_variable_id"],
        equation["scope_type"],
        equation["scope_value"],
        equation["expression"],
    )


# ============================================================
# DUPLICIDADE DE EQUATION_ID + VERSION
# ============================================================

def validate_equation_ids(equations):
    """
    Verifica duplicidade da combinação:

        equation_id + version

    A mesma Equation_ID pode possuir várias versões.
    """
    errors = []
    seen = set()

    for index, equation in enumerate(equations):

        if "equation_id" not in equation:
            continue

        if "version" not in equation:
            continue

        key = (
            equation["equation_id"],
            equation["version"],
        )

        if key in seen:
            errors.append(
                f"Equação no índice {index}: "
                f"combinação duplicada "
                f"(equation_id={equation['equation_id']}, "
                f"version={equation['version']})."
            )
        else:
            seen.add(key)

    return errors


# ============================================================
# DUPLICIDADE SEMÂNTICA
# ============================================================

def validate_equation_signatures(equations):
    """
    Identifica equações com a mesma regra matemática.

    Isso gera WARNING, e não ERROR.

    O mesmo conteúdo matemático pode existir em versões diferentes
    da mesma Equation_ID, pois o versionamento é permitido.
    """
    warnings = []
    signatures = {}

    for index, equation in enumerate(equations):

        required_fields = {
            "target_variable_id",
            "scope_type",
            "scope_value",
            "expression",
            "equation_id",
            "version",
        }

        if not required_fields.issubset(equation):
            continue

        signature = build_equation_signature(equation)

        if signature in signatures:

            previous_index = signatures[signature]

            warnings.append(
                f"Equação no índice {index}: "
                "mesma assinatura semântica encontrada "
                f"na equação do índice {previous_index}."
            )

        else:
            signatures[signature] = index

    return warnings


# ============================================================
# VALIDAÇÃO SINTÁTICA DA EXPRESSÃO (opt-in)
# ============================================================

def validate_expression_syntax(equations):
    """
    Valida se o campo 'expression' de cada equação é uma expressão
    matemática sintaticamente válida e seguro para o
    ExpressionParser/ExpressionEvaluator (VAR#####/PARAM##### com ou
    sem sufixo "@Lx", operadores aritméticos, parênteses).

    Esta validação é deliberadamente NÃO incluída em validate_seed():
    seeds legados/fixtures de teste usam expressões textuais
    (nomes livres, descrições de agregação temporal) que nunca
    passaram por essa checagem. Chamá-la é responsabilidade de quem
    está validando um seed que se pretende executável pelo Engine
    real (ex.: o seed real do Yield).
    """
    errors = []

    parser = ExpressionParser()

    for index, equation in enumerate(equations):
        expression = equation.get("expression")

        if not isinstance(expression, str):
            continue

        try:
            parser.parse(expression)
        except (
            InvalidExpressionError,
            UnsafeExpressionError,
        ) as exc:
            errors.append(
                f"Equação no índice {index} "
                f"({equation.get('equation_id', '?')}): "
                f"expressão inválida para o ExpressionParser: {exc}"
            )

    return errors


# ============================================================
# VALIDAÇÃO COMPLETA
# ============================================================

def validate_seed(seed_root: Path):
    """
    Executa todas as validações estruturais dos seeds
    do Equation Registry.

    Retorna:

        errors
        warnings
    """
    errors = []
    warnings = []

    seed_root = Path(seed_root)

    if not seed_root.exists():
        errors.append(
            f"Diretório de seed não encontrado: {seed_root}"
        )
        return errors, warnings

    equation_files = find_equation_files(seed_root)

    if not equation_files:
        return errors, warnings

    for file_path in equation_files:
        errors.extend(
            validate_seed_path(file_path)
        )

    equations, loading_errors = load_equations_from_seed(
        seed_root
    )

    errors.extend(loading_errors)

    if errors:
        return errors, warnings

    errors.extend(
        validate_required_fields(equations)
    )

    errors.extend(
        validate_field_types(equations)
    )

    errors.extend(
        validate_non_empty_values(equations)
    )

    errors.extend(
        validate_enum_values(equations)
    )

    errors.extend(
        validate_scope_consistency(equations)
    )

    errors.extend(
        validate_versions(equations)
    )

    errors.extend(
        validate_equation_id_ranges(equations)
    )

    errors.extend(
        validate_equation_ids(equations)
    )

    warnings.extend(
        validate_equation_signatures(equations)
    )

    return errors, warnings
