"""
Transforma a expressão textual em uma AST Python e aplica a validação de
segurança: verifica quais elementos e operadores são permitidos,
impedindo construções arbitrárias de Python.

A DSL é uma allowlist fechada. Além de aritmética, comparação e IF
(`a if cond else b`), ela aceita:

    - referências espaciais explícitas `VAR@Lx` e `VAR@<grupo>` (ver
      app.engine.scoped_reference), convertidas antes do ast.parse;
    - chamadas às funções de ALLOWED_FUNCTIONS (hoje apenas `ln`),
      somente pelo nome, com aridade exata e argumentos posicionais;
    - constantes de texto, somente onde um texto pode ser um valor
      final ou um operando de comparação (ver `_validate_constants`);
    - `and`/`or`, somente entre condições (comparações ou outros
      `and`/`or`), dentro da condição de um IF.

Nada disso é executado com eval/exec: a AST validada é interpretada
nó a nó pelo ExpressionEvaluator.
"""

import ast
import re

from app.engine import scoped_reference
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


# Funções permitidas: nome -> aridade exata. Nenhuma outra chamada
# (builtins, atributos, lambdas, nomes arbitrários) passa pelo parser.
ALLOWED_FUNCTIONS = {
    "ln": 1,
}


ALLOWED_BOOLEAN_OPERATORS = {
    ast.And,
    ast.Or,
}


