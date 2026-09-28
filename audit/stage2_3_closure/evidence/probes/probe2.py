import sys, json, re, ast, collections
sys.path.insert(0, "/home/user/forecast-model-audit-s06-v6-")
from wbr import rows
from app.engine import reference_resolver as rr
from app.engine.scoped_reference import InvalidScopeReferenceError
from app.engine.expression_parser import ExpressionParser
from app.engine.scope_resolver import ScopeResolver
from app.domain.values import VALUE_TYPES
from app.validation.variable_seed_validator import ALLOWED_UNITS, UNIT_ALIASES, ALLOWED_SCOPE_VALUES, ALLOWED_SCOPE_TYPES, ALLOWED_FREQUENCIES

B=["area_41","energy","max_ht","production","yield"]
AGG=re.compile(r"(?i)^\s*(m[ée]dia|somat[óo]rio)|média_ponderada|resultados di[áa]rios|dados entre")
parser=ExpressionParser(); SR=ScopeResolver()
def dc(s): return re.sub(r"(?<=\d),(?=\d)",".",s)
OUT={}; ALL={}
base=50000
for b in B:
    R,_=rows(b); recs=[]
    for i,v in enumerate(R):
        t=(v.get("Type") or "").strip()
        eid=("PARAM" if t=="parameter" else "VAR")+str(base+i)
        rec=dict(block=b,row=v["row"],type=t,name=v.get("name"),frequency=v.get("frequency"),scope_type=v.get("scope_type"),
                 scope_value=v.get("scope_value"),unit=v.get("unit"),variable_type=v.get("variable_type"),status=v.get("status"),
                 value_type=v.get("value_type"),allowed_values=v.get("allowed_values"),declared_result_states=v.get("declared_result_states"),
                 expression=None if v.get("expression") is None else str(v["expression"]),fonte=v.get("fonte"),entity_id=eid,issues=[])
        recs.append(rec)
    base+=1000
    # field-level contract checks
    for r in recs:
        if r["scope_type"] not in ALLOWED_SCOPE_TYPES: r["issues"].append(("scope_type_not_allowed",r["scope_type"]))
        if r["scope_value"] not in ALLOWED_SCOPE_VALUES: r["issues"].append(("scope_value_not_allowed",r["scope_value"]))
        try: SR.resolve_scopes(r["scope_type"],r["scope_value"])
        except Exception as e: r["issues"].append(("scope_resolver_rejects",f"{type(e).__name__}: {e}"[:120]))
        if r["type"]!="parameter" and r["frequency"] not in ALLOWED_FREQUENCIES: r["issues"].append(("frequency_invalid",r["frequency"]))
        u=UNIT_ALIASES.get(r["unit"],r["unit"])
        if u not in ALLOWED_UNITS: r["issues"].append(("unit_not_allowed",r["unit"]))
        if r["value_type"] not in VALUE_TYPES: r["issues"].append(("value_type_not_in_code_enum",r["value_type"]))
        if r["type"]!="parameter" and r["status"]!="ativo": r["issues"].append(("status",r["status"]))
    # identity uniqueness
    ident=collections.defaultdict(list)
    for r in recs:
        k=(r["name"],r["frequency"] if r["type"]!="parameter" else None,r["scope_type"],r["scope_value"])
        ident[k].append(r["row"])
    for k,rs in ident.items():
        if len(rs)>1:
            for r in recs:
                if r["row"] in rs: r["issues"].append(("identity_collision",rs))
    idx=rr.build_name_index([dict(name=r["name"],kind="parameter" if r["type"]=="parameter" else "variable",entity_id=r["entity_id"],
        frequency=r["frequency"],scope_type=r["scope_type"],scope_value="L6_L7" if r["scope_value"]=="L6_7" else ("PLANTA" if r["scope_value"]=="planta" else r["scope_value"])) for r in recs])
    for r in recs:
        ex=r["expression"]
        if not ex or not ex.strip(): r["cls"]="none"; continue
        if AGG.search(ex): r["cls"]="D-aggregation-description"; continue
        x=dc(ex); r["decimal_comma"]=x!=ex
        cs=(r["scope_type"],{"L6_7":"L6_L7","planta":"PLANTA"}.get(r["scope_value"],r["scope_value"]))
        r["at_refs"]=re.findall(r"([A-Za-zÀ-ÿ_][\wÀ-ÿ]*)@(L\d(?:_L\d)?|\w+)",ex)
        r["text_literals"]=re.findall(r"\"([^\"]*)\"|'([^']*)'",ex)
        try:
            tr=rr.translate_expression(x,idx,r["frequency"],consumer_scope=cs); r["a019"]="resolved"; r["translated"]=tr
        except rr.ReferenceNotFoundError as e: r["a019"]="NOT_FOUND"; r["a019_err"]=str(e); r["cls"]="?"; continue
        except (rr.ReferenceResolutionError,InvalidScopeReferenceError,ValueError) as e: r["a019"]="AMBIGUOUS/INVALID"; r["a019_err"]=str(e)[:400]; r["cls"]="?"; continue
        code=re.sub(r"(\"[^\"]*\"|'[^']*')","",tr)
        left=[w for w in re.findall(r"(?<![\w@])([A-Za-zÀ-ÿ_][\wÀ-ÿ]*)",re.sub(r"\b(?:VAR|PARAM)\d{5}\b","",code)) if w not in("if","else","and","or","not","ln") and not re.fullmatch(r"L\d(_L\d)?",w)]
        r["unresolved_names"]=sorted(set(left))
        try:
            tree=parser.parse(tr); r["parse"]="ok"
            hs=any(isinstance(n,ast.Constant) and isinstance(n.value,str) for n in ast.walk(tree))
            hi=any(isinstance(n,ast.IfExp) for n in ast.walk(tree))
            hl=any(isinstance(n,ast.Call) for n in ast.walk(tree))
            r["cls"]=("B-cond+text" if hs else "B-conditional" if hi else "C-scoped" if "@" in tr else "A-arithmetic")+("+ln" if hl else "")
        except Exception as e:
            r["parse"]=f"FAIL {type(e).__name__}: {str(e)[:200]}"; r["cls"]="G-not-executable"
    OUT[b]=recs
json.dump(OUT,open("probe2_out.json","w"),ensure_ascii=False,indent=1,default=str)
for b in B:
    recs=OUT[b]
    print("=====",b,len(recs))
    print("  cls:",dict(collections.Counter(r.get("cls") for r in recs)))
    print("  a019:",dict(collections.Counter(r.get("a019") for r in recs if r.get("a019"))))
    ic=collections.Counter(i[0] for r in recs for i in r["issues"]); print("  field issues:",dict(ic))
    print("  decimal comma:",[r["row"] for r in recs if r.get("decimal_comma")])
