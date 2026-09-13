"""
É o orquestrador principal do cálculo.
Recebe uma equação, utiliza o parser para transformá-la em AST,
o contexto para resolver valores e o evaluator para calcular o resultado.
É a porta de entrada da execução de uma equação.
"""

import re

from app.domain.equations.models import Equation

from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    EquationEvaluationError,
    EvaluationError,
    VariableNotFoundError,
    ParameterNotFoundError,
)
from app.engine.expression_evaluator import ExpressionEvaluator
from app.engine.expression_parser import ExpressionParser


class EquationEngine:
    """
    Núcleo responsável pela execução de uma equação.

    Nesta primeira versão, o Engine recebe diretamente uma Equation.
    A resolução de versão publicada e regras de workflow serão
    incorporadas posteriormente.
    """

    def __init__(self):
        self.parser = ExpressionParser()

    def calculate(
        self,
        equation: Equation,
        calculation_context: CalculationContext,
    ) -> int | float:
        """
        Executa uma equação utilizando os valores fornecidos
        no CalculationContext.

        Erros de avaliação são enriquecidos com o contexto
        da Equation antes de serem propagados.
        """

        tree = self.parser.parse(
            equation.expression
        )

        evaluator = ExpressionEvaluator(
            calculation_context
        )

        try:
            return evaluator.evaluate(tree)

        except (VariableNotFoundError, ParameterNotFoundError):
            raise

        except EvaluationError as exc:
            raise EquationEvaluationError(
                equation_id=equation.equation_id,
                target_variable_id=equation.target_variable_id,
                expression=equation.expression,
                original_error=exc,
            ) from exc

    def calculate_instance(
        self,
        instance,
        definition,
        calculation_context: CalculationContext,
    ) -> int | float:
        """
        Executa uma EquationInstance utilizando a expressão
        pertencente à EquationDefinition.

        A EquationInstance fornece o contexto concreto.
        A EquationDefinition fornece a expressão matemática.

        A expressão é contextualizada para o escopo da instance
        antes de ser enviada ao parser.
        """

        expression = self._contextualize_expression(
            definition.expression,
            instance,
        )

        tree = self.parser.parse(
            expression
        )

        # Referências sem escopo explícito na expressão (ex.:
        # "PARAM11003" ou "VAR11020") são resolvidas, em primeiro
        # lugar, no próprio escopo da EquationInstance em execução.
        # Referências explicitamente escopadas (ex.: "VAR11001@L2")
        # não são afetadas: já foram tratadas por
        # _contextualize_expression/normalizadas pelo parser.
        evaluator = ExpressionEvaluator(
            calculation_context,
            default_scope_type=instance.scope_type,
            default_scope_value=instance.scope_value,
        )

        try:
            return evaluator.evaluate(tree)

        except (
            VariableNotFoundError,
            ParameterNotFoundError,
        ):
            raise

        except EvaluationError as exc:
            raise EquationEvaluationError(
                equation_id=definition.equation_definition_id,
                target_variable_id=definition.target_variable_id,
                expression=expression,
                original_error=exc,
            ) from exc

    @staticmethod
    def _contextualize_expression(
        expression: str,
        instance,
    ) -> str:
        """
        Ajusta referências contextualizadas da expressão para o
        escopo concreto da EquationInstance.

        Exemplo:

            VAR10001@L4

        para uma instance L5 torna-se:

            VAR10001@L5
        """

        if (
            instance.scope_type != "linha"
            or not instance.scope_value
        ):
            return expression

        return re.sub(
            r"\b(VAR\d{5}|PARAM\d{5})@L[1-7]\b",
            lambda match: (
                f"{match.group(1)}@{instance.scope_value}"
            ),
            expression,
        )
