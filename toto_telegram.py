# -*- coding: utf-8 -*-
"""Telegram sendPhoto voor de TOTO 50x-actie (foto + bijschrift + knop)."""
import json, requests
from so_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL, TELEGRAM_TEST_CHAT
from toto_config import TOTO_IMAGE

def send_photo(caption, promo_url, test=False):
    if not TELEGRAM_BOT_TOKEN:
        print("  · Telegram overgeslagen (geen TELEGRAM_BOT_TOKEN)."); return False
    chat_id = TELEGRAM_TEST_CHAT if test else TELEGRAM_CHANNEL
    if test and not TELEGRAM_TEST_CHAT:
        print("  · Testmodus maar geen TELEGRAM_TEST_CHAT."); return False
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps({"inline_keyboard": [[
            {"text": "Bekijk de actie →", "url": promo_url}
        ]]}),
    }
    with open(TOTO_IMAGE, "rb") as f:
        r = requests.post(api, data=data, files={"photo": f}, timeout=30)
    r.raise_for_status()
    return True
