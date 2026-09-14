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
        default_period_id: str | None = None,
    ):
        self.calculation_context = calculation_context

        # Escopo da EquationInstance em execução, usado para resolver
        # referências sem escopo explícito (ex.: "PARAM11003" dentro de
        # uma instance @L4) no mesmo escopo da própria instance, antes
        # de recorrer à API legada (não escopada).
        self.default_scope_type = default_scope_type
        self.default_scope_value = default_scope_value

        # Período corrente da execução (ex.: "2026-09-14", "2026-09",
        # "2026"), usado para resolver o valor de qualquer referência
        # (explícita ou não) no período em que o cálculo está sendo
        # feito. Não introduz nova sintaxe: "@Lx" continua controlando
        # apenas o espaço, o período vem sempre do contexto.
        self.default_period_id = default_period_id

    @property
    def _default_parameter_period_id(self) -> str | None:
        """
        Um Parameter é constante dentro do ForecastYear (não tem
        frequência própria): sua identidade temporal é o ano, não o
        período diário/mensal/anual da equação em execução. Como todas
        as convenções de period_id começam por "YYYY", o ano é sempre
        os 4 primeiros caracteres do period_id corrente.
        """

        if not self.default_period_id:
            return None

        return self.default_period_id[:4]

    def _get_variable_with_period_fallback(
        self,
        identifier: str,
        scope_type: str,
        scope_value: str | None,
    ) -> int | float:
        """
        Resolve um valor de variável em um escopo concreto,
        priorizando o valor do período corrente da execução.

        Quando um period_id está ativo mas o valor não foi
        armazenado com esse period_id exato, tenta, nesta ordem:

            1. o period_id corrente da execução (ex.: "2026-09-14");
            2. o ForecastYear derivado dele (ex.: "2026") — cobre o
               caso de uma variável "anual" (ex.: um "_base"
               calculado ou um input anual) referenciada dentro de
               uma equação diária/mensal, já que uma variável anual
               é sempre armazenada com period_id=YYYY,
               independentemente da frequência de quem a consome;
            3. sem período (period_id=None) — preserva o
               comportamento anterior à introdução do período para
               qualquer chamador que ainda não segmenta seus inputs
               por período.

        Propaga o erro apenas se nenhuma das três tentativas
        encontrar o valor.
        """

        candidate_period_ids = [self.default_period_id]

        forecast_year = self._default_parameter_period_id

        if forecast_year is not None and forecast_year != (
            self.default_period_id
        ):
            candidate_period_ids.append(forecast_year)

        if self.default_period_id is not None:
            candidate_period_ids.append(None)

        last_error: VariableNotFoundError | None = None

        for period_id in candidate_period_ids:
            try:
                return self.calculation_context.get_variable_value(
                    identifier,
                    scope_type=scope_type,
                    scope_value=scope_value,
                    period_id=period_id,
                )
            except VariableNotFoundError as exc:
                last_error = exc

        raise last_error

    def _get_parameter_with_period_fallback(
        self,
        identifier: str,
        scope_type: str,
        scope_value: str | None,
    ) -> int | float:
        """
        Equivalente a `_get_variable_with_period_fallback`, mas para
        Parameters: usa `_default_parameter_period_id` (o ForecastYear,
        não o period_id diário/mensal/anual da equação) como período
        preferencial, com fallback para o valor sem período.
        """

        parameter_period_id = self._default_parameter_period_id

        try:
            return self.calculation_context.get_parameter_value(
                identifier,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=parameter_period_id,
            )
        except ParameterNotFoundError:
            if parameter_period_id is None:
                raise

            return self.calculation_context.get_parameter_value(
                identifier,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=None,
            )

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

                return self._get_variable_with_period_fallback(
                    identifier,
                    scope_type="linha",
                    scope_value=scope_value,
                )

            if identifier.startswith("PARAM"):

                return self._get_parameter_with_period_fallback(
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
                    return self._get_variable_with_period_fallback(
                        name,
                        scope_type=self.default_scope_type,
                        scope_value=self.default_scope_value,
                    )
                except VariableNotFoundError:
                    pass

            return self.calculation_context.get_variable(
                name,
            )

        if name.startswith("PARAM"):

            if self.default_scope_type and self.default_scope_value:
                try:
                    return self._get_parameter_with_period_fallback(
                        name,
                        scope_type=self.default_scope_type,
                        scope_value=self.default_scope_value,
                    )
                except ParameterNotFoundError:
                    pass

            return self.calculation_context.get_parameter(
                name,
            )

        raise EvaluationError(
            f"Identificador não suportado: {name}"
        )
