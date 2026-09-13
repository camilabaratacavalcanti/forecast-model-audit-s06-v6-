"""
Objetivo:
    Disponibilizar os registries de EquationDefinition e
    EquationInstance, mantendo o EquationRegistry legado.

    EquationDefinition contém a regra matemática e EquationInstance
    representa a aplicação concreta dessa regra em um escopo.
"""

from typing import List

from app.domain.equations.models import (
    Equation,
    EquationDefinition,
    EquationInstance,
)


class EquationRegistry:
    """
    Registry legado de equações.

    Mantém o versionamento pela combinação:
    equation_id + version.
    """

    def __init__(self):
        self._equations = {}

    def add(self, equation: Equation):
        key = (
            equation.equation_id,
            equation.version,
        )

        if key in self._equations:
            raise ValueError(
                "Equation já cadastrada para a versão: "
                f"{equation.equation_id} "
                f"v{equation.version}"
            )

        self._equations[key] = equation

    def get(
        self,
        equation_id: str,
        version: int,
    ) -> Equation:
        key = (
            equation_id,
            version,
        )

        return self._equations[key]

    def all(self) -> List[Equation]:
        return list(self._equations.values())


class EquationDefinitionRegistry:
    """
    Registry das definições lógicas de equações.

    A chave considera:
        equation_definition_id
        version
        scope_type
        scope_value
    """

    def __init__(self):
        self._definitions = {}

    def add(self, definition: EquationDefinition):
        key = (
            definition.equation_definition_id,
            definition.version,
            definition.scope_type,
            definition.scope_value,
        )

        if key in self._definitions:
            raise ValueError(
                "EquationDefinition já cadastrada: "
                f"{definition.equation_definition_id} "
                f"v{definition.version} "
                f"{definition.scope_type}/"
                f"{definition.scope_value}"
            )

        self._definitions[key] = definition

    def get(
        self,
        equation_definition_id: str,
        version: int | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> EquationDefinition:

        matches = [
            definition
            for key, definition in self._definitions.items()
            if key[0] == equation_definition_id
            and (
                version is None
                or key[1] == version
            )
            and (
                scope_type is None
                or key[2] == scope_type
            )
            and (
                scope_value is None
                or key[3] == scope_value
            )
        ]

        if not matches:
            raise KeyError(equation_definition_id)

        if len(matches) > 1:
            raise ValueError(
                "EquationDefinition ambígua. "
                "Informe version e/ou scope."
            )

        return matches[0]

    def all(self):
        return list(self._definitions.values())


class EquationInstanceRegistry:
    """
    Registry das instâncias concretas de equações.
    """

    def __init__(self):
        self._instances = {}

    def add(
        self,
        instance: EquationInstance,
    ):
        if (
            instance.equation_instance_id
            in self._instances
        ):
            raise ValueError(
                "EquationInstance já cadastrada: "
                f"{instance.equation_instance_id}"
            )

        self._instances[
            instance.equation_instance_id
        ] = instance

    def get(
        self,
        equation_instance_id: str,
    ) -> EquationInstance:
        return self._instances[
            equation_instance_id
        ]

    def all(self) -> List[EquationInstance]:
        return list(self._instances.values())
