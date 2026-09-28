"""Stage 2.4 — consumption probe (read-only).

Runs the two existing xlsx builders in memory on the official Stage-2.3
workbooks; never calls main(), never writes seeds. A monkeypatch of
LAST_DATA_ROW is used ONLY as a diagnostic (module attribute in memory;
the source file is not modified) to show what the builder would produce
if the hardcoded row window matched v9.
"""
import json, sys, traceback
from collections import Counter
sys.path.insert(0, "/home/user/forecast-model-audit-s06-v6-")
U = "/root/.claude/uploads/afd1cfda-5340-5625-86ea-0588b02fbed0/"
from tools import energy_seed_builder as E, max_ht_seed_builder as M

def compare(block, seeds):
    for k, v in seeds.items():
        cur = json.load(open(f"data/seed/{block}/{k}.json", encoding="utf-8"))
        print(f"  {k}: generated={len(v)} seed={len(cur)} equal={v == cur}")

print("== energy_seed_builder on energy v5")
rows = E.extract_rows(U + "b7873d62-descritivo_das_vari_veis_energy_v5.xlsx")
print("  rows read", len(rows), "empty", sum(1 for r in rows if not r.get("name")))
print("  columns present but NOT consumed:", sorted(set(rows[0]) - {"Type","name","description","unit","value","version","variable_type","frequency","scope_type","scope_value","status","expression","fonte","row"}))
model = E.build_canonical_model(rows)
print("  canonical entity keys:", sorted(model["entities"][0]))
seeds = E.build_seeds(model)
compare("energy", seeds)
cur = json.load(open("data/seed/energy/variables.json", encoding="utf-8"))
for g, o in zip(seeds["variables"], cur):
    for k in set(g) | set(o):
        if g.get(k) != o.get(k):
            print("  variable diff", g["variable_id"], k, repr(o.get(k)), "->", repr(g.get(k)))
print("  generated variable keys:", sorted(seeds["variables"][0]))
print("  value_type values in workbook rows:", Counter(r.get("value_type") for r in rows))
print("  SOURCE_REFERENCE constant:", E.SOURCE_REFERENCE)

print("== max_ht_seed_builder on MaxHT v9 (as-is)")
f = U + "28284f78-descritivo_das_vari_veis_MaxHT_v9.xlsx"
rows = M.extract_rows(f)
empty = [r["row"] for r in rows if not r.get("name")]
print("  LAST_DATA_ROW", M.LAST_DATA_ROW, "rows read", len(rows), "empty rows read", len(empty), empty[:3], "...", empty[-1:])
try:
    M.build_seeds(M.build_canonical_model(rows))
    print("  build_seeds OK")
except Exception as ex:
    tb = traceback.extract_tb(ex.__traceback__)[-1]
    print(f"  build_seeds FAILED: {type(ex).__name__}: {ex} @ {tb.filename.split('/')[-1]}:{tb.lineno} {tb.name}")

print("== max_ht diagnostic: LAST_DATA_ROW=122 in memory only")
M.LAST_DATA_ROW = 122
rows = M.extract_rows(f)
ents = M.build_canonical_model(rows)["entities"]
seeds = M.build_seeds({"entities": ents})
compare("max_ht", seeds)
print("  DSL aggregations recognized:", Counter(e["dsl"][0] for e in ents if e["dsl"]))
print("  identity collisions in v9 entities:", sum(1 for v in Counter((e["name"], e["frequency"], e["scope_type"], e["scope_value"]) for e in ents).values() if v > 1))
print("  SOURCE_REFERENCE constant:", M.SOURCE_REFERENCE)
