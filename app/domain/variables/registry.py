"""
Objetivo:
    Disponibilizar os registries de VariableDefinition e
    VariableInstance, mantendo também o VariableRegistry legado.

    Os registries novos separam a identidade lógica da variável
    de suas ocorrências concretas por escopo.
"""

import json
from app.domain.variables.models import Variable


# Responsável por localizar e salvar uma variável pelo seu ID,
# ou seja, organiza o acesso aos formulários preenchidos


# Cria uma classe responsável pelo cadastro
class VariableRegistry:
    def __init__(self):
        # Cria um dicionário Python
        self._variables = {}

    def add(self, variable: Variable):
        if variable.variable_id in self._variables:
            raise ValueError(
                f"Variable_ID já cadastrado: {variable.variable_id}"
            )

        self._variables[variable.variable_id] = variable

    def get(self, variable_id: str) -> Variable:
        return self._variables[variable_id]

    def all(self):
        return list(self._variables.values())

    # Conectar o arquivo .json ao python
    def load_from_json(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        for item in data:
            variable = Variable(**item)
            self.add(variable)


class VariableDefinitionRegistry:
    """Registry das definições lógicas de variáveis."""

    def __init__(self):
        self._definitions = {}

    def add(self, definition):
        if definition.variable_definition_id in self._definitions:
            raise ValueError(
                "Variable definition ID já cadastrado: "
                f"{definition.variable_definition_id}"
            )

        self._definitions[
            definition.variable_definition_id
        ] = definition

    def get(self, variable_definition_id: str):
        return self._definitions[variable_definition_id]

    def all(self):
        return list(self._definitions.values())


class VariableInstanceRegistry:
    """Registry das instâncias concretas de variáveis."""

    def __init__(self):
        self._instances = {}

    def add(self, instance):
        if instance.variable_instance_id in self._instances:
            raise ValueError(
                "Variable instance ID já cadastrado: "
                f"{instance.variable_instance_id}"
            )

        self._instances[
            instance.variable_instance_id
        ] = instance

    def get(self, variable_instance_id: str):
        return self._instances[variable_instance_id]

    def all(self):
        return list(self._instances.values())
