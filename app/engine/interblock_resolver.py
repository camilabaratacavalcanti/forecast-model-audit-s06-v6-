"""
Resolução de valores interbloco em runtime (Etapa 3.1).

    Seeds
      -> entidades locais (VariableDefinition / CalculationContext)
      -> vínculos canônicos (InterblockLinkRegistry)
      -> lookup do valor produzido
      -> consumo pela variável de entrada do bloco consumidor

O resolver reutiliza o `CalculationContext` existente: o valor do
produtor é lido na chave (source_definition_id, scope_type, scope_value,
period_id) e, na transferência, gravado na chave do consumidor com a
MESMA instância e o MESMO período. O consumidor continua sendo a sua
própria entidade (ID próprio); o motor de equações segue lendo o ID do
consumidor como sempre — nada nele é alterado.

Regras (contratos 2.4 / 2.5B / 2.6C, sem reabrir nenhum):

    - só vínculos da seção `links` do artefato canônico participam;
    - instância exatamente a do vínculo (sem L3 -> L1, sem L1_L7);
    - período exatamente o pedido, com a granularidade da frequência do
      vínculo (sem fallback nem conversão temporal entre blocos);
    - valor transportado sem conversão de unidade nem transformação;
    - vínculo pendente (bloco não carregado) ou rejeitado é erro
      explícito; nunca zero, None, valor local, outro bloco ou
      `source_reference`;
    - cadeias (A <- B <- C) são percorridas por transferências
      sucessivas na ordem topológica do registro, cada salto com as
      identidades próprias.

Etapa 3.3A: o que é transportado é o resultado canônico
(`app.domain.results.Result`: value, state, detail), inteiro e sem
alteração — nenhum recálculo, conversão, inferência ou descarte de
state/detail. `resolve`/`transfer` continuam devolvendo o valor
(compatibilidade 3.1); `resolve_result`/`transfer_result` devolvem o
resultado completo. O conflito com um valor já presente no consumidor
compara o resultado completo.
"""

from __future__ import annotations

from app.domain.interblock.models import InterblockLink
from app.domain.interblock.registry import InterblockLinkRegistry
from app.domain.results import Result, scalar_of
from app.domain.values import ScalarValue
from app.engine.calculation_context import CalculationContext
from app.engine.exceptions import (
    InterblockConsumerValueConflictError,
    InterblockInstanceNotDeclaredError,
    InterblockLinkNotFoundError,
    InterblockLinkRejectedError,
    InterblockPeriodFrequencyMismatchError,
    InterblockSourceNotLoadedError,
    InterblockSourceValueNotFoundError,
    VariableNotFoundError,
)


# Convenção de period_id já usada pelo runtime (ExpressionEvaluator,
# TimePeriodResolver): diário YYYY-MM-DD, mensal YYYY-MM, anual YYYY.
PERIOD_LENGTH = {"diário": 10, "mensal": 7, "anual": 4}

_MISSING = object()


