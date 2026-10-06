# -*- coding: utf-8 -*-
"""Welkomstbericht vanaf Jaspers eigen Telegram-account naar nieuwe VIP-abonnees.

  .venv/bin/python vip_welkom.py            # versturen (LaunchAgent, elke 10 min)
  .venv/bin/python vip_welkom.py --dry      # alleen tonen

Kijkt in Stripe naar abonnementen van de laatste 3 dagen. Staat er een geldige Telegram-gebruikersnaam
in het checkoutveld, dan krijgt die persoon één keer een persoonlijk bericht met de aanvraaglinks.
Veilig tegen spamblokkades: alleen nieuwe betalers, max. 5 per run, 30-60 s pauze, stopt bij PeerFlood.
Log: state/vip/welkom_log.json (ook handmatig verstuurde berichten staan daar als 'handmatig')."""
import asyncio, datetime as dt, json, os, random, re, sys, time
import requests
from telethon import TelegramClient, errors

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "state", "vip", "welkom_log.json")
PLAN = {
    "plink_1NkN04EbH2EIpuOZR99NdbAi": "maandabonnement",
    "plink_1NkNKeEbH2EIpuOZKbF6C14E": "abonnement van 3 maanden",
    "plink_1NkNPgEbH2EIpuOZZw12KYaQ": "jaarabonnement",
}
LINKS = {"Prebet VIP": "https://t.me/+CTu6YgGT3k9mNTc0", "Livebet": "https://t.me/+AkQ-BPaJOvFmMTZk"}
TEKST = ("Hoi{naam}! 👋\n\n"
         "Bedankt voor je {plan} bij Bet Experts VIP, welkom bij de club! 🎉\n\n"
         "Je krijgt toegang tot onze twee VIP-kanalen:\n"
         "🆕 Prebet VIP: {prebet}\n"
         "⚡ Livebet: {livebet}\n\n"
         "Tik op beide links en vraag toegang aan, dan laat onze bot je direct toe. "
         "Lukt er iets niet of heb je een vraag? Stuur me hier gerust een berichtje.\n\n"
         "Veel succes en speel bewust! 💪")


def env():
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)


def handle(raw):
    h = re.sub(r"^https?://(t|telegram)\.me/", "", (raw or "").strip(), flags=re.I).lstrip("@")
    return h if re.fullmatch(r"[A-Za-z0-9_]{5,32}", h) else None


def nieuwe_abonnees():
    S = requests.Session(); S.auth = (os.environ["STRIPE_RESTRICTED_KEY"], "")
    since = int((dt.datetime.now() - dt.timedelta(days=3)).timestamp())
    subs = S.get("https://api.stripe.com/v1/subscriptions", params={"limit": 50, "status": "all", "created[gte]": since},
                 timeout=30).json().get("data", [])
    out = []
    for s in subs:
        if s["status"] not in ("active", "trialing"):
            continue
        cs = S.get("https://api.stripe.com/v1/checkout/sessions", params={"subscription": s["id"], "limit": 1}, timeout=30).json()["data"]
        if not cs:
            continue
        raw = next((f["text"]["value"] for f in cs[0].get("custom_fields", []) if f["key"] == "gebruikersnaamtelegram"), None)
        out.append({"sub": s["id"], "raw": raw, "handle": handle(raw), "plan": PLAN.get(cs[0].get("payment_link"), "abonnement"),
                    "naam": (cs[0].get("customer_details") or {}).get("name") or ""})
    return out


async def main(dry):
    env()
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {}
    todo = [a for a in nieuwe_abonnees() if a["sub"] not in log]
    if not todo:
        return
    c = TelegramClient(os.path.join(HERE, "state", "telegram", "jasper"), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    await c.connect()
    if not await c.is_user_authorized():
        print("niet ingelogd"); return
    for n, a in enumerate(todo[:5]):
        if not a["handle"]:
            log[a["sub"]] = {"status": "geen geldige gebruikersnaam", "raw": a["raw"], "tijd": time.strftime("%Y-%m-%d %H:%M")}
            print(f"overgeslagen, geen gebruikersnaam: {a['raw']!r}"); continue
        try:
            u = await c.get_entity(a["handle"])
        except Exception as e:
            log[a["sub"]] = {"status": f"gebruikersnaam niet gevonden: {a['handle']}", "tijd": time.strftime("%Y-%m-%d %H:%M")}
            print(f"niet gevonden: @{a['handle']} ({type(e).__name__})"); continue
        voornaam = (getattr(u, "first_name", None) or (a["naam"].split() or [""])[0]).strip()
        if not re.fullmatch(r"[^\W\d_][\w'-]{1,20}", voornaam):    # emoji/rare tekens -> zonder naam
            voornaam = ""
        tekst = TEKST.format(naam=f" {voornaam}" if voornaam else "", plan=a["plan"], prebet=LINKS["Prebet VIP"], livebet=LINKS["Livebet"])
        if dry:
            print(f"--- naar @{a['handle']}\n{tekst}\n"); continue
        try:
            await c.send_message(u, tekst, link_preview=False)
            log[a["sub"]] = {"status": "verstuurd", "handle": a["handle"], "tijd": time.strftime("%Y-%m-%d %H:%M")}
            print(f"verstuurd: @{a['handle']}")
        except errors.FloodWaitError as e:
            print(f"FloodWait {e.seconds}s, volgende run verder"); break
        except errors.PeerFloodError:
            print("STOP: spamlimiet (PeerFlood)"); break
        except Exception as e:
            log[a["sub"]] = {"status": f"fout: {str(e)[:80]}", "tijd": time.strftime("%Y-%m-%d %H:%M")}
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if n < len(todo) - 1:
            await asyncio.sleep(random.uniform(30, 60))
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    await c.disconnect()

asyncio.run(main("--dry" in sys.argv))
