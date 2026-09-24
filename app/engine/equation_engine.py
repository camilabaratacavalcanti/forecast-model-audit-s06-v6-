"""
É o orquestrador principal do cálculo.
Recebe uma equação, utiliza o parser para transformá-la em AST,
o contexto para resolver valores e o evaluator para calcular o resultado.
É a porta de entrada da execução de uma equação.
"""

from app.domain.equations.models import Equation
from app.domain.values import ScalarValue

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
    ) -> ScalarValue:
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
        period_id: str | None = None,
    ) -> ScalarValue:
        """
        Executa uma EquationInstance utilizando a expressão
        pertencente à EquationDefinition.

        A EquationInstance fornece o contexto concreto.
        A EquationDefinition fornece a expressão matemática.

        A expressão da Definition é enviada ao parser exatamente
        como declarada — nenhuma reescrita textual é aplicada aqui.
        A contextualização acontece inteiramente na resolução de
        cada referência (ver ExpressionEvaluator):

            - uma referência sem escopo explícito (ex.: "PARAM11003")
              é resolvida no escopo da própria EquationInstance;
            - uma referência explicitamente escopada (ex.:
              "VAR11001@L2") é resolvida exatamente naquele escopo,
              independentemente do escopo da instance em execução.

        Essa é a única regra de contextualização da plataforma; não
        há uma segunda transformação (textual) sobrepondo-a.

        `period_id`, quando informado, identifica o período temporal
        corrente da execução (ex.: "2026-09-14", "2026-09" ou "2026")
        e é propagado ao ExpressionEvaluator como período padrão para
        resolver VAR/PARAM. Omitido, o comportamento é o mesmo de
        antes (sem dimensão temporal).
        """

        expression = definition.expression

        tree = self.parser.parse(
            expression
        )

        evaluator = ExpressionEvaluator(
            calculation_context,
            default_scope_type=instance.scope_type,
            default_scope_value=instance.scope_value,
            default_period_id=period_id,
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
