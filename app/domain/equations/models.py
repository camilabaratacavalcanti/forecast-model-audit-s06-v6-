from dataclasses import dataclass


@dataclass
class Equation:
    """
    Modelo legado de equação.

    O versionamento continua pertencendo à equação.
    """

    equation_id: str
    target_variable_id: str
    version: int
    scope_type: str | None
    scope_value: str | None
    expression: str
    source_reference: str
    status: str


@dataclass(frozen=True)
class EquationDefinition:
    """
    Definição lógica de uma equação.

    A Definition contém a regra matemática, seu alvo,
    sua versão e seu escopo declarado.

    A expressão pertence à Definition.
    """

    equation_definition_id: str
    target_variable_id: str
    version: int
    scope_type: str | None
    scope_value: str | None
    expression: str
    source_reference: str
    status: str

    @classmethod
    def from_equation(
        cls,
        equation: Equation,
    ) -> "EquationDefinition":
        return cls(
            equation_definition_id=equation.equation_id,
            target_variable_id=equation.target_variable_id,
            version=equation.version,
            scope_type=equation.scope_type,
            scope_value=equation.scope_value,
            expression=equation.expression,
            source_reference=equation.source_reference,
            status=equation.status,
        )


@dataclass(frozen=True)
class EquationInstance:
    """
    Instância concreta de uma EquationDefinition
    em um escopo resolvido.

    A expressão não é duplicada na Instance.
    """

    equation_instance_id: str
    equation_definition_id: str
    target_variable_id: str
    version: int
    scope_type: str
    scope_value: str

    @classmethod
    def create(
        cls,
        definition: EquationDefinition,
        scope_type: str,
        scope_value: str,
    ) -> "EquationInstance":
        if not scope_type:
            raise ValueError(
                "scope_type é obrigatório para criar "
                "EquationInstance."
            )

        if not scope_value:
            raise ValueError(
                "scope_value é obrigatório para criar "
                "EquationInstance."
            )

        instance_id = (
            f"{definition.equation_definition_id}"
            f"@v{definition.version}"
            f"@{scope_value}"
        )

        return cls(
            equation_instance_id=instance_id,
            equation_definition_id=(
                definition.equation_definition_id
            ),
            target_variable_id=definition.target_variable_id,
            version=definition.version,
            scope_type=scope_type,
            scope_value=scope_value,
        )
