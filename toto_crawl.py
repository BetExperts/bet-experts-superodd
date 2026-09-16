# -*- coding: utf-8 -*-
"""Crawlt de TOTO welkomstbonus-sportpagina en haalt de dagelijkse 50x-wedstrijd op.

De pagina bevat een zin als:
  "Plaats je eerste weddenschap van max. €1 op 'winst Juventus' of 'winst NEC' ..."
Daaruit halen we de team(s) → de wedstrijd van vandaag.
"""
import os, re
from toto_config import TOTO_URL

# Optionele proxy (zelfde mechaniek als de Bet365-crawler).
def _proxy():
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    cfg = {"server": server}
    if os.environ.get("PROXY_USER"): cfg["username"] = os.environ["PROXY_USER"]
    if os.environ.get("PROXY_PASS"): cfg["password"] = os.environ["PROXY_PASS"]
    return cfg

def _teams_from_text(text):
    """Unieke teamnamen uit 'winst X' / 'winst Y' (volgorde behouden)."""
    hits = re.findall(r"winst\s+([A-Za-zÀ-ÿ0-9][\wÀ-ÿ .'&/-]+?)['’]", text)
    seen, out = set(), []
    for t in hits:
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out

def crawl_50x(headless=True, timeout_ms=45000):
    """Return {'teams':[...], 'match':'A - B'} of None als er geen 50x-actie staat."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL", timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900}, proxy=_proxy(),
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()
        try:
            page.goto(TOTO_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            browser.close()
            raise RuntimeError(f"Kon toto.nl niet laden: {e}")

        # Cookie-banner: weigeren (privacyvriendelijk).
        for label in ("Weigeren", "Alleen noodzakelijke", "Akkoord"):
            try:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click(timeout=3000); break
            except Exception:
                pass

        try:
            page.wait_for_selector("main", timeout=timeout_ms)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        text = page.evaluate("() => (document.querySelector('main')?.innerText) || document.body.innerText")
        browser.close()

    teams = _teams_from_text(text or "")
    if not teams:
        return None
    match = " - ".join(teams[:2]) if len(teams) >= 2 else teams[0]
    return {"teams": teams, "match": match}

if __name__ == "__main__":
    import json
    print(json.dumps(crawl_50x(headless=True), ensure_ascii=False, indent=2))
