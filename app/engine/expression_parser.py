"""
Transforma a expressão textual em uma AST Python e aplica a validação de
segurança: verifica quais elementos e operadores são permitidos,
impedindo construções arbitrárias de Python.
"""

import ast
import re

from app.engine.exceptions import (
    InvalidExpressionError,
    UnsafeExpressionError,
)


VARIABLE_PATTERN = re.compile(
    r"VAR\d{5}"
)

PARAMETER_PATTERN = re.compile(
    r"PARAM\d{5}"
)

SCOPED_VARIABLE_PATTERN = re.compile(
    r"VAR\d{5}__L[1-7]"
)

SCOPED_PARAMETER_PATTERN = re.compile(
    r"PARAM\d{5}__L[1-7]"
)


ALLOWED_BINARY_OPERATORS = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
}


ALLOWED_UNARY_OPERATORS = {
    ast.UAdd,
    ast.USub,
}


ALLOWED_COMPARE_OPERATORS = {
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
}


class ExpressionParser:
    """
    Responsável por analisar e validar expressões
    matemáticas utilizadas pelo Equation Engine.
    """

    def parse(self, expression: str) -> ast.Expression:
        """
        Converte uma expressão textual em uma AST validada.
        """

        if not isinstance(expression, str):
            raise InvalidExpressionError(
                "A expressão deve ser uma string."
            )

        expression = expression.strip()

        if not expression:
            raise InvalidExpressionError(
                "A expressão não pode ser vazia."
            )

        expression = self._normalize_scoped_references(
            expression
        )

        try:
            tree = ast.parse(
                expression,
                mode="eval",
            )
        except SyntaxError as exc:
            raise InvalidExpressionError(
                f"Expressão inválida: {expression}"
            ) from exc

        self._validate_ast(tree)

        return tree

    @staticmethod
    def _normalize_scoped_references(
        expression: str,
    ) -> str:
        """
        Converte referências contextualizadas da forma:

            VAR11001@L4
            PARAM11001@L4

        para identificadores Python seguros:

            VAR11001__L4
            PARAM11001__L4
        """

        expression = re.sub(
            r"\b(VAR\d{5}|PARAM\d{5})@L([1-7])\b",
            r"\1__L\2",
            expression,
        )

        return expression

    def _validate_ast(self, tree: ast.AST) -> None:
        """
        Permite somente elementos matemáticos controlados.
        """

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.Expression,
                    ast.Constant,
                    ast.Name,
                    ast.BinOp,
                    ast.UnaryOp,
                    ast.Load,
                    ast.IfExp,
                    ast.Compare,
                ),
            ):
                continue

            if isinstance(node, ast.operator):
                if type(node) not in ALLOWED_BINARY_OPERATORS:
                    raise UnsafeExpressionError(
                        "Operador não permitido: "
                        f"{type(node).__name__}"
                    )
                continue

            if isinstance(node, ast.unaryop):
                if type(node) not in ALLOWED_UNARY_OPERATORS:
                    raise UnsafeExpressionError(
                        "Operador unário não permitido: "
                        f"{type(node).__name__}"
                    )
                continue

            if isinstance(node, ast.cmpop):
                if type(node) not in ALLOWED_COMPARE_OPERATORS:
                    raise UnsafeExpressionError(
                        "Operador de comparação não permitido: "
                        f"{type(node).__name__}"
                    )
                continue

            raise UnsafeExpressionError(
                "Elemento não permitido na expressão: "
                f"{type(node).__name__}"
            )

        self._validate_constants(tree)
        self._validate_names(tree)

    @staticmethod
    def _validate_constants(tree: ast.AST) -> None:
        """
        Permite somente constantes numéricas.
        """

        for node in ast.walk(tree):

            if not isinstance(node, ast.Constant):
                continue

            if isinstance(node.value, bool):
                raise UnsafeExpressionError(
                    "Valores booleanos não são permitidos."
                )

            if not isinstance(node.value, (int, float)):
                raise UnsafeExpressionError(
                    "Somente constantes numéricas são permitidas."
                )

    @staticmethod
    def _validate_names(tree: ast.AST) -> None:
        """
        Permite identificadores VARxxxxx e PARAMxxxxx,
        com ou sem escopo contextualizado.
        """

        for node in ast.walk(tree):

            if not isinstance(node, ast.Name):
                continue

            name = node.id

            if SCOPED_VARIABLE_PATTERN.fullmatch(name):
                continue

            if SCOPED_PARAMETER_PATTERN.fullmatch(name):
                continue

            if VARIABLE_PATTERN.fullmatch(name):
                continue

            if PARAMETER_PATTERN.fullmatch(name):
                continue

            raise UnsafeExpressionError(
                f"Identificador não permitido: {name}"
            )
