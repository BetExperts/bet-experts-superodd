# -*- coding: utf-8 -*-
"""Configuratie voor de Bet365 Super-Odd-agent."""
import os

# --- Webflow ---
WEBFLOW_TOKEN        = os.environ.get("WEBFLOW_TOKEN", "").strip()
WF_API               = "https://api.webflow.com/v2"
PROMOTIES_COLLECTION = "65e6fb5b08aed95b983b590f"

# Rubriek "SuperOdd" (Promotie Rubrieken-collectie 65e71837e04f7160201506cf)
RUBRIEK_SUPERODD = "6aaa9afdf92f60c1aeff6a58"

# Bet365 in de Bookmakers-collectie (ref-veld bookmaker-3 + multiref bookmakers)
BET365_BOOKMAKER = "651bd6728c40de720bd8072a"

# Bet365 sport-affiliatelink (nooit gokken — deze staat vast in de CMS)
BET365_AFFILIATE = "https://www.bet365.nl/hub/nl-nl/open-account?affiliate=365_02599619"

# geldig-voor optie: Sport
GELDIG_VOOR_SPORT = "9c0fbc22d905260428d1de2988b86dea"

# --- Bronpagina ---
BET365_URL = "https://www.bet365.nl"

# Evergreen: één vast CMS-item per bookmaker dat dagelijks/uurlijks wordt
# bijgewerkt (beter voor SEO dan elke dag een nieuw item). Vaste slug:
SUPERODD_SLUG = "bet365-super-odd"
STATE_KEY     = "bet365"   # sleutel in state/superodd.json

# --- Publieke promotie-URL (voor de Telegram-link) ---
PROMO_BASE = "https://www.bet-experts.nl/promoties/"

# --- Telegram (zelfde conventie als de telegram_agent-repo) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# Doelkanaal: @username of numeriek -100... id. Default = het echte kanaal.
TELEGRAM_CHANNEL   = os.environ.get("TELEGRAM_CHANNEL") or "@BetExpertsGroup"
# Aparte testbestemming (je eigen user-id of testkanaal) voor --test.
TELEGRAM_TEST_CHAT = os.environ.get("TELEGRAM_TEST_CHAT", "").strip()

# Disclaimer (verplicht, KSA)
DISCLAIMER = "Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust."
