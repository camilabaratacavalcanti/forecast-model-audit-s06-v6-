from app.domain.equations.models import Equation
from app.domain.equations.registry import EquationRegistry
from app.domain.parameters.registry import ParameterRegistry
from app.domain.variables.registry import VariableRegistry
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.exceptions import (
    ParameterReferenceNotFoundError,
    TargetVariableNotFoundError,
    VariableReferenceNotFoundError,
)


class RegistryIntegrityValidator:
    """
    Valida a integridade das referências entre:

        VariableRegistry
        ParameterRegistry
        EquationRegistry

    Responsabilidades:

    - verificar se a variável alvo da equação existe;
    - verificar se as variáveis utilizadas na expressão existem;
    - verificar se os parâmetros utilizados na expressão existem.
    """

    def __init__(
        self,
        dependency_extractor: DependencyExtractor | None = None,
    ):
        self.dependency_extractor = (
            dependency_extractor or DependencyExtractor()
        )

    def validate_equation(
        self,
        equation: Equation,
        variable_registry: VariableRegistry,
        parameter_registry: ParameterRegistry,
    ) -> None:
        """
        Valida as referências de uma única equação.
        """

        self._validate_target_variable(
            equation=equation,
            variable_registry=variable_registry,
        )

        dependencies = self.dependency_extractor.extract(
            equation.expression
        )

        self._validate_variables(
            equation=equation,
            variable_ids=dependencies.variables,
            variable_registry=variable_registry,
        )

        self._validate_parameters(
            equation=equation,
            parameter_ids=dependencies.parameters,
            parameter_registry=parameter_registry,
        )

    def validate_registry(
        self,
        equation_registry: EquationRegistry,
        variable_registry: VariableRegistry,
        parameter_registry: ParameterRegistry,
    ) -> None:
        """
        Valida todas as equações cadastradas no EquationRegistry.
        """

        for equation in equation_registry.all():
            self.validate_equation(
                equation=equation,
                variable_registry=variable_registry,
                parameter_registry=parameter_registry,
            )

    def _validate_target_variable(
        self,
        equation: Equation,
        variable_registry: VariableRegistry,
    ) -> None:
        """
        Verifica se a variável alvo da equação existe.
        """

        try:
            variable_registry.get(equation.target_variable_id)
        except KeyError as exc:
            raise TargetVariableNotFoundError(
                f"A equação {equation.equation_id} possui como "
                f"variável alvo {equation.target_variable_id}, "
                f"mas essa variável não está cadastrada no "
                f"VariableRegistry."
            ) from exc

    def _validate_variables(
        self,
        equation: Equation,
        variable_ids: frozenset[str],
        variable_registry: VariableRegistry,
    ) -> None:
        """
        Verifica se todas as variáveis utilizadas na expressão
        existem no VariableRegistry.
        """

        for variable_id in sorted(variable_ids):
            try:
                variable_registry.get(variable_id)
            except KeyError as exc:
                raise VariableReferenceNotFoundError(
                    f"A equação {equation.equation_id} referencia "
                    f"a variável {variable_id}, mas essa variável "
                    f"não está cadastrada no VariableRegistry."
                ) from exc

    def _validate_parameters(
        self,
        equation: Equation,
        parameter_ids: frozenset[str],
        parameter_registry: ParameterRegistry,
    ) -> None:
        """
        Verifica se todos os parâmetros utilizados na expressão
        existem no ParameterRegistry.
        """

        for parameter_id in sorted(parameter_ids):
            try:
                parameter_registry.get(parameter_id)
            except KeyError as exc:
                raise ParameterReferenceNotFoundError(
                    f"A equação {equation.equation_id} referencia "
                    f"o parâmetro {parameter_id}, mas esse parâmetro "
                    f"não está cadastrado no ParameterRegistry."
                ) from exc
