# -*- coding: utf-8 -*-
"""Deelafbeeldingen (1200x630 .webp) voor de Casino providers-collectie. Zelfde motor als slot_og.py.

  python provider_og.py --all                  # alle gepubliceerde providers
  python provider_og.py pragmatic-play --preview
  python provider_og.py --all --attach         # + push en 'deelafbeelding' in Webflow (staged + live)
"""
import html, io, os, re, sys
from slot_og import (HERE, PROVIDERS, Renderer, _all_items, _env, _fetch, _data_uri, _fonts_css, attach, num, save,
                     verdict)

OUT = os.path.join(HERE, "assets", "providers")


# ---------- waarden ----------

def nl_chip(status):
    m = re.search(r"(\d+)\s+van\s+(?:de\s+)?(\d+)", status or "")
    return f"{m.group(1)} van de {m.group(2)} NL-casino's" if m and int(m.group(1)) > 0 else None


def games_chip(v):
    v = (v or "").strip()
    if not v or "(" in v:                       # bv. 'hele netwerk, inclusief zustermerken' -> niet op het beeld
        return None
    m = re.search(r"(\d[\d.]*)", v)
    if not m:
        return None
    n = m.group(1)
    plus = "+" in v or re.search(r"meer dan|ruim", v, re.I)
    kind = re.search(r"(slingo-spellen|slots|spellen)", v, re.I)
    return f"{n}{'+' if plus else ''} {kind.group(1) if kind else 'spellen'}"


def top_label(titel):
    t = (titel or "").lower()
    return "TOP LIVE SPELLEN" if "live" in t else "TOP SPELLEN" if "spellen" in t else "TOP SLOTS"


def initials(name):
    w = [x for x in re.split(r"[\s&']+", name) if x and x[0].isalnum()]
    return ("".join(x[0] for x in w[:2]) if len(w) > 1 else name[:2]).upper()


