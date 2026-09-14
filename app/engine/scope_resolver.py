"""
Objetivo:
    Resolver a dimensão espacial/organizacional declarada nas
    Definitions e materializar VariableInstance, ParameterInstance
    e EquationInstance.

    O ScopeResolver não trata valores, expressões matemáticas,
    dependências ou períodos temporais.

    Sua responsabilidade é exclusivamente:

        Definition
            ↓
        Scope declarado
            ↓
        Scope concreto
            ↓
        Instance
"""

from app.domain.equations.models import EquationInstance
from app.domain.parameters.models import ParameterInstance
from app.domain.variables.models import VariableInstance


class ScopeResolver:
    """
    Resolve um escopo declarado em uma Definition em uma ou mais Instances.

    O resolver é responsável exclusivamente pela dimensão espacial/
    organizacional. Não trata frequência, período ou cálculo matemático.
    """

    LINE_SCOPES = {
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
    }

    LINE_GROUP_SCOPES = {
        "L1_L3",
        "L4_L5",
        "L6_L7",
        "L1_L7",
    }

    PLANT_SCOPE = "PLANTA"

    def resolve_variable(
        self,
        definition,
    ) -> list[VariableInstance]:
        """
        Resolve o escopo de uma VariableDefinition.

        Retorna uma ou mais VariableInstance.
        """

        scopes = self.resolve_scopes(
            scope_type=definition.scope_type,
            scope_value=definition.scope_value,
        )

        return [
            VariableInstance.create(
                definition=definition,
                scope_type=scope_type,
                scope_value=scope_value,
            )
            for scope_type, scope_value in scopes
        ]

    def resolve_parameter(
        self,
        definition,
    ) -> list[ParameterInstance]:
        """
        Resolve o escopo de uma ParameterDefinition.

        Retorna uma ou mais ParameterInstance.
        """

        scopes = self.resolve_scopes(
            scope_type=definition.scope_type,
            scope_value=definition.scope_value,
        )

        return [
            ParameterInstance.create(
                definition=definition,
                scope_type=scope_type,
                scope_value=scope_value,
            )
            for scope_type, scope_value in scopes
        ]

    def resolve_equation(
        self,
        definition,
    ) -> list[EquationInstance]:
        """
        Resolve o escopo de uma EquationDefinition.

        Retorna uma ou mais EquationInstance.
        """

        scopes = self.resolve_scopes(
            scope_type=definition.scope_type,
            scope_value=definition.scope_value,
        )

        return [
            EquationInstance.create(
                definition=definition,
                scope_type=scope_type,
                scope_value=scope_value,
            )
            for scope_type, scope_value in scopes
        ]

    def resolve_scopes(
        self,
        scope_type: str | None,
        scope_value: str | None,
    ) -> list[tuple[str, str]]:
        """
        Converte uma declaração de escopo em escopos concretos.

        Exemplos:

        linha / L1_L7
            -> L1, L2, L3, L4, L5, L6, L7

        linha_grupo / L1_L3
            -> L1_L3

        linha_grupo / L1_L7
            -> L1_L7

        planta / PLANTA
            -> PLANTA
        """

        if not scope_type:
            raise ValueError(
                "scope_type is required for scope resolution"
            )

        # "área" e "global" são escopos únicos, sem materialização
        # por linha: seu scope_value concreto é sempre None — a
        # ausência de valor não é um erro, mas um valor presente é
        # (mesma exigência que "planta" já faz para "PLANTA").
        # São resolvidos antes da exigência geral de scope_value
        # abaixo, que só se aplica aos scope_types que materializam
        # por linha/grupo/planta.
        if scope_type in {"área", "global"}:
            if scope_value is not None:
                raise ValueError(
                    f"scope_type '{scope_type}' does not accept a "
                    f"concrete scope_value: {scope_value!r}"
                )

            return [
                (scope_type, scope_value),
            ]

        if not scope_value:
            raise ValueError(
                "scope_value is required for scope resolution"
            )

        if scope_type == "linha":
            return self._resolve_line_scope(scope_value)

        if scope_type == "linha_grupo":
            return self._resolve_line_group_scope(scope_value)

        if scope_type == "planta":
            return self._resolve_plant_scope(scope_value)

        raise ValueError(
            f"Unsupported scope_type: {scope_type}"
        )

    def _resolve_line_scope(
        self,
        scope_value: str,
    ) -> list[tuple[str, str]]:
        """
        Resolve um escopo do tipo linha.

        L1       -> [L1]
        L1_L3    -> [L1, L2, L3]
        L1_L7    -> [L1, ..., L7]
        """

        if scope_value in self.LINE_SCOPES:
            return [
                ("linha", scope_value),
            ]

        start, end = self._parse_line_range(scope_value)

        return [
            ("linha", f"L{i}")
            for i in range(start, end + 1)
        ]

    def _resolve_line_group_scope(
        self,
        scope_value: str,
    ) -> list[tuple[str, str]]:
        """
        Resolve um escopo do tipo linha_grupo.

        O grupo permanece como uma única unidade.

        L1_L3 -> [L1_L3]
        L4_L5 -> [L4_L5]
        L6_L7 -> [L6_L7]
        L1_L7 -> [L1_L7]
        """

        if scope_value not in self.LINE_GROUP_SCOPES:
            raise ValueError(
                f"Invalid line group scope_value: {scope_value}"
            )

        return [
            ("linha_grupo", scope_value),
        ]

    def _resolve_plant_scope(
        self,
        scope_value: str,
    ) -> list[tuple[str, str]]:
        """
        Resolve o escopo de planta.
        """

        if scope_value != self.PLANT_SCOPE:
            raise ValueError(
                f"Invalid plant scope_value: {scope_value}"
            )

        return [
            ("planta", self.PLANT_SCOPE),
        ]

    @staticmethod
    def _parse_line_range(
        scope_value: str,
    ) -> tuple[int, int]:
        """
        Converte, por exemplo, L1_L7 em (1, 7).
        """

        try:
            start, end = scope_value.split("_")
            start_number = int(start[1:])
            end_number = int(end[1:])
        except (ValueError, IndexError):
            raise ValueError(
                f"Invalid line range: {scope_value}"
            ) from None

        if start_number > end_number:
            raise ValueError(
                f"Invalid line range: {scope_value}"
            )

        if not (
            1 <= start_number <= 7
            and 1 <= end_number <= 7
        ):
            raise ValueError(
                f"Line range outside supported lines: "
                f"{scope_value}"
            )

        return start_number, end_number
