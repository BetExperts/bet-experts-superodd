# -*- coding: utf-8 -*-
"""TOTO 50x-agent: crawl toto.nl -> CMS-titel bijwerken -> dagelijks Telegram (foto).

  python3 toto50x.py --dry          # alleen crawlen + tonen
  python3 toto50x.py --test         # CMS-titel live + Telegram naar TEST-chat
  python3 toto50x.py --no-telegram  # wel CMS-titel, geen Telegram
  python3 toto50x.py                # CMS-titel live + Telegram naar het kanaal

Alleen de TITEL van het bestaande artikel wordt bijgewerkt (rest blijft).
Telegram gaat één keer per dag uit: bij een NIEUWE wedstrijd.
"""
import os, sys, json, argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import toto_crawl as C
import toto_build as B
import toto_telegram as TG
import so_webflow as WF                     # hergebruikt update_item (publiceert)
from so_config import PROMO_BASE, WEBFLOW_TOKEN
from toto_config import TOTO_ITEM_ID, TOTO_SLUG, STATE_KEY

NL = ZoneInfo("Europe/Amsterdam")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "toto50x.json")

def load_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()

    now = datetime.now(NL)
    print(f"== TOTO 50x — {now:%Y-%m-%d %H:%M} ==")

    try:
        data = C.crawl_50x(headless=not a.headed)
    except Exception as e:
        print(f"FOUT bij crawlen: {e}"); sys.exit(2)

    if not data:
        print("Geen 50x-actie gevonden op toto.nl (mogelijk even geen actie). Niets gedaan.")
        sys.exit(0)

    title = B.build_title(data)
    print(f"  Wedstrijd: {data['match']}")
    print(f"  Titel    : {title}")

    if a.dry:
        print("  [dry] zou de CMS-titel hierop zetten en (bij nieuwe wedstrijd) Telegram sturen.")
        return

    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = load_state()
    prev = state.get(STATE_KEY)
    match_changed = (prev is None) or (prev.get("match") != data["match"])
    promo_url = PROMO_BASE + TOTO_SLUG

    if match_changed:
        WF.update_item(TOTO_ITEM_ID, {"name": title})
        print(f"  ✔ CMS-titel bijgewerkt + live: {title}")
    else:
        print("  · Zelfde wedstrijd als vorige run — titel ongewijzigd.")

    state[STATE_KEY] = {"item_id": TOTO_ITEM_ID, "slug": TOTO_SLUG,
                        "match": data["match"], "title": title,
                        "url": promo_url, "updated": now.isoformat()}
    save_state(state)

    # Telegram: één bericht per nieuwe wedstrijd (≈ dagelijks).
    if a.no_telegram:
        print("  · Telegram overgeslagen (--no-telegram).")
    elif not match_changed:
        print("  · Telegram overgeslagen (zelfde wedstrijd, al gepost).")
    else:
        caption = B.telegram_caption(data)
        if TG.send_photo(caption, promo_url, test=a.test):
            print(f"  ✔ Telegram-foto verstuurd{' (TEST)' if a.test else ''}.")

    print("KLAAR.")

if __name__ == "__main__":
    main()
