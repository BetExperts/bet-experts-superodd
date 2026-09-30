# -*- coding: utf-8 -*-
"""Dagelijkse slot-agent: nieuwe slots van AboutSlots (upcoming, pagina 1) die naar Nederland komen, compleet op de site.

Per nieuwe slot (nog niet in ons CMS, nog niet eerder afgewezen):
  1. NL-check vooraf: staat de slot al bij een NL-casino, en is de provider bij ons bekend/actief in NL?
  2. Onderzoek met Claude (web search + web fetch): komt hij naar NL, feiten van de provider, reviews.
  3. Schrijven met Claude (structured output, zelfde brief/velden als de bestaande reviews) + plagiaatcheck.
  4. Onbekende provider: providerpagina onderzoeken en schrijven (provider_publish.py).
  5. Live zetten (slot_publish.py), deelafbeelding (slot_og.py), NL-status/Nieuw (slot_nl_check.py).

  python slot_agent.py                 # normaal (LaunchAgent: dagelijks)
  python slot_agent.py --dry-run       # onderzoeken en schrijven, niets publiceren (JSON in state/slot_agent_runs/)
  python slot_agent.py --max 2         # maximaal 2 nieuwe slots deze run (standaard 6)
  python slot_agent.py --only "Wicked Grin"
"""
import datetime as dt, html, json, os, re, sys, time, unicodedata, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from slot_og import SLOTS, PROVIDERS, _all_items, _env  # noqa: E402

AGENT = os.path.join(HERE, "slot_agent")
STATE = os.path.join(HERE, "state", "slot_agent.json")
RUNS = os.path.join(HERE, "state", "slot_agent_runs")
SOURCE = "https://www.aboutslots.com/upcoming-casino-slots/1"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
MODEL = os.environ.get("SLOT_AGENT_MODEL", "claude-opus-5-5")
RECHECK_DAYS = 21          # afgewezen slots na zoveel dagen opnieuw bekijken
MAX_TRIES = 3              # mislukte slots zoveel runs opnieuw proberen
PROVIDER_ALIAS = {"red tiger gaming": "Red Tiger", "yggdrasil gaming": "Yggdrasil", "snowborn": "Snowborn Games",
                  "all41 studios": "All For One Studios", "all41studios": "All For One Studios"}


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def norm(t):
    t = unicodedata.normalize("NFKD", html.unescape(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t.replace("&", "and"))


def slugify(t):
    t = unicodedata.normalize("NFKD", html.unescape(t or "")).encode("ascii", "ignore").decode().lower()
    t = t.replace("&", " ").replace("'", "")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t)).strip("-")


# ---------------- bron: AboutSlots ----------------

MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def fetch_upcoming(page=1):
    req = urllib.request.Request(SOURCE.rsplit("/", 1)[0] + f"/{page}", headers=UA)
    t = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
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


# ---------------- Claude ----------------

def _client():
    import anthropic
    return anthropic.Anthropic()


def _system(brief_file, example_file):
    brief = open(os.path.join(AGENT, brief_file)).read()
    example = open(os.path.join(AGENT, example_file)).read()
    return [{"type": "text", "text": brief + "\n\n## Voorbeeld (bestaand item op de site)\n```json\n" + example + "\n```",
             "cache_control": {"type": "ephemeral"}}]


TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 15},
         {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 12}]


USAGE = {"in": 0, "out": 0, "cache_read": 0, "searches": 0, "fetches": 0}


