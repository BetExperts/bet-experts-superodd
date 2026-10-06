# -*- coding: utf-8 -*-
"""Bericht (vanaf Jaspers account) naar VIP-leden van wie de Stripe-betaling is mislukt.

  .venv/bin/python vip_betaling.py [--dry]

Kijkt naar abonnementen met status past_due. Per openstaande factuur krijgt het lid één keer een kort
bericht: betaling mislukt, wie niet betaalt wordt verwijderd, stuur Jasper een berichtje voor een betaallink.
Het Telegram-account komt uit de VIP-koppeling (Cloudflare KV, sub:<id> -> tg_ids) of anders uit de
gebruikersnaam in de checkout. Log: state/vip/betaling_log.json. Draait mee met run_vip_welkom.sh."""
import asyncio, json, os, random, re, sys, time
import requests
from telethon import TelegramClient, errors

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "state", "vip", "betaling_log.json")
KV_NS = "e60e4b46dfee41c984a67d2bdedfc66c"
TEKST = ("Hoi{naam}! 👋\n\n"
         "De betaling voor je Bet Experts VIP-abonnement is helaas mislukt. "
         "Lukt de betaling niet, dan word je automatisch uit de VIP gehaald.\n\n"
         "Wil je wel betalen? Stuur me hier even een berichtje, dan stuur ik je een betaallink. 💪")


def env():
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)


def kv(key):
    r = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/storage/kv/"
                     f"namespaces/{KV_NS}/values/{key}", headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
                     timeout=20)
    try:
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def mislukt():
    S = requests.Session(); S.auth = (os.environ["STRIPE_RESTRICTED_KEY"], "")
    subs = S.get("https://api.stripe.com/v1/subscriptions", params={"status": "past_due", "limit": 100}, timeout=30).json().get("data", [])
    out = []
    for s in subs:
        inv = s.get("latest_invoice")
        inv = inv["id"] if isinstance(inv, dict) else inv
        cs = S.get("https://api.stripe.com/v1/checkout/sessions", params={"subscription": s["id"], "limit": 1}, timeout=30).json().get("data", [])
        raw = next((f["text"]["value"] for f in (cs[0].get("custom_fields", []) if cs else []) if f["key"] == "gebruikersnaamtelegram"), None)
        h = re.sub(r"^https?://(t|telegram)\.me/", "", (raw or "").strip(), flags=re.I).lstrip("@")
        rec = kv(f"sub:{s['id']}") or {}
        out.append({"sub": s["id"], "invoice": inv or s["id"], "tg_ids": rec.get("tg_ids") or [],
                    "handle": h if re.fullmatch(r"[A-Za-z0-9_]{5,32}", h) else None,
                    "naam": ((cs[0].get("customer_details") or {}).get("name") if cs else "") or rec.get("naam") or ""})
    return out


async def main(dry):
    env()
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {}
    todo = [m for m in mislukt() if m["invoice"] not in log]
    if not todo:
        return
    c = TelegramClient(os.path.join(HERE, "state", "telegram", "jasper"), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    await c.connect()
    if not await c.is_user_authorized():
        print("niet ingelogd"); return
    for n, m in enumerate(todo[:5]):
        u = None
        for target in m["tg_ids"] + ([m["handle"]] if m["handle"] else []):
            try:
                u = await c.get_entity(target); break
            except Exception:
                continue
        if not u:
            log[m["invoice"]] = {"status": "geen Telegram-account gevonden", "sub": m["sub"], "naam": m["naam"], "tijd": time.strftime("%Y-%m-%d %H:%M")}
            print(f"geen Telegram-account voor {m['naam']} ({m['sub']})"); continue
        voornaam = (getattr(u, "first_name", None) or (m["naam"].split() or [""])[0]).strip()
        if not re.fullmatch(r"[^\W\d_][\w'-]{1,20}", voornaam):
            voornaam = ""
        tekst = TEKST.format(naam=f" {voornaam}" if voornaam else "")
        if dry:
            print(f"--- naar {getattr(u, 'username', None) or u.id}\n{tekst}\n"); continue
        try:
            await c.send_message(u, tekst)
            log[m["invoice"]] = {"status": "verstuurd", "sub": m["sub"], "naam": m["naam"], "tg": u.id, "tijd": time.strftime("%Y-%m-%d %H:%M")}
            print(f"verstuurd: {m['naam']} ({getattr(u, 'username', None) or u.id})")
        except errors.FloodWaitError as e:
            print(f"FloodWait {e.seconds}s"); break
        except errors.PeerFloodError:
            print("STOP: spamlimiet (PeerFlood)"); break
        except Exception as e:
            log[m["invoice"]] = {"status": f"fout: {str(e)[:80]}", "sub": m["sub"], "tijd": time.strftime("%Y-%m-%d %H:%M")}
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if n < len(todo) - 1:
            await asyncio.sleep(random.uniform(30, 60))
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    await c.disconnect()

asyncio.run(main("--dry" in sys.argv))
