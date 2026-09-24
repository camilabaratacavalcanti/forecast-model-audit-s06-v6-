"""
Executa a AST já validada pelo parser. Resolve VAR... e PARAM... no
CalculationContext e aplica as operações matemáticas permitidas.
Também trata erros de avaliação.

Regras de tipo (valores numéricos ou categóricos, ver app.domain.values):

    aritmética / unário / ln   somente números
    <, <=, >, >=               somente número com número
    ==, !=                     número com número ou texto com texto
                               (número com texto é erro, nunca False)
    and / or                   somente condições (bool), com curto-
                               circuito: `a and b` avalia b só se a é
                               verdadeira; `a or b` só se a é falsa;
                               precedência de Python (and antes de or)
    condição de IF             bool, ou número (legado: != 0)
    resultado final            número ou texto (bool é erro)

Falha condicional ("F"): consumir o marcador em qualquer operação
levanta ConditionalFailureError; a única leitura permitida é `== "F"`
/ `!= "F"` contra o literal "F" (verdadeiro/falso conforme o valor
seja a falha; um número nunca é a falha). Um ramo de IF que devolve
"F" apenas o repassa.
"""

import ast
import math
import operator

from app.domain.values import (
    CONDITIONAL_FAILURE,
    ScalarValue,
    is_conditional_failure,
    is_numeric,
)
from app.engine import scoped_reference
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    ConditionalFailureError,
    DivisionByZeroError,
    EvaluationError,
    ExpressionTypeError,
    MathDomainError,
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


EQUALITY_OPERATORS = {ast.Eq, ast.NotEq}


def _natural_log(value: int | float) -> float:
    if value <= 0:
        raise MathDomainError("ln", value)

    return math.log(value)


