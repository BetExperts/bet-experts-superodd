# -*- coding: utf-8 -*-
"""Wedtips voor nieuwe voorbeschouwingen uit FootyMetrics (gebruiker, 22-10-2026).

Voor elke voorbeschouwing (Nieuws-collectie, 'wedtips' in de slug) met een lege 'Wedtip 1' en een
aftrap in de toekomst zoekt dit script de wedstrijd op FootyMetrics en verzamelt kandidaat-tips uit:
  - team trends van de wedstrijd (hit rate, hits tegen de tegenstander, H2H-hits, odds per bookmaker)
  - player trends van de wedstrijd (hit rate + AI-modelkans, odds per bookmaker)
  - de AI-kansen van de wedstrijd (over/under, BTTS, teamgoals, corners)
Per kandidaat een geschatte kans (model + trend + tegenstander + H2H) en value = kans × odd − 1.
Daaruit max. 4 tips, beste eerst (Wedtip 1 = beste), elke odd ≥ 1.45, max. 2 spelers-tips, één tip
per markt. Eén NL-bookmaker per artikel (die de meeste van de beste tips aanbiedt); de quoteringen
zijn van die bookmaker. Kambi-odds → vaste keuze uit Jaspers Kambi-partners, nooit BetCity.

Schrijft ALLEEN staged (PATCH /items/{id}): drafts blijven draft, ingeplande items blijven ingepland,
niets gaat live. Velden die al gevuld zijn worden nooit overschreven. Jasper controleert alles.

Draaien (Mac, gebruikt een kopie van het FootyMetrics-scannerprofiel):
    .venv/bin/python fm_wedtips.py --dry            # voorstellen tonen
    .venv/bin/python fm_wedtips.py                  # velden invullen
    .venv/bin/python fm_wedtips.py --slug <slug>    # één voorbeschouwing (ook --dry)
"""
import argparse, html, json, os, re, shutil, statistics, tempfile, time, unicodedata, urllib.request, zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

PROFILE = Path.home() / "Library" / "Application Support" / "betexperts-footymetrics-chrome"
BASE = "https://www.footymetrics.com"
TOKEN = os.environ.get("WEBFLOW_TOKEN", "")
NIEUWS = "64ff0fbd5a8f205b05d54656"

MIN_ODD, MIN_HIT, MIN_KANS, MAX_TIPS, MAX_SPELERS = 1.45, 70, 0.55, 4, 2
# Geen enkele tip voldoet? Dan toch de beste losse tip (Jasper 22-10: "1 wedtip is ook goed, als het maar de beste is").
FALLBACK_KANS, FALLBACK_ODD, FALLBACK_VALUE = 0.50, 1.40, -0.08
# Super sub (invalregel bij bookmakers, bv. Wissel+/Gouden Wissel) alleen in topcompetities; lagere competities hebben
# dat niet (Jasper 22-10). FootyMetrics-league-ids: PL, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, CL, EL, ECL.
SUPER_SUB_LEAGUES = {8, 564, 384, 82, 301, 72, 2, 5, 2286}
MIN_VALUE = -0.05    # geschatte value; licht negatief mag (sterke trend, odd ≥1.45), sortering blijft op value
MIN_VAN = 5          # trend over minstens 5 wedstrijden ('thuis 4/4' is te dun)
# Teammarkten zoals Jasper ze tipt
# (Jaspers selectie 22-10: BTTS, goals, shots, shots on target, tackles, saves; geen corners/kaarten/fouls/offsides.)
TEAM_KEYS = {"goals", "btts", "sh", "sot", "tackles", "saves"}
ALLE_BK = "1,2,3,4,5,101,102,104,105,106,107,109,110,111,112,113,114,115,116,117,118,120"

