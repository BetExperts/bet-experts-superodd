# -*- coding: utf-8 -*-
"""Titel + Telegram-tekst voor de TOTO 50x-actie."""

def build_title(data, live=False):
    """CMS-titel. Zodra de wedstrijd live is (live=True) geen teamnamen meer (KSA)."""
    if live:
        return "TOTO: 50x je inzet — pak €50 aan Free Bets!"
    teams = data["teams"]
    if len(teams) >= 2:
        return f"TOTO: 50x je inzet — zet €1 op {teams[0]} of {teams[1]} en win €50!"
    return f"TOTO: 50x je inzet — zet €1 op winst {teams[0]} en win €50!"

def telegram_caption(data):
    """Mooi teaser-bijschrift onder de TOTO 50x-afbeelding."""
    teams = data["teams"]
    if len(teams) >= 2:
        wed = f"<b>{teams[0]} - {teams[1]}</b>"
        keuze = f"Zet max. €1 op winst {teams[0]} óf {teams[1]}"
    else:
        wed = f"<b>{teams[0]}</b>"
        keuze = f"Zet max. €1 op winst {teams[0]}"
    return (
        "🟢 <b>TOTO 50x je inzet!</b> ⚽\n"
        f"NIEUW: {wed}\n\n"
        f"{keuze} en pak <b>50x je inleg</b>: jouw €1 wordt <b>€50 aan Free Bets</b>! 💸\n"
        "✅ Nieuw bij TOTO Sport · max. €1 inzet · uitbetaling in Free Bets (7 dagen geldig)\n\n"
        "<i>Wat kost gokken jou? Stop op tijd. 18+ | Speel bewust.</i>"
    )
