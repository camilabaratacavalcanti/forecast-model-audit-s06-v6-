"""
Objetivo:
    Orquestrar a execução das equações do Forecast Platform,
    respeitando suas dependências e delegando a seleção de
    equações ao EquationSelector quando configurado.

    O ForecastEngine coordena o fluxo de execução, mas não
    implementa diretamente as regras de seleção, resolução de
    escopo ou avaliação das expressões.
"""

from app.domain.equations.models import Equation
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.registry import VariableRegistry
from app.engine.calculation_context import CalculationContext
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.dependency_graph import DependencyGraph
from app.engine.dependency_resolver import DependencyResolver
from app.engine.equation_engine import EquationEngine
from app.engine.exceptions import DuplicateVariableProducerError
from app.engine.registry_validator import RegistryIntegrityValidator
from app.engine.equation_selector import EquationSelector
from app.engine.scope_resolver import ScopeResolver
from app.domain.equations.models import (
    EquationDefinition,
    EquationInstance,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationRegistry,
)


class ForecastEngine:
    """
    Orquestra a execução de um conjunto de equações
    respeitando suas dependências.
    """

    def __init__(
        self,
        equation_engine: EquationEngine | None = None,
        dependency_extractor: DependencyExtractor | None = None,
        dependency_resolver: DependencyResolver | None = None,
        registry_validator: RegistryIntegrityValidator | None = None,
        equation_selector: EquationSelector | None = None,
        scope_resolver: ScopeResolver | None = None,
    ):
        self.equation_engine = (
            equation_engine or EquationEngine()
        )

        self.dependency_extractor = (
            dependency_extractor or DependencyExtractor()
        )

        self.dependency_resolver = (
            dependency_resolver or DependencyResolver()
        )

        self.registry_validator = (
            registry_validator or RegistryIntegrityValidator()
        )

        self.equation_selector = equation_selector

        self.scope_resolver = (
            scope_resolver or ScopeResolver()
        )

    def materialize_equation(
        self,
        definition: EquationDefinition,
    ) -> list[EquationInstance]:
        """
        Materializa uma definição de equação em instâncias concretas
        de acordo com seu escopo.
        """
        return self.scope_resolver.resolve_equation(definition)

    def select_equation(
        self,
        equation_id: str,
        version: int | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> Equation:
        """
        Seleciona uma equação aplicável por meio do EquationSelector.

        O ForecastEngine não implementa as regras de seleção.
        Essa responsabilidade permanece no EquationSelector.
        """

        if self.equation_selector is None:
            raise RuntimeError(
                "EquationSelector não foi configurado "
                "no ForecastEngine."
            )

        return self.equation_selector.select(
            equation_id=equation_id,
            version=version,
            scope_type=scope_type,
            scope_value=scope_value,
        )

    def calculate(
        self,
        equations: list[Equation],
        variable_producers: dict[str, str],
        calculation_context: CalculationContext,
    ) -> dict[str, int | float]:
        """
        Executa as equações respeitando a ordem
        determinada pelas dependências.
        """

        graph = DependencyGraph()

        for equation in equations:
            graph.add_equation(
                equation,
                variable_producers,
                self.dependency_extractor,
            )

        execution_order = self.dependency_resolver.resolve(
            graph
        )

        equations_by_id = {
            equation.equation_id: equation
            for equation in equations
        }

        results: dict[str, int | float] = {}

        for equation_id in execution_order:
            equation = equations_by_id[equation_id]

            result = self.equation_engine.calculate(
                equation,
                calculation_context,
            )

            calculation_context.set_variable(
                equation.target_variable_id,
                result,
            )

            results[equation_id] = result

        return results

    def _build_variable_producers(
        self,
        equations: list[Equation],
    ) -> dict[str, str]:
        """
        Constrói o mapa:

            variável → equação produtora

        Garante que cada variável calculada possua
        apenas uma equação produtora.
        """

        variable_producers: dict[str, str] = {}

        for equation in equations:
            variable_id = equation.target_variable_id

            existing_producer = variable_producers.get(
                variable_id
            )

            if existing_producer is not None:
                raise DuplicateVariableProducerError(
                    f"A variável {variable_id} possui mais de "
                    f"uma equação produtora: "
                    f"{existing_producer} e "
                    f"{equation.equation_id}."
                )

            variable_producers[variable_id] = (
                equation.equation_id
            )

        return variable_producers

    def calculate_from_registry(
        self,
        equation_registry: EquationRegistry,
        variable_registry: VariableRegistry,
        parameter_registry: ParameterRegistry,
        calculation_context: CalculationContext,
    ) -> dict[str, int | float]:
        """
        Valida os Registries e executa as equações cadastradas
        no EquationRegistry.
        """

        self.registry_validator.validate_registry(
            equation_registry=equation_registry,
            variable_registry=variable_registry,
            parameter_registry=parameter_registry,
        )

        equations = equation_registry.all()

        variable_producers = self._build_variable_producers(
            equations
        )

        return self.calculate(
            equations=equations,
            variable_producers=variable_producers,
            calculation_context=calculation_context,
        )

    def calculate_from_definition_registry(
        self,
        equation_definition_registry: EquationDefinitionRegistry,
        calculation_context: CalculationContext,
    ) -> dict[str, int | float]:
        """
        Executa as EquationDefinitions cadastradas no
        EquationDefinitionRegistry.

        O fluxo é:

            Definition
                ↓
            Instance
                ↓
            DependencyGraph
                ↓
            DependencyResolver
                ↓
            EquationEngine

        O fluxo legado baseado em EquationRegistry permanece
        separado e inalterado.

        Apenas EquationDefinitions com status elegível para
        publicação (ver EquationSelector.ACTIVE_STATUSES) participam
        do cálculo. Definitions em DRAFT/PENDING/REJECTED nunca são
        materializadas nem calculadas por este caminho.
        """

        definitions = [
            definition
            for definition in equation_definition_registry.all()
            if definition.status
            in EquationSelector.ACTIVE_STATUSES
        ]

        instances: list[EquationInstance] = []

        definitions_by_id_and_version: dict[
            tuple[str, int],
            EquationDefinition,
        ] = {}

        for definition in definitions:
            key = (
                definition.equation_definition_id,
                definition.version,
            )

            definitions_by_id_and_version[key] = definition

            instances.extend(
                self.materialize_equation(
                    definition
                )
            )

        variable_producers = (
            self._build_instance_variable_producers(
                instances
            )
        )

        graph = DependencyGraph()

        for instance in instances:
            definition = definitions_by_id_and_version[
                (
                    instance.equation_definition_id,
                    instance.version,
                )
            ]

            graph.add_instance(
                instance=instance,
                definition=definition,
                variable_producers=variable_producers,
                extractor=self.dependency_extractor,
            )

        execution_order = self.dependency_resolver.resolve(
            graph
        )

        instances_by_node_id = {
            self._build_instance_node_id(instance): instance
            for instance in instances
        }

        results: dict[str, int | float] = {}

        for node_id in execution_order:
            instance = instances_by_node_id.get(node_id)

            if instance is None:
                continue

            definition = definitions_by_id_and_version[
                (
                    instance.equation_definition_id,
                    instance.version,
                )
            ]

            result = self.equation_engine.calculate_instance(
                instance=instance,
                definition=definition,
                calculation_context=calculation_context,
            )

            calculation_context.set_variable_value(
                variable_id=instance.target_variable_id,
                value=result,
                scope_type=instance.scope_type,
                scope_value=instance.scope_value,
            )

            results[
                instance.equation_instance_id
            ] = result

        return results

    def _build_instance_variable_producers(
        self,
        instances: list[EquationInstance],
    ) -> dict[str, str]:
        """
        Constrói o mapa de produtores para variáveis
        contextualizadas por instância.

        Exemplo:

            VAR11001@L4
                →
            EQ11001@linha:L4
        """

        variable_producers: dict[str, str] = {}

        for instance in instances:
            if instance.scope_type == "linha":
                variable_id = (
                    f"{instance.target_variable_id}"
                    f"@{instance.scope_value}"
                )
            else:
                variable_id = instance.target_variable_id

            existing_producer = variable_producers.get(
                variable_id
            )

            if existing_producer is not None:
                raise DuplicateVariableProducerError(
                    f"A variável {variable_id} possui mais de "
                    f"uma equação produtora: "
                    f"{existing_producer} e "
                    f"{self._build_instance_node_id(instance)}."
                )

            variable_producers[variable_id] = (
                self._build_instance_node_id(instance)
            )

        return variable_producers

    @staticmethod
    def _build_instance_node_id(
        instance: EquationInstance,
    ) -> str:
        """
        Constrói o identificador do nó do DependencyGraph
        correspondente a uma EquationInstance.

        O ID do grafo é deliberadamente diferente do
        equation_instance_id.

        Instance:

            EQ11001@v1@L4

        Nó do grafo:

            EQ11001@linha:L4
        """

        return (
            f"{instance.equation_definition_id}"
            f"@{instance.scope_type}"
            f":{instance.scope_value}"
        )
