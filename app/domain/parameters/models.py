from dataclasses import dataclass

from app.domain.values import NUMERIC, VALUE_TYPES, is_numeric


@dataclass
class Parameter:
    """
    Modelo legado de parâmetro.

    Mantido por compatibilidade com o Registry atual.
    """

    parameter_id: str
    parameter_name: str
    description: str | None
    unit: str
    value: float | int
    version: int
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str
    # Obrigatório: parâmetros são numéricos ("numerico"); não existe
    # valor padrão.
    value_type: str
    # Frequência declarada no workbook (pode estar vazia): parte da
    # identidade name + frequency + scope.
    frequency: str | None = None


@dataclass(frozen=True)
class ParameterDefinition:
    """
    Definição lógica de um parâmetro.

    A Definition descreve o parâmetro e seu valor declarado.
    Não representa uma ocorrência concreta em uma linha,
    grupo ou planta.
    """

    parameter_definition_id: str
    parameter_name: str
    description: str | None
    unit: str
    value: float | int
    version: int
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str
    value_type: str
    frequency: str | None = None

    @classmethod
    def from_parameter(
        cls,
        parameter: Parameter,
    ) -> "ParameterDefinition":
        return cls(
            parameter_definition_id=parameter.parameter_id,
            parameter_name=parameter.parameter_name,
            description=parameter.description,
            unit=parameter.unit,
            value=parameter.value,
            version=parameter.version,
            scope_type=parameter.scope_type,
            scope_value=parameter.scope_value,
            source_reference=parameter.source_reference,
            status=parameter.status,
            value_type=parameter.value_type,
            frequency=parameter.frequency,
        )

    def __post_init__(self) -> None:
        if self.value_type not in VALUE_TYPES:
            raise ValueError(
                f"value_type inválido para {self.parameter_definition_id}: "
                f"{self.value_type!r} (permitidos: {sorted(VALUE_TYPES)})"
            )

        if self.value_type != NUMERIC or not is_numeric(self.value):
            raise ValueError(
                f"{self.parameter_definition_id}: parâmetro exige value_type "
                f"'{NUMERIC}' e valor numérico (recebido "
                f"{self.value_type!r}, {self.value!r}); nenhum valor é "
                "convertido."
            )


@dataclass(frozen=True)
class ParameterInstance:
    """
    Instância concreta de uma ParameterDefinition
    em um escopo resolvido.

    O valor do parâmetro não é duplicado na Instance.
    Ele continua pertencendo à ParameterDefinition.
    """

    parameter_instance_id: str
    parameter_definition_id: str
    version: int
    scope_type: str
    scope_value: str | None
    value: float | int

    # scope_types cujo scope_value concreto é None (não materializam
    # por linha/grupo/planta): a Definition e a Instance coincidem
    # em uma única ocorrência singular.
    SCOPELESS_SCOPE_TYPES = {"área", "global"}

    @classmethod
    def create(
        cls,
        definition: ParameterDefinition,
        scope_type: str,
        scope_value: str | None,
    ) -> "ParameterInstance":

        if not scope_type:
            raise ValueError(
                "scope_type is required to create a parameter instance"
            )

        if (
            not scope_value
            and scope_type not in cls.SCOPELESS_SCOPE_TYPES
        ):
            raise ValueError(
                "scope_value is required to create a parameter instance"
            )

        instance_id = (
            f"{definition.parameter_definition_id}"
            f"@v{definition.version}"
            f"@{scope_value}"
            if scope_value
            else (
                f"{definition.parameter_definition_id}"
                f"@v{definition.version}"
            )
        )

        return cls(
            parameter_instance_id=instance_id,
            parameter_definition_id=definition.parameter_definition_id,
            version=definition.version,
            scope_type=scope_type,
            scope_value=scope_value,
            value=definition.value,
        )
