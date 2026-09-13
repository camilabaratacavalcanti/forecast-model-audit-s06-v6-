"""
Mantém o contexto de cálculo em memória.

Objetivo:
    Armazenar e recuperar os valores utilizados durante uma execução
    do Forecast Engine, preservando a compatibilidade com a API legada
    e suportando valores contextualizados por escopo e período.

Responsabilidades:
    - armazenar valores legados de Variable e Parameter;
    - armazenar valores contextualizados por scope e period;
    - armazenar e recuperar valores a partir de VariableInstance;
    - armazenar e recuperar valores a partir de ParameterInstance;
    - validar que os valores utilizados nos cálculos sejam numéricos.

Arquitetura:
    VariableDefinition
        ↓
    VariableInstance
        ↓
    CalculationContext

    ParameterDefinition
        ↓
    ParameterInstance
        ↓
    CalculationContext

    EquationInstance
        ↓
    EquationEngine
        ↓
    resultado
        ↓
    VariableInstance
        ↓
    CalculationContext

O CalculationContext não é responsável por armazenar ou executar
EquationInstances. A execução das equações pertence ao EquationEngine.
"""

from dataclasses import dataclass
from typing import Mapping

from app.engine.exceptions import (
    CalculationValueError,
    ParameterNotFoundError,
    VariableNotFoundError,
)


@dataclass(frozen=True)
class CalculationKey:
    """
    Identifica univocamente um valor dentro do contexto de cálculo.

    A chave combina:

        entity_id
        scope_type
        scope_value
        period_id

    Exemplos:

        VAR11001 / linha / L1 / 2026-01
        PARAM12001 / linha / L1 / 2026-01
    """

    entity_id: str
    scope_type: str | None = None
    scope_value: str | None = None
    period_id: str | None = None


