from dataclasses import dataclass


@dataclass
class Parameter:
    """
    Modelo legado de parâmetro.

    Mantido por compatibilidade com o Registry atual.
    """

    parameter_id: str
    parameter_name: str
    description: str
    unit: str
    value: float | int
    version: int
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str


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
    description: str
    unit: str
    value: float | int
    version: int
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str

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
    scope_value: str
    value: float | int

    @classmethod
    def create(
        cls,
        definition: ParameterDefinition,
        scope_type: str,
        scope_value: str,
    ) -> "ParameterInstance":

        if not scope_type or not scope_value:
            raise ValueError(
                "scope_type and scope_value are required "
                "to create a parameter instance"
            )

        instance_id = (
            f"{definition.parameter_definition_id}"
            f"@v{definition.version}"
            f"@{scope_value}"
        )

        return cls(
            parameter_instance_id=instance_id,
            parameter_definition_id=definition.parameter_definition_id,
            version=definition.version,
            scope_type=scope_type,
            scope_value=scope_value,
            value=definition.value,
        )
