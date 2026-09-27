# -*- coding: utf-8 -*-
"""JACKS.NL Superboost-agent: de (zeldzame) Superboost van JACKS.NL, vooral bij Oranje.

Bron: https://jacks.nl/sports#specials (Kambi, brand 'jvh'). Elke special is een kaart met wedstrijd,
selectie(s) en oude -> nieuwe odd. De Superboost is de kaart met de grote boost (bv. 2.35 -> 20.00);
na een klik staat in de wedcoupon het reward-label 'Superboost · Max. inzet €1.00 · Verloopt ...'.

- Nieuwe Superboost          -> vaste pagina /promoties/jacks-nl-superboost bijwerken + Telegram.
- Andere speler/selectie     -> pagina bijwerken + nieuwe Telegram (bv. als de speler niet start).
- Superboost verdwenen vóór de aftrap -> pagina melden als 'niet meer beschikbaar' (geldig tot = nu).

  python3 jacks_superboost.py --dry
  python3 jacks_superboost.py --publish --post
"""
import re, sys, json, argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from playwright.sync_api import sync_playwright
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE
from toto_lekkerman import fmt, send_telegram, DISCLAIMER

NL = ZoneInfo("Europe/Amsterdam")
URL = "https://jacks.nl/sports#specials"
KAMBI = "https://eu-offering-api.kambicdn.com/offering/v2018/jvh"
PROMOTIES = "65e6fb5b08aed95b983b590f"
SLUG = "jacks-nl-superboost"
BOOKMAKER = "64ff0fbd5a8f205b05d5465c"
AFFILIATE = "https://media.friendsofjacks.eu/redirect.aspx?pid=2527&bid=2257"
LOGO = ("https://cdn.prod.website-files.com/64f9f8e867f73b8e88841e09/65e725359304931c5d92e1bc_jacks.nl-logo-"
        "e1696321802604-218z18lvv1o46wzs6lsayoaxs28disg3dmap8j3nn61w.webp")
STATE = "state/jacks_superboost.json"
RUB_SUPERODD, RUB_SPORT = "6aaa9afdf92f60c1aeff6a58", "6ab50fb0ddc77f0861db8e44"
MIN_RATIO = 2.0          # 'gewone' specials zijn ~+20%; de Superboost is een veelvoud van de normale odd
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

_JS_CARDS = r"""() => {
  const out = [];
  for (const btn of document.querySelectorAll('.KambiBC-partnerSpecials-odds')) {
    const t = (btn.innerText || '').replace(/\s+/g, ' ').trim();
    const m = t.match(/^(\d+[.,]\d+)\s+(\d+[.,]\d+)$/);
    if (!m) continue;
    let card = btn;
    for (let i = 0; i < 8 && card.parentElement; i++) { card = card.parentElement; if (/Selectie/.test(card.innerText || '')) break; }
    const a = card.querySelector('a[href*="/event/"]');
    out.push({old: m[1], new: m[2], text: (card.innerText || '').split('\n').map(s => s.trim()).filter(Boolean),
              href: a ? a.getAttribute('href') : null});
  }
  return out;
}"""

def _f(s):
    return float(str(s).replace(",", ".")) if s else None

def crawl():
    """Superboost-kaart + reward-label uit de wedcoupon, of None."""
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(locale="nl-NL", timezone_id="Europe/Amsterdam", user_agent=UA, viewport={"width": 1400, "height": 1000})
        pg = ctx.new_page()
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(10000)
        try:
            pg.get_by_role("button", name="Weigeren").first.click(timeout=3000)
        except Exception:
            pass
        pg.wait_for_timeout(2000)
        cards = pg.evaluate(_JS_CARDS)
        best = None
        for i, c in enumerate(cards):
            old, new = _f(c["old"]), _f(c["new"])
            if old and new and new / old >= MIN_RATIO and (not best or new / old > best["new"] / best["old"]):
                best = {**c, "old": old, "new": new, "idx": i}
        if not best:
            b.close(); return None
        # klik -> wedcoupon: reward-label met max. inzet en verlooptijd
        reward = None
        try:
            pg.locator(".KambiBC-partnerSpecials-odds").nth(best["idx"]).click(timeout=5000)
            pg.wait_for_timeout(4000)
            for el in pg.query_selector_all(".KambiBC-react-reward-container__label"):
                t = (el.inner_text() or "").replace("\n", " ")
                if re.search(r"superboost", t, re.I):
                    reward = t; break
        except Exception as e:
            print(f"  ! wedcoupon niet gelezen: {e}")
        b.close()
    lines = best["text"]
    # ['Zijlijn Special', '1 Selecties', 'Servië - Nederland', 'Mexx Meerdink - Ja - Scoort', '2.35', '20.00']
    body = [l for l in lines if not re.fullmatch(r"\d+[.,]\d+", l) and not re.search(r"Selecties?$", l)]
    title, event, sels = body[0], body[1], body[2:]
    m = re.search(r"/event/(\d+)", best.get("href") or "")
    out = {"title": title, "event": event.replace(" - ", " – "), "selections": sels, "old": best["old"], "new": best["new"],
           "event_id": m.group(1) if m else None, "max": None, "expiry": None, "is_superboost": bool(reward)}
    if reward:
        mm = re.search(r"Max\.?\s*inzet\s*€\s*([\d.,]+)", reward, re.I)
        me = re.search(r"Verloopt\s+(.+)$", reward, re.I)
        out["max"] = mm.group(1).rstrip("0").rstrip(".").rstrip(",") if mm else None
        out["expiry"] = me.group(1).strip() if me else None
    if out["event_id"]:
        try:
            j = requests.get(f"{KAMBI}/betoffer/event/{out['event_id']}.json",
                             params={"lang": "nl_NL", "market": "NL", "client_id": "2", "channel_id": "1"}, timeout=20).json()
            st = (j.get("events") or [{}])[0].get("start")
            out["kickoff"] = datetime.fromisoformat(st.replace("Z", "+00:00")).astimezone(NL) if st else None
        except Exception:
            out["kickoff"] = None
    return out

