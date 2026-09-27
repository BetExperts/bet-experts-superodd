# -*- coding: utf-8 -*-
"""BetMGM Odds Boost: vaste pagina /promoties/betmgm-odds-boost, HANDMATIG bijgewerkt.

BetMGM doet dit maar af en toe en heeft geen landingspagina om te scrapen, dus de gebruiker
geeft de boost door (screenshot) en we zetten hem hiermee op de site:

  python3 betmgm_boost.py --home "Servië" --away "Nederland" --selectie "Nederland leidt bij rust" \
      --markt "Rust" --oud 1.79 --nieuw 3.00 --aftrap "2026-09-27 18:00" [--max 10] [--post] [--dry]

Het item wordt de eerste keer aangemaakt (slug betmgm-odds-boost) en daarna steeds bijgewerkt.
"""
import sys, json, argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE
from toto_lekkerman import fmt, send_telegram, DISCLAIMER

NL = ZoneInfo("Europe/Amsterdam")
PROMOTIES = "65e6fb5b08aed95b983b590f"
SLUG = "betmgm-odds-boost"
BOOKMAKER = "66bb685ec057aa8c4337ceea"
AFFILIATE = "https://casino.betmgm.nl/redirect.aspx?pid=3781431&lpid=3329&bid=20762"
LOGO_FROM = "betmgm-sport-welkomstbonus-ontvang-2-profit-boosts-exclusieve-seizoenkaart"
STATE = "state/betmgm_boost.json"
RUB_SUPERODD, RUB_SPORT = "6aaa9afdf92f60c1aeff6a58", "6ab50fb0ddc77f0861db8e44"

def H():
    return {"Authorization": f"Bearer {WEBFLOW_TOKEN}", "accept": "application/json", "content-type": "application/json"}

