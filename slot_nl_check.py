# -*- coding: utf-8 -*-
"""Dagelijkse NL-check voor slots: staat een (nieuwe) slot al bij Nederlandse KSA-casino's?

Voor elke slot met 'Status NL' anders dan 'Beschikbaar in NL' (of met --all: elke slot) wordt bij de
casino's gekeken of er een spelpagina is (200 + de naam in de titel; niet gevonden = 404). Bij een treffer:
  - casino's toevoegen aan 'casino-s' (alleen live bookmakers),
  - 'Status NL' -> 'Beschikbaar in NL', 'Live in NL' -> vandaag (als die nog niet in het verleden lag),
  - FAQ 5 ('Is <naam> beschikbaar in Nederland?') opnieuw schrijven,
  - item live bijwerken als het gepubliceerd is, en de deelafbeelding opnieuw maken.
Zonder treffer: status 'Binnenkort in NL' (als 'Live in NL' in de toekomst ligt) of 'Nog niet in NL'.

Bronnen per casino (sleutel = naam exact zoals in de Bookmakers-collectie), alleen-lezen, robots.txt gerespecteerd:
  - URL-sjablonen (CASINOS, 1 request per slug):  Unibet, LeoVegas, BetMGM, Toto, JACKS.NL, 711, Winz
  - sitemap (SITEMAPS, 1 request per run):         Starcasino, Oranje Palace, One Casino
      One Casino zet soms een code achter de naam (starburstr300000): zonder exacte treffer wordt zo'n
      kandidaat geopend en telt hij alleen als de paginatitel exact de slotnaam is.
  - publieke spelcatalogus (KATALOGI, één keer per run, exacte genormaliseerde naam + providercheck):
      Vbet       go-cms.vbet.nl games/pages/N (24 per pagina, ~107 requests) -> /nl/casino/game-view/<id>/<alias>
                 (eigen sitemapformaat; anoniem = inlogscherm voor het spel, onbekend id = 'niet beschikbaar')
      Tonybet    platform.tonybet.nl/api/v3/casino/game (500 per pagina, ~8 requests) -> providerpagina
                 /casino/all/<provider> (spelpagina's sturen anonieme bezoekers naar de homepage)
      Hard Rock  hardrockcasino.nl/api/games (robots: Allow /api/games; 500 per pagina, ~10 requests)
                 -> /spelreviews/<slug> als die in de sitemap staat, anders /g/nl/<code>/fun|real (404 bij onbekend)
  - handmatige spellijst (KATALOGI, alleen naam, geen provider): Bet365 = state/bet365_gamelijst.json, door Jasper
      gekopieerd van casino.bet365.nl/gameslist/nl (23-10-2026; site blokkeert scripts). Opnieuw plakken = bijwerken.
  - Circus = state/circus_gamelijst.json: slugs van onze slots die op circus.nl/nl/casino/slots/alle-slots staan
      (23-10-2026 eenmalig in de ingebouwde browser vergeleken; scripts krijgen 403). Nieuwe lijst = opnieuw vergelijken.
  - Bingoal = state/bingoal_gamelijst.json: id, naam en provider van 4.669 spellen (25-10-2026 in de ingebouwde browser
      via het aanbiedersfilter; scripts krijgen een Cloudflare-blokkade) -> /nl/casino/spel/<id>/. Nieuwe lijst = opnieuw uitlezen.
  - niet mogelijk (23-10-2026): 888 Casino/Sport en ComeOn! (robots.txt verbiedt /rest/* én /*/casino/game*; spellijst alleen via /rest).

  python slot_nl_check.py            # dry-run
  python slot_nl_check.py --write    # bijwerken (LaunchAgent: dagelijks)
  python slot_nl_check.py --write --all   # ook casinolijsten van al beschikbare slots aanvullen
  python slot_nl_check.py --write --all --alleen=Bet365   # alleen deze casino('s) controleren (komma-gescheiden)
"""
import datetime as dt, html, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from slot_og import SLOTS, PROVIDERS, _all_items, _env, _wf

