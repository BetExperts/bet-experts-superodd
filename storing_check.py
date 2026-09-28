# -*- coding: utf-8 -*-
"""Storingsmelder: website-check van alle bookmakers vanaf de Mac (NL-IP).

Veel vergunde bookmakers blokkeren de checks van Cloudflare (403/451). Vanaf een Nederlandse
thuisverbinding werken ze wel. Dit script controleert elke 5 minuten (LaunchAgent) alle sites en
stuurt de uitkomst naar de Worker (POST /storing-api/check-ingest, header X-Check-Key).

  ok        = site antwoordt normaal (2xx/3xx)
  fout      = 5xx, time-out of verbindingsfout
  onbekend  = geblokkeerd (403/429/451/Cloudflare-challenge) — telt nooit als storing

Vangnet: als de Mac zelf geen internet heeft (bijna alles faalt), wordt er niets verstuurd.

  python3 storing_check.py --dry     # alleen tonen
  python3 storing_check.py           # controleren + versturen
"""
import os, sys, time, socket, argparse
import requests

INGEST = "https://www.bet-experts.nl/storing-api/check-ingest"
SITES = {
    "circus": "https://www.circus.nl/nl", "bet365": "https://www.bet365.nl", "toto": "https://www.toto.nl",
    "711": "https://www.711.nl", "unibet": "https://www.unibet.nl", "jacks-nl": "https://jacks.nl",
    "betcity": "https://www.betcity.nl", "betmgm": "https://www.betmgm.nl", "leovegas": "https://www.leovegas.nl",
    "comeon": "https://www.comeon.nl/nl", "holland-casino": "https://www.hollandcasino.nl", "kansino": "https://www.kansino.nl",
    "tonybet": "https://tonybet.nl", "betnation": "https://www.betnation.nl", "zebet": "https://www.zebet.nl",
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "nl-NL,nl;q=0.9"}
BLOCKED = {401, 403, 429, 451}

def classify(code, challenged=False):
    if challenged or code in BLOCKED:
        return "onbekend"
    if 200 <= code < 400:
        return "ok"
    if code >= 500:
        return "fout"
    return "onbekend"

def check_http(url):
    t = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True, allow_redirects=True)
        code, challenged = r.status_code, r.headers.get("cf-mitigated") == "challenge"
        r.close()
        return classify(code, challenged), code, int((time.time() - t) * 1000), challenged
    except requests.RequestException:
        return "fout", 0, int((time.time() - t) * 1000), False

def check_browser(urls):
    """Echte browser voor sites met een bot-challenge (bv. Circus)."""
    out = {}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
            pg = b.new_page(locale="nl-NL", user_agent=UA)
            for k, url in urls.items():
                t = time.time()
                try:
                    r = pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                    pg.wait_for_timeout(3000)
                    code = r.status if r else 0
                    title = (pg.title() or "").lower()
                    challenged = "just a moment" in title or "even geduld" in title
                    out[k] = (classify(code, challenged), code, int((time.time() - t) * 1000))
                except Exception:
                    out[k] = ("fout", 0, int((time.time() - t) * 1000))
            b.close()
    except Exception as e:
        print(f"  ! browser niet beschikbaar: {e}")
    return out

def online():
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5).close()
        return True
    except OSError:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if not online():
        print("Geen internet op de Mac — niets gecontroleerd."); return
    results, retry = {}, {}
    for k, url in SITES.items():
        res, code, ms, challenged = check_http(url)
        results[k] = (res, code, ms)
        if challenged or code in BLOCKED:
            retry[k] = url
    if retry:
        results.update({k: v for k, v in check_browser(retry).items()})
    for k, (res, code, ms) in results.items():
        print(f"  {k:15} {res:9} {code} {ms}ms")
    fout = sum(1 for r in results.values() if r[0] == "fout")
    if fout / len(results) >= 0.5:
        print(f"  ! {fout}/{len(results)} fout — waarschijnlijk een lokale netwerkstoring, niet verstuurd."); return
    if a.dry:
        return
    key = os.environ.get("STORING_CHECK_KEY", "").strip()
    if not key:
        print("FOUT: STORING_CHECK_KEY ontbreekt in .env"); sys.exit(1)
    payload = {"results": [{"id": k, "result": r, "http": c, "ms": m} for k, (r, c, m) in results.items()]}
    r = requests.post(INGEST, json=payload, headers={"X-Check-Key": key, "User-Agent": "BetExpertsStatusMac/1.0"}, timeout=20)
    print(f"  → Worker: {r.status_code} {r.text[:120]}")

if __name__ == "__main__":
    main()
