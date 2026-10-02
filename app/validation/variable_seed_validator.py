import json
from pathlib import Path

from app.domain.values import CATEGORICAL, RESULT_STATE_TAXONOMY, VALUE_TYPES
from app.engine.scope_resolver import ScopeResolver


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
    "value_type",
]


# Campos contratuais opcionais (ausentes = não declarados no workbook).
OPTIONAL_VARIABLE_FIELDS = [
    "allowed_values",
    "declared_result_states",
    "instances",
]

ALLOWED_VARIABLE_FIELDS = set(REQUIRED_VARIABLE_FIELDS) | set(
    OPTIONAL_VARIABLE_FIELDS
)


# Taxonomia oficial de blocos (29 blocos, faixa continua
# 10000-38999, 1000 IDs por bloco, sem sobreposicao).
#
# "hydrate" e "costs" foram removidos desta taxonomia:
# "hydrate" foi substituido por "max_ht" na mesma faixa
# (13000-13999); "costs" foi desmembrado nos tres blocos de
# custo (budget_cost, budget_forecast_cost, actual_forecast_cost)
# mais os blocos budget/forecast, cada um com faixa propria.
#
# As chaves da taxonomia anterior (em portugues) foram renomeadas
# para ingles mantendo os mesmos ranges numericos (commit 1d3276e).
# O crosswalk historico -> canonico e normativo (D-TAX-02, blocos de
# custo) e nao deve ser inferido por nome: ver
# audit/stage3_4/taxonomy_migration/cost_crosswalk_d_tax_02.json.
#
# "budget_vs_forecast" foi introduzido em 37000-37999; "shared"
# foi realocado de 37000-37999 para 38000-38999.
# D-TAX-01 (decisao normativa posterior ao fechamento da Stage 3):
# esta e a lista canonica de 29 blocos, na ordem canonica, em todas
# as fontes -- identica a tools.workbook_seed.taxonomy.BLOCK_TAXONOMY
# e a taxonomia de data/seed/interblock_links.json. A faixa
# 30000-30999 chama-se thickener_flocculant.
VARIABLE_ID_RANGES = {
    "maintenance": (10000, 10999),
    "yield": (11000, 11999),
    "production": (12000, 12999),
    "max_ht": (13000, 13999),
    "alumina": (14000, 14999),
    "temperature_lp": (15000, 15999),
    "area_41": (16000, 16999),
    "area_04_13": (17000, 17999),
    "energy": (18000, 18999),
    "boilers": (19000, 19999),
    "volume": (20000, 20999),
    "soda": (21000, 21999),
    "residue_factor": (22000, 22999),
    "condensate_flow": (23000, 23999),
    "forecast_volume": (24000, 24999),
    "full_volume_target": (25000, 25999),
    "empty_space_target_control": (26000, 26999),
    "lime": (27000, 27999),
    "hydrated_flocculant": (28000, 28999),
    "sludge_flocculant": (29000, 29999),
    "thickener_flocculant": (30000, 30999),
    "acid": (31000, 31999),
    "budget_cost": (32000, 32999),
    "budget_forecast_cost": (33000, 33999),
    "actual_forecast_cost": (34000, 34999),
    "budget": (35000, 35999),
    "forecast": (36000, 36999),
    "budget_vs_forecast": (37000, 37999),
    "shared": (38000, 38999),
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
    "área",
    "planta",
    "global",
}


ALLOWED_STATUSES = {
    "draft",
    "ativo",
    "inativo",
}


ALLOWED_UNITS = {
    # D-5A-1 (Stage 5A): boilers (5B), max_ht v13 e area_04_13
    "kWh/tv",
    "tv/MWh",
    "tv/t carvão",
    "GJ/d",
    "m³/d",
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
    # Padronizacao de unidades de taxa de massa: "t/h" ja existia;
    # "t/d" e "t/mês" adicionadas para completar o trio oficial
    # (toneladas por hora / dia / mes).
    "t/d",
    "t/mês",
    # Bloco MaxHT (auditoria descritivo_das_variáveis_MaxHT_v5.xlsx):
    "t/ano",
    "kg/h",
    "kg/d",
    "kg/mês",
    "kg/ano",
    "m³/mês",
    "m³/ano",
    "mg/l",
}


# Aliases de unidade que representam a MESMA grandeza física que uma
# unidade já canônica em ALLOWED_UNITS, apenas com grafia diferente
# na fonte (workbook). Normalizados para a forma canônica no
# carregamento do seed (`load_variables_from_seed`), antes de
# qualquer validação -- não é uma conversão numérica (nenhum fator
# multiplicativo), apenas troca de rótulo textual.
UNIT_ALIASES = {
    "tph": "t/h",
}