def _stream(client, **kw):
    """Één request met server-side fallback bij een weigering; geeft het eindbericht terug."""
    with client.beta.messages.stream(model=MODEL, betas=["server-side-fallback-2026-07-01"],
                                     extra_body={"fallbacks": "default"}, **kw) as s:
        resp = s.get_final_message()
    u = resp.usage
    USAGE["in"] += (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
    USAGE["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
    USAGE["out"] += u.output_tokens or 0
    stu = getattr(u, "server_tool_use", None)
    if stu:
        USAGE["searches"] += getattr(stu, "web_search_requests", 0) or 0
        USAGE["fetches"] += getattr(stu, "web_fetch_requests", 0) or 0
    return resp


def usage_line():
    kosten = USAGE["in"] * 4 / 1e6 + USAGE["cache_read"] * 0.2 / 1e6 + USAGE["out"] * 20 / 1e6 + USAGE["searches"] * 0.01
    return (f"tokens in {USAGE['in']:,} (+{USAGE['cache_read']:,} cache), uit {USAGE['out']:,}, "
            f"{USAGE['searches']} zoekopdrachten, {USAGE['fetches']} pagina's; ca. ${kosten:.2f}")


def research(client, system, prompt):
    """Onderzoek met web search/fetch; handelt pause_turn af. -> (dossiertekst, bron-urls)"""
    messages = [{"role": "user", "content": prompt}]
    texts, urls = [], []
    for _ in range(8):
        resp = _stream(client, max_tokens=32000, system=system, messages=messages, tools=TOOLS,
                       thinking={"type": "adaptive"}, output_config={"effort": "high"})
        for b in resp.content:
            if b.type == "text":
                texts.append(b.text)
            elif b.type == "web_fetch_tool_result" and getattr(b.content, "url", None):
                urls.append(b.content.url)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})   # server hervat zelf
            continue
        if resp.stop_reason == "refusal":
            raise RuntimeError("onderzoek geweigerd door het model")
        break
    return "\n".join(texts), list(dict.fromkeys(urls))


def write_json(client, system, prompt, schema):
    resp = _stream(client, max_tokens=48000, system=system, messages=[{"role": "user", "content": prompt}],
                   thinking={"type": "adaptive"}, output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}})
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"schrijven gestopt: {resp.stop_reason}")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


S_ = {"type": "string"}
NS = {"anyOf": [{"type": "string"}, {"type": "null"}]}
SLOT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "komt_naar_nl": {"type": "boolean"}, "nl_zekerheid": NS, "reden_niet_nl": NS,
        "provider": S_, "naam": S_, "officiele_naam": NS, "slug": S_,
        "seo_titel": S_, "meta_omschrijving": S_, "intro": S_,
        "rtp": NS, "rtp_versies": NS, "volatiliteit": NS, "max_winst": NS, "raster": NS, "winlijnen": NS, "inzet": NS,
        "releasedatum": NS, "review_html": S_, "bonusfuncties_html": S_,
        "pluspunten": {"type": "array", "items": S_}, "minpunten": {"type": "array", "items": S_},
        "faq": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                           "properties": {"vraag": S_, "antwoord": S_}, "required": ["vraag", "antwoord"]}},
        "vergelijkbare_slots": {"type": "array", "items": S_}, "deelregel": S_, "nl_verwacht": NS,
        "bronnen": {"type": "array", "items": S_},
    },
}
SLOT_SCHEMA["required"] = list(SLOT_SCHEMA["properties"])

PROV_KEYS = ["name", "slug", "seo-titel", "meta-omschrijving", "intro", "opgericht", "hoofdkantoor", "aantal-spellen",
             "gemiddelde-rtp", "bekend-van", "spelsoorten", "status-nederland", "over-de-provider", "spelaanbod-per-soort",
             "rtp-en-volatiliteit", "sterke-punten", "minder-sterke-punten"] + \
            [f"faq-{i}-{k}" for i in range(1, 6) for k in ("vraag", "antwoord")] + \
            ["top-3-titel"] + [f"top-slot-{i}{s}" for i in (1, 2, 3) for s in ("", "-tekst")] + \
            ["spelaanbod-score", "gemiddelde-rtp-score", "innovatie-score", "officiele-website", "deelregel"]
PROV_SCHEMA = {"type": "object", "additionalProperties": False,
               "properties": {**{k: NS for k in PROV_KEYS}, "bronnen": {"type": "array", "items": S_}},
               "required": PROV_KEYS + ["bronnen"]}