# Constantes de texto: apenas caracteres imprimíveis simples, sem
# aspas, barra invertida ou "@" (reservado a referências espaciais).
TEXT_CONSTANT_PATTERN = re.compile(r"[^\x00-\x1f\x7f'\"\\@]{1,64}")


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

        try:
            expression = self._normalize_scoped_references(
                expression
            )
        except scoped_reference.InvalidScopeReferenceError as exc:
            raise UnsafeExpressionError(str(exc)) from exc

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

            VAR11001@L4        (linha)
            VAR11001@L1_L3     (linha_grupo)
            PARAM11001@L4

        para identificadores Python seguros:

            VAR11001__L4
            VAR11001__L1_L3
            PARAM11001__L4

        O "@" nunca chega ao ast.parse (onde seria o operador
        MatMult): um "@" que não forma uma referência válida é
        rejeitado.
        """

        return scoped_reference.to_internal(expression)

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

            if isinstance(node, ast.Call):
                self._validate_call(node)
                continue

            if isinstance(node, ast.BoolOp):
                continue

            if isinstance(node, ast.boolop):
                if type(node) not in ALLOWED_BOOLEAN_OPERATORS:
                    raise UnsafeExpressionError(
                        "Operador booleano não permitido: "
                        f"{type(node).__name__}"
                    )
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

        parents = self._parent_map(tree)

        self._validate_boolean_operations(tree, parents)
        self._validate_constants(tree, parents)
        self._validate_names(tree)

    @staticmethod
    def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
        return {
            id(child): node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }

    @staticmethod
    def _validate_call(node: ast.Call) -> None:
        """
        Uma chamada só é aceita quando o alvo é um nome simples da
        allowlist, com aridade exata e apenas argumentos posicionais.
        Atributos (os.system), subscrições, lambdas, *args/**kwargs e
        nomes fora da allowlist (eval, exec, open, __import__, abs,
        max...) são rejeitados.
        """

        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError(
                "Chamada de função não permitida: somente funções da "
                f"allowlist {sorted(ALLOWED_FUNCTIONS)} pelo nome."
            )

        function_name = node.func.id

        if function_name not in ALLOWED_FUNCTIONS:
            raise UnsafeExpressionError(
                f"Função não permitida: {function_name}"
            )

        if node.keywords:
            raise UnsafeExpressionError(
                f"Argumentos nomeados não são permitidos em "
                f"{function_name}()."
            )

        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise UnsafeExpressionError(
                f"Argumentos expandidos não são permitidos em "
                f"{function_name}()."
            )

        arity = ALLOWED_FUNCTIONS[function_name]

        if len(node.args) != arity:
            raise UnsafeExpressionError(
                f"{function_name}() exige exatamente {arity} "
                f"argumento(s); recebeu {len(node.args)}."
            )

    @staticmethod
    def _is_condition(node: ast.AST) -> bool:
        return isinstance(node, (ast.Compare, ast.BoolOp))

    def _validate_boolean_operations(
        self,
        tree: ast.AST,
        parents: dict[int, ast.AST],
    ) -> None:
        """
        `and`/`or` combinam apenas condições (comparações ou outros
        `and`/`or`) e só podem aparecer como condição de um IF (ou
        dentro de outro `and`/`or` que seja essa condição). Assim um
        `and`/`or` nunca produz um valor numérico ou textual por
        acidente (`VAR1 or VAR2` como em Python é rejeitado).
        """

        for node in ast.walk(tree):

            if not isinstance(node, ast.BoolOp):
                continue

            for operand in node.values:
                if not self._is_condition(operand):
                    raise UnsafeExpressionError(
                        "Operandos de and/or devem ser comparações "
                        "ou outras expressões and/or."
                    )

            parent = parents.get(id(node))

            if isinstance(parent, ast.BoolOp):
                continue

            if isinstance(parent, ast.IfExp) and parent.test is node:
                continue

            raise UnsafeExpressionError(
                "and/or só é permitido na condição de um IF."
            )

    @staticmethod
    def _validate_constants(
        tree: ast.AST,
        parents: dict[int, ast.AST],
    ) -> None:
        """
        Constantes numéricas são permitidas em qualquer posição.

        Constantes de texto só são permitidas onde um texto pode ser
        um valor legítimo:

            - a expressão inteira ("F");
            - o ramo verdadeiro/falso de um IF (`VAR if c else "F"`);
            - um operando de comparação (`VAR == "ABERTO"`).

        Em qualquer outra posição (`VAR + '100'`, `ln("x")`, condição
        de IF) o texto é rejeitado já na análise.
        """

        for node in ast.walk(tree):

            if not isinstance(node, ast.Constant):
                continue

            if isinstance(node.value, bool):
                raise UnsafeExpressionError(
                    "Valores booleanos não são permitidos."
                )

            if isinstance(node.value, (int, float)):
                continue

            if not isinstance(node.value, str):
                raise UnsafeExpressionError(
                    "Somente constantes numéricas ou de texto são "
                    "permitidas."
                )

            if not TEXT_CONSTANT_PATTERN.fullmatch(node.value):
                raise UnsafeExpressionError(
                    f"Constante de texto inválida: {node.value!r}"
                )

            parent = parents.get(id(node))

            if isinstance(parent, ast.Expression):
                continue

            if isinstance(parent, ast.Compare):
                continue

            if isinstance(parent, ast.IfExp) and parent.test is not node:
                continue

            raise UnsafeExpressionError(
                "Constante de texto só é permitida como resultado, "
                "ramo de IF ou operando de comparação: "
                f"{node.value!r}"
            )

    @staticmethod
    def _validate_names(tree: ast.AST) -> None:
        """
        Permite identificadores VARxxxxx e PARAMxxxxx,
        com ou sem escopo contextualizado (linha ou grupo), e o nome
        de uma função da allowlist somente na posição de função de
        uma chamada já validada.
        """

        function_name_nodes = {
            id(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }

        for node in ast.walk(tree):

            if not isinstance(node, ast.Name):
                continue

            name = node.id

            if id(node) in function_name_nodes:
                continue

            if scoped_reference.is_valid_internal(name):
                continue

            if VARIABLE_PATTERN.fullmatch(name):
                continue

            if PARAMETER_PATTERN.fullmatch(name):
                continue

            raise UnsafeExpressionError(
                f"Identificador não permitido: {name}"
            )
