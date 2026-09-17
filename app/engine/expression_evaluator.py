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
from app.engine.spatial_candidate_resolver import (
    get_spatial_candidates,
)


# scope_types com hierarquia espacial (linha -> linha_grupo -> planta)
# suportada por get_spatial_candidates. "área"/"global" não possuem
# projeção espacial (scope_value é sempre None) e continuam usando
# apenas o próprio scope, como antes da Decision E.
SPATIAL_SCOPE_TYPES = {"linha", "linha_grupo", "planta"}


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


COMPARE_OPERATORS = {
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
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

    @property
    def _default_containing_month_period_id(self) -> str | None:
        """
        O mês (`YYYY-MM`) que contém `default_period_id`, quando este
        é um period_id diário (`YYYY-MM-DD`). Convenção determinística
        de period_id: um mensal é sempre "YYYY-MM" (7 caracteres) e um
        diário é sempre "YYYY-MM-DD" (10 caracteres) — não há
        ambiguidade em derivar um a partir do outro por prefixo.

        Retorna None quando `default_period_id` não tem granularidade
        diária (mensal, anual ou ausente): nesses casos não existe um
        "mês que contém" um período que já é, ele mesmo, mensal, anual
        ou inexistente.
        """

        if self.default_period_id is None:
            return None

        if len(self.default_period_id) != len("YYYY-MM-DD"):
            return None

        return self.default_period_id[: len("YYYY-MM")]

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
            2. o mês que contém esse period_id (ex.: "2026-09") —
               cobre o caso de uma variável "mensal" (ex.: um input
               mensal como `fator_ajuste_lth`) referenciada dentro
               de uma equação diária, já que uma variável mensal é
               sempre armazenada com period_id=YYYY-MM,
               independentemente da frequência de quem a consome;
            3. o ForecastYear derivado dele (ex.: "2026") — cobre o
               caso de uma variável "anual" (ex.: um "_base"
               calculado ou um input anual) referenciada dentro de
               uma equação diária/mensal, já que uma variável anual
               é sempre armazenada com period_id=YYYY,
               independentemente da frequência de quem a consome;
            4. sem período (period_id=None) — preserva o
               comportamento anterior à introdução do período para
               qualquer chamador que ainda não segmenta seus inputs
               por período.

        Propaga o erro apenas se nenhuma das tentativas encontrar o
        valor.
        """

        candidate_period_ids = [self.default_period_id]

        containing_month = self._default_containing_month_period_id

        if containing_month is not None and containing_month != (
            self.default_period_id
        ):
            candidate_period_ids.append(containing_month)

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

    def _spatial_candidates_for_default_scope(
        self,
    ) -> list[tuple[str, str | None]]:
        """
        Decision E (spatial-first): candidatos espaciais para o
        escopo padrão (default_scope_type/default_scope_value) desta
        execução, do mais específico para o mais amplo.

        Para "linha"/"linha_grupo"/"planta", delega em
        `get_spatial_candidates` (Decision C + D). Para qualquer
        outro scope_type (ex.: "área", "global", que não têm
        hierarquia espacial), o único candidato continua sendo o
        próprio escopo — comportamento inalterado.
        """

        if self.default_scope_type in SPATIAL_SCOPE_TYPES:
            return get_spatial_candidates(
                self.default_scope_type,
                self.default_scope_value,
            )

        return [
            (self.default_scope_type, self.default_scope_value),
        ]

    def _get_variable_with_spatial_and_period_fallback(
        self,
        identifier: str,
    ) -> int | float:
        """
        Decision E: para cada candidato espacial do escopo padrão
        (do mais específico para o mais amplo), esgota o fallback
        temporal existente (`_get_variable_with_period_fallback`)
        antes de avançar para o próximo candidato espacial.

        Nunca o inverso (não itera períodos primeiro através de
        todos os scopes). `AmbiguousSpatialPrecedenceError`, se
        levantada por `get_spatial_candidates`, não é capturada aqui:
        é um erro estrutural, não uma ausência de valor, e deve
        propagar.
        """

        last_error: VariableNotFoundError | None = None

        for scope_type, scope_value in (
            self._spatial_candidates_for_default_scope()
        ):
            try:
                return self._get_variable_with_period_fallback(
                    identifier,
                    scope_type=scope_type,
                    scope_value=scope_value,
                )
            except VariableNotFoundError as exc:
                last_error = exc

        raise last_error

    def _get_parameter_with_spatial_and_period_fallback(
        self,
        identifier: str,
    ) -> int | float:
        """
        Equivalente a
        `_get_variable_with_spatial_and_period_fallback`, mas para
        Parameters: para cada candidato espacial, esgota
        `_get_parameter_with_period_fallback` antes de avançar.
        """

        last_error: ParameterNotFoundError | None = None

        for scope_type, scope_value in (
            self._spatial_candidates_for_default_scope()
        ):
            try:
                return self._get_parameter_with_period_fallback(
                    identifier,
                    scope_type=scope_type,
                    scope_value=scope_value,
                )
            except ParameterNotFoundError as exc:
                last_error = exc

        raise last_error

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

        if isinstance(node, ast.Compare):

            left = self._evaluate_node(node.left)

            for op, comparator in zip(
                node.ops, node.comparators
            ):
                right = self._evaluate_node(comparator)

                operation = COMPARE_OPERATORS.get(type(op))

                if operation is None:
                    raise EvaluationError(
                        "Operador de comparação não suportado: "
                        f"{type(op).__name__}"
                    )

                if not operation(left, right):
                    return False

                left = right

            return True

        if isinstance(node, ast.IfExp):

            condition = self._evaluate_node(node.test)

            if condition:
                return self._evaluate_node(node.body)

            return self._evaluate_node(node.orelse)

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
                resolve = (
                    self
                    ._get_variable_with_spatial_and_period_fallback
                )

                try:
                    return resolve(name)
                except VariableNotFoundError:
                    pass

            return self.calculation_context.get_variable(
                name,
            )

        if name.startswith("PARAM"):

            if self.default_scope_type and self.default_scope_value:
                resolve = (
                    self
                    ._get_parameter_with_spatial_and_period_fallback
                )

                try:
                    return resolve(name)
                except ParameterNotFoundError:
                    pass

            return self.calculation_context.get_parameter(
                name,
            )

        raise EvaluationError(
            f"Identificador não suportado: {name}"
        )
