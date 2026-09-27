"""Map market visibility using Bright Data SERP API structured results."""
import argparse,csv,json,os,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

FIELDS=["query","country","language","intent","position","global_rank","content_format","title","url","domain","snippet","observed_at"]

CONTENT_FORMATS=("comparison", "pricing", "how_to_guide", "listicle")

def classify_intent(query):
    text=query.lower()
    if any(term in text for term in ("buy", "order", "near me", "quote", "hire")):
        return "transactional"
    if any(term in text for term in ("best", "top ", "vs", "versus", "compare", "comparison", "alternative", "pricing", "price", "cost", "review")):
        return "commercial_investigation"
    if any(term in text for term in ("how to", "what is", "guide", "tutorial", "examples", "ideas")):
        return "informational"
    return "unclassified"

def classify_content(title):
    text=title.lower()
    if any(term in text for term in (" vs ", "versus", "comparison", "compare", "alternative")):
        return "comparison"
    if any(term in text for term in ("pricing", "price", "cost", "plans")):
        return "pricing"
    if any(term in text for term in ("how to", "guide", "tutorial", "explained")):
        return "how_to_guide"
    if "best" in text or "top " in text or "list of" in text:
        return "listicle"
    return "other"

def domain(url):
    try:
        p=urlsplit(url)
        hostname=p.hostname
        p.port
    except (TypeError, ValueError):
        raise ValueError("result URL must be a valid absolute HTTP(S) URL without user information") from None
    if p.scheme not in {"http", "https"} or not hostname or p.username or p.password: raise ValueError("result URL must be a valid absolute HTTP(S) URL without user information")
    return hostname.lower().removeprefix("www.")

def csv_safe(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n\x00").startswith(("=", "+", "-", "@")): return "'" + value
    return value

def rank_value(item, fallback):
    value=item.get("rank")
    if value is None: value=item.get("position")
    if value is None: return fallback
    if isinstance(value,bool): raise ValueError("SERP rank must be a positive integer")
    try: rank=int(value)
    except (TypeError,ValueError): raise ValueError("SERP rank must be a positive integer") from None
    if str(rank)!=str(value).strip() or rank<1: raise ValueError("SERP rank must be a positive integer")
    return rank

def normalize(response,query,country="us",language="en"):
    data=response.get("body",response) if isinstance(response,dict) else response
    if isinstance(data,str): data=json.loads(data)
    organic=data.get("organic",[]) if isinstance(data,dict) else []
    if not isinstance(organic,list): raise ValueError("SERP response organic field must be a list")
    rows=[]; seen=set(); now=datetime.now(timezone.utc).isoformat()
    for i,item in enumerate(organic,1):
        if not isinstance(item, dict): raise ValueError("SERP organic entries must be objects")
        url=item.get("link") or item.get("url")
        if not url: continue
        host=domain(url)
        parsed=urlsplit(url)
        canonical=parsed._replace(scheme=parsed.scheme.lower(),netloc=parsed.netloc.lower().removeprefix("www."),fragment="").geturl()
        key=(host,canonical)
        if key in seen: continue
        title=item.get("title") or ""
        seen.add(key); rows.append({"query":query,"country":country,"language":language,"intent":classify_intent(query),"position":rank_value(item,i),"global_rank":item.get("global_rank"),"content_format":classify_content(title),"title":title,"url":url,"domain":host,"snippet":item.get("description") or "","observed_at":now})
    return rows

def summarize(rows):
    counts=Counter((r.get("query", ""), r["domain"]) for r in rows)
    return [{"query":query,"domain":host,"results":count} for (query,host),count in counts.most_common()]

def synthesize(rows):
    grouped={}
    domain_queries={}
    for row in rows:
        group=grouped.setdefault((row["query"],row["country"],row["language"]),{"query":row["query"],"country":row["country"],"language":row["language"],"intent":row["intent"],"results":0,"domains":set(),"formats":set()})
        group["results"]+=1
        group["domains"].add(row["domain"])
        if row["content_format"] in CONTENT_FORMATS: group["formats"].add(row["content_format"])
        domain_queries.setdefault(row["domain"],set()).add(row["query"])
    queries=[]
    for group in grouped.values():
        observed=sorted(group.pop("formats"))
        unobserved=[fmt for fmt in CONTENT_FORMATS if fmt not in observed]
        group["domains"]=sorted(group["domains"])
        group["observed_content_formats"]=observed
        group["unobserved_content_formats"]=unobserved
        group["content_opportunities"]=[{"format":fmt,"signal":"not_observed_in_returned_sample","prompt":f"Check whether a useful {fmt.replace('_',' ')} page could answer this query better."} for fmt in unobserved]
        queries.append(group)
    competitors=[{"domain":domain,"query_count":len(query_set),"queries":sorted(query_set)} for domain,query_set in sorted(domain_queries.items(),key=lambda item:(-len(item[1]),item[0]))]
    return {"queries":queries,"market_competitors":competitors,"caveat":"Content gaps mean only that a format was not observed in this returned SERP sample. Rankings and coverage vary; validate manually. No search volume, traffic, or ranking outcomes are inferred."}

def request_serp(query,country,language,key,zone):
    if not key or not zone: raise ValueError("Set BRIGHT_DATA_API_KEY and BRIGHT_DATA_SERP_ZONE")
    target="https://www.google.com/search?"+urlencode({"q":query,"gl":country,"hl":language,"pws":"0"})
    req=Request("https://api.brightdata.com/request",data=json.dumps({"zone":zone,"url":target,"format":"json"}).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as response: return json.loads(response.read())
    except HTTPError as e: raise RuntimeError("Bright Data SERP API returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("SERP request failed: "+str(e)) from None

def write_csv(path,rows):
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        w.writerows({key:csv_safe(value) for key,value in row.items()} for row in rows)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--query",action="append",required=True); p.add_argument("--country",default="us"); p.add_argument("--language",default="en"); p.add_argument("--output",default="market_map.json"); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        if any(not query.strip() for query in a.query): raise ValueError("query cannot be blank")
        if not re.fullmatch(r"[A-Za-z]{2}",a.country): raise ValueError("country must be a two-letter ASCII code")
        if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*",a.language): raise ValueError("language must be a language tag such as en or en-US")
        if a.dry_run: print(f"Dry run: {len(a.query)} SERP request(s) planned; 0 requests made"); return 0
        rows=[]
        for query in a.query:
            rows.extend(normalize(request_serp(query,a.country.lower(),a.language.lower(),os.getenv("BRIGHT_DATA_API_KEY"),os.getenv("BRIGHT_DATA_SERP_ZONE")),query,a.country.lower(),a.language.lower()))
        report={"results":rows,"domain_summary":summarize(rows),"market_map":synthesize(rows)}
        if a.output.endswith(".csv"): write_csv(a.output,rows)
        else: Path(a.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"Wrote {len(rows)} SERP results across {len(a.query)} query(s)"); return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
