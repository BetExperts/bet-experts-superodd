# -*- coding: utf-8 -*-
"""Starcasino Gouden Boost-agent: leest de dagelijkse Gouden Boost uit het publieke Altenar-feed van
Starcasino (zelfde data als het 'Boosted odds'-blok op starcasino.nl/prematch-bets) en houdt één evergreen
CMS-item (Promoties) bij: /promoties/starcasino-gouden-boost.

Labels in het feed (Altenar-vertalingen): betOfTheDay = 'Fun Boost', isLimitedTime = 'Gouden Boost',
tipsterId = eigen label (bv. 'CRAZY ODDS'), anders 'BOOSTED ODDS'. De banner op de site kan een
verouderde odd tonen; het feed is leidend.

  python3 sc_goudenboost.py --dry        # alleen tonen
  python3 sc_goudenboost.py --publish    # CMS-item live bijwerken (of aanmaken)
  python3 sc_goudenboost.py --publish --post   # + Telegram-teaser bij een NIEUWE boost
"""
import os, re, sys, json, argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from so_config import (WEBFLOW_TOKEN, WF_API, PROMOTIES_COLLECTION, PROMO_BASE,
                       TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL)

NL = ZoneInfo("Europe/Amsterdam")
FEED = ("https://sb2frontend-altenar2.biahosted.com/api/BetCards/GetBetCards?culture=nl-NL&timezoneOffset=-120"
        "&integration=starcasino.nl&deviceType=1&numFormat=en-GB&countryCode=NL&betCardListId=263&sportId=0")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

SLUG = "starcasino-gouden-boost"
BOOKMAKER_ID = "6a7afdaa4a7453c17d31cab5"                     # Starcasino in de Bookmakers-collectie
AFFILIATE = "https://media1.affiliates.starcasino.nl/redirect.aspx?pid=2170&bid=1478"
RUBRIEK_SUPERODD = "6aaa9afdf92f60c1aeff6a58"                  # zelfde rubrieken als de Lucky's Boost
RUBRIEK_SPORT = "6ab50fb0ddc77f0861db8e44"
GELDIG_SPORT = "9c0fbc22d905260428d1de2988b86dea"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "starcasino_goudenboost.json")
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."


def _fmt(o):
    return "%.2f" % o


def fetch():
    """Alle boosts uit het feed, met label, wedstrijd, markt, selectie en odds."""
    d = requests.get(FEED, headers={"User-Agent": UA, "Origin": "https://starcasino.nl",
                                    "Referer": "https://starcasino.nl/"}, timeout=30).json()
    mk = {m["id"]: m for m in d.get("markets", [])}
    od = {o["id"]: o for o in d.get("odds", [])}
    ev = {e["id"]: e for e in d.get("events", [])}
    tip = {t["id"]: t["name"] for t in d.get("tipsters", [])}
    out = []
    for c in d.get("betCards", []):
        bi = c.get("boostInfo") or {}
        if c.get("isBB") or len(c.get("odds", [])) != 1 or not bi.get("price"):
            continue
        e = ev.get(c["eventIds"][0]) or {}
        m = mk.get(c["odds"][0]["marketId"]) or {}
        o = od.get(c["odds"][0]["selectionId"]) or {}
        label = (tip.get(c.get("tipsterId")) or ("Fun Boost" if bi.get("isBetOfTheDay") else
                 "Gouden Boost" if bi.get("isLimitedTime") else "Boosted odds"))
        out.append({"label": label, "event": (e.get("name") or "").replace(" vs. ", " - "),
                    "kickoff": e.get("startDate"), "end": bi.get("endDate"),
                    "market": re.sub(r"\s*\(\s*\)", "", m.get("name") or "").strip(),
                    "selection": re.sub(r"\s+", " ", o.get("name") or "").strip(),
                    "old_odd": c.get("price"), "new_odd": bi.get("price")})
    return out


