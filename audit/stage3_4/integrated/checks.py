"""
Stage 3.4C — verificações puras (sem importar `app`), usadas pelo driver e
pelos testes negativos. Toda função devolve uma lista de problemas; lista
vazia = verificação satisfeita.

Formato de resultado: [tipo, repr, state, detail]  (igualdade exata).
Chave de contexto:     (entity_id, scope_type, scope_value, period_id, window_end).
"""

from __future__ import annotations


def check_targets(expected: dict, observed: dict) -> list[str]:
    """
    expected: {target: {(scope_type, scope_value), ...}} — instâncias esperadas.
    observed: {date: {target: {(scope_type, scope_value), ...}}} — gravadas por dia.
    Cada alvo precisa ter TODAS as instâncias gravadas em TODAS as datas.
    """
    problems = []
    for day in sorted(observed):
        seen = observed[day]
        for target in sorted(expected):
            got = seen.get(target, set())
            if got != expected[target]:
                missing = sorted(expected[target] - got)
                problems.append(f"TARGET_NOT_EXECUTED {day} {target}: faltam {missing[:3]}")
        for extra in sorted(set(seen) - set(expected)):
            problems.append(f"TARGET_OUTSIDE_UNIVERSE {day} {extra}")
    return problems


def check_nodes(planned: list[str], expected_events: dict, executed: dict) -> list[str]:
    """
    planned: chaves de nó do plano, na ordem do planner.
    expected_events: {node_key: nº de instâncias que o nó grava}.
    executed: {date: [(node_key, n_events), ...] na ordem de execução}.
    Detecta nó só no plano, nó só na execução, contagem e ordem divergentes.
    """
    problems = []
    for day in sorted(executed):
        order = [key for key, _n in executed[day]]
        counts = dict(executed[day])
        for key in sorted(set(planned) - set(order)):
            problems.append(f"PLANNER_ONLY_NODE {day} {key}")
        for key in sorted(set(order) - set(planned)):
            problems.append(f"ENGINE_ONLY_NODE {day} {key}")
        if len(order) != len(set(order)):
            problems.append(f"NODE_EXECUTED_TWICE {day}")
        if [k for k in planned if k in counts] != order:
            problems.append(f"NODE_ORDER_DIFFERS_FROM_PLAN {day}")
        for key in sorted(set(planned) & set(order)):
            if counts[key] != expected_events[key]:
                problems.append(f"NODE_EVENT_COUNT {day} {key}: {counts[key]} != {expected_events[key]}")
    return problems


def check_transfers(records: list[dict], expected_nodes: set[str]) -> list[str]:
    """
    records: {date, node, instance, period, window, producer, consumer} por
    evento de transferência. Consumidor == produtor (value, state, detail) na
    mesma identidade temporal; cada transferência esperada executada.
    """
    problems = []
    for record in records:
        if record["producer"] is None or record["consumer"] is None:
            problems.append(f"INTERBLOCK_FAILURE {record['date']} {record['node']} {record['instance']}: resultado ausente")
        elif record["producer"] != record["consumer"]:
            problems.append(f"INTERBLOCK_FAILURE {record['date']} {record['node']} {record['instance']}: "
                            f"{record['consumer']} != produtor {record['producer']}")
    executed = {record["node"] for record in records}
    for node in sorted(expected_nodes - executed):
        problems.append(f"INTERBLOCK_FAILURE transferência não executada: {node}")
    return problems


def check_state_diff(clean: dict, stated: dict, descendants: set[str], state: str, detail) -> list[str]:
    """
    Oráculo de propagação por diferença entre execuções gêmeas (mesmas
    entradas; a execução `stated` só acrescenta a injeção):
      * mesmas chaves nos dois contextos;
      * chave igual nos dois -> não afetada;
      * chave diferente -> precisa ter exatamente o estado/detail injetado
        e pertencer a uma variável descendente da origem (grafo do planner).
    """
    problems = []
    for key in sorted(set(clean) | set(stated), key=repr):
        a, b = clean.get(key), stated.get(key)
        if a is None or b is None:
            problems.append(f"STATE_DIFFERENCE chave presente só em um lado: {key}")
        elif a != b:
            if key[0] not in descendants:
                problems.append(f"STATE_DIFFERENCE vazamento para não-descendente {key}: {b}")
            elif (b[2], b[3]) != (state, detail):
                problems.append(f"STATE_DIFFERENCE {key}: {b[2:]} != {(state, detail)}")
    return problems


def check_expectations(store: dict, stated_keys, plain_keys, state: str, detail) -> list[str]:
    """Casos nomeados: estas chaves precisam ter o estado; aquelas, não ter estado."""
    problems = []
    for key in stated_keys:
        got = store.get(key)
        if got is None or (got[2], got[3]) != (state, detail):
            problems.append(f"STATE_DIFFERENCE esperado {state}/{detail} em {key}, obtido {got}")
    for key in plain_keys:
        got = store.get(key)
        if got is None or got[2] is not None or got[3] is not None:
            problems.append(f"STATE_DIFFERENCE esperado sem estado em {key}, obtido {got}")
    return problems
