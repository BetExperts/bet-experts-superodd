# -*- coding: utf-8 -*-
"""Directe bron voor de promo-radar: starcasino.nl/bonussen (staat niet in de bonuskalender).

Levert 'kaarten' in hetzelfde formaat als pr_calendar.fetch_cards(), aangevuld met de
detail-URL, de banner en de volledige tekst van de promotiepagina (bron = StarCasino zelf)."""
import re, hashlib
from datetime import date
from pr_calendar import MAANDEN

BASE = "https://starcasino.nl"
OVERVIEW = BASE + "/bonussen"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# Geen promoties maar producten/features, of welkomstbonussen (die beheert de gebruiker zelf).
SKIP = re.compile(r"^(2up|starcombo|boosts?|jackpots?|toernooien|bonus informatie)\b|welkomst", re.I)

TYPE_RULES = [
    (r"free ?spins?", "freeSpinsBonus"), (r"free ?bet", "freeBetsBonus"), (r"toernooi|prijzenpot", "tournamentBonus"),
    (r"starcoins|starclub|starpoints", "loyaltyBonus"), (r"\bapp\b", "casinoAppsBonus"), (r"jackpot|kluis", "jackpotBonus"),
    (r"win & get|win en get|bet & get", "betAndGetBonus"), (r"stortingsbonus|op je storting", "depositBonus"),
    (r"nations league|voetbal|wedstrijd|weddenschap|live free bet", "sportBonus"), (r"live casino", "liveCasinoBonus"),
]

def _clean(text):
    i = text.find("Inloggen\n")
    text = text[i + 9:] if i >= 0 else text
    for stop in ("Huidige tijd", "\nBlog\nAlles bekijken"):
        j = text.find(stop)
        text = text[:j] if j > 0 else text
    return text.strip()

def _bullets(text):
    """Stappen/voorwaarden uit de tekst: regels met ✅/-/• of genummerd."""
    out = []
    for line in text.split("\n"):
        l = line.strip()
        m = re.match(r"^(?:✅|-|•|\d️⃣|\d+[.)])\s*(.+)$", l)
        if m and 12 <= len(m.group(1)) <= 160:
            out.append(re.sub(r"\s*[🎰🏆⚽🔥📱🍀]+\s*$", "", m.group(1)).strip())
    return out