def phrase(b):
    """'Assist - Ruben van Bommel' + 'Meer dan 0,5' -> 'Ruben van Bommel geeft een assist'."""
    m, s = b["market"], b["selection"]
    r = re.match(r"Assist - (.+?)(?:\s*\([^)]*\))?$", m)
    if r and s.lower().startswith("meer dan 0"):
        return f"{r.group(1)} geeft een assist"
    r = re.match(r"Speler scoort & 1x2 \((.+)\)$", m)
    if r:
        return f"{r.group(1)} scoort en {s} wint" if s.lower() != "gelijkspel" else f"{r.group(1)} scoort en het wordt gelijk"
    r = re.match(r"(?:Speler scoort|Doelpuntenmaker)(?: - | \()(.+?)\)?$", m)
    if r:
        return f"{r.group(1)} scoort"
    return f"{m}: {s}" if m else s


def geldig_tot(iso):
    ko = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(NL)
    return ko.replace(hour=23, minute=59, second=0, microsecond=0).isoformat()


def fielddata(b):
    old, new, ev, ph = _fmt(b["old_odd"]), _fmt(b["new_odd"]), b["event"], phrase(b)
    ko = datetime.fromisoformat(b["kickoff"].replace("Z", "+00:00")).astimezone(NL)
    dag = f"{ko:%d-%m} om {ko:%H:%M} uur"
    body = ("<h3><strong>De Starcasino Gouden Boost van vandaag</strong></h3>"
            f"<p>Met de Gouden Boost verhoogt Starcasino de quotering op <strong>{ph}</strong> bij {ev} "
            f"({dag}) van {old} naar <strong>{new}</strong>. De boost is beperkt geldig en verloopt bij de aftrap.</p>"
            "<h3><strong>Wat is de Gouden Boost?</strong></h3>"
            "<p>De Gouden Boost is de verhoogde quotering van Starcasino die maar kort beschikbaar is. Je vindt hem "
            "bovenaan de sportpagina en in het blok 'Boosted odds', naast de Fun Boost en de andere boosts van de dag. "
            "De boost wisselt regelmatig: op deze pagina staat altijd de actuele Gouden Boost.</p>")
    voorwaarde = (f"Starcasino Gouden Boost: de quotering op {ph} bij {ev} is verhoogd van {old} naar {new}. "
                  "De boost is beperkt geldig (tot de aftrap) en kan op elk moment wijzigen; controleer de actuele "
                  "boost op starcasino.nl. Alleen voor spelers van 24 jaar of ouder. " + DISCLAIMER)
    return {
        "name": f"Starcasino Gouden Boost: {ph} @ {new}",
        "slug": SLUG,
        "subtitel": f"{ev} · verhoogd van {old} naar {new}",
        "informatie": f"Starcasino Gouden Boost: {ev}",
        "bonus-tekst": f"{old} → {new}",
        "bedrag-of-boost": f"Gouden Boost {old} → {new}",
        "soort-welkomstbonus": "Gouden Boost (verhoogde quotering)",
        "minimale-storting": "Geen",
        "odds-om-vrij-te-spelen": new,
        "rondspeelvoorwaarden": "Geen",
        "leeftijd": "24 jaar of ouder",
        "check-1": f"Gouden Boost: {old} → {new}",
        "check-2": ph,
        "check-3": f"{ev}, {dag}",
        "button-1": "Bekijk de Gouden Boost bij Starcasino",
        "affiliatie-link-naar-broker": AFFILIATE,
        "voorwaarde-promotie": voorwaarde,
        "content-informatie-promotie-2": body,
        "boosted-odd": True,
        "bonus-types": "odds-boost,sport",
        "bonus-rubrieken": [RUBRIEK_SUPERODD, RUBRIEK_SPORT],
        "promotie-rubriek": RUBRIEK_SUPERODD,
        "geldig-voor": GELDIG_SPORT,
        "bookmaker-3": BOOKMAKER_ID,
        "bookmakers": [BOOKMAKER_ID],
        "stap-1-titel": "Open Starcasino",
        "stap-1-tekst": "Ga naar Starcasino en log in of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Gouden Boost",
        "stap-2-tekst": f"De Gouden Boost staat bovenaan de sportpagina: {ev} — {ph}, quotering {new}.",
        "stap-3-titel": "Plaats je weddenschap",
        "stap-3-tekst": "Voeg de boost toe aan je bonnetje en bevestig je inzet voordat de wedstrijd begint.",
        "wanneer-toegevoegd": geldig_tot(b["kickoff"]),
    }


