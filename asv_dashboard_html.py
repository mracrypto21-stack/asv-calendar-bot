#!/usr/bin/env python3
"""ASV ekonomikas dati — HTML→PNG dashboard (pikseļprecīzs teksts).

Atšķirībā no AI attēlu ģenerēšanas (kas bojā tekstu/ciparus), šī metode
ģenerē reālu HTML, kas tiek nofotografēts ar headless Chromium. Teksts ir
pikseļprecīzs, un visi skaitļi nāk no FRED (tie paši dati, ko lieto
asv_calendar.py).

Lietošana:
    /usr/bin/python3 asv_dashboard_html.py <out.png> key1 key2 ...

Atkarīgs no /usr/bin/python3 (sistēmas python), jo tam ir playwright + requests.
"""
import sys
import os
import csv
import io
import base64
import requests

# ---------------------------------------------------------------------------
# FRED dati — tā pati logika kā asv_calendar.py / asv_dashboard.py
# ---------------------------------------------------------------------------
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2022-01-01"

REGISTRY = {
    "gdp":      dict(id="GDPC1",    title="GDP Growth",       unit="% y/y", calc="yoy_q",  icon="📈"),
    "bezdarbs": dict(id="UNRATE",   title="Unemployment Rate", unit="%",     calc="value", icon="👥"),
    "cpi":      dict(id="CPIAUCSL", title="Inflation (CPI)",   unit="% y/y",  calc="yoy",   icon="🏷️"),
    "corecpi":  dict(id="CPILFESL", title="Core Inflation",    unit="% y/y",  calc="yoy",   icon="🏷️"),
    "ppi":      dict(id="PPIFIS",   title="Producer Prices",   unit="% y/y",  calc="yoy",   icon="🏭"),
    "coreppi":  dict(id="PPIFES",   title="Core PPI",          unit="% y/y",  calc="yoy",   icon="🏭"),
    "retail":   dict(id="RSAFS",    title="Retail Sales",      unit="% m/m",  calc="mom",   icon="🛒"),
    "ind":      dict(id="INDPRO",   title="Industrial Production", unit="% m/m", calc="mom", icon="⚙️"),
    "sent":     dict(id="UMCSENT",  title="Consumer Sentiment", unit="idx.", calc="value", icon="💬"),
    "housing":  dict(id="HOUST",    title="Housing Starts",    unit="thous.", calc="value_th", icon="🏠"),
    "gauge":    dict(id="DFEDTARU", title="Fed Funds Rate",    unit="%",      calc="gauge", icon="🏛️"),
}

# krāsu akcents katrai kartei (zelta/amber variants)
ACCENT = {
    "gdp": "#2fbf71", "bezdarbs": "#5aa9e6", "cpi": "#ef6c6c", "corecpi": "#ef6c6c",
    "ppi": "#f0b34a", "coreppi": "#f0b34a", "retail": "#2fbf71", "ind": "#2fbf71",
    "sent": "#f0b34a", "housing": "#5aa9e6", "gauge": "#f0c860",
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
    if calc == "value":
        vals = nums
    elif calc == "value_th":
        vals = [n / 1000.0 for n in nums]
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
    c = card["calc"]
    if c == "gauge":
        return f"{last:.2f}%" if last == last else "—"
    if c in ("yoy", "yoy_q", "mom"):
        return f"{last:+.1f}%" if last == last else "—"
    return f"{last:.1f}" if last == last else "—"


def _sparkline_poly(pairs, accent):
    """SVG polylīnija — līnijas grafiks. Atgriež (points, y_min, y_max)."""
    ys = [p[1] for p in pairs]
    if not ys:
        return "", "", ""
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    lo -= span * 0.15
    hi += span * 0.15
    n = len(ys)
    w, h = 220, 60
    pts = []
    for i, v in enumerate(ys):
        x = (i / (n - 1)) * w if n > 1 else 0
        y = h - ((v - lo) / ((hi - lo) or 1)) * h
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts), lo, hi


