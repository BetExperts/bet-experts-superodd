# -*- coding: utf-8 -*-
"""Bepaalt de 'bonus-rubrieken' (multi-reference) van een promotie, voor de filters op de bonuspagina."""
import re, json, os
RUB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "rubrieken.json"), encoding="utf-8"))
SPORT = "9c0fbc22d905260428d1de2988b86dea"
TEXT_RULES = [
    (r"free ?spins?|gratis spins", "free-spins"), (r"toernooi|tournament|races\b", "toernooi"),
    (r"jackpot", "jackpot"), (r"live ?casino|live blackjack|live roulette|evolution|free chips", "live-casino"),
    (r"\bbingo", "bingo-bonus"), (r"\bpoker", "poker-bonus"),
    (r"loyalit|award points|punten|rewards|coins|vip", "loyaliteitsbonus"), (r"\bapp\b|app-", "casino-apps"),
    (r"drops?\b|cash drop|prize drop|wheel drop", "cash-drop"), (r"bet ?(&|en|and) ?get|zet .{1,12} in (en|&) (krijg|ontvang|pak)", "bet-en-get"),
    (r"bonuscode", "bonuscode"), (r"stortingsbonus|bovenop je storting|op je storting|extra tegoed", "stortingsbonus"),
    (r"free ?bets?", "free-bets"), (r"\d{2,3}x je in(zet|leg)", "100x-je-inzet"),
]
TYPE_TO_RUB = {"welkomstbonus": "welkomstbonus", "free-bets": "free-bets", "free-spins": "free-spins",
               "bet-and-get": "bet-en-get", "no-deposit": "no-deposit-bonus", "stortingsbonus": "stortingsbonus",
               "cash-drop": "cash-drop", "toernooi": "toernooi", "loyaliteit": "loyaliteitsbonus",
               "casino-app": "casino-apps", "live-casino": "live-casino", "jackpot": "jackpot", "bingo": "bingo-bonus",
               "poker": "poker-bonus", "bonuscode": "bonuscode", "sport": "sport-bonus", "casino": "casino-promotie"}

def rubrieken(f):
    ids_by_slug = RUB
    slugs = set()
    cur = f.get("promotie-rubriek")
    if cur:
        slugs |= {s for s, i in ids_by_slug.items() if i == cur}
    for t in (f.get("bonus-types") or "").split(","):
        if t.strip() in TYPE_TO_RUB:
            slugs.add(TYPE_TO_RUB[t.strip()])
    if f.get("welkomstbonus-promotie"): slugs.add("welkomstbonus")
    if f.get("no-deposit-bonus"): slugs.add("no-deposit-bonus")
    if f.get("free-bets"): slugs.add("free-bets")
    if f.get("100x-promotie"): slugs.add("100x-je-inzet")
    if f.get("boosted-odd"): slugs.add("superodd")
    slugs.add("sport-bonus" if f.get("geldig-voor") == SPORT else "casino-promotie")
    blob = " ".join(str(f.get(k) or "") for k in ("name", "subtitel", "bonus-tekst", "soort-welkomstbonus", "check-1", "check-2", "check-3")).lower()
    for pat, slug in TEXT_RULES:
        if re.search(pat, blob):
            slugs.add(slug)
    return sorted(ids_by_slug[s] for s in slugs if s in ids_by_slug)
