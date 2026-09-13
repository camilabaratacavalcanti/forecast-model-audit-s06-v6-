"""
Carrega, valida e materializa os seeds da plataforma de Forecast.

O módulo coordena o fluxo:

    Seed
    ↓
    Validator
    ↓
    Definition
    ↓
    DefinitionRegistry
    ↓
    ScopeResolver
    ↓
    Instance
    ↓
    InstanceRegistry

Também mantém os métodos legados de carregamento para
compatibilidade com a arquitetura existente.
"""

from pathlib import Path

from app.domain.equations.models import (
    Equation,
    EquationDefinition,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationInstanceRegistry,
    EquationRegistry,
)

from app.domain.parameters.models import (
    Parameter,
    ParameterDefinition,
)
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterInstanceRegistry,
    ParameterRegistry,
)

from app.domain.variables.models import (
    Variable,
    VariableDefinition,
)
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableInstanceRegistry,
    VariableRegistry,
)

from app.engine.scope_resolver import ScopeResolver

from app.validation import equation_seed_validator
from app.validation import parameter_seed_validator
from app.validation import variable_seed_validator


class SeedLoader:
    """
    Responsável por validar e carregar os seeds do modelo.

    O SeedLoader coordena o fluxo:

        JSON
        ↓
        Validator
        ↓
        Domain Object
        ↓
        Registry

    A validação sempre ocorre antes da criação dos objetos
    de domínio e do registro dos dados.
    """

    def __init__(
        self,
        seed_root: str | Path,
        scope_resolver: ScopeResolver | None = None,
    ):
        self.seed_root = Path(seed_root)
        self.scope_resolver = (
            scope_resolver
            if scope_resolver is not None
            else ScopeResolver()
        )

    def load_variables(
        self,
        registry: VariableRegistry | None = None,
    ) -> VariableRegistry:
        """
        Valida e carrega todas as variáveis dos seeds.

        Retorna o VariableRegistry preenchido.

        Raises:
            ValueError: se o seed de variáveis for inválido.
        """

        validation_result = (
            variable_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if not validation_result["is_valid"]:
            raise ValueError(
                self._format_validation_errors(
                    "Variable",
                    validation_result["errors"],
                )
            )

        variables = (
            variable_seed_validator.load_variables_from_seed(
                self.seed_root
            )
        )

        if registry is None:
            registry = VariableRegistry()

        for variable_data in variables:
            variable_data = variable_data.copy()

            # _block é um metadado utilizado pelo validator.
            # Não pertence ao Domain Model Variable.
            variable_data.pop("_block", None)

            variable = Variable(**variable_data)

            registry.add(variable)

        return registry

    def load_parameters(
        self,
        registry: ParameterRegistry | None = None,
    ) -> ParameterRegistry:
        """
        Valida e carrega todos os parâmetros dos seeds.

        Retorna o ParameterRegistry preenchido.

        Raises:
            ValueError: se o seed de parâmetros for inválido.
        """

        errors, _warnings = (
            parameter_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if errors:
            raise ValueError(
                self._format_validation_errors(
                    "Parameter",
                    errors,
                )
            )

        parameters, loading_errors = (
            parameter_seed_validator.load_parameters_from_seed(
                self.seed_root
            )
        )

        if loading_errors:
            raise ValueError(
                self._format_validation_errors(
                    "Parameter",
                    loading_errors,
                )
            )

        if registry is None:
            registry = ParameterRegistry()

        for parameter_data, _file_path in parameters:
            parameter = Parameter(**parameter_data)

            registry.add(parameter)

        return registry

    def load_equations(
        self,
        registry: EquationRegistry | None = None,
    ) -> EquationRegistry:
        """
        Valida e carrega todas as equações dos seeds.

        Retorna o EquationRegistry preenchido.

        Raises:
            ValueError: se o seed de equações for inválido.
        """

        errors, _warnings = (
            equation_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if errors:
            raise ValueError(
                self._format_validation_errors(
                    "Equation",
                    errors,
                )
            )

        equations, loading_errors = (
            equation_seed_validator.load_equations_from_seed(
                self.seed_root
            )
        )

        if loading_errors:
            raise ValueError(
                self._format_validation_errors(
                    "Equation",
                    loading_errors,
                )
            )

        if registry is None:
            registry = EquationRegistry()

        for equation_data in equations:
            equation = Equation(**equation_data)

            registry.add(equation)

        return registry

    def load_all(
        self,
    ) -> tuple[
        VariableRegistry,
        ParameterRegistry,
        EquationRegistry,
    ]:
        """
        Valida e carrega todos os tipos de seed.

        Retorna:

            (
                VariableRegistry,
                ParameterRegistry,
                EquationRegistry,
            )

        O carregamento é interrompido se qualquer tipo de seed
        apresentar erro de validação.
        """

        variable_registry = self.load_variables()
        parameter_registry = self.load_parameters()
        equation_registry = self.load_equations()

        return (
            variable_registry,
            parameter_registry,
            equation_registry,
        )

    def load_variable_definitions(
        self,
        registry: VariableDefinitionRegistry | None = None,
    ) -> VariableDefinitionRegistry:
        """
        Valida e carrega as definições de variáveis dos seeds.

        O fluxo é:

            Seed
            ↓
            Validator
            ↓
            Variable
            ↓
            VariableDefinition
            ↓
            VariableDefinitionRegistry
        """

        validation_result = (
            variable_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if not validation_result["is_valid"]:
            raise ValueError(
                self._format_validation_errors(
                    "Variable",
                    validation_result["errors"],
                )
            )

        variables = (
            variable_seed_validator.load_variables_from_seed(
                self.seed_root
            )
        )

        if registry is None:
            registry = VariableDefinitionRegistry()

        for variable_data in variables:
            variable_data = variable_data.copy()

            # _block é um metadado utilizado pelo validator.
            # Não pertence ao Domain Model Variable.
            variable_data.pop("_block", None)

            variable = Variable(**variable_data)

            definition = VariableDefinition.from_variable(
                variable
            )

            registry.add(definition)

        return registry

    def load_variable_instances(
        self,
        definition_registry: VariableDefinitionRegistry | None = None,
        instance_registry: VariableInstanceRegistry | None = None,
    ) -> VariableInstanceRegistry:
        """
        Materializa VariableDefinitions em VariableInstances.

        Fluxo:

            VariableDefinitionRegistry
            ↓
            ScopeResolver
            ↓
            VariableInstanceRegistry
        """

        if definition_registry is None:
            definition_registry = (
                self.load_variable_definitions()
            )

        if instance_registry is None:
            instance_registry = VariableInstanceRegistry()

        for definition in definition_registry.all():
            instances = self.scope_resolver.resolve_variable(
                definition
            )

            for instance in instances:
                instance_registry.add(instance)

        return instance_registry

    def load_parameter_definitions(
        self,
        registry: ParameterDefinitionRegistry | None = None,
    ) -> ParameterDefinitionRegistry:
        """
        Valida e carrega as definições de parâmetros dos seeds.

        O fluxo é:

            Seed
            ↓
            Validator
            ↓
            Parameter
            ↓
            ParameterDefinition
            ↓
            ParameterDefinitionRegistry
        """

        errors, _warnings = (
            parameter_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if errors:
            raise ValueError(
                self._format_validation_errors(
                    "Parameter",
                    errors,
                )
            )

        parameters, loading_errors = (
            parameter_seed_validator.load_parameters_from_seed(
                self.seed_root
            )
        )

        if loading_errors:
            raise ValueError(
                self._format_validation_errors(
                    "Parameter",
                    loading_errors,
                )
            )

        if registry is None:
            registry = ParameterDefinitionRegistry()

        for parameter_data, _file_path in parameters:
            parameter = Parameter(**parameter_data)

            definition = ParameterDefinition.from_parameter(
                parameter
            )

            registry.add(definition)

        return registry

    def load_parameter_instances(
        self,
        definition_registry: ParameterDefinitionRegistry | None = None,
        instance_registry: ParameterInstanceRegistry | None = None,
    ) -> ParameterInstanceRegistry:
        """
        Materializa ParameterDefinitions em ParameterInstances.

        Fluxo:

            ParameterDefinitionRegistry
            ↓
            ScopeResolver
            ↓
            ParameterInstanceRegistry
        """

        if definition_registry is None:
            definition_registry = (
                self.load_parameter_definitions()
            )

        if instance_registry is None:
            instance_registry = ParameterInstanceRegistry()

        for definition in definition_registry.all():
            instances = self.scope_resolver.resolve_parameter(
                definition
            )

            for instance in instances:
                instance_registry.add(instance)

        return instance_registry

    def load_equation_definitions(
        self,
        registry: EquationDefinitionRegistry | None = None,
    ) -> EquationDefinitionRegistry:
        """
        Valida e carrega as definições de equações dos seeds.

        O fluxo é:

            Seed
            ↓
            Validator
            ↓
            Equation
            ↓
            EquationDefinition
            ↓
            EquationDefinitionRegistry
        """

        errors, _warnings = (
            equation_seed_validator.validate_seed(
                self.seed_root
            )
        )

        if errors:
            raise ValueError(
                self._format_validation_errors(
                    "Equation",
                    errors,
                )
            )

        equations, loading_errors = (
            equation_seed_validator.load_equations_from_seed(
                self.seed_root
            )
        )

        if loading_errors:
            raise ValueError(
                self._format_validation_errors(
                    "Equation",
                    loading_errors,
                )
            )

        if registry is None:
            registry = EquationDefinitionRegistry()

        for equation_data in equations:
            equation = Equation(**equation_data)

            definition = EquationDefinition.from_equation(
                equation
            )

            registry.add(definition)

        return registry

    @staticmethod
    def _format_validation_errors(
        entity_name: str,
        errors: list[str],
    ) -> str:
        """
        Formata os erros de validação em uma mensagem única.
        """

        lines = [
            f"{entity_name} seed validation failed:"
        ]

        lines.extend(
            f"- {error}"
            for error in errors
        )

        return "\n".join(lines)

    def load_equation_instances(
        self,
        definition_registry: EquationDefinitionRegistry | None = None,
        instance_registry: EquationInstanceRegistry | None = None,
    ) -> EquationInstanceRegistry:
        """
        Materializa EquationDefinitions em EquationInstances.

        Fluxo:

            EquationDefinitionRegistry
            ↓
            ScopeResolver
            ↓
            EquationInstanceRegistry
        """

        if definition_registry is None:
            definition_registry = (
                self.load_equation_definitions()
            )

        if instance_registry is None:
            instance_registry = EquationInstanceRegistry()

        for definition in definition_registry.all():
            instances = self.scope_resolver.resolve_equation(
                definition
            )

            for instance in instances:
                instance_registry.add(instance)

        return instance_registry

    def load_all_definitions_and_instances(
        self,
    ) -> tuple[
        VariableDefinitionRegistry,
        VariableInstanceRegistry,
        ParameterDefinitionRegistry,
        ParameterInstanceRegistry,
        EquationDefinitionRegistry,
        EquationInstanceRegistry,
    ]:
        """
        Carrega todas as Definitions e materializa suas Instances.

        Fluxo:

            Seed
            ↓
            Definitions
            ↓
            ScopeResolver
            ↓
            Instances
            ↓
            Instance Registries
        """

        variable_definitions = (
            self.load_variable_definitions()
        )

        variable_instances = (
            self.load_variable_instances(
                definition_registry=variable_definitions
            )
        )

        parameter_definitions = (
            self.load_parameter_definitions()
        )

        parameter_instances = (
            self.load_parameter_instances(
                definition_registry=parameter_definitions
            )
        )

        equation_definitions = (
            self.load_equation_definitions()
        )

        equation_instances = (
            self.load_equation_instances(
                definition_registry=equation_definitions
            )
        )

        return (
            variable_definitions,
            variable_instances,
            parameter_definitions,
            parameter_instances,
            equation_definitions,
            equation_instances,
        )
