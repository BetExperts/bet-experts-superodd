# -*- coding: utf-8 -*-
"""Leest (alleen lezen!) de ledenlijst van de twee VIP-kanalen met Jaspers eigen Telegram-account.

  .venv/bin/python vip_leden.py

De eerste keer vraagt Telegram om je telefoonnummer en de inlogcode (en evt. je 2FA-wachtwoord);
die typ je zelf in. De sessie blijft lokaal in state/telegram/ (gitignored).
Uitvoer: state/vip/leden.json  (id, @gebruikersnaam, naam, per kanaal)."""
import asyncio, json, os
from telethon import TelegramClient
from telethon.tl.types import ChannelParticipantsSearch

KANALEN = {"VIP": -1003300794018, "Livebet": -1003613655782}
HERE = os.path.dirname(os.path.abspath(__file__))


def env():
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)


async def main():
    env()
    client = TelegramClient(os.path.join(HERE, "state", "telegram", "jasper"),
                            int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    await (client.start(phone=os.environ["TG_PHONE"]) if os.environ.get("TG_PHONE") else client.start())
    await client.get_dialogs()                     # zodat de kanaal-id's bekend zijn
    out = {}
    for naam, cid in KANALEN.items():
        ent = await client.get_entity(cid)
        seen = {}
        # broadcastkanalen geven max. ~200 per zoekopdracht: leeg + per letter zoeken voor de volledigheid
        for q in [""] + list("abcdefghijklmnopqrstuvwxyz0123456789"):
            async for u in client.iter_participants(ent, search=q):
                seen[u.id] = {"id": u.id, "username": u.username, "naam": " ".join(x for x in (u.first_name, u.last_name) if x),
                              "bot": u.bot, "verwijderd_account": u.deleted}
        out[naam] = sorted(seen.values(), key=lambda x: (x["naam"] or "").lower())
        print(f"{naam}: {len(out[naam])} leden opgehaald")
    json.dump(out, open(os.path.join(HERE, "state", "vip", "leden.json"), "w"), ensure_ascii=False, indent=1)
    print("Klaar. Je kunt dit venster sluiten.")
    await client.disconnect()

asyncio.run(main())
