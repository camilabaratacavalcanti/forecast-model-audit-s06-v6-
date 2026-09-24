"""
Sintaxe das referências espaciais explícitas da DSL.

Fonte única de verdade para o sufixo `@<escopo>` de uma referência:

    VAR11001@L4       -> linha        / L4
    VAR11001@L1_L3    -> linha_grupo  / L1_L3

Os escopos aceitos vêm do próprio ScopeResolver (linhas individuais e
grupos declarados em `GROUP_MEMBERS`), para que a DSL nunca aceite um
escopo que o restante da plataforma não saiba materializar.

Representações:

    domínio   VAR11001@L1_L3     (seeds, DependencyExtractor, grafo)
    interna   VAR11001__L1_L3    (identificador Python seguro no AST)

A conversão domínio -> interna acontece antes do `ast.parse`, então o
`@` nunca chega ao AST como operador (MatMult).
"""

import re

from app.engine.scope_resolver import ScopeResolver


LINE_SCOPE_TYPE = "linha"
LINE_GROUP_SCOPE_TYPE = "linha_grupo"

INTERNAL_SEPARATOR = "__"

_IDENTIFIER = r"(?:VAR|PARAM)\d{5}"

# Forma sintática de um escopo candidato. A validação semântica (o
# grupo existe?) é feita contra o ScopeResolver em `scope_type_for`.
_SCOPE_TOKEN = r"L[1-7](?:_L[1-7])?"

_DOMAIN_REFERENCE = re.compile(
    rf"\b({_IDENTIFIER})@({_SCOPE_TOKEN})\b"
)

_INTERNAL_REFERENCE = re.compile(
    rf"({_IDENTIFIER}){INTERNAL_SEPARATOR}({_SCOPE_TOKEN})"
)


class InvalidScopeReferenceError(ValueError):
    """Escopo explícito inexistente ou malformado."""


def scope_type_for(scope_value: str) -> str:
    """
    Deriva o scope_type de um escopo explícito.

    L1..L7                      -> linha
    L1_L3, L4_L5, L6_L7, L1_L7  -> linha_grupo
    """

    if scope_value in ScopeResolver.LINE_SCOPES:
        return LINE_SCOPE_TYPE

    if scope_value in ScopeResolver.LINE_GROUP_SCOPES:
        return LINE_GROUP_SCOPE_TYPE

    raise InvalidScopeReferenceError(
        f"Escopo explícito desconhecido: @{scope_value}"
    )


def to_internal(expression: str) -> str:
    """
    Converte `VAR11001@L1_L3` em `VAR11001__L1_L3`, validando que o
    escopo exista. Qualquer `@` remanescente depois da conversão é uma
    referência espacial inválida.
    """

    def _replace(match: re.Match) -> str:
        identifier, scope_value = match.group(1), match.group(2)
        scope_type_for(scope_value)
        return f"{identifier}{INTERNAL_SEPARATOR}{scope_value}"

    converted = _DOMAIN_REFERENCE.sub(_replace, expression)

    if "@" in converted:
        raise InvalidScopeReferenceError(
            "Referência espacial inválida na expressão: "
            f"{expression!r}. Use VARxxxxx@Lx ou VARxxxxx@<grupo>, "
            "com um escopo existente."
        )

    return converted


def split_internal(name: str) -> tuple[str, str | None, str | None]:
    """
    Decompõe um identificador interno.

    VAR11001__L1_L3 -> ("VAR11001", "linha_grupo", "L1_L3")
    VAR11001        -> ("VAR11001", None, None)
    """

    match = _INTERNAL_REFERENCE.fullmatch(name)

    if match is None:
        return name, None, None

    identifier, scope_value = match.group(1), match.group(2)

    return identifier, scope_type_for(scope_value), scope_value


def is_valid_internal(name: str) -> bool:
    """Indica se `name` é um identificador interno escopado válido."""

    match = _INTERNAL_REFERENCE.fullmatch(name)

    if match is None:
        return False

    try:
        scope_type_for(match.group(2))
    except InvalidScopeReferenceError:
        return False

    return True


def to_domain(name: str) -> str:
    """VAR11001__L1_L3 -> VAR11001@L1_L3 (demais nomes inalterados)."""

    identifier, _scope_type, scope_value = split_internal(name)

    if scope_value is None:
        return name

    return f"{identifier}@{scope_value}"


def split_domain(reference: str) -> tuple[str, str | None, str | None]:
    """
    VAR11001@L1_L3 -> ("VAR11001", "linha_grupo", "L1_L3")
    VAR11001       -> ("VAR11001", None, None)
    """

    if "@" not in reference:
        return reference, None, None

    identifier, scope_value = reference.split("@", 1)

    return identifier, scope_type_for(scope_value), scope_value
