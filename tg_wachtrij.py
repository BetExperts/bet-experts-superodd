# -*- coding: utf-8 -*-
"""Telegram-wachtrij (9-11-2026): geplande posts naar @BetExpertsGroup.

state/tg_wachtrij.json = lijst met posts:
  {"id", "na": "2026-11-12T09:30" (NL-tijd), "tot": optioneel uiterste tijd, "slug", "kop", "tekst", "knop",
   "voorwaarde": optioneel "bevestigde_elf" (pas posten als de pagina de officiële opstelling toont),
   "verstuurd": msg-id of null}
Deelkaart: live-kijken-agent/og/nieuws/nieuws-<slug>.webp (anders zonder afbeelding). Knop -> eigen pagina, nooit een
affiliatelink. Draait elke 5 min mee in opstellingen-agent/run_finalize_mac.sh.
  python3 tg_wachtrij.py            # versturen wat aan de beurt is
  python3 tg_wachtrij.py --lijst    # overzicht
"""
import io, json, os, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from PIL import Image
import so_config as c

HIER = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HIER, "state", "tg_wachtrij.json")
OG = os.path.join(HIER, "..", "live-kijken-agent", "og", "nieuws")
NL = ZoneInfo("Europe/Amsterdam")
KSA = "<i>Wat kost gokken jou? Stop op tijd. 18+</i>"


def laad():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return []


def bewaar(q):
    json.dump(q, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def bevestigde_elf(slug):
    try:
        html = urllib.request.urlopen(urllib.request.Request(f"https://www.bet-experts.nl/nieuws/{slug}?w={int(datetime.now().timestamp())}",
                                                             headers={"User-Agent": "BetExpertsBot/1.0"}), timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return False
    titel = html.split("<title>", 1)[-1].split("</title>", 1)[0].lower()
    return "bevestigde elf" in titel or "definitieve opstelling" in titel


def stuur(p):
    url = f"https://www.bet-experts.nl/nieuws/{p['slug']}"
    tekst = f"<b>{p['kop']}</b>\n\n{p['tekst']}\n\n{KSA}"
    kb = json.dumps({"inline_keyboard": [[{"text": p["knop"], "url": url}]]})
    api = f"https://api.telegram.org/bot{c.TELEGRAM_BOT_TOKEN}"
    kaart = os.path.join(OG, f"nieuws-{p.get('kaart') or p['slug']}.webp")
    if os.path.exists(kaart):
        buf = io.BytesIO(); Image.open(kaart).convert("RGB").save(buf, "JPEG", quality=92); buf.seek(0)
        r = requests.post(f"{api}/sendPhoto", data={"chat_id": c.TELEGRAM_CHANNEL, "caption": tekst, "parse_mode": "HTML",
                                                     "reply_markup": kb}, files={"photo": ("kaart.jpg", buf, "image/jpeg")}, timeout=60)
    else:
        r = requests.post(f"{api}/sendMessage", data={"chat_id": c.TELEGRAM_CHANNEL, "text": tekst, "parse_mode": "HTML",
                                                       "disable_web_page_preview": "true", "reply_markup": kb}, timeout=60)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(j.get("description"))
    return j["result"]["message_id"]


def main():
    q = laad()
    nu = datetime.now(NL).replace(tzinfo=None)
    if "--lijst" in sys.argv:
        for p in q:
            print(f"{p['na']}  {'✓ ' + str(p['verstuurd']) if p.get('verstuurd') else ('✗ verlopen' if p.get('verlopen') else '…')}  {p['id']}")
        return
    for p in q:
        if p.get("verstuurd") or p.get("verlopen") or nu < datetime.fromisoformat(p["na"]):
            continue
        if p.get("tot") and nu > datetime.fromisoformat(p["tot"]):
            p["verlopen"] = True; bewaar(q); print(f"tg-wachtrij: verlopen {p['id']}"); continue
        if p.get("voorwaarde") == "bevestigde_elf" and not bevestigde_elf(p["slug"]):
            continue
        try:
            p["verstuurd"] = stuur(p)
            print(f"tg-wachtrij: verstuurd {p['id']} ({p['verstuurd']})")
        except Exception as e:
            print(f"tg-wachtrij: FOUT {p['id']}: {e}")
        bewaar(q)


if __name__ == "__main__":
    main()
