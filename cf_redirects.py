# -*- coding: utf-8 -*-
"""Cloudflare Bulk Redirects: 301's toevoegen aan de account-lijst (standaard 'oude_artikelen').
Token (CLOUDFLARE_API_TOKEN) heeft alleen 'Account Filter Lists: Edit'.

  python3 cf_redirects.py --list                       # lijsten + aantallen tonen
  python3 cf_redirects.py --csv bestand.csv            # regels uit CSV (bron,doel,301) toevoegen
"""
import os, sys, csv, time, argparse
import requests

API = "https://api.cloudflare.com/client/v4"
LIST_NAME = os.environ.get("CLOUDFLARE_REDIRECT_LIST", "oude_artikelen")

def _h():
    return {"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"].strip(), "Content-Type": "application/json"}

def _acc():
    acc = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not acc:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID ontbreekt in .env")
    return acc

def lists():
    r = requests.get(f"{API}/accounts/{_acc()}/rules/lists", headers=_h(), timeout=30)
    r.raise_for_status()
    return r.json()["result"]

def list_id(name=LIST_NAME):
    for l in lists():
        if l["name"] == name and l["kind"] == "redirect":
            return l["id"]
    raise RuntimeError(f"redirect-lijst '{name}' niet gevonden")

def existing_sources(lid):
    out, cursor = set(), None
    while True:
        r = requests.get(f"{API}/accounts/{_acc()}/rules/lists/{lid}/items", headers=_h(),
                         params={"cursor": cursor} if cursor else None, timeout=30)
        r.raise_for_status()
        j = r.json()
        out |= {i["redirect"]["source_url"].lower() for i in j["result"] if i.get("redirect")}
        cursor = ((j.get("result_info") or {}).get("cursors") or {}).get("after")
        if not cursor:
            return out

def add(rows, name=LIST_NAME, wait=True):
    """rows: [(bron-zonder-schema, doel-url, 301)] -> aantal toegevoegd (dubbele bronnen overgeslagen)."""
    lid = list_id(name)
    have = existing_sources(lid)
    items = []
    for src, dst, code in rows:
        src = src.replace("https://", "").replace("http://", "").strip()
        if src.lower() in have:
            continue
        items.append({"redirect": {"source_url": src, "target_url": dst, "status_code": int(code)}})
    if not items:
        return 0
    r = requests.post(f"{API}/accounts/{_acc()}/rules/lists/{lid}/items", headers=_h(), json=items, timeout=60)
    r.raise_for_status()
    op = r.json()["result"]["operation_id"]
    for _ in range(30 if wait else 0):
        s = requests.get(f"{API}/accounts/{_acc()}/rules/lists/bulk_operations/{op}", headers=_h(), timeout=30).json()["result"]
        if s["status"] in ("completed", "failed"):
            if s["status"] == "failed":
                raise RuntimeError(f"bulk-operatie mislukt: {s.get('error')}")
            break
        time.sleep(2)
    return len(items)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--csv")
    a = ap.parse_args()
    if a.list:
        for l in lists():
            print(l["id"], l["name"], l["kind"], l["num_items"])
    if a.csv:
        rows = [r for r in csv.reader(open(a.csv, encoding="utf-8")) if len(r) >= 3]
        print("toegevoegd:", add(rows))


def remove(sources, name=LIST_NAME):
    """Verwijdert redirects op bron-URL (zonder schema). Retourneert het aantal verwijderde regels."""
    lid = list_id(name)
    want = {s.replace("https://", "").replace("http://", "").strip().lower() for s in sources}
    ids, cursor = [], None
    while True:
        r = requests.get(f"{API}/accounts/{_acc()}/rules/lists/{lid}/items", headers=_h(),
                         params={"cursor": cursor} if cursor else None, timeout=30)
        r.raise_for_status(); j = r.json()
        ids += [i["id"] for i in j["result"] if i.get("redirect") and i["redirect"]["source_url"].lower() in want]
        cursor = ((j.get("result_info") or {}).get("cursors") or {}).get("after")
        if not cursor:
            break
    if not ids:
        return 0
    r = requests.delete(f"{API}/accounts/{_acc()}/rules/lists/{lid}/items", headers=_h(),
                        json={"items": [{"id": i} for i in ids]}, timeout=60)
    r.raise_for_status()
    return len(ids)