def wf(method, path, body=None):
    r = requests.request(method, WF_API + path, headers=H(), json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text.strip() else {}

def find_item(slug):
    off = 0
    while True:
        items = wf("GET", f"/collections/{PROMOTIES}/items?limit=100&offset={off}").get("items", [])
        for it in items:
            if it["fieldData"].get("slug") == slug:
                return it
        if len(items) < 100:
            return None
        off += 100

def build_fields(b):
    ev, sel, old, new, ko = b["event"], b["selectie"], fmt(b["oud"]), fmt(b["nieuw"]), b["aftrap"]
    markt = f" ({b['markt']})" if b.get("markt") else ""
    datum = f" ({ko:%d-%m} om {ko:%H:%M})"
    maxi = f" Maximale inzet €{b['max']}." if b.get("max") else ""
    return {
        "name": f"BetMGM Odds Boost: {ev} @ {new} (was {old})",
        "subtitel": f"{ev}{datum} · {sel}, verhoogd van {old} naar {new}",
        "informatie": f"BetMGM Odds Boost: {ev}", "bonus-tekst": f"{old} → {new}",
        "bedrag-of-boost": f"Odds Boost {old} → {new}", "soort-welkomstbonus": "Odds Boost (verhoogde quotering)",
        "check-1": f"Odds Boost: {old} → {new}", "check-2": f"{sel}{markt}"[:80],
        "check-3": f"Max. inzet €{b['max']}" if b.get("max") else "Tijdelijke boost van BetMGM",
        "button-1": "Bekijk de Odds Boost bij BetMGM",
        "odds-om-vrij-te-spelen": new, "boosted-odd": True, "beste-boosted-odd": True, "100x-promotie": False,
        "welkomstbonus-promotie": False, "casino-promotie": False,
        "nederlands-elftal": "nederland" in ev.lower(),
        "minimale-storting": "Geen", "rondspeelvoorwaarden": "Geen", "leeftijd": "24+",
        "wedstrijd-datum-tijd": f"{ko:%d-%m-%Y} om {ko:%H:%M}",
        "wanneer-toegevoegd": ko.replace(hour=23, minute=59, second=0).isoformat(),
        "affiliatie-link-naar-broker": AFFILIATE, "link-artikel-voor-sidebar": PROMO_BASE + SLUG,
        "bookmaker-3": BOOKMAKER, "bookmakers": [BOOKMAKER],
        "geldig-voor": "9c0fbc22d905260428d1de2988b86dea",
        "promotie-rubriek": RUB_SUPERODD, "bonus-types": "odds-boost,sport", "bonus-rubrieken": [RUB_SUPERODD, RUB_SPORT],
        "content-soort-promotie-1": (f"<h3><strong>BetMGM Odds Boost: {ev}</strong></h3><p>Af en toe verhoogt BetMGM met een "
            f"<strong>Odds Boost</strong> de quotering op een weddenschap bij een grote wedstrijd. Bij <strong>{ev}</strong>{datum}: "
            f"<strong>{sel}</strong>{markt}, verhoogd van {old} naar <strong>{new}</strong>.{maxi}</p>"),
        "content-informatie-promotie-2": ("<h3><strong>Zo pak je de Odds Boost</strong></h3><ul><li>Log in bij BetMGM of maak een account aan (24+).</li>"
            f"<li>Ga naar {ev} en zoek de markt met het label 'Odds Boost'.</li>"
            f"<li>Zet in op {sel} tegen de verhoogde quotering van {new}.</li><li>Plaats je weddenschap vóór de aftrap.</li></ul>"),
        "content-voorwaarden-promotie-3": ("<h3><strong>Belangrijkste voorwaarden</strong></h3><ul><li>Alleen voor spelers van 24 jaar of ouder.</li>"
            "<li>De boost geldt tot de aftrap en zolang BetMGM hem aanbiedt.</li>"
            + (f"<li>Maximale inzet €{b['max']}.</li>" if b.get("max") else "")
            + f"<li>De voorwaarden van BetMGM zijn leidend.</li></ul><p>{DISCLAIMER}</p>"),
        "stap-1-titel": "Open BetMGM", "stap-1-tekst": "Log in bij BetMGM of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Odds Boost", "stap-2-tekst": f"De Odds Boost van nu: {ev} — {sel}{markt}.",
        "stap-3-titel": "Plaats je weddenschap", "stap-3-tekst": f"Zet in tegen de verhoogde quotering van {new}, vóór de aftrap.{maxi}",
        "waar-op-letten-tekst": "De Odds Boost van BetMGM is kort geldig (tot de aftrap) en komt maar af en toe voorbij. Controleer de actuele quotering bij BetMGM.",
        "voorwaarde-promotie": f"BetMGM Odds Boost bij {ev}: {sel}{markt}, verhoogd van {old} naar {new}.{maxi} Geldig tot de aftrap. Alleen voor spelers van 24 jaar of ouder. {DISCLAIMER}",
        "volledige-voorwaarden-tekst": f"BetMGM Odds Boost bij {ev}{datum}: {sel}{markt}, verhoogde quotering {new} (was {old}).{maxi} Geldig tot de aftrap; alleen voor spelers van 24+. Voorwaarden van BetMGM zijn van toepassing.",
    }

def caption(b):
    return "\n".join(["🦁 <b>BetMGM Odds Boost LIVE!</b> 🚀", "", f"⚽ <b>{b['event']}</b>",
                      f"📈 Quotering geboost: <s>{fmt(b['oud'])}</s> → <b>{fmt(b['nieuw'])}</b>", "", f"<i>{DISCLAIMER}</i>"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True); ap.add_argument("--away", required=True)
    ap.add_argument("--selectie", required=True); ap.add_argument("--markt")
    ap.add_argument("--oud", type=float, required=True); ap.add_argument("--nieuw", type=float, required=True)
    ap.add_argument("--aftrap", required=True, help="YYYY-MM-DD HH:MM (NL-tijd)"); ap.add_argument("--max")
    ap.add_argument("--post", action="store_true"); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    b = {"event": f"{a.home} – {a.away}", "selectie": a.selectie, "markt": a.markt, "oud": a.oud, "nieuw": a.nieuw,
         "aftrap": datetime.strptime(a.aftrap, "%Y-%m-%d %H:%M").replace(tzinfo=NL), "max": a.max}
    fd = build_fields(b)
    print(f"== BetMGM Odds Boost: {fd['name']}")
    if a.dry:
        print(json.dumps({k: fd[k] for k in ('subtitel', 'check-2', 'wanneer-toegevoegd')}, ensure_ascii=False, indent=1)); return
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    item = find_item(SLUG) if not st.get("item_id") else {"id": st["item_id"]}
    if item:
        wf("PATCH", f"/collections/{PROMOTIES}/items/{item['id']}/live", {"isDraft": False, "fieldData": fd})
        print(f"  ✔ bijgewerkt: {PROMO_BASE}{SLUG}")
    else:
        logo = (find_item(LOGO_FROM) or {}).get("fieldData", {}).get("afbeelding-promotie")
        if logo:
            fd["afbeelding-promotie"] = {"url": logo["url"]}
        item = wf("POST", f"/collections/{PROMOTIES}/items/live", {"isDraft": False, "isArchived": False, "fieldData": {**fd, "slug": SLUG}})
        print(f"  ✔ aangemaakt: {PROMO_BASE}{item['fieldData']['slug']}")
    key = f"{b['event']}|{b['selectie']}"
    if a.post and key != st.get("posted_key"):
        if send_telegram(caption(b), PROMO_BASE + SLUG):
            print("  ✔ Telegram verstuurd."); st["posted_key"] = key
    st.update({"item_id": item["id"], "event": b["event"], "selectie": b["selectie"], "updated": datetime.now(NL).isoformat()})
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
