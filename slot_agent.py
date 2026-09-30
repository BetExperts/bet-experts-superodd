# -*- coding: utf-8 -*-
"""Slot-agent (zonder API-key): het onderzoek en schrijven gebeurt in een Claude Code-chat ("run de slot agent",
skill bet-experts-slot-agent); dit script doet de rest.

  python slot_agent.py prepare [--max 6] [--page 1] [--only "Naam"]
      Leest AboutSlots upcoming (pagina 1), slaat bestaande/afgewezen slots over, doet de NL-check van de spelpagina's
      en zoekt de SlotsLaunch-demo. Schrijft state/slot_agent_runs/<datum>/worklist.json (+ alle_slotnamen.json,
      providers_in_cms.json) als opdracht voor de schrijf-agents.

  python slot_agent.py publish [<run-map>]
      Leest de door de agents geschreven <key>.json (review volgens slot_agent/brief_slot.md) en eventueel
      providers.json (volgens slot_agent/brief_provider.md). Afgewezen slots (komt_naar_nl=false) gaan naar de state.
      Plagiaatcheck (>=3% = niet publiceren), nieuwe providers live, slots live, deelafbeeldingen, NL-check, top-3-koppelingen.
"""
import datetime as dt, html, json, os, re, sys, unicodedata, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from slot_og import SLOTS, PROVIDERS, _all_items, _env, _wf  # noqa: E402

AGENT = os.path.join(HERE, "slot_agent")
STATE = os.path.join(HERE, "state", "slot_agent.json")
RUNS = os.path.join(HERE, "state", "slot_agent_runs")
SOURCE = "https://www.aboutslots.com/upcoming-casino-slots/{page}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
RECHECK_DAYS = 21          # afgewezen slots na zoveel dagen opnieuw bekijken
PROVIDER_ALIAS = {"red tiger gaming": "Red Tiger", "yggdrasil gaming": "Yggdrasil", "snowborn": "Snowborn Games",
                  "all41 studios": "All For One Studios", "all41studios": "All For One Studios"}
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def norm(t):
    t = unicodedata.normalize("NFKD", html.unescape(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t.replace("&", "and"))


def slugify(t):
    t = unicodedata.normalize("NFKD", html.unescape(t or "")).encode("ascii", "ignore").decode().lower()
    t = t.replace("&", " ").replace("'", "")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t)).strip("-")


def fetch_upcoming(page=1):
    t = urllib.request.urlopen(urllib.request.Request(SOURCE.format(page=page), headers=UA), timeout=60).read().decode("utf-8", "replace")
    today = dt.date.today()
    out = []
    for m in re.finditer(r"Release:\s*(?:<[^>]+>\s*)*([A-Z][a-z]{2}) (\d{2})", t):
        before = t[max(0, m.start() - 600):m.start()]
        prov = [p.strip() for p in re.findall(r">([^<>]{2,40})<", before) if p.strip() and "Release" not in p]
        alt = re.search(r'alt="([^"]+?) Thumbnail"', t[m.end():m.end() + 900])
        href = re.findall(r'href="(/casino-slots/[a-z0-9-]+)"', t[max(0, m.start() - 1500):m.end() + 1500])
        if not alt:
            continue
        mon, day = MONTHS.get(m.group(1)), int(m.group(2))
        year = today.year + (1 if mon and mon < today.month - 6 else 0)
        out.append({"naam": html.unescape(alt.group(1)).strip(), "provider": html.unescape(prov[-1]) if prov else None,
                    "release": f"{year}-{mon:02d}-{day:02d}" if mon else None,
                    "url": "https://www.aboutslots.com" + href[-1] if href else None,
                    "key": href[-1].rsplit("/", 1)[-1] if href else slugify(alt.group(1))})
    return out


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"slots": {}}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)


def match_provider(name, provs):
    n = norm(PROVIDER_ALIAS.get((name or "").lower().strip(), name))
    for p in provs:
        pn = norm(p["fieldData"]["name"])
        if pn == n or (len(pn) > 4 and (n.startswith(pn) or pn.startswith(n))):
            return p
    return None


