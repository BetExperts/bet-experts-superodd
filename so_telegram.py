# -*- coding: utf-8 -*-
"""Stuurt een Telegram-bericht met de link naar het Super-Odd-artikel.

Losstaand van de telegram_agent-repo; hergebruikt alleen dezelfde bot-token en
kanaalconventie (TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL).
"""
import requests
from so_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT, DISCLAIMER

def send(text, promo_url, test=False):
    if not TELEGRAM_BOT_TOKEN:
        print("  · Telegram overgeslagen (geen TELEGRAM_BOT_TOKEN gezet).")
        return False
    chat_id = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if test and not TELEGRAM_TEST_CHAT:
        print("  · Testmodus maar geen TELEGRAM_TEST_CHAT gezet — niets verstuurd.")
        return False
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": {"inline_keyboard": [[
            {"text": "Bekijk de Boost →", "url": promo_url}
        ]]},
    }
    r = requests.post(api, json=body, timeout=20)
    r.raise_for_status()
    return True

def build_message(data, promo_url):
    """Teaser: wél de wedstrijd + de odd-boost, NIET wat er geboost wordt
    (dat lezen ze in het artikel). Knop 'Bekijk de Boost →' staat eronder."""
    match = data["match"].replace(" v ", " - ")
    old_o, new_o = data["old_odd"], data["new_odd"]
    lines = [
        "🔥 <b>Bet365 Super Odd LIVE!</b>",
        "",
        f"⚽ <b>{match}</b>",
        f"📈 Quotering geboost: <s>{old_o}</s> → <b>{new_o}</b>",
        "",
        f"<i>{DISCLAIMER}</i>",
    ]
    return "\n".join(lines)