class InterblockValueResolver:
    def __init__(
        self,
        registry: InterblockLinkRegistry,
        calculation_context: CalculationContext,
    ):
        self.registry = registry
        self.calculation_context = calculation_context

    # --------------------------------------------------------
    # Vínculo do consumidor
    # --------------------------------------------------------

    def link_for(self, consumer_definition_id: str) -> InterblockLink:
        link = self.registry.link_for(consumer_definition_id)

        if link is not None:
            return link

        pending = self.registry.pending_for(consumer_definition_id)

        if pending is not None:
            raise InterblockSourceNotLoadedError(
                f"consumidor {pending.consumer_block}.{pending.consumer_name} "
                f"({consumer_definition_id}, {pending.consumer_frequency} "
                f"{pending.consumer_scope_type}/{pending.consumer_scope_value}) "
                f"depende do bloco '{pending.source_block}', cujo workbook não está "
                "carregado: não há produtor nem valor.",
                consumer_block=pending.consumer_block,
                consumer_definition_id=consumer_definition_id,
                consumer_name=pending.consumer_name,
                source_block=pending.source_block,
                frequency=pending.consumer_frequency,
                scope=(pending.consumer_scope_type, pending.consumer_scope_value),
            )

        rejected = self.registry.rejected_for(consumer_definition_id)

        if rejected is not None:
            raise InterblockLinkRejectedError(
                f"consumidor {rejected.consumer_block} {consumer_definition_id}: vínculo "
                f"com '{rejected.source_block}' reprovado no build {list(rejected.error_codes)}.",
                consumer_block=rejected.consumer_block,
                consumer_definition_id=consumer_definition_id,
                source_block=rejected.source_block,
            )

        raise InterblockLinkNotFoundError(
            f"{consumer_definition_id} não é consumidor de nenhum vínculo interbloco canônico.",
            consumer_definition_id=consumer_definition_id,
        )

    # --------------------------------------------------------
    # Lookup e transferência
    # --------------------------------------------------------

    def resolve(
        self,
        consumer_definition_id: str,
        scope_type: str,
        scope_value: str | None,
        period_id: str | None = None,
    ) -> ScalarValue:
        """
        Valor produzido para exatamente (instância, período) do consumidor.
        Nunca lê o valor do próprio consumidor.
        """

        return scalar_of(
            self.resolve_result(consumer_definition_id, scope_type, scope_value, period_id),
            f"{consumer_definition_id} ({scope_type}/{scope_value}, period_id={period_id})",
        )

    def resolve_result(
        self,
        consumer_definition_id: str,
        scope_type: str,
        scope_value: str | None,
        period_id: str | None = None,
    ) -> Result:
        """
        Resultado canônico do produtor (value, state, detail) para
        exatamente (instância, período) do consumidor.
        """

        link = self.link_for(consumer_definition_id)
        details = dict(
            consumer_block=link.consumer_block,
            consumer_definition_id=consumer_definition_id,
            source_block=link.source_block,
            source_definition_id=link.source_definition_id,
            instance=(scope_type, scope_value),
            frequency=link.frequency,
            period_id=period_id,
        )

        if not link.declares(scope_type, scope_value):
            raise InterblockInstanceNotDeclaredError(
                f"{link.consumer_block} {consumer_definition_id}: instância "
                f"{scope_type}/{scope_value} não pertence ao vínculo com "
                f"{link.source_block} {link.source_definition_id} "
                f"(instâncias {[v for _t, v in link.instances]}).",
                **details,
            )

        expected = PERIOD_LENGTH.get(link.frequency)

        if period_id is not None and (expected is None or len(period_id) != expected):
            raise InterblockPeriodFrequencyMismatchError(
                f"{link.consumer_block} {consumer_definition_id}: period_id {period_id!r} "
                f"não tem a granularidade da frequência '{link.frequency}' do vínculo.",
                **details,
            )

        try:
            return self.calculation_context.get_variable_result(
                link.source_definition_id,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=period_id,
            )
        except VariableNotFoundError as error:
            raise InterblockSourceValueNotFoundError(
                f"{link.consumer_block} {consumer_definition_id} <- {link.source_block} "
                f"{link.source_definition_id}: produtor sem valor em "
                f"{scope_type}/{scope_value}, period_id={period_id!r} "
                "(sem fallback entre blocos).",
                **details,
            ) from error

    def transfer(
        self,
        consumer_definition_id: str,
        scope_type: str,
        scope_value: str | None,
        period_id: str | None = None,
    ) -> ScalarValue:
        """
        Grava no consumidor, na mesma instância e período, o resultado do
        produtor e devolve o valor. Ver `transfer_result`.
        """

        return scalar_of(
            self.transfer_result(consumer_definition_id, scope_type, scope_value, period_id),
            f"{consumer_definition_id} ({scope_type}/{scope_value}, period_id={period_id})",
        )

    def transfer_result(
        self,
        consumer_definition_id: str,
        scope_type: str,
        scope_value: str | None,
        period_id: str | None = None,
    ) -> Result:
        """
        Grava no consumidor, na mesma instância e período, o resultado
        canônico do produtor (value, state, detail), sem alteração. Um
        resultado local diferente já presente é conflito.
        """

        value = self.resolve_result(consumer_definition_id, scope_type, scope_value, period_id)
        existing = self._existing(consumer_definition_id, scope_type, scope_value, period_id)

        if existing is not _MISSING and existing != value:
            link = self.registry.link_for(consumer_definition_id)
            raise InterblockConsumerValueConflictError(
                f"{link.consumer_block} {consumer_definition_id} já tem {existing!r} em "
                f"{scope_type}/{scope_value}, period_id={period_id!r}; o produtor "
                f"{link.source_block} {link.source_definition_id} tem {value!r}.",
                consumer_block=link.consumer_block,
                consumer_definition_id=consumer_definition_id,
                source_block=link.source_block,
                instance=(scope_type, scope_value),
                period_id=period_id,
            )

        self.calculation_context.set_variable_result(
            consumer_definition_id,
            value,
            scope_type=scope_type,
            scope_value=scope_value,
            period_id=period_id,
        )

        return value

    def transfer_link(
        self,
        consumer_definition_id: str,
        period_id: str | None = None,
    ) -> dict[tuple[str, str | None], ScalarValue]:
        """Todas as instâncias validadas de um vínculo, para um período."""

        link = self.link_for(consumer_definition_id)

        return {
            instance: self.transfer(consumer_definition_id, *instance, period_id)
            for instance in link.instances
        }

    def transfer_all(
        self,
        period_ids: dict[str, str | None],
    ) -> list[tuple[str, tuple[str, str | None], str | None, ScalarValue]]:
        """
        Todos os vínculos válidos, na ordem topológica do registro
        (produtor antes do consumidor: cadeias A <- B <- C). `period_ids`
        informa o period_id de cada frequência presente; frequência sem
        período informado é erro explícito (KeyError), nunca default.
        """

        transferred = []

        for link in self.registry.links():
            period_id = period_ids[link.frequency]

            for instance in link.instances:
                # Etapa 3.3B: o Result inteiro é gravado no consumidor; a
                # lista devolve o valor (None quando o resultado só tem estado).
                result = self.transfer_result(link.consumer_definition_id, *instance, period_id)
                transferred.append((link.consumer_definition_id, instance, period_id, result.value))

        return transferred

    def _existing(self, variable_id, scope_type, scope_value, period_id):
        try:
            return self.calculation_context.get_variable_result(
                variable_id,
                scope_type=scope_type,
                scope_value=scope_value,
                period_id=period_id,
            )
        except VariableNotFoundError:
            return _MISSING


__all__ = ["InterblockValueResolver", "PERIOD_LENGTH"]
