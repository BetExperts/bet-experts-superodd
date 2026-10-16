# -*- coding: utf-8 -*-
"""TOTO 50x-agent: wedstrijd van de dag kiezen -> CMS-titel bijwerken -> dagelijks Telegram (foto).

Sinds 16-10-2026 (mail TOTO): de 50x-actie is generiek — nieuwe spelers mogen zelf een wedstrijd kiezen en
wij communiceren zelf welke. toto.nl noemt de wedstrijd dus niet meer. De agent kiest elke dag de belangrijkste
wedstrijd van vandaag uit onze topwedstrijden (/api/hero: Oranje, NL-topclubs, Europese toppers, met
voorbeschouwing), die nog minstens een uur moet beginnen. Geen geschikte wedstrijd -> algemene titel.

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

import requests
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

HERO_API = "https://www.bet-experts.nl/api/hero"


def kies_wedstrijd(state, now):
    """Wedstrijd van de dag: de eerder vandaag gekozen wedstrijd blijft staan; anders de belangrijkste
    topwedstrijd van vandaag die nog minstens 60 min moet beginnen (score uit /api/hero)."""
    prev = (state or {}).get(STATE_KEY) or {}
    vandaag = f"{now:%Y-%m-%d}"
    if prev.get("dag") == vandaag and prev.get("teams") and prev.get("kickoff"):
        return {"teams": prev["teams"], "match": prev["match"], "kickoff": prev["kickoff"]}
    try:
        items = requests.get(HERO_API, timeout=30, headers={"User-Agent": "bet-experts toto50x"}).json().get("items") or []
    except Exception as e:
        print(f"  · topwedstrijden niet op te halen: {e}")
        return None
    kand = []
    for it in items:
        ko = datetime.fromisoformat(it["ko"].replace("Z", "+00:00")).astimezone(NL)
        if f"{ko:%Y-%m-%d}" == vandaag and ko >= now + timedelta(minutes=60):
            kand.append((-(it.get("score") or 0), ko, it))
    if not kand:
        return None
    _, ko, it = sorted(kand, key=lambda x: (x[0], x[1]))[0]
    return {"teams": [it["home"], it["away"]], "match": f"{it['home']} - {it['away']}", "kickoff": ko.isoformat()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()

    now = datetime.now(NL)
    print(f"== TOTO 50x — {now:%Y-%m-%d %H:%M} ==")

    data = kies_wedstrijd(load_state(), now)
    if not data:
        data = {"teams": [], "match": f"algemeen-{now:%Y-%m-%d}", "kickoff": None}
        print("  Geen topwedstrijd meer vandaag -> algemene titel")
    else:
        print(f"  Wedstrijd: {data['match']}")

    # Aftrap (uit /api/hero): voor 'geldig tot', het datum/tijd-veld, en om te bepalen of de wedstrijd al
    # live is (dan namen weg).
    kickoff = data.get("kickoff"); geldig_tot = None; wed_dt = ""; live = not data["teams"]
    if kickoff:
        kk = datetime.fromisoformat(kickoff).astimezone(NL)
        live = now >= kk - timedelta(minutes=15)   # namen 15 min vóór de aftrap weg (agent draait elke 15 min)
        wed_dt = f"{kk:%d-%m-%Y om %H:%M}"
        gt = (kk.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1))
        geldig_tot = gt.isoformat()
        print(f"  Aftrap: {kk:%Y-%m-%d %H:%M} → "
              f"{'LIVE (algemeen, namen weg)' if live else 'vóór kickoff (met namen)'} | geldig tot {gt:%Y-%m-%d}")
    else:
        # algemene actie (geen wedstrijd gekozen): doorlopend, dus 'geldig tot' morgen 12:00 (nooit 'Verlopen')
        geldig_tot = (now.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
        print("  Geen wedstrijd -> algemene titel, geldig tot morgen 12:00")

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
                        "url": promo_url, "updated": now.isoformat(), "dag": f"{now:%Y-%m-%d}",
                        "teams": data["teams"], "tg_match": prev.get("tg_match")}
    save_state(state)

    # Telegram: één bericht per nieuwe wedstrijd, en alleen vóór kickoff (namen ok).
    if a.no_telegram:
        print("  · Telegram overgeslagen (--no-telegram).")
    elif prev.get("tg_match") == data["match"] and not a.test:
        print("  · Telegram overgeslagen (zelfde wedstrijd, al gepost).")
    elif live or not data["teams"]:
        print("  · Telegram overgeslagen (geen wedstrijd of al live).")
    elif not (9 <= now.hour < 22) and not a.test:
        print("  · Telegram wacht tot 09:00 (geen posts 's nachts).")
    else:
        caption = B.telegram_caption(data)
        if TG.send_photo(caption, promo_url, test=a.test):
            print(f"  ✔ Telegram-foto verstuurd{' (TEST)' if a.test else ''}.")
            if not a.test:
                state[STATE_KEY]["tg_match"] = data["match"]; save_state(state)

    print("KLAAR.")

if __name__ == "__main__":
    main()
