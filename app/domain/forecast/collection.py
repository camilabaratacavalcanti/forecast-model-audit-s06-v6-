"""
Coleção mínima de ForecastValue produzidos durante uma execução
(Fase C), evoluída (Fase C — TD-C01/TD-C02/TD-C03) para representar
o ESTADO VIGENTE de cada identidade lógica, preservando em histórico
o valor que cada atualização substituiu.

Não é um Repository: não persiste nada, não conhece Azure/SQL/Cosmos,
não sobrevive ao processo. É um container em memória cuja
responsabilidade é:

    - manter, para cada `ForecastValue.identity()`, o valor vigente
      (o resultado mais recentemente registrado);
    - preservar em histórico o valor anterior sempre que uma nova
      Execution substitui o vigente (mesma identidade, execution_id
      diferente do que produziu o vigente atual) — é o ponto
      explícito onde uma persistência real (com histórico durável)
      se conectaria no futuro, sem que o Temporal Forecast
      Orchestrator precise saber nada sobre isso.

Este módulo não implementa Execution nem decide quando uma Execution
deve substituir outra — apenas reage ao que já foi calculado e
entregue a `add()`.
"""

from dataclasses import dataclass
from datetime import date

from app.domain.forecast.models import ForecastValue


class ConflictingForecastValueError(ValueError):
    """
    A mesma Execution (mesmo `execution_id`) tentou produzir dois
    valores DIFERENTES para a mesma identidade lógica de
    ForecastValue.

    Diferente de uma nova Execution atualizando o vigente (sempre
    permitido, ver TD-C01), isto é sinal de um erro do chamador — um
    cálculo não-determinístico, ou duas chamadas indevidas
    reaproveitando a mesma Execution para recalcular a mesma
    identidade — e nunca é resolvido silenciosamente (nem
    sobrescrevendo, nem arquivando em histórico): a segunda adição é
    rejeitada e o estado (vigente e histórico) permanece intacto.

    Definida aqui, no domínio, e não em `app.engine.exceptions`,
    pelo mesmo motivo já registrado para `ForecastValueRegistry`
    (TD-C05 / Fase C): um modelo de domínio não deve depender do
    engine. Herda de `ValueError` para permanecer compatível com
    qualquer código que já capture `ValueError` genericamente.
    """


@dataclass(frozen=True)
class ForecastValueHistoryEntry:
    """
    Um registro do que um ForecastValue vigente ERA antes de ser
    substituído — não é um novo modelo genérico de auditoria, é
    apenas os quatro dados mínimos necessários para responder "o que
    mudou, quem produziu e quando": a identidade lógica que foi
    superada, o valor que ela tinha, e a proveniência
    (execution_id/run_date) de quem a produziu.
    """

    identity: tuple
    value: int | float
    execution_id: str | None
    run_date: date | None

    @classmethod
    def from_forecast_value(
        cls,
        forecast_value: ForecastValue,
    ) -> "ForecastValueHistoryEntry":
        return cls(
            identity=forecast_value.identity(),
            value=forecast_value.value,
            execution_id=forecast_value.execution_id,
            run_date=forecast_value.run_date,
        )


class ForecastValueRegistry:
    """
    Registry em memória de ForecastValue, indexado por
    `ForecastValue.identity()`, representando apenas o estado
    VIGENTE de cada identidade — não um histórico completo por si
    só (ver `history()` para o histórico de substituições).

    Regra de atualização (TD-C01/TD-C04):

        A. identidade nova (nunca vista): vira o vigente, sem
           histórico.
        B. identidade já vigente, MESMO execution_id, MESMO valor:
           re-adição redundante (ex.: o mesmo resultado entregue
           duas vezes pelo chamador) — no-op, sem entrada de
           histórico, sem reatribuir o vigente.
        C. identidade já vigente, execution_id DIFERENTE (valor
           igual ou diferente, tanto faz): uma nova Execution está
           substituindo o vigente anterior — o valor anterior (com
           seu execution_id/run_date originais) é arquivado em
           `history()` ANTES de o novo valor se tornar vigente. Vale
           mesmo quando o valor numérico não muda (duas execuções
           podem legitimamente produzir o mesmo número) — o que
           importa para o histórico é a proveniência, não apenas o
           valor.
        D. identidade já vigente, MESMO execution_id, valor
           DIFERENTE: a mesma Execution está tentando produzir dois
           valores diferentes para a mesma identidade — isto é um
           erro do chamador, nunca resolvido silenciosamente.
           Levanta `ConflictingForecastValueError`; nem o vigente
           nem o histórico são alterados.

    Uma nova Execution (caso C) nunca levanta erro: atualizar o
    vigente com um novo valor, vindo de uma Execution diferente da
    que produziu o vigente atual, é o comportamento correto e
    esperado de um forecast progressivo.
    """

    def __init__(self):
        self._current: dict[tuple, ForecastValue] = {}
        self._history: dict[
            tuple, list[ForecastValueHistoryEntry]
        ] = {}

    def add(self, value: ForecastValue) -> None:
        key = value.identity()
        existing = self._current.get(key)

        if existing is not None:
            if existing.execution_id == value.execution_id:
                if existing.value != value.value:
                    raise ConflictingForecastValueError(
                        f"A Execution {value.execution_id!r} tentou "
                        "produzir dois valores diferentes para a "
                        f"mesma identidade {key}: "
                        f"{existing.value!r} e {value.value!r}."
                    )

                # Caso B: mesmo execution_id, mesmo valor -> no-op.
                return

            # Caso C: execution_id diferente -> arquiva o vigente
            # anterior antes de substituí-lo.
            self._history.setdefault(key, []).append(
                ForecastValueHistoryEntry.from_forecast_value(
                    existing
                )
            )

        self._current[key] = value

    def get(self, identity: tuple) -> ForecastValue:
        """Retorna o valor VIGENTE para a identidade informada."""

        return self._current[identity]

    def history(
        self,
        identity: tuple,
    ) -> list[ForecastValueHistoryEntry]:
        """
        Retorna os valores substituídos para a identidade informada,
        em ordem cronológica (o mais antigo primeiro). Vazio quando
        a identidade nunca foi atualizada mais de uma vez (ou nunca
        existiu).
        """

        return list(self._history.get(identity, []))

    def all(self) -> list[ForecastValue]:
        """Retorna todos os valores VIGENTES (não o histórico)."""

        return list(self._current.values())

    def __len__(self) -> int:
        return len(self._current)

    def __iter__(self):
        return iter(self._current.values())