# ---------------- prepare ----------------

def prepare(argv):
    _env()
    maxn = int(argv[argv.index("--max") + 1]) if "--max" in argv else 6
    page = int(argv[argv.index("--page") + 1]) if "--page" in argv else 1
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    today = dt.date.today()
    st = load_state()
    slots, provs = _all_items(SLOTS), _all_items(PROVIDERS)
    have = {norm(i["fieldData"]["name"]) for i in slots} | {norm(i["fieldData"]["slug"]) for i in slots}
    import slot_nl_check, slot_publish
    cands = []
    for c in fetch_upcoming(page):
        if only and norm(c["naam"]) != norm(only):
            continue
        if norm(c["naam"]) in have or norm(c["key"]) in have:
            continue
        rec = st["slots"].get(c["key"], {})
        if rec.get("status") == "toegevoegd":
            continue
        if rec.get("status") == "afgewezen" and (today - dt.date.fromisoformat(rec["datum"])).days < RECHECK_DAYS:
            continue
        cands.append(c)
    run_dir = os.path.join(RUNS, today.isoformat())
    os.makedirs(run_dir, exist_ok=True)
    work = []
    for c in cands[:maxn]:
        prov = match_provider(c["provider"], provs)
        pf = prov["fieldData"] if prov else {}
        fake = {"fieldData": {"slug": slugify(c["naam"]), "name": c["naam"]}}
        found = slot_nl_check.find_casinos(fake, pf.get("slug") or slugify(c["provider"] or ""))
        sl = None
        if pf.get("slotslaunch-provider-id"):
            slot_publish.sl_game(1, pf["slotslaunch-provider-id"])
            sl = next((g for g in slot_publish._SL_CACHE.get(pf["slotslaunch-provider-id"], {}).values()
                       if norm(g["name"]) == norm(c["naam"])), None)
        work.append({**c, "provider_in_cms": pf.get("name"), "provider_nl_status": pf.get("status-nederland"),
                     "nl_casinos_gevonden": found, "demo": bool(sl), "slotslaunch_id": sl["id"] if sl else None,
                     "output": os.path.join(run_dir, f"{c['key']}.json")})
    json.dump(work, open(os.path.join(run_dir, "worklist.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(sorted(i["fieldData"]["name"] for i in slots), open(os.path.join(run_dir, "alle_slotnamen.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(sorted(p["fieldData"]["name"] for p in provs), open(os.path.join(run_dir, "providers_in_cms.json"), "w"), ensure_ascii=False, indent=1)
    log(f"AboutSlots p.{page}: {len(cands)} nieuwe kandidaten, {len(work)} in de worklist: {run_dir}/worklist.json")
    for w in work:
        log(f"   {w['naam']} | {w['provider']} ({w['provider_in_cms'] or 'NIEUWE provider'}) | release {w['release']} | "
            f"NL: {', '.join(w['nl_casinos_gevonden']) or '-'} | demo: {'ja' if w['demo'] else 'nee'}")
    for c in cands[maxn:]:
        log(f"   later: {c['naam']}")


# ---------------- publish ----------------

def plag(text, urls):
    sys.path.insert(0, AGENT)
    from plagcheck import check
    n, res = check({"naam": "", "intro": text, "bronnen": urls})
    return max([r[1] for r in res if r[1] is not None] or [0])


def slot_text(x):
    return " ".join([x.get("intro") or "", x.get("review_html") or "", x.get("bonusfuncties_html") or "",
                     " ".join(x.get("pluspunten") or []), " ".join(x.get("minpunten") or []),
                     " ".join(q["antwoord"] for q in x.get("faq") or [])])


def link_provider_reviews():
    slots = {norm(i["fieldData"]["name"]): i["id"] for i in _all_items(SLOTS)}
    rows = []
    for p in _all_items(PROVIDERS):
        f, fd = p["fieldData"], {}
        for n in (1, 2, 3):
            sid = slots.get(norm(f.get(f"top-slot-{n}")))
            if sid and f.get(f"top-slot-{n}-review") != sid:
                fd[f"top-slot-{n}-review"] = sid
        if fd:
            rows.append({"id": p["id"], "fieldData": fd})
    for path in ("items", "items/live"):
        for i in range(0, len(rows), 25):
            _wf(f"/collections/{PROVIDERS}/{path}", "PATCH", {"items": rows[i:i + 25]})


def publish(argv):
    _env()
    run_dir = next((a for a in argv if not a.startswith("--")), os.path.join(RUNS, dt.date.today().isoformat()))
    today = dt.date.today().isoformat()
    st = load_state()
    work = {w["key"]: w for w in json.load(open(os.path.join(run_dir, "worklist.json")))}
    import slot_publish, slot_og, slot_nl_check
    provs = _all_items(PROVIDERS)
    # nieuwe providers eerst (zodat de slots eraan gekoppeld kunnen worden)
    pfile = os.path.join(run_dir, "providers.json")
    if os.path.exists(pfile):
        ok = []
        for p in json.load(open(pfile)):
            txt = re.sub("<[^>]+>", " ", " ".join(str(v) for k, v in p.items() if isinstance(v, str) and "score" not in k))
            w = plag(txt, p.get("bronnen") or [])
            log(f"provider {p.get('name')}: overlap {w}%")
            if w < 3:
                ok.append(p)
        if ok:
            json.dump(ok, open(pfile, "w"), ensure_ascii=False, indent=1)
            import provider_publish
            provider_publish.main([pfile, "--write"])
            provs = _all_items(PROVIDERS)
    ready = []
    for key, w in work.items():
        f = w["output"]
        if not os.path.exists(f):
            log(f"{w['naam']}: geen output, overgeslagen")
            continue
        x = json.load(open(f))
        if not x.get("komt_naar_nl"):
            st["slots"][key] = {"status": "afgewezen", "naam": w["naam"], "reden": x.get("reden_niet_nl") or x.get("reden"), "datum": today}
            log(f"{w['naam']}: afgewezen ({st['slots'][key]['reden']})")
            continue
        overlap = plag(slot_text(x), x.get("bronnen") or [])
        if overlap >= 3:
            log(f"{w['naam']}: overlap {overlap}% met een bron, NIET gepubliceerd (herschrijven)")
            continue
        prov = match_provider(x.get("provider") or w["provider"], provs)
        if not prov:
            log(f"{w['naam']}: provider {x.get('provider')} staat (nog) niet in het CMS, overgeslagen")
            continue
        x["provider"] = prov["fieldData"]["name"]
        x["rank"] = 30
        x["slug"] = slugify(x.get("slug") or x["naam"])
        x["nl_casinos"] = list(w.get("nl_casinos_gevonden") or {})
        sid = w.get("slotslaunch_id")
        if not sid and prov["fieldData"].get("slotslaunch-provider-id"):
            pid = prov["fieldData"]["slotslaunch-provider-id"]
            slot_publish.sl_game(1, pid)
            g = next((g for g in slot_publish._SL_CACHE.get(pid, {}).values() if norm(g["name"]) == norm(x["naam"])), None)
            sid = g and g["id"]
        if sid:
            x["slotslaunch_id"] = sid
        if not x.get("releasedatum") and w.get("release"):
            x["releasedatum"] = w["release"]
        x["_key"] = key
        log(f"{x['naam']}: klaar voor publicatie (overlap {overlap}%, demo {'ja' if sid else 'nee'})")
        ready.append(x)
    save_state(st)
    if ready:
        sf = os.path.join(run_dir, "slots.json")
        json.dump(ready, open(sf, "w"), ensure_ascii=False, indent=1)
        slot_publish.main([sf, "--write", "--publish"])
        slot_og.main([x["slug"] for x in ready] + ["--attach"])
        for x in ready:
            st["slots"][x["_key"]] = {"status": "toegevoegd", "naam": x["naam"], "slug": x["slug"], "datum": today}
        save_state(st)
        slot_nl_check.main(["--write"])
        link_provider_reviews()
    log(f"klaar: {len(ready)} slots live")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    {"prepare": prepare, "publish": publish}[cmd](sys.argv[2:])
