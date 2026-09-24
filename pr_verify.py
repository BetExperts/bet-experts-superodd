# -*- coding: utf-8 -*-
"""Controleert een kalender-promo op de officiële promotiepagina's van de bookmaker en
haalt daar de detail-URL + banner vandaan. Zonder bevestiging -> geen live-publicatie."""
import re
from urllib.parse import urlparse

STOP = {"bonus", "bij", "pak", "voor", "jouw", "deze", "elke", "week", "met", "een", "het", "de", "van", "en",
        "op", "tot", "je", "in", "aan", "ontvang", "nieuwe", "spelers", "maximaal", "minimaal", "casino", "sport"}

def tokens(s):
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{3,}", (s or "").lower()) if w not in STOP}

def key_numbers(card):
    """Getallen die op de officiële pagina terug moeten komen (bedragen, spins, x-factoren, %)."""
    s = " ".join([card["title"]] + card["bullets"])
    nums = set()
    for m in re.finditer(r"€\s?(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:free spins|gratis spins|spins|x\b|%)", s, re.I):
        n = (m.group(1) or m.group(2)).replace(".", ",")
        try:
            v = float(n.replace(",", "."))
        except ValueError:
            continue
        if v >= 2 or "," in n:           # €1 / 1x zegt niets (staat overal)
            nums.add(n)
    return nums

def _has_num(text, n):
    alts = {n, n.replace(",", "."), n.split(",")[0] if n.endswith(",00") else n}
    return any(re.search(rf"(?<![\d,.]){re.escape(a)}(?![\d])", text) for a in alts)

class Verifier:
    def __init__(self, browser):
        self.ctx = browser.new_context(locale="nl-NL", user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"))
        self.cache = {}

    def _load(self, url, wait=5000):
        if url in self.cache:
            return self.cache[url]
        pg = self.ctx.new_page()
        out = {"text": "", "links": [], "image": None, "url": url}
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(wait)
            out["text"] = pg.inner_text("body")
            host = urlparse(url).netloc.replace("www.", "")
            out["links"] = pg.eval_on_selector_all("a", """els => els.map(e => [e.href, (e.innerText||'') + ' ' +
                (e.closest('article,li,div')?.innerText||'').slice(0,400)])""")
            out["links"] = [(h, t) for h, t in out["links"] if host.split(".")[-2] in h
                            and re.search(r"promo|actie|bonus|campaign", h, re.I)
                            and not re.search(r"voorwaarden|terms|#$", h, re.I)]
            imgs = pg.eval_on_selector_all("img", "els => els.map(e => [e.currentSrc||e.src, e.naturalWidth, e.naturalHeight])")
            imgs = [i for i in imgs if i[1] >= 600 and i[2] >= 250 and not re.search(r"logo|icon|license|\.svg", i[0], re.I)]
            imgs.sort(key=lambda i: -i[1] * i[2])
            out["image"] = imgs[0][0] if imgs else None
            if not out["image"]:
                og = pg.eval_on_selector_all("meta[property='og:image']", "els => els.map(e => e.content)")
                out["image"] = og[0] if og and "opengraph-image" not in og[0] else None
        except Exception as e:
            out["error"] = str(e)[:120]
        finally:
            pg.close()
        self.cache[url] = out
        return out

    def verify(self, card, pages):
        """-> dict(ok, reason, detail_url, image, text)"""
        if not pages:
            return {"ok": False, "reason": "geen officiële promopagina bekend"}
        ct = tokens(card["title"] + " " + " ".join(card["bullets"]))
        nums = key_numbers(card)
        best = (0, None)
        overview_text = ""
        for p in pages:
            o = self._load(p)
            overview_text += "\n" + o["text"]
            for href, txt in o["links"]:
                s = len(ct & tokens(txt + " " + href.replace("-", " "))) / max(1, len(ct))
                if s > best[0]:
                    best = (s, href)
        detail = self._load(best[1], wait=4000) if best[1] and best[0] >= 0.25 else None
        text = (detail or {}).get("text") or overview_text
        found = [n for n in nums if _has_num(text, n)]
        if nums:
            ok = len(found) / len(nums) >= 0.6 and (detail is not None or len(found) >= 2)
            reason = f"{len(found)}/{len(nums)} kerngetallen gevonden"
        else:
            ok = detail is not None and len(ct & tokens(text)) / max(1, len(ct)) >= 0.5
            reason = "geen getallen; tekstoverlap"
        if not detail:
            reason += " (alleen overzichtspagina)"
        return {"ok": ok, "reason": reason, "detail_url": best[1] if detail else None,
                "image": (detail or {}).get("image"), "text": text}
