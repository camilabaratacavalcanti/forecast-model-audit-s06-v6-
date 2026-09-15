"""
Representa uma Execution: uma rodada de cálculo do forecast,
identificada por um `run_date`, contextualizada por um `ForecastYear`
e uma versão de modelo, com um ciclo de vida mínimo:

    RUNNING -> COMPLETED
    RUNNING -> FAILED

Uma Execution "produz" um ou mais ForecastValue (DIRECT e/ou
TEMPORAL_AGGREGATED) por convenção, não por referência de objeto:
`ForecastValue.execution_id` aponta para o `execution_id` de quem o
produziu. Uma única Execution pode produzir muitos ForecastValues
(ex.: as 166 EquationInstances calculadas por uma única chamada de
`run_direct`, ou vários `run_aggregation` sucessivos feitos sob a
mesma rodada).

`forecast_year` nunca é informado de forma independente de forma que
permita inconsistência: é sempre derivado de `run_date` (o mesmo
`forecast_year = run_date.year` já estabelecido por `RunContext` na
Fase A — reaproveitado aqui como regra, não como import: `Execution`
é um modelo de domínio, e `RunContext` vive em `app/engine/`; importar
uma classe do engine dentro do domínio repetiria o mesmo desvio de
camadas já registrado como TD-B02 na Fase B, para economizar uma
única linha de código). Essa consistência é validada estruturalmente
em `__post_init__` para qualquer caminho de construção — não apenas
pela fábrica `start()`.

Não é um modelo de persistência: não é gravado em nenhum repositório,
banco ou Azure. Vive inteiramente na memória de quem a criou.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import date


EXECUTION_STATUSES = {"RUNNING", "COMPLETED", "FAILED"}


@dataclass(frozen=True)
class Execution:
    """
    Imutável, como os demais modelos de domínio da plataforma.
    Transições de status (`complete()`/`fail()`) devolvem uma NOVA
    Execution — não mutam a instância original.
    """

    execution_id: str
    run_date: date
    forecast_year: int
    model_version: str
    status: str

    def __post_init__(self) -> None:
        if self.forecast_year != self.run_date.year:
            raise ValueError(
                "forecast_year deve ser derivado de run_date "
                f"({self.run_date.year}); recebido "
                f"{self.forecast_year}."
            )

        if self.status not in EXECUTION_STATUSES:
            raise ValueError(
                f"Status de Execution não suportado: {self.status}"
            )

    @classmethod
    def start(
        cls,
        run_date: date,
        model_version: str = "v1",
        execution_id: str | None = None,
    ) -> "Execution":
        """
        Cria uma nova Execution em status RUNNING para `run_date`.

        `execution_id`, quando omitido, é gerado automaticamente
        (uuid4) — não depende de Azure, Repository ou qualquer
        infraestrutura externa, e não segue nenhuma convenção de ID
        determinística preexistente na plataforma (os IDs de
        Instance, por comparação, são determinísticos porque
        derivam de uma chave de negócio; uma Execution não tem
        chave de negócio natural, já que o mesmo run_date pode ter
        múltiplas execuções distintas). Pode ser informado
        explicitamente (ex.: em testes) quando um identificador
        específico for necessário.
        """

        forecast_year = run_date.year

        return cls(
            execution_id=(
                execution_id or f"EXEC-{uuid.uuid4().hex[:12]}"
            ),
            run_date=run_date,
            forecast_year=forecast_year,
            model_version=model_version,
            status="RUNNING",
        )

    def complete(self) -> "Execution":
        return self._transition("COMPLETED")

    def fail(self) -> "Execution":
        return self._transition("FAILED")

    def _transition(self, target_status: str) -> "Execution":
        if self.status != "RUNNING":
            raise ValueError(
                f"Não é possível transicionar de '{self.status}' "
                f"para '{target_status}': apenas uma Execution em "
                "RUNNING pode ser concluída ou falhar."
            )

        return replace(self, status=target_status)