HERE = os.path.dirname(os.path.abspath(__file__))
BOOKMAKERS = "64ff0fbd5a8f205b05d54686"
ALIASES = os.path.join(HERE, "state", "slot_nl_aliases.json")   # slug -> extra URL-slugs (bv. officiële naam)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "nl-NL,nl;q=0.9"}
STATUS = {"ja": "Beschikbaar in NL", "binnenkort": "Binnenkort in NL", "nee": "Nog niet in NL"}
MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()

# casino (naam zoals in de Bookmakers-collectie) -> URL-sjablonen
CASINOS = {
    "Unibet": ["https://www.unibet.nl/play/{s}"],
    "LeoVegas": ["https://www.leovegas.nl/game/{s}"],
    "BetMGM": ["https://www.betmgm.nl/casino/slots/{s}"],
    "Toto": ["https://casino.toto.nl/casino/games/{s}", "https://casino.toto.nl/casino/games/{s}-{p}"],
    "JACKS.NL": ["https://jacks.nl/casino/slots/{s}"],
    "711": ["https://www.711.nl/casino/{p}/{s}", "https://www.711.nl/casino/{p711}/{s}"],
    "Winz": ["https://www.winz.nl/slots/{s}"],   # 26-10-2026: titel 'Naam - Provider | Winz', onbekend = 404 (sitemap is onvolledig)
}
P711 = {"elk-studios": "elk", "print-studios": "silver-bullet"}   # 711 gebruikt soms een andere providermap
# casino's zonder voorspelbare game-URL: opzoeken in hun eigen sitemap (23-10-2026). naam -> (sitemap, url-regex)
SITEMAPS = {
    "Starcasino": ("https://starcasino.nl/sitemap-games-nl.xml", r"<loc>(https://starcasino\.nl/game/[^/<]+/([^<]+))</loc>"),
    "Oranje Palace": ("https://www.oranjepalace.nl/sitemap.xml", r"<loc>(https://www\.oranjepalace\.nl/nl/spellen/([^<]+))</loc>"),
    "One Casino": ("https://nl.onecasino.com/sitemap.xml", r"<loc>(https://nl\.onecasino\.com/casino/([a-z0-9]+))</loc>"),
}
# sitemap-casino's waarvan de slug soms een code achter de naam heeft: kandidaat openen, titel vóór dit teken = naam
SITEMAP_TITEL = {"One Casino": "➡"}
_SM = {}
_KAT = {}
_LAATST = {}                                      # host -> tijdstip laatste request (throttle)


def _kern(t):
    return re.sub(r"[^a-z0-9]", "", slugify(re.sub(r"[™®©]", "", t or "")))


def _get(url, timeout=60):
    """GET met minstens 0,6 s tussen requests per host; geeft de body als tekst."""
    host = urllib.parse.urlsplit(url).netloc
    wacht = _LAATST.get(host, 0) + 0.6 - time.time()
    if wacht > 0:
        time.sleep(wacht)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    finally:
        _LAATST[host] = time.time()


def sitemap_index(casino):
    """{genormaliseerde gamenaam: url} uit de sitemap van het casino (één keer per run)."""
    if casino not in _SM:
        url, rx = SITEMAPS[casino]
        try:
            xml = _get(url)
            _SM[casino] = {}
            for m in re.finditer(rx, xml):
                _SM[casino].setdefault(_kern(m.group(2)), m.group(1))
        except Exception as e:
            print(f"[{casino}] sitemap niet bruikbaar: {e}", file=sys.stderr)
            _SM[casino] = {}
    return _SM[casino]


