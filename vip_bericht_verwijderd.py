# -*- coding: utf-8 -*-
"""Stuurt vanaf Jaspers eigen Telegram-account een bericht naar leden die uit de VIP zijn gehaald.

  .venv/bin/python vip_bericht_verwijderd.py state/vip/verwijderd_2026-10-03.json

Veiligheid tegen een spam-ban:
- alleen mensen met wie Jasper al een privéchat heeft (nooit 'koud' naar onbekenden);
- één bericht per persoon, met 45-100 seconden willekeurige pauze ertussen en elke 15 berichten een langere pauze;
- FloodWait van Telegram -> netjes wachten; PeerFlood (spamlimiet) -> direct stoppen;
- voortgang in state/vip/berichten_log.json, dus opnieuw starten slaat al verstuurde berichten over."""
import asyncio, json, os, random, sys, time
from telethon import TelegramClient, errors

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "state", "vip", "berichten_log.json")
TEKST = ("Hoi{naam}! Je abonnement op Bet Experts VIP is verlopen, daarom ben je uit de VIP- en Livebet-groep gehaald. "
         "Wil je er weer in? Verleng je abonnement via bet-experts.nl/vip en stuur me daarna je Telegram-gebruikersnaam, "
         "dan voeg ik je direct weer toe. 💪")


def env():
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)


def voornaam(naam):
    w = (naam or "").strip().split()
    return f" {w[0]}" if w and w[0].isalpha() and len(w[0]) >= 2 else ""


async def main(path):
    env()
    mensen = json.load(open(path, encoding="utf-8"))
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {}
    c = TelegramClient(os.path.join(HERE, "state", "telegram", "jasper"), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    await c.connect()
    assert await c.is_user_authorized(), "niet ingelogd"
    verstuurd = 0
    for p in mensen:
        key = str(p["id"])
        if log.get(key, {}).get("status") in ("verstuurd", "geen chat", "overslaan"):
            continue
        if not any(v.startswith("verwijderd") for v in p["resultaat"].values()):
            continue
        try:
            heeft_chat = bool(await c.get_messages(p["id"], limit=1))
        except Exception:
            heeft_chat = False
        if not heeft_chat:
            log[key] = {"naam": p["naam"], "status": "geen chat"}
            json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"overgeslagen (geen eerdere chat): {p['naam']}")
            continue
        try:
            await c.send_message(p["id"], TEKST.format(naam=voornaam(p["naam"])))
            log[key] = {"naam": p["naam"], "status": "verstuurd", "tijd": time.strftime("%H:%M:%S")}
            verstuurd += 1
            print(f"{time.strftime('%H:%M:%S')} verstuurd ({verstuurd}): {p['naam']}", flush=True)
        except errors.FloodWaitError as e:
            print(f"FloodWait: {e.seconds}s wachten", flush=True)
            await asyncio.sleep(e.seconds + 5)
            continue
        except errors.PeerFloodError:
            print("STOP: Telegram meldt een spamlimiet (PeerFlood). Later opnieuw starten.", flush=True)
            break
        except Exception as e:
            log[key] = {"naam": p["naam"], "status": f"fout: {str(e)[:80]}"}
            print(f"fout bij {p['naam']}: {e}", flush=True)
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        await asyncio.sleep(random.uniform(45, 100) + (240 if verstuurd and verstuurd % 15 == 0 else 0))
    await c.disconnect()
    print(f"KLAAR: {verstuurd} berichten verstuurd", flush=True)

asyncio.run(main(sys.argv[1]))
