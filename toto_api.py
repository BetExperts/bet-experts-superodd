# -*- coding: utf-8 -*-
"""Zoekt de aftraptijd van de TOTO 50x-wedstrijd op via api-sports (direct key).

De toto.nl-pagina noemt alleen de teams, niet de datum. We zoeken per team het
team-id op en vragen het eerstvolgende onderlinge duel op → dat is de wedstrijd
waar de 50x-actie voor geldt. De aftrap = "geldig tot" van de promotie.
"""
import os, requests
from datetime import datetime, timedelta, timezone

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("APISPORTS_KEY", "").strip()

FINISHED = {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}

def _get(path, **params):
    r = requests.get(f"{BASE}/{path}", headers={"x-apisports-key": KEY},
                     params=params, timeout=25)
    r.raise_for_status()
    return r.json().get("response", []) or []

def _team_id(name):
    """Beste team-id voor een naam. Voorkeur voor een exacte naam-match."""
    res = _get("teams", search=name)
    if not res:
        return None
    low = name.strip().lower()
    for t in res:                      # exacte naam eerst (bv. 'Excelsior')
        if t["team"]["name"].strip().lower() == low:
            return t["team"]["id"]
    return res[0]["team"]["id"]         # anders de meest relevante hit

def _valid_upcoming(fx):
    """Alleen accepteren als het duel nog moet komen en binnen ~5 dagen valt
    (voorkomt dat een naam-mismatch een duel over weken oppikt)."""
    if fx["fixture"]["status"]["short"] in FINISHED:
        return False
    try:
        dt = datetime.fromisoformat(fx["fixture"]["date"])
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    return (now - timedelta(hours=6)) <= dt <= (now + timedelta(days=5))

def kickoff_for(teams):
    """Return ISO-aftraptijd (UTC, met offset) van de 50x-wedstrijd, of None.

    teams = ['Ajax', 'Excelsior'] (of één team). Bij twee teams gebruiken we het
    eerstvolgende onderlinge duel; bij één team de eerstvolgende wedstrijd."""
    if not KEY:
        raise RuntimeError("APISPORTS_KEY ontbreekt")
    ids = []
    for name in teams[:2]:
        tid = _team_id(name)
        if tid:
            ids.append(tid)
    if not ids:
        return None

    if len(ids) >= 2:
        res = _get("fixtures/headtohead", h2h=f"{ids[0]}-{ids[1]}", next=1)
    else:
        res = _get("fixtures", team=ids[0], next=1)

    if not res:
        return None
    fx = res[0]
    if not _valid_upcoming(fx):
        return None
    return fx["fixture"]["date"]        # bv. '2026-09-19T18:00:00+00:00'

if __name__ == "__main__":
    import sys
    print(kickoff_for(sys.argv[1:] or ["Ajax", "Excelsior"]))