def _bars_svg(pairs, accent):
    """SVG stabiņu diagramma (m/m vai g/g ar nulles līniju)."""
    ys = [p[1] for p in pairs]
    if not ys:
        return ""
    mx = max(abs(v) for v in ys) or 1.0
    n = len(ys)
    w, h = 220, 60
    mid = h * 0.8
    bw = w / n * 0.6
    parts = []
    for i, v in enumerate(ys):
        x = i * (w / n) + (w / n - bw) / 2
        bh = (v / mx) * (h * 0.62)
        col = accent if v >= 0 else "#ef6c6c"
        y = mid - bh if v > 0 else mid
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{abs(bh):.1f}" fill="{col}" rx="2"/>')
    return '<line x1="0" y1="{mid}" x2="{w}" y2="{mid}" stroke="#3a5a7a" stroke-width="1"/>'.format(mid=mid, w=w) + "".join(parts)


def build_html(keys, bg_data_uri=None):
    if bg_data_uri:
        # kie.ai premium fons + tumšs pārklājums, lai dati būtu skaidri salasāmi
        bg_css = (
            "linear-gradient(rgba(7,19,35,0.55), rgba(7,19,35,0.55)), "
            f"url('data:image/png;base64,{bg_data_uri}') center/cover no-repeat, "
            "radial-gradient(1200px 520px at 50% -10%, #12314f, #091a2e 60%, #06111f)"
        )
    else:
        bg_css = "radial-gradient(1200px 520px at 50% -10%, #12314f, #091a2e 60%, #06111f)"
    cards_html = []
    # Kolonnu skaits atbilstoši kartīšu skaitam — lai bilde vienmēr būtu piepildīta
    if len(keys) == 1:
        cols = 1
    elif len(keys) in (2, 4):
        cols = 2
    elif len(keys) == 3:
        cols = 3
    elif len(keys) <= 6:
        cols = 3
    else:
        cols = 6
    # Feder gauge kartīte nedefinē kolonnu izkārtojumu — viss vienotā režģī
    for idx, key in enumerate(keys):
        card = REGISTRY[key]
        span = 2 if (len(keys) == 7 and idx < 3) else (3 if (len(keys) == 7 and idx >= 3) else 1)
        try:
            pairs = _series(card["id"], card["calc"])
            last = pairs[-1][1]
        except Exception:
            pairs, last = [], float("nan")
        val = _fmt(card, last)
        per = pairs[-1][0][:7] if pairs else ""
        accent = ACCENT.get(key, "#f0c860")

        if card["calc"] == "gauge":
            frac = max(0.0, min(1.0, (last - 1.5) / 4.0)) if last == last else 0.5
            conic = "linear-gradient(90deg,#2fbf71 0%,#f0b34a 50%,#ef6c6c 100%)"
            gauge = (
                f'<div class="gauge"><div class="gauge-bg" style="background:{conic}">'
                f'<div class="gauge-arrow" style="left:{frac*100:.1f}%"></div></div></div>'
            )
        elif card["calc"] in ("yoy", "yoy_q", "mom"):
            gauge = f'<svg class="chart" viewBox="0 0 220 70">{_bars_svg(pairs, accent)}</svg>'
        else:
            pts, _, _ = _sparkline_poly(pairs, accent)
            gauge = (
                f'<svg class="chart" viewBox="0 0 220 70">'
                f'<polyline points="{pts}" fill="none" stroke="{accent}" stroke-width="2.5" stroke-linejoin="round"/>'
                f'</svg>'
            )

        vcol = "#f5f1e6"
        if card["calc"] in ("yoy", "yoy_q", "mom") and last == last:
            vcol = "#2fbf71" if last >= 0 else "#ef6c6c"

        cards_html.append(f"""
        <div class="card" style="grid-column:span {span};">
          <div class="card-head">
            <span class="icon" style="background:{accent}22;color:{accent}">{card['icon']}</span>
            <span class="title">{card['title']}</span>
          </div>
          <div class="value" style="color:{vcol}">{val}</div>
          <div class="meta">{card['unit']} &middot; <span class="per">{per}</span></div>
          {gauge}
        </div>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ height:100%; }}
  body {{
    width: 1180px; height:100vh; display:flex; flex-direction:column;
    background: {bg_css};
    font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color:#f5f1e6; padding: 28px 32px 22px;
  }}
  .header {{ display:flex; align-items:center; justify-content:space-between; }}
  .header h1 {{ font-size:30px; font-weight:800; letter-spacing:.5px; }}
  .header .sub {{ color:#8fa8bf; font-size:13px; margin-top:3px; }}
  .grid {{ display:grid; grid-template-columns:repeat({cols},1fr); gap:16px; margin-top:18px; flex:1 1 auto; grid-auto-rows:1fr; }}
  .card {{
    background: rgba(20,40,63,0.35); border:1px solid rgba(255,255,255,0.18); border-radius:20px;
    padding:22px 22px 18px; display:flex; flex-direction:column; justify-content:space-between;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
  }}
  .card-head {{ display:flex; align-items:center; gap:10px; }}
  .icon {{ width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px; }}
  .title {{ font-size:17px; font-weight:700; }}
  .value {{ font-size:52px; font-weight:800; line-height:1.1; }}
  .meta {{ font-size:13px; color:#8fa8bf; }}
  .per {{ color:#c7d6e4; }}
  .chart {{ width:100%; height:110px; }}
  .gauge {{ height:18px; border-radius:8px; background:#27405a; position:relative; }}
  .gauge-bg {{ height:100%; border-radius:8px; position:relative; }}
  .gauge-arrow {{ position:absolute; top:-5px; width:3px;height:28px; background:#f5f1e6; transform:translateX(-50%); }}
  .footer {{ margin-top:16px; color:#f0c860; font-weight:700; font-size:13px; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>US ECONOMIC DATA</h1>
      <div class="sub">Current indicators &mdash; <span id="today"></span></div>
    </div>
  </div>
  <div class="grid">
    {''.join(cards_html)}
  </div>
<script>document.getElementById('today').textContent=new Date().toLocaleDateString('en-US');</script>
</body>
</html>"""


def render(html, out_path, width=1180, height=1180):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        pg.set_content(html, wait_until="networkidle")
        pg.wait_for_timeout(300)
        pg.screenshot(path=out_path, full_page=True, animations="disabled")
        b.close()


def _bg_data_uri(bg_path):
    with open(bg_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def generate_dashboard(keys, out_path, seed=None, bg_path=None):
    """Ģenerē premium dashboard: kie.ai fons + HTML dati virsū.

    - bg_path: ja dots, izmanto šo fonu (jau ģenerētu). Ja None, ģenerē
      jaunu caur kie.ai (seed = ISO nedēļas numurs → katru nedēļu savādāks).
    - Ja kie.ai neizdodas, atkāpjas uz iebūvēto gradienta fonu (bez bildes).
    """
    bg_data_uri = None
    if bg_path and os.path.exists(bg_path):
        bg_data_uri = _bg_data_uri(bg_path)
    else:
        try:
            import kie_bg
            tmp_bg = out_path + ".bg.png"
            kie_bg.generate_background(tmp_bg, seed)
            bg_data_uri = _bg_data_uri(tmp_bg)
            if os.path.exists(tmp_bg):
                os.remove(tmp_bg)
        except Exception as e:
            print(f"⚠️ kie.ai fons neizdevās, izmanto iebūvēto fonu: {e}")
            bg_data_uri = None
    html = build_html(keys, bg_data_uri)
    render(html, out_path)
    print("saved", out_path, os.path.getsize(out_path))
    return out_path


def main():
    out = sys.argv[1]
    keys = sys.argv[2:]
    if not keys:
        keys = ["gdp", "bezdarbs", "cpi", "gauge", "retail", "ind", "sent"]
    generate_dashboard(keys, out)


if __name__ == "__main__":
    main()