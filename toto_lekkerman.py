# -*- coding: utf-8 -*-
"""TOTO Lekker Man-agent: de odds-boost van TOTO (vergelijkbaar met de Bet365 Super Odd en de
Oranje Palace Lucky's Boost). Niet elke dag beschikbaar, vaak bij Oranje en grote wedstrijden.

Werkt het vaste promotie-item /promoties/toto-lekker-man bij en stuurt bij een NIEUWE Lekker Man
(andere wedstrijd/selectie) een Telegram-teaser. Geen Lekker Man op de site -> niets doen.

  python3 toto_lekkerman.py --dry
  python3 toto_lekkerman.py --publish --post
"""
import re, sys, json, argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from playwright.sync_api import sync_playwright
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT
import toto_api as API

NL = ZoneInfo("Europe/Amsterdam")
URL = "https://sport.toto.nl/wedden/729/lekker-man/wedstrijden"
PROMOTIES = "65e6fb5b08aed95b983b590f"
SLUG = "toto-lekker-man"
TOTO_BM = "669ab9f5aceb8b717cea24c3"
AFFILIATE = "https://partner.toto.nl/C.ashx?btag=a_375b_474c_&affid=184&siteid=375&adid=474&c="
LOGO = "https://cdn.prod.website-files.com/64f9f8e867f73b8e88841e09/66ec2585dcd5bb973c21cbab_toto-nederland-rond.webp"
RUB_SPECIALS = "65eb24f2e8d4c04e87892eab"
RUB_SUPERODD = "6aaa9afdf92f60c1aeff6a58"   # rubriek SuperOdd: de kalender toont dan de eigen boost-naam
GELDIG_SPORT = "9c0fbc22d905260428d1de2988b86dea"
STATE = "state/toto_lekkerman.json"
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."
DAGEN = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}
MND = {m: i + 1 for i, m in enumerate(["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"])}

def H():
    return {"Authorization": f"Bearer {WEBFLOW_TOKEN}", "accept": "application/json", "content-type": "application/json"}

def _when(txt, now):
    """'Vandaag 20:45' / 'Morgen 18:30' / 'za 27 sep 18:30' -> datetime (NL) of None."""
    t = txt.strip().lower()
    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if t.startswith("vandaag"):
        d = now.date()
    elif t.startswith("morgen"):
        d = now.date() + timedelta(days=1)
    else:
        m2 = re.search(r"(\d{1,2})\s+([a-z]{3})", t)
        if not m2 or m2.group(2) not in MND:
            return None
        d = datetime(now.year, MND[m2.group(2)], int(m2.group(1))).date()
        if d < now.date() - timedelta(days=1):
            d = d.replace(year=now.year + 1)
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=NL)

def _odd(s):
    return float(s.replace(",", "."))

