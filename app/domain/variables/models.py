"""
Objetivo:
    Definir os modelos de domínio de Variable, incluindo a separação
    entre VariableDefinition e VariableInstance.

    VariableDefinition representa a definição lógica da variável.

    VariableInstance representa uma ocorrência concreta da definição
    em um escopo resolvido.

    A dimensão temporal não pertence à VariableInstance e será tratada
    posteriormente pelo mecanismo de resolução temporal.
"""

from dataclasses import dataclass

from app.domain.values import (
    CATEGORICAL,
    NUMERIC,
    RESULT_STATE_TAXONOMY,
    VALUE_TYPES,
    is_conditional_failure,
    is_numeric,
)


@dataclass
class Variable:
    """
    Modelo atual de variável (forma do seed).

    Mantido temporariamente para compatibilidade com o contrato
    existente da plataforma. Os campos contratuais do workbook chegam
    aqui como no seed (listas/objetos JSON) e são convertidos em
    estruturas imutáveis por `VariableDefinition.from_variable`.
    """

    variable_id: str
    variable_name: str
    description: str | None
    unit: str
    variable_type: str
    frequency: str
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str
    # Tipo do valor (app.domain.values): "numerico" ou "categorico".
    # Obrigatório: não existe valor padrão.
    value_type: str
    allowed_values: list[str] | None = None
    declared_result_states: list[dict] | None = None
    instances: list[dict] | None = None


@dataclass(frozen=True)
class DeclaredResultState:
    """
    Estado de resultado que a própria regra da variável produz (R1),
    com o literal textual que o representa (ex.: NO_APPLICABLE_RULE
    -> "F"). Metadado contratual: a semântica de propagação pertence à
    Etapa 3.
    """

    state: str
    literal: str

    def __post_init__(self) -> None:
        if self.state not in RESULT_STATE_TAXONOMY:
            raise ValueError(
                f"Estado {self.state!r} fora da taxonomia "
                f"{sorted(RESULT_STATE_TAXONOMY)}."
            )

        if not isinstance(self.literal, str) or not self.literal:
            raise ValueError(
                f"Literal do estado {self.state} deve ser texto não "
                f"vazio: {self.literal!r}."
            )


@dataclass(frozen=True)
class VariableInstanceDeclaration:
    """
    Instância declarada no workbook de uma definição com instâncias
    por linha: uma linha do workbook = uma instância da MESMA
    definição, com a sua própria descrição e referência de origem.
    """

    scope_value: str
    description: str | None
    source_reference: str