def phrase(sel):
    """'Mexx Meerdink - Ja - Scoort' -> 'Mexx Meerdink scoort'."""
    parts = [s.strip() for s in sel.split(" - ")]
    if len(parts) == 3 and parts[1].lower() == "ja":
        return f"{parts[0]} {parts[2][0].lower() + parts[2][1:]}"
    if len(parts) == 3:
        return f"{parts[0]} ({parts[1].lower()}) – {parts[2]}"
    return sel

def build_fields(b):
    ev, old, new, ko = b["event"], fmt(b["old"]), fmt(b["new"]), b.get("kickoff")
    sel = " + ".join(phrase(s) for s in b["selections"])
    datum = f" ({ko:%d-%m} om {ko:%H:%M})" if ko else ""
    maxi = f" Maximale inzet €{b['max']}." if b.get("max") else ""
    return {
        "name": f"JACKS.NL Superboost: {sel} @ {new} (was {old})",
        "subtitel": f"{ev}{datum} · {sel}, verhoogd van {old} naar {new}" + (f" · max. inzet €{b['max']}" if b.get("max") else ""),
        "informatie": f"JACKS.NL Superboost: {ev}", "bonus-tekst": f"{old} → {new}",
        "bedrag-of-boost": f"Superboost {old} → {new}", "soort-welkomstbonus": "Superboost (verhoogde quotering)",
        "check-1": f"Superboost: {old} → {new}", "check-2": sel[:80],
        "check-3": f"Max. inzet €{b['max']}" if b.get("max") else "Tijdelijke boost van JACKS.NL",
        "button-1": "Bekijk de Superboost bij JACKS.NL",
        "odds-om-vrij-te-spelen": new, "boosted-odd": True, "beste-boosted-odd": True, "100x-promotie": False,
        "welkomstbonus-promotie": False, "casino-promotie": False, "nederlands-elftal": "nederland" in ev.lower(),
        "minimale-storting": "Geen", "rondspeelvoorwaarden": "Geen", "leeftijd": "24+",
        "wedstrijd-datum-tijd": f"{ko:%d-%m-%Y} om {ko:%H:%M}" if ko else "",
        "wanneer-toegevoegd": ko.replace(hour=23, minute=59, second=0, microsecond=0).isoformat() if ko else None,
        "affiliatie-link-naar-broker": AFFILIATE, "link-artikel-voor-sidebar": PROMO_BASE + SLUG,
        "bookmaker-3": BOOKMAKER, "bookmakers": [BOOKMAKER], "geldig-voor": "9c0fbc22d905260428d1de2988b86dea",
        "promotie-rubriek": RUB_SUPERODD, "bonus-types": "odds-boost,sport", "bonus-rubrieken": [RUB_SUPERODD, RUB_SPORT],
        "content-soort-promotie-1": (f"<h3><strong>JACKS.NL Superboost: {ev}</strong></h3><p>Heel af en toe – vooral bij wedstrijden "
            f"van Oranje – pakt JACKS.NL uit met een <strong>Superboost</strong>: een flink verhoogde quotering op één weddenschap. "
            f"Bij <strong>{ev}</strong>{datum}: <strong>{sel}</strong>, verhoogd van {old} naar <strong>{new}</strong>.{maxi}</p>"),
        "content-informatie-promotie-2": ("<h3><strong>Zo pak je de Superboost</strong></h3><ul><li>Log in bij JACKS.NL of maak een account aan (24+).</li>"
            "<li>Ga naar Sports → Specials; de Superboost staat bovenaan.</li>"
            f"<li>Zet in op {sel} tegen de verhoogde quotering van {new}.</li><li>Plaats je weddenschap vóór de aftrap.</li></ul>"),
        "content-voorwaarden-promotie-3": ("<h3><strong>Belangrijkste voorwaarden</strong></h3><ul><li>Alleen voor spelers van 24 jaar of ouder.</li>"
            + (f"<li>Maximale inzet €{b['max']}.</li>" if b.get("max") else "")
            + "<li>De Superboost geldt tot kort voor de aftrap en zolang JACKS.NL hem aanbiedt.</li>"
            + f"<li>De voorwaarden van JACKS.NL zijn leidend.</li></ul><p>{DISCLAIMER}</p>"),
        "stap-1-titel": "Open JACKS.NL", "stap-1-tekst": "Log in bij JACKS.NL of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Superboost", "stap-2-tekst": f"Ga naar Sports → Specials: {ev} — {sel}.",
        "stap-3-titel": "Plaats je weddenschap", "stap-3-tekst": f"Zet in tegen de verhoogde quotering van {new}, vóór de aftrap.{maxi}",
        "waar-op-letten-tekst": "De Superboost is kort geldig en kan wijzigen, bijvoorbeeld als een speler niet in de basis staat. Controleer de actuele boost bij JACKS.NL.",
        "voorwaarde-promotie": f"JACKS.NL Superboost bij {ev}: {sel}, verhoogd van {old} naar {new}.{maxi} Geldig tot kort voor de aftrap. Alleen voor spelers van 24 jaar of ouder. {DISCLAIMER}",
        "volledige-voorwaarden-tekst": f"JACKS.NL Superboost bij {ev}{datum}: {sel}, verhoogde quotering {new} (was {old}).{maxi} Geldig zolang JACKS.NL hem aanbiedt; alleen voor spelers van 24+. Voorwaarden van JACKS.NL zijn van toepassing.",
    }