def _titel_check(casino, idx, kern):
    """Sitemap-slug = naam + code (bv. starburstr300000): open max. 3 kandidaten, exacte titel telt."""
    code = re.compile(r"(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{3,8}")   # letters én cijfers (geen '1000'-versies)
    for slug in [s for s in idx if s.startswith(kern) and code.fullmatch(s[len(kern):])][:3]:
        try:
            t = re.search(r"<title[^>]*>(.*?)</title>", _get(idx[slug], 25), re.S | re.I)
        except Exception:
            continue
        if t and _kern(html.unescape(t.group(1)).split(SITEMAP_TITEL[casino])[0]) == kern:
            return idx[slug]
    return None


# --- publieke spelcatalogi: {genormaliseerde naam: [(provider, url), ...]} -----------------------------------
def _kat_vbet():
    api = "https://go-cms.vbet.nl/api/public/v1/dut/casino/partners/18756479/platforms/0/games/pages/{}"
    idx, page, last = {}, 1, 1
    while page <= last and page <= 300:
        d = json.loads(_get(api.format(page)))["data"]
        last = d["lastPage"]
        for g in d["data"]:
            idx.setdefault(_kern(g["name"]), []).append(
                ((g.get("provider") or {}).get("title", ""), f"https://www.vbet.nl/nl/casino/game-view/{g['id']}/{g['alias']}"))
        page += 1
    return idx


def _kat_tonybet():
    api = "https://platform.tonybet.nl/api/v3/casino/game?has_live=0&is_desktop=1&perPage=500&page={}&_trlang=nl"
    idx, page = {}, 1
    while page <= 40:
        d = json.loads(_get(api.format(page)))["data"]
        for g in d["items"]:
            p = g.get("producer") or {}
            idx.setdefault(_kern(g["title"]), []).append(
                (p.get("text") or p.get("name", ""), f"https://tonybet.nl/casino/all/{p.get('platformSlug') or p.get('name')}"))
        if not d["pagination"].get("gotMore"):
            break
        page += 1
    return idx


def _kat_hardrock():
    api = "https://hardrockcasino.nl/api/games?device_support=desktop&locale=nl&per_page=500&page={}"
    try:                                           # spelreviews = echte, publieke spelpagina's (alleen populaire titels)
        rev = {_kern(m.group(2)): m.group(1) for m in
               re.finditer(r"<loc>(https://hardrockcasino\.nl/spelreviews/([^<]+))</loc>", _get("https://hardrockcasino.nl/sitemap.xml"))}
    except Exception:
        rev = {}
    idx, page, last = {}, 1, 1
    while page <= last and page <= 40:
        d = json.loads(_get(api.format(page)))
        last = d["meta"]["last_page"]
        for g in d["data"]:
            k = _kern(g["name"])
            url = rev.get(k) or (g.get("fun_play_url") if g.get("fun_play") else None) or g.get("real_play_url")
            if url:
                idx.setdefault(k, []).append((g.get("provider", ""), url))
        page += 1
    return idx


def _kat_bet365():
    d = json.load(open(os.path.join(HERE, "state", "bet365_gamelijst.json")))
    idx = {}
    for namen in d["secties"].values():
        for n in namen:
            idx.setdefault(_kern(n), []).append(("", d["bron"]))
    return idx


def _kat_circus():
    d = json.load(open(os.path.join(HERE, "state", "circus_gamelijst.json")))
    return {_kern(sl): [("", d["bron"])] for sl in d["slugs"]}


def _kat_bingoal():
    d = json.load(open(os.path.join(HERE, "state", "bingoal_gamelijst.json")))
    idx = {}
    for g in d["spellen"]:
        idx.setdefault(_kern(g["naam"]), []).append((g.get("provider", ""), f"https://www.bingoal.nl/nl/casino/spel/{g['id']}/"))
    return idx


KATALOGI = {"Vbet": _kat_vbet, "Tonybet": _kat_tonybet, "Hard Rock Casino": _kat_hardrock, "Bet365": _kat_bet365,
            "Circus": _kat_circus, "Bingoal": _kat_bingoal}
ALLEEN = None                                     # --alleen=A,B: alleen deze casino's controleren


