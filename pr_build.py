# -*- coding: utf-8 -*-
"""Bouwt een Promoties-item (eigen tekst in Bet-Experts-stijl) uit de feiten van een actie."""
import re, unicodedata
from datetime import datetime, time
from zoneinfo import ZoneInfo
from pr_config import TYPE_LABELS, SPORT_TYPES, RUBRIEK, GELDIG_SPORT, GELDIG_CASINO, DISCLAIMER

NL = ZoneInfo("Europe/Amsterdam")
MND = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
MAAND = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
         "oktober", "november", "december"]

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("€", "").replace("&", "en").replace("%", "-procent")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")

def clean_title(title, bm_name):
    """Haal de bookmakernaam uit de titel ('... bij JACKS.NL') en maak 'm compact."""
    t = title
    for n in sorted({bm_name, bm_name.replace(".NL", ".nl"), bm_name.split()[0], re.sub(r"\.nl$", "", bm_name, flags=re.I)}, key=len, reverse=True):
        t = re.sub(rf"\s*(bij|van|met de \w+ van)\s+{re.escape(n)}(\.nl)?(?![\w.])", "", t, flags=re.I)
        t = re.sub(rf"^{re.escape(n)}[:\s]+", "", t, flags=re.I)
    t = re.sub(r"€\s+(\d)", r"€\1", t).strip(" :-")
    return t[:1].upper() + t[1:]

def _num(s):
    return re.sub(r"€\s+(\d)", r"€\1", s)

def _dag(d):
    return f"{d.day} {MAAND[d.month - 1]}"

def period_text(start, end, recurring):
    if start and end:
        return f"van {_dag(start)} t/m {_dag(end)}"
    if end:
        return f"t/m {_dag(end)}"
    if recurring:
        return recurring
    return "doorlopend"

SPORT_RE = re.compile(r"\bfree ?bets?\b|\bodds\b|\bwedden\b|weddenschap|voetbal|league|eredivisie|grand prix|\bf1\b|\bkkd\b|\bsport", re.I)
CASINO_RE = re.compile(r"spins|slot|casino|jackpot|toernooi|roulette|blackjack|chips|drops|gokkast", re.I)

def classify(card):
    types = set(card["types"])
    s = " ".join([card["title"]] + card["bullets"])
    sport = bool(types & {"sportBonus", "freeBetsBonus"}) or bool(SPORT_RE.search(s))
    if CASINO_RE.search(s) and "sportBonus" not in types and not re.search(r"free ?bet", s, re.I):
        sport = False
    low = s.lower()
    if "welcomeBonus" in types:
        rub = "welkomstbonus"
    elif re.search(r"(?<![\d.])\d{2,3}x je in(zet|leg)\b", low):
        rub = "100x"
    elif "noDepositBonus" in types:
        rub = "no-deposit"
    elif "freeBetsBonus" in types or re.search(r"free ?bet", low):
        rub = "free-bets"
    elif "depositBonus" in types:
        rub = "stortingsbonus"
    elif not sport:
        rub = "casino"
    else:
        rub = "specials"
    return sport, rub

# Alleen echte odds-boosts: 50x/60x/100x je inzet, SuperBoost/Super Odd, Lucky's Boost e.d.
# (géén Profit Boost, acca boost of 'boost je odds' bij bet builders).
BOOST_RE = re.compile(r"(?<![\d.])\d{2,3}(?:[.,]00)?\s?x je in(?:zet|leg)|super ?(?:boost|odds?)|lucky'?s? ?boost|"
                      r"golden odds|oddboost|uniboost|zet\s?€\s?1 in (?:en|&) win\s?€\s?(?:50|60|100)\b", re.I)

def is_boosted(text):
    return bool(BOOST_RE.search(text or ""))

def extract(card):
    s = " · ".join(card["bullets"] + [card["title"]])
    dep = re.search(r"(?:minimale\s+storting|stort(?:ing)?(?:\s+minimaal)?)[^€\d]{0,20}€\s?(\d+(?:,\d+)?)", s, re.I)
    wag = re.search(r"(\d+)\s*x\s*(?:rondspelen|inzetvereiste|inzetverplichting)|(?:inzetvereiste|inzetverplichting|rondspeel\w*)\s*:?\s*(\d+)\s*x", s, re.I)
    no_wag = re.search(r"geen\s+(rondspeel|inzetvereiste|inzetverplichting)", s, re.I)
    amount = (re.search(r"(\d+)\s*(?:free spins|gratis spins)", s, re.I) or
              re.search(r"€\s?\d+(?:,\d+)?(?:\s*(?:aan free bets|free bet|bonus|cash))?", s, re.I))
    return {
        "deposit": f"€{dep.group(1)}" if dep else None,
        "wager": "Geen" if no_wag else (f"{wag.group(1) or wag.group(2)}x" if wag else None),
        "amount": _num(amount.group(0)) if amount else None,
    }

