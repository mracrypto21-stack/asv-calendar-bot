#!/usr/bin/env python3
"""ASV ekonomikas dati — kripto-stila dashboard (kie.ai fons + HTML/SVG → PNG).

Tāds pats dizains kā kripto nedēļas update: pilns 8 kartīšu 4x2 režģis ar
neon glassmorphism un reālām SVG diagrammām, bet datus rāda ASV ekonomiskos
rādītājus no FRED. KIE ģenerē TIKAI fonu (bez teksta/cipariem); visi skaitļi
tiek uzlikti kā reāls HTML → pikseļprecīzi.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 asv_dashboard_html.py <out.png> [key1 key2 ...]
Rāda FIKSU 8 kartīšu komplektu (neatkarīgi no padotajiem keys), lai bilde
vienmēr būtu pilna kā kripto.
"""
import os
import sys
import json
import time
import math
import base64
import csv
import io
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
    prompt = (
        "Dark premium financial data background, deep navy and gold macro "
        "economic theme, elegant glowing charts, subtle GDP growth curve and "
        "stock market candle, corporate skyline silhouette in dark navy, "
        "neon amber and gold glowing accents, luxury fintech aesthetic, "
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


# ---------------- FRED dati (tā pati loģika kā ASV kalendāram) ----------------

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2022-01-01"

REGISTRY = {
    "gdp":      dict(id="GDPC1",    title="GDP Growth",          unit="% y/y",  calc="yoy_q",  accent="#00ff9d", icon="cap"),
    "bezdarbs": dict(id="UNRATE",   title="Unemployment Rate",   unit="%",       calc="value",  accent="#00d4ff", icon="dom"),
    "cpi":      dict(id="CPIAUCSL", title="Inflation (CPI)",     unit="% y/y",   calc="yoy",    accent="#ff5ce1", icon="fng"),
    "gauge":    dict(id="DFEDTARU", title="Fed Funds Rate",      unit="%",       calc="gauge",  accent="#ffb300", icon="fng"),
    "retail":   dict(id="RSAFS",    title="Retail Sales",        unit="% m/m",   calc="mom",    accent="#00e5a0", icon="cap"),
    "ind":      dict(id="INDPRO",   title="Industrial Production", unit="% m/m", calc="mom",    accent="#b44dff", icon="eth"),
    "sent":     dict(id="UMCSENT",  title="Consumer Sentiment",  unit="idx.",    calc="sent",   accent="#ff8a3d", icon="fng"),
}


def _fetch(sid):
    r = requests.get(FRED_BASE.format(sid=sid), headers={"User-Agent": "curl/8.0"}, timeout=20)
    r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.text)))[1:]
    return [(row[0], row[1]) for row in rows if len(row) >= 2 and row[1] not in ("", ".")]


