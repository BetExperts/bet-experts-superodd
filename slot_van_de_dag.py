# -*- coding: utf-8 -*-
"""Slot van de dag in het Telegram-kanaal Bet Experts Casino (@betexpertscasino).

Kandidaten: live slots met 'Status NL' = Beschikbaar in NL en een deelafbeelding. Willekeurig, maar een slot pas
opnieuw als alle andere geweest zijn, en nooit twee dagen achter elkaar dezelfde provider.

  python3 slot_van_de_dag.py --dry
  python3 slot_van_de_dag.py --post --vanaf 19      # max. 1x per dag, niet vóór 19:00 NL-tijd (GitHub Actions)
  python3 slot_van_de_dag.py --post --test
"""
import argparse, json, os, random, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from slot_og import SLOTS, PROVIDERS, _all_items, _env, _wf
import casino_telegram as T

NL = ZoneInfo("Europe/Amsterdam")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state", "slot_van_de_dag.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--post", action="store_true")
    ap.add_argument("--test", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--vanaf", type=int, default=9)
    a = ap.parse_args()
    _env()
    now = datetime.now(NL)
    today = f"{now:%Y-%m-%d}"
    print(f"== Slot van de dag — {now:%Y-%m-%d %H:%M} ==")
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    if a.post and not a.test and not a.force:
        if st.get("datum") == today:
            print("  · Vandaag al gepost."); return
        if not (a.vanaf <= now.hour < 22):
            print(f"  · Buiten posttijden ({now:%H:%M})."); return
    opt = {o["name"]: o["id"] for f in _wf(f"/collections/{SLOTS}")["fields"] if f["slug"] == "status-nl"
           for o in f["validations"]["options"]}
    provs = {p["id"]: p["fieldData"] for p in _all_items(PROVIDERS)}
    items = [i for i in _all_items(SLOTS) if i.get("lastPublished") and not i.get("isDraft")
             and i["fieldData"].get("status-nl") == opt.get("Beschikbaar in NL")
             and (i["fieldData"].get("deelafbeelding") or {}).get("url")]
    if not items:
        print("  ! Geen kandidaten."); return
    gehad = [s for s in st.get("gehad", []) if s in {i["fieldData"]["slug"] for i in items}]
    pool = [i for i in items if i["fieldData"]["slug"] not in gehad] or items
    if len(pool) == len(items):
        gehad = []
    last_prov = st.get("laatste_provider")
    pool = [i for i in pool if i["fieldData"].get("provider") != last_prov] or pool
    it = random.choice(pool)
    fd = it["fieldData"]
    pf = provs.get(fd.get("provider")) or {}
    print(f"  Gekozen: {fd['name']} ({pf.get('name')}) — {len(gehad) + 1}/{len(items)} deze ronde\n")
    print(T.slot_caption(fd, pf.get("name"), "dag"))
    if a.dry or not a.post:
        return
    if T.post_slot(it, "dag", pf.get("name"), pf.get("slug"), test=a.test) and not a.test:
        print("  ✔ Telegram verstuurd.")
        st.update({"datum": today, "gehad": gehad + [fd["slug"]], "laatste_provider": fd.get("provider")})
        st.setdefault("historie", []).append({"datum": today, "slot": fd["slug"]})
        st["historie"] = st["historie"][-90:]
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