def katalogus(casino):
    """Spelcatalogus van het casino, één keer per run; bij een fout leeg (casino wordt dan overgeslagen)."""
    if casino not in _KAT:
        try:
            _KAT[casino] = KATALOGI[casino]()
        except Exception as e:
            print(f"[{casino}] catalogus niet bruikbaar: {e}", file=sys.stderr)
            _KAT[casino] = {}
    return _KAT[casino]


def _prov_ok(prov_slug, naam):
    a, b = _kern(prov_slug), _kern(naam)
    return not a or not b or a in b or b in a or a[:4] == b[:4]


def _kies(treffers, prov_slug):
    """Bij dezelfde naam van meerdere providers: alleen de juiste provider; één provider: altijd (aggregatornamen)."""
    if not treffers:
        return None
    goed = [u for p, u in treffers if _prov_ok(prov_slug, p)]
    if goed:
        return goed[0]
    return treffers[0][1] if len({_kern(p) for p, u in treffers}) == 1 else None


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("&", "and")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.replace("'", ""))).strip("-")


def datum_nl(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def _probe(url, name):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            body = r.read(400000).decode("utf-8", "replace")
            final = r.geturl()
    except Exception:
        return False
    t = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    title = slugify(html.unescape(t.group(1))) if t else ""
    core = "-".join(slugify(name).split("-")[:2])            # eerste twee woorden van de naam
    return bool(core) and core in title and slugify(name).split("-")[0] in final.lower()


def find_casinos(item, prov_slug):
    fd = item["fieldData"]
    aliases = json.load(open(ALIASES)).get(fd["slug"], []) if os.path.exists(ALIASES) else []
    slugs = list(dict.fromkeys([fd["slug"], slugify(fd["name"])] + aliases))
    found = {}
    for casino, templates in CASINOS.items():
        if ALLEEN and casino not in ALLEEN:
            continue
        for tpl in templates:
            for s in slugs:
                url = tpl.format(s=s, p=prov_slug or "", p711=P711.get(prov_slug, prov_slug or ""))
                if "{" in url or url.endswith("//" + s) or "/-" in url:
                    continue
                if _probe(url, fd["name"]):
                    found[casino] = url
                    break
                time.sleep(0.5)
            if casino in found:
                break
    kernen = list(dict.fromkeys(_kern(s) for s in slugs))
    for casino in SITEMAPS:                       # exacte naam- of slugmatch in de sitemap
        if ALLEEN and casino not in ALLEEN:
            continue
        idx = sitemap_index(casino)
        for k in kernen:
            if k in idx:
                found[casino] = idx[k]
                break
        else:
            if casino in SITEMAP_TITEL and idx:   # naam + code in de slug: alleen bij exacte paginatitel
                for k in kernen:
                    url = _titel_check(casino, idx, k)
                    if url:
                        found[casino] = url
                        break
    for casino in KATALOGI:                       # exacte genormaliseerde naam in de spelcatalogus (+ providercheck)
        if ALLEEN and casino not in ALLEEN:
            continue
        idx = katalogus(casino)
        for k in kernen:
            url = _kies(idx.get(k), prov_slug)
            if url:
                found[casino] = url
                break
    return found


def faq5(name, status, release, live_nl, casinos):
    q = f"Is {name} beschikbaar in Nederland?"
    if status == STATUS["ja"]:
        namen = [c for c in casinos][:2]
        extra = f", zoals {' en '.join(namen)}" if namen else ""
        sinds = f"sinds {datum_nl(live_nl)} " if live_nl else ""
        a = (f"Ja. {name} is {sinds}te spelen bij Nederlandse casino's met een vergunning van de Kansspelautoriteit{extra}. "
             "Speel alleen bij een casino met een KSA-vergunning.")
    else:
        uit = f"kwam op {datum_nl(release)} uit, maar " if release else ""
        a = f"Nog niet. {name} {uit}staat nog niet bij Nederlandse casino's met een KSA-vergunning. "
        a += (f"De verwachte lancering in Nederland is {datum_nl(live_nl)}. " if status == STATUS["binnenkort"] and live_nl
              else "Een Nederlandse lanceerdatum is nog niet bekend. ")
        a += "Wij controleren dit dagelijks en passen deze pagina aan zodra het spel hier live staat."
    return q, a


NIEUW_DAGEN = 90


def is_nieuw(status, release, live_nl, today):
    """Nieuw = in de laatste 90 dagen uitgekomen (NL-datum, anders wereldwijd), of recent/aangekondigd maar nog niet in NL."""
    t = dt.date.fromisoformat(today)
    grens = (t - dt.timedelta(days=NIEUW_DAGEN)).isoformat()
    if status != STATUS["ja"]:
        return not release or release >= (t - dt.timedelta(days=180)).isoformat()
    if release and release < (t - dt.timedelta(days=180)).isoformat():
        return False                               # oude titel die we later toevoegden: niet "nieuw", ook al is de NL-datum recent
    d = live_nl or release
    return bool(d) and grens <= d <= today


def main(argv):
    _env()
    global ALLEEN
    write, alles = "--write" in argv, "--all" in argv
    ALLEEN = next((set(a.split("=", 1)[1].split(",")) for a in argv if a.startswith("--alleen=")), None)
    today = dt.date.today().isoformat()
    items = _all_items(SLOTS)
    provs = {p["id"]: p["fieldData"]["slug"] for p in _all_items(PROVIDERS)}
    books = {b["fieldData"]["name"]: b["id"] for b in _all_items(BOOKMAKERS) if not b.get("isDraft") and not b.get("isArchived")}
    opt = {o["name"]: o["id"] for f in _wf(f"/collections/{SLOTS}")["fields"] if f["slug"] == "status-nl"
           for o in f["validations"]["options"]}
    name_of = {v: k for k, v in opt.items()}
    changed, rerender = [], []
    for it in items:
        fd = it["fieldData"]
        status = name_of.get(fd.get("status-nl"))
        if status == STATUS["ja"] and not alles:
            nieuw = is_nieuw(status, (fd.get("releasedatum") or "")[:10] or None, (fd.get("live-in-nl") or "")[:10] or None, today)
            if nieuw != bool(fd.get("nieuw")):
                changed.append((it, {"nieuw": nieuw}))
                print(f"{fd['name'][:32]:32} nieuw -> {nieuw}")
            continue
        found = find_casinos(it, provs.get(fd.get("provider")))
        cas_ids = [books[c] for c in found if c in books]
        live_nl = (fd.get("live-in-nl") or "")[:10] or None
        new = {}
        release = (fd.get("releasedatum") or "")[:10] or None
        if found and release and release > today:          # casino heeft de pagina al, maar het spel is nog niet uit
            new_status, live_nl = STATUS["binnenkort"], release
        elif found:
            new_status = STATUS["ja"]
            if not live_nl or live_nl > today:
                live_nl = today
        else:
            new_status = STATUS["binnenkort"] if live_nl and live_nl > today else (status if status == STATUS["ja"] else STATUS["nee"])
        if found:
            merged = list(dict.fromkeys((fd.get("casino-s") or []) + cas_ids))
            if merged != (fd.get("casino-s") or []):
                new["casino-s"] = merged
        if new_status != status:
            new["status-nl"] = opt[new_status]
        if live_nl and live_nl != (fd.get("live-in-nl") or "")[:10]:
            new["live-in-nl"] = live_nl + "T00:00:00.000Z"
        managed = not fd.get("faq-5-vraag") or fd["faq-5-vraag"].startswith(f"Is {fd['name']} beschikbaar in Nederland")
        if managed and (new or not fd.get("faq-5-vraag")):
            new["faq-5-vraag"], new["faq-5-antwoord"] = faq5(fd["name"], new_status, (fd.get("releasedatum") or "")[:10] or None,
                                                             live_nl, [c for c in found] or [])
        nieuw = is_nieuw(new_status, (fd.get("releasedatum") or "")[:10] or None, live_nl, today)
        if nieuw != bool(fd.get("nieuw")):
            new["nieuw"] = nieuw
        print(f"{fd['name'][:32]:32} {status or '-':18} -> {new_status:18} {', '.join(found) or 'geen NL-casino'}")
        if new:
            changed.append((it, new))
            if "status-nl" in new:
                rerender.append(fd["slug"])
    # slots zonder demo: kijk of SlotsLaunch de game inmiddels heeft (demo-ID + afbeelding; deelafbeelding opnieuw)
    import slot_publish
    prov_sl = {p["id"]: p["fieldData"].get("slotslaunch-provider-id") for p in _all_items(PROVIDERS)}
    norm = lambda t: re.sub(r"[^a-z0-9]", "", slugify(t))
    geo = set(json.load(open(os.path.join(HERE, "state", "slot_demo_geoblocked.json"))))   # demo geblokkeerd in NL
    for it in items:
        fd = it["fieldData"]
        pid = prov_sl.get(fd.get("provider"))
        if fd.get("slotslaunch-game-id") or not pid or fd["slug"] in geo:
            continue
        slot_publish.sl_game(1, pid)
        g = next((g for g in slot_publish._SL_CACHE.get(pid, {}).values() if norm(g["name"]) == norm(fd["name"])), None)
        if g:
            new = {"slotslaunch-game-id": g["id"]}
            if not (fd.get("afbeelding") or {}).get("url") and g.get("thumb"):
                new["afbeelding"] = {"url": g["thumb"], "alt": fd["name"]}
            print(f"{fd['name'][:32]:32} demo gevonden bij SlotsLaunch: {g['id']}")
            changed.append((it, new))
            rerender.append(fd["slug"])
    if not write or not changed:
        print(f"{len(changed)} wijzigingen" + ("" if write else " (dry-run)"))
        return
    merged = {}
    for it, new in changed:                        # één regel per item (Webflow weigert dubbele items)
        merged.setdefault(it["id"], (it, {}))[1].update(new)
    staged = [{"id": i, "fieldData": new} for i, (it, new) in merged.items()]
    live = [{"id": i, "fieldData": new} for i, (it, new) in merged.items() if it.get("lastPublished") and not it.get("isDraft")]
    rerender = list(dict.fromkeys(rerender))
    for path, rows in (("items", staged), ("items/live", live)):
        for i in range(0, len(rows), 25):
            print("PATCH", path, _wf(f"/collections/{SLOTS}/{path}", "PATCH", {"items": rows[i:i + 25]}))
    if rerender:                                   # status-pil op de deelafbeelding bijwerken
        import slot_og
        slot_og.main(rerender + ["--attach"])
    # nieuwe slots die vandaag in NL live gingen: melden in het casino-kanaal
    nu_live = [it["fieldData"]["slug"] for i, (it, new) in merged.items()
               if new.get("status-nl") == opt[STATUS["ja"]] and name_of.get(it["fieldData"].get("status-nl")) in (STATUS["nee"], STATUS["binnenkort"])]
    if nu_live and not os.environ.get("GEEN_TELEGRAM"):
        import casino_telegram as T
        provs = {p["id"]: p["fieldData"] for p in _all_items(PROVIDERS)}
        fresh = {i["fieldData"]["slug"]: i for i in _all_items(SLOTS)}
        for sl in nu_live:
            it = fresh.get(sl)
            if not it["fieldData"].get("nieuw"):   # oudere titels die we later aanvulden niet als "nu live" melden
                continue
            pf = provs.get(it["fieldData"].get("provider")) or {}
            if T.post_slot(it, "live_nl", pf.get("name"), pf.get("slug")):
                print(f"Telegram casino: {it['fieldData']['name']} nu live in NL gepost")


if __name__ == "__main__":
    main(sys.argv[1:])