def _d(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return float("nan")


def _series(sid, calc):
    raw = _fetch(sid)
    dates = [x[0] for x in raw]
    nums = [_d(x[1]) for x in raw]
    if calc == "value" or calc == "sent" or calc == "gauge":
        vals = nums
    elif calc == "yoy":
        vals = [(nums[i] / nums[i - 12] - 1) * 100 if i >= 12 and nums[i - 12] else float("nan") for i in range(len(nums))]
    elif calc == "yoy_q":
        vals = [(nums[i] / nums[i - 4] - 1) * 100 if i >= 4 and nums[i - 4] else float("nan") for i in range(len(nums))]
    elif calc == "mom":
        vals = [(nums[i] / nums[i - 1] - 1) * 100 if i >= 1 and nums[i - 1] else float("nan") for i in range(len(nums))]
    else:
        vals = nums
    pairs = [(d, v) for d, v in zip(dates, vals) if v == v]
    return pairs[-16:]


def _fmt(card, last):
    if last != last:
        return "—"
    if card["calc"] in ("yoy", "yoy_q", "mom"):
        return f"{last:+.1f}%"
    if card["calc"] == "gauge":
        return f"{last:.2f}%"
    return f"{last:.1f}"


# ---------------- SVG grafiku ģeneratori (kā kripto) ----------------

def area_chart(series, w, h, color, gid):
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


def smooth_line(series, w, h, color, gid):
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


def bars(series, w, h, color, fmt=None):
    """Joslu grafiks no nulles līnijas (m/m vai y/y izmaiņas)."""
    if not series or len(series) < 2:
        return ""
    vals = [float(v) for v in series]
    maxv = max([abs(v) for v in vals] + [1.0])
    pad = 8
    n = len(vals)
    bw = (w - 2 * pad) / n * 0.6
    zero = h / 2
    scale = (h / 2 - 14) / maxv
    out = []
    out.append(f'<line x1="0" y1="{zero:.1f}" x2="{w}" y2="{zero:.1f}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>')
    max_i = max(range(n), key=lambda i: abs(vals[i]))
    for i, v in enumerate(vals):
        x = pad + i * (w - 2 * pad) / n + ((w - 2 * pad) / n - bw) / 2
        col = "#00ff9d" if v >= 0 else "#ff3b5c"
        bh = abs(v) * scale
        y = zero - bh if v >= 0 else zero
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{col}" style="filter:drop-shadow(0 0 4px {col}66);"/>')
        if i == max_i:
            vy = y - 6 if v >= 0 else y + bh + 16
            label = f"{v:+.1f}%" if not fmt else fmt(v)
            out.append(f'<text x="{x+bw/2:.1f}" y="{vy:.1f}" text-anchor="middle" font-size="11" font-weight="800" fill="{col}">{label}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(out)}</svg>'


def gauge(value, floor, ceil, w, h, left_label, right_label, accent_start="#ff3b5c", accent_end="#00b36b"):
    """Pusloka spidometrs (piem. Fed likme: Loose→Tight; Noskaņojums: Pestimistic→Optimistic)."""
    frac0 = 0.0
    frac1 = 1.0
    value = max(floor, min(ceil, value))
    frac = (value - floor) / ((ceil - floor) or 1.0)
    cx, cy = w / 2, h - 6
    r = min(w, h * 2) / 2 - 8
    def angle(f):
        return 180 - f * 180
    def pt(f, rad):
        a = angle(f) * math.pi / 180
        return (cx + rad * math.cos(a), cy - rad * math.sin(a))
    # gradēta skala
    segs = ""
    nseg = 10
    for i in range(nseg):
        v0, v1 = frac0 + i / nseg, frac0 + (i + 1) / nseg
        t = (v0 + v1) / 2
        col = accent_start if t < 0.5 else accent_end
        a0 = angle(v0) * math.pi / 180
        a1 = angle(v1) * math.pi / 180
        x0, y0 = cx + r * math.cos(a0), cy - r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy - r * math.sin(a1)
        segs += f'<path d="M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{col}" stroke-width="13" stroke-linecap="butt" style="filter:drop-shadow(0 0 5px {col}66);"/>'
    # left/right labels
    fx, fy = pt(0.06, r + 6)
    gx, gy = pt(0.94, r + 6)
    labels = (f'<text x="{fx:.1f}" y="{fy:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#ff8a3d">{left_label}</text>'
              f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#00e5a0">{right_label}</text>')
    ax, ay = pt(frac, r - 14)
    needle = f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#ffffff" stroke-width="3" stroke-linecap="round" style="filter:drop-shadow(0 0 6px #ffffff88);"/>'
    hub = f'<circle cx="{cx}" cy="{cy}" r="6" fill="#ffffff"/>'
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">
      {segs}
      {labels}
      {needle}
      {hub}
    </svg>"""


def progress_rows(rows, w, h):
    items = []
    n = len(rows)
    row_h = h / n
    label_w = 102
    val_w = 62
    bar_w = w - label_w - val_w - 12
    for i, (label, val_str, val_num, up) in enumerate(rows):
        y = row_h * i + row_h / 2
        col = "#00ff9d" if up else "#ff3b5c"
        pct = max(0.0, min(100.0, abs(val_num) * 4.0))
        bar_x = label_w
        bar_y = y - 5
        items.append(f"""
        <g>
          <text x="0" y="{y+4}" font-size="12" font-weight="700" fill="#cfe0ff">{label}</text>
          <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="rgba(255,255,255,0.10)"/>
          <rect x="{bar_x}" y="{bar_y}" width="{bar_w*pct/100:.1f}" height="10" rx="5" fill="{col}" style="filter:drop-shadow(0 0 5px {col}88);"/>
          <text x="{w}" y="{y+4}" text-anchor="end" font-size="12" font-weight="800" fill="{col}">{val_str}</text>
        </g>""")
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">{"".join(items)}</svg>'


def tri(up, size=13):
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


def icon_svg(color, kind):
    if kind == "cap":
        return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 7h6v6" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    if kind == "eth":
        return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
    if kind == "dom":
        return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2.5"/><path d="M12 3v9l6 3" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
    if kind == "fng":
        return f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 100 18 9 9 0 000-18z" stroke="{color}" stroke-width="2.5"/><path d="M8 14l2-2 2 2 4-4" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    return ""


# ---------------- HTML uzbūve ----------------

def build_html(d, bg_data_uri=None):
    if bg_data_uri:
        bg_css = (
            "linear-gradient(rgba(8,6,28,0.52), rgba(8,6,28,0.52)), "
            f"url('data:image/png;base64,{bg_data_uri}') center/cover no-repeat, "
            "radial-gradient(1600px 700px at 50% -10%, #2a1a5e, #120b33 55%, #07041a)"
        )
    else:
        bg_css = (
            "radial-gradient(1600px 700px at 50% -10%, #2a1a5e, #120b33 55%, #07041a), "
            "radial-gradient(900px 500px at 85% 90%, #0a3a4a, transparent 60%), "
            "radial-gradient(900px 500px at 10% 80%, #3a0a4a, transparent 60%)"
        )

    # Ielasīt datus visiem rādītājiem + aprēķināt summary
    card_data = {}
    for key, card in REGISTRY.items():
        try:
            pairs = _series(card["id"], card["calc"])
            card_data[key] = dict(card=card, pairs=pairs, last=pairs[-1][1] if pairs else float("nan"))
        except Exception:
            card_data[key] = dict(card=card, pairs=[], last=float("nan"))

    def lastval(key):
        return card_data[key]["last"]

    def series(key):
        return [v for _, v in card_data[key]["pairs"]]

    chart_w, chart_h = 300, 130

    gdp_chart = area_chart(series("gdp"), chart_w, chart_h, "#00ff9d", "ggdp")
    unr_chart = smooth_line(series("bezdarbs"), chart_w, chart_h, "#00d4ff", "gunr")
    cpi_chart = smooth_line(series("cpi"), chart_w, chart_h, "#ff5ce1", "gcpi")
    fed_chart = gauge(lastval("gauge"), 0.0, 6.0, chart_w, chart_h, "Loose", "Tight")
    retail_chart = bars(series("retail"), chart_w, chart_h, "#00e5a0")
    ind_chart = bars(series("ind"), chart_w, chart_h, "#b44dff")
    sent_chart = gauge(lastval("sent"), 50.0, 120.0, chart_w, chart_h, "Pess.", "Opt.")

    # Weekly Change Summary (ekonomiskā versija)
    def ch(series, i=-1):
        if len(series) < 2:
            return 0.0
        return series[i] - series[i - 1]
    gdp_last = lastval("gdp")
    unr_last = lastval("bezdarbs")
    cpi_last = lastval("cpi")
    ret_last = lastval("retail")
    fed_last = lastval("gauge")
    sent_last = lastval("sent")
    gdp_ch = ch(series("gdp"))
    unr_ch = ch(series("bezdarbs"))
    cpi_ch = ch(series("cpi"))
    ret_ch = ch(series("retail"))
    fed_ch = ch(series("gauge"))
    summary_rows = [
        ("GDP Growth", f"{gdp_ch:+.1f} pp", gdp_ch, gdp_ch >= 0),
        ("Unemployment", f"{unr_ch:+.1f} pp", unr_ch, unr_ch <= 0),
        ("Inflation CPI", f"{cpi_ch:+.1f} pp", cpi_ch, cpi_ch <= 0),
        ("Retail Sales", f"{ret_ch:+.1f} pp", ret_ch, ret_ch >= 0),
        ("Fed Funds", f"{fed_ch:+.2f} pts", fed_ch, fed_ch <= 0),
    ]
    good = sum(1 for _, _, _, u in summary_rows if u)
    tone = "Strong economy" if good >= 4 else ("Stable balance" if good >= 2 else "Pressure")
    tone_color = "#00ff9d" if good >= 4 else ("#ffb300" if good >= 2 else "#ff3b5c")
    sum_chart = progress_rows(summary_rows, chart_w, chart_h)

    def card(title, chart, value, sub, up, accent, glow, icon, unit=None):
        return f"""
        <div class="card" style="--accent:{accent}; --glow:{glow};">
          <div class="card-top">
            <div class="card-title">{title}</div>
            <div class="card-icon" style="background:linear-gradient(135deg,{accent},#ffffff33);">{icon}</div>
          </div>
          <div class="chart">{chart}</div>
          <div class="card-value" style="color:#ffffff;">{value}</div>
          <div class="card-sub" style="color:#9fb6d4;">{unit or ''}</div>
          <div class="card-sub" style="color:{'#00ff9d' if up else '#ff3b5c'};">
            {tri(up)} {sub}
          </div>
        </div>"""

    def sub_str(key):
        pairs = card_data[key]["pairs"]
        return pairs[-1][0][:7] if pairs else ""

    cards = []
    cards.append(card(
        REGISTRY["gdp"]["title"], gdp_chart, _fmt(REGISTRY["gdp"], gdp_last),
        f"{gdp_ch:+.1f} pp change", gdp_ch >= 0,
        "#00ff9d", "rgba(0,255,157,0.55)", icon_svg("#00ff9d", "cap"), unit=f"% y/y · {sub_str('gdp')}"))
    cards.append(card(
        REGISTRY["bezdarbs"]["title"], unr_chart, _fmt(REGISTRY["bezdarbs"], unr_last),
        f"{unr_ch:+.1f} pp change", unr_ch >= 0,
        "#00d4ff", "rgba(0,212,255,0.55)", icon_svg("#00d4ff", "dom"), unit=f"% · {sub_str('bezdarbs')}"))
    cards.append(card(
        REGISTRY["cpi"]["title"], cpi_chart, _fmt(REGISTRY["cpi"], cpi_last),
        f"{cpi_ch:+.1f} pp change", cpi_ch >= 0,
        "#ff5ce1", "rgba(255,92,225,0.55)", icon_svg("#ff5ce1", "fng"), unit=f"% y/y · {sub_str('cpi')}"))
    cards.append(card(
        REGISTRY["gauge"]["title"], fed_chart, f"{fed_last:.2f}%",
        f"{fed_ch:+.2f} pts change", fed_ch >= 0,
        "#ffb300", "rgba(255,179,0,0.55)", icon_svg("#ffb300", "fng"), unit=f"% · {sub_str('gauge')}"))
    cards.append(card(
        REGISTRY["retail"]["title"], retail_chart, _fmt(REGISTRY["retail"], ret_last),
        f"{ret_ch:+.1f} pp change", ret_ch >= 0,
        "#00e5a0", "rgba(0,229,160,0.55)", icon_svg("#00e5a0", "cap"), unit=f"% m/m · {sub_str('retail')}"))
    cards.append(card(
        REGISTRY["ind"]["title"], ind_chart, _fmt(REGISTRY["ind"], lastval("ind")),
        f"last month {lastval('ind'):+.1f}%", lastval("ind") >= 0,
        "#b44dff", "rgba(180,77,255,0.55)", icon_svg("#b44dff", "eth"), unit=f"% m/m · {sub_str('ind')}"))
    cards.append(card(
        REGISTRY["sent"]["title"], sent_chart, f"{sent_last:.1f}",
        f"idx. · {sub_str('sent')}", sent_last >= 50,
        "#ff8a3d", "rgba(255,138,61,0.55)", icon_svg("#ff8a3d", "fng"), unit="idx."))

    # 8. Weekly Change Summary
    summary_card = f"""
    <div class="card" style="--accent:#ffd700; --glow:rgba(255,215,0,0.55);">
      <div class="card-top">
        <div class="card-title">Weekly Change Summary</div>
        <div class="card-icon" style="background:linear-gradient(135deg,#ffd700,#ffffff33);">{icon_svg("#ffd700", "eth")}</div>
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
      <div class="title">US ECONOMIC DATA</div>
      <div class="subtitle">Current indicators · {time.strftime('%m/%d/%Y')}</div>
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


def generate_dashboard(d_keys, out_path):
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
    html = build_html(None, bg_data_uri)
    render(html, out_path)
    print("saved", out_path, os.path.getsize(out_path))
    return out_path


def main():
    out = sys.argv[1]
    # keys ignorējam — rādām fiksu pilnu 8 kartīšu komplektu (kā kripto)
    generate_dashboard(sys.argv[2:], out)


if __name__ == "__main__":
    main()