def _dates(text, today=None):
    """Alle 'DD maand [JJJJ]'-data in de tekst -> (start, end) (None als onbekend)."""
    today = today or date.today()
    found = []
    for d, mnd, y in re.findall(r"\b(\d{1,2})[ -]([a-zA-Z]+)[ -]?(\d{4})?", text):
        mnd = mnd.lower()
        if mnd not in MAANDEN:
            continue
        try:
            found.append(date(int(y) if y else today.year, MAANDEN[mnd], int(d)))
        except ValueError:
            pass
    for d, m, y in re.findall(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", text):
        try:
            found.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    if not found:
        return None, None
    future = [x for x in found if x >= today]
    end = max(future) if future else None
    start = min(found) if end and min(found) < end else None
    return start, end

def fetch(browser):
    ctx = browser.new_context(locale="nl-NL", user_agent=UA)
    pg = ctx.new_page()
    pg.goto(OVERVIEW, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    body = pg.inner_text("body")
    # kaarttitels = regels direct vóór 'Lees meer'-blokken op de overzichtspagina
    titles = []
    lines = [l.strip() for l in _clean(body).split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if l == "Lees meer" and i >= 2:
            titles.append((lines[i - 2], lines[i - 1]))
    cards = []
    for title, desc in titles:
        if SKIP.search(title):
            continue
        try:
            pg.goto(OVERVIEW, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(3000)
            el = pg.get_by_text(title, exact=True).first
            box = el.locator("xpath=ancestor::*[.//text()[contains(.,'Lees meer')]][1]")
            box.get_by_text("Lees meer").first.click()
            pg.wait_for_timeout(3500)
            url = pg.url
            text = _clean(pg.inner_text("body"))
            imgs = pg.eval_on_selector_all("img", "els => els.map(e => [e.currentSrc||e.src, e.naturalWidth, e.naturalHeight])")
            imgs = [i for i in imgs if i[1] >= 600 and "open-over-gokken" not in i[0] and not i[0].endswith(".svg")]
        except Exception as e:
            print(f"   ! StarCasino '{title}': {str(e)[:80]}")
            continue
        bullets = _bullets(text) or [desc]
        low = (title + " " + desc + " " + text).lower()
        types = list(dict.fromkeys(t for pat, t in TYPE_RULES if re.search(pat, low)))
        recurring = re.search(r"elke (maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)", low)
        start, end = (None, None) if recurring else _dates(text)
        cards.append({
            "op": "starcasino", "title": title, "desc": desc, "bullets": bullets[:4], "types": types,
            "tag": "", "period": (start, end, recurring.group(0) if recurring else None),
            "detail_url": url, "image": imgs[0][0] if imgs else None,
            "hash": hashlib.md5(text.encode()).hexdigest(),
        })
    ctx.close()
    return cards


# ---------------------------------------------------------------- toernooien
TOURNAMENTS = BASE + "/tournaments"
MIN_PRIZE = 1000          # alleen toernooien met een prijzenpot van €1.000 of meer (afspraak gebruiker)

def _eur(s):
    return float(s.replace(".", "").replace(",", ".")) if s else None

def _dm(s, today):
    m = re.search(r"(\d{1,2})/(\d{1,2}),?\s*(\d{1,2}):(\d{2})", s or "")
    if not m:
        return None
    d = date(today.year, int(m.group(2)), int(m.group(1)))
    if (d - today).days < -180:
        d = d.replace(year=today.year + 1)
    return d

def fetch_tournaments(browser, today=None):
    """Lopende + aankomende toernooien via de info-knop van elke kaart (prijzenpot, inzet, start, einde)."""
    today = today or date.today()
    ctx = browser.new_context(locale="nl-NL", viewport={"width": 1500, "height": 1100}, user_agent=UA)
    pg = ctx.new_page()
    pg.goto(TOURNAMENTS, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(7000)
    L = pg.locator("img[src*='MultiplierTournamentImage']")
    seen, cards = set(), []
    for n in range(L.count()):
        img = L.nth(n)
        title = (img.get_attribute("alt") or "").strip()
        src = img.get_attribute("src") or ""
        try:
            img.locator("xpath=ancestor::*[3]").locator("svg").first.click(force=True)
            pg.wait_for_timeout(2500)
            dlg = pg.locator("[role=dialog]")
            txt = dlg.last.inner_text() if dlg.count() else ""
            pg.keyboard.press("Escape"); pg.wait_for_timeout(1500)
        except Exception as e:
            print(f"   ! toernooi '{title}': {str(e)[:80]}")
            continue
        if not txt.strip().startswith(title):
            continue      # geen (juiste) info-venster, bv. aankomend toernooi -> later opnieuw
        g = lambda lab: (re.search(lab + r"\s*\n\s*(.+)", txt) or [None, None])[1]
        prize = _eur((re.search(r"Prijzenpot\s*\n\s*€\s?([\d.,]+)", txt) or [None, None])[1])
        start, end = _dm(g("Start"), today), _dm(g("Einde"), today)
        ident = (title, str(start))
        if ident in seen or not prize:
            continue
        seen.add(ident)
        inzet, spellen, voorw, odds = g("Minimale inzet"), g("Deelnemende spellen"), g("Inzet voorwaarden"), g("Minimale odds")
        sport = bool(voorw or odds) or "sport" in title.lower()
        prize_txt = f"€{prize:,.0f}".replace(",", ".")
        bullets = [f"Prijzenpot: {prize_txt}"]
        inzet = inzet.replace("\xa0", " ") if inzet else inzet
        if inzet: bullets.append(f"Minimale inzet: {inzet.strip()}")
        if spellen: bullets.append(f"Deelnemende spellen: {spellen.strip()}")
        if voorw: bullets.append(f"Inzetvoorwaarden: {voorw.strip()}")
        if odds: bullets.append(f"Minimale odds: {odds.strip()}")
        big = re.sub(r"&w=\d+", "&w=1200", src) if src.startswith("http") else None
        cards.append({
            "op": "starcasino", "kind": "toernooi", "title": f"{prize_txt} {title}", "desc": f"Multiplier-toernooi met {prize_txt} aan prijzen",
            "bullets": bullets[:4], "types": ["tournamentBonus"] + (["sportBonus"] if sport else []), "tag": "",
            "prize": prize, "period": (start, end, None), "detail_url": TOURNAMENTS, "image": big,
            "key": f"starcasino-toernooi|{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}|{start}",
            "hash": hashlib.md5(txt.split("Ranglijst")[0].encode()).hexdigest(),
        })
    ctx.close()
    return [c for c in cards if c["prize"] >= MIN_PRIZE], [c for c in cards if c["prize"] < MIN_PRIZE]
