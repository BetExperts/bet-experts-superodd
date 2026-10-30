# -*- coding: utf-8 -*-
"""VIP-banner in de artikelen (naast de welkomstbonus-CTA's): 'Alle VIP-picks van vandaag. Eén overzicht.' met een
gelockte Topkeuze-kaart en de actuele ROI / hit rate uit het VIP-portaal (vip_portaal.bouw()).

Jasper 30-10-2026: ontwerp B, met ROI, automatisch bijwerken. Draait in run_fm.sh na vip_portaal.py; rendert en
deployt alleen als de getoonde cijfers veranderen (en hooguit eens per 3 uur).
- Bestanden: site-static/files/vip-cta.webp (1400x514) en vip-cta-m.webp (1080x960), vaste namen met korte cache
  (VASTE_NAMEN in site-static/deploy.py). Plaatsing: site-static/files/vip-cta.js (footer), vóór 'Veelgestelde vragen'.
- Is een ROI niet positief, dan valt de chip terug op de hit rate (nooit een negatieve ROI in reclame tonen).
    .venv/bin/python vip_cta.py [--force] [--geen-deploy]"""
import json, os, subprocess, sys, time, uuid, pathlib
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE.parent / "site-static"
FILES = STATIC / "files"
ASSETS = pathlib.Path("/Users/jaspervandenboogaard/bet-experts/preview-images-agent/assets")
STATE = HERE / "state" / "vip_cta.json"
G, GL, GOUD = "#169A47", "#2FD46E", "#E8C46B"
MIN_INTERVAL = 3 * 3600


def pct(x, plus=False):
    s = f"{x:.1f}".replace(".", ",")
    return ("+" if plus and x > 0 else "") + s + "%"


def chips(roi):
    """Twee cijfers voor de chips: liefst ROI player picks + hit rate team trends; nooit een ROI <= 0."""
    sp, tm = roi.get("spelers") or {}, roi.get("teams") or {}
    out = []
    if sp.get("n", 0) >= 20 and sp.get("roi", 0) > 0:
        out.append(("ROI player picks", pct(sp["roi"], True)))
    elif tm.get("n", 0) >= 20 and tm.get("roi", 0) > 0:
        out.append(("ROI team trends", pct(tm["roi"], True)))
    best = max((("team trends", tm), ("player picks", sp)), key=lambda kv: kv[1].get("hit", 0) if kv[1].get("n", 0) >= 20 else -1)
    if best[1].get("n", 0) >= 20:
        out.append((f"Hit rate {best[0]}", f"{round(best[1]['hit'])}%"))
    n = sp.get("n", 0) + tm.get("n", 0)
    if len(out) < 2 and n:
        out.append(("Picks afgerekend", str(n)))
    return out[:2]


ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>'
STAR = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.6l2.9 6 6.5.8-4.8 4.5 1.2 6.5L12 17.3l-5.8 3.1 1.2-6.5L2.6 9.4l6.5-.8z"/></svg>'
USER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>'

