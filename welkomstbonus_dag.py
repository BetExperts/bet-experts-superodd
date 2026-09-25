# -*- coding: utf-8 -*-
"""Welkomstbonus van de dag: elke dag één sport-welkomstbonus uitlichten in Telegram.

Bron: de live sport-welkomstbonussen in de Promoties-CMS ('<Bookmaker>: Sport Welkomstbonus | ...').
Willekeurige keuze, maar pas een bookmaker herhalen als alle bookmakers een keer geweest zijn
(en nooit twee dagen achter elkaar dezelfde). Knoppen: onze welkomstbonus-review + bookmaker-review.

  python3 welkomstbonus_dag.py --dry        # laat zien wat er gepost zou worden
  python3 welkomstbonus_dag.py --post       # posten (max. 1x per dag)
  python3 welkomstbonus_dag.py --post --test  # naar de testchat
"""
import os, sys, json, time, html, random, socket, argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT
import pr_config as C

NL = ZoneInfo("Europe/Amsterdam")
STATE = "state/welkomstbonus_dag.json"
POST_UREN = range(9, 22)          # na het wakker worden van de Mac niet 's nachts nog posten
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."

def H():
    return {"Authorization": f"Bearer {WEBFLOW_TOKEN}", "accept": "application/json"}

def all_items(coll):
    out, off = [], 0
    while True:
        r = requests.get(f"{WF_API}/collections/{coll}/items", headers=H(), params={"limit": 100, "offset": off}, timeout=60)
        r.raise_for_status()
        items = r.json().get("items", [])
        out += items
        if len(items) < 100:
            return out
        off += 100

def kandidaten():
    books = {b["id"]: b["fieldData"] for b in all_items(C.BOOKMAKERS_COLL)}
    out = []
    for it in all_items(C.PROMOTIES):
        f = it["fieldData"]
        if it.get("isDraft") or it.get("isArchived") or not it.get("lastPublished"):
            continue
        if not f.get("welkomstbonus-promotie") or f.get("geldig-voor") != C.GELDIG_SPORT:
            continue
        if "sport welkomstbonus" not in (f.get("name") or "").lower():
            continue      # geen 100x-acties, no-deposit of seizoenkaart: alleen de echte sport-welkomstbonus
        b = books.get(f.get("bookmaker-3")) or {}
        out.append({"slug": f["slug"], "book_id": f.get("bookmaker-3"), "book": f["name"].split(":")[0].strip() if ":" in f["name"] else b.get("name"),
                    "review": b.get("review-pagina"), "f": f})
    return out

def kies(cands, st):
    per_book = {}
    for c in cands:
        per_book.setdefault(c["book_id"], []).append(c)
    gehad = [b for b in st.get("gehad", []) if b in per_book]
    open_ = [b for b in per_book if b not in gehad]
    if not open_:                                   # ronde klaar -> nieuwe ronde
        gehad, open_ = [], list(per_book)
    if len(open_) > 1 and st.get("laatste_book") in open_:
        open_.remove(st["laatste_book"])            # nooit twee dagen achter elkaar dezelfde bookmaker
    book = random.choice(open_)
    opties = per_book[book]
    if len(opties) > 1:
        opties = [c for c in opties if c["slug"] != st.get("laatste_slug", {}).get(book)] or opties
    return random.choice(opties), gehad + [book]

def caption(c):
    f = {k: html.escape(v, quote=False) if isinstance(v, str) else v for k, v in c["f"].items()}
    bonus = f["name"].split("|", 1)[1].strip() if "|" in f["name"] else (f.get("bonus-tekst") or "")
    lines = [f"🎁 <b>Welkomstbonus van de dag: {html.escape(c['book'])}</b>", "", f"⚽ <b>{bonus}</b>"]
    if f.get("subtitel"):
        lines.append(f.get("subtitel"))
    checks = [f.get(k) for k in ("check-1", "check-2", "check-3") if f.get(k)]
    if checks:
        lines += [""] + [f"✅ {x}" for x in checks]
    extra = []
    if f.get("minimale-storting") and f["minimale-storting"].lower() not in ("geen", "-"):
        extra.append(f"💶 Min. storting/inzet: {f['minimale-storting'].replace('Inzet vanaf ', '')}")
    extra.append("🔞 Alleen voor nieuwe spelers van 24+")
    lines += [""] + extra + ["", "👇 Lees in onze review hoe je de bonus claimt en waar je op moet letten.", "", f"<i>{DISCLAIMER}</i>"]
    return "\n".join(lines)

def send(text, c, test=False):
    chat = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if not TELEGRAM_BOT_TOKEN or not chat:
        print("  · Telegram overgeslagen (token/chat ontbreekt)."); return False
    kb = [[{"text": "📖 Lees de welkomstbonus review →", "url": PROMO_BASE + c["slug"]}]]
    if c.get("review"):
        kb.append([{"text": f"⭐ {c['book']} review", "url": c["review"]}])
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", timeout=30, data={
        "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False,
        "link_preview_options": json.dumps({"url": PROMO_BASE + c["slug"], "prefer_large_media": True}),
        "reply_markup": json.dumps({"inline_keyboard": kb})})
    r.raise_for_status(); return True

def wacht_op_netwerk():
    for _ in range(10):
        try:
            socket.gethostbyname("api.webflow.com"); return True
        except OSError:
            time.sleep(30)
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--post", action="store_true")
    ap.add_argument("--test", action="store_true"); ap.add_argument("--force", action="store_true", help="ook als er vandaag al gepost is")
    ap.add_argument("--vanaf", type=int, default=POST_UREN.start, help="niet posten vóór dit uur (NL-tijd); GitHub-cron draait in UTC")
    a = ap.parse_args()
    now = datetime.now(NL)
    print(f"== Welkomstbonus van de dag — {now:%Y-%m-%d %H:%M} ==")
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    today = f"{now:%Y-%m-%d}"
    if a.post and not a.test and not a.force:
        if st.get("datum") == today:
            print("  · Vandaag al gepost."); return
        if now.hour < a.vanaf or now.hour not in POST_UREN:
            print(f"  · Buiten posttijden ({now:%H:%M}) — morgen weer."); return
    if not wacht_op_netwerk():
        print("  ! Geen netwerk — overgeslagen."); sys.exit(2)
    cands = kandidaten()
    if not cands:
        print("  ! Geen sport-welkomstbonussen gevonden."); return
    c, gehad = kies(cands, st)
    text = caption(c)
    print(f"  Gekozen: {c['book']} — {c['slug']}  ({len(gehad)}/{len({x['book_id'] for x in cands})} bookmakers deze ronde)\n")
    print(text)
    if a.dry or not a.post:
        return
    if send(text, c, test=a.test):
        print("  ✔ Telegram verstuurd.")
        if not a.test:
            st.update({"datum": today, "gehad": gehad, "laatste_book": c["book_id"],
                       "laatste_slug": {**st.get("laatste_slug", {}), c["book_id"]: c["slug"]}})
            st.setdefault("historie", []).append({"datum": today, "book": c["book"], "slug": c["slug"]})
            st["historie"] = st["historie"][-60:]
            os.makedirs("state", exist_ok=True)
            json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
