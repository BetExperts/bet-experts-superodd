# -*- coding: utf-8 -*-
"""Titel, CMS-velddata en Telegram-teaser voor de 888Sport 60x-actie.

Tot de kickoff noemen we de wedstrijd + markt; zodra de wedstrijd live gaat
(nu >= kickoff) schakelen we naar de ALGEMENE variant zonder teamnamen (KSA)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NL = ZoneInfo("Europe/Amsterdam")
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."

def is_live(data, now=None):
    now = now or datetime.now(NL)
    return bool(data.get("kickoff")) and now >= data["kickoff"]

def signature(data):
    return f'{data.get("home")}|{data.get("away")}|{data.get("date")}'

def build_fields(data, now=None):
    now = now or datetime.now(NL)
    live = is_live(data, now)
    home, away, market = data.get("home"), data.get("away"), data.get("market")
    if live:
        fd = {
            "name": "🔥 888sport: Pak 60x je inzet!",
            "subtitel": "Zet €1 in en pak 60x je inzet met de 888sport welkomstboost.",
            "informatie": "888sport: pak 60x je inzet",
            "wedstrijd-datum-tijd": "",          # namen/tijd weg zodra live
            "bedrag-of-boost": "60x je inzet",
        }
    else:
        fd = {
            "name": f"🔥 888sport: Pak 60x je inzet op '{market}' bij {home} – {away}!",
            "subtitel": f"Zet €1 op '{market}' bij {home} – {away} en pak 60x je inzet.",
            "informatie": f"888sport 60x je inzet: {home} – {away}",
            "wedstrijd-datum-tijd": data.get("datetime_text", ""),
            "bedrag-of-boost": "60x je inzet",
        }
        ko = data.get("kickoff")
        if ko:
            fd["wanneer-toegevoegd"] = ko.astimezone(timezone.utc).isoformat()  # geldig tot = kickoff
    return fd, live

def telegram_caption(data):
    home, away, market = data.get("home"), data.get("away"), data.get("market")
    return (
        "🔥 <b>888sport 60x je inzet!</b> ⚽\n"
        f"NIEUW: zet <b>€1</b> op '{market}' bij <b>{home} – {away}</b> en pak <b>60x je inzet</b>! 💸\n"
        "✅ Nieuw bij 888sport · max. €1 inzet · winst 10x rondspelen\n\n"
        f"<i>{DISCLAIMER}</i>"
    )
