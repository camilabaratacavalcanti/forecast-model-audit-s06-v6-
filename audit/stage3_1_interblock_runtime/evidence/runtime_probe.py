"""
Etapa 3.1 — sonda de caixa-preta do runtime interbloco.

Executada em subprocesso por `analysis_stage3_1.py` (que não importa o
runtime). Recebe em stdin um JSON com os valores a gravar no contexto
({"values": [[entity_id, scope_type, scope_value, period_id, value], ...],
"periods": {freq: period_id}, "pending_probes": [[consumer_id, scope_type,
scope_value, period_id], ...]}), executa `transfer_all` e devolve em
stdout o valor que cada consumidor recebeu e o código de erro de cada
pendência sondada.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.engine.calculation_context import CalculationContext  # noqa: E402
from app.engine.exceptions import InterblockRuntimeError  # noqa: E402
from app.engine.interblock_resolver import InterblockValueResolver  # noqa: E402
from app.repositories.seed_loader import SeedLoader  # noqa: E402

request = json.load(sys.stdin)
registry = SeedLoader(REPO / "data" / "seed").load_interblock_links()
context = CalculationContext()
for entity_id, scope_type, scope_value, period_id, value in request["values"]:
    context.set_variable_value(entity_id, value, scope_type, scope_value, period_id)

resolver = InterblockValueResolver(registry, context)
received = [
    [consumer, instance[0], instance[1], period_id, value]
    for consumer, instance, period_id, value in resolver.transfer_all(request["periods"])
]
pending = []
for consumer, scope_type, scope_value, period_id in request["pending_probes"]:
    try:
        resolver.resolve(consumer, scope_type, scope_value, period_id)
        pending.append([consumer, "NO_ERROR"])
    except InterblockRuntimeError as error:
        pending.append([consumer, error.code])

json.dump({"received": received, "pending": pending}, sys.stdout)
