#!/usr/bin/env python3
"""Kripto nedēļas infografika — kie.ai fons + HTML→PNG (premium fintech).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs, jo AI modeļi slikti
renderē ciparus. kie.ai ģenerē TIKAI fonu (bez teksta/cipariem).

Dizains: premium fintech dashboard. 8 logrīki 4x2 režģī, 1600x1000,
glassmorphism kartītes ar neona glow, SVG trijstūri (▲/▼), bez avotu teksta.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 krypto_dashboard_html.py <out.png> '<json_data>'
    # json_data: {"total_cap":..., "btc_price":..., "btc_7d":...,
    #             "eth_price":..., "eth_7d":..., "btc_dom":...,
    #             "fng":..., "fng_class":..., "fng_prev":...,
    #             "etf": {"BTC": {...}, "ETH": {...}}}
"""
import os
import sys
import json
import time
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


# Labākie pieejamie KIE attēlu modeļi, secībā (labākais pirmais)
KIE_MODELS = [
    "nano-banana-2-lite",   # labākā attēla kvalitāte
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


def tri(up, size=14):
    """SVG trijstūris — ▲ zaļš / ▼ sarkans (ne emoji, lai neizplēn fonts)."""
    if up:
        pts = f"0,{size} {size},{size} {size/2},0"
        color = "#00ff9d"
    else:
        pts = f"0,0 {size},0 {size/2},{size}"
        color = "#ff3b5c"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="display:inline-block;vertical-align:middle;margin-right:6px;">'
            f'<polygon points="{pts}" fill="{color}" '
            f'style="filter:drop-shadow(0 0 6px {color}88);"/></svg>')


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
    btc_etf_chg = (btc_etf_this - btc_etf_prev) if btc_etf_this is not None else None
    eth_etf_chg = (eth_etf_this - eth_etf_prev) if eth_etf_this is not None else None

    # ---- 8 logrīki ----
    # 1. Market Cap
    mc_up = btc_7d >= 0
    # 2. BTC
    btc_up = btc_7d >= 0
    # 3. ETH
    eth_up = eth_7d >= 0
    # 4. BTC Dominance
    dom_up = btc_dom >= 50
    # 5. Fear & Greed
    fng_up = fng_chg >= 0
    # 6. BTC ETF — krāsa pēc izmaiņas pret iepr. nedēļu; vērtība sarkana ja negatīva
    btc_etf_up = (btc_etf_chg or 0) >= 0
    btc_etf_val_red = (btc_etf_this or 0) < 0
    # 7. ETH ETF
    eth_etf_up = (eth_etf_chg or 0) >= 0
    eth_etf_val_red = (eth_etf_this or 0) < 0

    # 8. Weekly Change Summary — 5 kompaktas rindiņas + tonis
    net_etf = (btc_etf_this or 0) + (eth_etf_this or 0)
    summary_rows = [
        ("Market Cap", fmt_pct(btc_7d), btc_7d >= 0),
        ("BTC", fmt_pct(btc_7d), btc_7d >= 0),
        ("ETH", fmt_pct(eth_7d), eth_7d >= 0),
        ("Fear & Greed", f"{fng_chg:+.0f} pts", fng_chg >= 0),
        ("ETF Net", fmt_usd(net_etf), net_etf >= 0),
    ]
    # Kopējais tonis: vairāk zaļo nekā sarkano → Risk-on, citādi Cautious
    greens = sum(1 for _, _, u in summary_rows if u)
    tone = "Risk-on" if greens >= 3 else "Cautious"
    tone_color = "#00ff9d" if tone == "Risk-on" else "#ffb300"

    def card(title, value, sub, up, accent, glow, icon, value_red=False):
        val_color = "#ff3b5c" if value_red else "#ffffff"
        return f"""
        <div class="card" style="--accent:{accent}; --glow:{glow};">
          <div class="card-top">
            <div class="card-title">{title}</div>
            <div class="card-icon" style="background:linear-gradient(135deg,{accent},#ffffff33);">{icon}</div>
          </div>
          <div class="card-value" style="color:{val_color};">{value}</div>
          <div class="card-sub" style="color:{'#00ff9d' if up else '#ff3b5c'};">
            {tri(up)} {sub}
          </div>
        </div>"""

    def icon_svg(color, kind):
        if kind == "cap":
            return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 7h6v6" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        if kind == "btc":
            return f'<text x="12" y="17" font-size="15" font-weight="900" text-anchor="middle" fill="{color}">₿</text>'
        if kind == "eth":
            return f'<text x="12" y="17" font-size="15" font-weight="900" text-anchor="middle" fill="{color}">Ξ</text>'
        if kind == "dom":
            return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2.5"/><path d="M12 3v9l6 3" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        if kind == "fng":
            return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 100 18 9 9 0 000-18z" stroke="{color}" stroke-width="2.5"/><path d="M8 14l2-2 2 2 4-4" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        if kind == "etf":
            return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="16" rx="3" stroke="{color}" stroke-width="2.5"/><path d="M8 12h8M8 16h5" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        if kind == "sum":
            return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/></svg>'
        return ""

    cards = []
    cards.append(card("Market Capitalization", fmt_usd(d.get("total_cap", 0)),
                      f"vs previous week {fmt_pct(btc_7d)}", mc_up,
                      "#00d4ff", "rgba(0,212,255,0.55)", icon_svg("#00d4ff", "cap")))
    cards.append(card("Bitcoin (BTC) Price", f"${d.get('btc_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(btc_7d)}", btc_up,
                      "#ffb300", "rgba(255,179,0,0.55)", icon_svg("#ffb300", "btc")))
    cards.append(card("Ethereum (ETH) Price", f"${d.get('eth_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(eth_7d)}", eth_up,
                      "#b44dff", "rgba(180,77,255,0.55)", icon_svg("#b44dff", "eth")))
    cards.append(card("Bitcoin Dominance", f"{btc_dom:.1f}%",
                      "share of total market", dom_up,
                      "#00e5a0", "rgba(0,229,160,0.55)", icon_svg("#00e5a0", "dom")))
    cards.append(card("Fear & Greed Index", f"{fng}",
                      f"{fng_class} · {fng_chg:+.0f} pts", fng_up,
                      "#ff5ce1", "rgba(255,92,225,0.55)", icon_svg("#ff5ce1", "fng")))
    if btc_etf_this is not None:
        cards.append(card("Bitcoin ETF Weekly Inflow", fmt_usd(btc_etf_this),
                          f"vs previous week {fmt_usd(btc_etf_chg)}", btc_etf_up,
                          "#ff8a3d", "rgba(255,138,61,0.55)", icon_svg("#ff8a3d", "etf"),
                          value_red=btc_etf_val_red))
    if eth_etf_this is not None:
        cards.append(card("Ethereum ETF Weekly Inflow", fmt_usd(eth_etf_this),
                          f"vs previous week {fmt_usd(eth_etf_chg)}", eth_etf_up,
                          "#7a5cff", "rgba(122,92,255,0.55)", icon_svg("#7a5cff", "etf"),
                          value_red=eth_etf_val_red))

    # 8. Weekly Change Summary
    rows_html = ""
    for label, val, up in summary_rows:
        rows_html += f"""
        <div class="sum-row">
          <span class="sum-label">{label}</span>
          <span class="sum-val" style="color:{'#00ff9d' if up else '#ff3b5c'};">{tri(up, 10)} {val}</span>
        </div>"""
    summary_card = f"""
    <div class="card" style="--accent:#ffd700; --glow:rgba(255,215,0,0.55);">
      <div class="card-top">
        <div class="card-title">Weekly Change Summary</div>
        <div class="card-icon" style="background:linear-gradient(135deg,#ffd700,#ffffff33);">{icon_svg("#ffd700", "sum")}</div>
      </div>
      <div class="sum-rows">{rows_html}</div>
      <div class="tone" style="color:{tone_color}; border-color:{tone_color}66;">{tone}</div>
    </div>"""
    cards.append(summary_card)

    cards_html = "\n".join(cards)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    width:1600px; height:1000px;
    background:{bg_css};
    font-family:-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color:#f4f6ff; padding:40px 44px 36px;
    display:flex; flex-direction:column;
  }}
  .header {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:26px;
  }}
  .title {{
    font-size:44px; font-weight:900; letter-spacing:1px;
    background:linear-gradient(90deg,#ffffff 0%,#9fd0ff 40%,#c9a7ff 100%);
    -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
    filter:drop-shadow(0 0 18px rgba(120,160,255,0.45));
  }}
  .subtitle {{ font-size:20px; color:#b9c8e8; margin-top:6px; letter-spacing:0.3px; }}
  .badge {{
    background:linear-gradient(135deg,rgba(255,255,255,0.16),rgba(255,255,255,0.05));
    border:1px solid rgba(255,255,255,0.28);
    border-radius:14px; padding:10px 18px; font-size:17px; font-weight:700;
    color:#eaf2ff; backdrop-filter:blur(10px);
    box-shadow:0 0 24px rgba(120,160,255,0.25), inset 0 1px 0 rgba(255,255,255,0.25);
  }}
  .grid {{
    display:grid; grid-template-columns:repeat(4,1fr); grid-template-rows:repeat(2,1fr);
    gap:20px; flex:1;
  }}
  .card {{
    position:relative;
    background:linear-gradient(160deg, rgba(255,255,255,0.14), rgba(255,255,255,0.04));
    border:1px solid rgba(255,255,255,0.22);
    border-radius:22px; padding:20px 20px 16px;
    backdrop-filter:blur(16px);
    box-shadow:
      0 10px 40px rgba(0,0,0,0.45),
      0 0 0 1px rgba(255,255,255,0.06) inset,
      0 0 34px var(--glow);
    display:flex; flex-direction:column; justify-content:space-between;
    overflow:hidden;
  }}
  .card::before {{
    content:""; position:absolute; top:-40%; left:-20%; width:140%; height:80%;
    background:linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.10) 50%, transparent 70%);
    transform:rotate(8deg); pointer-events:none;
  }}
  .card::after {{
    content:""; position:absolute; inset:0; border-radius:22px;
    background:radial-gradient(120px 80px at 20% 0%, var(--glow), transparent 70%);
    opacity:0.35; pointer-events:none;
  }}
  .card-top {{ display:flex; align-items:flex-start; justify-content:space-between; }}
  .card-title {{ font-size:16px; color:#dbe7ff; font-weight:700; line-height:1.25; }}
  .card-icon {{
    width:36px; height:36px; border-radius:10px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 16px var(--glow), inset 0 1px 0 rgba(255,255,255,0.4);
  }}
  .card-value {{ font-size:38px; font-weight:900; margin-top:12px; letter-spacing:0.5px;
    text-shadow:0 0 22px var(--glow); }}
  .card-sub {{ font-size:15px; font-weight:700; margin-top:10px; }}
  .sum-rows {{ display:flex; flex-direction:column; gap:7px; margin-top:12px; }}
  .sum-row {{ display:flex; justify-content:space-between; align-items:center; font-size:14px; }}
  .sum-label {{ color:#cfe0ff; font-weight:600; }}
  .sum-val {{ font-weight:800; }}
  .tone {{
    margin-top:12px; text-align:center; font-size:16px; font-weight:900;
    border:1px solid; border-radius:10px; padding:6px 0;
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


def render(html, out_path, width=1600, height=1000):
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
