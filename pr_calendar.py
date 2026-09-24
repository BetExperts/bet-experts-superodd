# -*- coding: utf-8 -*-
"""Leest de bonuskalender uit (alleen als ontdekkingsbron) en parseert de looptijd."""
import re, html
from datetime import date
import requests
from pr_config import CALENDAR_URL

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAANDEN = {m: i + 1 for i, m in enumerate(["januari", "februari", "maart", "april", "mei", "juni", "juli",
                                           "augustus", "september", "oktober", "november", "december"])}

def _g(pat, s):
    m = re.search(pat, s, re.S)
    return m.group(1) if m else None

def _txt(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).replace("\xa0", " ").strip()

def fetch_cards():
    r = requests.get(CALENDAR_URL, headers={"User-Agent": UA, "Accept-Language": "nl-NL"}, timeout=40)
    r.raise_for_status()
    cards = []
    for c in r.text.split('<div class="bonusCalendar__bonusCard ')[1:]:
        logo = _g(r'bonusCalendar__bonusCard-image"[^>]*src="([^"]+)"', c) or ""
        op = re.sub(r"-(casino-)?logo.*", "", logo.rsplit("/", 1)[-1]) if logo else "?"
        types = [t.split(",")[0] for t in (html.unescape(_g(r'data-bonustypes="([^"]*)"', c) or "")).split("|") if t]
        desc = _g(r'bonusCard-description">(.*?)</div>', c) or ""
        cards.append({
            "op": op,
            "types": types,
            "tag": _txt(_g(r'bonusCard-tagline">(.*?)</div>', c)),
            "title": _txt(_g(r'bonusCard-title">(.*?)</div>', c)),
            "bullets": [_txt(b) for b in re.findall(r"<li>(.*?)</li>", desc, re.S) if _txt(b)],
            "exclusive": "--exclusive" in c[:400],
        })
    return cards

def _d(dag, maand, jaar):
    return date(jaar, MAANDEN[maand], int(dag))

def parse_period(tag, today=None):
    """'23 september T/M 26 september' -> (date, date); 'Altijd geldig' -> (None, None, None);
    'Iedere donderdag & vrijdag' -> (None, None, 'iedere donderdag & vrijdag')."""
    today = today or date.today()
    t = (tag or "").strip().lower()
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+t/m\s+(\d{1,2})\s+([a-z]+)", t)
    if m and m.group(2) in MAANDEN and m.group(4) in MAANDEN:
        y = today.year
        start = _d(m.group(1), m.group(2), y)
        if (start - today).days > 120:          # start ligt ver in de 'toekomst' -> vorig jaar begonnen
            start = _d(m.group(1), m.group(2), y - 1)
        end = _d(m.group(3), m.group(4), start.year)
        if end < start or end < today:          # actie staat vandaag in de kalender -> eindigt niet in het verleden
            end = _d(m.group(3), m.group(4), max(start.year, today.year) + (1 if _d(m.group(3), m.group(4), today.year) < today else 0))
        return start, end, None
    m = re.match(r"(?:tot|t/m)\s+(\d{1,2})\s+([a-z]+)", t)
    if m and m.group(2) in MAANDEN:
        end = _d(m.group(1), m.group(2), today.year)
        if end < today:
            end = _d(m.group(1), m.group(2), today.year + 1)
        return None, end, None
    if not t or "altijd" in t:
        return None, None, None
    return None, None, t                         # terugkerend, bv. 'iedere donderdag & vrijdag'