CSS = f"""@import url('fonts.css');
*{{margin:0;padding:0;box-sizing:border-box}} body{{background:#0B1117;-webkit-font-smoothing:antialiased;color:#F5F9FA;font-family:'Plus Jakarta Sans'}}
.b{{position:relative;overflow:hidden;background:#0B1117}}
.glow{{position:absolute;border-radius:50%;filter:blur(110px)}}
.top{{position:absolute;left:0;right:0;top:0;height:4px;background:linear-gradient(90deg,{G},rgba(22,154,71,0))}}
.eb{{display:flex;align-items:center;gap:14px;font:800 17px 'Plus Jakarta Sans';letter-spacing:2.6px;color:#6CC08B;text-transform:uppercase;white-space:nowrap}}
.vip{{display:inline-flex;align-items:center;height:30px;padding:0 13px;border-radius:999px;background:{G};color:#fff;font:800 14px 'Poppins';letter-spacing:1.5px}}
.h{{font:800 50px/1.06 'Poppins';letter-spacing:-1.2px}} .h em{{font-style:normal;color:{GL}}}
.stat{{display:flex;gap:10px;flex-wrap:wrap}}
.chip{{height:42px;padding:0 17px;border-radius:999px;background:rgba(255,255,255,.06);border:1.5px solid rgba(255,255,255,.14);display:flex;align-items:center;gap:9px;font:600 16px 'Plus Jakarta Sans';color:#C9D3DB;white-space:nowrap}}
.chip b{{font:800 17px 'Poppins';color:{GL}}}
.btn{{display:inline-flex;align-items:center;gap:16px;height:56px;padding:0 30px;border-radius:999px;background:{G};font:700 19px 'Plus Jakarta Sans';color:#fff;white-space:nowrap}} .btn svg{{width:20px;height:20px}}
.ft{{position:absolute;bottom:0;border-top:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:space-between;font:500 17px 'Plus Jakarta Sans';color:#AEB9C2}}
.ft .l{{display:flex;align-items:center;gap:18px}} .age{{height:34px;padding:0 13px;border-radius:999px;border:1.5px solid rgba(255,255,255,.35);display:flex;align-items:center;font:700 15px 'Plus Jakarta Sans';color:#F5F9FA}}
.card{{border-radius:24px;overflow:hidden;background:#F5F9FA;box-shadow:0 26px 60px rgba(0,0,0,.5),0 0 0 1px rgba(232,196,107,.35);transform:rotate(-2deg)}}
.card .hd{{height:44px;background:linear-gradient(90deg,{GOUD},#F3D88F);display:flex;align-items:center;justify-content:space-between;padding:0 22px;font:800 15px 'Poppins';color:#3B2B05;letter-spacing:1px}}
.card .hd span{{display:flex;align-items:center;gap:8px}} .card .hd svg{{width:16px;height:16px}}
.card .bd{{padding:15px 22px 18px;color:#0B1117}} .row{{display:flex;justify-content:space-between;align-items:center}}
.tm{{font:800 21px 'Poppins'}} .cp{{font:600 15px 'Plus Jakarta Sans';color:#5E6B76}} .wd{{margin-top:4px;font:800 23px 'Poppins';white-space:nowrap}}
.tag{{display:inline-flex;align-items:center;gap:7px;height:30px;padding:0 12px;border-radius:9px;background:#E3F3E8;color:#14773A;font:700 14px 'Plus Jakarta Sans'}} .tag svg{{width:15px;height:15px}}
.lockrow{{margin-top:10px;display:flex;gap:12px;align-items:center}}
.blur{{flex:1;height:52px;border-radius:12px;background:#E9EFEC;position:relative;overflow:hidden}}
.blur:before{{content:'';position:absolute;left:14px;top:13px;width:62%;height:12px;border-radius:6px;background:#C9D3CE;filter:blur(3px)}}
.blur:after{{content:'';position:absolute;left:14px;top:32px;width:40%;height:10px;border-radius:5px;background:#D6DEDA;filter:blur(3px)}}
.odd{{width:84px;height:52px;border-radius:12px;background:#E9EFEC;display:flex;align-items:center;justify-content:center;font:800 24px 'Poppins';color:#B9C4BF;filter:blur(3.5px)}}
.lk{{position:absolute;right:22px;bottom:18px;display:flex;align-items:center;gap:9px;height:52px;padding:0 18px;border-radius:12px;background:#0B1117;color:#fff;font:700 16px 'Plus Jakarta Sans';white-space:nowrap}} .lk svg{{width:19px;height:19px}}
"""


def kaart_html(breed, rot=-2):
    return f"""<div class="card" style="width:{breed}px;position:relative;transform:rotate({rot}deg)"><div class="hd"><span>{STAR}TOPKEUZE</span><span style="font:700 13px 'Plus Jakarta Sans'">volgens Bet Experts</span></div>
  <div class="bd"><div class="row"><span class="tm">20:45</span><span class="cp">Premier League</span></div><div class="wd">Thuisploeg – Uitploeg</div>
  <div style="margin-top:10px"><span class="tag">{USER}Player pick</span></div>
  <div class="lockrow"><div class="blur"></div><div class="odd">1,92</div></div></div>
  <div class="lk">{LOCK}Alleen voor VIP</div></div>"""


