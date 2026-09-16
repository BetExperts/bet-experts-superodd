# -*- coding: utf-8 -*-
"""Config voor de TOTO 50x-je-inzet-agent (deelt Webflow/Telegram met so_config)."""
import os

# Bron: de TOTO welkomstbonus-sportpagina noemt de dagelijkse 50x-wedstrijd.
TOTO_URL = "https://www.toto.nl/welkomstbonus/sport"

# Bestaand CMS-item (alleen de TITEL wordt dagelijks bijgewerkt; body blijft).
TOTO_ITEM_ID = "67865ef6d4531cbd03e8f9f1"
TOTO_SLUG    = "toto-50x-je-inzet"

# Afbeelding voor het Telegram-bericht (uit de CMS, omgezet naar jpg).
TOTO_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "toto-50x.jpg")

# State (aparte sleutel/bestand, los van de Bet365-agent).
STATE_KEY = "toto"
