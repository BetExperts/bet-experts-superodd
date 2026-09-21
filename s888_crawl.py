# -*- coding: utf-8 -*-
"""Crawlt de 888Sport 60x-welkomstboost-pagina.

De hoofdtekst noemt de wedstrijd + markt; de voorwaarden (onder de knop
'Sportsbook bonusvoorwaarden') geven de exacte datum/tijd, bv.:
  "Deze Odds Boost is uitsluitend geldig voor de wedstrijd Nederland – Duitsland
   op 24-09-2026 om 20:45u op de markt 'Over 0.5 goals'."
Daaruit halen we thuis/uit, datum, tijd en markt.
"""
import os, re
from datetime import datetime
from zoneinfo import ZoneInfo
from s888_config import PROMO_URL

NL = ZoneInfo("Europe/Amsterdam")

# "... wedstrijd X – Y op DD-MM-YYYY om HH:MM(u) op de markt 'MARKT' ..."
_RE_VW = re.compile(
    r"geldig voor de wedstrijd\s+(.+?)\s+op\s+(\d{2})-(\d{2})-(\d{4})\s+om\s+"
    r"(\d{1,2})[:.](\d{2})\s*u?\s+op de markt\s+['‘\"]?(.+?)['’\"]",
    re.IGNORECASE)
# fallback op de hoofdregel: "ZET €1 IN OP 'MARKT' BIJ X VS Y"
_RE_HEAD = re.compile(r"op\s+['‘\"](.+?)['’\"]\s+bij\s+(.+?)\s+en\s+win", re.IGNORECASE)

def _proxy():
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    cfg = {"server": server}
    if os.environ.get("PROXY_USER"): cfg["username"] = os.environ["PROXY_USER"]
    if os.environ.get("PROXY_PASS"): cfg["password"] = os.environ["PROXY_PASS"]
    return cfg

def _split_teams(s):
    parts = re.split(r"\s+(?:–|-|vs\.?|tegen)\s+", s.strip(), maxsplit=1, flags=re.IGNORECASE)
    parts = [p.strip(" .'’") for p in parts if p.strip()]
    return (parts[0], parts[1]) if len(parts) >= 2 else (parts[0] if parts else None, None)

def _parse(text):
    m = _RE_VW.search(text)
    if not m:
        return None
    teams, dd, mm, yyyy, hh, mi, market = m.groups()
    home, away = _split_teams(teams)
    if not (home and away):
        return None
    kickoff = datetime(int(yyyy), int(mm), int(dd), int(hh), int(mi), tzinfo=NL)
    return {
        "home": home, "away": away,
        "market": market.strip(),
        "date": f"{dd}-{mm}-{yyyy}", "time": f"{int(hh):02d}:{mi}",
        "datetime_text": f"{dd}-{mm}-{yyyy} om {int(hh):02d}:{mi}",
        "kickoff": kickoff,
    }

def crawl_60x(headless=True, timeout_ms=45000):
    """Return dict met de 60x-actie, of None als er geen actieve boost staat."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless,
                                    args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL", timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900}, proxy=_proxy(),
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        try:
            page.goto(PROMO_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            browser.close(); raise RuntimeError(f"Kon 888-pagina niet laden: {e}")

        for label in ("Weigeren", "Alleen noodzakelijke", "Alles weigeren", "Akkoord", "Accepteren"):
            try:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click(timeout=2500); break
            except Exception:
                pass
        # voorwaarden-blok openklappen indien nodig
        for label in ("Sportsbook bonusvoorwaarden", "bonusvoorwaarden", "Voorwaarden"):
            try:
                el = page.get_by_text(label, exact=False)
                if el.count() > 0: el.first.click(timeout=2000)
            except Exception:
                pass
        page.wait_for_timeout(1200)
        # textContent pakt ook (ingeklapte) voorwaarden mee
        text = page.evaluate("() => document.body.innerText + '\\n' + document.body.textContent")
        browser.close()
    return _parse(text or "")

if __name__ == "__main__":
    import json
    d = crawl_60x(headless=True)
    if d: d = {**d, "kickoff": d["kickoff"].isoformat()}
    print(json.dumps(d, ensure_ascii=False, indent=2))
