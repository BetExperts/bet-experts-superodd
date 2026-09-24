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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import toto_crawl as C
import toto_build as B
import toto_telegram as TG
import toto_api as API                      # aftraptijd (= geldig tot) opzoeken
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

    print(f"  Wedstrijd: {data['match']}")

    # Aftrap opzoeken (staat niet op toto.nl → uit de API): voor 'geldig tot', het
    # datum/tijd-veld, én om te bepalen of de wedstrijd al live is (dan namen weg).
    kickoff = None; geldig_tot = None; wed_dt = ""; live = False
    try:
        kickoff = API.kickoff_for(data["teams"])
    except Exception as e:
        print(f"  · aftrap niet opgezocht: {e}")
    if kickoff:
        kk = datetime.fromisoformat(kickoff).astimezone(NL)
        live = now >= kk - timedelta(minutes=15)   # namen 15 min vóór de aftrap weg (agent draait elke 15 min)
        wed_dt = f"{kk:%d-%m-%Y om %H:%M}"
        gt = (kk.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1))
        geldig_tot = gt.isoformat()
        print(f"  Aftrap: {kk:%Y-%m-%d %H:%M} → "
              f"{'LIVE (algemeen, namen weg)' if live else 'vóór kickoff (met namen)'} | geldig tot {gt:%Y-%m-%d}")
    else:
        print("  Aftrap onbekend (geldig tot/datum-tijd leeg; namen blijven staan)")

    title = B.build_title(data, live)
    print(f"  Titel    : {title}")

    if a.dry:
        print("  [dry] zou de CMS-titel (+ geldig tot + datum/tijd) zetten en (bij nieuwe wedstrijd) Telegram sturen.")
        return

    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = load_state()
    prev = state.get(STATE_KEY) or {}
    match_changed = prev.get("match") != data["match"]
    content_sig = f'{data["match"]}|{"live" if live else "pre"}'
    content_changed = (prev.get("content_sig") != content_sig
                       or (bool(geldig_tot) and prev.get("geldig_tot") != geldig_tot))
    promo_url = PROMO_BASE + TOTO_SLUG

    fields = {"name": title, "wedstrijd-datum-tijd": ("" if live else wed_dt)}
    if geldig_tot:
        fields["wanneer-toegevoegd"] = geldig_tot   # "Geldig tot" = dag na de wedstrijd

    if content_changed:
        WF.update_item(TOTO_ITEM_ID, fields)
        print(f"  ✔ CMS bijgewerkt + live ({'algemeen' if live else 'met namen'}): {title}")
    else:
        print("  · Zelfde inhoud als vorige run — niets bijgewerkt.")

    state[STATE_KEY] = {"item_id": TOTO_ITEM_ID, "slug": TOTO_SLUG,
                        "match": data["match"], "title": title, "content_sig": content_sig,
                        "kickoff": kickoff, "geldig_tot": geldig_tot, "live": live,
                        "url": promo_url, "updated": now.isoformat()}
    save_state(state)

    # Telegram: één bericht per nieuwe wedstrijd, en alleen vóór kickoff (namen ok).
    if a.no_telegram:
        print("  · Telegram overgeslagen (--no-telegram).")
    elif not match_changed:
        print("  · Telegram overgeslagen (zelfde wedstrijd, al gepost).")
    elif live:
        print("  · Telegram overgeslagen (wedstrijd is al live).")
    else:
        caption = B.telegram_caption(data)
        if TG.send_photo(caption, promo_url, test=a.test):
            print(f"  ✔ Telegram-foto verstuurd{' (TEST)' if a.test else ''}.")

    print("KLAAR.")

if __name__ == "__main__":
    main()
