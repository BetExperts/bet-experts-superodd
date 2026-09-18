# -*- coding: utf-8 -*-
"""Crawlt de dagelijkse Oranje Palace Super Odd ('Lucky's Boost') van de homepage.

De boost staat als AFBEELDING op de home (tekst niet in de DOM), maar de banner
linkt naar een Kambi-coupon: href = '#/event/{id}/?coupon=combination|{cid}|0|replace'.
Door die coupon te laden komt de boost in de Kambi-betslip te staan, waar alle
data wél als tekst beschikbaar is (selectie, markt, wedstrijd, oude+nieuwe odd).
Oranje Palace draait op Kambi (brand 'hgtnl'); de aftrap halen we uit de Kambi-API.
"""
import os, re, requests
from op_config import HOME, KAMBI_API

def _proxy():
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    cfg = {"server": server}
    if os.environ.get("PROXY_USER"): cfg["username"] = os.environ["PROXY_USER"]
    if os.environ.get("PROXY_PASS"): cfg["password"] = os.environ["PROXY_PASS"]
    return cfg

# In de browser uit te voeren: leest de boost uit de Kambi-betslip.
_JS_EXTRACT = r"""
() => {
  const q = s => { const e=document.querySelector(s); return e ? e.innerText.trim() : null; };
  const bs = document.querySelector('.KambiBC-betslip') || document.querySelector('[class*="betslip"]');
  if (!bs) return {ok:false};
  const txt = bs.innerText.replace(/\s+/g,' ').trim();
  const selection = q('.mod-KambiBC-betslip-outcome__outcome-label');
  const event     = q('.mod-KambiBC-betslip-outcome__event-link');
  const oldOdd    = q('.mod-KambiBC-betslip-outcome__odds');
  const newOdd    = q('.mod-KambiBC-betslip-outcome__boosted-odds');
  const flagsRaw  = q('.mod-KambiBC-betslip-outcome__label-sticker-container');
  const flags     = flagsRaw ? flagsRaw.replace(/\s+/g,' ').trim() : null;
  // markt/criterium = tekst tussen de selectie en de wedstrijdnaam, zonder de flags
  let market = null;
  if (selection && event) {
    const selN = selection.replace(/\s+/g,' ').trim();
    const evN  = event.replace(/\s+/g,' ').trim();
    const i = txt.indexOf(selN);
    const j = i >= 0 ? txt.indexOf(evN, i + selN.length) : -1;
    if (i >= 0 && j > i) {
      market = txt.slice(i + selN.length, j)
                  .replace(/ODDS ?BOOST|CASH ?OUT/ig, '')
                  .replace(/^[\s·\-]+/, '').trim();
    }
  }
  // max inzet + verloopt uit het reward-label van de Lucky's Boost
  let maxStake=null, expiry=null;
  for (const el of document.querySelectorAll('.KambiBC-react-reward-container__label')) {
    const t = el.innerText || '';
    if (/Lucky'?s Boost/i.test(t)) {
      const m1 = t.match(/Max\.?\s*inzet\s*€\s*([\d.,]+)/i); if (m1) maxStake = m1[1];
      const m2 = t.match(/Verloopt\s+(.+)$/i);               if (m2) expiry = m2[1].trim();
      break;
    }
  }
  const isBoost = /ODDS ?BOOST/i.test(txt);
  return {ok:true, isBoost, selection, market, event, oldOdd, newOdd, flags, maxStake, expiry, raw: txt.slice(0,300)};
}
"""

def _kickoff(event_id):
    """Aftrap (ISO, UTC) uit de publieke Kambi-offering-API."""
    try:
        url = f"{KAMBI_API}/betoffer/event/{event_id}.json"
        params = {"lang": "nl_NL", "market": "NL", "client_id": "2", "channel_id": "1"}
        j = requests.get(url, params=params, timeout=20).json()
        ev = (j.get("events") or [{}])[0]
        return ev.get("start"), ev.get("name")
    except Exception:
        return None, None

def _num(s):
    if not s: return None
    m = re.search(r"\d+[.,]\d+", s)
    return float(m.group(0).replace(",", ".")) if m else None

def crawl_superodd(headless=True, timeout_ms=45000):
    """Return dict met de Super Odd, of None als er geen boost-banner staat."""
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
            page.goto(HOME, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            browser.close(); raise RuntimeError(f"Kon oranjepalace.nl niet laden: {e}")

        for label in ("Weigeren", "Alleen noodzakelijke", "Akkoord"):
            try:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click(timeout=3000); break
            except Exception:
                pass

        # de Super Odd-banner = de enige met een coupon-link
        try:
            page.wait_for_selector('a[href*="coupon=combination"]', timeout=timeout_ms)
        except Exception:
            browser.close(); return None
        href = page.eval_on_selector('a[href*="coupon=combination"]',
                                     "a => a.getAttribute('href')")
        # coupon laden -> boost verschijnt in de betslip
        page.evaluate("h => { location.hash = h.replace(/^#/, ''); }", href)
        try:
            page.wait_for_selector('.mod-KambiBC-betslip-outcome__outcome-label', timeout=timeout_ms)
        except Exception:
            browser.close(); return None
        page.wait_for_timeout(1200)
        data = page.evaluate(_JS_EXTRACT)
        browser.close()

    if not data or not data.get("ok") or not data.get("selection"):
        return None

    m = re.search(r"/event/(\d+)/", href or "")
    event_id = m.group(1) if m else None
    kickoff, api_name = _kickoff(event_id) if event_id else (None, None)

    old = _num(data.get("oldOdd"))
    new = _num(data.get("newOdd"))
    return {
        "selection": data.get("selection"),          # bv. 'Thom van Bergen - Ja'
        "market":    data.get("market"),             # bv. 'Scoort of geeft een assist (...)'
        "event":     data.get("event") or api_name,  # 'FC Groningen - PEC Zwolle'
        "old_odd":   old, "new_odd": new,
        "max_stake": data.get("maxStake"),           # '14.00'
        "expiry":    data.get("expiry"),             # 'Vandaag 19:59'
        "event_id":  event_id, "kickoff": kickoff,   # ISO UTC
        "is_boost":  data.get("isBoost", False),
        "raw":       data.get("raw"),
    }

if __name__ == "__main__":
    import json
    print(json.dumps(crawl_superodd(headless=True), ensure_ascii=False, indent=2))
