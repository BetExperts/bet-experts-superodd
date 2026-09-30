# -*- coding: utf-8 -*-
"""Slotreviews (JSON volgens slot_brief) in de Webflow Slots-collectie zetten: velden, scores, casino's,
vergelijkbare slots, SlotsLaunch-demo en -afbeelding. Daarna de deelafbeelding via slot_og.

  python slot_publish.py reviews.json [meer.json ...]            # dry-run: toont wat er gebeurt
  python slot_publish.py reviews.json --write                    # aanmaken als draft (bestaande slug: bijwerken)
  python slot_publish.py reviews.json --write --publish          # direct live

Verwacht per review o.a.: naam, slug, provider (naam), slotslaunch_id, seo_titel, meta_omschrijving, intro, rtp,
rtp_versies, volatiliteit, max_winst, raster, winlijnen, inzet, releasedatum, review_html, bonusfuncties_html,
pluspunten, minpunten, faq[5], vergelijkbare_slots, deelregel, nl_casinos, rank (populariteit, 1-50).
"""
import datetime as dt, html, json, os, re, sys, urllib.parse, urllib.request
from slot_og import PROVIDERS, SLOTS, _all_items, _env, _wf

BOOKMAKERS = "64ff0fbd5a8f205b05d54686"
CASINO_ALIAS = {"toto": "Toto", "jacks": "JACKS.NL", "jacks.nl": "JACKS.NL", "711": "711", "betmgm": "BetMGM",
                "leovegas": "LeoVegas", "unibet": "Unibet", "circus": "Circus", "bingoal": "Bingoal", "tonybet": "Tonybet"}


# ---------- score (zelfde formule als de eerste 50 slots) ----------

def _num(s):
    m = re.search(r"(\d+(?:[.,]\d+)?)", (s or "").replace(".", "").replace(",", ".")) if s and "%" not in s \
        else re.search(r"(\d+(?:[.,]\d+)?)", (s or "").replace(",", "."))
    return float(m.group(1)) if m else None


def _rtp_range(r):
    v = [float(x.replace(",", ".")) for x in re.findall(r"(\d{2}[,.]\d{1,2})", (r.get("rtp") or "") + " " + (r.get("rtp_versies") or ""))]
    if not v:
        m = re.search(r"(\d{2})", r.get("rtp") or "")
        v = [float(m.group(1))] if m else []
    return (max(v), min(v)) if v else (None, None)


def _maxwin(r):
    s = (r.get("max_winst") or "").lower()
    return _num(s.split("x")[0]) if "x" in s else None


def score(r):
    """-> dict met onze-beoordeling, gameplay-score, bonusronde-score, uitbetaling-score, beoordeling-schema."""
    bf = r.get("bonusfuncties_html") or ""
    low = ((r.get("review_html") or "") + bf).lower()
    n = len(re.findall(r"<h3>", bf))
    hi, lo = _rtp_range(r)
    mw, vol, rank = _maxwin(r), (r.get("volatiliteit") or "").lower(), r.get("rank") or 30
    pay = 6.0 if hi is None else (6.5 if hi < 94 else 7.0 if hi < 95 else 7.4 if hi < 95.8 else 7.9 if hi < 96.3 else 8.3 if hi < 96.7 else 8.7 if hi < 97.5 else 9.2)
    pay += 0 if mw is None else (0.0 if mw < 1000 else 0.3 if mw < 5000 else 0.5 if mw < 10000 else 0.7 if mw < 50000 else 0.9)
    if lo is not None and hi is not None and lo < hi:
        pay -= 0.4 if lo < 90 else 0.2
    bon = 6.3 + 0.35 * min(n, 6)
    if re.search(r"multiplier|vermenigvuldig", low): bon += 0.3
    if re.search(r"free spins|gratis spins|freespins|bonusronde", low): bon += 0.2
    if re.search(r"bonus ?buy|bonus kopen|koop de bonus|feature buy", low): bon += 0.1
    gp = 7.0 + 0.12 * min(n, 6)
    if re.search(r"cascade|tumble|avalanche|cluster|megaways|collect|verdwijn|vallen|raster groeit|uitbreid", low): gp += 0.5
    gp += 0.5 if rank <= 10 else 0.3 if rank <= 25 else 0.15
    if "zeer hoog" in vol: gp -= 0.1
    clamp = lambda x: max(5.5, min(9.6, x))
    pay, bon, gp = clamp(pay), clamp(bon), clamp(gp)
    pop = 0.3 if rank <= 10 else 0.15 if rank <= 25 else 0.0
    tot = max(5.5, min(9.5, 0.35 * gp + 0.35 * bon + 0.30 * pay + pop))
    f = lambda x: f"{x:.1f}".replace(".", ",")
    return {"onze-beoordeling": f(tot), "gameplay-score": f(gp), "bonusronde-score": f(bon), "uitbetaling-score": f(pay),
            "beoordeling-schema": f"{tot:.1f}"}


# ---------- SlotsLaunch ----------

_SL_CACHE = {}


