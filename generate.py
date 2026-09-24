# -*- coding: utf-8 -*-
"""Bet365 Super-Odd-agent: crawl -> evergreen CMS-promotieartikel -> Telegram.

Eén vast CMS-item (slug 'bet365-super-odd') dat elk uur wordt bijgewerkt:
- nieuwe wedstrijd (nieuwe Super Boost) -> artikel bijwerken + Telegram
- alleen odd/selectie gewijzigd          -> artikel stil bijwerken (geen Telegram)
- niets gewijzigd                        -> niets doen

  python3 generate.py --dry         # alleen crawlen + tonen
  python3 generate.py --test        # CMS live + Telegram naar TEST-chat
  python3 generate.py --no-telegram # wel CMS, geen Telegram
  python3 generate.py               # CMS live + Telegram naar het kanaal
"""
import sys, re, argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import so_crawl as C
import so_build as B
import toto_api as API          # aftrap opzoeken (api-sports)
import op_build as OB           # geldig_tot()
import so_webflow as WF
import so_telegram as TG
from so_config import PROMO_BASE, WEBFLOW_TOKEN, SUPERODD_SLUG, STATE_KEY

NL = ZoneInfo("Europe/Amsterdam")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="alleen crawlen, niets schrijven")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--test", action="store_true", help="Telegram naar TELEGRAM_TEST_CHAT i.p.v. het kanaal")
    ap.add_argument("--force-telegram", action="store_true", help="ook Telegram sturen bij een kleine update")
    ap.add_argument("--headed", action="store_true", help="browser zichtbaar (lokaal debuggen)")
    a = ap.parse_args()

    now = datetime.now(NL)
    print(f"== Bet365 Super Odd — {now:%Y-%m-%d %H:%M} ==")

    try:
        data = C.crawl_super_boost(headless=not a.headed)
    except Exception as e:
        print(f"FOUT bij crawlen: {e}")
        sys.exit(2)

    if not data:
        print("Geen Super Boost gevonden (of pagina geblokkeerd). Niets gedaan.")
        sys.exit(0)

    sig = B.signature(data)
    print(f"  Wedstrijd : {data['match']}")
    print(f"  Selecties : {data['selections']}")
    print(f"  Odd       : {data['old_odd']} -> {data['new_odd']}")
    print(f"  Uitbetaling: {data.get('payout')}")

    fd, slug, title = B.build_fielddata(data, slug=SUPERODD_SLUG, now=now)

    # 'Geldig tot' = einde van de wedstrijddag (aftrap via api-sports). Onbekend -> leeg.
    fd["wanneer-toegevoegd"] = None
    try:
        teams = [t.strip() for t in re.split(r"\s+(?:v|vs|-|–)\s+", data["match"]) if t.strip()]
        ko = API.kickoff_for(teams)
        if ko:
            fd["wanneer-toegevoegd"] = OB.geldig_tot(ko)
            print(f"  Aftrap   : {ko} -> geldig tot {fd['wanneer-toegevoegd'][:10]}")
        else:
            print("  Aftrap onbekend -> geldig tot leeg")
    except Exception as e:
        print(f"  · aftrap niet opgezocht: {e}")

    if a.dry:
        print(f"  [dry] evergreen item '{slug}' zou titel krijgen: {title}")
        return

    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)

    state = WF.load_state()
    prev = state.get(STATE_KEY)
    promo_url = PROMO_BASE + slug

    is_new_item   = prev is None
    match_changed = (prev is None) or (prev.get("match") != data["match"])
    unchanged     = (prev is not None) and (prev.get("sig") == sig)

    if unchanged:
        print("  · Ongewijzigd sinds vorige run — niets bijgewerkt.")
        return

    if is_new_item:
        item_id = WF.create_live(fd)
        print(f"  ✔ evergreen artikel aangemaakt: {title}  (item {item_id})")
    else:
        item_id = prev["item_id"]
        WF.update_item(item_id, fd)
        kind = "nieuwe Super Boost" if match_changed else "odd/selectie bijgewerkt"
        print(f"  ✎ artikel bijgewerkt ({kind}): {title}  (item {item_id})")

    state[STATE_KEY] = {"item_id": item_id, "slug": slug, "match": data["match"],
                        "sig": sig, "url": promo_url, "updated": now.isoformat()}
    WF.save_state(state)

    # Telegram: bij een nieuw item of een nieuwe wedstrijd; niet bij kleine tweaks.
    send = (is_new_item or match_changed or a.force_telegram)
    if a.no_telegram:
        print("  · Telegram overgeslagen (--no-telegram).")
    elif not send:
        print("  · Telegram overgeslagen (alleen kleine update, zelfde wedstrijd).")
    else:
        msg = TG.build_message(data, promo_url)
        if TG.send(msg, promo_url, test=a.test):
            print(f"  ✔ Telegram-bericht verstuurd{' (TEST)' if a.test else ''}.")

    print("KLAAR.")

if __name__ == "__main__":
    main()