# NL-merkgroepen: FootyMetrics-id's met dezelfde odds → (Webflow Bookmakers-item)
GROEPEN = {
    "bet365": {"ids": (1,), "item": ("Bet365", "651bd6728c40de720bd8072a")},
    "toto": {"ids": (104,), "item": ("TOTO", "669ab9f5aceb8b717cea24c3")},
    "starcasino": {"ids": (5, 105), "item": ("Starcasino", "6a7afdaa4a7453c17d31cab5")},
    "kambi": {"ids": (2, 101), "item": None},     # → Kambi-partner, zie kambi_partner()
}
KAMBI_PARTNERS = [("JACKS.NL", "64ff0fbd5a8f205b05d5465c"), ("Bingoal", "68dd287867de5cd59d44dc39"),
                  ("BetMGM", "66bb685ec057aa8c4337ceea"), ("LeoVegas", "6526a08a94d8631739581743"),
                  ("Oranje Palace", "6aad0c21a14e9435daf42e79")]


# ---------------------------------------------------------------- webflow
def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN, "accept": "application/json", "content-type": "application/json"})
    for _ in range(5):
        try:
            return json.load(urllib.request.urlopen(r, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After", "5")) + 1)
                continue
            raise
    raise RuntimeError("Webflow blijft weigeren")


WEDTIP_VELDEN = [f"wedtip-{i}-2" for i in range(1, 5)] + [f"quotering-wedtip-{i}" for i in range(1, 5)] \
    + ["bookmaker-wedtips"]
STATE = Path(__file__).resolve().parent / "state" / "fm_wedtips.json"   # wat de agent zelf invulde


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def eigen_invulling(it, state):
    """True als de wedtipvelden nog precies zo staan als de agent ze invulde (Jasper heeft niets aangepast)."""
    oud = state.get(it["id"])
    fd = it["fieldData"]
    return bool(oud) and all((fd.get(k) or "") == (oud.get(k) or "") for k in WEDTIP_VELDEN)


def voorspelling(fd):
    """Voorspelde uitslag van de preview-agent: velden thuisteam-score/uitteam-score, anders 'Eindvoorspelling: 2-1'."""
    a, b = fd.get("thuisteam-score"), fd.get("uitteam-score")
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return int(a), int(b)
    tekst = re.sub(r"<[^>]+>", "", " ".join(fd.get(v) or "" for v in ("content", "content-2", "content-3")))
    m = re.search(r"Eindvoorspelling:\s*(\d+)\s*-\s*(\d+)", html.unescape(tekst))
    return (int(m.group(1)), int(m.group(2))) if m else None


def voorbeschouwingen(slug=None, herzien=False, state=None):
    """Staged items (dus ook drafts/ingepland) met lege Wedtip 1 en aftrap in de toekomst.
    herzien: ook items die de agent eerder invulde en die Jasper nog niet heeft aangepast."""
    now = datetime.now(timezone.utc)
    items = []
    for off in range(0, 400, 100):
        b = _req("GET", f"https://api.webflow.com/v2/collections/{NIEUWS}/items?limit=100&offset={off}"
                        f"&sortBy=createdOn&sortOrder=desc").get("items") or []
        items += b
        if len(b) < 100:
            break
    uit = []
    for it in items:
        fd = it["fieldData"]
        # rubriek Voorbeschouwing (switch) = altijd een wedtip-artikel; teams uit de titel 'Wedtips X – Y: …'
        if not fd.get("voorbeschouwing-2") or not teams(fd.get("name"))[0] or (slug and fd["slug"] != slug):
            continue
        if not slug and (fd.get("wedtip-1-2") or "").strip() \
                and not (herzien and eigen_invulling(it, state or {})):
            continue
        ko = fd.get("datum-tijd-van-wedstrijd")
        if not ko or ts(ko) < now:
            continue
        thuis, uitteam = teams(fd.get("name"))
        if thuis:
            uit.append({"item": it, "ko": ts(ko), "thuis": thuis, "uit": uitteam, "score": voorspelling(fd)})
    return uit


# ---------------------------------------------------------------- helpers
def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def norm(s):
    s = unicodedata.normalize("NFKD", html.unescape(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


STOP = {"fc", "sc", "ac", "afc", "cf", "sv", "vfb", "rb", "as", "us", "ss", "sk", "kv", "club", "de", "real",
        "atletico", "borussia", "manchester", "sporting", "united", "city", "inter", "racing", "madrid",
        "milan", "athletic", "olympique", "paris", "saint", "royal", "union", "young", "jong", "tc", "lp",
        "u21", "u23", "saudi", "top"}


def zelfde_team(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    wa = {w for w in a.split() if len(w) >= 3 and w not in STOP}
    wb = {w for w in b.split() if len(w) >= 3 and w not in STOP}
    return bool(wa & wb)


def teams(naam):
    m = re.search(r"Wedtips\s+(.*?)\s*:", html.unescape(naam or ""))
    p = re.split(r"\s+[–—-]+\s+", m.group(1).strip()) if m else []
    return (p[0].strip(), p[-1].strip()) if len(p) >= 2 else (None, None)


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- footymetrics
class FM:
    """Headless Chrome op een kopie van het scannerprofiel (de LaunchAgent gebruikt het origineel)."""

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp()) / "p"
        shutil.copytree(PROFILE, self.tmp, ignore=shutil.ignore_patterns(
            "Singleton*", "*.lock", "Cache", "Code Cache", "GPUCache", "Service Worker", "RunningChromeVersion"),
            ignore_dangling_symlinks=True)   # Chrome-symlinks die alleen bestaan terwijl de scanner draait
        self.pw = sync_playwright().start()
        self.ctx = self.pw.chromium.launch_persistent_context(str(self.tmp), channel="chrome", headless=True)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.goto(f"{BASE}/trends/player-all", wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(3000)
        return self

    def __exit__(self, *a):
        self.ctx.close()
        self.pw.stop()
        shutil.rmtree(self.tmp.parent, ignore_errors=True)

    def get(self, path, params=None, verplicht=False):
        url = path + ("?" + urlencode(params) if params else "")
        for poging in range(4):
            res = self.page.evaluate("""async (u) => {
                const r = await fetch(u, {credentials: 'include'});
                return {s: r.status, b: r.ok ? await r.json() : null};
            }""", url)
            time.sleep(0.8)
            if res["s"] == 200:
                return res["b"]
            if res["s"] not in (429, 500, 502, 503, 504):
                break
            time.sleep(10 * (poging + 1))            # afgeremd: rustig opnieuw
        if verplicht:
            raise RuntimeError(f"FootyMetrics gaf {res['s']} op {path}")
        return None

    def fixtures(self, datum):
        lijst = self.get("/api/front/fixtures", {"date": datum, "tz": "Europe/Amsterdam", "late": 1}) or []
        return [f for l in lijst for f in l.get("fixtures") or []]

    def alle_paginas(self, path, params):
        uit, page, pages = [], 1, 1
        while page <= min(pages, 6):
            b = self.get(path, {**params, "page": page}, verplicht=True) or {}
            uit += b.get("data") or []
            pages = (b.get("pagination") or {}).get("pages") or 1
            page += 1
        return uit

    def team_trends(self, apid):
        return self.alle_paginas(f"/api/front/trends/fixtures/{apid}/teams", {
            "sort": "hr-h", "min_opp_hits": 0, "min_h2h_hits": 0, "min_hit": 70, "min_matches": 4,
            "directions": "over,under,yes,no,most", "parties": "match,team",
            "markets": "1,2,3,4,5,6,7,8,9,10", "bookmakers": ALLE_BK, "league_only": "false"})

    def speler_trends(self, apid, super_sub=False):
        return self.alle_paginas(f"/api/front/trends/fixtures/{apid}/players", {
            # zelfde als Jaspers filter (22-10): Started only (so), Super sub (ss), inactieve spelers en
            # niet-starters uitsluiten (xin/xnrs). Zonder 'so' telden invalbeurten mee en vielen o.a. Canales weg.
            "sort": "hr-h", "min_hit": 70, "min_matches": 4, "lineup": "all", "lines": "", "pos": "1,2,3,4",
            "so": "true", "xin": "true", "xnrs": "true", **({"ss": "true"} if super_sub else {}),
            "bookmakers": ALLE_BK, "markets": "1,2,3,4,5,14,6,12,7,8,9,10,15,11,13", "league_only": "false"})

    def ai(self, apid):
        return (self.get(f"/api/front/predictions/{apid}/premium") or {}).get("matchProbability") or {}


def zoek_fixture(fm, v, cache):
    datum = v["ko"].astimezone(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    for d in {datum, (v["ko"] - timedelta(hours=12)).strftime("%Y-%m-%d"), v["ko"].strftime("%Y-%m-%d")}:
        if d not in cache:
            cache[d] = fm.fixtures(d)
        for f in cache[d]:
            if abs((ts(f["timestamp"]) - v["ko"]).total_seconds()) <= 900 \
                    and zelfde_team((f.get("Home") or {}).get("name"), v["thuis"]) \
                    and zelfde_team((f.get("Away") or {}).get("name"), v["uit"]):
                return f
    return None


# ---------------------------------------------------------------- kandidaten
def odds_per_groep(odds, kant):
    """{'bet365': 1.85, 'kambi': 1.80, ...} — hoogste odd per NL-merkgroep voor deze kant."""
    uit, alle = {}, []
    for o in odds or []:
        v = fl(o.get(kant))
        if not v or v <= 1:
            continue
        alle.append((o.get("bk"), v))
        for g, info in GROEPEN.items():
            if o.get("bk") in info["ids"]:
                uit[g] = max(v, uit.get(g, 0))
    # Uitschieters weg: een odd ≥1.35× de mediaan van de andere bookmakers is bijna altijd een verkeerd gekoppelde markt
    # (22-10-2026: TOTO 'schot op doel' 2.20 stond bij FootyMetrics als 'schoten' terwijl de rest 1.15-1.20 bood).
    for g in list(uit):
        rest = [v for bk, v in alle if bk not in GROEPEN[g]["ids"]]
        if len(rest) >= 2 and uit[g] >= 1.35 * statistics.median(rest):
            del uit[g]
    return uit


def lijn_sleutel(line):
    """2.5 → '25' (voor prob_over25)."""
    return str(line).replace(".", "")


def ai_kans(ai, fx, t):
    """AI-kans van de wedstrijd voor een team trend, als die markt in de AI-voorspelling zit."""
    if not ai:
        return None
    m, d, l = t.get("market") or "", t.get("direction"), lijn_sleutel(t.get("line"))
    k = None
    if m == "total_goals":
        k = f"prob_{d}{l}"
    elif m in ("home_goals", "away_goals"):
        k = f"prob_{m.split('_')[0]}_{d}{l}"
    elif m == "btts" or t.get("key") == "btts":
        k = "prob_btts" if d == "yes" else "prob_btts_no"
    elif m == "total_corners":
        k = f"prob_{d}{l}_corners"
    v = ai.get(k) if k else None
    if v is None and k:
        v = fx.get(k)          # de wedstrijdlijst heeft een deel van de kansen ook
    return v / 100 if v is not None else None


def schat(hit, van, opp=None, h2h=None, model=None):
    """Geschatte kans: modelkans weegt het zwaarst, daarna de trend (gekrompen naar 50%),
    hits tegen deze tegenstander-categorie en de onderlinge duels."""
    delen = [((hit * van / 100 + 2) / (van + 4), 3)]
    if model is not None:
        delen.append((model, 4))
    if opp is not None:
        delen.append((opp, 2))
    if h2h is not None:
        delen.append((h2h, 1))
    return sum(p * w for p, w in delen) / sum(w for _, w in delen)


EENHEID = {"goals": ("doelpunt", "doelpunten"), "corners": ("hoekschop", "hoekschoppen"),
           "cards": ("kaart", "kaarten"), "sh": ("schot", "schoten"), "sot": ("schot op doel", "schoten op doel"),
           "tackles": ("tackle", "tackles"), "foulsc": ("overtreding", "overtredingen"),
           "foulsC": ("overtreding", "overtredingen"), "foulsD": ("overtreding ondergaan", "overtredingen ondergaan"),
           "offsides": ("buitenspel", "keer buitenspel"), "saves": ("redding", "reddingen"),
           "assists": ("assist", "assists"), "sotob": ("schot op doel van buiten de zestien",
                                                     "schoten op doel van buiten de zestien"),
           "shotsCreated": ("gecreëerde kans", "gecreëerde kansen"), "passes": ("pass", "passes")}


def lijn_tekst(richting, line, key):
    line = fl(line)
    enk, mv = EENHEID.get(key, (key, key))
    woord = "Meer dan" if richting == "over" else "Minder dan"
    return f"{woord} {line:g} {enk if line == 0.5 else mv}"


def team_tip_tekst(t, fx, v):
    """Tekst in Jaspers stijl, met de teamnamen uit het artikel."""
    m, key, d = t.get("market") or "", t.get("key"), t.get("direction")
    if key == "btts" or m == "btts":
        return "Beide teams scoren" if d == "yes" else "Beide teams scoren | NEE"     # Jaspers notatie
    if d not in ("over", "under"):
        return None
    if m.startswith("total_"):
        return lijn_tekst(d, t["line"], key)
    if m.startswith("home_") or m.startswith("away_"):
        team = v["thuis"] if m.startswith("home_") else v["uit"]
        if key == "goals" and d == "over" and fl(t["line"]) == 0.5:
            return f"{team} - Scoort"
        return f"{team} - {lijn_tekst(d, t['line'], key)}"
    return None


def speler_tip_tekst(t):
    key, d, line = t.get("key"), t.get("direction"), fl(t.get("line"))
    if d != "over":
        return None
    if key == "goals" and line == 0.5:
        return f"{t['shortName']} - Scoort"
    if key == "assists" and line == 0.5:
        return f"{t['shortName']} - Geeft een assist"
    if key == "gi" and line == 0.5:
        return f"{t['shortName']} - Scoort of geeft een assist"
    if key not in EENHEID:
        return None
    return f"{t['shortName']} - {lijn_tekst(d, line, key)}"


def past_bij(t, score, speler=False):
    """Sluit de tip aan op de voorspelde uitslag van de voorbeschouwing? (Jasper, 22-10-2026)
    Doelpunten- en BTTS-tips moeten met die uitslag uitkomen; schoten/tackles/reddingen zijn neutraal."""
    if not score:
        return True
    a, b = score
    key, d, m = t.get("key"), t.get("direction"), t.get("market") or ""
    if speler:
        if key in ("goals", "gi", "assists") and d == "over":
            eigen = a if (t.get("Fixture") or {}).get("h") else b
            return eigen > 0
        return True
    if key == "btts" or m == "btts":
        beide = a > 0 and b > 0
        return beide if d == "yes" else not beide
    if key != "goals":
        return True
    waarde = {"total_goals": a + b, "home_goals": a, "away_goals": b}.get(m)
    line = fl(t.get("line"))
    if waarde is None or line is None:
        return True
    return waarde > line if d == "over" else waarde < line


def kandidaten(fm, fx, v, alle_markten=False):
    apid = fx["apid"]
    ai = {**{k: v_ for k, v_ in fx.items() if k.startswith("prob_")}, **fm.ai(apid)}
    uit = []
    for t in fm.team_trends(apid):
        tekst = team_tip_tekst(t, fx, v)
        kant = t.get("direction")
        odds = odds_per_groep(t.get("odds"), kant)
        if not tekst or not odds or (t.get("percentage") or 0) < MIN_HIT or (t.get("bestTotal") or 0) < MIN_VAN:
            continue
        if not alle_markten and t.get("key") not in TEAM_KEYS and t.get("market") != "btts":
            continue
        if not past_bij(t, v.get("score")):
            continue
        opp = (t["oppCount"] / t["oppTotal"]) if (t.get("oppTotal") or 0) >= 5 else None
        h2h = (t["h2hCount"] / t["h2hTotal"]) if (t.get("h2hTotal") or 0) >= 3 else None
        model = (t.get("model") or {}).get("p") or ai_kans(ai, fx, t)
        kans = schat(t["percentage"], t.get("bestTotal") or 0, opp, h2h, model)
        uit.append({"tekst": tekst, "odds": odds, "kans": kans, "soort": "team",
                    "markt": (t.get("market"), t.get("key")), "model": model,
                    "uitleg": f"{t.get('bestCount')}/{t.get('bestTotal')}"
                              + (f", tegenstander {t['oppCount']}/{t['oppTotal']}" if opp is not None else "")
                              + (f", H2H {t['h2hCount']}/{t['h2hTotal']}" if h2h is not None else "")
                              + (f", model {model*100:.0f}%" if model is not None else "")})
    for t in fm.speler_trends(apid, fx.get("leagueApid") in SUPER_SUB_LEAGUES):
        tekst = speler_tip_tekst(t)
        odds = odds_per_groep(t.get("odds"), t.get("direction"))
        model = (t.get("model") or {}).get("p")
        if (not tekst or not odds or (t.get("percentage") or 0) < MIN_HIT or model is None
                or (t.get("bestTotal") or 0) < MIN_VAN):
            continue   # spelers alleen mét modelkans (anders te dun)
        if not past_bij(t, v.get("score"), speler=True):
            continue
        kans = schat(t["percentage"], t.get("bestTotal") or 0, model=model)
        uit.append({"tekst": tekst, "odds": odds, "kans": kans, "soort": "speler",
                    "markt": (t.get("apid"), t.get("key")), "model": model,
                    "uitleg": f"{t.get('bestCount')}/{t.get('bestTotal')}, model {model*100:.0f}%"})
    # dubbelen (zelfde tekst uit 'alle'/'thuis'/'uit'-varianten): beste schatting houden
    beste = {}
    for k in uit:
        if k["tekst"] not in beste or k["kans"] > beste[k["tekst"]]["kans"]:
            beste[k["tekst"]] = k
    return list(beste.values())


def kies(kands, slug):
    """Bookmaker + max. 4 tips (beste eerst)."""
    def value(k, g):
        return k["kans"] * k["odds"][g] - 1

    goed = [k for k in kands if k["kans"] >= MIN_KANS]
    beste_g, beste_tips, beste_score = None, [], -9
    for g in GROEPEN:
        tips = [k for k in goed if k["odds"].get(g, 0) >= MIN_ODD and value(k, g) >= MIN_VALUE]
        tips.sort(key=lambda k: -value(k, g))
        gekozen, markten, spelers = [], set(), 0
        for k in tips:
            if k["markt"] in markten or (k["soort"] == "speler" and spelers >= MAX_SPELERS):
                continue
            gekozen.append(k)
            markten.add(k["markt"])
            spelers += k["soort"] == "speler"
            if len(gekozen) == MAX_TIPS:
                break
        score = sum(value(k, g) + 0.1 for k in gekozen) + 0.05 * len(gekozen)
        if score > beste_score:
            beste_g, beste_tips, beste_score = g, gekozen, score
    if not beste_tips:                                  # terugval: 1 tip, de beste die er is
        for g in GROEPEN:
            for k in kands:
                o = k["odds"].get(g, 0)
                if k["kans"] >= FALLBACK_KANS and o >= FALLBACK_ODD and value(k, g) >= FALLBACK_VALUE:
                    sc = value(k, g) + k["kans"]               # kans telt mee: liever zeker dan net iets meer waarde
                    if sc > beste_score:
                        beste_g, beste_tips, beste_score = g, [k], sc
    if not beste_tips:
        return None, []
    item = GROEPEN[beste_g]["item"] or KAMBI_PARTNERS[zlib.crc32(slug.encode()) % len(KAMBI_PARTNERS)]
    return (beste_g, item), [{**k, "odd": k["odds"][beste_g], "value": value(k, beste_g)} for k in beste_tips]


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--slug")
    ap.add_argument("--alle-markten", action="store_true", help="ook hoekschoppen/kaarten/schoten/reddingen")
    ap.add_argument("--herzien", action="store_true",
                    help="ook eerder door de agent ingevulde items opnieuw doen (alleen als Jasper niets aanpaste)")
    ap.add_argument("--drafts-van", metavar="JJJJ-MM-DD",
                    help="alleen drafts die op deze dag zijn aangemaakt (geen ingeplande of live artikelen)")
    a = ap.parse_args()
    state = load_state()
    lijst = voorbeschouwingen(a.slug, a.herzien, state)
    if a.drafts_van:
        lijst = [v for v in lijst if v["item"].get("isDraft") and not v["item"].get("lastPublished")
                 and (v["item"].get("createdOn") or "").startswith(a.drafts_van)]
    print(f"{len(lijst)} voorbeschouwingen zonder wedtips")
    if not lijst:
        return
    gevuld = 0
    with FM() as fm:
        cache = {}
        for v in sorted(lijst, key=lambda v: v["ko"]):
            it, fd = v["item"], v["item"]["fieldData"]
            status = "draft" if it.get("isDraft") else ("live" if it.get("lastPublished") else "ingepland")
            sc = f", voorspelling {v['score'][0]}-{v['score'][1]}" if v.get("score") else ", geen voorspelling gevonden"
            print(f"\n▶ {v['thuis']} – {v['uit']} ({v['ko'].astimezone(timezone(timedelta(hours=2))):%d-%m %H:%M}, {status}{sc})")
            try:
                fx = zoek_fixture(fm, v, cache)
                groep_item, tips = kies(kandidaten(fm, fx, v, a.alle_markten), fd["slug"]) if fx else (None, [])
            except RuntimeError as e:
                print(f"  ! {e} — overgeslagen, draai later opnieuw")
                continue
            if not fx:
                print("  · niet gevonden op FootyMetrics")
                continue
            if not tips:
                print("  · geen tips die aan de eisen voldoen (odd ≥ 1.45, kans ≥ 55%)")
                continue
            groep, (bk_naam, bk_id) = groep_item
            print(f"  bookmaker: {bk_naam}")
            velden = {"bookmaker-wedtips": bk_id}
            for i, k in enumerate(tips, 1):
                print(f"  {i}. {k['tekst']} @ {k['odd']:.2f}  (kans {k['kans']*100:.0f}%, value {k['value']*100:+.0f}%; {k['uitleg']})")
                velden[f"wedtip-{i}-2"] = k["tekst"]
                velden[f"quotering-wedtip-{i}"] = f"{k['odd']:.2f}"
            if a.dry:
                continue
            # Alleen staged: status blijft zoals hij is, niets gaat live. Gevulde velden niet overschrijven.
            if eigen_invulling(it, state):
                # eigen eerdere invulling vervangen; overgebleven tipvelden leegmaken
                velden = {k: velden.get(k, "") for k in WEDTIP_VELDEN}
            else:
                velden = {k: w for k, w in velden.items() if not (fd.get(k) or "").strip()}
            _req("PATCH", f"https://api.webflow.com/v2/collections/{NIEUWS}/items/{it['id']}",
                 {"fieldData": velden})
            state[it["id"]] = {k: (velden.get(k) if k in velden else fd.get(k)) or "" for k in WEDTIP_VELDEN}
            STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))
            gevuld += 1
            time.sleep(1.1)
    print(f"\n{gevuld} voorbeschouwingen ingevuld (staged).")


if __name__ == "__main__":
    main()
