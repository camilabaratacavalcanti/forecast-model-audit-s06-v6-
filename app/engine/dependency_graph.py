"""
Objetivo:
    Representar o grafo de dependências entre equações e suas
    instâncias contextualizadas, preservando o contexto espacial
    necessário para a resolução correta das dependências.
"""

from dataclasses import dataclass, field

from app.domain.equations.models import Equation
from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.engine.dependency_extractor import DependencyExtractor


@dataclass
class DependencyGraph:
    """
    Grafo de dependências entre equações.

    Cada nó representa uma equação.
    Uma aresta A -> B significa que A depende de B.

    Para equações contextualizadas, o identificador do nó incorpora
    o contexto da equação, por exemplo:

        EQ11001@linha:L4
    """

    _dependencies: dict[str, set[str]] = field(default_factory=dict)

    @staticmethod
    def _build_node_id(
        equation_id: str,
        scope_type: str | None,
        scope_value: str | None,
    ) -> str:
        """
        Constrói o identificador do nó da equação.
        """

        if scope_type is None and scope_value is None:
            return equation_id

        return f"{equation_id}@{scope_type}:{scope_value}"

    def add_equation(
        self,
        equation: Equation,
        variable_producers: dict[str, str],
        extractor: DependencyExtractor,
    ) -> None:
        dependencies = extractor.extract(equation.expression)

        has_scoped_dependency = any(
            "@" in variable_reference
            for variable_reference in dependencies.variables
        )

        scoped_target_reference = None

        if (
            equation.scope_type == "linha"
            and equation.scope_value is not None
        ):
            scoped_target_reference = (
                f"{equation.target_variable_id}@{equation.scope_value}"
            )

        has_scoped_target = (
            scoped_target_reference in variable_producers
            if scoped_target_reference is not None
            else False
        )

        is_contextualized = (
            equation.scope_type is not None
            and equation.scope_value is not None
            and (
                has_scoped_dependency
                or has_scoped_target
            )
        )

        if is_contextualized:
            equation_node_id = self._build_node_id(
                equation.equation_id,
                equation.scope_type,
                equation.scope_value,
            )
        else:
            equation_node_id = equation.equation_id

        equation_dependencies: set[str] = set()

        for variable_reference in dependencies.variables:
            producer_equation_id = variable_producers.get(
                variable_reference
            )

            if producer_equation_id is None:
                continue

            dependency_id = producer_equation_id

            if (
                is_contextualized
                and "@" in variable_reference
                and "@" not in producer_equation_id
            ):
                dependency_id = self._build_node_id(
                    producer_equation_id,
                    equation.scope_type,
                    equation.scope_value,
                )

            equation_dependencies.add(dependency_id)

        self._dependencies.setdefault(
            equation_node_id,
            set(),
        )

        self._dependencies[equation_node_id].update(
            equation_dependencies
        )

        for dependency_id in equation_dependencies:
            self._dependencies.setdefault(
                dependency_id,
                set(),
            )

    def as_dict(self) -> dict[str, set[str]]:
        """
        Retorna uma cópia do grafo no formato de dicionário.

        A cópia evita que consumidores externos alterem diretamente
        o estado interno do grafo.
        """

        return {
            equation_id: set(dependency_ids)
            for equation_id, dependency_ids in self._dependencies.items()
        }

    def get_dependencies(
        self,
        equation_id: str,
    ) -> frozenset[str]:
        """
        Retorna as equações das quais uma equação depende.

        Retorna um conjunto imutável para impedir que o estado interno
        do grafo seja alterado externamente.
        """

        return frozenset(
            self._dependencies.get(
                equation_id,
                set(),
            )
        )

    def get_equations(self) -> frozenset[str]:
        """
        Retorna todos os nós de equações presentes no grafo.
        """

        return frozenset(
            self._dependencies.keys()
        )

    def add_instance(
        self,
        instance: EquationInstance,
        definition: EquationDefinition,
        variable_producers: dict[str, str],
        extractor: DependencyExtractor,
    ) -> None:
        """
        Adiciona uma EquationInstance ao grafo utilizando a expressão
        pertencente à sua EquationDefinition.

        A definição contém a regra matemática.
        A instância fornece o contexto concreto de execução.

        Referências de variáveis contextualizadas na expressão são
        adaptadas ao escopo da instância antes da resolução de seus
        produtores.

        Exemplo:

            Definition:
                VAR11001@L4

            Instance:
                linha:L5

            Referência contextualizada:
                VAR11001@L5
        """

        dependencies = extractor.extract(
            definition.expression
        )

        equation_node_id = self._build_node_id(
            definition.equation_definition_id,
            instance.scope_type,
            instance.scope_value,
        )

        self._dependencies.setdefault(
            equation_node_id,
            set(),
        )

        for variable_reference in dependencies.variables:
            (
                matched_reference,
                producer_id,
            ) = self._resolve_variable_producer(
                variable_reference,
                instance,
                variable_producers,
            )

            if producer_id is None:
                continue

            dependency_id = producer_id

            if (
                "@" in matched_reference
                and "@" not in producer_id
            ):
                dependency_id = self._build_node_id(
                    producer_id,
                    instance.scope_type,
                    instance.scope_value,
                )

            self._dependencies[equation_node_id].add(
                dependency_id
            )

            self._dependencies.setdefault(
                dependency_id,
                set(),
            )

    @classmethod
    def _resolve_variable_producer(
        cls,
        variable_reference: str,
        instance: EquationInstance,
        variable_producers: dict[str, str],
    ) -> tuple[str, str | None]:
        """
        Resolve o produtor de uma referência de variável dentro do
        contexto de uma EquationInstance.

        Referências já explicitamente escopadas (contêm "@") seguem
        o comportamento existente: são recontextualizadas para o
        escopo da instance corrente.

        Referências sem escopo (ex.: "VAR11020") são resolvidas, em
        primeiro lugar, contra um produtor no mesmo escopo da
        instance (ex.: "VAR11020@L4"), refletindo a regra de que uma
        referência sem "@Lx" pertence ao escopo da própria equação.
        Se não houver produtor nesse escopo, cai para a busca legada
        pela referência não escopada (compatibilidade retroativa).
        """

        if "@" in variable_reference:
            contextualized = cls._contextualize_variable_reference(
                variable_reference,
                instance,
            )

            return (
                contextualized,
                variable_producers.get(contextualized),
            )

        if (
            instance.scope_type == "linha"
            and instance.scope_value
        ):
            scoped_reference = (
                f"{variable_reference}@{instance.scope_value}"
            )

            scoped_producer_id = variable_producers.get(
                scoped_reference
            )

            if scoped_producer_id is not None:
                return (
                    scoped_reference,
                    scoped_producer_id,
                )

        return (
            variable_reference,
            variable_producers.get(variable_reference),
        )

    @staticmethod
    def _contextualize_variable_reference(
        variable_reference: str,
        instance: EquationInstance,
    ) -> str:
        """
        Contextualiza uma referência de variável para o escopo
        da EquationInstance.

        Referências sem contexto permanecem inalteradas.

        Exemplo:

            VAR11001@L4 + Instance(L5)
            -> VAR11001@L5
        """

        if (
            instance.scope_type != "linha"
            or instance.scope_value is None
        ):
            return variable_reference

        if "@" not in variable_reference:
            return variable_reference

        variable_id, _ = variable_reference.split(
            "@",
            1,
        )

        return f"{variable_id}@{instance.scope_value}"
