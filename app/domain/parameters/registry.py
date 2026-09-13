"""
Objetivo:
    Disponibilizar os registries de ParameterDefinition e
    ParameterInstance, mantendo também o ParameterRegistry legado.

    ParameterDefinition representa a definição versionada do
    parâmetro, enquanto ParameterInstance representa sua aplicação
    em um escopo concreto.
"""

import json

from app.domain.parameters.models import (
    Parameter,
    ParameterDefinition,
    ParameterInstance,
)


class ParameterRegistry:
    """
    Registry legado de parâmetros.

    Mantido por compatibilidade com a arquitetura existente.
    """

    def __init__(self):
        self._parameters = {}

    def add(self, parameter: Parameter):
        if parameter.parameter_id in self._parameters:
            raise ValueError(
                f"Parameter_ID já cadastrado: "
                f"{parameter.parameter_id}"
            )

        self._parameters[parameter.parameter_id] = parameter

    def get(self, parameter_id: str) -> Parameter:
        return self._parameters[parameter_id]

    def all(self):
        return list(self._parameters.values())

    def load_from_json(self, file_path: str):

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        for item in data:
            parameter = Parameter(**item)
            self.add(parameter)


class ParameterDefinitionRegistry:
    """
    Registry das definições lógicas de parâmetros.

    A identidade de uma definição é composta por:

        parameter_definition_id
        version
        scope_type
        scope_value
    """

    def __init__(self):
        self._definitions = {}

    def add(
        self,
        definition: ParameterDefinition,
    ):
        key = (
            definition.parameter_definition_id,
            definition.version,
            definition.scope_type,
            definition.scope_value,
        )

        if key in self._definitions:
            raise ValueError(
                "ParameterDefinition já cadastrada: "
                f"{definition.parameter_definition_id} "
                f"v{definition.version} "
                f"scope={definition.scope_type}/"
                f"{definition.scope_value}"
            )

        self._definitions[key] = definition

    def get(
        self,
        parameter_definition_id: str,
        version: int | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> ParameterDefinition:

        # --------------------------------------------------
        # Busca exata
        # --------------------------------------------------
        if (
            version is not None
            or scope_type is not None
            or scope_value is not None
        ):
            key = (
                parameter_definition_id,
                version,
                scope_type,
                scope_value,
            )

            return self._definitions[key]

        # --------------------------------------------------
        # Busca por ID quando não há versão/escopo informado
        # --------------------------------------------------
        matches = [
            definition
            for key, definition in self._definitions.items()
            if key[0] == parameter_definition_id
        ]

        if not matches:
            raise KeyError(
                parameter_definition_id
            )

        # Evita retornar uma definição arbitrária
        # quando existem múltiplas versões/scopes.
        if len(matches) > 1:
            raise ValueError(
                "Mais de uma ParameterDefinition encontrada "
                f"para '{parameter_definition_id}'. "
                "Informe version, scope_type e scope_value."
            )

        return matches[0]

    def all(self):
        return list(self._definitions.values())


class ParameterInstanceRegistry:
    """
    Registry das instâncias concretas de parâmetros.
    """

    def __init__(self):
        self._instances = {}

    def add(
        self,
        instance: ParameterInstance,
    ):
        if (
            instance.parameter_instance_id
            in self._instances
        ):
            raise ValueError(
                "ParameterInstance já cadastrada: "
                f"{instance.parameter_instance_id}"
            )

        self._instances[
            instance.parameter_instance_id
        ] = instance

    def get(
        self,
        parameter_instance_id: str,
    ) -> ParameterInstance:
        return self._instances[
            parameter_instance_id
        ]

    def all(self):
        return list(self._instances.values())
