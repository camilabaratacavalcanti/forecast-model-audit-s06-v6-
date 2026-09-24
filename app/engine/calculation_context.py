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
    - validar o tipo dos valores (ver app.domain.values):
        * parâmetros são sempre numéricos;
        * variáveis são numéricas, exceto as declaradas categóricas
          (value_type="categorical"), que aceitam texto;
        * o marcador de falha condicional "F" é aceito como valor de
          qualquer variável (resultado de uma rotina IF que falhou),
          sem conversão — consumi-lo em um cálculo é erro explícito.

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
from typing import Iterable, Mapping

from app.domain.values import (
    NumericValue,
    ScalarValue,
    is_conditional_failure,
    is_numeric,
)
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
        variables: Mapping[str, ScalarValue] | None = None,
        parameters: Mapping[str, NumericValue] | None = None,
        categorical_variable_ids: Iterable[str] | None = None,
    ):
        self._categorical_variable_ids: set[str] = set(
            categorical_variable_ids or ()
        )

        self._variables = dict(variables or {})
        self._parameters = dict(parameters or {})

        self._scoped_variables: dict[
            CalculationKey,
            ScalarValue,
        ] = {}

        self._scoped_parameters: dict[
            CalculationKey,
            NumericValue,
        ] = {}

        for variable_id, value in self._variables.items():
            self._validate_variable_value(variable_id, value)

        self._validate_values(
            self._parameters,
            "parâmetro",
        )

    # ========================================================
    # TIPOS DE VALOR
    # ========================================================

    def declare_categorical_variables(
        self,
        variable_ids: Iterable[str],
    ) -> None:
        """
        Declara variáveis cujo valor é texto (value_type
        "categorical"). Somente elas aceitam texto além do marcador
        de falha condicional.
        """

        self._categorical_variable_ids.update(variable_ids)

    def is_categorical_variable(self, variable_id: str) -> bool:
        return variable_id in self._categorical_variable_ids

    # ========================================================
    # API LEGADA — VARIÁVEIS
    # ========================================================

    def get_variable(
        self,
        variable_id: str,
    ) -> ScalarValue:
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
        value: ScalarValue,
    ) -> None:
        """
        Define ou atualiza o valor legado de uma variável.
        """

        self._validate_variable_value(variable_id, value)

        self._variables[variable_id] = value

    # ========================================================
    # API LEGADA — PARÂMETROS
    # ========================================================

    def get_parameter(
        self,
        parameter_id: str,
    ) -> NumericValue:
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
        value: NumericValue,
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
    ) -> ScalarValue:
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
        value: ScalarValue,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza um valor contextualizado de variável.
        """

        self._validate_variable_value(variable_id, value)

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
    ) -> NumericValue:
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
        value: NumericValue,
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
    ) -> ScalarValue:
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
        value: ScalarValue,
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
    ) -> NumericValue:
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
        value: NumericValue,
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

    def _validate_variable_value(
        self,
        variable_id: str,
        value: ScalarValue,
    ) -> None:
        """
        Número: sempre aceito. Texto: aceito para variáveis
        declaradas categóricas (não vazio) e, para qualquer variável,
        o marcador de falha condicional "F". Nenhum texto é convertido
        em número.
        """

        if isinstance(value, bool):
            raise CalculationValueError(
                f"O valor da variável {variable_id} não pode ser "
                "booleano."
            )

        if is_numeric(value):
            return

        if is_conditional_failure(value):
            return

        if isinstance(value, str):
            if variable_id not in self._categorical_variable_ids:
                raise CalculationValueError(
                    f"O valor da variável {variable_id} deve ser "
                    "numérico: a variável não é declarada categórica."
                )

            if not value.strip():
                raise CalculationValueError(
                    f"O valor categórico da variável {variable_id} "
                    "não pode ser vazio."
                )

            return

        raise CalculationValueError(
            f"O valor da variável {variable_id} deve ser numérico "
            "ou texto categórico."
        )

    @staticmethod
    def _validate_values(
        values: Mapping[str, NumericValue],
        value_type: str,
    ) -> None:
        for identifier, value in values.items():
            CalculationContext._validate_single_value(
                value,
                f"{value_type} {identifier}",
            )

    @staticmethod
    def _validate_single_value(
        value: NumericValue,
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
