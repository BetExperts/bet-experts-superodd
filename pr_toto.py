# -*- coding: utf-8 -*-
"""Directe bron voor de promo-radar: https://www.toto.nl/acties (veel TOTO-acties staan niet in de bonuskalender).

Leest de actiekaarten (button.promotion-block): categorie (SPORT/CASINO/WINNITT), titel, omschrijving en banner.
De volledige voorwaarden staan achter de login, dus de radar maakt de pagina op basis van de kaart;
bij twijfel over details liever een korte pagina dan verzonnen voorwaarden.
Levert 'kaarten' in hetzelfde formaat als pr_starcasino.fetch()."""
import re, hashlib

URL = "https://www.toto.nl/acties"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# Geen losse actie: welkomstbonussen (beheert de gebruiker), productfeatures, verzamelkaarten en
# acties met een eigen agent (Lekker Man, 50x).
SKIP = re.compile(r"^(nieuw bij|rondspeelvoorwaarden|live streaming|toto specials|betbuilder|lekker man|"
                  r"game show specials|toto toernooien)|50x je inle?g|welkomst", re.I)
SKIP_CATEGORIES = {"WINNITT"}       # ander merk (bingo), geen affiliatelink

TYPE_RULES = [
    (r"gratis weddenschap|free ?bet", "freeBetsBonus"), (r"gratis spins|free ?spins", "freeSpinsBonus"),
    (r"toernooi|prijzenpot|deel van €", "tournamentBonus"), (r"zet €\d+ in", "betAndGetBonus"),
    (r"blackjack|roulette|live|game show|ice fishing", "liveCasinoBonus"), (r"drops|cash drop", "cashDropBonus"),
    (r"jackpot", "jackpotBonus"), (r"\breis\b", "sportBonus"),
]

_JS = r"""() => [...document.querySelectorAll('button.promotion-block')].map(b => {
  const lines = (b.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
  const img = b.querySelector('img');
  return {lines, img: img ? (img.currentSrc || img.src) : null};
})"""

def fetch(browser):
    ctx = browser.new_context(locale="nl-NL", user_agent=UA, viewport={"width": 1400, "height": 1000})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(8000)
    for label in ("Weigeren", "Alleen noodzakelijke"):
        try:
            bt = pg.get_by_role("button", name=label)
            if bt.count():
                bt.first.click(timeout=2000); break
        except Exception:
            pass
    pg.mouse.wheel(0, 8000); pg.wait_for_timeout(2500)        # lazy images laden
    raw = pg.evaluate(_JS)
    ctx.close()
    cards, seen = [], set()
    for r in raw:
        lines = r["lines"]
        if len(lines) < 2:
            continue
        cat = lines[0].upper() if lines[0].isupper() else ""
        rest = lines[1:] if cat else lines
        rest = [l for l in rest if not re.match(r"(?i)^verloopt in\b|^\d+\s*[dum]\b", l)]   # aftelklokje is geen titel
        if not rest:
            continue
        title, desc = rest[0], " ".join(rest[1:])
        if not cat or cat in SKIP_CATEGORIES or SKIP.search(title) or title in seen:
            continue
        seen.add(title)
        low = (title + " " + desc).lower()
        types = list(dict.fromkeys(t for pat, t in TYPE_RULES if re.search(pat, low)))
        if cat == "SPORT" and "sportBonus" not in types:
            types.append("sportBonus")
        recurring = re.search(r"elke (maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag|week|dag)|toto maandag", low)
        bullets = [b for b in (desc,) if b] + ["Geen rondspeelvoorwaarden: wat je wint is direct van jou"]
        cards.append({
            "op": "toto", "category": cat, "title": title, "desc": desc, "bullets": bullets, "types": types, "tag": "",
            "period": (None, None, recurring.group(0) if recurring else None),
            "detail_url": URL, "image": r["img"],
            "key": f"toto-acties|{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}",
            "hash": hashlib.md5((title + "|" + desc).encode()).hexdigest(),
        })
    return cards
