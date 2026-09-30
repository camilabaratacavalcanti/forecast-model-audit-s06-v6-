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


def check_transfers(records: list[dict], expected_nodes: set[str], expected: dict | None = None) -> list[str]:
    """
    records: {date, node, instance, period, producer, consumer[, block, source_block]} por
    evento de transferência. Consumidor == produtor (value, state, detail) na
    mesma identidade temporal; cada transferência esperada executada.
    expected (Stage 3.4D): {node: {"instances": {instance, ...}, "consumer_block": b,
    "source_block": b}} — cada nó grava exatamente suas instâncias, uma vez por
    data, no bloco consumidor do vínculo.
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
    if expected is None:
        return problems
    seen: dict = {}
    for record in records:
        identity = (record["date"], record["node"], record["instance"], record["period"])
        if identity in seen:
            problems.append(f"INTERBLOCK_FAILURE transferência duplicada {identity}")
        seen[identity] = record
        link = expected.get(record["node"])
        if link is None:
            problems.append(f"INTERBLOCK_FAILURE transferência fora do plano {record['node']}")
            continue
        for field, key in (("block", "consumer_block"), ("source_block", "source_block")):
            if field in record and record[field] != link[key]:
                problems.append(f"INTERBLOCK_FAILURE {record['date']} {record['node']} {record['instance']}: "
                                f"{field} {record[field]} != {link[key]}")
    for day in sorted({r["date"] for r in records}):
        for node, link in sorted(expected.items()):
            got = {r["instance"] for r in records if r["date"] == day and r["node"] == node}
            if got != link["instances"]:
                problems.append(f"INTERBLOCK_FAILURE {day} {node}: instâncias {sorted(got)} != {sorted(link['instances'])}")
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
            elif b[:2] != ["NoneType", "None"]:
                # Stage 3.4D: a origem injetada é state-only (value None); propagação causal
                # (3.3B) e Policy B (3.3C) não podem produzir valor junto com o estado.
                problems.append(f"STATE_DIFFERENCE {key}: valor {b[:2]} num resultado que deve ser state-only")
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


# ------------------------------------------------------------------ Stage 3.4D
def check_target_identities(records: list, expected_period: dict) -> list[str]:
    """
    records: [(date, variable, scope_type, scope_value, period_id)] dos eventos que gravam alvos.
    expected_period: {(variable, date): period_id} (frequência da definição x data).
    Cada instância de alvo é gravada UMA vez por data, na identidade temporal da data.
    """
    problems, seen = [], set()
    for day, variable, st, sv, period in records:
        identity = (day, variable, st, sv)
        if identity in seen:
            problems.append(f"TARGET_DUPLICATED {day} {variable} {st}/{sv}")
        seen.add(identity)
        want = expected_period.get((variable, day))
        if want is not None and period != want:
            problems.append(f"TARGET_WRONG_PERIOD {day} {variable} {st}/{sv}: {period} != {want}")
    return problems


def _kind(period) -> str | None:
    return {10: "daily", 7: "monthly", 4: "annual"}.get(len(period or ""))


def check_temporal(store: dict, january_snapshot: dict, days: list[str], derived: set[str]) -> tuple[dict, list[str]]:
    """
    Identidade temporal das variáveis DERIVADAS (produzidas por nós do plano):
      * diária: chave sem window_end;
      * mensal/anual: toda chave tem window_end, pertencente ao período da chave;
      * janelas mensais de janeiro = exatamente os 31 dias; de fevereiro = {2026-02-01};
        anuais = exatamente as datas executadas (YTD parcial);
      * janelas de janeiro inalteradas depois de 2026-02-01 (sem contaminação).
    """
    problems = []
    windows: dict = {}
    for k in store:
        if k[0] in derived:
            windows.setdefault(k[:4], set()).add(k[4])
    jan_days = {d for d in days if d.startswith("2026-01")}
    counts = {"monthly_jan": 0, "monthly_feb": 0, "annual": 0}
    for (entity, st, sv, period), ws in sorted(windows.items(), key=repr):
        kind = _kind(period)
        if kind == "daily":
            if ws != {None}:
                problems.append(f"TEMPORAL_FAILURE chave diária com janela {entity} {st}/{sv} {period} {sorted(map(str, ws))}")
            continue
        if None in ws:
            problems.append(f"TEMPORAL_FAILURE identidade {kind} sem janela {entity} {st}/{sv} {period}")
        bad = sorted(w for w in ws if w is not None and not w.startswith(period))
        if bad:
            problems.append(f"TEMPORAL_FAILURE janela fora do período {entity} {st}/{sv} {period} {bad}")
        if kind == "monthly" and period == "2026-01":
            counts["monthly_jan"] += 1
            want = jan_days
        elif kind == "monthly" and period == "2026-02":
            counts["monthly_feb"] += 1
            want = {d for d in days if d.startswith("2026-02")}
        elif kind == "annual":
            counts["annual"] += 1
            want = set(days)
        else:
            want = None
        if want is not None and ws != want:
            problems.append(f"TEMPORAL_FAILURE janelas {entity} {st}/{sv} {period}: "
                            f"faltam {sorted(want - ws)[:3]} sobram {sorted(map(str, ws - want))[:3]}")
    after = {k: v for k, v in store.items() if k[3] == "2026-01"}
    if january_snapshot is not None and after != january_snapshot:
        changed = sorted((k for k in set(after) | set(january_snapshot) if after.get(k) != january_snapshot.get(k)), key=repr)
        problems.append(f"TEMPORAL_FAILURE janelas de janeiro mudaram após 2026-02-01: {changed[:3]}")
    return counts, problems


def event_identity(event: list) -> tuple:
    """(kind, node, variable, scope_type, scope_value, period) de uma linha de `events_of`."""
    return (event[1], event[2], event[4], event[5], event[6], event[7])


def check_reexecution(day: str, before: dict, after: dict, first_events: list, re_events: list) -> list[str]:
    """
    Reexecução da mesma data no mesmo contexto: store idêntico (nenhuma chave nova,
    nenhum valor/estado alterado), zero estado residual, eventos idênticos aos da
    primeira execução (só TRANSFER passa de WRITTEN a UNCHANGED), sem evento duplicado.
    """
    problems = []
    new = sorted(set(after) - set(before), key=repr)
    lost = sorted(set(before) - set(after), key=repr)
    changed = sorted((k for k in set(after) & set(before) if after[k] != before[k]), key=repr)
    if new:
        problems.append(f"REEXECUTION_FAILURE {day} identidade nova {new[:3]}")
    if lost or changed:
        problems.append(f"REEXECUTION_FAILURE {day} store alterado {(lost + changed)[:3]}")
    stated = [k for k, v in after.items() if v[2] is not None or v[3] is not None]
    if stated:
        problems.append(f"REEXECUTION_FAILURE {day} estado residual {sorted(stated, key=repr)[:3]}")
    identities = [event_identity(e) for e in re_events]
    duplicated = sorted({i for i in identities if identities.count(i) > 1}, key=repr)
    if duplicated:
        problems.append(f"REEXECUTION_FAILURE {day} evento duplicado {duplicated[:3]}")
    statuses = {e[8] for e in re_events if e[1] == "TRANSFER"}
    if statuses - {"UNCHANGED"}:
        problems.append(f"REEXECUTION_FAILURE {day} transferência regravada {sorted(statuses)}")
    expected = [[*e[:8], "UNCHANGED" if e[1] == "TRANSFER" else e[8], *e[9:]] for e in first_events]
    if re_events != expected:
        problems.append(f"REEXECUTION_FAILURE {day} eventos diferem da primeira execução")
    return problems


def check_determinism(runs: dict) -> list[str]:
    """runs: {label: {results_sha256, store_sha256, graph_hash, plan_order}} — todos iguais a RUN_A."""
    problems = []
    reference = runs["RUN_A"]
    for label, run in sorted(runs.items()):
        for field in ("results_sha256", "store_sha256", "graph_hash", "plan_order"):
            if field in run and run[field] != reference[field]:
                problems.append(f"DETERMINISM_FAILURE {label}.{field} != RUN_A")
    return problems


def check_clean_context(store: dict) -> list[str]:
    """Contexto sem injeção: nenhum resultado pode ter state ou detail."""
    stated = sorted((k for k, v in store.items() if v[2] is not None or v[3] is not None), key=repr)
    return [f"STATE_PROPAGATION_FAILURE contexto limpo contaminado {k}" for k in stated[:5]] + (
        [f"STATE_PROPAGATION_FAILURE +{len(stated) - 5} chaves"] if len(stated) > 5 else [])


def check_result_contract(store: dict) -> list[str]:
    """D33B-03 na evidência: detail sem state; value None sem state."""
    problems = []
    for key, (kind, _repr, state, detail) in sorted(store.items(), key=lambda kv: repr(kv[0])):
        if detail is not None and state is None:
            problems.append(f"DETAIL_WITHOUT_STATE {key}")
        if kind == "NoneType" and state is None:
            problems.append(f"RESULT_CONTRACT_INVALID value None sem state {key}")
    return problems