def normalize_unit(unit):
    """Normaliza um alias de unidade para sua forma canônica."""
    return UNIT_ALIASES.get(unit, unit)


# Faixas contíguas de linhas (L1_L2 ... L6_L7): escopo declarado de
# uma definição com instâncias por linha (uma instância por linha do
# workbook). Só são aceitas com `instances` declaradas, exceto L1_L7.
LINE_RANGE_VALUES = {
    f"L{start}_L{end}"
    for start in range(1, 8)
    for end in range(start + 1, 8)
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
    "PLANTA",
} | LINE_RANGE_VALUES


# Campos que obrigatoriamente devem conter uma string
# não vazia.
NON_EMPTY_STRING_FIELDS = {
    "variable_id",
    "variable_name",
    "unit",
    "source_reference",
}


# Campos que devem ser strings quando preenchidos.
OPTIONAL_STRING_FIELDS = {
    "scope_type",
    "scope_value",
    # A descrição vem do workbook aprovado, onde pode estar vazia
    # (null); quando preenchida, não pode ser texto vazio.
    "description",
}

# Campos que possuem valores controlados por enum.
ENUM_FIELDS = {
    "variable_type": ALLOWED_VARIABLE_TYPES,
    "frequency": ALLOWED_FREQUENCIES,
    "status": ALLOWED_STATUSES,
    "unit": ALLOWED_UNITS,
    "scope_type": ALLOWED_SCOPE_TYPES,
    "scope_value": ALLOWED_SCOPE_VALUES,
    # Obrigatório (REQUIRED_VARIABLE_FIELDS): sem padrão, sem alias.
    "value_type": VALUE_TYPES,
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

    A unidade de cada variável é normalizada (`normalize_unit`) neste
    ponto, antes de qualquer validação ou construção de domain
    object -- ex.: "tph" (grafia do workbook) vira "t/h" (forma
    canônica), sem nenhuma conversão numérica.
    """
    variables = []

    variable_files = find_variable_files(seed_path)

    for variables_file in variable_files:
        block_name = variables_file.parent.name
        block_variables = load_json(variables_file)

        for variable in block_variables:
            variable_with_block = variable.copy()
            variable_with_block["_block"] = block_name
            if "unit" in variable_with_block:
                variable_with_block["unit"] = normalize_unit(
                    variable_with_block["unit"]
                )
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

        for field in NON_EMPTY_STRING_FIELDS | {"description"}:
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


# scope_types cujo scope_value concreto é sempre None: não
# materializam por linha/grupo/planta, e essa ausência de valor não
# é um erro (ver contrato de scope da plataforma).
SCOPELESS_SCOPE_TYPES = {"área", "global"}


def validate_scope_consistency(
    variables: list[dict],
) -> list[str]:
    """
    Valida a consistência entre scope_type e scope_value.

    Regra:
    - ambos None; ou
    - ambos preenchidos; ou
    - scope_type em {"área", "global"} com scope_value None
      (escopo singular, sem materialização por linha).
    """
    errors = []

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        scope_type = variable.get("scope_type")
        scope_value = variable.get("scope_value")

        if (
            scope_type in SCOPELESS_SCOPE_TYPES
            and scope_value is None
        ):
            continue

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


def validate_scope_type_value_combination(
    variables: list[dict],
) -> list[str]:
    """
    Valida a combinação semântica entre scope_type e scope_value,
    equivalente à mesma validação já existente em
    parameter_seed_validator/equation_seed_validator:

        linha       -> L1 ... L7 ou L1_L7
        linha_grupo -> L1_L3, L4_L5, L6_L7 ou L1_L7
        área/global -> sem scope_value específico de linha
        planta      -> scope_value deve ser exatamente "PLANTA"
                       (escopo singular, mas com um scope_value
                       concreto — não None — pois é o valor exigido
                       por ScopeResolver.PLANT_SCOPE para resolver a
                       instância; ver ScopeResolver._resolve_plant_scope)
    """
    errors = []

    valid_line_values = {
        "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L1_L7",
    }

    valid_line_group_values = {
        "L1_L3", "L4_L5", "L6_L7", "L1_L7",
    }

    for variable in variables:
        block = variable.get("_block", "unknown")
        variable_id = variable.get("variable_id", "unknown")

        scope_type = variable.get("scope_type")
        scope_value = variable.get("scope_value")

        if scope_type is None:
            continue

        if scope_type == "linha":
            # Uma faixa de linhas (ex.: L4_L7) só é escopo de uma
            # definição com instâncias por linha declaradas.
            declared_range = (
                scope_value in LINE_RANGE_VALUES
                and variable.get("instances") is not None
            )

            if scope_value not in valid_line_values and not declared_range:
                errors.append(
                    f"Invalid scope_value '{scope_value}' for "
                    f"scope_type 'linha' in {block}/variables.json "
                    f"for variable {variable_id}"
                )

        elif scope_type == "linha_grupo":
            if scope_value not in valid_line_group_values:
                errors.append(
                    f"Invalid scope_value '{scope_value}' for "
                    f"scope_type 'linha_grupo' in "
                    f"{block}/variables.json for variable "
                    f"{variable_id}"
                )

        elif scope_type in SCOPELESS_SCOPE_TYPES:
            if scope_value is not None:
                errors.append(
                    f"scope_type '{scope_type}' must not have a "
                    f"line-specific scope_value in "
                    f"{block}/variables.json for variable "
                    f"{variable_id}"
                )

        elif scope_type == "planta":
            if scope_value != "PLANTA":
                errors.append(
                    f"scope_type 'planta' requires scope_value "
                    f"'PLANTA' in {block}/variables.json for "
                    f"variable {variable_id}"
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


def _instance_scopes(variable: dict) -> list[tuple]:
    scope_type = variable.get("scope_type")

    if scope_type is None:
        return [(None, None)]

    try:
        return ScopeResolver().resolve_scopes(
            scope_type, variable.get("scope_value")
        )
    except ValueError:
        # Escopo inválido já é reportado pelas validações de escopo.
        return []


def validate_variable_identity(
    variables: list[dict],
) -> tuple[list[str], list[str]]:
    """
    Identidade contratual = variable_name + frequency + scope_type +
    scope_value, avaliada por instância concreta (ScopeResolver).
    unit, variable_type, description e source_reference NÃO fazem parte
    da identidade.

    Duas definições do MESMO bloco com a mesma identidade: erro.
    A mesma identidade em blocos diferentes: aviso — o mecanismo de
    ligação entre workbooks (identidade global x entrada local) é uma
    decisão contratual pendente (D24-11) e não é decidido aqui.
    """

    errors = []
    warnings = []
    seen: dict[tuple, dict] = {}
    reported_cross_block: set[tuple] = set()

    for variable in variables:
        if not all(
            field in variable
            for field in ("variable_name", "frequency", "scope_type", "scope_value")
        ):
            continue

        for scope in _instance_scopes(variable):
            key = (variable["variable_name"], variable["frequency"], *scope)
            previous = seen.get(key)

            if previous is None:
                seen[key] = variable
                continue

            if previous.get("_block") == variable.get("_block"):
                errors.append(
                    "Duplicate variable identity "
                    f"{key} in {variable.get('_block', 'unknown')}/"
                    "variables.json: "
                    f"{previous.get('variable_id', 'unknown')} and "
                    f"{variable.get('variable_id', 'unknown')}"
                )
            else:
                pair = (
                    variable["variable_name"],
                    variable["frequency"],
                    variable.get("scope_type"),
                    variable.get("scope_value"),
                    previous.get("_block"),
                    variable.get("_block"),
                )

                if pair not in reported_cross_block:
                    reported_cross_block.add(pair)
                    warnings.append(
                        "Cross-block identity (pending contract decision "
                        f"D24-11): {key[:2]} "
                        f"{variable.get('scope_type')}/"
                        f"{variable.get('scope_value')} declared by "
                        f"{previous.get('variable_id', 'unknown')} "
                        f"({previous.get('_block', 'unknown')}) and "
                        f"{variable.get('variable_id', 'unknown')} "
                        f"({variable.get('_block', 'unknown')})"
                    )

    return errors, warnings


# ============================================================
# CAMPOS CONTRATUAIS DO WORKBOOK
# ============================================================


def _label(variable: dict) -> str:
    return (
        f"{variable.get('_block', 'unknown')}/variables.json for "
        f"variable {variable.get('variable_id', 'unknown')}"
    )


def validate_unknown_fields(variables: list[dict]) -> list[str]:
    """Campo fora do contrato do seed é erro, nunca descartado."""

    errors = []

    for variable in variables:
        unknown = sorted(
            set(variable) - ALLOWED_VARIABLE_FIELDS - {"_block"}
        )

        if unknown:
            errors.append(
                f"Unknown field(s) {unknown} in {_label(variable)}"
            )

    return errors


def validate_allowed_values(variables: list[dict]) -> list[str]:
    errors = []

    for variable in variables:
        if "allowed_values" not in variable:
            continue

        options = variable["allowed_values"]

        if (
            not isinstance(options, list)
            or not options
            or any(not isinstance(o, str) or not o for o in options)
            or len(set(options)) != len(options)
        ):
            errors.append(
                "Invalid allowed_values (non-empty list of unique "
                f"non-empty strings expected) in {_label(variable)}"
            )

        if variable.get("value_type") != CATEGORICAL:
            errors.append(
                f"allowed_values requires value_type '{CATEGORICAL}' "
                f"in {_label(variable)}"
            )

    return errors


def validate_declared_result_states(variables: list[dict]) -> list[str]:
    errors = []

    for variable in variables:
        if "declared_result_states" not in variable:
            continue

        states = variable["declared_result_states"]

        if not isinstance(states, list) or not states:
            errors.append(
                "Invalid declared_result_states (non-empty list expected) "
                f"in {_label(variable)}"
            )
            continue

        names = []

        for state in states:
            if (
                not isinstance(state, dict)
                or set(state) != {"state", "literal"}
                or state["state"] not in RESULT_STATE_TAXONOMY
                or not isinstance(state["literal"], str)
                or not state["literal"]
            ):
                errors.append(
                    f"Invalid declared_result_states entry {state!r} "
                    f"(state in {sorted(RESULT_STATE_TAXONOMY)} and a "
                    f"non-empty text literal) in {_label(variable)}"
                )
                continue

            names.append(state["state"])

        if len(set(names)) != len(names):
            errors.append(
                f"Repeated state in declared_result_states in {_label(variable)}"
            )

    return errors


def validate_instances(variables: list[dict]) -> list[str]:
    """
    `instances` declara as instâncias de uma definição com instâncias
    por linha (uma linha do workbook = uma instância). Quando
    presentes, cobrem exatamente os escopos concretos da definição. Uma
    faixa de linhas diferente de L1_L7 só existe como definição com
    instâncias declaradas.
    """

    errors = []

    for variable in variables:
        scope_value = variable.get("scope_value")
        instances = variable.get("instances")

        if (
            variable.get("scope_type") == "linha"
            and scope_value in LINE_RANGE_VALUES
            and scope_value != "L1_L7"
            and instances is None
        ):
            errors.append(
                f"Line range '{scope_value}' requires declared instances "
                f"in {_label(variable)}"
            )

        if instances is None:
            continue

        if not isinstance(instances, list) or not instances:
            errors.append(
                f"Invalid instances (non-empty list expected) in {_label(variable)}"
            )
            continue

        declared = []

        for instance in instances:
            if (
                not isinstance(instance, dict)
                or set(instance) != {"scope_value", "description", "source_reference"}
                or not isinstance(instance["scope_value"], str)
                or not isinstance(instance["source_reference"], str)
                or not instance["source_reference"]
                or (
                    instance["description"] is not None
                    and (
                        not isinstance(instance["description"], str)
                        or not instance["description"]
                    )
                )
            ):
                errors.append(
                    f"Invalid instance declaration {instance!r} in "
                    f"{_label(variable)}"
                )
                continue

            declared.append(("linha", instance["scope_value"]))

        expected = _instance_scopes(variable)

        if sorted(declared) != sorted(expected):
            errors.append(
                f"Declared instances {sorted(d[1] for d in declared)} do not "
                f"match the definition scopes {sorted(e[1] for e in expected)} "
                f"in {_label(variable)}"
            )

    return errors


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
            if "unit" in variable_with_block:
                variable_with_block["unit"] = normalize_unit(
                    variable_with_block["unit"]
                )
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
        validate_scope_type_value_combination(variables)
    )

    errors.extend(
        validate_variable_id_ranges(variables)
    )

    errors.extend(
        validate_variable_ids(variables)
    )

    errors.extend(validate_unknown_fields(variables))
    errors.extend(validate_allowed_values(variables))
    errors.extend(validate_declared_result_states(variables))
    errors.extend(validate_instances(variables))

    identity_errors, warnings = validate_variable_identity(variables)
    errors.extend(identity_errors)

    return {
        "errors": errors,
        "warnings": warnings,
        "is_valid": len(errors) == 0,
    }