# ---------------- plagiaat ----------------

def plag(item_text, urls):
    sys.path.insert(0, AGENT)
    from plagcheck import check
    n, res = check({"naam": "", "intro": item_text, "bronnen": urls})
    worst = max([r[1] for r in res if r[1] is not None] or [0])
    voorbeelden = [e for _, p, ex in res if p and p >= 1.5 for e in ex[:3]]
    return worst, voorbeelden


def slot_text(x):
    return " ".join([x.get("intro") or "", x.get("review_html") or "", x.get("bonusfuncties_html") or "",
                     " ".join(x.get("pluspunten") or []), " ".join(x.get("minpunten") or []),
                     " ".join(q["antwoord"] for q in x.get("faq") or [])])


# ---------------- hoofdlijn ----------------

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


def main(argv):
    _env()
    dry = "--dry-run" in argv
    maxn = int(argv[argv.index("--max") + 1]) if "--max" in argv else int(os.environ.get("SLOT_AGENT_MAX", "6"))
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    page = int(argv[argv.index("--page") + 1]) if "--page" in argv else 1
    today = dt.date.today()
    st = load_state()
    slots = _all_items(SLOTS)
    provs = _all_items(PROVIDERS)
    have = {norm(i["fieldData"]["name"]) for i in slots} | {norm(i["fieldData"]["slug"]) for i in slots}
    names_all = [i["fieldData"]["name"] for i in slots]

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
        if rec.get("status") == "mislukt" and rec.get("pogingen", 0) >= MAX_TRIES:
            continue
        cands.append(c)
    log(f"AboutSlots: {len(cands)} nieuwe kandidaten" + (f", deze run max. {maxn}" if len(cands) > maxn else ""))
    if not cands:
        return
    for c in cands[maxn:]:
        log(f"   later: {c['naam']}")
    client = _client()
    import slot_nl_check, slot_publish
    sys_slot = _system("brief_slot.md", "voorbeeld_review.json")
    sys_prov = _system("brief_provider.md", "voorbeeld_provider.json")
    run_dir = os.path.join(RUNS, today.isoformat())
    os.makedirs(run_dir, exist_ok=True)
    ready, new_providers, done_keys = [], [], []

    for c in cands[:maxn]:
        key = c["key"]
        try:
            log(f"— {c['naam']} ({c['provider']}, release {c['release']})")
            prov = match_provider(c["provider"], provs)
            pf = prov["fieldData"] if prov else {}
            fake = {"fieldData": {"slug": slugify(c["naam"]), "name": c["naam"]}}
            found = slot_nl_check.find_casinos(fake, pf.get("slug") or slugify(c["provider"] or ""))
            pid = pf.get("slotslaunch-provider-id")
            sl = None
            if pid:
                slot_publish.sl_game(1, pid)
                sl = next((g for g in slot_publish._SL_CACHE.get(pid, {}).values() if norm(g["name"]) == norm(c["naam"])), None)
            context = (
                f"Slot: {c['naam']}\nProvider volgens AboutSlots: {c['provider']}\nRelease volgens AboutSlots: {c['release']}\n"
                f"AboutSlots-pagina (alleen feiten gebruiken): {c['url']}\n"
                f"Provider in ons CMS: {'ja, als ' + pf['name'] + ' — NL-status: ' + (pf.get('status-nederland') or 'onbekend') if prov else 'nee'}\n"
                f"Onze eigen NL-check van de spelpagina's (Unibet, LeoVegas, BetMGM, TOTO, JACKS.NL, 711): "
                f"{', '.join(f'{k}: {v}' for k, v in found.items()) or 'nog niet gevonden'}\n"
                f"Demo beschikbaar op onze pagina: {'ja' if sl else 'nee'}\n"
                f"Datum vandaag: {today.isoformat()}\n")
            dossier, urls = research(client, sys_slot, context + "\nDoe stap 1 en 2 van de brief. Zoek de officiële "
                                     "gamepagina/factsheet/persbericht van de provider en 2-3 goede reviews. Schrijf daarna een "
                                     "feitendossier: per feit de waarde en de bron-URL, tegenstrijdigheden expliciet benoemd, en je "
                                     "conclusie over komt_naar_nl met onderbouwing. Nog GEEN review schrijven.")
            open(os.path.join(run_dir, f"{key}.dossier.md"), "w").write(dossier + "\n\nURLs:\n" + "\n".join(urls))
            prompt = (context + "\nFeitendossier uit je onderzoek:\n" + dossier +
                      "\n\nGebruik voor vergelijkbare_slots alleen namen uit deze lijst:\n" + json.dumps(names_all, ensure_ascii=False) +
                      "\n\nSchrijf nu het complete item volgens de brief (stap 3 en 4) als JSON. Zet in bronnen alle URLs die je voor feiten gebruikte.")
            x = write_json(client, sys_slot, prompt, SLOT_SCHEMA)
            x["bronnen"] = list(dict.fromkeys((x.get("bronnen") or []) + urls))
            if not x["komt_naar_nl"]:
                st["slots"][key] = {"status": "afgewezen", "naam": c["naam"], "reden": x.get("reden_niet_nl"), "datum": today.isoformat()}
                log(f"   afgewezen: {x.get('reden_niet_nl')}")
                save_state(st)
                continue
            worst, voorbeelden = plag(slot_text(x), x["bronnen"])
            if worst >= 3:
                log(f"   overlap {worst}% met een bron, herschrijven")
                x = write_json(client, sys_slot, prompt + "\n\nLET OP: een eerdere versie nam te letterlijk tekst over, bv.: "
                               + json.dumps(voorbeelden[:10], ensure_ascii=False) + ". Formuleer alles opnieuw in eigen woorden.", SLOT_SCHEMA)
                x["bronnen"] = list(dict.fromkeys((x.get("bronnen") or []) + urls))
                worst, _ = plag(slot_text(x), x["bronnen"])
                if worst >= 3:
                    raise RuntimeError(f"plagiaatcheck blijft te hoog ({worst}%)")
            x["rank"] = 30
            x["naam"] = x.get("naam") or c["naam"]
            x["slug"] = slugify(x.get("slug") or x["naam"])
            x["nl_casinos"] = list(found)
            if sl:
                x["slotslaunch_id"] = sl["id"]
            if prov:
                x["provider"] = pf["name"]
            elif x["provider"] not in new_providers:
                new_providers.append(x["provider"])
            x["_key"], x["_release_aboutslots"] = key, c["release"]
            if (x.get("releasedatum") or "") == "" and c["release"]:
                x["releasedatum"] = c["release"]
            json.dump(x, open(os.path.join(run_dir, f"{key}.json"), "w"), ensure_ascii=False, indent=1)
            log(f"   klaar: {x['naam']} (overlap {worst}%, NL: {', '.join(found) or '-'}, demo: {'ja' if sl else 'nee'})")
            ready.append(x)
        except Exception as ex:
            rec = st["slots"].get(key, {})
            st["slots"][key] = {"status": "mislukt", "naam": c["naam"], "reden": str(ex)[:300], "datum": today.isoformat(),
                                "pogingen": rec.get("pogingen", 0) + 1}
            save_state(st)
            log(f"   MISLUKT: {ex}")

    # nieuwe providers eerst (zodat de slots eraan gekoppeld kunnen worden)
    prov_rows = []
    for pname in new_providers:
        try:
            log(f"— nieuwe provider: {pname}")
            ctx = f"Provider: {pname}\nNieuwe slot van deze provider op onze site: {[x['naam'] for x in ready if x['provider'] == pname]}\nDatum vandaag: {today.isoformat()}\n"
            dossier, urls = research(client, sys_prov, ctx + "\nOnderzoek deze provider (officiële site eerst, daarna nieuws/reviews): "
                                     "oprichting, eigenaar, distributie, licenties, aantal spellen, bekendste titels met feiten, RTP-beleid. "
                                     "Controleer via zoeken of bekende titels bij Nederlandse KSA-casino's staan (Unibet, LeoVegas, BetMGM, TOTO, 711, JACKS.NL). "
                                     "Schrijf een feitendossier met bron-URL per feit en tel bij hoeveel van die 6 casino's je de provider vond.")
            m = re.search(r"(\d)\s*(?:van|/)\s*(?:de\s*)?6", dossier)
            n = int(m.group(1)) if m else 0
            status = f"Bij {n} van de 6 gecontroleerde vergunde casino's" if n else "Niet gevonden bij de gecontroleerde vergunde casino's"
            p = write_json(client, sys_prov, ctx + f"\nGebruik voor status-nederland exact: {status}\n\nFeitendossier:\n" + dossier +
                           "\n\nSchrijf nu de complete providerpagina als JSON (Webflow-veldslugs als keys).", PROV_SCHEMA)
            p["status-nederland"] = status
            p["bronnen"] = list(dict.fromkeys((p.get("bronnen") or []) + urls))
            txt = " ".join(str(p.get(k) or "") for k in PROV_KEYS if "score" not in k)
            worst, _ = plag(re.sub("<[^>]+>", " ", txt), p["bronnen"])
            if worst >= 3:
                raise RuntimeError(f"plagiaatcheck provider te hoog ({worst}%)")
            p["slug"] = slugify(p.get("slug") or p.get("name") or pname)
            from provider_publish import _sl_providers
            slp = [q for q in _sl_providers().values() if norm(q["name"]) == norm(p.get("name") or pname)]
            if slp:
                p["slotslaunch-provider-id"] = slp[0]["id"]
            prov_rows.append(p)
        except Exception as ex:
            log(f"   provider MISLUKT: {ex} (slots van deze provider wachten tot een volgende run)")
            ready = [x for x in ready if x["provider"] != pname]
    if dry:
        log(f"dry-run: {len(ready)} slots en {len(prov_rows)} providers klaargezet in {run_dir} | {usage_line()}")
        return
    if prov_rows:
        pf_file = os.path.join(run_dir, "providers.json")
        json.dump(prov_rows, open(pf_file, "w"), ensure_ascii=False, indent=1)
        import provider_publish
        provider_publish.main([pf_file, "--write"])
        # demo-ID's opzoeken nu de provider bekend is
        for x in ready:
            p = next((q for q in prov_rows if q.get("name") == x["provider"]), None)
            if p and p.get("slotslaunch-provider-id") and not x.get("slotslaunch_id"):
                slot_publish.sl_game(1, p["slotslaunch-provider-id"])
                g = next((g for g in slot_publish._SL_CACHE.get(p["slotslaunch-provider-id"], {}).values() if norm(g["name"]) == norm(x["naam"])), None)
                if g:
                    x["slotslaunch_id"] = g["id"]
    if ready:
        sf = os.path.join(run_dir, "slots.json")
        json.dump(ready, open(sf, "w"), ensure_ascii=False, indent=1)
        slot_publish.main([sf, "--write", "--publish"])
        import slot_og
        slot_og.main([x["slug"] for x in ready] + ["--attach"])
        for x in ready:
            st["slots"][x["_key"]] = {"status": "toegevoegd", "naam": x["naam"], "slug": x["slug"], "datum": today.isoformat()}
        save_state(st)
        slot_nl_check.main(["--write"])     # status, Nieuw, FAQ 5 en provider-reviewlinks bijwerken
        link_provider_reviews()
    log(f"klaar: {len(ready)} slots live, {len(prov_rows)} nieuwe providers | {usage_line()}")


def link_provider_reviews():
    """Top-3 van providers koppelen aan slotreviews die nu bestaan."""
    from slot_og import _wf
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


if __name__ == "__main__":
    main(sys.argv[1:])
