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

    title = B.build_title(data)
    print(f"  Wedstrijd: {data['match']}")
    print(f"  Titel    : {title}")

    # Geldig tot = de dag ná de wedstrijd (de actie loopt t/m de wedstrijddag zelf).
    # We zoeken de aftrap op (staat niet op toto.nl → uit de API) en zetten het veld
    # op 12:00 lokaal van de dag erna. Noon voorkomt de UTC-dagverschuiving.
    kickoff = None       # ruwe aftrap (voor logging + state-vergelijking)
    geldig_tot = None    # wat we in het CMS-veld zetten
    try:
        kickoff = API.kickoff_for(data["teams"])
    except Exception as e:
        print(f"  · geldig-tot niet opgezocht: {e}")
    if kickoff:
        kk = datetime.fromisoformat(kickoff).astimezone(NL)
        gt = (kk.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1))
        geldig_tot = gt.isoformat()
        print(f"  Wedstrijd aftrap: {kk:%Y-%m-%d %H:%M}  →  Geldig tot: {gt:%Y-%m-%d} (dag erna)")
    else:
        print("  Geldig tot: niet gevonden (veld blijft ongemoeid)")

    if a.dry:
        print("  [dry] zou de CMS-titel (+ geldig tot) hierop zetten en (bij nieuwe wedstrijd) Telegram sturen.")
        return

    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = load_state()
    prev = state.get(STATE_KEY)
    match_changed = (prev is None) or (prev.get("match") != data["match"])
    geldig_changed = bool(geldig_tot) and (prev is None or prev.get("geldig_tot") != geldig_tot)
    promo_url = PROMO_BASE + TOTO_SLUG

    fields = {"name": title}
    if geldig_tot:
        fields["wanneer-toegevoegd"] = geldig_tot   # "Geldig tot" = dag na de wedstrijd

    if match_changed or geldig_changed:
        WF.update_item(TOTO_ITEM_ID, fields)
        wat = "titel + geldig tot" if geldig_tot else "titel"
        print(f"  ✔ CMS bijgewerkt + live ({wat}): {title}")
    else:
        print("  · Zelfde wedstrijd én geldig tot als vorige run — niets bijgewerkt.")

    state[STATE_KEY] = {"item_id": TOTO_ITEM_ID, "slug": TOTO_SLUG,
                        "match": data["match"], "title": title,
                        "kickoff": kickoff, "geldig_tot": geldig_tot,
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
