# -*- coding: utf-8 -*-
"""Titel, CMS-velddata en Telegram-teaser voor de Oranje Palace Super Odd."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from op_config import OP_AFFILIATE

NL = ZoneInfo("Europe/Amsterdam")
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."

def _fmt(o):
    return ("%.2f" % o) if isinstance(o, (int, float)) else (o or "?")

def phrase(data):
    """Leesbare omschrijving van de boost, bv. 'Thom van Bergen — Scoort of geeft een assist'."""
    sel = (data.get("selection") or "").strip()
    market = (data.get("market") or "").strip()
    base, tail = sel, ""
    for suf in (" - Ja", " - Nee", " - JA", " - NEE"):
        if sel.endswith(suf):
            base = sel[: -len(suf)]
            tail = "" if "ja" in suf.lower() else " (nee)"
            break
    if market and base and base.lower() not in market.lower():
        return f"{base} — {market}{tail}"
    return (market or sel) + tail

def build_title(data):
    return f"Oranje Palace Lucky's Boost: {phrase(data)} @ {_fmt(data.get('new_odd'))}"

def signature(data):
    return "|".join(str(x) for x in (data.get("event"), data.get("selection"),
                                     data.get("old_odd"), data.get("new_odd")))

def build_fielddata(data, now=None):
    now = now or datetime.now(NL)
    old, new = _fmt(data.get("old_odd")), _fmt(data.get("new_odd"))
    ev = data.get("event") or ""
    ph = phrase(data)
    maxs = data.get("max_stake")
    maxs_fmt = maxs.rstrip("0").rstrip(".") if maxs else None    # '14.00' -> '14'
    sub = f"{ev} · verhoogd van {old} naar {new}" + (f" · max. inzet €{maxs_fmt}" if maxs_fmt else "")
    body = (f"<h3><strong>De Oranje Palace Lucky's Boost van vandaag</strong></h3>"
            f"<p>Vandaag verhoogt Oranje Palace met de dagelijkse Lucky's Boost de quotering op "
            f"<strong>{ph}</strong>{(' bij ' + ev) if ev else ''} van {old} naar <strong>{new}</strong>."
            + (f" Je kunt maximaal €{maxs_fmt} inzetten;" if maxs_fmt else "")
            + " de boost verloopt rond de aftrap.</p>")
    voorwaarde = (
        f"Dagelijkse Lucky's Boost van Oranje Palace: de quotering op {ph}"
        f"{(' bij ' + ev) if ev else ''} is verhoogd van {old} naar {new}."
        + (f" Max. inzet €{maxs_fmt}." if maxs_fmt else "")
        + " Boosts wisselen dagelijks en zijn kort geldig (tot de aftrap); controleer de actuele"
          " boost op oranjepalace.nl. Alleen voor spelers van 24 jaar of ouder."
          " Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust.")
    fd = {
        "name": build_title(data),
        "subtitel": sub,
        "informatie": f"Oranje Palace Lucky's Boost: {ev}" if ev else "Oranje Palace Lucky's Boost",
        "bonus-tekst": f"{old} → {new}",
        "bedrag-of-boost": f"Lucky's Boost {old} → {new}",
        "soort-welkomstbonus": "Lucky's Boost (verhoogde quotering)",
        "minimale-storting": "Geen",
        "odds-om-vrij-te-spelen": new,
        "rondspeelvoorwaarden": "Geen",
        "leeftijd": "24 jaar of ouder",
        "check-1": f"Lucky's Boost: {old} → {new}",
        "check-2": ph,
        "check-3": (f"Max. inzet €{maxs_fmt}" if maxs_fmt else "Wisselt elke dag"),
        "button-1": "Bekijk de Lucky's Boost bij Oranje Palace",
        "affiliatie-link-naar-broker": OP_AFFILIATE,
        "voorwaarde-promotie": voorwaarde,
        "content-informatie-promotie-2": body,
        "boosted-odd": True,
        "stap-1-titel": "Open Oranje Palace",
        "stap-1-tekst": "Ga naar Oranje Palace en log in of maak een account aan (24+).",
        "stap-2-titel": "Zoek de Lucky's Boost",
        "stap-2-tekst": (f"De Lucky's Boost van vandaag staat op {ev} — {ph}, quotering {new}."
                         if ev else f"De Lucky's Boost van vandaag: {ph}, quotering {new}."),
        "stap-3-titel": "Plaats je weddenschap",
        "stap-3-tekst": ("Voeg de Lucky's Boost toe aan je bonnetje en bevestig je inzet zolang de "
                         "boost geldig is" + (f" (max. inzet €{maxs_fmt})." if maxs_fmt else ".")),
    }
    # 'Geldig tot' = einde van de wedstrijddag (gebruiker, 24-09-2026). Aftrap onbekend -> leeg.
    fd["wanneer-toegevoegd"] = geldig_tot(data.get("kickoff"))
    return fd

def geldig_tot(kickoff_iso):
    """ISO-aftrap -> 23:59 lokale tijd op de wedstrijddag (of None als onbekend)."""
    if not kickoff_iso:
        return None
    try:
        ko = datetime.fromisoformat(str(kickoff_iso).replace("Z", "+00:00")).astimezone(NL)
    except ValueError:
        return None
    return ko.replace(hour=23, minute=59, second=0, microsecond=0).isoformat()

def telegram_caption(data, promo_url):
    """Zelfde opbouw als de Bet365 Super Odd-post: wél de wedstrijd + de odd-boost,
    NIET wat er geboost is (dat lezen ze in het artikel)."""
    ev = (data.get("event") or "").strip()
    old, new = data.get("old_odd"), data.get("new_odd")
    lines = ["🧡 <b>Oranje Palace Lucky's Boost LIVE!</b> 👑", ""]
    if ev:
        lines.append(f"⚽ <b>{ev}</b>")
    lines += [f"📈 Quotering geboost: <s>{_fmt(old)}</s> → <b>{_fmt(new)}</b>", "", f"<i>{DISCLAIMER}</i>"]
    return "\n".join(lines)
