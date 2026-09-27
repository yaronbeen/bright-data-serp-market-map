"""Map market visibility using Bright Data SERP API structured results."""
import argparse,csv,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

FIELDS=["query","country","language","position","title","url","domain","snippet","observed_at"]

def domain(url):
    try:
        p=urlsplit(url)
        hostname=p.hostname
        p.port
    except (TypeError, ValueError):
        raise ValueError("result URL must be a valid absolute HTTP(S) URL without user information") from None
    if p.scheme not in {"http", "https"} or not hostname or p.username or p.password: raise ValueError("result URL must be a valid absolute HTTP(S) URL without user information")
    return hostname.lower().removeprefix("www.")

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
        host=domain(url); key=(host,url)
        if key in seen: continue
        canonical=urlsplit(url)._replace(netloc=host).geturl()
        key=(host,canonical)
        if key in seen: continue
        seen.add(key); rows.append({"query":query,"country":country,"language":language,"position":item.get("global_rank") or item.get("position") or i,"title":item.get("title") or "","url":url,"domain":host,"snippet":item.get("description") or "","observed_at":now})
    return rows

def summarize(rows):
    counts=Counter((r.get("query", ""), r["domain"]) for r in rows)
    return [{"query":query,"domain":host,"results":count} for (query,host),count in counts.most_common()]

def request_serp(query,country,language,key,zone):
    if not key or not zone: raise ValueError("Set BRIGHT_DATA_API_KEY and BRIGHT_DATA_SERP_ZONE")
    target="https://www.google.com/search?"+urlencode({"q":query,"gl":country,"hl":language,"pws":"0"})
    req=Request("https://api.brightdata.com/request",data=json.dumps({"zone":zone,"url":target,"format":"json"}).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as response: return json.loads(response.read())
    except HTTPError as e: raise RuntimeError("Bright Data SERP API returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("SERP request failed: "+str(e)) from None

def write_csv(path,rows):
    with Path(path).open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--query",action="append",required=True); p.add_argument("--country",default="us"); p.add_argument("--language",default="en"); p.add_argument("--output",default="market_map.json"); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        if not a.country.isalpha() or len(a.country)!=2: raise ValueError("country must be a two-letter code")
        if not a.language.replace("-", "").isalpha(): raise ValueError("language must be a language code")
        if a.dry_run: print(f"Dry run: {len(a.query)} SERP request(s) planned; 0 requests made"); return 0
        rows=[]
        for query in a.query:
            if not query.strip(): raise ValueError("query cannot be blank")
            rows.extend(normalize(request_serp(query,a.country.lower(),a.language.lower(),os.getenv("BRIGHT_DATA_API_KEY"),os.getenv("BRIGHT_DATA_SERP_ZONE")),query,a.country.lower(),a.language.lower()))
        report={"results":rows,"domain_summary":summarize(rows),"caveat":"Observed result snapshot; rankings vary by time, location, personalization and query. Opportunity cues are not traffic or ranking guarantees."}
        if a.output.endswith(".csv"): write_csv(a.output,rows)
        else: Path(a.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"Wrote {len(rows)} SERP results across {len(a.query)} query(s)"); return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
