from app.domain.equations.models import (
    Equation,
    EquationDefinition,
)
from app.domain.equations.registry import (
    EquationDefinitionRegistry,
    EquationRegistry,
)


class EquationSelector:
    """
    Responsável por selecionar a definição ou equação aplicável
    a partir de um Registry.

    Mantém compatibilidade com o EquationRegistry legado e
    disponibiliza seleção sobre o EquationDefinitionRegistry.

    A seleção não executa a expressão matemática.
    """

    PUBLISHED_STATUS = "PUBLISHED"
    ACTIVE_STATUSES = {
        "PUBLISHED",
        "ativo",
        "active",
    }

    def __init__(
        self,
        equation_registry: EquationRegistry
        | EquationDefinitionRegistry,
    ):
        self.equation_registry = equation_registry

    # ========================================================
    # LEGACY — Equation
    # ========================================================

    def select(
        self,
        equation_id: str,
        version: int | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> Equation:
        """
        Seleciona uma equação PUBLISHED.

        Quando version não é informada, seleciona a maior
        versão PUBLISHED compatível com o escopo.

        Este método preserva o contrato legado existente.
        """

        candidates = [
            equation
            for equation in self.equation_registry.all()
            if equation.equation_id == equation_id
            and equation.status == self.PUBLISHED_STATUS
        ]

        candidates = self._filter_scope(
            candidates,
            scope_type,
            scope_value,
        )

        if version is not None:
            candidates = [
                equation
                for equation in candidates
                if equation.version == version
            ]

        if not candidates:
            raise ValueError(
                "Nenhuma equação PUBLISHED encontrada para "
                f"equation_id={equation_id}, "
                f"version={version}, "
                f"scope_type={scope_type}, "
                f"scope_value={scope_value}."
            )

        return max(
            candidates,
            key=lambda equation: equation.version,
        )

    # ========================================================
    # NEW — EquationDefinition
    # ========================================================

    def select_definition(
        self,
        equation_definition_id: str,
        version: int | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> EquationDefinition:
        """
        Seleciona uma EquationDefinition aplicável.

        Regras:

        1. O identificador deve existir.
        2. Apenas definições em status selecionável podem ser usadas.
        3. Se version for informada, somente aquela versão é considerada.
        4. Se version não for informada, a maior versão é selecionada.
        5. O escopo informado deve ser respeitado.
        6. Se houver mais de uma definição igualmente aplicável,
           a seleção é considerada ambígua.
        """

        if not isinstance(
            self.equation_registry,
            EquationDefinitionRegistry,
        ):
            raise TypeError(
                "select_definition requer "
                "EquationDefinitionRegistry."
            )

        if not equation_definition_id:
            raise ValueError(
                "equation_definition_id é obrigatório."
            )

        candidates = [
            definition
            for definition in self.equation_registry.all()
            if (
                definition.equation_definition_id
                == equation_definition_id
            )
            and (
                definition.status
                in self.ACTIVE_STATUSES
            )
        ]

        candidates = self._filter_scope(
            candidates,
            scope_type,
            scope_value,
        )

        if version is not None:
            candidates = [
                definition
                for definition in candidates
                if definition.version == version
            ]

        if not candidates:
            raise ValueError(
                "Nenhuma EquationDefinition selecionável "
                "encontrada para "
                f"equation_definition_id="
                f"{equation_definition_id}, "
                f"version={version}, "
                f"scope_type={scope_type}, "
                f"scope_value={scope_value}."
            )

        highest_version = max(
            definition.version
            for definition in candidates
        )

        highest_version_candidates = [
            definition
            for definition in candidates
            if definition.version == highest_version
        ]

        if len(highest_version_candidates) > 1:
            raise ValueError(
                "EquationDefinition ambígua. "
                "Informe version e/ou scope."
            )

        return highest_version_candidates[0]

    # ========================================================
    # INTERNAL
    # ========================================================

    @staticmethod
    def _filter_scope(
        candidates,
        scope_type: str | None,
        scope_value: str | None,
    ):
        """
        Filtra candidatos pelo escopo informado.

        O método é compartilhado entre Equation e
        EquationDefinition.
        """

        if scope_type is not None:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.scope_type == scope_type
            ]

        if scope_value is not None:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.scope_value == scope_value
            ]

        return candidates