def prep_logo(b):
    """Logo bijsnijden tot de inhoud en de tegel erop afstemmen.
    -> (png-bytes, tegelkleur, breedte/hoogte-verhouding van de inhoud)"""
    from PIL import Image
    im = Image.open(io.BytesIO(b)).convert("RGBA")
    lum = lambda p: 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]
    a = im.getchannel("A")
    if a.getextrema()[0] < 200:                                   # transparant logo
        bbox = a.point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, *im.size)
        crop = im.crop(bbox)
        px = [p for p in crop.resize((80, 80)).getdata() if p[3] > 128]
        light = px and sum(map(lum, px)) / len(px) > 190
        bg = "#16212b" if light else "#ffffff"
    else:                                                         # logo met eigen achtergrond
        rgb = im.convert("RGB")
        w, h = rgb.size
        edge = [rgb.getpixel((x, y)) for x in range(0, w, max(1, w // 40)) for y in (0, h - 1)] + \
               [rgb.getpixel((x, y)) for y in range(0, h, max(1, h // 40)) for x in (0, w - 1)]
        ec = tuple(sorted(c[i] for c in edge)[len(edge) // 2] for i in range(3))
        from PIL import ImageChops
        mask = ImageChops.difference(rgb, Image.new("RGB", rgb.size, ec)).convert("L").point(lambda v: 255 if v > 38 else 0)
        bbox = mask.getbbox() or (0, 0, w, h)
        crop = im.crop(bbox)
        bg = "#%02x%02x%02x" % ec
    out = io.BytesIO()
    crop.save(out, "PNG")
    return out.getvalue(), bg, crop.size[0] / max(1, crop.size[1])


def info_from_item(item):
    fd = item["fieldData"]
    chips = [c for c in (nl_chip(fd.get("status-nederland")), games_chip(fd.get("aantal-spellen"))) if c]
    if len(chips) < 2 and fd.get("opgericht"):
        chips.append(f"Sinds {fd['opgericht']}")
    top = []
    for n in (1, 2, 3):
        if fd.get(f"top-slot-{n}"):
            top.append((fd[f"top-slot-{n}"], (fd.get(f"top-slot-{n}-afbeelding") or {}).get("url")))
    subs = [(k, num(fd.get(f))) for k, f in (("Spelaanbod", "spelaanbod-score"), ("RTP", "gemiddelde-rtp-score"),
                                             ("Innovatie", "innovatie-score"), ("Beschikbaarheid NL", "beschikbaarheid-nl-score"))]
    return {"slug": fd["slug"], "naam": fd["name"], "logo": (fd.get("logo") or {}).get("url"),
            "tagline": (fd.get("deelregel") or fd.get("intro") or "").strip(), "chips": chips[:2],
            "label": top_label(fd.get("top-3-titel")), "top": top, "score": num(fd.get("onze-beoordeling")),
            "subs": [(k, v) for k, v in subs if v is not None]}


# ---------- HTML ----------

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1200px;height:630px;overflow:hidden}
body{background:#0a1016;font-family:Jakarta,sans-serif;color:#f4f7f9;position:relative;-webkit-font-smoothing:antialiased}
.bg{position:absolute;inset:0;background:
  radial-gradient(620px 440px at 0% 0%,rgba(22,154,71,.28),transparent 70%),
  radial-gradient(560px 380px at 100% 100%,rgba(22,154,71,.13),transparent 70%)}
.topbar{position:absolute;top:0;left:0;width:760px;height:4px;background:linear-gradient(90deg,#169a47,rgba(22,154,71,0))}
.brand{position:absolute;top:40px;left:100px;height:32px}
.domain{position:absolute;top:44px;right:100px;font-weight:700;font-size:18px;color:#5fcf86}
.left{position:absolute;top:118px;left:100px;width:580px}
.eyebrow{display:flex;align-items:center;height:28px}
.eyebrow .bar{width:4px;height:16px;background:#169a47;border-radius:1px;margin-right:12px}
.eyebrow .kind{font-weight:700;font-size:14px;letter-spacing:.14em;color:#6fcf8f}
.head{display:flex;align-items:center;gap:20px;margin-top:16px}
.logo{height:84px;min-width:84px;flex:none;border-radius:20px;background:#fff;display:flex;align-items:center;justify-content:center;
  overflow:hidden;box-shadow:0 14px 34px rgba(0,0,0,.4),inset 0 0 0 1px rgba(255,255,255,.08)}
.logo img{display:block;object-fit:contain}
.logo .ini{font-family:Poppins;font-weight:700;font-size:28px;color:#0f1a14;letter-spacing:-.01em}
h1{font-family:Poppins;font-weight:700;font-size:52px;line-height:1.06;letter-spacing:-.02em;color:#fff;white-space:nowrap;min-width:0;flex:1}
h1.wrap{white-space:normal}
.tag{margin-top:18px;font-weight:500;font-size:20px;line-height:1.45;color:#a7b1bc;max-width:570px;text-wrap:balance}
.chips{display:flex;gap:10px;margin-top:18px}
.chip{height:36px;padding:0 15px;border-radius:999px;background:#18222c;border:1px solid #273543;display:flex;align-items:center;
  font-weight:700;font-size:15px;color:#f4f7f9;white-space:nowrap}
.chip:first-child{background:rgba(22,154,71,.14);border-color:rgba(95,207,134,.38);color:#bdf0cf}
.tops{position:absolute;left:100px;bottom:72px;width:560px}
.tops .lab{font-weight:700;font-size:11px;letter-spacing:.14em;color:#7c8793;margin-bottom:10px}
.grid{display:flex;gap:16px}
.cell{width:176px}
.tile{position:relative;width:176px;height:117px;border-radius:14px;overflow:hidden;background:#16202a;box-shadow:0 14px 30px rgba(0,0,0,.4)}
.tile img{width:100%;height:100%;object-fit:cover;display:block}
.tile:after{content:"";position:absolute;inset:0;border-radius:14px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.09)}
.tile .ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:18px;
  background:radial-gradient(200px 140px at 20% 0%,rgba(95,207,134,.32),transparent 70%),linear-gradient(150deg,#123524,#0d1a14 60%,#0b1117)}
.tile .ph .lg{border-radius:12px;display:flex;align-items:center;justify-content:center;padding:10px 14px;opacity:.95;
  box-shadow:0 8px 22px rgba(0,0,0,.35)}
.tile .ph .lg img{display:block;object-fit:contain}
.tile .ph .lg span{font-family:Poppins;font-weight:700;font-size:20px;color:#0f1a14}
.num{position:absolute;top:8px;left:8px;width:24px;height:24px;border-radius:7px;background:rgba(8,14,19,.82);
  display:flex;align-items:center;justify-content:center;font-family:Poppins;font-weight:700;font-size:12px;color:#5fcf86;z-index:2;
  box-shadow:inset 0 0 0 1px rgba(95,207,134,.3)}
.cell .n{margin-top:9px;font-weight:700;font-size:14px;color:#f4f7f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.score{position:absolute;left:720px;top:118px;width:380px;height:440px;border-radius:24px;padding:34px 36px 32px 36px;
  background:linear-gradient(160deg,#16222c 0%,#0f1820 100%);border:1px solid #223140;border-left:5px solid #169a47;
  box-shadow:0 30px 70px rgba(0,0,0,.45);display:flex;flex-direction:column}
.score .lab{font-weight:700;font-size:13px;letter-spacing:.16em;color:#8792a0}
.score .big{display:flex;align-items:baseline;gap:10px;margin-top:10px}
.score .big b{font-family:Poppins;font-weight:700;font-size:92px;line-height:1;letter-spacing:-.03em;color:#fff}
.score .big span{font-family:Poppins;font-weight:600;font-size:26px;color:#6b7785}
.score .verd{margin-top:14px;font-family:Poppins;font-weight:600;font-size:20px;color:#5fcf86}
.score .sp{flex:1}
.score .div{height:1px;background:#243240;margin-bottom:20px}
.sub+.sub{margin-top:15px}
.sub .t{display:flex;justify-content:space-between;font-size:15px;font-weight:500;color:#c6ced6}
.sub .t b{font-weight:700;color:#fff}
.sub .tr{margin-top:8px;height:6px;border-radius:3px;background:#243140;overflow:hidden}
.sub .tr i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#3fb56b,#5fcf86)}
.foot{position:absolute;left:100px;top:580px;display:flex;align-items:center;gap:12px;font-size:13px;font-weight:500;color:#7c8793}
.foot .age{height:22px;padding:0 8px;border:1px solid #37434f;border-radius:999px;display:flex;align-items:center;font-weight:700;font-size:11px;color:#c6ced6}
"""

# Naam op één regel (kleiner lettertype indien nodig), regel max. 2 regels, bovenblok mag de top 3 niet raken.
FIT_JS = """() => {
  const h = document.getElementById('h1'), t = document.getElementById('tag'), left = document.querySelector('.left'),
        tops = document.querySelector('.tops');
  let fs = 52; while (fs > 36 && h.scrollWidth > h.clientWidth + 1) { fs -= 2; h.style.fontSize = fs + 'px'; }
  if (h.scrollWidth > h.clientWidth + 1) { h.classList.add('wrap'); }
  const lh = () => parseFloat(getComputedStyle(t).lineHeight);
  let ts = 20; while (t && ts > 15 && t.getBoundingClientRect().height > 2 * lh() + 2) { ts -= 1; t.style.fontSize = ts + 'px'; }
  const clash = () => left.getBoundingClientRect().bottom > tops.getBoundingClientRect().top - 14;
  while (t && clash() && ts > 15) { ts -= 1; t.style.fontSize = ts + 'px'; }
  return {overflow: clash()};
}"""


def _page(info, logo, tiles, be_logo):
    e = lambda s: html.escape(str(s), quote=True)
    f1 = lambda v: f"{v:.1f}".replace(".", ",")
    logo_raw = logo
    if logo:
        uri, bg, ratio = logo
        ih = 56 if ratio < 1.6 else 44 if ratio < 3.2 else 34        # vierkante logo's groter, brede lager
        iw = min(172, ih * ratio)
        ih = iw / ratio
        tw = max(84, iw + (28 if ratio < 1.6 else 36))
        logo = (f'<div class="logo" style="background:{bg};width:{tw:.0f}px">'
                f'<img src="{uri}" style="width:{iw:.0f}px;height:{ih:.0f}px"></div>')
    else:
        logo = f'<div class="logo"><span class="ini">{e(initials(info["naam"]))}</span></div>'
    if logo_raw:
        u, bg, ratio = logo_raw
        pw = min(110, 40 * ratio) if ratio >= 1 else 40 * ratio
        ph = f'<div class="lg" style="background:{bg}"><img src="{u}" style="width:{pw:.0f}px;height:{pw / ratio:.0f}px"></div>'
    else:
        ph = f'<div class="lg" style="background:#fff"><span>{e(initials(info["naam"]))}</span></div>'
    cells = "".join(
        f'<div class="cell"><div class="tile"><span class="num">{n}</span>'
        + (f'<img src="{uri}">' if uri else f'<div class="ph">{ph}</div>')
        + f'</div><div class="n">{e(name)}</div></div>'
        for n, (name, uri) in enumerate(tiles, 1))
    subs = "".join(
        f'<div class="sub"><div class="t"><span>{e(k)}</span><b>{f1(v)}</b></div>'
        f'<div class="tr"><i style="width:{max(0, min(100, v * 10)):.1f}%"></i></div></div>' for k, v in info["subs"])
    score = info["score"] or 0
    chips = "".join(f'<span class="chip">{e(c)}</span>' for c in info["chips"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_fonts_css()}{CSS}</style></head><body>
<div class="bg"></div><div class="topbar"></div>
<img class="brand" src="{be_logo}"><div class="domain">bet-experts.nl</div>
<div class="left">
  <div class="eyebrow"><span class="bar"></span><span class="kind">CASINO PROVIDER</span></div>
  <div class="head">{logo}<h1 id="h1">{e(info["naam"])}</h1></div>
  {'<div class="tag" id="tag">' + e(info["tagline"]) + '</div>' if info["tagline"] else ''}
  {'<div class="chips">' + chips + '</div>' if chips else ''}
</div>
{'<div class="tops"><div class="lab">' + info["label"] + '</div><div class="grid">' + cells + '</div></div>' if tiles else ''}
<div class="score"><div class="lab">ONZE BEOORDELING</div>
  <div class="big"><b>{f1(score)}</b><span>/10</span></div>
  <div class="verd">{verdict(score)}</div><div class="sp"></div><div class="div"></div>{subs}</div>
<div class="foot"><span class="age">18+</span>Wat kost gokken jou? Stop op tijd.</div>
</body></html>"""


def render(r, info):
    logo = None
    if info.get("logo"):
        try:
            png, bg, ratio = prep_logo(_fetch(info["logo"])[0])
            logo = (_data_uri(png, "image/png"), bg, ratio)
        except Exception as ex:
            print(f"   ! logo niet te verwerken voor {info['slug']}: {ex}")
    tiles = [(name, r.image_uri(url, info["slug"])) for name, url in info["top"]]
    return r.shoot(_page(info, logo, tiles, r._logo), FIT_JS, info["slug"])


def main(argv):
    _env()
    items = [i for i in _all_items(PROVIDERS) if i.get("lastPublished") and not i.get("isDraft")]
    by_slug = {i["fieldData"]["slug"]: i for i in items}
    by_name = {i["fieldData"]["name"]: i for i in _all_items(PROVIDERS)}
    todo = list(by_slug) if "--all" in argv else [a for a in argv if not a.startswith("--")]
    r, files = Renderer(), {}
    try:
        for slug in todo:
            info = info_from_item(by_slug[slug])
            if not info["logo"] and info["naam"].endswith(" Live"):      # live-tak zonder eigen logo -> logo moederbedrijf
                base = by_name.get(info["naam"][:-5])
                info["logo"] = base and (base["fieldData"].get("logo") or {}).get("url")
            webp, png = render(r, info)
            files[slug] = save(info, webp, OUT)
            if "--preview" in argv:
                open(os.path.join(os.environ.get("SLOT_OG_PREVIEW", "/tmp"), f"prov-og-{slug}.png"), "wb").write(png)
            print(f"   ✓ {files[slug]}  ({len(webp) // 1024} kB)")
    finally:
        r.close()
    if "--attach" in argv:
        attach(files, by_slug, collection=PROVIDERS, subdir="assets/providers", alt_suffix=" casino provider", label="Provider")


if __name__ == "__main__":
    main(sys.argv[1:])
