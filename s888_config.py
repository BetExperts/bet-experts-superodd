# -*- coding: utf-8 -*-
"""Config voor de 888Sport 60x-je-inzet-agent (deelt Webflow/Telegram met so_config)."""
import os

# Bronpagina met de dagelijkse/actuele 60x-welkomstboost.
PROMO_URL = "https://promo.888.nl/sportsbook-welkomstbonus-boost"

# Evergreen CMS-item (Promoties) met de vaste slug — alleen inhoud wordt bijgewerkt.
ITEM_ID = "6a2e68703f9feeabc2020aa8"
SLUG    = "888sport-odd-boosts-pak-60-00x-je-inzet"

# Afbeelding voor het Telegram-bericht.
IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "888-60x.jpg")

# State (aparte sleutel/bestand).
STATE_KEY = "888_60x"
