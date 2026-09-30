# -*- coding: utf-8 -*-
"""Dagelijkse NL-check voor slots: staat een (nieuwe) slot al bij Nederlandse KSA-casino's?

Voor elke slot met 'Status NL' anders dan 'Beschikbaar in NL' (of met --all: elke slot) wordt bij de
casino's gekeken of er een spelpagina is (200 + de naam in de titel; niet gevonden = 404). Bij een treffer:
  - casino's toevoegen aan 'casino-s' (alleen live bookmakers),
  - 'Status NL' -> 'Beschikbaar in NL', 'Live in NL' -> vandaag (als die nog niet in het verleden lag),
  - FAQ 5 ('Is <naam> beschikbaar in Nederland?') opnieuw schrijven,
  - item live bijwerken als het gepubliceerd is, en de deelafbeelding opnieuw maken.
Zonder treffer: status 'Binnenkort in NL' (als 'Live in NL' in de toekomst ligt) of 'Nog niet in NL'.

  python slot_nl_check.py            # dry-run
  python slot_nl_check.py --write    # bijwerken (LaunchAgent: dagelijks)
  python slot_nl_check.py --write --all   # ook casinolijsten van al beschikbare slots aanvullen
"""
import datetime as dt, html, json, os, re, sys, time, unicodedata, urllib.request
from slot_og import SLOTS, PROVIDERS, _all_items, _env, _wf

HERE = os.path.dirname(os.path.abspath(__file__))
BOOKMAKERS = "64ff0fbd5a8f205b05d54686"
ALIASES = os.path.join(HERE, "state", "slot_nl_aliases.json")   # slug -> extra URL-slugs (bv. officiële naam)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "nl-NL,nl;q=0.9"}
STATUS = {"ja": "Beschikbaar in NL", "binnenkort": "Binnenkort in NL", "nee": "Nog niet in NL"}
MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()

# casino (naam zoals in de Bookmakers-collectie) -> URL-sjablonen
CASINOS = {
    "Unibet": ["https://www.unibet.nl/play/{s}"],
    "LeoVegas": ["https://www.leovegas.nl/game/{s}"],
    "BetMGM": ["https://www.betmgm.nl/casino/slots/{s}"],
    "Toto": ["https://casino.toto.nl/casino/games/{s}", "https://casino.toto.nl/casino/games/{s}-{p}"],
    "JACKS.NL": ["https://jacks.nl/casino/slots/{s}"],
    "711": ["https://www.711.nl/casino/{p}/{s}", "https://www.711.nl/casino/{p711}/{s}"],
}
P711 = {"elk-studios": "elk", "print-studios": "silver-bullet"}   # 711 gebruikt soms een andere providermap


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("&", "and")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.replace("'", ""))).strip("-")