@dataclass(frozen=True)
class VariableDefinition:
    """
    Definição lógica de uma variável.

    Representa o que a variável é, sua granularidade temporal
    e sua declaração de escopo.

    Não representa uma ocorrência concreta.
    """

    variable_definition_id: str
    variable_name: str
    description: str | None
    unit: str
    variable_type: str
    frequency: str
    scope_type: str | None
    scope_value: str | None
    source_reference: str
    status: str
    # Tipo do valor (app.domain.values): "numerico" ou "categorico".
    # Obrigatório: ausência é erro, nunca "numerico" implícito.
    value_type: str
    allowed_values: tuple[str, ...] | None = None
    declared_result_states: tuple[DeclaredResultState, ...] | None = None
    instances: tuple[VariableInstanceDeclaration, ...] | None = None

    @classmethod
    def from_variable(cls, variable: Variable) -> "VariableDefinition":
        return cls(
            variable_definition_id=variable.variable_id,
            variable_name=variable.variable_name,
            description=variable.description,
            unit=variable.unit,
            variable_type=variable.variable_type,
            frequency=variable.frequency,
            scope_type=variable.scope_type,
            scope_value=variable.scope_value,
            source_reference=variable.source_reference,
            status=variable.status,
            value_type=variable.value_type,
            allowed_values=(
                tuple(variable.allowed_values)
                if variable.allowed_values is not None
                else None
            ),
            declared_result_states=(
                tuple(
                    DeclaredResultState(**state)
                    for state in variable.declared_result_states
                )
                if variable.declared_result_states is not None
                else None
            ),
            instances=(
                tuple(
                    VariableInstanceDeclaration(**instance)
                    for instance in variable.instances
                )
                if variable.instances is not None
                else None
            ),
        )

    def __post_init__(self) -> None:
        if self.value_type not in VALUE_TYPES:
            raise ValueError(
                f"value_type inválido para {self.variable_definition_id}: "
                f"{self.value_type!r} (permitidos: {sorted(VALUE_TYPES)})"
            )

        if self.allowed_values is not None:
            if self.value_type != CATEGORICAL:
                raise ValueError(
                    f"{self.variable_definition_id}: allowed_values só se "
                    f"aplica a value_type '{CATEGORICAL}'."
                )

            if (
                not isinstance(self.allowed_values, tuple)
                or not self.allowed_values
                or any(
                    not isinstance(option, str) or not option
                    for option in self.allowed_values
                )
                or len(set(self.allowed_values)) != len(self.allowed_values)
            ):
                raise ValueError(
                    f"{self.variable_definition_id}: allowed_values deve "
                    "ser uma tupla não vazia de textos únicos: "
                    f"{self.allowed_values!r}."
                )

        if self.declared_result_states is not None:
            states = [s.state for s in self.declared_result_states]

            if not states or len(set(states)) != len(states):
                raise ValueError(
                    f"{self.variable_definition_id}: declared_result_states "
                    f"vazio ou com estado repetido: {states}."
                )

        if self.instances is not None:
            scopes = [i.scope_value for i in self.instances]

            if not scopes or len(set(scopes)) != len(scopes):
                raise ValueError(
                    f"{self.variable_definition_id}: instâncias declaradas "
                    f"vazias ou repetidas: {scopes}."
                )

    @property
    def is_categorical(self) -> bool:
        return self.value_type == CATEGORICAL

    def is_value_in_domain(self, value) -> bool:
        """
        O valor pertence ao domínio declarado da variável?

        numerico: número (nunca bool, nunca texto numérico);
        categorico: texto não vazio e, havendo allowed_values, uma das
        opções. O marcador de falha condicional "F" não é um valor de
        negócio e não pertence a nenhum domínio.

        Apenas responde: tratar um valor fora do domínio (INVALID_INPUT)
        é responsabilidade do runtime da Etapa 3.
        """

        if is_conditional_failure(value):
            return False

        if self.value_type == NUMERIC:
            return is_numeric(value)

        if not isinstance(value, str) or not value:
            return False

        return self.allowed_values is None or value in self.allowed_values


@dataclass(frozen=True)
class VariableInstance:
    """
    Instância concreta de uma VariableDefinition.

    O período não pertence à instance.
    A dimensão temporal será resolvida posteriormente.
    """

    variable_instance_id: str
    variable_definition_id: str
    scope_type: str
    scope_value: str | None

    # scope_types cujo scope_value concreto é None (não materializam
    # por linha/grupo/planta): a Definition e a Instance coincidem
    # em uma única ocorrência singular.
    SCOPELESS_SCOPE_TYPES = {"área", "global"}

    @classmethod
    def create(
        cls,
        definition: VariableDefinition,
        scope_type: str,
        scope_value: str | None,
    ) -> "VariableInstance":

        if not scope_type:
            raise ValueError(
                "scope_type is required to create a variable instance"
            )

        if (
            not scope_value
            and scope_type not in cls.SCOPELESS_SCOPE_TYPES
        ):
            raise ValueError(
                "scope_value is required to create a variable instance"
            )

        instance_id = (
            f"{definition.variable_definition_id}@{scope_value}"
            if scope_value
            else definition.variable_definition_id
        )

        return cls(
            variable_instance_id=instance_id,
            variable_definition_id=definition.variable_definition_id,
            scope_type=scope_type,
            scope_value=scope_value,
        )