def caption(b):
    return "\n".join(["🃏 <b>JACKS.NL Superboost LIVE!</b> 🚀", "", f"⚽ <b>{b['event']}</b>",
                      f"📈 Quotering geboost: <s>{fmt(b['old'])}</s> → <b>{fmt(b['new'])}</b>", "", f"<i>{DISCLAIMER}</i>"])

def H():
    return {"Authorization": f"Bearer {WEBFLOW_TOKEN}", "accept": "application/json", "content-type": "application/json"}

def wf(method, path, body=None):
    r = requests.request(method, WF_API + path, headers=H(), json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text.strip() else {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--publish", action="store_true")
    ap.add_argument("--post", action="store_true"); ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    now = datetime.now(NL)
    print(f"== JACKS.NL Superboost — {now:%Y-%m-%d %H:%M} ==")
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    try:
        b = crawl()
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)
    if not b or not b["is_superboost"]:
        print("  Geen Superboost op de specials-pagina.")
        # Verdwenen terwijl de vorige nog niet voorbij was (bv. speler start niet) -> pagina eerlijk maken
        ko = datetime.fromisoformat(st["kickoff"]) if st.get("kickoff") else None
        if st.get("item_id") and st.get("status") == "live" and ko and now < ko - timedelta(minutes=5) and not a.dry:
            wf("PATCH", f"/collections/{PROMOTIES}/items/{st['item_id']}" + ("/live" if a.publish else ""),
               {"fieldData": {"subtitel": f"{st.get('event')} · Deze Superboost is niet meer beschikbaar bij JACKS.NL",
                              "wanneer-toegevoegd": now.isoformat()}})
            st["status"] = "verdwenen"; json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("  ! Vorige Superboost is vóór de aftrap verdwenen — pagina bijgewerkt.")
        return
    print(f"  {b['event']} | {b['selections']} | {fmt(b['old'])} -> {fmt(b['new'])} | max €{b['max']} | verloopt {b['expiry']} | aftrap {b.get('kickoff')}")
    fd = build_fields(b)
    if a.dry:
        print(f"  [dry] {fd['name']}"); return
    sig = f"{b['event']}|{'|'.join(b['selections'])}|{b['old']}|{b['new']}|{b['max']}"
    key = f"{b['event']}|{'|'.join(b['selections'])}"
    if not st.get("item_id"):
        j = wf("POST", f"/collections/{PROMOTIES}/items" + ("/live" if a.publish else ""),
               {"isDraft": not a.publish, "isArchived": False, "fieldData": {**fd, "slug": SLUG, "afbeelding-promotie": {"url": LOGO}}})
        st["item_id"] = j["id"]; print(f"  ✔ aangemaakt: {PROMO_BASE}{j['fieldData']['slug']}")
    elif st.get("sig") != sig or st.get("status") != "live":
        wf("PATCH", f"/collections/{PROMOTIES}/items/{st['item_id']}" + ("/live" if a.publish else ""), {"isDraft": False, "fieldData": fd})
        print(f"  ✔ CMS bijgewerkt: {fd['name']}")
    else:
        print("  · Zelfde Superboost — CMS ongewijzigd.")
    if a.post and key != st.get("posted_key"):
        if send_telegram(caption(b), PROMO_BASE + SLUG, test=a.test):
            print("  ✔ Telegram verstuurd."); st["posted_key"] = key
    st.update({"sig": sig, "status": "live", "event": b["event"], "updated": now.isoformat(),
               "kickoff": b["kickoff"].isoformat() if b.get("kickoff") else None})
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("KLAAR.")

if __name__ == "__main__":
    main()
