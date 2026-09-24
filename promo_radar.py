# -*- coding: utf-8 -*-
"""Promo-radar: vindt lopende acties van onze bookmakers via de bonuskalender, controleert ze op
de officiële promotiepagina van de bookmaker en zet ontbrekende acties als eigen promotie in de CMS.

  python3 promo_radar.py --dry             # alleen tonen wat er zou gebeuren
  python3 promo_radar.py                   # aanmaken: bevestigd -> live, anders draft
  python3 promo_radar.py --only jacks.nl --limit 3

Regels:
- Alleen bookmakers waarmee een deal is (pr_config.BOOKMAKERS) en met een affiliatelink.
- Acties die al in de CMS staan (vergelijkbare titel/getallen) of al eerder verwerkt zijn: overslaan.
- Live alleen als de kerngetallen op de officiële pagina terugkomen; welkomstbonussen altijd draft.
- Tekst is eigen tekst op basis van de feiten; banner komt van de bookmaker zelf (nooit van de kalender).
"""
import io, os, re, sys, json, argparse, subprocess
from datetime import date, datetime
import requests
from PIL import Image
from playwright.sync_api import sync_playwright
from so_config import WEBFLOW_TOKEN, WF_API, PROMO_BASE
import pr_config as C
from pr_calendar import fetch_cards, parse_period
from pr_verify import Verifier, tokens, key_numbers, _has_num
from pr_build import build_fields, slugify
from pr_rubrieken import rubrieken
import cf_redirects

BASE = os.path.dirname(os.path.abspath(__file__))
H = lambda: {"Authorization": f"Bearer {WEBFLOW_TOKEN}", "accept": "application/json", "content-type": "application/json"}

