# -*- coding: utf-8 -*-
"""Nieuwe casino providers (JSON met Webflow-veldslugs, zie provider-brief) live zetten in de Casino providers-collectie.
Rekent beschikbaarheid + eindscore uit (zelfde formule als de andere providers), pakt logo en top-3-afbeeldingen
van SlotsLaunch, koppelt top-3 aan bestaande slotreviews en maakt de deelafbeelding.

  python provider_publish.py providers.json            # dry-run
  python provider_publish.py providers.json --write    # live aanmaken (bestaande slug: bijwerken) + deelafbeelding
"""
import json, os, re, sys, time
from slot_og import PROVIDERS, SLOTS, _all_items, _env, _wf
import slot_publish

HERE = os.path.dirname(os.path.abspath(__file__))
SL_PROVIDERS = os.path.join(HERE, "state", "sl_providers.json")     # cache van de SlotsLaunch-providerlijst


def _sl_providers():
    if os.path.exists(SL_PROVIDERS):
        return {p["id"]: p for p in json.load(open(SL_PROVIDERS))}
    import urllib.parse, urllib.request
    out, page = [], 1
    while True:
        u = "https://slotslaunch.com/api/providers?" + urllib.parse.urlencode({"token": os.environ["SLOTSLAUNCH_API_KEY"], "per_page": 100, "page": page})
        r = urllib.request.Request(u, headers={"Origin": "https://www.bet-experts.nl", "Referer": "https://www.bet-experts.nl/", "User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(r, timeout=60))
        out += d.get("data", [])
        if page >= d.get("meta", {}).get("last_page", 1):
            break
        page += 1
    json.dump(out, open(SL_PROVIDERS, "w"))
    return {p["id"]: p for p in out}


def num(v): return float(str(v).replace(",", "."))
def f1(v): return f"{v:.1f}".replace(".", ",")
def norm(t): return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def build(x, fields, slp, slots_by_name):
    fd = {k: v for k, v in x.items() if k in fields and v is not None}
    m = re.search(r"(\d+)\s+van\s+(?:de\s+)?(\d+)", fd.get("status-nederland") or "")
    n, tot = (int(m.group(1)), int(m.group(2))) if m else (0, 12)
    besch = round(3 + n / tot * 6.5, 1)
    sc = [num(x["spelaanbod-score"]), num(x["gemiddelde-rtp-score"]), num(x["innovatie-score"]), besch]
    fd["beschikbaarheid-nl-score"], fd["onze-beoordeling"] = f1(besch), f1(round(sum(sc) / 4 + 1e-9, 1))
    pid = x.get("slotslaunch-provider-id") or x.get("slotslaunch_provider_id")
    if pid:
        fd["slotslaunch-provider-id"] = pid
        if not fd.get("logo") and slp.get(pid, {}).get("thumb"):
            fd["logo"] = {"url": slp[pid]["thumb"], "alt": fd["name"] + " logo"}
        slot_publish.sl_game(1, pid)
        games = slot_publish._SL_CACHE.get(pid, {})
    else:
        games = {}
    for i in (1, 2, 3):
        name = fd.get(f"top-slot-{i}")
        fd.pop(f"top-slot-{i}-review", None)
        if norm(name) in slots_by_name:
            fd[f"top-slot-{i}-review"] = slots_by_name[norm(name)]
        g = next((g for g in games.values() if norm(g["name"]) == norm(name)), None)
        if g and g.get("thumb"):
            fd[f"top-slot-{i}-afbeelding"] = {"url": g["thumb"], "alt": name}
    return fd


def main(argv):
    _env()
    rows = [x for f in argv if not f.startswith("--") for x in json.load(open(f))]
    fields = {f["slug"] for f in _wf(f"/collections/{PROVIDERS}")["fields"]}
    slp = _sl_providers()
    slots_by_name = {norm(i["fieldData"]["name"]): i["id"] for i in _all_items(SLOTS)}
    existing = {i["fieldData"]["slug"]: i for i in _all_items(PROVIDERS)}
    done = []
    for x in rows:
        fd = build(x, fields, slp, slots_by_name)
        print(f"{fd['onze-beoordeling']:>4} {fd['name'][:28]:28} logo={'ok' if fd.get('logo') else '-'} "
              f"top3-img={sum(1 for i in (1, 2, 3) if fd.get(f'top-slot-{i}-afbeelding'))} {fd.get('status-nederland')}")
        if "--write" not in argv:
            continue
        for _ in range(5):
            try:
                if fd["slug"] in existing:
                    it = existing[fd["slug"]]
                    for p in ("items", "items/live"):
                        _wf(f"/collections/{PROVIDERS}/{p}", "PATCH", {"items": [{"id": it["id"], "fieldData": fd}]})
                else:
                    _wf(f"/collections/{PROVIDERS}/items/live", "POST", {"items": [{"isDraft": False, "fieldData": fd}]})
                done.append(fd["slug"])
                break
            except RuntimeError as e:                    # externe afbeelding niet te importeren -> weglaten en opnieuw
                m = re.search(r"request to (\S+) failed", str(e))
                if not m:
                    raise
                for k in [k for k, v in fd.items() if isinstance(v, dict) and v.get("url") == m.group(1)]:
                    print(f"   ! afbeelding weggelaten: {k}")
                    fd.pop(k)
                time.sleep(2)
    if done:
        import provider_og
        provider_og.main(done + ["--attach"])


if __name__ == "__main__":
    main(sys.argv[1:])