class CalculationContext:
    """
    Contexto de valores utilizado durante uma execução.

    O Variable Registry e o Parameter Registry armazenam
    definições.

    O CalculationContext armazena os valores efetivamente
    utilizados durante o cálculo.

    O contexto suporta duas formas de acesso:

        1. API legada:
            get_variable()
            set_variable()
            get_parameter()
            set_parameter()

        2. API contextualizada:
            get_variable_value()
            set_variable_value()
            get_parameter_value()
            set_parameter_value()

        3. API orientada a Instance:
            get_variable_instance_value()
            set_variable_instance_value()
            get_parameter_instance_value()
            set_parameter_instance_value()
    """

    def __init__(
        self,
        variables: Mapping[str, int | float] | None = None,
        parameters: Mapping[str, int | float] | None = None,
    ):
        self._variables = dict(variables or {})
        self._parameters = dict(parameters or {})

        self._scoped_variables: dict[
            CalculationKey,
            int | float,
        ] = {}

        self._scoped_parameters: dict[
            CalculationKey,
            int | float,
        ] = {}

        self._validate_values(
            self._variables,
            "variável",
        )

        self._validate_values(
            self._parameters,
            "parâmetro",
        )

    # ========================================================
    # API LEGADA — VARIÁVEIS
    # ========================================================

    def get_variable(
        self,
        variable_id: str,
    ) -> int | float:
        """
        Retorna o valor legado de uma variável.
        """

        if variable_id not in self._variables:
            raise VariableNotFoundError(
                f"Valor da variável não encontrado: "
                f"{variable_id}"
            )

        return self._variables[variable_id]

    def set_variable(
        self,
        variable_id: str,
        value: int | float,
    ) -> None:
        """
        Define ou atualiza o valor legado de uma variável.
        """

        self._validate_single_value(
            value,
            f"variável {variable_id}",
        )

        self._variables[variable_id] = value

    # ========================================================
    # API LEGADA — PARÂMETROS
    # ========================================================

    def get_parameter(
        self,
        parameter_id: str,
    ) -> int | float:
        """
        Retorna o valor legado de um parâmetro.
        """

        if parameter_id not in self._parameters:
            raise ParameterNotFoundError(
                f"Valor do parâmetro não encontrado: "
                f"{parameter_id}"
            )

        return self._parameters[parameter_id]

    def set_parameter(
        self,
        parameter_id: str,
        value: int | float,
    ) -> None:
        """
        Define ou atualiza o valor legado de um parâmetro.
        """

        self._validate_single_value(
            value,
            f"parâmetro {parameter_id}",
        )

        self._parameters[parameter_id] = value

    # ========================================================
    # API CONTEXTUALIZADA — VARIÁVEIS
    # ========================================================

    def get_variable_value(
        self,
        variable_id: str,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> int | float:
        """
        Retorna o valor contextualizado de uma variável.
        """

        key = CalculationKey(
            entity_id=variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        if key not in self._scoped_variables:
            raise VariableNotFoundError(
                "Valor contextualizado da variável não encontrado: "
                f"{variable_id}, "
                f"scope_type={scope_type}, "
                f"scope_value={scope_value}, "
                f"period_id={period_id}"
            )

        return self._scoped_variables[key]

    def set_variable_value(
        self,
        variable_id: str,
        value: int | float,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza um valor contextualizado de variável.
        """

        self._validate_single_value(
            value,
            f"variável {variable_id}",
        )

        key = CalculationKey(
            entity_id=variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        self._scoped_variables[key] = value

    # ========================================================
    # API CONTEXTUALIZADA — PARÂMETROS
    # ========================================================

    def get_parameter_value(
        self,
        parameter_id: str,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> int | float:
        """
        Retorna o valor contextualizado de um parâmetro.
        """

        key = CalculationKey(
            entity_id=parameter_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        if key not in self._scoped_parameters:
            raise ParameterNotFoundError(
                "Valor contextualizado do parâmetro não encontrado: "
                f"{parameter_id}, "
                f"scope_type={scope_type}, "
                f"scope_value={scope_value}, "
                f"period_id={period_id}"
            )

        return self._scoped_parameters[key]

    def set_parameter_value(
        self,
        parameter_id: str,
        value: int | float,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza um valor contextualizado de parâmetro.
        """

        self._validate_single_value(
            value,
            f"parâmetro {parameter_id}",
        )

        key = CalculationKey(
            entity_id=parameter_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        self._scoped_parameters[key] = value

    # ========================================================
    # API POR INSTANCE — VARIÁVEIS
    # ========================================================

    def get_variable_instance_value(
        self,
        instance,
        period_id: str | None = None,
    ) -> int | float:
        """
        Retorna o valor de uma VariableInstance.

        A identidade espacial é obtida diretamente da Instance.
        O CalculationContext utiliza o variable_definition_id como
        entity_id e o scope_type/scope_value da Instance para formar
        a CalculationKey.

        A periodização continua sendo informada separadamente,
        pois o período representa uma dimensão do cálculo e não
        uma propriedade espacial da Instance.
        """

        return self.get_variable_value(
            variable_id=instance.variable_definition_id,
            scope_type=instance.scope_type,
            scope_value=instance.scope_value,
            period_id=period_id,
        )

    def set_variable_instance_value(
        self,
        instance,
        value: int | float,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza o valor de uma VariableInstance.

        A identidade da Instance determina automaticamente:
            - variable_definition_id;
            - scope_type;
            - scope_value.

        O período permanece explícito porque pertence ao contexto
        temporal da execução.
        """

        self.set_variable_value(
            variable_id=instance.variable_definition_id,
            value=value,
            scope_type=instance.scope_type,
            scope_value=instance.scope_value,
            period_id=period_id,
        )

    # ========================================================
    # API POR INSTANCE — PARÂMETROS
    # ========================================================

    def get_parameter_instance_value(
        self,
        instance,
        period_id: str | None = None,
    ) -> int | float:
        """
        Retorna o valor de uma ParameterInstance.

        A identidade espacial é obtida diretamente da Instance.
        O CalculationContext utiliza o parameter_definition_id como
        entity_id e o scope_type/scope_value da Instance para formar
        a CalculationKey.
        """

        return self.get_parameter_value(
            parameter_id=instance.parameter_definition_id,
            scope_type=instance.scope_type,
            scope_value=instance.scope_value,
            period_id=period_id,
        )

    def set_parameter_instance_value(
        self,
        instance,
        value: int | float,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza o valor de uma ParameterInstance.

        A identidade da Instance determina automaticamente:
            - parameter_definition_id;
            - scope_type;
            - scope_value.

        O período permanece explícito porque pertence ao contexto
        temporal da execução.
        """

        self.set_parameter_value(
            parameter_id=instance.parameter_definition_id,
            value=value,
            scope_type=instance.scope_type,
            scope_value=instance.scope_value,
            period_id=period_id,
        )

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    @staticmethod
    def _validate_values(
        values: Mapping[str, int | float],
        value_type: str,
    ) -> None:
        for identifier, value in values.items():
            CalculationContext._validate_single_value(
                value,
                f"{value_type} {identifier}",
            )

    @staticmethod
    def _validate_single_value(
        value: int | float,
        description: str,
    ) -> None:
        if isinstance(value, bool):
            raise CalculationValueError(
                f"O valor da {description} não pode ser booleano."
            )

        if not isinstance(value, (int, float)):
            raise CalculationValueError(
                f"O valor da {description} deve ser numérico."
            )