def sl_game(game_id, sl_provider_id):
    """Game-info (thumb) via de SlotsLaunch-lijst van de provider (er is geen endpoint per game).
    API vereist Origin/Referer bet-experts.nl."""
    key = os.environ.get("SLOTSLAUNCH_API_KEY")
    if not key or not game_id or not sl_provider_id:
        return None
    if sl_provider_id not in _SL_CACHE:
        games, page = {}, 1
        while True:
            u = "https://slotslaunch.com/api/games?" + urllib.parse.urlencode(
                {"token": key, "provider[]": sl_provider_id, "per_page": 100, "page": page})
            req = urllib.request.Request(u, headers={"Origin": "https://www.bet-experts.nl",
                                                     "Referer": "https://www.bet-experts.nl/", "User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    d = json.load(r)
            except Exception as ex:
                print(f"   ! SlotsLaunch provider {sl_provider_id}: {ex}")
                break
            games.update({g["id"]: g for g in d.get("data", [])})
            if page >= d.get("meta", {}).get("last_page", 1):
                break
            page += 1
        _SL_CACHE[sl_provider_id] = games
    return _SL_CACHE[sl_provider_id].get(int(game_id))


# ---------- velden ----------

def _ul(items):
    return "<ul>" + "".join(f"<li>{html.escape(x, quote=False)}</li>" for x in items or []) + "</ul>"


def field_data(r, provider_id, casino_ids, thumb):
    fd = {"name": r["naam"], "slug": r["slug"], "seo-titel": r.get("seo_titel"), "meta-omschrijving": r.get("meta_omschrijving"),
          "provider": provider_id, "intro": r.get("intro"), "slotslaunch-game-id": r.get("slotslaunch_id"),
          "rtp": r.get("rtp"), "rtp-versies": r.get("rtp_versies"), "volatiliteit": r.get("volatiliteit"),
          "max-winst": r.get("max_winst"), "raster": r.get("raster"), "winlijnen": r.get("winlijnen"), "inzet": r.get("inzet"),
          "review": r.get("review_html"), "bonusfuncties": r.get("bonusfuncties_html"),
          "pluspunten": _ul(r.get("pluspunten")), "minpunten": _ul(r.get("minpunten")),
          "casino-s": casino_ids, "deelregel": r.get("deelregel"),
          "laatst-bijgewerkt": dt.date.today().isoformat() + "T00:00:00.000Z"}
    if r.get("releasedatum") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["releasedatum"]):
        fd["releasedatum"] = r["releasedatum"] + "T00:00:00.000Z"
    for i, q in enumerate((r.get("faq") or [])[:5], 1):
        fd[f"faq-{i}-vraag"], fd[f"faq-{i}-antwoord"] = q.get("vraag"), q.get("antwoord")
    if thumb:
        fd["afbeelding"] = {"url": thumb, "alt": r["naam"]}
    fd.update(score(r))
    return {k: v for k, v in fd.items() if v is not None}


def main(argv):
    _env()
    files = [a for a in argv if not a.startswith("--")]
    reviews = [x for f in files for x in json.load(open(f))]
    prov_items = _all_items(PROVIDERS)
    provs = {p["fieldData"]["name"].lower(): p["id"] for p in prov_items}
    prov_sl = {p["id"]: p["fieldData"].get("slotslaunch-provider-id") for p in prov_items}
    books = {b["fieldData"]["name"]: b["id"] for b in _all_items(BOOKMAKERS) if not b.get("isDraft") and not b.get("isArchived")}
    existing = {i["fieldData"]["slug"]: i for i in _all_items(SLOTS)}
    rows_new, rows_upd = [], []
    for r in reviews:
        pid = provs.get((r.get("provider") or "").lower())
        cas = sorted({books[CASINO_ALIAS.get(c.lower(), c)] for c in r.get("nl_casinos") or []
                      if CASINO_ALIAS.get(c.lower(), c) in books})          # alleen live bookmakers
        g = sl_game(r.get("slotslaunch_id"), prov_sl.get(pid))
        fd = field_data(r, pid, cas, (g or {}).get("thumb"))
        print(f"{fd['onze-beoordeling']:>4} {r['naam'][:32]:32} provider={'ok' if pid else '??'} casino's={len(cas)} "
              f"demo={r.get('slotslaunch_id')} img={'ok' if fd.get('afbeelding') else '-'} woorden={len(re.sub('<[^>]+>', ' ', fd.get('review', '')).split())}")
        (rows_upd if r["slug"] in existing else rows_new).append(
            {"id": existing[r["slug"]]["id"], "fieldData": fd} if r["slug"] in existing else {"isDraft": "--publish" not in argv, "fieldData": fd})
    if "--write" not in argv:
        return
    live = "--publish" in argv
    for i in range(0, len(rows_new), 25):
        path = f"/collections/{SLOTS}/items" + ("/live" if live else "")
        print("POST", _wf(path, "POST", {"items": rows_new[i:i + 25]}))
    for i in range(0, len(rows_upd), 25):
        print("PATCH", _wf(f"/collections/{SLOTS}/items", "PATCH", {"items": rows_upd[i:i + 25]}))
    # vergelijkbare slots pas nu (nieuwe items hebben dan een id)
    items = _all_items(SLOTS)
    by_name = {i["fieldData"]["name"].lower(): i["id"] for i in items}
    by_slug = {i["fieldData"]["slug"]: i for i in items}
    sim = []
    for r in reviews:
        ids = [by_name[n.lower()] for n in r.get("vergelijkbare_slots") or [] if n.lower() in by_name and n.lower() != r["naam"].lower()][:4]
        if ids and r["slug"] in by_slug:
            sim.append({"id": by_slug[r["slug"]]["id"], "fieldData": {"vergelijkbare-slots": ids}})
    for i in range(0, len(sim), 25):
        print("PATCH vergelijkbaar", _wf(f"/collections/{SLOTS}/items", "PATCH", {"items": sim[i:i + 25]}))


if __name__ == "__main__":
    main(sys.argv[1:])
