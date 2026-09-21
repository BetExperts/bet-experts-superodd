# -*- coding: utf-8 -*-
"""888Sport 60x-agent: crawl promo.888.nl -> CMS-artikel bijwerken -> Telegram (foto).

  python3 s888_60x.py --dry          # alleen crawlen + tonen
  python3 s888_60x.py --test         # CMS live + Telegram naar TEST-chat
  python3 s888_60x.py --no-telegram  # wel CMS, geen Telegram
  python3 s888_60x.py                # CMS live + Telegram naar het kanaal

Tot de kickoff staan de teamnamen in het artikel; zodra de wedstrijd live gaat
schakelt het artikel automatisch naar de algemene variant (namen weg, KSA).
Telegram gaat 1x per NIEUWE wedstrijd uit (met de 60x-afbeelding).
"""
import os, sys, json, argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import s888_crawl as C
import s888_build as B
import so_webflow as WF
from so_config import PROMO_BASE, WEBFLOW_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT
from s888_config import ITEM_ID, SLUG, STATE_KEY, IMAGE

NL = ZoneInfo("Europe/Amsterdam")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "s888_60x.json")

def load_state():
    try: return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception: return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def send_photo(caption, url, test=False):
    chat = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if not TELEGRAM_BOT_TOKEN or (test and not TELEGRAM_TEST_CHAT):
        print("  · Telegram overgeslagen (token/chat ontbreekt)."); return False
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": chat, "caption": caption, "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Bekijk de actie →", "url": url}]]})}
    with open(IMAGE, "rb") as f:
        r = requests.post(api, data=data, files={"photo": f}, timeout=30)
    r.raise_for_status(); return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()

    now = datetime.now(NL)
    print(f"== 888Sport 60x — {now:%Y-%m-%d %H:%M} ==")
    try:
        data = C.crawl_60x(headless=not a.headed)
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)
    if not data:
        print("Geen actieve 60x-boost gevonden op de 888-pagina. Niets gedaan."); sys.exit(0)

    fields, live = B.build_fields(data, now)
    print(f"  Wedstrijd : {data['home']} – {data['away']}  ({data['market']})")
    print(f"  Kickoff   : {data['datetime_text']}   → {'LIVE (algemeen, namen weg)' if live else 'vóór kickoff (met namen)'}")
    print(f"  Titel     : {fields['name']}")

    if a.dry:
        print("  [dry] zou het CMS-artikel hierop bijwerken en (bij nieuwe wedstrijd) Telegram sturen.")
        return
    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = load_state()
    prev = state.get(STATE_KEY) or {}
    sig = B.signature(data)
    match_changed = prev.get("sig") != sig
    content_sig = f"{sig}|{'live' if live else 'pre'}"
    content_changed = prev.get("content_sig") != content_sig
    promo_url = PROMO_BASE + SLUG

    if content_changed:
        WF.update_item(ITEM_ID, fields)
        print(f"  ✔ CMS bijgewerkt + live ({'algemeen' if live else 'met namen'}).")
    else:
        print("  · Zelfde inhoud als vorige run — CMS ongewijzigd.")

    state[STATE_KEY] = {"item_id": ITEM_ID, "slug": SLUG, "sig": sig,
                        "content_sig": content_sig, "live": live,
                        "match": f'{data["home"]} - {data["away"]}',
                        "kickoff": data["kickoff"].isoformat(), "updated": now.isoformat()}
    save_state(state)

    # Telegram: 1x per NIEUWE wedstrijd, en alleen vóór kickoff (namen mogen dan).
    if a.no_telegram:
        print("  · Telegram overgeslagen (--no-telegram).")
    elif not match_changed:
        print("  · Telegram overgeslagen (zelfde wedstrijd).")
    elif live:
        print("  · Telegram overgeslagen (wedstrijd is al live).")
    else:
        if send_photo(B.telegram_caption(data), promo_url, test=a.test):
            print(f"  ✔ Telegram-foto verstuurd{' (TEST)' if a.test else ''}.")
    print("KLAAR.")

if __name__ == "__main__":
    main()
