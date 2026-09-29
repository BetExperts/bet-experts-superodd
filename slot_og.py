# -*- coding: utf-8 -*-
"""Deelafbeeldingen (1200x630 .webp) voor de Slots-collectie.

  python slot_og.py --all                 # alle slots renderen naar assets/slots/
  python slot_og.py gates-of-olympus      # één of meer slugs
  python slot_og.py --all --attach        # + commit/push en 'deelafbeelding' in Webflow zetten
  python slot_og.py --preview gates-of-olympus   # schrijft ook een .png naar $SLOT_OG_PREVIEW (standaard /tmp)

Voor de slot-agent: `render_slot(info) -> bytes` en `attach(slug_to_file)` zijn herbruikbaar;
`info_from_item(item, provider_names)` maakt de info uit een Webflow-item.
Vereist: playwright (chromium) en Pillow (zie requirements.txt).
"""
import base64, hashlib, html, io, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "slot-og")
OUT = os.path.join(HERE, "assets", "slots")
RAW = "https://raw.githubusercontent.com/BetExperts/bet-experts-superodd/main/assets/slots/"
SLOTS, PROVIDERS = "6abbdb3436d326e0b5292850", "6abbdb32ec098f3c93d66937"


def _env():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _wf(path, method="GET", body=None):
    r = urllib.request.Request("https://api.webflow.com/v2" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": "Bearer " + os.environ["WEBFLOW_TOKEN"],
                                        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as x:
        return json.load(x) if method == "GET" else x.status


def _all_items(cid):
    items, off = [], 0
    while True:
        d = _wf(f"/collections/{cid}/items?limit=100&offset={off}")
        items += d["items"]
        off += 100
        if off >= d["pagination"]["total"]:
            return items


# ---------- waarden netjes maken voor het beeld ----------

def fmt_maxwin(v):
    v = (v or "").strip()
    if not v:
        return None
    if re.search(r"geen.*limiet", v, re.I):
        return "Geen limiet"
    xs = re.findall(r"(\d{1,3}(?:\.\d{3})+|\d+)\s*x", v)
    if xs:
        best = max(xs, key=lambda s: int(s.replace(".", "")))
        return best + "x" + (" lijninzet" if "lijninzet" in v else "")
    m = re.search(r"€\s?[\d.,]+", v)
    return m.group(0).replace(" ", "") if m else None


def fmt_raster(v):
    v = (v or "").strip()
    return re.split(r"\s*[(+]", v)[0].strip() or None if v else None


VOL = {"laag": 1, "laag-gemiddeld": 2, "laag tot gemiddeld": 2, "gemiddeld": 3,
       "gemiddeld-hoog": 4, "hoog": 4, "zeer hoog": 5, "extreem hoog": 5}


def verdict(score):
    return ("Uitstekend" if score >= 9 else "Zeer goed" if score >= 8 else
            "Goed" if score >= 7 else "Redelijk" if score >= 6 else "Matig")


def num(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def tagline_from(fd):
    t = (fd.get("deelregel") or "").strip()
    if t:
        return t
    first = re.split(r"(?<=\.)\s", (fd.get("intro") or "").strip())[0]
    first = first.split(",")[0].rstrip(".")
    return first + "." if 0 < len(first) <= 60 else ""


def info_from_item(item, provider_names):
    fd = item["fieldData"]
    stats = []
    if fd.get("rtp"):
        stats.append(("RTP", fd["rtp"], None))
    vol = (fd.get("volatiliteit") or "").strip()
    if vol and vol.lower() in VOL:
        stats.append(("Volatiliteit", vol, VOL[vol.lower()]))
    mw = fmt_maxwin(fd.get("max-winst"))
    if mw:
        stats.append(("Max. winst", mw, "green"))
    for label, val in (("Raster", fmt_raster(fd.get("raster"))), ("Winlijnen", fd.get("winlijnen"))):
        if len(stats) < 3 and val:
            stats.append((label, val, None))
    img = (fd.get("afbeelding") or {}).get("url")
    return {
        "slug": fd["slug"], "naam": fd["name"], "provider": provider_names.get(fd.get("provider"), ""),
        "tagline": tagline_from(fd), "demo": bool(fd.get("slotslaunch-game-id")), "thumb": img,
        "score": num(fd.get("onze-beoordeling")),
        "subs": [(k, num(fd.get(f))) for k, f in (("Gameplay", "gameplay-score"), ("Bonusronde", "bonusronde-score"),
                                                   ("Uitbetaling", "uitbetaling-score")) if num(fd.get(f)) is not None],
        "stats": stats[:3],
    }


# ---------- HTML ----------

def _data_uri(path_or_bytes, mime):
    b = open(path_or_bytes, "rb").read() if isinstance(path_or_bytes, str) else path_or_bytes
    return f"data:{mime};base64," + base64.b64encode(b).decode()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BetExperts og-render)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get_content_type()


_FONTS = None


def _fonts_css():
    global _FONTS
    if _FONTS is None:
        faces = [("Poppins", 600, "Poppins-SemiBold"), ("Poppins", 700, "Poppins-Bold"),
                 ("Jakarta", 500, "PlusJakartaSans-Medium"), ("Jakarta", 600, "PlusJakartaSans-SemiBold"),
                 ("Jakarta", 700, "PlusJakartaSans-Bold")]
        _FONTS = "".join(
            f"@font-face{{font-family:{fam};font-weight:{w};src:url({_data_uri(os.path.join(ASSETS, 'fonts', f + '.ttf'), 'font/ttf')})}}"
            for fam, w, f in faces)
    return _FONTS


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1200px;height:630px;overflow:hidden}
body{background:#0a1016;font-family:Jakarta,sans-serif;color:#f4f7f9;position:relative;-webkit-font-smoothing:antialiased}
.bg{position:absolute;inset:0;background:
  radial-gradient(620px 440px at 0% 0%,rgba(22,154,71,.28),transparent 70%),
  radial-gradient(560px 380px at 100% 100%,rgba(22,154,71,.13),transparent 70%)}
.topbar{position:absolute;top:0;left:0;width:760px;height:4px;background:linear-gradient(90deg,#169a47,rgba(22,154,71,0))}
.brand{position:absolute;top:40px;left:100px;height:32px}
.domain{position:absolute;top:44px;right:100px;font-weight:700;font-size:18px;color:#5fcf86;letter-spacing:.005em}
.left{position:absolute;top:118px;left:100px;width:580px}
.eyebrow{display:flex;align-items:center;height:28px;white-space:nowrap}
.eyebrow .bar{width:4px;height:16px;background:#169a47;border-radius:1px;margin-right:12px}
.eyebrow .kind{font-weight:700;font-size:14px;letter-spacing:.14em;color:#6fcf8f}
.eyebrow .dot{width:4px;height:4px;border-radius:50%;background:#4a5663;margin:0 12px}
.eyebrow .prov{font-weight:600;font-size:15px;color:#f4f7f9}
.pill{display:inline-flex;align-items:center;gap:7px;margin-left:14px;height:26px;padding:0 13px 0 11px;border-radius:999px;
  background:linear-gradient(180deg,#5fcf86,#3fb56b);color:#08130d;font-weight:700;font-size:11px;letter-spacing:.1em;
  box-shadow:0 0 0 1px rgba(95,207,134,.35),0 6px 16px rgba(22,154,71,.28)}
.pill svg{width:8px;height:9px}
h1{margin-top:14px;font-family:Poppins;font-weight:700;font-size:58px;line-height:1.08;letter-spacing:-.02em;color:#fff}
.tag{margin-top:14px;font-weight:500;font-size:20px;line-height:1.4;color:#a7b1bc;white-space:nowrap}
.cards{position:absolute;left:100px;top:392px;width:560px;height:166px;display:flex;gap:16px}
.thumb{width:249px;height:166px;flex:none;border-radius:16px;overflow:hidden;position:relative;background:#16202a;
  box-shadow:0 18px 40px rgba(0,0,0,.45)}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb .ph{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:18px;
  background:radial-gradient(260px 180px at 20% 0%,rgba(95,207,134,.35),transparent 70%),linear-gradient(150deg,#123524,#0d1a14 60%,#0b1117)}
.thumb .ph b{font-family:Poppins;font-weight:700;font-size:24px;line-height:1.1;color:#fff;letter-spacing:-.01em}
.thumb .ph span{margin-top:6px;font-weight:600;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#7ed59b}
.thumb:after{content:"";position:absolute;inset:0;border-radius:16px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.09)}
.stats{flex:1;border-radius:16px;background:rgba(19,28,37,.82);border:1px solid #213040;padding:0 18px;display:flex;flex-direction:column}
.row{flex:1;display:flex;align-items:center;justify-content:space-between;gap:10px}
.row+.row{border-top:1px solid #1f2b37}
.row .l{font-weight:700;font-size:11px;letter-spacing:.13em;color:#7c8793;text-transform:uppercase;white-space:nowrap}
.row .v{font-family:Poppins;font-weight:600;font-size:21px;color:#fff;white-space:nowrap;letter-spacing:-.005em}
.row .v.green{color:#5fcf86}
.vol{display:flex;align-items:center;gap:9px}
.segs{display:flex;gap:3px}
.segs i{display:block;width:12px;height:6px;border-radius:3px;background:#27333f}
.segs i.on{background:#5fcf86}
.vol b{font-weight:700;font-size:14px;color:#fff;white-space:nowrap}
.score{position:absolute;left:720px;top:118px;width:380px;height:440px;border-radius:24px;padding:34px 36px 32px 36px;
  background:linear-gradient(160deg,#16222c 0%,#0f1820 100%);border:1px solid #223140;border-left:5px solid #169a47;
  box-shadow:0 30px 70px rgba(0,0,0,.45);display:flex;flex-direction:column}
.score .lab{font-weight:700;font-size:13px;letter-spacing:.16em;color:#8792a0}
.score .big{display:flex;align-items:baseline;gap:10px;margin-top:10px}
.score .big b{font-family:Poppins;font-weight:700;font-size:92px;line-height:1;letter-spacing:-.03em;color:#fff}
.score .big span{font-family:Poppins;font-weight:600;font-size:26px;color:#6b7785}
.score .verd{margin-top:14px;font-family:Poppins;font-weight:600;font-size:20px;color:#5fcf86}
.score .sp{flex:1}
.score .div{height:1px;background:#243240;margin-bottom:22px}
.sub+.sub{margin-top:18px}
.sub .t{display:flex;justify-content:space-between;font-size:16px;font-weight:500;color:#c6ced6}
.sub .t b{font-weight:700;color:#fff}
.sub .tr{margin-top:9px;height:6px;border-radius:3px;background:#243140;overflow:hidden}
.sub .tr i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#3fb56b,#5fcf86)}
.foot{position:absolute;left:100px;top:580px;display:flex;align-items:center;gap:12px;font-size:13px;font-weight:500;color:#7c8793}
.foot .age{height:22px;padding:0 8px;border:1px solid #37434f;border-radius:999px;display:flex;align-items:center;font-weight:700;font-size:11px;color:#c6ced6}
"""

PLAY = '<svg viewBox="0 0 8 9"><path d="M0 0l8 4.5L0 9z" fill="#08130d"/></svg>'


def _page(info, thumb_uri, logo_uri):
    e = lambda s: html.escape(str(s), quote=True)
    f1 = lambda v: f"{v:.1f}".replace(".", ",")
    rows = []
    for label, val, kind in info["stats"]:
        if isinstance(kind, int):
            segs = "".join(f'<i class="{"on" if n < kind else ""}"></i>' for n in range(5))
            v = f'<div class="vol"><div class="segs">{segs}</div><b>{e(val)}</b></div>'
        else:
            v = f'<div class="v{" green" if kind == "green" else ""}">{e(val)}</div>'
        rows.append(f'<div class="row"><div class="l">{e(label)}</div>{v}</div>')
    subs = "".join(
        f'<div class="sub"><div class="t"><span>{e(k)}</span><b>{f1(v)}</b></div>'
        f'<div class="tr"><i style="width:{max(0, min(100, v * 10)):.1f}%"></i></div></div>' for k, v in info["subs"])
    score = info["score"] or 0
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_fonts_css()}{CSS}</style></head><body>
<div class="bg"></div><div class="topbar"></div>
<img class="brand" src="{logo_uri}"><div class="domain">bet-experts.nl</div>
<div class="left">
  <div class="eyebrow"><span class="bar"></span><span class="kind">SLOT REVIEW</span>
    {'<span class="dot"></span><span class="prov">' + e(info["provider"]) + '</span>' if info["provider"] else ''}
    {'<span class="pill">' + PLAY + 'DEMO SPELEN</span>' if info["demo"] else ''}</div>
  <h1 id="h1">{e(info["naam"])}</h1>
  {'<div class="tag" id="tag">' + e(info["tagline"]) + '</div>' if info["tagline"] else ''}
</div>
<div class="cards">
  <div class="thumb">{'<img src="' + thumb_uri + '">' if thumb_uri else '<div class="ph"><b>' + e(info["naam"]) + '</b><span>' + e(info["provider"]) + '</span></div>'}</div>
  <div class="stats">{''.join(rows)}</div>
</div>
<div class="score"><div class="lab">ONZE BEOORDELING</div>
  <div class="big"><b>{f1(score)}</b><span>/10</span></div>
  <div class="verd">{verdict(score)}</div><div class="sp"></div><div class="div"></div>{subs}</div>
<div class="foot"><span class="age">18+</span>Wat kost gokken jou? Stop op tijd.</div>
</body></html>"""


# Titel en regel passend maken: titel max. 2 regels en niet onder de kaarten; regel op één regel.
FIT_JS = """() => {
  const h = document.getElementById('h1'), t = document.getElementById('tag'), eb = document.querySelector('.eyebrow');
  const limitBottom = 372;
  let fs = 58;
  const bottom = () => (t || h).getBoundingClientRect().bottom;
  const lines = () => Math.round(h.getBoundingClientRect().height / (fs * 1.08));
  while (fs > 34 && (lines() > 2 || bottom() > limitBottom || h.scrollWidth > 580)) { fs -= 2; h.style.fontSize = fs + 'px'; }
  if (t) { let ts = 20; while (ts > 15 && t.scrollWidth > 580) { ts -= 1; t.style.fontSize = ts + 'px'; } }
  let es = 1; while (eb.scrollWidth > 580 && es > 0.8) { es -= 0.04; eb.style.transform = `scale(${es})`; eb.style.transformOrigin = 'left center'; }
  document.querySelectorAll('.row').forEach(r => { const v = r.lastElementChild; let s = 21;
    while (r.scrollWidth > r.clientWidth + 1 && s > 14 && v.classList.contains('v')) { s -= 1; v.style.fontSize = s + 'px'; } });
  return {fs, overflow: [...document.querySelectorAll('.row')].some(r => r.scrollWidth > r.clientWidth + 1)};
}"""


class Renderer:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._logo = _data_uri(os.path.join(ASSETS, "betexperts-logo.svg"), "image/svg+xml")

    def render(self, info):
        """-> (webp-bytes, png-bytes)"""
        from PIL import Image
        thumb = None
        if info.get("thumb"):
            try:
                b, mt = _fetch(info["thumb"])
                thumb = _data_uri(b, mt or "image/jpeg")
            except Exception as ex:
                print(f"   ! afbeelding niet op te halen voor {info['slug']}: {ex}")
        page = self._browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
        page.set_content(_page(info, thumb, self._logo), wait_until="load")
        page.evaluate("document.fonts.ready")
        fit = page.evaluate(FIT_JS)
        if fit.get("overflow"):
            print(f"   ! waarde past niet helemaal: {info['slug']}")
        png = page.screenshot(type="png")
        page.close()
        im = Image.open(io.BytesIO(png)).convert("RGB").resize((1200, 630), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=90, method=6)
        pv = io.BytesIO()
        im.save(pv, "PNG")
        return out.getvalue(), pv.getvalue()

    def close(self):
        self._browser.close()
        self._pw.stop()


def render_slot(info, renderer=None):
    r = renderer or Renderer()
    try:
        return r.render(info)[0]
    finally:
        if renderer is None:
            r.close()


def save(info, webp):
    """Schrijft assets/slots/<slug>-<hash>.webp (hash in de naam, zodat Webflow een nieuwe versie ophaalt)."""
    os.makedirs(OUT, exist_ok=True)
    name = f"{info['slug']}-{hashlib.md5(webp).hexdigest()[:6]}.webp"
    for old in os.listdir(OUT):
        if old.startswith(info["slug"] + "-") and old != name and re.fullmatch(re.escape(info["slug"]) + r"-[0-9a-f]{6}\.webp", old):
            os.remove(os.path.join(OUT, old))
    open(os.path.join(OUT, name), "wb").write(webp)
    return name


def attach(files, items_by_slug):
    """Commit + push assets/slots en zet 'deelafbeelding' (staged en, indien gepubliceerd, live)."""
    subprocess.run(["git", "add", "-A", "assets/slots"], cwd=HERE, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode:
        subprocess.run(["git", "commit", "-m", f"Slot-deelafbeeldingen ({len(files)})\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"], cwd=HERE, check=True)
        for _ in range(3):
            if subprocess.run(["git", "push"], cwd=HERE).returncode == 0:
                break
            subprocess.run(["git", "pull", "--rebase", "--autostash", "-X", "theirs"], cwd=HERE)
    staged, live = [], []
    for slug, name in files.items():
        it = items_by_slug[slug]
        row = {"id": it["id"], "fieldData": {"deelafbeelding": {"url": RAW + name, "alt": it["fieldData"]["name"] + " review"}}}
        staged.append(row)
        if it.get("lastPublished"):
            live.append(row)
    for path, rows in (("items", staged), ("items/live", live)):
        for i in range(0, len(rows), 25):
            print("PATCH", path, _wf(f"/collections/{SLOTS}/{path}", "PATCH", {"items": rows[i:i + 25]}))


def main(argv):
    _env()
    slugs = [a for a in argv if not a.startswith("--")]
    items = _all_items(SLOTS)
    provs = {p["id"]: p["fieldData"]["name"] for p in _all_items(PROVIDERS)}
    by_slug = {i["fieldData"]["slug"]: i for i in items}
    todo = list(by_slug) if "--all" in argv else slugs
    r = Renderer()
    files = {}
    try:
        for slug in todo:
            info = info_from_item(by_slug[slug], provs)
            webp, png = r.render(info)
            files[slug] = save(info, webp)
            if "--preview" in argv:
                pdir = os.environ.get("SLOT_OG_PREVIEW", "/tmp")
                open(os.path.join(pdir, f"slot-og-{slug}.png"), "wb").write(png)
            print(f"   ✓ {files[slug]}  ({len(webp) // 1024} kB)")
    finally:
        r.close()
    if "--attach" in argv:
        attach(files, by_slug)


if __name__ == "__main__":
    main(sys.argv[1:])
