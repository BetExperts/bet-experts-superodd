# -*- coding: utf-8 -*-
"""Webflow Data API v2 — create/update/publish van promotie-items + state."""
import os, json
import requests
from so_config import WEBFLOW_TOKEN, WF_API, PROMOTIES_COLLECTION

BASE  = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "state", "superodd.json")

def _headers():
    return {
        "Authorization": f"Bearer {WEBFLOW_TOKEN}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def create_live(field_data):
    """Maak het item aan én publiceer het meteen (live endpoint)."""
    url = f"{WF_API}/collections/{PROMOTIES_COLLECTION}/items/live"
    body = {"isArchived": False, "isDraft": False, "fieldData": field_data}
    r = requests.post(url, headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json().get("id")

def update_item(item_id, field_data):
    """Update velddata van een bestaand (live) item en publiceer het opnieuw."""
    url = f"{WF_API}/collections/{PROMOTIES_COLLECTION}/items/{item_id}/live"
    body = {"isArchived": False, "isDraft": False, "fieldData": field_data}
    r = requests.patch(url, headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json().get("id", item_id)
