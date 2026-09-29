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
          (value_type="categorico"), que aceitam texto;
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

Resultado canônico (Etapa 3.3A): cada valor contextualizado de variável
é armazenado como `app.domain.results.Result` (value, state, detail) na
mesma chave de antes (CalculationKey). A API por valor
(`get_variable_value`/`set_variable_value`) continua funcionando: ela
lê `Result.value` e grava `Result(value)` — a conversão acontece só em
`as_result`. `get_variable_result`/`set_variable_result` dão acesso ao
contrato completo. Parâmetros continuam numéricos (não são resultados).
"""

from dataclasses import dataclass
from typing import Iterable, Mapping

from app.domain.results import Result, as_result, check_value_domain, scalar_of
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

        # Armazenamento canônico dos valores contextualizados de variáveis.
        self._scoped_results: dict[
            CalculationKey,
            Result,
        ] = {}

        # allowed_values por variável (domínio do valor categórico),
        # conhecido quando a definição é declarada ao contexto.
        self._value_domains: dict[str, tuple[str, ...]] = {}

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
        "categorico"). Somente elas aceitam texto além do marcador
        de falha condicional.
        """

        self._categorical_variable_ids.update(variable_ids)

    def is_categorical_variable(self, variable_id: str) -> bool:
        return variable_id in self._categorical_variable_ids

    def declare_variable_definitions(self, definitions: Iterable) -> None:
        """
        Declara VariableDefinitions ao contexto: as categóricas passam a
        aceitar texto e, havendo `allowed_values`, todo valor gravado
        para a variável é validado contra esse domínio
        (`check_value_domain`, validação única e centralizada).
        """

        for definition in definitions:
            if definition.is_categorical:
                self._categorical_variable_ids.add(
                    definition.variable_definition_id
                )

            if definition.allowed_values is not None:
                self._value_domains[definition.variable_definition_id] = tuple(
                    definition.allowed_values
                )

    # ========================================================
    # COMPATIBILIDADE — mapa escalar derivado do armazenamento canônico
    # ========================================================

    @property
    def _scoped_variables(self) -> dict[CalculationKey, ScalarValue]:
        """
        Visão escalar (somente leitura, cópia) do armazenamento canônico,
        para código que ainda inspeciona o mapa legado chave -> valor.
        """

        return {
            key: result.value
            for key, result in self._scoped_results.items()
        }

    @_scoped_variables.setter
    def _scoped_variables(self, values: Mapping[CalculationKey, ScalarValue]) -> None:
        results = {}

        for key, value in values.items():
            self._validate_variable_value(key.entity_id, value)
            results[key] = as_result(value)

        self._scoped_results = results

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
        Retorna o valor contextualizado de uma variável
        (`Result.value` do resultado canônico).
        """

        # Etapa 3.3B: um resultado com estado e sem valor não cabe na
        # resposta escalar -> STATEFUL_RESULT_ON_SCALAR_API (nunca None).
        return scalar_of(
            self.get_variable_result(
                variable_id, scope_type, scope_value, period_id
            ),
            f"{variable_id} ({scope_type}/{scope_value}, period_id={period_id})",
        )

    def set_variable_value(
        self,
        variable_id: str,
        value: ScalarValue,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza um valor contextualizado de variável
        (grava o contrato mínimo `Result(value)`).
        """

        self.set_variable_result(
            variable_id, value, scope_type, scope_value, period_id
        )

    def get_variable_result(
        self,
        variable_id: str,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> Result:
        """
        Retorna o resultado canônico (value, state, detail).
        """

        key = CalculationKey(
            entity_id=variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        if key not in self._scoped_results:
            raise VariableNotFoundError(
                "Valor contextualizado da variável não encontrado: "
                f"{variable_id}, "
                f"scope_type={scope_type}, "
                f"scope_value={scope_value}, "
                f"period_id={period_id}"
            )

        return self._scoped_results[key]

    def set_variable_result(
        self,
        variable_id: str,
        result,
        scope_type: str | None = None,
        scope_value: str | None = None,
        period_id: str | None = None,
    ) -> None:
        """
        Define ou atualiza o resultado canônico. Aceita `Result` ou o
        valor legado (convertido por `as_result`). O valor é validado
        como antes e, se a definição declarou `allowed_values`, contra
        esse domínio. state e detail são preservados sem alteração.
        """

        # Validação existente primeiro (mesmos erros de antes para o
        # valor legado); só então o valor vira o contrato canônico.
        value = result.value if isinstance(result, Result) else result

        # Etapa 3.3B: estado sem valor (contrato 2.2 §13) não passa pela
        # validação de valor nem de domínio — não há valor.
        if not (isinstance(result, Result) and value is None):
            self._validate_variable_value(variable_id, value)
            check_value_domain(
                variable_id, value, self._value_domains.get(variable_id)
            )

        result = as_result(result)

        key = CalculationKey(
            entity_id=variable_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        self._scoped_results[key] = result

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
