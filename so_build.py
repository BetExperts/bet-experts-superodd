# -*- coding: utf-8 -*-
"""Bouwt de Webflow-velddata voor een Super-Odd-promotieartikel."""
import re, unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from so_config import (RUBRIEK_SUPERODD, BET365_BOOKMAKER, BET365_AFFILIATE,
                       GELDIG_VOOR_SPORT, DISCLAIMER)

NL = ZoneInfo("Europe/Amsterdam")
_MND = ["januari","februari","maart","april","mei","juni","juli","augustus",
        "september","oktober","november","december"]

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-+", "-", s)

def nl_datum(dt):
    return f"{dt.day} {_MND[dt.month-1]} {dt.year}"

def _match_nl(match):
    """'Sunderland v AZ' -> 'Sunderland - AZ' (leesbaarder in NL)."""
    return re.sub(r"\s+v\s+", " - ", match)

def _selecties_html(selections):
    if not selections:
        return ""
    return "<ul>" + "".join(f"<li>{s}</li>" for s in selections) + "</ul>"

def _selecties_zin(selections):
    if not selections:
        return "de geselecteerde markt"
    if len(selections) == 1:
        return selections[0]
    return ", ".join(selections[:-1]) + " én " + selections[-1]

def build_fielddata(data, slug=None, now=None):
    """data = output van so_crawl.crawl_super_boost(); return (fd, slug, title)."""
    now = now or datetime.now(NL)
    match = _match_nl(data["match"])
    old_o, new_o = data["old_odd"], data["new_odd"]
    payout = data.get("payout") or ""
    sels = data.get("selections") or []
    datum = nl_datum(now)

    sel_zin = _selecties_zin(sels)   # "A én B"

    title = f"Bet365 Super Odd Vandaag: {match} @ {new_o} (was {old_o})"
    subtitel = f"{match}: {sel_zin} — geboost van {old_o} naar {new_o}."
    bonus_tekst = f"{old_o} → {new_o}"

    if not slug:
        slug = "bet365-super-odd"   # evergreen; wordt dagelijks/uurlijks bijgewerkt

    sel_html = _selecties_html(sels)

    content1 = (f"<p><strong>Bet365 Super Odd van vandaag ({datum}):</strong> "
                f"Bet365 boost bij <strong>{match}</strong> de weddenschap "
                f"<strong>{sel_zin}</strong> — de quotering gaat omhoog van "
                f"<strong>{old_o}</strong> naar <strong>{new_o}</strong>."
                + (f" {payout}." if payout else "") + "</p>")

    content2 = (f"<p><strong>Wat wordt er geboost?</strong> De Super Boost van vandaag "
                f"gaat over <strong>{match}</strong>. Deze weddenschap is verhoogd van "
                f"{old_o} naar een gebooste <strong>Super Odd van {new_o}</strong>:</p>"
                f"{sel_html}"
                + (f"<p>{payout}.</p>" if payout else ""))

    content3 = ("<ul>"
                f"<li>Markt: {sel_zin}</li>"
                f"<li>Quotering: {old_o} → <strong>{new_o}</strong> (Super Odd)</li>"
                + (f"<li>{payout}</li>" if payout else "")
                + "<li>Beschikbaar bij Bet365, zolang de boost geldig is (meestal 1 dag)</li>"
                "<li>Bedragen en beschikbaarheid kunnen wijzigen — check altijd Bet365 vóór inzet</li>"
                "</ul>"
                f"<p>{DISCLAIMER}</p>")

    voorwaarde = (f"Super Boost van {datum}. Bet365 verhoogt de quotering op {match} "
                  f"van {old_o} naar {new_o}. Super Boosts zijn tijdelijk (meestal één dag) "
                  f"en zolang de voorraad strekt. Bedragen, markten en beschikbaarheid kunnen "
                  f"wijzigen; controleer de actuele Super Boost altijd op bet365.nl vóór je inzet. "
                  f"Alleen voor spelers van 24 jaar of ouder. {DISCLAIMER}")

    informatie = (f"De Bet365 Super Odd van {datum} gaat over {match}: de quotering is "
                  f"verhoogd van {old_o} naar {new_o}. {payout + '. ' if payout else ''}"
                  f"Super Boosts wisselen dagelijks en zijn maar kort geldig.")

    fd = {
        "name": title,
        "slug": slug,
        "subtitel": subtitel,
        "bonus-tekst": bonus_tekst,
        "voorwaarde-promotie": voorwaarde,
        "informatie": informatie,
        "content-soort-promotie-1": content1,
        "content-informatie-promotie-2": content2,
        "content-voorwaarden-promotie-3": content3,
        "check-1": f"Super Odd: {old_o} → {new_o}",
        "check-2": (sels[0] if sels else "Dagelijkse Super Boost"),
        "check-3": (payout or "Wisselt elke dag"),
        "button-1": "Bekijk de Super Odd bij Bet365",
        "bedrag-of-boost": f"Super Odd {old_o} → {new_o}",
        "odds-om-vrij-te-spelen": new_o,
        "soort-welkomstbonus": "Super Boost (verhoogde quotering)",
        "minimale-storting": "n.v.t. (odds-boost)",
        "rondspeelvoorwaarden": "Geen",
        "leeftijd": "24 jaar of ouder",
        "stap-1-titel": "Open Bet365",
        "stap-1-tekst": "Ga naar Bet365 en log in of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Super Boost",
        "stap-2-tekst": f"De Super Boost van vandaag staat op {match} — quotering {new_o}.",
        "stap-3-titel": "Plaats je weddenschap",
        "stap-3-tekst": "Voeg de Super Boost toe aan je bonnetje en bevestig je inzet zolang de boost geldig is.",
        "waar-op-letten-tekst": ("Super Boosts zijn tijdelijk (meestal één dag) en kunnen elk moment "
                                 "wijzigen of verlopen. Controleer de actuele quotering altijd op bet365.nl "
                                 f"vóór je inzet. {DISCLAIMER}"),
        "volledige-voorwaarden-tekst": voorwaarde,
        "affiliatie-link-naar-broker": BET365_AFFILIATE,
        "promotie-rubriek": RUBRIEK_SUPERODD,
        "bookmaker-3": BET365_BOOKMAKER,
        "bookmakers": [BET365_BOOKMAKER],
        "geldig-voor": GELDIG_VOOR_SPORT,
        "boosted-odd": True,
    }
    return fd, slug, title

def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def signature(data):
    """Handtekening van de huidige Super Boost — verandert bij een andere
    wedstrijd, odd of selectie, zodat we alleen dan het artikel bijwerken."""
    sels = "/".join(data.get("selections") or [])
    return f"{data['match']}|{data['old_odd']}|{data['new_odd']}|{sels}"
