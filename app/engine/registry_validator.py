from app.domain.equations.models import Equation, EquationDefinition
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationRegistry,
)
from app.domain.parameters.registry import (
    ParameterDefinitionRegistry,
    ParameterRegistry,
)
from app.domain.variables.registry import (
    VariableDefinitionRegistry,
    VariableRegistry,
)
from app.engine.dependency_extractor import DependencyExtractor
from app.engine.exceptions import (
    EquationTargetScopeMismatchError,
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

    # ========================================================
    # DEFINITION REGISTRIES — escopo Equation × Variable alvo
    # ========================================================

    def validate_definition_registry(
        self,
        equation_definition_registry: EquationDefinitionRegistry,
        variable_definition_registry: VariableDefinitionRegistry,
        parameter_definition_registry: ParameterDefinitionRegistry
        | None = None,
    ) -> None:
        """
        Valida as EquationDefinitions cadastradas no
        EquationDefinitionRegistry contra as Definitions de
        variáveis (e, quando informado, de parâmetros).

        Verifica:
        - a variável alvo existe como VariableDefinition;
        - o escopo (scope_type/scope_value) da EquationDefinition é
          idêntico ao escopo declarado da VariableDefinition alvo;
        - toda variável/parâmetro referenciado na expressão existe
          como Definition (a referência é comparada pelo seu ID
          base, ignorando um eventual sufixo "@Lx" explícito).
        """

        for definition in equation_definition_registry.all():
            self.validate_definition(
                definition=definition,
                variable_definition_registry=(
                    variable_definition_registry
                ),
                parameter_definition_registry=(
                    parameter_definition_registry
                ),
            )

    def validate_definition(
        self,
        definition: EquationDefinition,
        variable_definition_registry: VariableDefinitionRegistry,
        parameter_definition_registry: ParameterDefinitionRegistry
        | None = None,
    ) -> None:
        """
        Valida uma única EquationDefinition.
        """

        self._validate_definition_target_scope(
            definition=definition,
            variable_definition_registry=(
                variable_definition_registry
            ),
        )

        dependencies = self.dependency_extractor.extract(
            definition.expression
        )

        self._validate_definition_variable_references(
            definition=definition,
            variable_ids=dependencies.variables,
            variable_definition_registry=(
                variable_definition_registry
            ),
        )

        if parameter_definition_registry is not None:
            self._validate_definition_parameter_references(
                definition=definition,
                parameter_ids=dependencies.parameters,
                parameter_definition_registry=(
                    parameter_definition_registry
                ),
            )

    def _validate_definition_target_scope(
        self,
        definition: EquationDefinition,
        variable_definition_registry: VariableDefinitionRegistry,
    ) -> None:
        try:
            target_definition = variable_definition_registry.get(
                definition.target_variable_id
            )
        except KeyError as exc:
            raise TargetVariableNotFoundError(
                f"A equação {definition.equation_definition_id} "
                "possui como variável alvo "
                f"{definition.target_variable_id}, mas essa "
                "variável não está cadastrada no "
                "VariableDefinitionRegistry."
            ) from exc

        scope_matches = (
            definition.scope_type == target_definition.scope_type
            and definition.scope_value
            == target_definition.scope_value
        )

        if not scope_matches:
            raise EquationTargetScopeMismatchError(
                f"A equação {definition.equation_definition_id} "
                f"declara escopo "
                f"({definition.scope_type}/"
                f"{definition.scope_value}), incompatível com o "
                "escopo declarado da variável alvo "
                f"{definition.target_variable_id} "
                f"({target_definition.scope_type}/"
                f"{target_definition.scope_value})."
            )

    @staticmethod
    def _strip_scope_suffix(reference: str) -> str:
        """
        Remove um sufixo "@Lx" explícito de uma referência,
        retornando apenas o ID base (ex.: "VAR11001@L4" ->
        "VAR11001"). Referências sem sufixo são retornadas
        inalteradas.
        """

        return reference.split("@", 1)[0]

    def _validate_definition_variable_references(
        self,
        definition: EquationDefinition,
        variable_ids: frozenset[str],
        variable_definition_registry: VariableDefinitionRegistry,
    ) -> None:
        for variable_reference in sorted(variable_ids):
            variable_id = self._strip_scope_suffix(
                variable_reference
            )

            try:
                variable_definition_registry.get(variable_id)
            except KeyError as exc:
                raise VariableReferenceNotFoundError(
                    f"A equação "
                    f"{definition.equation_definition_id} "
                    f"referencia a variável {variable_id}, mas "
                    "essa variável não está cadastrada no "
                    "VariableDefinitionRegistry."
                ) from exc

    def _validate_definition_parameter_references(
        self,
        definition: EquationDefinition,
        parameter_ids: frozenset[str],
        parameter_definition_registry: ParameterDefinitionRegistry,
    ) -> None:
        for parameter_reference in sorted(parameter_ids):
            parameter_id = self._strip_scope_suffix(
                parameter_reference
            )

            try:
                parameter_definition_registry.get(parameter_id)
            except ValueError:
                # ID existe, mas há mais de uma Definition (ex.:
                # uma por linha, como "tanque_base"). A referência
                # em si é válida; a escolha da Definition concreta
                # cabe à resolução contextual em tempo de cálculo,
                # não a esta validação estrutural.
                continue
            except KeyError as exc:
                raise ParameterReferenceNotFoundError(
                    f"A equação "
                    f"{definition.equation_definition_id} "
                    f"referencia o parâmetro {parameter_id}, mas "
                    "esse parâmetro não está cadastrado no "
                    "ParameterDefinitionRegistry."
                ) from exc
