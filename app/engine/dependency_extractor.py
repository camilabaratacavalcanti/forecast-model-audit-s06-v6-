import ast
from dataclasses import dataclass

from app.engine import scoped_reference
from app.engine.expression_parser import ExpressionParser


@dataclass(frozen=True)
class ExpressionDependencies:
    """
    Representa as dependências identificadas em uma expressão.

    As referências contextualizadas são normalizadas para a forma
    original utilizada pelo domínio:

        VAR11001@L4
        PARAM11001@L4
    """

    variables: frozenset[str]
    parameters: frozenset[str]


class DependencyExtractor:
    """
    Identifica variáveis e parâmetros utilizados em uma expressão.

    A identificação é feita sobre a AST da expressão, aproveitando
    o mesmo parser utilizado pelo EquationEngine.

    Referências contextualizadas são convertidas da representação
    interna do parser:

        VAR11001__L4

    para a representação de domínio:

        VAR11001@L4
    """

    VARIABLE_PREFIX = "VAR"
    PARAMETER_PREFIX = "PARAM"

    def __init__(self):
        self.parser = ExpressionParser()

    def extract(
        self,
        expression: str,
    ) -> ExpressionDependencies:
        """
        Extrai as dependências de uma expressão.
        """

        tree = self.parser.parse(expression)

        variables: set[str] = set()
        parameters: set[str] = set()

        # Nomes de função (ex.: "ln" em ln(VAR11001)) não são
        # dependências: só o argumento é.
        function_name_nodes = {
            id(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.Name):
                continue

            if id(node) in function_name_nodes:
                continue

            name = self._restore_scoped_reference(node.id)

            if name.startswith(self.VARIABLE_PREFIX):
                variables.add(name)

            elif name.startswith(self.PARAMETER_PREFIX):
                parameters.add(name)

        return ExpressionDependencies(
            variables=frozenset(variables),
            parameters=frozenset(parameters),
        )

    @staticmethod
    def _restore_scoped_reference(name: str) -> str:
        """
        Converte a representação interna segura utilizada pelo AST:

            VAR11001__L4
            VAR11001__L1_L3
            PARAM11001__L4

        para a representação contextualizada do domínio:

            VAR11001@L4
            VAR11001@L1_L3
            PARAM11001@L4
        """

        return scoped_reference.to_domain(name)
