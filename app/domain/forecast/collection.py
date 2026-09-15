"""
Coleção mínima de ForecastValue produzidos durante uma execução (Fase C).

Não é um Repository: não persiste nada, não conhece Azure/SQL/Cosmos,
não sobrevive ao processo. É um container em memória cuja única
responsabilidade é reunir os ForecastValue produzidos (DIRECT e
TEMPORAL_AGGREGATED) sob uma mesma estrutura, detectando identidade
duplicada — o ponto explícito onde uma persistência real se
conectaria no futuro, sem que o Temporal Forecast Orchestrator
precise saber nada sobre isso.
"""

from app.domain.forecast.models import ForecastValue


class ForecastValueRegistry:
    """
    Registry em memória de ForecastValue, indexado por
    `ForecastValue.identity()`.

    Duas adições com a MESMA identidade e o MESMO valor são
    idempotentes (recalcular o mesmo período não é um erro — é o
    comportamento esperado de uma reexecução, ver
    `ForecastValue.__doc__`). Duas adições com a mesma identidade e
    valores DIFERENTES indicam um conflito real (ex.: um recálculo
    não-determinístico, ou dois resultados de regras diferentes
    colidindo por engano) e são rejeitadas explicitamente.
    """

    def __init__(self):
        self._values: dict[tuple, ForecastValue] = {}

    def add(self, value: ForecastValue) -> None:
        key = value.identity()
        existing = self._values.get(key)

        if existing is not None and existing.value != value.value:
            raise ValueError(
                "ForecastValue duplicado com valor conflitante "
                f"para a identidade {key}: "
                f"existente={existing.value}, novo={value.value}"
            )

        self._values[key] = value

    def get(self, identity: tuple) -> ForecastValue:
        return self._values[identity]

    def all(self) -> list[ForecastValue]:
        return list(self._values.values())

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values.values())