def wf(method, path, body=None):
    r = requests.request(method, WF_API + path, headers=H(), json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text.strip() else {}

def all_items(coll):
    out, off = [], 0
    while True:
        d = wf("GET", f"/collections/{coll}/items?limit=100&offset={off}")
        out += d["items"]; off += len(d["items"])
        if not d["items"] or off >= d["pagination"]["total"]:
            return out

def load_state():
    try:
        return json.load(open(os.path.join(BASE, C.STATE_FILE), encoding="utf-8"))
    except Exception:
        return {}

def save_state(st):
    json.dump(st, open(os.path.join(BASE, C.STATE_FILE), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def card_key(card):
    return f"{card['op']}|{slugify(card['title'])}|{slugify(card['tag'])}"

GENERIC = {"free", "bets", "bet", "spins", "welkomstbonus", "promotie", "inzet", "win", "zet", "gratis", "extra"}

def similar_existing(card, existing, bm_name=""):
    """Staat deze actie al in de CMS? (zelfde bookmaker, overlappende woorden + exact dezelfde getallen)"""
    drop = GENERIC | tokens(bm_name) | tokens(bm_name.replace(".NL", "").replace(".nl", ""))
    ct = tokens(card["title"] + " " + " ".join(card["bullets"])) - drop
    nums = key_numbers(card)
    best = (0, None)
    for f in existing:
        blob = " ".join(str(f.get(k) or "") for k in ("name", "subtitel", "informatie", "voorwaarde-promotie",
                                                      "bedrag-of-boost", "check-1", "check-2", "check-3"))
        tok = len(ct & tokens(blob)) / max(1, len(ct))
        if len(nums) >= 2:        # meerdere identieke getallen = sterk signaal
            s = 0.6 * (sum(1 for n in nums if _has_num(blob, n)) / len(nums)) + 0.4 * tok
        elif nums:                # één getal kan toeval zijn -> woorden moeten ook kloppen
            s = min(tok, sum(1 for n in nums if _has_num(blob, n)) / len(nums))
        else:
            s = tok
        if s > best[0]:
            best = (s, f.get("name"))
    return best

def to_webp(url, name):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    im.thumbnail((C.IMG_MAX, C.IMG_MAX))
    path = os.path.join(BASE, C.ASSET_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=C.IMG_QUALITY, method=6)
    return path

def git_push(paths):
    if not paths:
        return True
    try:
        subprocess.run(["git", "-C", BASE, "add"] + paths, check=True)
        subprocess.run(["git", "-C", BASE, "commit", "-q", "-m", f"promo-radar: {len(paths)} afbeelding(en)"], check=True)
        subprocess.run(["git", "-C", BASE, "pull", "-q", "--rebase", "--autostash"], check=False)
        subprocess.run(["git", "-C", BASE, "push", "-q"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ! git push mislukt ({e}); items worden zonder banner aangemaakt")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", help="alleen deze kalender-operator (bv. jacks.nl)")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if not WEBFLOW_TOKEN:
        print("FOUT: WEBFLOW_TOKEN ontbreekt."); sys.exit(1)
    print(f"== Promo-radar {datetime.now():%Y-%m-%d %H:%M} | {'DRY' if a.dry else 'LIVE'} ==")

    # bookmakers + bestaande promoties
    bms = {b["id"]: b["fieldData"] for b in wf("GET", f"/collections/{C.BOOKMAKERS_COLL}/items?limit=100")["items"]}
    for op, cfg in C.BOOKMAKERS.items():
        if not cfg["id"]:
            cfg["id"] = next((i for i, f in bms.items()
                              if f["name"].lower().replace("!", "").startswith(cfg["name"].lower().replace("!", "").split()[0])), None)
    promos = [p for p in all_items(C.PROMOTIES) if not p.get("isArchived")]
    by_bm = {}
    for p in promos:
        by_bm.setdefault(p["fieldData"].get("bookmaker-3"), []).append(p["fieldData"])

    def affiliate(bm_id, sport):
        want = C.GELDIG_SPORT if sport else C.GELDIG_CASINO
        for f in by_bm.get(bm_id, []):
            # gewone welkomstbonus-link (niet die van een 100x/boost-actie: die landt op een speciale promo)
            if (f.get("geldig-voor") == want and f.get("welkomstbonus-promotie") and f.get("affiliatie-link-naar-broker")
                    and not f.get("100x-promotie") and not f.get("boosted-odd")):
                return f["affiliatie-link-naar-broker"]
        return bms.get(bm_id, {}).get("affiliate-url")

    def logo(bm_id):
        for f in by_bm.get(bm_id, []):
            if (f.get("afbeelding-promotie") or {}).get("url"):
                return {"url": f["afbeelding-promotie"]["url"]}
        return None

    state = load_state()
    cards = fetch_cards()
    print(f"   kalender: {len(cards)} acties vandaag")
    todo = []
    for c in cards:
        cfg = C.BOOKMAKERS.get(c["op"])
        if not cfg or (a.only and c["op"] != a.only):
            continue
        k = card_key(c)
        if k in state:
            continue
        if not cfg["id"]:
            state[k] = {"status": "overgeslagen", "reden": "bookmaker niet in CMS"}; continue
        if "welcomeBonus" in c["types"]:
            state[k] = {"status": "overgeslagen", "reden": "welkomstbonus (beheert de gebruiker zelf)"}; continue
        if re.search(r"\bexclusie(f|ve)\b", c["title"], re.I):
            state[k] = {"status": "overgeslagen", "reden": "exclusieve deal van de kalender-site"}; continue
        _, end, _ = parse_period(c["tag"])
        if end and end < date.today():
            continue      # al afgelopen: niet aanmaken (acties die vandaag eindigen wél: je kunt nog meedoen)
        s, name = similar_existing(c, by_bm.get(cfg["id"], []), cfg["name"])
        if s >= 0.5:
            state[k] = {"status": "bestond al", "cms": name, "score": round(s, 2), "datum": str(date.today())}
            continue
        todo.append(c)
    if a.limit:
        todo = todo[:a.limit]

    # Door de radar aangemaakte acties die verlopen zijn (einddatum voorbij) of niet meer in de
    # kalender staan: verwijderen (gebruiker: verlopen promoties mogen weg).
    current = {card_key(c) for c in cards}
    now = datetime.now().astimezone()
    for k, e in state.items():
        # 'einddatum' = handmatig toegevoegde promo die op zijn 'Geldig tot' offline moet (niet in de kalender)
        if e.get("status") not in ("live", "draft", "einddatum") or not e.get("item_id"):
            continue
        if a.only and not k.startswith(a.only + "|"):
            continue
        it = next((p for p in promos if p["id"] == e["item_id"]), None)
        if not it:
            e["status"] = "verwijderd"; continue
        end = it["fieldData"].get("wanneer-toegevoegd")
        expired = bool(end) and datetime.fromisoformat(end.replace("Z", "+00:00")) < now
        gone = k not in current and e.get("status") != "einddatum"
        if not (expired or gone):
            continue
        print(f"  ✂ {'verlopen' if expired else 'niet meer in kalender'} -> verwijderen: {it['fieldData'].get('name', '')[:70]}")
        if a.dry:
            continue
        try:
            was_live = bool(it.get("lastPublished")) and not it.get("isDraft")
            if was_live:
                # eerst de 301 (sport -> /promoties, casino -> /casino-bonussen), dan pas verwijderen
                target = "/promoties" if it["fieldData"].get("geldig-voor") == C.GELDIG_SPORT else "/casino-bonussen"
                row = (f"www.bet-experts.nl/promoties/{it['fieldData'].get('slug')}", f"https://www.bet-experts.nl{target}", 301)
                try:
                    cf_redirects.add([row])
                except Exception as ex:
                    print(f"    ! redirect niet gezet ({ex}) -> promo blijft staan"); continue
                wf("DELETE", f"/collections/{C.PROMOTIES}/items/{e['item_id']}/live")
            wf("DELETE", f"/collections/{C.PROMOTIES}/items/{e['item_id']}")
            e.update({"status": "verwijderd", "reden": "verlopen" if expired else "niet meer in kalender",
                      "verwijderd": str(date.today())})
        except Exception as ex:
            print(f"    ! {ex}")
    save_state(state)
    print(f"   nieuw te verwerken: {len(todo)}")

    plans, images = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ver = Verifier(browser)
        for c in todo:
            cfg = C.BOOKMAKERS[c["op"]]
            bm = {"id": cfg["id"], "name": cfg["name"]}
            period = parse_period(c["tag"])
            v = ver.verify(c, cfg["pages"])
            sport = None
            fd, sport, rub = build_fields(c, bm, period, v, None, logo(cfg["id"]))
            link = affiliate(cfg["id"], sport)
            if not link:
                state[card_key(c)] = {"status": "overgeslagen", "reden": "geen affiliatelink"}; continue
            fd["affiliatie-link-naar-broker"] = link
            fd["link-artikel-voor-sidebar"] = PROMO_BASE + fd["slug"]
            fd["bonus-rubrieken"] = rubrieken(fd)
            live = v["ok"] and not (C.WELCOME_AS_DRAFT and fd["welkomstbonus-promotie"])
            img_name = None
            if v.get("image") and not a.dry:
                try:
                    img_name = f"betexperts-{fd['slug'][:70]}.webp"
                    images.append(os.path.relpath(to_webp(v["image"], img_name), BASE))
                except Exception as e:
                    print(f"   ! afbeelding mislukt: {e}"); img_name = None
            plans.append((c, fd, live, v, img_name, rub))
            print(f"  {'●' if live else '○'} {fd['name'][:78]}\n      {rub} | {'sport' if sport else 'casino'} | {v['reason']}"
                  f"{' | banner' if v.get('image') else ''}{' | ' + v['detail_url'] if v.get('detail_url') else ''}")
        browser.close()

    if a.dry:
        cleanup_expired(dry=True)
        sweep_nieuw(dry=True)
        print(f"\nDRY — {sum(1 for p in plans if p[2])} zouden live gaan, {sum(1 for p in plans if not p[2])} als draft.")
        return

    pushed = git_push(images)
    made = {"live": 0, "draft": 0}
    for c, fd, live, v, img_name, rub in plans:
        if img_name and pushed:
            fd["afbeelding-promotie-specifiek"] = {"url": C.RAW_BASE + img_name, "alt": fd["name"][:100]}
        try:
            body = {"isDraft": not live, "isArchived": False, "fieldData": fd}
            j = wf("POST", f"/collections/{C.PROMOTIES}/items" + ("/live" if live else ""), body)
            made["live" if live else "draft"] += 1
            state[card_key(c)] = {"status": "live" if live else "draft", "item_id": j.get("id"),
                                  "slug": (j.get("fieldData") or {}).get("slug"), "check": v["reason"],
                                  "bron": v.get("detail_url"), "datum": str(date.today())}
            print(f"  ✔ {'LIVE ' if live else 'DRAFT'} {PROMO_BASE}{(j.get('fieldData') or {}).get('slug')}")
        except Exception as e:
            print(f"  ! mislukt: {fd['name'][:60]} — {e}")
        save_state(state)
    save_state(state)
    cleanup_expired(a.dry)
    sweep_nieuw(a.dry)
    print(f"\nKLAAR — {made['live']} live, {made['draft']} als draft.")

def _unlink_from_news(item_id):
    """Haalt een promo uit het veld 'promotie-s' van nieuwsartikelen (anders weigert Webflow verwijderen)."""
    N = "64ff0fbd5a8f205b05d54656"
    fixed = 0
    for it in all_items(N):
        refs = it["fieldData"].get("promotie-s") or []
        if item_id not in refs:
            continue
        new = [x for x in refs if x != item_id]
        live = bool(it.get("lastPublished")) and not it.get("isDraft")
        try:
            wf("PATCH", f"/collections/{N}/items/{it['id']}" + ("/live" if live else ""), {"fieldData": {"promotie-s": new}})
        except RuntimeError:
            wf("PATCH", f"/collections/{N}/items/{it['id']}", {"fieldData": {"promotie-s": new}})
        fixed += 1
    return fixed

def cleanup_expired(dry=False):
    """Elke verlopen promo (behalve evergreen agent-pagina's): 301 zetten, offline halen en uit de CMS verwijderen."""
    now = datetime.now().astimezone()
    state = load_state()
    eenmalig = {e.get("item_id") for e in state.values() if isinstance(e, dict)
                and e.get("status") in ("live", "draft", "einddatum") and e.get("item_id")}
    beoordeling = {}
    for it in all_items(C.PROMOTIES):
        f = it["fieldData"]; end = f.get("wanneer-toegevoegd")
        if it.get("isArchived") or not end or f.get("slug") in C.EVERGREEN_SLUGS:
            continue
        if (now - datetime.fromisoformat(end.replace("Z", "+00:00"))).total_seconds() < C.OPRUIM_MARGE_UUR * 3600:
            continue
        if it["id"] not in eenmalig:
            # Niet zeker dat het eenmalig is -> NIET verwijderen, eerst aan de gebruiker vragen.
            beoordeling[it["id"]] = {"slug": f.get("slug"), "name": f.get("name"), "geldig_tot": end[:10]}
            print(f"  ? verlopen, ter beoordeling (niet verwijderd): {f.get('name', '')[:70]}")
            continue
        print(f"  ✂ verlopen ({end[:10]}) -> offline + verwijderen: {f.get('name', '')[:70]}")
        if dry:
            continue
        was_live = bool(it.get("lastPublished"))
        if was_live:
            target = "/promoties" if f.get("geldig-voor") == C.GELDIG_SPORT else "/casino-bonussen"
            try:
                cf_redirects.add([(f"www.bet-experts.nl/promoties/{f['slug']}", f"https://www.bet-experts.nl{target}", 301)])
            except Exception as ex:
                print(f"    ! redirect niet gezet ({ex}) -> promo blijft staan"); continue
        for attempt in (1, 2):
            try:
                if was_live:
                    wf("DELETE", f"/collections/{C.PROMOTIES}/items/{it['id']}/live")
                wf("DELETE", f"/collections/{C.PROMOTIES}/items/{it['id']}")
                break
            except RuntimeError as ex:
                if "409" in str(ex) and attempt == 1:
                    print(f"    · nog gekoppeld aan nieuwsartikelen -> {_unlink_from_news(it['id'])} artikel(en) losgekoppeld")
                    continue
                print(f"    ! {ex}"); break
    if not dry:
        state = load_state(); state["_ter_beoordeling"] = beoordeling; save_state(state)

def sweep_nieuw(dry=False):
    """Houdt voor ALLE promo's de rubriek 'Nieuw' (laatste NIEUW_DAGEN dagen) en het veld 'bonus-types'
    (tokens voor de bonuskalender-embed, incl. 'nieuw' en 'welkomstbonus') in sync."""
    from pr_rubrieken import RUB, types_for
    nid = RUB.get("nieuw")
    now = datetime.now().astimezone()
    n = 0
    for it in all_items(C.PROMOTIES):
        if it.get("isArchived"):
            continue
        f = it["fieldData"]; cur = f.get("bonus-rubrieken") or []
        created = datetime.fromisoformat(it["createdOn"].replace("Z", "+00:00"))
        new = (created.date().isoformat() >= C.NIEUW_VANAF and (now - created).days < C.NIEUW_DAGEN) or \
              now.date().isoformat() <= C.NIEUW_HANDMATIG.get(it["id"], "")
        rub = [x for x in cur if x != nid] + ([nid] if (new and nid) else [])
        types = types_for(f, rub, new)
        patch = {}
        if sorted(rub) != sorted(cur):
            patch["bonus-rubrieken"] = rub
        if types != (f.get("bonus-types") or ""):
            patch["bonus-types"] = types
        if not patch:
            continue
        n += 1
        if "bonus-rubrieken" in patch:
            print(f"  {'+' if new else '-'} Nieuw: {f.get('name', '')[:70]}")
        if dry:
            continue
        live = bool(it.get("lastPublished")) and not it.get("isDraft")
        try:
            wf("PATCH", f"/collections/{C.PROMOTIES}/items/{it['id']}" + ("/live" if live else ""), {"fieldData": patch})
        except RuntimeError as e:
            if "409" in str(e):
                wf("PATCH", f"/collections/{C.PROMOTIES}/items/{it['id']}", {"fieldData": patch})
            else:
                print(f"    ! {e}")
    print(f"   bonus-types/Nieuw gesynchroniseerd: {n} promo('s) {'zouden worden ' if dry else ''}bijgewerkt")

if __name__ == "__main__":
    main()