def crawl(headless=True):
    """-> lijst boosts [{event, home, away, selection, old, new, kickoff}] (leeg als er geen Lekker Man is)."""
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless)
        pg = b.new_page(locale="nl-NL", user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"))
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        text = pg.inner_text("body")
        b.close()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    now = datetime.now(NL)
    out = []
    for i, l in enumerate(lines):
        m = re.match(r"^(.+?)\s+vs\s+(.+?):?$", l)
        if not m or i + 4 >= len(lines):
            continue
        # verwacht: selectie, 'NU', oude odd, nieuwe odd, datum/tijd
        sel = lines[i + 1]
        rest = lines[i + 2:i + 8]
        odds = [x for x in rest if re.fullmatch(r"\d+[.,]\d{2}", x)]
        when = next((x for x in rest if re.search(r"\d{1,2}:\d{2}", x)), "")
        if len(odds) < 2:
            continue
        out.append({"home": m.group(1).strip(), "away": m.group(2).strip().rstrip(":"),
                    "event": f"{m.group(1).strip()} – {m.group(2).strip().rstrip(':')}", "selection": sel,
                    "old": _odd(odds[0]), "new": _odd(odds[1]), "kickoff": _when(when, now)})
    return out

def fmt(x):
    return f"{x:.2f}"

def build_fields(bst):
    ev, sel, old, new = bst["event"], bst["selection"], fmt(bst["old"]), fmt(bst["new"])
    ko = bst.get("kickoff")
    wanneer = f"{ko:%d-%m-%Y} om {ko:%H:%M}" if ko else ""
    datum = f" ({ko:%d-%m} om {ko:%H:%M})" if ko else ""
    fd = {
        "name": f"TOTO Lekker Man: {ev} @ {new} (was {old})",
        "subtitel": f"{ev}{datum} · verhoogd van {old} naar {new}",
        "informatie": f"TOTO Lekker Man: {ev}",
        "bonus-tekst": f"{old} → {new}",
        "bedrag-of-boost": f"Lekker Man {old} → {new}",
        "soort-welkomstbonus": "Lekker Man (verhoogde quotering)",
        "check-1": f"Lekker Man: {old} → {new}",
        "check-2": sel[:80],
        "check-3": "De odds-boost van TOTO",
        "button-1": "Bekijk de Lekker Man bij TOTO",
        "odds-om-vrij-te-spelen": new, "minimale-storting": "Geen", "rondspeelvoorwaarden": "Geen", "leeftijd": "24+",
        "boosted-odd": True, "beste-boosted-odd": True, "100x-promotie": False, "welkomstbonus-promotie": False,
        "casino-promotie": False, "geldig-voor": GELDIG_SPORT, "promotie-rubriek": RUB_SUPERODD,
        "bookmaker-3": TOTO_BM, "bookmakers": [TOTO_BM], "affiliatie-link-naar-broker": AFFILIATE,
        "afbeelding-promotie": {"url": LOGO},
        "wedstrijd-datum-tijd": wanneer,
        "wanneer-toegevoegd": ko.replace(hour=23, minute=59).isoformat() if ko else None,
        "nederlands-elftal": "nederland" in ev.lower(),
        "content-soort-promotie-1": (f"<h3><strong>TOTO Lekker Man: {ev}</strong></h3>"
            f"<p>Met de <strong>Lekker Man</strong> verhoogt TOTO de quotering op een speciale weddenschap bij een grote wedstrijd. "
            f"Bij <strong>{ev}</strong>{datum} gaat het om: <strong>{sel}</strong>. De quotering gaat van {old} naar <strong>{new}</strong>.</p>"),
        "content-informatie-promotie-2": ("<h3><strong>Zo pak je de Lekker Man</strong></h3><ul>"
            "<li>Log in bij TOTO of maak een account aan (24+).</li>"
            "<li>Ga naar Sport en open de Lekker Man.</li>"
            f"<li>Zet in op de verhoogde quotering van {new} zolang de actie geldig is (tot de aftrap).</li></ul>"
            "<p>De Lekker Man is er niet elke dag: TOTO zet hem vooral bij Oranje en grote wedstrijden online. "
            "Op deze pagina vind je altijd de nieuwste.</p>"),
        "content-voorwaarden-promotie-3": ("<h3><strong>Belangrijkste voorwaarden</strong></h3><ul>"
            "<li>Alleen voor spelers van 24 jaar of ouder.</li><li>De verhoogde quotering geldt tot de aftrap en kan een maximale inzet hebben.</li>"
            "<li>De voorwaarden van TOTO zijn leidend.</li></ul>" f"<p>{DISCLAIMER}</p>"),
        "stap-1-titel": "Open TOTO", "stap-1-tekst": "Log in bij TOTO of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Lekker Man", "stap-2-tekst": f"De Lekker Man van nu: {ev} — {sel}.",
        "stap-3-titel": "Plaats je weddenschap", "stap-3-tekst": f"Zet in tegen de verhoogde quotering van {new}, vóór de aftrap.",
        "waar-op-letten-tekst": "De Lekker Man is kort geldig (tot de aftrap) en wisselt per wedstrijd. Controleer de actuele boost en eventuele maximale inzet bij TOTO.",
        "voorwaarde-promotie": f"TOTO Lekker Man bij {ev}: {sel}, verhoogd van {old} naar {new}. Geldig tot de aftrap. Alleen voor spelers van 24 jaar of ouder. {DISCLAIMER}",
        "volledige-voorwaarden-tekst": f"TOTO Lekker Man bij {ev}{datum}: {sel}, verhoogde quotering {new} (was {old}). Geldig tot de aftrap; alleen voor spelers van 24+. Voorwaarden van TOTO zijn van toepassing.",
        "bonus-types": "odds-boost,sport",
        "bonus-rubrieken": [RUB_SUPERODD, "6ab50fb0ddc77f0861db8e44"],   # SuperOdd, Sport bonus (zoals Bet365/Lucky's Boost)
    }
    return fd

def caption(bst):
    return "\n".join(["⚡ <b>TOTO Lekker Man LIVE!</b> 🔥", "", f"⚽ <b>{bst['event']}</b>",
                      f"📈 Quotering geboost: <s>{fmt(bst['old'])}</s> → <b>{fmt(bst['new'])}</b>", "", f"<i>{DISCLAIMER}</i>"])

def send_telegram(text, url, test=False):
    chat = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if not TELEGRAM_BOT_TOKEN or not chat:
        print("  · Telegram overgeslagen (token/chat ontbreekt)."); return False
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", timeout=30, data={
        "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False,
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Bekijk de Boost →", "url": url}]]})})
    r.raise_for_status(); return True

def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--publish", action="store_true")
    ap.add_argument("--post", action="store_true"); ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    now = datetime.now(NL)
    print(f"== TOTO Lekker Man — {now:%Y-%m-%d %H:%M} ==")
    try:
        boosts = crawl()
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)
    if not boosts:
        print("Geen Lekker Man op de site. Niets gedaan."); return
    bst = boosts[0]
    if not bst["kickoff"]:
        try:
            k = API.kickoff_for([bst["home"], bst["away"]])
            bst["kickoff"] = datetime.fromisoformat(k).astimezone(NL) if k else None
        except Exception:
            pass
    print(f"  Wedstrijd: {bst['event']} | {bst['selection']} | {fmt(bst['old'])} -> {fmt(bst['new'])} | aftrap {bst['kickoff']}")
    if bst["kickoff"] and now >= bst["kickoff"]:
        print("  · Wedstrijd is al begonnen — niets bijwerken/posten."); return
    fd = build_fields(bst)
    if a.dry:
        print(f"  [dry] titel: {fd['name']}"); return

    st = load_state()
    sig = f"{bst['event']}|{bst['selection']}|{bst['old']}|{bst['new']}"
    boost_key = f"{bst['event']}|{bst['selection']}"
    item_id = st.get("item_id")
    if not item_id:   # item opzoeken op slug
        off = 0
        while not item_id:
            d = requests.get(f"{WF_API}/collections/{PROMOTIES}/items?limit=100&offset={off}", headers=H(), timeout=60).json()
            item_id = next((i["id"] for i in d["items"] if i["fieldData"].get("slug") == SLUG), None)
            off += len(d["items"])
            if off >= d["pagination"]["total"] or not d["items"]:
                break
    if st.get("sig") != sig:
        if item_id:
            r = requests.patch(f"{WF_API}/collections/{PROMOTIES}/items/{item_id}" + ("/live" if a.publish else ""),
                               headers=H(), json={"fieldData": fd}, timeout=60)
            r.raise_for_status()
        else:
            fd.update({"slug": SLUG, "link-artikel-voor-sidebar": PROMO_BASE + SLUG})
            r = requests.post(f"{WF_API}/collections/{PROMOTIES}/items" + ("/live" if a.publish else ""),
                              headers=H(), json={"isDraft": False, "isArchived": False, "fieldData": fd}, timeout=60)
            r.raise_for_status(); item_id = r.json()["id"]
            print(f"  ✔ item aangemaakt: {r.json()['fieldData']['slug']}")
        print(f"  ✔ CMS bijgewerkt: {fd['name']}")
    else:
        print("  · Zelfde Lekker Man als vorige run — CMS ongewijzigd.")
    if a.post and boost_key != st.get("posted_key"):
        if send_telegram(caption(bst), PROMO_BASE + SLUG, test=a.test):
            print("  ✔ Telegram-teaser verstuurd."); st["posted_key"] = boost_key
    st.update({"item_id": item_id, "sig": sig, "event": bst["event"], "updated": now.isoformat()})
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("KLAAR.")

if __name__ == "__main__":
    main()
