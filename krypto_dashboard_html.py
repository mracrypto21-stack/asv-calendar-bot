#!/usr/bin/env python3
"""Kripto nedēļas infografika — kie.ai fons + HTML/SVG→PNG (premium fintech).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs, jo AI modeļi slikti
renderē ciparus. kie.ai ģenerē TIKAI fonu (bez teksta/cipariem).

Katrai no 8 kartītēm ir īsts SVG grafiks ar datiem. 1600x900, 4x2 režģis,
bez avotu teksta. Visi grafiki zīmēti ar kodu (HTML/SVG), KIE tikai fonam.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 krypto_dashboard_html.py <out.png> '<json_data>'
"""
import os
import sys
import json
import time
import math
import base64
import urllib.request

import requests


def load_api_key():
    key = os.environ.get("KIE_AI_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for env_path in (os.path.join(here, ".env"), "/root/.hermes/.env"):
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("KIE_AI_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("'").strip('"')
    return None


def check_credits(api_key):
    r = requests.get(
        "https://api.kie.ai/api/v1/chat/credit",
        headers={"Authorization": f"Bearer {api_key}"}, timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"kie.ai credit kļūda: {data}")
    return float(data.get("data", 0))


KIE_MODELS = [
    "nano-banana-2-lite",
    "seedream/5-lite-text-to-image",
]


def generate_background(out_path, api_key):
    """Ģenerē košu kosmisku fonu (bez teksta) caur KIE, izmēģinot modeļus."""
    prompt = (
        "Dark cosmic crypto landscape background, vibrant violet-blue-pink-cyan "
        "gradients, glowing neon lights, 3D glass bubbles floating, luminous "
        "candlestick charts and a rising upward curve, premium fintech "
        "aesthetic, deep space nebula with colorful aurora, "
        "no text, no numbers, no letters, no words, no labels, "
        "empty background for data overlay"
    )
    last_err = None
    for model in KIE_MODELS:
        try:
            payload = {
                "model": model,
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": "16:9",
                    "quality": "high",
                    "output_format": "png",
                    "nsfw_checker": False,
                },
            }
            r = requests.post(
                "https://api.kie.ai/api/v1/jobs/createTask",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("code") != 200:
                raise RuntimeError(f"kie.ai createTask kļūda: {data}")
            task_id = data["data"]["taskId"]

            deadline = time.time() + 200
            while time.time() < deadline:
                resp = requests.get(
                    f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                    headers={"Authorization": f"Bearer {api_key}"}, timeout=30,
                )
                resp.raise_for_status()
                d = resp.json().get("data", {})
                state = d.get("state")
                if state == "success":
                    urls = d.get("resultJson", "")
                    try:
                        urls = json.loads(urls).get("resultUrls", [])
                    except Exception:
                        urls = []
                    if urls:
                        return urls[0]
                    raise RuntimeError("kie.ai: success, bet nav rezultāta URL")
                if state in ("failed", "error"):
                    raise RuntimeError(f"kie.ai uzdevums neizdevās: {d.get('failMsg')}")
                time.sleep(5)
            raise RuntimeError("kie.ai: uzdevuma apstrādes taimauts")
        except Exception as e:
            last_err = e
            print(f"  ⚠️ modelis {model} neizdevās: {e}")
            continue
    raise RuntimeError(f"Visi KIE modeļi neizdevās: {last_err}")


def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(out_path, "wb") as f:
            f.write(r.read())
    return out_path


def _bg_data_uri(bg_path):
    with open(bg_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def fmt_usd(v):
    v = float(v)
    a = abs(v)
    if a >= 1e12:
        return f"${v/1e12:.2f}T"
    if a >= 1e9:
        return f"${v/1e9:.2f}B"
    if a >= 1e6:
        return f"${v/1e6:.1f}M"
    if a >= 1e3:
        return f"${v/1e3:.1f}K"
    return f"${v:.0f}"


def fmt_pct(v):
    return f"{v:+.1f}%"


def tri(up, size=13):
    """SVG trijstūris — ▲ zaļš / ▼ sarkans (ne emoji)."""
    if up:
        pts = f"0,{size} {size},{size} {size/2},0"
        color = "#00ff9d"
    else:
        pts = f"0,0 {size},0 {size/2},{size}"
        color = "#ff3b5c"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="display:inline-block;vertical-align:middle;margin-right:5px;">'
            f'<polygon points="{pts}" fill="{color}" '
            f'style="filter:drop-shadow(0 0 5px {color}88);"/></svg>')


# ---------------- SVG grafiku ģeneratori ----------------

def area_chart(series, w, h, color, gid):
    """Area chart: path seko līknei un beidzas pie baseline (gradient fill)."""
    if not series or len(series) < 2:
        return ""
    vals = [float(v) for v in series]
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1.0
    pad = 4
    def px(i):
        return pad + i * (w - 2 * pad) / (len(vals) - 1)
    def py(v):
        return h - pad - (v - mn) / rng * (h - 2 * pad)
    line = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
    area = f"M {px(0):.1f},{h} L " + " L ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals)) + f" L {px(len(vals)-1):.1f},{h} Z"
    last_x, last_y = px(len(vals) - 1), py(vals[-1])
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">
      <defs>
        <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.50"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <path d="{area}" fill="url(#{gid})"/>
      <polyline points="{line}" fill="none" stroke="{color}" stroke-width="3"
        stroke-linejoin="round" stroke-linecap="round"
        style="filter:drop-shadow(0 0 6px {color}99);"/>
      <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="{color}"
        style="filter:drop-shadow(0 0 8px {color});"/>
    </svg>"""


def candlestick(series, w, h, up_color="#00ff9d", down_color="#ff3b5c"):
    """7 dienu sveču (candlestick) grafiks no cenu sērijas."""
    if not series or len(series) < 2:
        return ""
    vals = [float(v) for v in series]
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1.0
    pad = 6
    n = len(vals)
    bw = (w - 2 * pad) / n
    body_w = bw * 0.55
    def py(v):
        return h - pad - (v - mn) / rng * (h - 2 * pad)
    out = []
    for i, v in enumerate(vals):
        x = pad + i * bw + bw / 2
        prev = vals[i - 1] if i > 0 else v
        up = v >= prev
        col = up_color if up else down_color
        # wick
        out.append(f'<line x1="{x:.1f}" y1="{py(max(v,prev)):.1f}" x2="{x:.1f}" y2="{py(min(v,prev)):.1f}" stroke="{col}" stroke-width="2"/>')
        # body
        y_top = py(max(v, prev))
        y_bot = py(min(v, prev))
        bh = max(2.0, abs(y_bot - y_top))
        out.append(f'<rect x="{x-body_w/2:.1f}" y="{y_top:.1f}" width="{body_w:.1f}" height="{bh:.1f}" rx="2" fill="{col}" style="filter:drop-shadow(0 0 4px {col}66);"/>')
    # beigu punkts
    lx = pad + (n - 1) * bw + bw / 2
    ly = py(vals[-1])
    out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="#ffffff" style="filter:drop-shadow(0 0 6px #ffffff88);"/>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(out)}</svg>'


def smooth_line(series, w, h, color, gid):
    """Gluda līnija ar gradientu (ETH)."""
    if not series or len(series) < 2:
        return ""
    vals = [float(v) for v in series]
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1.0
    pad = 4
    def px(i):
        return pad + i * (w - 2 * pad) / (len(vals) - 1)
    def py(v):
        return h - pad - (v - mn) / rng * (h - 2 * pad)
    # Catmull-Rom → bezjē līkne
    pts = [(px(i), py(v)) for i, v in enumerate(vals)]
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d += f" C {c1x:.1f} {c1y:.1f}, {c2x:.1f} {c2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}"
    area = d + f" L {pts[-1][0]:.1f},{h} L {pts[0][0]:.1f},{h} Z"
    last_x, last_y = pts[-1]
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">
      <defs>
        <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.40"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <path d="{area}" fill="url(#{gid})"/>
      <path d="{d}" fill="none" stroke="{color}" stroke-width="3"
        stroke-linecap="round" style="filter:drop-shadow(0 0 6px {color}99);"/>
      <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="{color}"
        style="filter:drop-shadow(0 0 8px {color});"/>
    </svg>"""


def donut(btc, eth, w, h):
    """Donut BTC/ETH/Others. Centrā tikai 'BTC'. Legenda zem gredzena."""
    others = max(0.0, 100.0 - btc - eth)
    segs = [("BTC", btc, "#ffb300"), ("ETH", eth, "#b44dff"), ("Others", others, "#3a4a6a")]
    cx, cy = w / 2, h / 2 - 8
    r = min(w, h) / 2 - 10
    stroke = r * 0.30
    rr = r - stroke / 2
    circ = 2 * math.pi * rr
    offset = 0.0
    arcs = []
    for name, pct, col in segs:
        if pct <= 0:
            continue
        frac = pct / 100.0
        dash = frac * circ
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="{col}" '
            f'stroke-width="{stroke}" stroke-dasharray="{dash:.1f} {circ:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" stroke-linecap="butt" '
            f'style="filter:drop-shadow(0 0 6px {col}66);"/>'
        )
        offset += dash
    # centrā tikai "BTC"
    center = f'<text x="{cx}" y="{cy+6}" text-anchor="middle" font-size="20" font-weight="900" fill="#ffb300" style="filter:drop-shadow(0 0 8px #ffb30088);">BTC</text>'
    # legenda zem gredzena
    ly = cy + r + 16
    legend = ""
    lx = cx - 70
    for name, pct, col in segs:
        legend += (f'<circle cx="{lx}" cy="{ly}" r="4" fill="{col}"/>'
                   f'<text x="{lx+8}" y="{ly+4}" font-size="11" font-weight="600" fill="#cfe0ff">{name} {pct:.1f}%</text>')
        lx += 70
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">
      {''.join(arcs)}
      {center}
      {legend}
    </svg>"""


def gauge(fng, fng_prev, w, h):
    """Pusloka spidometrs ar Fear/Greed uzrakstiem un Prev marķieri."""
    cx, cy = w / 2, h - 6
    r = min(w, h * 2) / 2 - 8
    stops = [
        (0.0, "#ff3b5c"), (0.25, "#ff8a3d"), (0.5, "#ffd700"),
        (0.75, "#00e5a0"), (1.0, "#00b36b"),
    ]
    def angle(v):
        return 180 - (v / 100.0) * 180
    def pt(v, rad):
        a = angle(v) * math.pi / 180
        return (cx + rad * math.cos(a), cy - rad * math.sin(a))
    segs = ""
    for i in range(5):
        v0, v1 = i * 20, (i + 1) * 20
        col = stops[i][1]
        a0 = angle(v0) * math.pi / 180
        a1 = angle(v1) * math.pi / 180
        x0, y0 = cx + r * math.cos(a0), cy - r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy - r * math.sin(a1)
        segs += f'<path d="M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{col}" stroke-width="13" stroke-linecap="butt" style="filter:drop-shadow(0 0 5px {col}66);"/>'
    # Fear / Greed uzraksti skalas galos
    fx, fy = pt(5, r + 14)
    gx, gy = pt(95, r + 14)
    labels = (f'<text x="{fx:.1f}" y="{fy:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#ff8a3d">Fear</text>'
              f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#00e5a0">Greed</text>')
    # adata
    ax, ay = pt(fng, r - 14)
    needle = f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#ffffff" stroke-width="3" stroke-linecap="round" style="filter:drop-shadow(0 0 6px #ffffff88);"/>'
    # Prev marķieris + tags
    px_, py_ = pt(fng_prev, r - 2)
    prev_mark = f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="5" fill="none" stroke="#ffffff" stroke-width="2.5"/>'
    tag_x, tag_y = px_ + 8, py_ - 8
    prev_tag = f'<text x="{tag_x:.1f}" y="{tag_y:.1f}" font-size="11" font-weight="700" fill="#ffffff" style="filter:drop-shadow(0 0 4px #000000aa);">Prev: {fng_prev}</text>'
    hub = f'<circle cx="{cx}" cy="{cy}" r="6" fill="#ffffff"/>'
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">
      {segs}
      {labels}
      {prev_mark}
      {prev_tag}
      {needle}
      {hub}
    </svg>"""


def etf_bars(daily, prev, this, w, h, color):
    """Tīrs joslu grafiks: 5 dienu joslas no nulles līnijas (Mon-Fri)."""
    if daily and len(daily) >= 2:
        vals = [float(v) for v in daily]
        days = ["M", "T", "W", "T", "F"][:len(vals)]
        maxv = max([abs(v) for v in vals] + [1.0])
        pad = 8
        n = len(vals)
        bw = (w - 2 * pad) / n * 0.6
        zero = h / 2
        scale = (h / 2 - 14) / maxv
        out = []
        # nulles līnija
        out.append(f'<line x1="0" y1="{zero:.1f}" x2="{w}" y2="{zero:.1f}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>')
        max_i = max(range(n), key=lambda i: abs(vals[i]))
        for i, v in enumerate(vals):
            x = pad + i * (w - 2 * pad) / n + ((w - 2 * pad) / n - bw) / 2
            col = "#00ff9d" if v >= 0 else "#ff3b5c"
            bh = abs(v) * scale
            y = zero - bh if v >= 0 else zero
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{col}" style="filter:drop-shadow(0 0 4px {col}66);"/>')
            out.append(f'<text x="{x+bw/2:.1f}" y="{h-2}" text-anchor="middle" font-size="11" font-weight="700" fill="#9fb6d4">{days[i]}</text>')
            if i == max_i:
                vy = y - 6 if v >= 0 else y + bh + 16
                out.append(f'<text x="{x+bw/2:.1f}" y="{vy:.1f}" text-anchor="middle" font-size="11" font-weight="800" fill="{col}">{fmt_usd(v)}</text>')
        return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(out)}</svg>'
    # fallback: 2 joslas Prev / This
    maxv = max(abs(prev), abs(this), 1.0)
    pad = 20
    bw = (w - 2 * pad) / 2 * 0.5
    zero = h / 2
    scale = (h / 2 - 14) / maxv
    out = [f'<line x1="0" y1="{zero:.1f}" x2="{w}" y2="{zero:.1f}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>']
    for i, (v, label) in enumerate([(prev, "Prev"), (this, "This")]):
        x = pad + i * (w - 2 * pad) / 2 + ((w - 2 * pad) / 2 - bw) / 2
        col = "#3a4a6a" if i == 0 else color
        bh = abs(v) * scale
        y = zero - bh if v >= 0 else zero
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{col}" style="filter:drop-shadow(0 0 4px {col}66);"/>')
        vy = y - 6 if v >= 0 else y + bh + 16
        out.append(f'<text x="{x+bw/2:.1f}" y="{vy:.1f}" text-anchor="middle" font-size="12" font-weight="800" fill="{col}">{fmt_usd(v)}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-2}" text-anchor="middle" font-size="11" font-weight="700" fill="#9fb6d4">{label}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(out)}</svg>'


def progress_rows(rows, w, h):
    """Weekly Change Summary: 5 rindas, nosaukums | josla (atsevišķā kolonnā) | vērtība."""
    items = []
    n = len(rows)
    row_h = h / n
    label_w = 78
    val_w = 70
    bar_w = w - label_w - val_w - 12
    for i, (label, val_str, val_num, up) in enumerate(rows):
        y = row_h * i + row_h / 2
        col = "#00ff9d" if up else "#ff3b5c"
        # josla mērogota, clamp 0..100%
        pct = max(0.0, min(100.0, abs(val_num) * 2.0))
        bar_x = label_w
        bar_y = y - 5
        items.append(f"""
        <g>
          <text x="0" y="{y+4}" font-size="13" font-weight="700" fill="#cfe0ff">{label}</text>
          <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="rgba(255,255,255,0.10)"/>
          <rect x="{bar_x}" y="{bar_y}" width="{bar_w*pct/100:.1f}" height="10" rx="5" fill="{col}" style="filter:drop-shadow(0 0 5px {col}88);"/>
          <text x="{w}" y="{y+4}" text-anchor="end" font-size="13" font-weight="800" fill="{col}">{val_str}</text>
        </g>""")
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(items)}</svg>'


# ---------------- HTML uzbūve ----------------

def build_html(d, bg_data_uri=None):
    if bg_data_uri:
        bg_css = (
            "linear-gradient(rgba(8,6,28,0.50), rgba(8,6,28,0.50)), "
            f"url('data:image/png;base64,{bg_data_uri}') center/cover no-repeat, "
            "radial-gradient(1600px 700px at 50% -10%, #2a1a5e, #120b33 55%, #07041a)"
        )
    else:
        bg_css = (
            "radial-gradient(1600px 700px at 50% -10%, #2a1a5e, #120b33 55%, #07041a), "
            "radial-gradient(900px 500px at 85% 90%, #0a3a4a, transparent 60%), "
            "radial-gradient(900px 500px at 10% 80%, #3a0a4a, transparent 60%)"
        )

    btc_7d = d.get("btc_7d", 0)
    eth_7d = d.get("eth_7d", 0)
    btc_dom = d.get("btc_dom", 0)
    eth_dom = d.get("eth_dom", 0)
    fng = d.get("fng", 0)
    fng_class = d.get("fng_class", "")
    fng_prev = d.get("fng_prev", fng)
    fng_chg = fng - fng_prev

    etf = d.get("etf") or {}
    btc_etf = etf.get("BTC") or {}
    eth_etf = etf.get("ETH") or {}
    btc_etf_this = btc_etf.get("this_week")
    eth_etf_this = eth_etf.get("this_week")
    btc_etf_prev = btc_etf.get("prev_week", 0)
    eth_etf_prev = eth_etf.get("prev_week", 0)
    btc_etf_daily = btc_etf.get("daily", [])
    eth_etf_daily = eth_etf.get("daily", [])
    btc_etf_chg = (btc_etf_this - btc_etf_prev) if btc_etf_this is not None else None
    eth_etf_chg = (eth_etf_this - eth_etf_prev) if eth_etf_this is not None else None

    # Grafiki
    chart_w, chart_h = 300, 130
    mc_chart = area_chart(d.get("total_cap_series", []), chart_w, chart_h, "#00d4ff", "gmc")
    btc_chart = candlestick(d.get("btc_series", []), chart_w, chart_h)
    eth_chart = smooth_line(d.get("eth_series", []), chart_w, chart_h, "#b44dff", "geth")
    dom_chart = donut(btc_dom, eth_dom, chart_w, chart_h)
    fng_chart = gauge(fng, fng_prev, chart_w, chart_h)
    btc_etf_chart = etf_bars(btc_etf_daily, btc_etf_prev, btc_etf_this or 0, chart_w, chart_h, "#ff8a3d")
    eth_etf_chart = etf_bars(eth_etf_daily, eth_etf_prev, eth_etf_this or 0, chart_w, chart_h, "#7a5cff")

    # Weekly Change Summary
    net_etf = (btc_etf_this or 0) + (eth_etf_this or 0)
    summary_rows = [
        ("Market Cap", fmt_pct(btc_7d), btc_7d, btc_7d >= 0),
        ("BTC", fmt_pct(btc_7d), btc_7d, btc_7d >= 0),
        ("ETH", fmt_pct(eth_7d), eth_7d, eth_7d >= 0),
        ("Fear & Greed", f"{fng_chg:+.0f} pts", fng_chg, fng_chg >= 0),
        ("ETF Net", fmt_usd(net_etf), net_etf, net_etf >= 0),
    ]
    greens = sum(1 for _, _, _, u in summary_rows if u)
    tone = "Risk-on" if greens >= 3 else ("Cautious" if greens == 2 else "Risk-off")
    tone_color = "#00ff9d" if tone == "Risk-on" else ("#ffb300" if tone == "Cautious" else "#ff3b5c")
    sum_chart = progress_rows(summary_rows, chart_w, chart_h)

    def card(title, chart, value, sub, up, accent, glow, icon, value_red=False, prev_capsule=None):
        val_color = "#ff3b5c" if value_red else "#ffffff"
        capsule = ""
        if prev_capsule:
            capsule = f'<div class="capsule">{prev_capsule}</div>'
        return f"""
        <div class="card" style="--accent:{accent}; --glow:{glow};">
          <div class="card-top">
            <div class="card-title">{title}</div>
            <div class="card-icon" style="background:linear-gradient(135deg,{accent},#ffffff33);">{icon}</div>
          </div>
          <div class="chart">{chart}</div>
          <div class="card-value" style="color:{val_color};">{value}</div>
          <div class="card-sub" style="color:{'#00ff9d' if up else '#ff3b5c'};">
            {tri(up)} {sub}
          </div>
          {capsule}
        </div>"""

    def icon_svg(color, kind):
        if kind == "cap":
            return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 7h6v6" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        if kind == "btc":
            return f'<text x="12" y="18" font-size="20" font-weight="900" text-anchor="middle" fill="{color}">₿</text>'
        if kind == "eth":
            return f'<text x="12" y="18" font-size="20" font-weight="900" text-anchor="middle" fill="{color}">Ξ</text>'
        if kind == "dom":
            return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2.5"/><path d="M12 3v9l6 3" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        if kind == "fng":
            return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 100 18 9 9 0 000-18z" stroke="{color}" stroke-width="2.5"/><path d="M8 14l2-2 2 2 4-4" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        if kind == "etf":
            return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="16" rx="3" stroke="{color}" stroke-width="2.5"/><path d="M8 12h8M8 16h5" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        if kind == "sum":
            return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        return ""

    cards = []
    cards.append(card("Market Capitalization", mc_chart, fmt_usd(d.get("total_cap", 0)),
                      f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0,
                      "#00d4ff", "rgba(0,212,255,0.55)", icon_svg("#00d4ff", "cap")))
    cards.append(card("Bitcoin (BTC) Price", btc_chart, f"${d.get('btc_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0,
                      "#ffb300", "rgba(255,179,0,0.55)", icon_svg("#ffb300", "btc")))
    cards.append(card("Ethereum (ETH) Price", eth_chart, f"${d.get('eth_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(eth_7d)}", eth_7d >= 0,
                      "#b44dff", "rgba(180,77,255,0.55)", icon_svg("#b44dff", "eth")))
    cards.append(card("Bitcoin Dominance", dom_chart, f"{btc_dom:.1f}%",
                      "share of total market", btc_dom >= 50,
                      "#00e5a0", "rgba(0,229,160,0.55)", icon_svg("#00e5a0", "dom")))
    cards.append(card("Fear & Greed Index", fng_chart, f"{fng}",
                      f"{fng_class} · {fng_chg:+.0f} pts", fng_chg >= 0,
                      "#ff5ce1", "rgba(255,92,225,0.55)", icon_svg("#ff5ce1", "fng")))
    if btc_etf_this is not None:
        cards.append(card("Bitcoin ETF Weekly Inflow", btc_etf_chart, fmt_usd(btc_etf_this),
                          f"vs previous week {fmt_usd(btc_etf_chg)}", (btc_etf_chg or 0) >= 0,
                          "#ff8a3d", "rgba(255,138,61,0.55)", icon_svg("#ff8a3d", "btc"),
                          value_red=(btc_etf_this < 0),
                          prev_capsule=f"Prev week {fmt_usd(btc_etf_prev)}"))
    if eth_etf_this is not None:
        cards.append(card("Ethereum ETF Weekly Inflow", eth_etf_chart, fmt_usd(eth_etf_this),
                          f"vs previous week {fmt_usd(eth_etf_chg)}", (eth_etf_chg or 0) >= 0,
                          "#7a5cff", "rgba(122,92,255,0.55)", icon_svg("#7a5cff", "eth"),
                          value_red=(eth_etf_this < 0),
                          prev_capsule=f"Prev week {fmt_usd(eth_etf_prev)}"))

    # 8. Weekly Change Summary
    summary_card = f"""
    <div class="card" style="--accent:#ffd700; --glow:rgba(255,215,0,0.55);">
      <div class="card-top">
        <div class="card-title">Weekly Change Summary</div>
        <div class="card-icon" style="background:linear-gradient(135deg,#ffd700,#ffffff33);">{icon_svg("#ffd700", "sum")}</div>
      </div>
      <div class="chart">{sum_chart}</div>
      <div class="tone" style="color:{tone_color}; border-color:{tone_color}66;">{tone}</div>
    </div>"""
    cards.append(summary_card)

    cards_html = "\n".join(cards)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    width:1600px; height:900px;
    background:{bg_css};
    font-family:-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color:#f4f6ff; padding:48px;
    display:flex; flex-direction:column;
  }}
  .header {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:24px;
  }}
  .title {{
    font-size:40px; font-weight:900; letter-spacing:1px;
    background:linear-gradient(90deg,#ffffff 0%,#9fd0ff 40%,#c9a7ff 100%);
    -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
    filter:drop-shadow(0 0 18px rgba(120,160,255,0.45));
  }}
  .subtitle {{ font-size:18px; color:#b9c8e8; margin-top:4px; letter-spacing:0.3px; }}
  .badge {{
    background:linear-gradient(135deg,rgba(255,255,255,0.16),rgba(255,255,255,0.05));
    border:1px solid rgba(255,255,255,0.28);
    border-radius:14px; padding:9px 16px; font-size:16px; font-weight:700;
    color:#eaf2ff; backdrop-filter:blur(10px);
    box-shadow:0 0 24px rgba(120,160,255,0.25), inset 0 1px 0 rgba(255,255,255,0.25);
  }}
  .grid {{
    display:grid; grid-template-columns:repeat(4,1fr); grid-template-rows:repeat(2,1fr);
    gap:24px; flex:1;
  }}
  .card {{
    position:relative;
    background:linear-gradient(160deg, rgba(20,16,48,0.72), rgba(10,8,30,0.55));
    border:1px solid rgba(255,255,255,0.22);
    border-radius:20px; padding:18px 20px 14px;
    backdrop-filter:blur(14px);
    box-shadow:
      0 10px 40px rgba(0,0,0,0.45),
      0 0 0 1px rgba(255,255,255,0.06) inset,
      0 0 30px var(--glow);
    display:flex; flex-direction:column;
    overflow:hidden;
  }}
  .card::after {{
    content:""; position:absolute; top:0; left:0; width:120px; height:120px;
    border-radius:50%;
    background:radial-gradient(circle, var(--glow), transparent 70%);
    opacity:0.30; pointer-events:none;
  }}
  .card-top {{ display:flex; align-items:flex-start; justify-content:space-between; }}
  .card-title {{ font-size:15px; color:#e6eeff; font-weight:700; line-height:1.2; }}
  .card-icon {{
    width:48px; height:48px; border-radius:12px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 18px var(--glow), inset 0 1px 0 rgba(255,255,255,0.4);
  }}
  .chart {{ margin-top:8px; flex:1; display:flex; align-items:center; justify-content:center; min-height:0; }}
  .chart svg {{ width:100%; height:100%; }}
  .card-value {{ font-size:34px; font-weight:900; margin-top:6px; letter-spacing:0.5px;
    text-shadow:0 0 20px var(--glow); }}
  .card-sub {{ font-size:14px; font-weight:700; margin-top:6px; }}
  .capsule {{
    margin-top:6px; display:inline-block; align-self:flex-start;
    background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.18);
    border-radius:8px; padding:3px 10px; font-size:12px; font-weight:700; color:#cfe0ff;
  }}
  .tone {{
    margin-top:8px; text-align:center; font-size:15px; font-weight:900;
    border:1px solid; border-radius:9px; padding:5px 0;
  }}
</style></head>
<body>
  <div class="header">
    <div>
      <div class="title">CRYPTO MARKET WEEKLY SUMMARY</div>
      <div class="subtitle">Comparison vs. previous week</div>
    </div>
    <div class="badge">Weekly Report</div>
  </div>
  <div class="grid">
    {cards_html}
  </div>
</body></html>"""
    return html


def render(html, out_path, width=1600, height=900):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        pg.set_content(html, wait_until="networkidle")
        pg.wait_for_timeout(300)
        pg.screenshot(path=out_path, full_page=True, animations="disabled")
        b.close()


def generate_dashboard(d, out_path):
    """kie.ai fons + HTML dati virsū. Ja kie.ai neizdodas, iebūvētais fons."""
    bg_data_uri = None
    api_key = load_api_key()
    if api_key:
        try:
            if check_credits(api_key) < 6:
                print("⚠️ kie.ai kredīti < 6 — izmantoju iebūvēto fonu.")
            else:
                tmp_bg = out_path + ".bg.png"
                url = generate_background(tmp_bg, api_key)
                download(url, tmp_bg)
                bg_data_uri = _bg_data_uri(tmp_bg)
                if os.path.exists(tmp_bg):
                    os.remove(tmp_bg)
        except Exception as e:
            print(f"⚠️ kie.ai fons neizdevās, izmantoju iebūvēto fonu: {e}")
            bg_data_uri = None
    html = build_html(d, bg_data_uri)
    render(html, out_path)
    print("saved", out_path, os.path.getsize(out_path))
    return out_path


def main():
    out = sys.argv[1]
    data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    generate_dashboard(data, out)


if __name__ == "__main__":
    main()
