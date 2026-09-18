#!/usr/bin/env python3
"""Kripto nedēļas infografika — kie.ai fons + HTML→PNG (glassmorphism, neon).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs, jo AI modeļi slikti
renderē ciparus. kie.ai ģenerē TIKAI fonu (bez teksta/cipariem).

Dizains: ļoti krāsaina tumša tēma, spilgti gradienti, mirdzoši stikla
logrīki (glassmorphism), 3D dziļums, neonas notis. 7 rādītāji simetriskā
režģī (4 augšā + 3 apakšā) — bez tukšiem laukumiem. NAV avotu rindiņas.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 krypto_dashboard_html.py <out.png> '<json_data>'
    # json_data: {"total_cap":..., "btc_price":..., "btc_7d":...,
    #             "eth_price":..., "eth_7d":..., "btc_dom":...,
    #             "fng":..., "fng_class":..., "etf": {...}}
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


def generate_background(out_path, api_key):
    """Ģenerē košu neonu fonu (bez teksta) caur kie.ai Seedream 5.0 Lite."""
    prompt = (
        "Vibrant premium crypto market dashboard background, rich deep dark "
        "gradient with vivid neon color washes (electric purple, magenta, "
        "cyan, teal and gold glowing aurora blending across a near-black "
        "base), luminous glowing candlestick charts in bright green and red, "
        "holographic rising line chart with a glowing arrow, floating neon "
        "glass orbs and bokeh light particles, dramatic volumetric glow, "
        "high-end fintech aesthetic, colorful and energetic, "
        "no text, no numbers, no letters, no words, no labels, "
        "empty background for data overlay"
    )
    payload = {
        "model": "seedream/5-lite-text-to-image",
        "input": {
            "prompt": prompt,
            "aspect_ratio": "4:3",
            "quality": "basic",
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

    deadline = time.time() + 180
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


def arrow(v):
    return "🟢" if v >= 0 else "🔴"


def build_html(d, bg_data_uri=None):
    if bg_data_uri:
        bg_css = (
            "linear-gradient(rgba(10,8,30,0.55), rgba(10,8,30,0.55)), "
            f"url('data:image/png;base64,{bg_data_uri}') center/cover no-repeat, "
            "radial-gradient(1400px 600px at 50% -10%, #2a1a5e, #120b33 55%, #07041a)"
        )
    else:
        bg_css = (
            "radial-gradient(1400px 600px at 50% -10%, #2a1a5e, #120b33 55%, #07041a), "
            "radial-gradient(900px 500px at 85% 90%, #0a3a4a, transparent 60%), "
            "radial-gradient(900px 500px at 10% 80%, #3a0a4a, transparent 60%)"
        )

    btc_7d = d.get("btc_7d", 0)
    eth_7d = d.get("eth_7d", 0)
    btc_dom = d.get("btc_dom", 0)
    fng = d.get("fng", 0)
    fng_class = d.get("fng_class", "")

    etf = d.get("etf") or {}
    btc_etf = etf.get("BTC") or {}
    eth_etf = etf.get("ETH") or {}
    btc_etf_this = btc_etf.get("this_week")
    eth_etf_this = eth_etf.get("this_week")
    btc_etf_chg = (btc_etf.get("this_week", 0) - btc_etf.get("prev_week", 0)) if btc_etf_this is not None else None
    eth_etf_chg = (eth_etf.get("this_week", 0) - eth_etf.get("prev_week", 0)) if eth_etf_this is not None else None

    # Katram logrīkam sava neonas akcenta krāsa (gradients + mirdzums)
    def card(title, value, sub, up, accent, glow):
        color = "#00ff9d" if up else "#ff3b5c"
        arrowc = "▲" if up else "▼"
        return f"""
        <div class="card" style="--accent:{accent}; --glow:{glow};">
          <div class="card-top">
            <div class="card-title">{title}</div>
            <div class="card-icon" style="background:linear-gradient(135deg,{accent},#ffffff22);"></div>
          </div>
          <div class="card-value">{value}</div>
          <div class="card-sub" style="color:{color}; text-shadow:0 0 12px {color}88;">
            <span class="arr">{arrowc}</span> {sub}
          </div>
        </div>"""

    cards_top = []
    cards_top.append(card("Market Capitalization", fmt_usd(d.get("total_cap", 0)),
                          f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0,
                          "#00d4ff", "rgba(0,212,255,0.55)"))
    cards_top.append(card("Bitcoin (BTC) Price", f"${d.get('btc_price', 0):,.0f}",
                          f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0,
                          "#ffb300", "rgba(255,179,0,0.55)"))
    cards_top.append(card("Ethereum (ETH) Price", f"${d.get('eth_price', 0):,.0f}",
                          f"vs previous week {fmt_pct(eth_7d)}", eth_7d >= 0,
                          "#b44dff", "rgba(180,77,255,0.55)"))
    cards_top.append(card("Bitcoin Dominance", f"{btc_dom:.1f}%",
                          "share of total market", btc_dom >= 50,
                          "#00e5a0", "rgba(0,229,160,0.55)"))

    cards_bot = []
    cards_bot.append(card("Fear & Greed Index", f"{fng}",
                          f"{fng_class}", fng >= 50,
                          "#ff5ce1", "rgba(255,92,225,0.55)"))
    if btc_etf_this is not None:
        cards_bot.append(card("Bitcoin ETF Weekly Inflow", fmt_usd(btc_etf_this),
                              f"vs previous week {fmt_usd(btc_etf_chg)}", (btc_etf_chg or 0) >= 0,
                              "#ff8a3d", "rgba(255,138,61,0.55)"))
    if eth_etf_this is not None:
        cards_bot.append(card("Ethereum ETF Weekly Inflow", fmt_usd(eth_etf_this),
                              f"vs previous week {fmt_usd(eth_etf_chg)}", (eth_etf_chg or 0) >= 0,
                              "#7a5cff", "rgba(122,92,255,0.55)"))

    top_html = "\n".join(cards_top)
    bot_html = "\n".join(cards_bot)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    width:1180px; height:1180px;
    background:{bg_css};
    font-family:-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color:#f4f6ff; padding:46px 44px 40px;
    display:flex; flex-direction:column;
  }}
  .header {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:30px;
  }}
  .title {{
    font-size:46px; font-weight:900; letter-spacing:1px;
    background:linear-gradient(90deg,#ffffff 0%,#9fd0ff 40%,#c9a7ff 100%);
    -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
    filter:drop-shadow(0 0 18px rgba(120,160,255,0.45));
  }}
  .subtitle {{ font-size:21px; color:#b9c8e8; margin-top:8px; letter-spacing:0.3px; }}
  .badge {{
    background:linear-gradient(135deg,rgba(255,255,255,0.16),rgba(255,255,255,0.05));
    border:1px solid rgba(255,255,255,0.28);
    border-radius:16px; padding:12px 20px; font-size:18px; font-weight:700;
    color:#eaf2ff; backdrop-filter:blur(10px);
    box-shadow:0 0 24px rgba(120,160,255,0.25), inset 0 1px 0 rgba(255,255,255,0.25);
  }}
  .row-top {{ display:grid; grid-template-columns:repeat(4,1fr); gap:20px; }}
    .row-bot {{ display:flex; gap:20px; margin-top:20px; }}
    .row-bot .card {{ flex:1; }}
  .card {{
    position:relative;
    background:linear-gradient(160deg, rgba(255,255,255,0.14), rgba(255,255,255,0.04));
    border:1px solid rgba(255,255,255,0.22);
    border-radius:24px; padding:24px 22px;
    backdrop-filter:blur(16px);
    box-shadow:
      0 10px 40px rgba(0,0,0,0.45),
      0 0 0 1px rgba(255,255,255,0.06) inset,
      0 0 34px var(--glow);
    display:flex; flex-direction:column; justify-content:space-between;
    min-height:250px;
    overflow:hidden;
  }}
  .card::before {{
    content:""; position:absolute; top:-40%; left:-20%; width:140%; height:80%;
    background:linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.10) 50%, transparent 70%);
    transform:rotate(8deg); pointer-events:none;
  }}
  .card::after {{
    content:""; position:absolute; inset:0; border-radius:24px;
    background:radial-gradient(120px 80px at 20% 0%, var(--glow), transparent 70%);
    opacity:0.35; pointer-events:none;
  }}
  .card-top {{ display:flex; align-items:flex-start; justify-content:space-between; }}
  .card-title {{ font-size:18px; color:#dbe7ff; font-weight:700; line-height:1.25; }}
  .card-icon {{
    width:34px; height:34px; border-radius:10px; flex-shrink:0;
    box-shadow:0 0 16px var(--glow), inset 0 1px 0 rgba(255,255,255,0.4);
  }}
  .card-value {{ font-size:42px; font-weight:900; margin-top:14px; letter-spacing:0.5px;
    text-shadow:0 0 22px var(--glow); }}
  .card-sub {{ font-size:17px; font-weight:700; margin-top:12px; }}
  .arr {{ font-size:15px; }}
</style></head>
<body>
  <div class="header">
    <div>
      <div class="title">CRYPTO MARKET WEEKLY SUMMARY</div>
      <div class="subtitle">Comparison vs. previous week</div>
    </div>
    <div class="badge">Weekly Report</div>
  </div>
  <div class="row-top">
    {top_html}
  </div>
  <div class="row-bot">
    {bot_html}
  </div>
</body></html>"""
    return html


def render(html, out_path, width=1180, height=1180):
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