def html(variant, cs):
    chips_html = "".join(f'<span class="chip">{k} <b>{v}</b></span>' for k, v in cs)
    ft_rechts = "Resultaten uit het verleden bieden geen garantie"
    glows = (f'<div class="top"></div><div class="glow" style="width:720px;height:520px;left:-260px;top:-300px;background:rgba(22,154,71,.40)"></div>'
             f'<div class="glow" style="width:620px;height:420px;right:-200px;bottom:-320px;background:rgba(22,154,71,.20)"></div>')
    if variant == "d":
        body = f"""<div class="b" style="width:1400px;height:514px">{glows}
  <div class="eb" style="position:absolute;left:70px;top:52px"><span class="vip">VIP</span>Nieuw: het VIP-portaal</div>
  <div style="position:absolute;left:70px;top:104px;width:640px">
    <div class="h">Alle VIP-picks van vandaag.<br><em>In één overzicht.</em></div>
    <div class="stat" style="margin-top:22px">{chips_html}</div>
    <div class="btn" style="margin-top:22px">Bekijk het VIP-portaal {ARROW}</div></div>
  <img src="betexperts_logo.png" style="position:absolute;right:70px;top:46px;height:30px">
  <div style="position:absolute;right:84px;top:122px">{kaart_html(440)}</div>
  <div class="ft" style="left:70px;right:70px;height:104px"><div class="l"><span class="age">24+</span>Wat kost gokken jou? Stop op tijd.</div><div>{ft_rechts}</div></div></div>"""
        return body, (1400, 514)
    body = f"""<div class="b" style="width:1080px;height:960px">{glows}
  <div class="eb" style="position:absolute;left:64px;top:60px"><span class="vip">VIP</span>Nieuw: het VIP-portaal</div>
  <img src="betexperts_logo.png" style="position:absolute;right:64px;top:56px;height:30px">
  <div style="position:absolute;left:64px;top:122px;width:952px"><div class="h" style="font-size:58px">Alle VIP-picks van vandaag.<br><em>In één overzicht.</em></div></div>
  <div class="stat" style="position:absolute;left:64px;top:300px;width:952px;gap:12px">{"".join(f'<span class="chip" style="height:48px;font-size:18px">{k} <b style="font-size:19px">{v}</b></span>' for k, v in cs)}</div>
  <div style="position:absolute;left:64px;top:392px">{kaart_html(952, -1)}</div>
  <div style="position:absolute;left:64px;top:680px"><div class="btn" style="height:66px;font-size:23px;padding:0 38px">Bekijk het VIP-portaal {ARROW}</div></div>
  <div class="ft" style="left:64px;right:64px;height:162px;flex-direction:column;align-items:flex-start;justify-content:center;gap:12px">
    <div class="l"><span class="age">24+</span>Wat kost gokken jou? Stop op tijd.</div><div style="font-size:16px">{ft_rechts}</div></div></div>"""
    return body, (1080, 960)


CHECK = """(() => { const r = [], b = document.querySelector('.b').getBoundingClientRect();
  const ft = document.querySelector('.ft').getBoundingClientRect(), logo = document.querySelector('img').getBoundingClientRect();
  const card = document.querySelector('.card').getBoundingClientRect();
  if (card.top < logo.bottom + 30) r.push('kaart te dicht op logo: ' + Math.round(card.top - logo.bottom));
  if (card.bottom > ft.top - 14) r.push('kaart raakt voetregel');
  document.querySelectorAll('.b *').forEach(e => { if (e.classList.contains('glow') || e.classList.contains('top') || e.closest('.card')) return; const q = e.getBoundingClientRect();
    if (q.width && (q.right > b.right - 30 || q.bottom > b.bottom)) r.push('buiten beeld: ' + (e.className || e.tagName)); });
  const h = document.querySelector('.h').getBoundingClientRect(); if (h.right > card.left - 20 && h.bottom > card.top) r.push('kop raakt kaart');
  document.querySelectorAll('.chip,.btn').forEach(e => { const q = e.getBoundingClientRect(); if (q.left < card.right + 16 && q.right > card.left - 16 && q.bottom > card.top && q.top < card.bottom) r.push('raakt kaart: ' + e.textContent.trim()); });
  return r; })()"""


def render(cs, uitdir=FILES, namen=("vip-cta.webp", "vip-cta-m.webp")):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    import io
    fouten = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--font-render-hinting=none"])
        for variant, naam in zip("dm", namen):
            body, (w, h) = html(variant, cs)
            f = ASSETS / f".vipcta-{uuid.uuid4().hex[:6]}.html"
            f.write_text(f"<!doctype html><html lang='nl'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")
            try:
                pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
                pg.goto(f.as_uri()); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(300)
                fouten += [f"{variant}: {x}" for x in pg.evaluate(CHECK)]
                png = pg.screenshot(); pg.close()
            finally:
                f.unlink(missing_ok=True)
            Image.open(io.BytesIO(png)).convert("RGB").resize((w, h), Image.LANCZOS).save(pathlib.Path(uitdir) / naam, "WEBP", quality=86, method=6)
        br.close()
    return fouten


def main():
    sys.path.insert(0, str(HERE))
    import vip_portaal as vp
    force, deploy = "--force" in sys.argv, "--geen-deploy" not in sys.argv
    cs = chips(vp.bouw()["roi"])
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not force and st.get("chips") == cs:
        print("vip-cta: ongewijzigd", cs); return
    if not force and time.time() - st.get("ts", 0) < MIN_INTERVAL:
        print("vip-cta: te kort geleden bijgewerkt, later opnieuw", cs); return
    fouten = render(cs)
    if fouten:
        print("vip-cta: NIET gedeployd, opmaakfouten:", fouten); return
    if deploy:
        subprocess.run([sys.executable, str(STATIC / "deploy.py")], check=True, stdout=subprocess.DEVNULL)
    STATE.write_text(json.dumps({"chips": cs, "ts": time.time(), "datum": datetime.now().isoformat(timespec="minutes")}, ensure_ascii=False))
    print("vip-cta: bijgewerkt", cs, "(gedeployd)" if deploy else "")


if __name__ == "__main__":
    main()
