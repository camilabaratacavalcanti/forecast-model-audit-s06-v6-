"""
Objetivo:
    Definir os modelos de domínio de Variable, incluindo a separação
    entre VariableDefinition e VariableInstance.

    VariableDefinition representa a definição lógica da variável.

    VariableInstance representa uma ocorrência concreta da definição
    em um escopo resolvido.

    A dimensão temporal não pertence à VariableInstance e será tratada
    posteriormente pelo mecanismo de resolução temporal.
"""

from dataclasses import dataclass


@dataclass
class Variable:
    """
    Modelo atual de variável.

    Mantido temporariamente para compatibilidade com o contrato
    existente da plataforma.
    """

    variable_id: str
    variable_name: str
    description: str
    unit: str
    variable_type: str
    frequency: str
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str


@dataclass(frozen=True)
class VariableDefinition:
    """
    Definição lógica de uma variável.

    Representa o que a variável é, sua granularidade temporal
    e sua declaração de escopo.

    Não representa uma ocorrência concreta.
    """

    variable_definition_id: str
    variable_name: str
    description: str
    unit: str
    variable_type: str
    frequency: str
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str

    @classmethod
    def from_variable(cls, variable: Variable) -> "VariableDefinition":
        return cls(
            variable_definition_id=variable.variable_id,
            variable_name=variable.variable_name,
            description=variable.description,
            unit=variable.unit,
            variable_type=variable.variable_type,
            frequency=variable.frequency,
            scope_type=variable.scope_type,
            scope_value=variable.scope_value,
            source_reference=variable.source_reference,
            status=variable.status,
        )


@dataclass(frozen=True)
class VariableInstance:
    """
    Instância concreta de uma VariableDefinition.

    O período não pertence à instance.
    A dimensão temporal será resolvida posteriormente.
    """

    variable_instance_id: str
    variable_definition_id: str
    scope_type: str
    scope_value: str

    @classmethod
    def create(
        cls,
        definition: VariableDefinition,
        scope_type: str,
        scope_value: str,
    ) -> "VariableInstance":

        if not scope_type:
            raise ValueError(
                "scope_type is required to create a variable instance"
            )

        if not scope_value:
            raise ValueError(
                "scope_value is required to create a variable instance"
            )

        instance_id = (
            f"{definition.variable_definition_id}@{scope_value}"
        )

        return cls(
            variable_instance_id=instance_id,
            variable_definition_id=definition.variable_definition_id,
            scope_type=scope_type,
            scope_value=scope_value,
        )
