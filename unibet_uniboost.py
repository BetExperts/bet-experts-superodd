# -*- coding: utf-8 -*-
"""Unibet Uniboost-agent: de 'SUPERboost' van Unibet (niet dagelijks, vooral bij grote wedstrijden).

Bron: de sportpromotie-kaart op https://www.unibet.nl/promotions, bv.
  'Nations League SUPERboost!' / 'Nederland - Duitsland | Gakpo schiet op doel NU geboost naar 2.00 (was 1.45)'.
Werkt het vaste item /promoties/unibet-uniboost bij en stuurt bij een NIEUWE boost een Telegram-teaser.

  python3 unibet_uniboost.py --dry
  python3 unibet_uniboost.py --publish --post
"""
import re, sys, json, argparse
from datetime import datetime
import requests
from playwright.sync_api import sync_playwright
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE
import toto_api as API
from toto_lekkerman import NL, H, fmt, send_telegram, DISCLAIMER

URL = "https://www.unibet.nl/promotions"
PROMOTIES = "65e6fb5b08aed95b983b590f"
SLUG = "unibet-uniboost"
ITEM_ID = "6ab569a498befe31ca6d402d"
AFFILIATE = "https://b1.trickyrock.com/redirect.aspx?pid=86118747&bid=39312"
STATE = "state/unibet_uniboost.json"
KAMBI = "https://eu-offering-api.kambicdn.com/offering/v2018/ubnl/betoffer/outcome.json"

def kambi_odds(outcome_id):
    """Actuele normale odd van een Unibet-outcome (Kambi, brand ubnl) of None."""
    try:
        d = requests.get(KAMBI, params={"id": outcome_id, "lang": "nl_NL", "market": "NL"}, timeout=20).json()
        for bo in d.get("betOffers", []):
            for o in bo.get("outcomes", []):
                if str(o.get("id")) == str(outcome_id) and o.get("odds"):
                    return o["odds"] / 1000
    except Exception:
        pass
    return None

BOOST_RE = re.compile(r"^(?P<home>.+?)\s+-\s+(?P<away>.+?)\s*\|\s*(?P<sel>.+?)\s+NU geboost naar\s+(?P<new>\d+[.,]\d+)\s*\(was\s+(?P<old>\d+[.,]\d+)\)", re.I)

def crawl():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale="nl-NL", viewport={"width": 1400, "height": 1000}, user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"))
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(9000)
        text = pg.inner_text("body")
        b.close()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if not re.search(r"super ?boost", l, re.I):
            continue
        for nxt in lines[i + 1:i + 4]:
            m = BOOST_RE.search(nxt)
            if m:
                maxi = re.search(r"max\.?\s*inzet\s*€\s?(\d+)", " ".join(lines[i + 1:i + 5]), re.I)
                return {"title": l, "home": m["home"].strip(), "away": m["away"].strip(),
                        "event": f"{m['home'].strip()} – {m['away'].strip()}", "selection": m["sel"].strip(),
                        "old": float(m["old"].replace(",", ".")), "new": float(m["new"].replace(",", ".")),
                        "max": maxi.group(1) if maxi else None}
    return None

def build_fields(b):
    ev, sel, old, new, ko = b["event"], b["selection"], fmt(b["old"]), fmt(b["new"]), b.get("kickoff")
    datum = f" ({ko:%d-%m} om {ko:%H:%M})" if ko else ""
    maxi = f" Maximale inzet €{b['max']}." if b.get("max") else ""
    return {
        "name": f"Unibet Uniboost: {ev} @ {new} (was {old})",
        "subtitel": f"{ev}{datum} · {sel}, verhoogd van {old} naar {new}",
        "informatie": f"Unibet Uniboost: {ev}", "bonus-tekst": f"{old} → {new}", "bedrag-of-boost": f"Uniboost {old} → {new}",
        "check-1": f"Uniboost: {old} → {new}", "check-2": sel[:80],
        "check-3": f"Max. inzet €{b['max']}" if b.get("max") else "De Super Boost van Unibet",
        "odds-om-vrij-te-spelen": new, "boosted-odd": True, "beste-boosted-odd": True, "100x-promotie": False,
        "nederlands-elftal": "nederland" in ev.lower(),
        "wedstrijd-datum-tijd": f"{ko:%d-%m-%Y} om {ko:%H:%M}" if ko else "",
        "wanneer-toegevoegd": ko.replace(hour=23, minute=59).isoformat() if ko else None,
        "affiliatie-link-naar-broker": AFFILIATE,
        "promotie-rubriek": "6aaa9afdf92f60c1aeff6a58",          # SuperOdd -> kalender toont 'Uniboost'
        "bonus-types": "odds-boost,sport", "bonus-rubrieken": ["6aaa9afdf92f60c1aeff6a58", "6ab50fb0ddc77f0861db8e44"],
        "content-soort-promotie-1": (f"<h3><strong>Unibet Uniboost: {ev}</strong></h3><p>Met de <strong>Uniboost</strong> verhoogt Unibet af en toe "
            f"de quotering op een speciale weddenschap bij een grote wedstrijd. Bij <strong>{ev}</strong>{datum}: <strong>{sel}</strong>, "
            f"verhoogd van {old} naar <strong>{new}</strong>.{maxi}</p>"),
        "stap-2-tekst": f"De Uniboost van nu: {ev} — {sel}.",
        "stap-3-tekst": f"Zet in tegen de verhoogde quotering van {new}, vóór de aftrap.{maxi}",
        "voorwaarde-promotie": f"Unibet Uniboost bij {ev}: {sel}, verhoogd van {old} naar {new}.{maxi} Geldig tot de aftrap. Alleen voor spelers van 24 jaar of ouder. {DISCLAIMER}",
        "volledige-voorwaarden-tekst": f"Unibet Uniboost bij {ev}{datum}: {sel}, verhoogde quotering {new} (was {old}).{maxi} Geldig tot de aftrap; alleen voor spelers van 24+. Voorwaarden van Unibet zijn van toepassing.",
    }