def telegram(b, url):
    """Zelfde opbouw als de Bet365/Oranje Palace-posts: wedstrijd + boost, niet de selectie zelf."""
    tekst = "\n".join(["⭐ <b>Starcasino Gouden Boost LIVE!</b> 🏆", "", f"⚽ <b>{b['event'].replace(' - ', ' – ')}</b>",
                       f"📈 Quotering geboost: <s>{_fmt(b['old_odd'])}</s> → <b>{_fmt(b['new_odd'])}</b>", "",
                       f"<i>{DISCLAIMER}</i>"])
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", timeout=30, data={
        "chat_id": TELEGRAM_CHANNEL, "text": tekst, "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Bekijk de Boost →", "url": url}]]})})
    r.raise_for_status()


def _wf(method, path, body=None):
    r = requests.request(method, f"{WF_API}/collections/{PROMOTIES_COLLECTION}/items{path}",
                         headers={"Authorization": "Bearer " + WEBFLOW_TOKEN, "content-type": "application/json"},
                         json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--post", action="store_true", help="Telegram bij een nieuwe boost (andere wedstrijd/selectie)")
    a = ap.parse_args()
    now = datetime.now(NL)
    print(f"== Starcasino Gouden Boost — {now:%Y-%m-%d %H:%M} ==")
    boosts = fetch()
    nu = datetime.now(timezone.utc)
    gb = [b for b in boosts if b["label"] == "Gouden Boost" and b["kickoff"]
          and datetime.fromisoformat(b["kickoff"].replace("Z", "+00:00")) > nu]
    if not gb:
        print(f"Geen actieve Gouden Boost in het feed ({len(boosts)} boosts). Niets gedaan."); return
    b = min(gb, key=lambda x: x["kickoff"])
    fd = fielddata(b)
    print(f"  {b['event']} | {b['market']} — {b['selection']} | {b['old_odd']} -> {b['new_odd']}\n  Titel: {fd['name']}")
    if a.dry:
        return
    try:
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        state = {}
    sig = "|".join(str(b[k]) for k in ("event", "market", "selection", "old_odd", "new_odd"))
    boost_key = f"{b['event']}|{phrase(b)}"          # niet de ruwe markt: Starcasino wisselt '(PSV)' / '()'
    if state.get("sig") == sig and state.get("item_id"):
        print("  · Zelfde boost als vorige run — CMS ongewijzigd.")
        _post(a, b, state, boost_key); return
    if state.get("item_id"):
        _wf("PATCH", f"/{state['item_id']}/live", {"isDraft": False, "isArchived": False, "fieldData": fd})
        iid = state["item_id"]
    else:
        iid = _wf("POST", "/live", {"isDraft": False, "isArchived": False, "fieldData": fd})["id"]
    state.update({"item_id": iid, "slug": SLUG, "sig": sig, "title": fd["name"], "event": b["event"],
                  "old_odd": b["old_odd"], "new_odd": b["new_odd"], "url": PROMO_BASE + SLUG,
                  "updated": now.isoformat()})
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  ✔ CMS live bijgewerkt: {PROMO_BASE}{SLUG}")
    _post(a, b, state, boost_key)


def _post(a, b, state, boost_key):
    """Telegram alleen bij een nieuwe boost; schommelende odds passen alleen stil de pagina aan."""
    if not a.post or state.get("posted_key") == boost_key:
        return
    telegram(b, PROMO_BASE + SLUG)
    state["posted_key"] = boost_key
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  ✔ Telegram-teaser verstuurd.")


if __name__ == "__main__":
    main()
