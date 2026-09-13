"""
Executa a AST já validada pelo parser. Resolve VAR... e PARAM... no
CalculationContext e aplica as operações matemáticas permitidas.
Também trata erros de avaliação.
"""

import ast
import operator

from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    DivisionByZeroError,
    EvaluationError,
    ParameterNotFoundError,
    VariableNotFoundError,
)


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


BINARY_OPERATOR_SYMBOLS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
    ast.Mod: "%",
}


UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class ExpressionEvaluator:
    """
    Avalia uma expressão matemática previamente validada.
    """

    def __init__(
        self,
        calculation_context: CalculationContext,
        default_scope_type: str | None = None,
        default_scope_value: str | None = None,
    ):
        self.calculation_context = calculation_context

        # Escopo da EquationInstance em execução, usado para resolver
        # referências sem escopo explícito (ex.: "PARAM11003" dentro de
        # uma instance @L4) no mesmo escopo da própria instance, antes
        # de recorrer à API legada (não escopada).
        self.default_scope_type = default_scope_type
        self.default_scope_value = default_scope_value

    def evaluate(
        self,
        tree: ast.Expression,
    ) -> int | float:
        """
        Avalia a AST utilizando os valores do CalculationContext.
        """

        try:
            return self._evaluate_node(tree.body)

        except EvaluationError:
            raise

        except VariableNotFoundError:
            raise

        except ParameterNotFoundError:
            raise

        except (OverflowError, ValueError) as exc:
            raise EvaluationError(
                "Resultado matemático inválido."
            ) from exc

        except Exception as exc:
            raise EvaluationError(
                "Erro durante a avaliação da expressão."
            ) from exc

    def _evaluate_node(
        self,
        node: ast.AST,
    ) -> int | float:

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self._resolve_name(node.id)

        if isinstance(node, ast.BinOp):

            left = self._evaluate_node(node.left)
            right = self._evaluate_node(node.right)

            operation = BINARY_OPERATORS.get(
                type(node.op)
            )

            if operation is None:
                raise EvaluationError(
                    "Operador não suportado: "
                    f"{type(node.op).__name__}"
                )

            try:
                return operation(left, right)

            except ZeroDivisionError as exc:
                symbol = BINARY_OPERATOR_SYMBOLS.get(
                    type(node.op),
                    type(node.op).__name__,
                )

                raise DivisionByZeroError(
                    operation=symbol,
                    left_value=left,
                    right_value=right,
                ) from exc

        if isinstance(node, ast.UnaryOp):

            value = self._evaluate_node(node.operand)

            operation = UNARY_OPERATORS.get(
                type(node.op)
            )

            if operation is None:
                raise EvaluationError(
                    "Operador unário não suportado: "
                    f"{type(node.op).__name__}"
                )

            return operation(value)

        raise EvaluationError(
            "Nó não suportado: "
            f"{type(node).__name__}"
        )

    def _resolve_name(
        self,
        name: str,
    ) -> int | float:
        """
        Resolve uma referência de variável ou parâmetro.

        Referências sem escopo:

            VAR11001
            PARAM11001

        são resolvidas utilizando as APIs legadas do
        CalculationContext.

        Referências contextualizadas são representadas
        internamente pelo parser como:

            VAR11001__L4
            PARAM11001__L4

        e são resolvidas como:

            variable_id = VAR11001
            scope_type = linha
            scope_value = L4

        ou:

            parameter_id = PARAM11001
            scope_type = linha
            scope_value = L4
        """

        if "__L" in name:

            identifier, scope = name.split(
                "__L",
                maxsplit=1,
            )

            scope_value = f"L{scope}"

            if identifier.startswith("VAR"):

                return self.calculation_context.get_variable_value(
                    identifier,
                    scope_type="linha",
                    scope_value=scope_value,
                )

            if identifier.startswith("PARAM"):

                return self.calculation_context.get_parameter_value(
                    identifier,
                    scope_type="linha",
                    scope_value=scope_value,
                )

            raise EvaluationError(
                f"Identificador contextualizado não suportado: {name}"
            )

        if name.startswith("VAR"):

            if self.default_scope_type and self.default_scope_value:
                try:
                    return (
                        self.calculation_context
                        .get_variable_value(
                            name,
                            scope_type=self.default_scope_type,
                            scope_value=self.default_scope_value,
                        )
                    )
                except VariableNotFoundError:
                    pass

            return self.calculation_context.get_variable(
                name,
            )

        if name.startswith("PARAM"):

            if self.default_scope_type and self.default_scope_value:
                try:
                    return (
                        self.calculation_context
                        .get_parameter_value(
                            name,
                            scope_type=self.default_scope_type,
                            scope_value=self.default_scope_value,
                        )
                    )
                except ParameterNotFoundError:
                    pass

            return self.calculation_context.get_parameter(
                name,
            )

        raise EvaluationError(
            f"Identificador não suportado: {name}"
        )
