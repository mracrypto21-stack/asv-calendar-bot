#!/usr/bin/env python3
"""Kopīgais "plakanais" dashboard stils (kripto nedēļas + ASV ekonomikas bildes).

Kvadrāts 1080x1080, cietas tumšas kartītes ar plānu pelēku malu, BEZ neona,
BEZ glow/blur, BEZ AI fona. Krāsas tikai trīs: zaļš (kāpums), sarkans (kritums),
zelts (akcents) + balts/pelēks teksts. Viss ir īsts HTML/SVG → PNG (Playwright),
tāpēc cipari vienmēr pikseļprecīzi.
"""
import math
import datetime as _dt

W = H = 1080

GREEN = "#3ddc97"
RED = "#f2556b"
GOLD = "#e8b84a"
TEXT = "#f3f5f9"
MUTED = "#8a94a6"
GRID = "#212837"

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:1080px; height:1080px; }
body {
  background: linear-gradient(180deg, #0d1118 0%, #090c11 100%);
  font-family: 'Liberation Sans', Arial, Helvetica, sans-serif;
  color:#f3f5f9; padding:40px;
  display:flex; flex-direction:column; gap:20px;
}
.header { height:70px; display:flex; flex-direction:column; justify-content:center; }
.title { font-size:46px; font-weight:800; letter-spacing:0.3px; line-height:1.05; }
.subtitle { font-size:20px; font-weight:700; color:#e8b84a; margin-top:6px; letter-spacing:0.3px; }
.row { display:flex; gap:20px; }
.card {
  background:#141a24; border:1px solid #2a3243; border-radius:16px;
  padding:20px 22px; display:flex; flex-direction:column; min-width:0; overflow:hidden;
}
.ctitle { font-size:19px; font-weight:800; letter-spacing:0.8px; text-transform:uppercase; color:#c3cad6; }
.big { font-size:54px; font-weight:800; line-height:1; letter-spacing:0.3px; }
.delta { font-size:26px; font-weight:800; display:flex; align-items:center; gap:8px; }
.muted { color:#8a94a6; font-size:16px; font-weight:600; }
.grow { flex:1; display:flex; flex-direction:column; justify-content:center; gap:10px; }
table { width:100%; border-collapse:collapse; }
th { font-size:14px; font-weight:700; letter-spacing:0.8px; color:#8a94a6; text-align:left;
     padding:0 0 8px; border-bottom:1px solid #2a3243; text-transform:uppercase; }
th.r, td.r { text-align:right; }
td { padding:0; border-bottom:1px solid #1f2633; }
tr:last-child td { border-bottom:none; }
.tk { font-size:24px; font-weight:800; }
.nm { font-size:14px; font-weight:600; color:#8a94a6; margin-top:2px; }
.num { font-size:24px; font-weight:800; }
"""


def tri(up, size=16):
    """Plakans trijstūris: ▲ zaļš / ▼ sarkans."""
    color = GREEN if up else RED
    pts = f"0,{size} {size},{size} {size/2},0" if up else f"0,0 {size},0 {size/2},{size}"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="display:inline-block;flex-shrink:0;"><polygon points="{pts}" fill="{color}"/></svg>')


def col(up):
    return GREEN if up else RED


def money(v):
    v = float(v)
    a = abs(v)
    if a >= 1e12:
        s = f"${a/1e12:.2f}T"
    elif a >= 1e9:
        s = f"${a/1e9:.2f}B"
    elif a >= 1e6:
        s = f"${a/1e6:.1f}M"
    elif a >= 1e3:
        s = f"${a/1e3:.1f}K"
    else:
        s = f"${a:.0f}"
    return ("-" if v < 0 else "") + s


def smoney(v):
    """Ar zīmi: +$74.6M / -$1.91B."""
    v = float(v)
    m = money(abs(v))
    return ("-" if v < 0 else "+") + m


def pct(v, nd=1):
    return f"{float(v):+.{nd}f}%"


def _nice_step(rng, target=3):
    raw = rng / max(target, 1)
    if raw <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * p:
            return m * p
    return 10 * p


def line_chart(vals, w, h, y_fmt, x_labels=None, end_label=None, color=GOLD, gid="g1"):
    """Viena līnija + maiga zona zem tās + režģis ar Y/X etiķetēm + beigu birka."""
    vals = [float(v) for v in vals]
    if len(vals) < 2:
        return ""
    ml, mr, mt, mb = 74, 16, 14, 30
    mn, mx = min(vals), max(vals)
    step = _nice_step((mx - mn) or abs(mx) * 0.1 or 1.0, 3)
    lo = math.floor(mn / step) * step
    hi = math.ceil(mx / step) * step
    if hi - lo < step * 2:
        hi = lo + step * 2
    iw, ih = w - ml - mr, h - mt - mb

    def px(i):
        return ml + i * iw / (len(vals) - 1)

    def py(v):
        return mt + ih - (v - lo) / (hi - lo) * ih

    out = []
    t = lo
    while t <= hi + step * 0.001:
        y = py(t)
        out.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{w - mr}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{ml - 10}" y="{y + 5:.1f}" text-anchor="end" font-size="15" font-weight="600" fill="{MUTED}">{y_fmt(t)}</text>')
        t += step
    # asis
    out.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ih}" stroke="#2a3243" stroke-width="1.5"/>')
    out.append(f'<line x1="{ml}" y1="{mt + ih}" x2="{w - mr}" y2="{mt + ih}" stroke="#2a3243" stroke-width="1.5"/>')
    for idx, lab in (x_labels or []):
        x, anchor = px(idx), "middle"
        if x > w - mr - 24:
            x, anchor = w - mr, "end"
        elif x < ml + 24:
            x, anchor = ml, "start"
        out.append(f'<text x="{x:.1f}" y="{h - 6}" text-anchor="{anchor}" font-size="15" font-weight="600" fill="{MUTED}">{lab}</text>')
    line = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
    area = f"M {px(0):.1f},{mt + ih} L " + " L ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals)) + f" L {px(len(vals) - 1):.1f},{mt + ih} Z"
    defs = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{color}" stop-opacity="0.20"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0.01"/></linearGradient></defs>')
    out.append(f'<path d="{area}" fill="url(#{gid})"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    ex, ey = px(len(vals) - 1), py(vals[-1])
    out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="6" fill="{color}" stroke="#141a24" stroke-width="2.5"/>')
    if end_label:
        bw, bh = 12 + 12 * len(end_label) * 0.78 + 12, 30
        bx = min(ex - bw / 2, w - mr - bw)
        by = ey - bh - 12
        if by < 2:
            by = ey + 14
        out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh}" rx="7" fill="{color}"/>')
        out.append(f'<text x="{bx + bw / 2:.1f}" y="{by + 21:.1f}" text-anchor="middle" font-size="17" font-weight="800" fill="#10141b">{end_label}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{defs}{"".join(out)}</svg>'


def mini_bars(vals, w, h, labels=None):
    """Mazs joslu grafiks no nulles līnijas (zaļš/sarkans), bez glow."""
    vals = [float(v) for v in vals]
    if not vals:
        return ""
    n = len(vals)
    lab_h = 16 if labels else 0
    ch = h - lab_h
    zero = ch / 2
    maxv = max(abs(v) for v in vals) or 1.0
    slot = w / n
    bw = slot * 0.58
    out = [f'<line x1="0" y1="{zero:.1f}" x2="{w}" y2="{zero:.1f}" stroke="#2f384a" stroke-width="1.5"/>']
    for i, v in enumerate(vals):
        bh = max(2.0, abs(v) / maxv * (ch / 2 - 2))
        x = i * slot + (slot - bw) / 2
        y = zero - bh if v >= 0 else zero
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{col(v >= 0)}"/>')
        if labels and i < len(labels):
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 3}" text-anchor="middle" font-size="12" font-weight="700" fill="{MUTED}">{labels[i]}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(out)}</svg>'


def scale_bar(value, lo, hi, ticks, left_color="#b8545c", mid_color="#c9a24a", right_color="#4aa880", marker_color="#ffffff"):
    """Skala ar maigu gradientu un trijstūra marķieri (kā atsauces Fear & Greed josla)."""
    frac = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    tick_html = "".join(f'<span>{t}</span>' for t in ticks)
    return f"""
    <div style="position:relative; padding-top:18px;">
      <svg width="18" height="14" viewBox="0 0 18 14" style="position:absolute; top:0; left:calc({frac*100:.1f}% - 9px);">
        <polygon points="0,0 18,0 9,14" fill="{marker_color}"/></svg>
      <div style="height:14px; border-radius:7px; background:linear-gradient(90deg,{left_color} 0%,{mid_color} 50%,{right_color} 100%);"></div>
      <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:15px; font-weight:700; color:{MUTED};">{tick_html}</div>
    </div>"""


def header(title, subtitle):
    return f'<div class="header"><div class="title">{title}</div><div class="subtitle">{subtitle}</div></div>'


def page(body):
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'


def render(html, out_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg.set_content(html, wait_until="networkidle")
        pg.wait_for_timeout(300)
        pg.screenshot(path=out_path, animations="disabled")
        b.close()


def date_ticks(n, step_samples, end_dt, fmt="%b %-d", count=7, per_sample_hours=1):
    """X ass etiķetes: indeksi no beigām ar soli step_samples."""
    ticks = []
    for k in range(count):
        idx = n - 1 - k * step_samples
        if idx < 0:
            break
        dt = end_dt - _dt.timedelta(hours=per_sample_hours * (n - 1 - idx))
        ticks.append((idx, dt.strftime(fmt)))
    return list(reversed(ticks))
