# -*- coding: utf-8 -*-
"""Crawlt bet365.nl en haalt de Super Boost (Super Odd) van de dag op.

Onderscheid Super Boost vs Bet Boost: Bet365 gebruikt een aparte badge-SVG
(`SuperBoostBadges/Super-Boost-*.svg`). Er staat er precies één op de homepage.
"""
import os, re
from so_config import BET365_URL

def _proxy():
    """Optionele proxy uit env (voor draaien vanaf een geblokkeerd IP).
    Zet PROXY_SERVER (bv. http://nl.proxy.example:8000) + evt. PROXY_USER/PASS."""
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    cfg = {"server": server}
    if os.environ.get("PROXY_USER"): cfg["username"] = os.environ["PROXY_USER"]
    if os.environ.get("PROXY_PASS"): cfg["password"] = os.environ["PROXY_PASS"]
    return cfg

# JS dat in de paginacontext draait: vindt de Super-Boost-kaart via de badge
# en geeft de losse tekstblokjes (leaf nodes) terug in leesvolgorde.
_EXTRACT_JS = r"""
() => {
  const badge = [...document.querySelectorAll('img')]
    .find(i => /SuperBoostBadges\/Super-Boost/i.test(i.src));
  if (!badge) return null;
  // Klim omhoog tot een compacte container die de uitbetaling bevat.
  let card = badge;
  for (let i = 0; i < 8; i++) {
    card = card.parentElement;
    if (!card) return null;
    if (/betaalt.*uit/i.test(card.textContent) && card.textContent.length < 800) break;
  }
  const leaves = [];
  const walk = el => {
    for (const ch of el.children) {
      if (ch.children.length === 0) {
        const t = (ch.textContent || '').trim();
        if (t) leaves.push(t);
      } else walk(ch);
    }
  };
  walk(card);
  return { leaves };
}
"""

def _parse(leaves):
    """Zet de rauwe leaf-teksten om naar gestructureerde velden."""
    if not leaves:
        return None
    title = leaves[0]
    odds, payout, popularity, selections = [], None, None, []
    for t in leaves[1:]:
        if re.fullmatch(r"\d+\.\d{2}", t):            # 2.00 / 3.00
            odds.append(t)
        elif re.search(r"betaalt.*uit", t, re.I):     # €10 betaalt €30 uit
            payout = t
        elif re.fullmatch(r"\d+(?:[.,]\d+)?\s*k?", t, re.I):  # 2k / 1.3k (populariteit)
            popularity = t
        elif re.search(r"[a-zA-Z]", t):               # beschrijvende selectie
            selections.append(t)
    if len(odds) < 2:
        return None
    return {
        "match": title,
        "selections": selections,
        "old_odd": odds[0],
        "new_odd": odds[-1],
        "payout": payout,
        "popularity": popularity,
    }

def crawl_super_boost(headless=True, timeout_ms=45000):
    """Return dict met de Super Odd, of None als er geen te vinden is / geblokkeerd."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900},
            proxy=_proxy(),
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()
        try:
            page.goto(BET365_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            browser.close()
            raise RuntimeError(f"Kon bet365.nl niet laden (mogelijk geblokkeerd/geo): {e}")

        # Cookie-banner: alleen functionele cookies (privacyvriendelijk).
        for label in ("Alleen functionele cookies", "Alles accepteren"):
            try:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click(timeout=3000)
                    break
            except Exception:
                pass

        # Wacht tot de Super-Boost-badge geladen is (max ~timeout).
        try:
            page.wait_for_selector('img[src*="SuperBoostBadges/Super-Boost"]', timeout=timeout_ms)
        except Exception:
            browser.close()
            return None

        raw = page.evaluate(_EXTRACT_JS)
        browser.close()
        if not raw:
            return None
        return _parse(raw.get("leaves"))

if __name__ == "__main__":
    import json
    data = crawl_super_boost(headless=True)
    print(json.dumps(data, ensure_ascii=False, indent=2))