def build_fields(card, bm, period, verify, affiliate, logo):
    start, end, recurring = period
    sport, rub = classify(card)
    ex = extract(card)
    title = clean_title(card["title"], bm["name"])
    per = period_text(start, end, recurring)
    labels = [TYPE_LABELS.get(t, t) for t in card["types"]]
    labels.append("sport" if sport else "casino")
    bullets = [_num(b) for b in card["bullets"]][:4]
    lower = lambda b: b[:1].lower() + b[1:] if b and not b[:2].isupper() else b

    intro_period = (f"De actie loopt {per}." if start or end else
                    (f"Deze actie komt {recurring} terug." if recurring else "Deze actie is doorlopend geldig."))
    body1 = (f"<h3><strong>{bm['name']}: {title}</strong></h3>"
             f"<p>Bij {bm['name']} loopt op dit moment de actie <strong>{title}</strong>. "
             f"{intro_period} Hieronder lees je in het kort hoe het werkt en waar je op moet letten.</p>")
    body2 = ("<h3><strong>Zo werkt de actie</strong></h3><ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
             f"<p>Via de knop op deze pagina ga je direct naar de actie bij {bm['name']}. "
             f"Daar vind je ook de volledige en actuele actievoorwaarden.</p>")
    cond = [f"Alleen voor spelers van 24 jaar of ouder."]
    if start or end:
        cond.append(f"Looptijd: {per}.")
    if ex["deposit"]:
        cond.append(f"Minimale storting: {ex['deposit']}.")
    if ex["wager"]:
        cond.append("Geen rondspeelvoorwaarden." if ex["wager"] == "Geen" else f"Rondspeelvoorwaarden: {ex['wager']}.")
    cond.append(f"De actievoorwaarden van {bm['name']} zijn leidend; controleer ze altijd vóór je meedoet.")
    body3 = ("<h3><strong>Belangrijkste voorwaarden</strong></h3><ul>" + "".join(f"<li>{c}</li>" for c in cond) +
             f"</ul><p>{DISCLAIMER}</p>")

    sub = lower(bullets[0]) if bullets else title
    fd = {
        "name": f"{bm['name']}: {title}" + (f" ({per})" if start and end and (end - start).days <= 14 else ""),
        "slug": slugify(f"{bm['name']} {title}")[:80].strip("-"),
        "subtitel": sub[:1].upper() + sub[1:],
        "informatie": f"{bm['name']}: {title}",
        "bonus-tekst": (ex["amount"] or title.split(":")[0])[:28].upper(),
        "voorwaarde-promotie": " · ".join(bullets[:4] + ([per] if (start or end) else []) + ["24+"]),
        "bookmaker-3": bm["id"], "bookmakers": [bm["id"]],
        "promotie-rubriek": RUBRIEK[rub],
        "geldig-voor": GELDIG_SPORT if sport else GELDIG_CASINO,
        "check-1": bullets[0] if bullets else title,
        "check-2": bullets[1] if len(bullets) > 1 else per.capitalize(),
        "check-3": bullets[2] if len(bullets) > 2 else "24+ | Speel bewust",
        "button-1": "Bekijk de actie",
        "affiliatie-link-naar-broker": affiliate,
        "welkomstbonus-promotie": "welcomeBonus" in card["types"],
        "casino-promotie": not sport,
        "no-deposit-bonus": "noDepositBonus" in card["types"],
        "free-bets": "freeBetsBonus" in card["types"],
        "boosted-odd": is_boosted(card["title"] + " " + " ".join(card["bullets"])),
        "100x-promotie": rub == "100x",
        "minimale-storting": ex["deposit"] or "Zie voorwaarden",
        "rondspeelvoorwaarden": ex["wager"] or "Zie voorwaarden",
        "soort-welkomstbonus": ", ".join(l.replace("-", " ") for l in labels[:2]).capitalize(),
        "bedrag-of-boost": ex["amount"] or title[:40],
        "leeftijd": "24+",
        "bonus-types": ",".join(dict.fromkeys(labels)),
        "stap-1-titel": "Open je account", "stap-1-tekst": f"Log in bij {bm['name']} of maak een account aan (24+).",
        "stap-2-titel": "Doe mee met de actie",
        "stap-2-tekst": (bullets[0] if bullets else "Volg de stappen in de actievoorwaarden.").rstrip(".") + ".",
        "stap-3-titel": "Ontvang je beloning",
        "stap-3-tekst": (bullets[1] if len(bullets) > 1 else "Je beloning wordt volgens de voorwaarden bijgeschreven.").rstrip(".") + ".",
        "content-soort-promotie-1": body1,
        "content-informatie-promotie-2": body2,
        "content-voorwaarden-promotie-3": body3,
        "waar-op-letten-tekst": (f"Let op de looptijd ({per})" if (start or end) else "Controleer de actuele voorwaarden") +
                                 (f", de minimale storting van {ex['deposit']}" if ex["deposit"] else "") +
                                 (f" en de rondspeelvoorwaarden ({ex['wager']})" if ex["wager"] and ex["wager"] != "Geen" else "") +
                                 f". Alleen voor spelers van 24 jaar en ouder.",
        "volledige-voorwaarden-tekst": " ".join(cond) + " " + " · ".join(bullets),
    }
    if logo:
        fd["afbeelding-promotie"] = logo
    if start:
        fd["geldig-vanaf"] = datetime.combine(start, time(0, 0), NL).isoformat()
    if end:
        fd["wanneer-toegevoegd"] = datetime.combine(end, time(23, 59), NL).isoformat()
    return fd, sport, rub
