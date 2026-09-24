# -*- coding: utf-8 -*-
"""Oranje Palace Super Odd-agent: crawl 'Lucky's Boost' -> CMS-item bijwerken -> Telegram.

  python3 op_superodd.py --dry            # alleen crawlen + tonen
  python3 op_superodd.py                  # CMS-item GESTAGED bijwerken (niet live)
  python3 op_superodd.py --publish        # CMS-item LIVE zetten (na partnership)
  python3 op_superodd.py --publish --post # live + Telegram-teaser
  python3 op_superodd.py --headed         # zichtbare browser (debug)

Pre-partnership: standaard STAGED (niet publiceren) en GEEN Telegram. Zet --publish
en --post pas aan zodra de deal rond is en de affiliatelink in de CMS staat.
"""
import os, sys, json, argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import op_crawl as C
import op_build as B
from op_config import OP_ITEM_ID, OP_SLUG, STATE_KEY
from so_config import (WEBFLOW_TOKEN, WF_API, PROMOTIES_COLLECTION, PROMO_BASE,
                       TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT)

NL = ZoneInfo("Europe/Amsterdam")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "oranjepalace.json")

def load_state():
    try: return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception: return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _headers():
    return {"Authorization": "Bearer " + WEBFLOW_TOKEN, "accept": "application/json",
            "content-type": "application/json"}

def update_item(fields, live=False):
    """live=False -> gestaged (niet gepubliceerd); live=True -> direct live."""
    suffix = "/live" if live else ""
    url = f"{WF_API}/collections/{PROMOTIES_COLLECTION}/items/{OP_ITEM_ID}{suffix}"
    body = {"isArchived": False, "isDraft": not live, "fieldData": fields}
    if live:
        body["isDraft"] = False
    r = requests.patch(url, headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json().get("id", OP_ITEM_ID)

def send_telegram(caption, url, test=False):
    chat = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if not TELEGRAM_BOT_TOKEN or (test and not TELEGRAM_TEST_CHAT):
        print("  · Telegram overgeslagen (token/chat ontbreekt)."); return False
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat, "text": caption, "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Bekijk de Lucky's Boost →", "url": url}]]})}
    r = requests.post(api, data=data, timeout=30); r.raise_for_status(); return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--publish", action="store_true", help="CMS live zetten i.p.v. gestaged")
    ap.add_argument("--post", action="store_true", help="Telegram-teaser sturen (bij nieuwe boost)")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    now = datetime.now(NL)
    print(f"== Oranje Palace Super Odd — {now:%Y-%m-%d %H:%M} ==")

    try:
        data = C.crawl_superodd(headless=not a.headed)
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)
    if not data:
        print("Geen Lucky's Boost gevonden op de homepage. Niets gedaan."); sys.exit(0)

    title = B.build_title(data)
    print(f"  Wedstrijd : {data.get('event')}")
    print(f"  Selectie  : {data.get('selection')}  ({data.get('market')})")
    print(f"  Odd       : {data.get('old_odd')} -> {data.get('new_odd')}"
          f"   max €{data.get('max_stake')}   verloopt {data.get('expiry')}")
    print(f"  Titel     : {title}")

    if a.dry:
        print("  [dry] zou het CMS-item hierop bijwerken"
              f"{' + LIVE' if a.publish else ' (gestaged)'}"
              f"{' + Telegram' if a.post else ''}.")
        return

    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = load_state()
    prev = state.get(STATE_KEY) or {}
    sig = B.signature(data)
    changed = prev.get("sig") != sig
    promo_url = PROMO_BASE + OP_SLUG

    fields = B.build_fielddata(data, now)
    if changed:
        update_item(fields, live=a.publish)
        print(f"  ✔ CMS bijgewerkt ({'LIVE' if a.publish else 'gestaged'}): {title}")
    else:
        print("  · Zelfde boost als vorige run — CMS ongewijzigd.")

    state[STATE_KEY] = {"item_id": OP_ITEM_ID, "slug": OP_SLUG, "sig": sig,
                        "title": title, "event": data.get("event"),
                        "old_odd": data.get("old_odd"), "new_odd": data.get("new_odd"),
                        "url": promo_url, "updated": now.isoformat()}
    save_state(state)

    if a.post and changed:
        if send_telegram(B.telegram_caption(promo_url), promo_url, test=a.test):
            print(f"  ✔ Telegram-teaser verstuurd{' (TEST)' if a.test else ''}.")
    elif a.post:
        print("  · Telegram overgeslagen (zelfde boost).")

    print("KLAAR.")

if __name__ == "__main__":
    main()
