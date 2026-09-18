# -*- coding: utf-8 -*-
"""Config voor de Oranje Palace Super Odd-agent (deelt Webflow/Telegram met so_config)."""

# Bron: de dagelijkse 'Lucky's Boost' op de sport-homepage.
HOME = "https://www.oranjepalace.nl/nl/sport#home"

# Oranje Palace draait op Kambi; publieke offering-API (brand 'hgtnl').
KAMBI_BRAND = "hgtnl"
KAMBI_API   = f"https://eu-offering-api.kambicdn.com/offering/v2018/{KAMBI_BRAND}"

# Evergreen CMS-item (Promoties) dat dagelijks/uurlijks wordt bijgewerkt.
OP_ITEM_ID = "6aad0e95a9e2428f79776379"
OP_SLUG    = "oranje-palace-super-odd"

# Bookmaker-item in de Bookmakers-collectie (referentie/logo/affiliate).
BOOKMAKER_ID = "6aad0c21a14e9435daf42e79"

# State (aparte sleutel, los van bet365/toto).
STATE_KEY = "oranjepalace"
