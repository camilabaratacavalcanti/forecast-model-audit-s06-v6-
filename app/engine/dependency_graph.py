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
from app.engine import scoped_reference
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

        Uma referência explicitamente escopada na expressão (ex.:
        "VAR11001@L4") é usada exatamente como declarada — nunca é
        reescrita para o escopo da instância. Somente referências
        sem escopo (ex.: "VAR11001") são resolvidas contra um
        produtor no mesmo escopo da instância corrente; essa é a
        mesma semântica aplicada pelo EquationEngine/
        ExpressionEvaluator na avaliação.

        Exemplo:

            Definition:
                VAR11001@L4 + VAR11002

            Instance:
                linha:L5

            Dependências:
                VAR11001@L4  (mantida, explícita)
                VAR11002@L5  (contextualizada, era implícita)
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

        # Variáveis e parâmetros usam exatamente a mesma regra de
        # resolução/contextualização — a referência (VAR ou PARAM)
        # é que determina se o escopo é explícito ou implícito, não
        # o tipo do identificador.
        all_references = (
            dependencies.variables | dependencies.parameters
        )

        for reference in all_references:
            (
                matched_reference,
                producer_id,
            ) = self._resolve_variable_producer(
                reference,
                instance,
                variable_producers,
            )

            if producer_id is None:
                continue

            dependency_id = self._scope_dependency_id(
                matched_reference,
                producer_id,
                instance,
            )

            self._dependencies[equation_node_id].add(
                dependency_id
            )

            self._dependencies.setdefault(
                dependency_id,
                set(),
            )

    @classmethod
    def _scope_dependency_id(
        cls,
        matched_reference: str,
        producer_id: str,
        instance: EquationInstance,
    ) -> str:
        """
        Constrói o identificador de nó do produtor, quando o valor
        registrado em variable_producers ainda não é um node_id
        totalmente qualificado (não contém "@").

        O escopo usado para qualificar o produtor vem SEMPRE da
        própria referência resolvida (matched_reference), nunca do
        escopo da EquationInstance corrente:

            - referência explícita (ex.: "VAR10001@L2"): o escopo
              "linha:L2" embutido na própria referência é usado —
              mesmo que a instance em execução seja outra linha
              (ex.: L5). Fazer o contrário reintroduziria o
              vazamento de contexto que este método existe para
              impedir.
            - referência implícita já contextualizada por
              _resolve_variable_producer (ex.: "VAR10001@L5",
              produzida a partir de "VAR10001" em uma instance L5):
              o escopo embutido já É o da instance, então o
              resultado é idêntico a usar instance.scope_type/
              scope_value diretamente.
            - referência implícita sem contextualização disponível
              (fallback legado, sem "@"): usa o escopo da própria
              instance, mantendo a compatibilidade retroativa já
              existente.
        """

        if "@" in producer_id:
            return producer_id

        if "@" in matched_reference:
            (
                _base_reference,
                explicit_scope_type,
                explicit_scope_value,
            ) = scoped_reference.split_domain(matched_reference)

            return cls._build_node_id(
                producer_id,
                explicit_scope_type,
                explicit_scope_value,
            )

        return cls._build_node_id(
            producer_id,
            instance.scope_type,
            instance.scope_value,
        )

    @staticmethod
    def _resolve_variable_producer(
        variable_reference: str,
        instance: EquationInstance,
        variable_producers: dict[str, str],
    ) -> tuple[str, str | None]:
        """
        Resolve o produtor de uma referência de variável dentro do
        contexto de uma EquationInstance.

        Referência explicitamente escopada (contém "@", ex.:
        "VAR11020@L2"): NUNCA é reescrita. É usada exatamente como
        declarada para localizar seu produtor, independentemente do
        escopo da instance corrente — essa é a mesma garantia dada
        pelo EquationEngine/ExpressionEvaluator na avaliação, e é
        crítica para equações de agregação (linha_grupo) que somam/
        ponderam explicitamente várias linhas em uma única
        expressão.

        Referência sem escopo (ex.: "VAR11020"): pertence ao escopo
        da própria equação. É resolvida, em primeiro lugar, contra
        um produtor no mesmo escopo da instance (ex.:
        "VAR11020@L4"); se não houver produtor ali, cai para a
        busca legada pela referência não escopada (compatibilidade
        retroativa com o fluxo baseado em Equation/EquationRegistry).
        """

        if "@" in variable_reference:
            return (
                variable_reference,
                variable_producers.get(variable_reference),
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
