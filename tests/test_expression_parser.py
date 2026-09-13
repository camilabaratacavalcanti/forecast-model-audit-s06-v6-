"""
Verifica o parsing das expressões e, principalmente, o whitelist de segurança
da AST: operadores permitidos, elementos proibidos, nomes válidos etc.
"""

import ast

import pytest

from app.engine.exceptions import (
    InvalidExpressionError,
    UnsafeExpressionError,
)
from app.engine.expression_parser import ExpressionParser


@pytest.fixture
def parser():
    return ExpressionParser()


def test_parse_simple_expression(parser):
    tree = parser.parse(
        "VAR12001 + VAR12002"
    )

    assert isinstance(tree, ast.Expression)


def test_parse_expression_with_parameter(parser):
    tree = parser.parse(
        "VAR12001 * PARAM12001"
    )

    assert isinstance(tree, ast.Expression)


def test_parse_expression_with_parentheses(parser):
    tree = parser.parse(
        "(VAR12001 + VAR12002) / PARAM12001"
    )

    assert isinstance(tree, ast.Expression)


def test_parse_expression_with_power(parser):
    tree = parser.parse(
        "VAR12001 ** 2"
    )

    assert isinstance(tree, ast.Expression)


def test_parse_expression_with_modulo(parser):
    tree = parser.parse(
        "VAR12001 % 2"
    )

    assert isinstance(tree, ast.Expression)


def test_empty_expression_is_rejected(parser):
    with pytest.raises(InvalidExpressionError):
        parser.parse("")


def test_whitespace_expression_is_rejected(parser):
    with pytest.raises(InvalidExpressionError):
        parser.parse("   ")


def test_non_string_expression_is_rejected(parser):
    with pytest.raises(InvalidExpressionError):
        parser.parse(123)


def test_invalid_syntax_is_rejected(parser):
    with pytest.raises(InvalidExpressionError):
        parser.parse(
            "VAR12001 +"
        )


def test_unknown_identifier_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR12001 + ABC"
        )


def test_function_call_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "abs(VAR12001)"
        )


def test_import_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "__import__('os')"
        )


def test_attribute_access_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR12001.real"
        )


def test_boolean_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR12001 + True"
        )


def test_string_is_rejected(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR12001 + '100'"
        )


def test_parser_accepts_scoped_variable_reference(parser):
    tree = parser.parse(
        "VAR11001@L4 + 10"
    )

    assert tree is not None


def test_parser_accepts_scoped_parameter_reference(parser):
    tree = parser.parse(
        "VAR11001@L4 * PARAM11001@L4"
    )

    assert tree is not None


def test_parser_accepts_multiple_scoped_references(parser):
    tree = parser.parse(
        "(VAR11001@L4 + VAR11001@L5) / 2"
    )

    assert tree is not None


def test_parser_rejects_invalid_scoped_variable(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR11001@L8"
        )


def test_parser_rejects_invalid_scoped_identifier(parser):
    with pytest.raises(UnsafeExpressionError):
        parser.parse(
            "VAR11001@AREA"
        )
