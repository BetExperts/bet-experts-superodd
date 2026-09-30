# Vergelijkt onze reviewtekst met de gebruikte bronnen: gedeelde 8-woord-reeksen (shingles).
import json, re, sys, html, unicodedata, requests, concurrent.futures as cf
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36","Accept-Language":"nl-NL,nl;q=0.9,en;q=0.8"}
N=8
def words(t):
    t=html.unescape(re.sub(r"<[^>]+>"," ",t or ""))
    t=unicodedata.normalize("NFKD",t).encode("ascii","ignore").decode().lower()
    return re.findall(r"[a-z0-9]+",t)
def shingles(w): return {" ".join(w[i:i+N]) for i in range(len(w)-N+1)}
_cache={}
def fetch(u):
    if u in _cache: return _cache[u]
    try:
        r=requests.get(u,headers=UA,timeout=25); t=re.sub(r"<script.*?</script>|<style.*?</style>","",r.text,flags=re.S) if r.ok else ""
    except Exception: t=""
    _cache[u]=t; return t
def check(item):
    ours=" ".join([item.get("intro") or "",item.get("review_html") or "",item.get("bonusfuncties_html") or "",
                   " ".join(item.get("pluspunten") or []), " ".join(item.get("minpunten") or []),
                   " ".join((q.get("antwoord") or "") for q in item.get("faq") or [])])
    ow=words(ours); os_=shingles(ow)
    res=[]
    urls=[u for u in item.get("bronnen") or [] if u.startswith("http")]
    with cf.ThreadPoolExecutor(6) as ex: pages=list(ex.map(fetch,urls))
    for u,p in zip(urls,pages):
        ps=shingles(words(p))
        if not ps: res.append((u,None,[])); continue
        common=os_&ps
        res.append((u,round(100*len(common)/max(len(os_),1),1),sorted(common)[:5]))
    return len(ow),res
if __name__=="__main__":
    for f in sys.argv[1:]:
        for it in json.load(open(f)):
            n,res=check(it)
            worst=max([r[1] for r in res if r[1] is not None] or [0])
            flag="!!" if worst>=3 else "ok"
            print(f'{flag} {it.get("naam","?")[:30]:30} {n} woorden | max overlap {worst}% | bronnen gelezen {sum(1 for r in res if r[1] is not None)}/{len(res)}')
            for u,p,ex in res:
                if p and p>=1.5: print(f'      {p}% {u[:80]}  bv: "{ex[0] if ex else ""}"')
