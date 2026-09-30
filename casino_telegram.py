# -*- coding: utf-8 -*-
"""Posts voor het Telegram-kanaal Bet Experts Casino (@betexpertscasino): slots en casino-promo's.

  post_slot(item, soort)   soort = "dag" (slot van de dag) | "nieuw" (nieuwe release) | "live_nl" (nu speelbaar in NL)
  post_promo(item)         nieuwe casino-promo/toernooi uit de promo-radar
Dubbele posts worden voorkomen via state/casino_telegram.json. Alleen Webflow API + Telegram: draait overal.
"""
import html, json, os, re
from datetime import date
import requests
from so_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CASINO_CHANNEL, TELEGRAM_TEST_CHAT

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state", "casino_telegram.json")
SITE = "https://www.bet-experts.nl"
SLOGAN = "Wat kost gokken jou? Stop op tijd. 18+"
MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()
STATUS_NAMEN = {}      # option-id -> naam ('Status NL'), gevuld door de aanroeper of lazy via Webflow


def _state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {"posted": {}}


def _save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def al_gepost(key, soort):
    return soort in _state()["posted"].get(key, [])


def _markeer(key, soort):
    st = _state()
    st["posted"].setdefault(key, [])
    if soort not in st["posted"][key]:
        st["posted"][key].append(soort)
    _save(st)


def datum_nl(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def _send(method, data, test=False):
    chat = TELEGRAM_TEST_CHAT if test else TELEGRAM_CASINO_CHANNEL
    if not TELEGRAM_BOT_TOKEN or not chat:
        print("  · Telegram overgeslagen (token/chat ontbreekt).")
        return False
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", data={"chat_id": chat, **data}, timeout=60)
    if not r.ok:
        print(f"  ! Telegram {method}: {r.status_code} {r.text[:200]}")
    return r.ok


def _status(fd):
    if not STATUS_NAMEN and fd.get("status-nl"):
        from slot_og import _wf, SLOTS
        for f in _wf(f"/collections/{SLOTS}")["fields"]:
            if f["slug"] == "status-nl":
                STATUS_NAMEN.update({o["id"]: o["name"] for o in f["validations"]["options"]})
    return STATUS_NAMEN.get(fd.get("status-nl"))


def slot_caption(fd, provider, soort):
    e = lambda s: html.escape(str(s), quote=False)
    naam = e(fd["name"])
    kop = {"dag": f"🎰 <b>Slot van de dag: {naam}</b>",
           "nieuw": f"🆕 <b>Nieuwe slot: {naam}</b>",
           "live_nl": f"🇳🇱 <b>Nu speelbaar in Nederland: {naam}</b>"}[soort]
    lines = [kop]
    if provider:
        lines.append(f"<i>{e(provider)}</i>")
    if fd.get("deelregel"):
        lines += ["", e(fd["deelregel"])]
    specs = [x for x in (f"RTP {fd['rtp']}" if fd.get("rtp") else None, fd.get("volatiliteit"),
                         f"max. {fd['max-winst']}" if fd.get("max-winst") and len(fd["max-winst"]) < 20 else None) if x]
    if specs:
        lines += ["", "📊 " + " · ".join(e(x) for x in specs)]
    st = _status(fd)
    if soort == "nieuw":
        if fd.get("releasedatum"):
            lines.append(f"📅 Release: {datum_nl(fd['releasedatum'])}")
        if st == "Beschikbaar in NL":
            lines.append("✅ Al speelbaar bij Nederlandse casino's met een KSA-vergunning")
        elif st == "Binnenkort in NL" and fd.get("live-in-nl"):
            lines.append(f"⏳ Verwacht in Nederland vanaf {datum_nl(fd['live-in-nl'])}")
        else:
            lines.append("⏳ Nog niet bij Nederlandse casino's; wij houden het in de gaten")
    elif soort == "live_nl":
        lines.append("✅ Vanaf vandaag te spelen bij Nederlandse casino's met een KSA-vergunning")
    if fd.get("onze-beoordeling"):
        lines += ["", f"⭐ Onze beoordeling: <b>{e(fd['onze-beoordeling'])}/10</b>"]
    demo = bool(fd.get("slotslaunch-game-id"))
    lines += ["", "👇 " + ("Lees de review en speel de gratis demo." if demo else "Lees de volledige review."), "", f"<i>{SLOGAN}</i>"]
    return "\n".join(lines)


def post_slot(item, soort, provider=None, provider_slug=None, test=False):
    fd = item["fieldData"]
    key = "slot:" + fd["slug"]
    if soort != "dag" and not test and al_gepost(key, soort):
        return False
    url = f"{SITE}/slots/{fd['slug']}"
    kb = [[{"text": "📖 Review & gratis demo →" if fd.get("slotslaunch-game-id") else "📖 Lees de review →", "url": url}]]
    if provider_slug:
        kb.append([{"text": f"🏢 Meer van {provider}", "url": f"{SITE}/casino-providers/{provider_slug}"}])
    img = (fd.get("deelafbeelding") or {}).get("url")
    cap = slot_caption(fd, provider, soort)
    data = {"caption": cap, "parse_mode": "HTML", "reply_markup": json.dumps({"inline_keyboard": kb})}
    ok = _send("sendPhoto", {**data, "photo": img}, test) if img else \
        _send("sendMessage", {"text": cap, "parse_mode": "HTML", "reply_markup": data["reply_markup"]}, test)
    if ok and not test and soort != "dag":
        _markeer(key, soort)
    return ok


def post_promo(item, bookmaker=None, test=False):
    """Nieuwe casino-promo (toernooi, cash drop e.d.) uit de promo-radar."""
    fd = item["fieldData"]
    key = "promo:" + fd["slug"]
    if not test and al_gepost(key, "nieuw"):
        return False
    e = lambda s: html.escape(str(s), quote=False)
    titel = fd["name"].split("|", 1)[-1].strip() if bookmaker and "|" in fd["name"] else fd["name"]
    lines = [f"🏆 <b>{e(bookmaker + ': ' if bookmaker else '')}{e(titel)}</b>"]
    if fd.get("subtitel"):
        lines += ["", e(fd["subtitel"])]
    if fd.get("wanneer-toegevoegd"):
        lines.append(f"📅 Geldig t/m {datum_nl(fd['wanneer-toegevoegd'])}")
    lines += ["", "👇 Lees hoe het werkt en wat de voorwaarden zijn.", "", f"<i>{SLOGAN}</i>"]
    kb = [[{"text": "🎁 Bekijk de actie →", "url": f"{SITE}/promoties/{fd['slug']}"}]]
    ok = _send("sendMessage", {"text": "\n".join(lines), "parse_mode": "HTML", "disable_web_page_preview": False,
                               "link_preview_options": json.dumps({"url": f"{SITE}/promoties/{fd['slug']}", "prefer_large_media": True}),
                               "reply_markup": json.dumps({"inline_keyboard": kb})}, test)
    if ok and not test:
        _markeer(key, "nieuw")
    return ok