FUNCTIONS = {
    "ln": _natural_log,
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
    ) -> ScalarValue:
        """
        Avalia a AST utilizando os valores do CalculationContext.

        O resultado é um número ou um texto (categórico ou "F"); uma
        expressão cujo resultado final é uma condição (bool) é um
        erro de tipo, não um número 0/1.
        """

        try:
            result = self._evaluate_node(tree.body)

            if isinstance(result, bool):
                raise ExpressionTypeError(
                    "O resultado da expressão é uma condição "
                    "(verdadeiro/falso), não um valor."
                )

            return result

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

    @staticmethod
    def _require_numeric(value, operation: str) -> int | float:
        """
        Garante que `value` seja um operando numérico. O marcador "F"
        nunca é convertido: consumi-lo é uma falha explícita.
        """

        if is_conditional_failure(value):
            raise ConditionalFailureError(
                f"Operação '{operation}' sobre falha condicional "
                f"({CONDITIONAL_FAILURE!r})."
            )

        if not is_numeric(value):
            raise ExpressionTypeError(
                f"Operação '{operation}' exige valor numérico; "
                f"recebeu {value!r}."
            )

        return value

    @staticmethod
    def _require_condition(value, operation: str) -> bool:
        if isinstance(value, bool):
            return value

        if is_conditional_failure(value):
            raise ConditionalFailureError(
                f"Operação '{operation}' sobre falha condicional "
                f"({CONDITIONAL_FAILURE!r})."
            )

        raise ExpressionTypeError(
            f"Operandos de '{operation}' devem ser condições; "
            f"recebeu {value!r}."
        )

    def _compare(
        self,
        op: ast.cmpop,
        left,
        right,
        is_failure_check: bool = False,
    ) -> bool:
        operation = COMPARE_OPERATORS.get(type(op))

        if operation is None:
            raise EvaluationError(
                "Operador de comparação não suportado: "
                f"{type(op).__name__}"
            )

        symbol = type(op).__name__

        if type(op) in EQUALITY_OPERATORS:
            # Detecção explícita da falha: comparar com o literal "F"
            # (`x == "F"`) é verdadeiro somente quando x é a falha; um
            # número nunca é a falha.
            if is_failure_check:
                return operation(left, right)

            # Qualquer outra igualdade envolvendo uma falha
            # (`x == 0`, `x == "ABERTO"`) consome a falha: erro, nunca
            # um False silencioso.
            if is_conditional_failure(left) or is_conditional_failure(
                right
            ):
                raise ConditionalFailureError(
                    f"Comparação '{symbol}' sobre falha condicional "
                    f"({CONDITIONAL_FAILURE!r}); use == \"F\" para "
                    "detectá-la."
                )

            if isinstance(left, str) and isinstance(right, str):
                return operation(left, right)

            if is_numeric(left) and is_numeric(right):
                return operation(left, right)

            # Número x texto categórico nunca é silenciosamente
            # "diferente": é um erro de tipo.
            raise ExpressionTypeError(
                f"Comparação '{symbol}' entre número e texto: "
                f"{left!r} e {right!r}."
            )

        self._require_numeric(left, symbol)
        self._require_numeric(right, symbol)

        return operation(left, right)

    def _evaluate_node(
        self,
        node: ast.AST,
    ) -> ScalarValue | bool:

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self._resolve_name(node.id)

        if isinstance(node, ast.BinOp):

            operation = BINARY_OPERATORS.get(
                type(node.op)
            )

            if operation is None:
                raise EvaluationError(
                    "Operador não suportado: "
                    f"{type(node.op).__name__}"
                )

            symbol = BINARY_OPERATOR_SYMBOLS.get(
                type(node.op),
                type(node.op).__name__,
            )

            left = self._require_numeric(
                self._evaluate_node(node.left), symbol
            )
            right = self._require_numeric(
                self._evaluate_node(node.right), symbol
            )

            try:
                return operation(left, right)

            except ZeroDivisionError as exc:
                raise DivisionByZeroError(
                    operation=symbol,
                    left_value=left,
                    right_value=right,
                ) from exc

        if isinstance(node, ast.UnaryOp):

            operation = UNARY_OPERATORS.get(
                type(node.op)
            )

            if operation is None:
                raise EvaluationError(
                    "Operador unário não suportado: "
                    f"{type(node.op).__name__}"
                )

            value = self._require_numeric(
                self._evaluate_node(node.operand),
                type(node.op).__name__,
            )

            return operation(value)

        if isinstance(node, ast.Call):

            function_name = node.func.id
            function = FUNCTIONS.get(function_name)

            if function is None:
                raise EvaluationError(
                    f"Função não suportada: {function_name}"
                )

            arguments = [
                self._require_numeric(
                    self._evaluate_node(argument), function_name
                )
                for argument in node.args
            ]

            return function(*arguments)

        if isinstance(node, ast.Compare):

            left_node = node.left
            left = self._evaluate_node(left_node)

            for op, comparator in zip(
                node.ops, node.comparators
            ):
                right = self._evaluate_node(comparator)

                is_failure_check = any(
                    isinstance(operand, ast.Constant)
                    and is_conditional_failure(operand.value)
                    for operand in (left_node, comparator)
                )

                if not self._compare(
                    op, left, right, is_failure_check
                ):
                    return False

                left_node, left = comparator, right

            return True

        if isinstance(node, ast.BoolOp):

            is_and = isinstance(node.op, ast.And)
            symbol = "and" if is_and else "or"

            for operand in node.values:
                value = self._require_condition(
                    self._evaluate_node(operand), symbol
                )

                if is_and and not value:
                    return False

                if not is_and and value:
                    return True

            return is_and

        if isinstance(node, ast.IfExp):

            condition = self._evaluate_node(node.test)

            if not isinstance(condition, bool):
                condition = self._require_numeric(
                    condition, "if"
                )

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

        Um grupo explícito (VAR11001@L1_L3, internamente
        VAR11001__L1_L3) é resolvido como scope_type = linha_grupo,
        scope_value = L1_L3. Uma referência explícita usa apenas o
        próprio escopo (com fallback somente temporal): nunca é
        projetada para outro escopo.

        ou:

            parameter_id = PARAM11001
            scope_type = linha
            scope_value = L4
        """

        identifier, scope_type, scope_value = (
            scoped_reference.split_internal(name)
        )

        if scope_type is not None:

            if identifier.startswith("VAR"):

                return self._get_variable_with_period_fallback(
                    identifier,
                    scope_type=scope_type,
                    scope_value=scope_value,
                )

            if identifier.startswith("PARAM"):

                return self._get_parameter_with_period_fallback(
                    identifier,
                    scope_type=scope_type,
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