def datum_nl(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def _probe(url, name):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            body = r.read(400000).decode("utf-8", "replace")
            final = r.geturl()
    except Exception:
        return False
    t = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    title = slugify(html.unescape(t.group(1))) if t else ""
    core = "-".join(slugify(name).split("-")[:2])            # eerste twee woorden van de naam
    return bool(core) and core in title and slugify(name).split("-")[0] in final.lower()


def find_casinos(item, prov_slug):
    fd = item["fieldData"]
    aliases = json.load(open(ALIASES)).get(fd["slug"], []) if os.path.exists(ALIASES) else []
    slugs = list(dict.fromkeys([fd["slug"], slugify(fd["name"])] + aliases))
    found = {}
    for casino, templates in CASINOS.items():
        for tpl in templates:
            for s in slugs:
                url = tpl.format(s=s, p=prov_slug or "", p711=P711.get(prov_slug, prov_slug or ""))
                if "{" in url or url.endswith("//" + s) or "/-" in url:
                    continue
                if _probe(url, fd["name"]):
                    found[casino] = url
                    break
                time.sleep(0.4)
            if casino in found:
                break
    return found


def faq5(name, status, release, live_nl, casinos):
    q = f"Is {name} beschikbaar in Nederland?"
    if status == STATUS["ja"]:
        namen = [c for c in casinos][:2]
        extra = f", zoals {' en '.join(namen)}" if namen else ""
        sinds = f"sinds {datum_nl(live_nl)} " if live_nl else ""
        a = (f"Ja. {name} is {sinds}te spelen bij Nederlandse casino's met een vergunning van de Kansspelautoriteit{extra}. "
             "Speel alleen bij een casino met een KSA-vergunning.")
    else:
        uit = f"kwam op {datum_nl(release)} uit, maar " if release else ""
        a = f"Nog niet. {name} {uit}staat nog niet bij Nederlandse casino's met een KSA-vergunning. "
        a += (f"De verwachte lancering in Nederland is {datum_nl(live_nl)}. " if status == STATUS["binnenkort"] and live_nl
              else "Een Nederlandse lanceerdatum is nog niet bekend. ")
        a += "Wij controleren dit dagelijks en passen deze pagina aan zodra het spel hier live staat."
    return q, a


def main(argv):
    _env()
    write, alles = "--write" in argv, "--all" in argv
    today = dt.date.today().isoformat()
    items = _all_items(SLOTS)
    provs = {p["id"]: p["fieldData"]["slug"] for p in _all_items(PROVIDERS)}
    books = {b["fieldData"]["name"]: b["id"] for b in _all_items(BOOKMAKERS) if not b.get("isDraft") and not b.get("isArchived")}
    opt = {o["name"]: o["id"] for f in _wf(f"/collections/{SLOTS}")["fields"] if f["slug"] == "status-nl"
           for o in f["validations"]["options"]}
    name_of = {v: k for k, v in opt.items()}
    changed, rerender = [], []
    for it in items:
        fd = it["fieldData"]
        status = name_of.get(fd.get("status-nl"))
        if status == STATUS["ja"] and not alles:
            continue
        found = find_casinos(it, provs.get(fd.get("provider")))
        cas_ids = [books[c] for c in found if c in books]
        live_nl = (fd.get("live-in-nl") or "")[:10] or None
        new = {}
        if found:
            new_status = STATUS["ja"]
            if not live_nl or live_nl > today:
                live_nl = today
            merged = list(dict.fromkeys((fd.get("casino-s") or []) + cas_ids))
            if merged != (fd.get("casino-s") or []):
                new["casino-s"] = merged
        else:
            new_status = STATUS["binnenkort"] if live_nl and live_nl > today else (status if status == STATUS["ja"] else STATUS["nee"])
        if new_status != status:
            new["status-nl"] = opt[new_status]
        if live_nl and live_nl != (fd.get("live-in-nl") or "")[:10]:
            new["live-in-nl"] = live_nl + "T00:00:00.000Z"
        managed = not fd.get("faq-5-vraag") or fd["faq-5-vraag"].startswith(f"Is {fd['name']} beschikbaar in Nederland")
        if managed and (new or not fd.get("faq-5-vraag")):
            new["faq-5-vraag"], new["faq-5-antwoord"] = faq5(fd["name"], new_status, (fd.get("releasedatum") or "")[:10] or None,
                                                             live_nl, [c for c in found] or [])
        print(f"{fd['name'][:32]:32} {status or '-':18} -> {new_status:18} {', '.join(found) or 'geen NL-casino'}")
        if new:
            changed.append((it, new))
            if "status-nl" in new:
                rerender.append(fd["slug"])
    if not write or not changed:
        print(f"{len(changed)} wijzigingen" + ("" if write else " (dry-run)"))
        return
    staged = [{"id": it["id"], "fieldData": new} for it, new in changed]
    live = [{"id": it["id"], "fieldData": new} for it, new in changed if it.get("lastPublished") and not it.get("isDraft")]
    for path, rows in (("items", staged), ("items/live", live)):
        for i in range(0, len(rows), 25):
            print("PATCH", path, _wf(f"/collections/{SLOTS}/{path}", "PATCH", {"items": rows[i:i + 25]}))
    if rerender:                                   # status-pil op de deelafbeelding bijwerken
        import slot_og
        slot_og.main(rerender + ["--attach"])


if __name__ == "__main__":
    main(sys.argv[1:])