def caption(b):
    return "\n".join(["🟢 <b>Unibet Uniboost LIVE!</b> 🚀", "", f"⚽ <b>{b['event']}</b>",
                      f"📈 Quotering geboost: <s>{fmt(b['old'])}</s> → <b>{fmt(b['new'])}</b>", "", f"<i>{DISCLAIMER}</i>"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--publish", action="store_true")
    ap.add_argument("--post", action="store_true"); ap.add_argument("--test", action="store_true")
    ap.add_argument("--coupon", help="Unibet-couponlink van de boost (coupon=combination|<outcomeId>|...): "
                                      "normale odd komt dan uit Kambi i.p.v. de (soms verouderde) promotekst")
    a = ap.parse_args()
    now = datetime.now(NL)
    print(f"== Unibet Uniboost — {now:%Y-%m-%d %H:%M} ==")
    try:
        b = crawl()
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)
    if not b:
        print("Geen Uniboost op de promotiepagina. Niets gedaan."); return
    try:
        k = API.kickoff_for([b["home"], b["away"]])
        b["kickoff"] = datetime.fromisoformat(k).astimezone(NL) if k else None
    except Exception:
        b["kickoff"] = None
    try:
        st0 = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st0 = {}
    key0 = f"{b['event']}|{b['selection']}"
    oid = None
    if a.coupon:
        m = re.search(r"combination(?:%7C|\|)(\d+)", a.coupon)
        oid = m.group(1) if m else None
    elif st0.get("outcome_id") and st0.get("outcome_key") == key0:
        oid = st0["outcome_id"]
    if oid:
        k_old = kambi_odds(oid)
        if k_old:
            print(f"  · normale odd uit Kambi (outcome {oid}): {fmt(k_old)} (promotekst zei {fmt(b['old'])})")
            b["old"] = k_old
        b["outcome_id"] = oid
    print(f"  {b['event']} | {b['selection']} | {fmt(b['old'])} -> {fmt(b['new'])} | max €{b.get('max')} | aftrap {b['kickoff']}")
    if b["kickoff"] and now >= b["kickoff"]:
        print("  · Wedstrijd is al begonnen — niets bijwerken/posten."); return
    fd = build_fields(b)
    if a.dry:
        print(f"  [dry] titel: {fd['name']}"); return
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    sig = f"{b['event']}|{b['selection']}|{b['old']}|{b['new']}"
    key = f"{b['event']}|{b['selection']}"
    if st.get("sig") != sig:
        r = requests.patch(f"{WF_API}/collections/{PROMOTIES}/items/{ITEM_ID}" + ("/live" if a.publish else ""),
                           headers=H(), json={"fieldData": fd}, timeout=60)
        r.raise_for_status()
        print(f"  ✔ CMS bijgewerkt: {fd['name']}")
    else:
        print("  · Zelfde Uniboost als vorige run — CMS ongewijzigd.")
    if a.post and key != st.get("posted_key"):
        if send_telegram(caption(b), PROMO_BASE + SLUG, test=a.test):
            print("  ✔ Telegram-teaser verstuurd."); st["posted_key"] = key
    st.update({"sig": sig, "event": b["event"], "updated": now.isoformat()})
    if b.get("outcome_id"):
        st.update({"outcome_id": b["outcome_id"], "outcome_key": key})
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("KLAAR.")

if __name__ == "__main__":
    main()
