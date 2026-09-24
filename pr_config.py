# -*- coding: utf-8 -*-
"""Config voor de promo-radar: bonuskalender (ontdekkingsbron) -> eigen promoties in de CMS."""
import os

# Ontdekkingsbron: alleen gebruikt om te zien WELKE acties er lopen. Feiten, data en
# banners komen van de promotiepagina's van de bookmaker zelf (zie BOOKMAKERS).
CALENDAR_URL = "https://www.onlinecasinoground.nl/casino-bonussen/"

PROMOTIES = "65e6fb5b08aed95b983b590f"
BOOKMAKERS_COLL = "64ff0fbd5a8f205b05d54686"

# Afbeeldingen: de Webflow-token mist 'assets:write', dus we hosten de WebP in de publieke
# repo en laten Webflow 'm via {"url": ...} ingesten (komt op de Webflow-CDN met onze naam).
ASSET_DIR = "assets/promos"
RAW_BASE = "https://raw.githubusercontent.com/BetExperts/bet-experts-superodd/main/assets/promos/"
IMG_MAX = 800          # max. breedte/hoogte in px
IMG_QUALITY = 76       # WebP-kwaliteit (doel < 40 KB)

# Kalender-operator (uit de logo-bestandsnaam) -> bookmaker-id in onze CMS + officiële promo-pagina's.
# Operators die hier niet staan (geen deal) worden overgeslagen.
BOOKMAKERS = {
    "jacks.nl":      {"id": "64ff0fbd5a8f205b05d5465c", "name": "JACKS.NL",  "pages": ["https://jacks.nl/promoties"]},
    "oranje-palace": {"id": "6aad0c21a14e9435daf42e79", "name": "Oranje Palace", "pages": ["https://www.oranjepalace.nl/nl/promoties"]},
    "circus":        {"id": None, "name": "Circus",    "pages": ["https://www.circus.nl/nl/promoties", "https://www.circus.nl/nl/promoties/casino",
                                                                  "https://www.circus.nl/nl/promoties/sport", "https://www.circus.nl/nl/promoties/toernooien"]},
    "leovegas":      {"id": None, "name": "LeoVegas",  "pages": ["https://www.leovegas.nl/promoties", "https://www.leovegas.nl/promoties/wedden"]},
    "betmgm":        {"id": None, "name": "BetMGM",    "pages": ["https://www.betmgm.nl/promoties", "https://www.betmgm.nl/promoties/casino",
                                                                  "https://www.betmgm.nl/promoties/wedden"]},
    "toto":          {"id": None, "name": "TOTO",      "pages": ["https://www.toto.nl/acties"]},
    "hard-rock":     {"id": None, "name": "Hard Rock Casino", "pages": ["https://hardrockcasino.nl/promoties"]},
    "888":           {"id": None, "name": "888",       "pages": ["https://www.888.nl/nl/promotions"]},
    "vbet":          {"id": None, "name": "Vbet",      "pages": ["https://www.vbet.nl/nl/promotions"]},
    "tonybet":       {"id": None, "name": "Tonybet",   "pages": ["https://tonybet.nl/promotions"]},
    "unibet":        {"id": None, "name": "Unibet",    "pages": ["https://www.unibet.nl/promotions", "https://www.unibet.nl/promotions/betting",
                                                                  "https://www.unibet.nl/promotions/casino"]},
    "one":           {"id": None, "name": "One Casino", "pages": ["https://nl.onecasino.com/promotions"]},
    "711":           {"id": None, "name": "711",       "pages": ["https://www.711.nl/promoties"]},
    "comeon":        {"id": None, "name": "ComeOn!",   "pages": ["https://www.comeon.nl/nl/promoties"]},
    "bet365":        {"id": None, "name": "Bet365",    "pages": []},     # promo's zitten achter de app/login
}
# id None -> wordt bij de start opgezocht op naam in de Bookmakers-collectie.

# Kalender-types -> onze labels (voor het veld bonus-types en de filters)
TYPE_LABELS = {
    "welcomeBonus": "welkomstbonus", "sportBonus": "sport", "freeBetsBonus": "free-bets",
    "freeSpinsBonus": "free-spins", "betAndGetBonus": "bet-and-get", "noDepositBonus": "no-deposit",
    "depositBonus": "stortingsbonus", "cashDropBonus": "cash-drop", "tournamentBonus": "toernooi",
    "loyaltyBonus": "loyaliteit", "casinoAppsBonus": "casino-app", "liveCasinoBonus": "live-casino",
    "jackpotBonus": "jackpot", "bingoBonus": "bingo", "pokerBonus": "poker", "bonusCodeBonus": "bonuscode",
}
SPORT_TYPES = {"sportBonus", "freeBetsBonus", "betAndGetBonus"}

# Promotie-rubrieken
RUBRIEK = {
    "welkomstbonus": "65e7184eac16c5708f019c90", "free-bets": "65f1b2b7726eafb3921efdd5",
    "no-deposit": "65e718dc381280c80e7b6e8b", "stortingsbonus": "65e718905cce36906ffc6a34",
    "casino": "65e718ae4d11a64bccab872e", "specials": "65eb24f2e8d4c04e87892eab",
    "100x": "65e7186a56e4d824ad5f1787",
}
GELDIG_SPORT = "9c0fbc22d905260428d1de2988b86dea"
GELDIG_CASINO = "149fd8f57ae471590f6553417235ec74"

# Welkomstbonussen beheert de gebruiker zelf met exacte deal-cijfers -> altijd als draft.
WELCOME_AS_DRAFT = True

STATE_FILE = "state/promo_radar.json"
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."

# Filter "Nieuw": promo's die korter dan NIEUW_DAGEN geleden zijn aangemaakt krijgen de rubriek 'nieuw'.
# De eerste bulk (24-09-2026) telt niet mee -> pas vanaf NIEUW_VANAF.
NIEUW_DAGEN = 3
NIEUW_VANAF = "2026-09-25"

# Handmatig 'Nieuw' tot en met deze datum (item-id -> YYYY-MM-DD), naast de automatische 3-dagenregel.
NIEUW_HANDMATIG = {
    "66c5cc4307ddceb00c519f75": "2026-09-27",   # ComeOn! Dubbele Casino Welkomstbonus
    "6ab5284c35713b17e2523870": "2026-09-27",   # 888 Casino Welkomstbonus Special
}

# Opruiming: alleen BEKENDE eenmalige promo's (radar-promo's + state-status 'einddatum') waarvan 'Geldig tot' langer dan OPRUIM_MARGE_UUR voorbij is, wordt
# offline gehaald + verwijderd (met 301). Uitgezonderd: evergreen pagina's die agents hergebruiken
# voor de volgende boost/wedstrijd (hun 'Geldig tot' schuift steeds mee).
OPRUIM_MARGE_UUR = 2
EVERGREEN_SLUGS = {
    "bet365-super-odd",                              # Bet365 Super Odd (so-agent)
    "oranje-palace-luckys-boost",                    # Oranje Palace Lucky's Boost (op-agent)
    "toto-50x-je-inzet",                             # TOTO 50x (toto-agent)
    "888sport-odd-boosts-pak-60-00x-je-inzet",       # 888sport 60x (s888-agent)
    "jacks-nl-100x-je-inzet",                        # JACKS.NL 100x (vaste pagina, bij elke nieuwe 100x-actie bijwerken)
    # Terugkerende acties: blijven staan en worden bijgewerkt zodra ze terugkomen (gebruiker, 24-09)
    "comeon-welkomstbonus-dubbel-casino-400-free-spins-bij-comeon",
    "888-casino-welkomstbonus-special-400-free-spins",
}
