#!/usr/bin/env python3
"""Kripto nedēļas infografika — kie.ai fons + HTML→PNG (glassmorphism).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs, jo AI modeļi slikti
renderē ciparus. kie.ai ģenerē TIKAI fonu (bez teksta/cipariem).

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
    """Ģenerē premium tumšu fonu (bez teksta) caur kie.ai Seedream 5.0 Lite."""
    prompt = (
        "Premium crypto market dashboard background, deep near-black premium "
        "gradient (dark charcoal center fading to deep indigo edges), "
        "subtle glowing neon candlestick charts in red and green scattered in "
        "the background depth, faint holographic rising line chart with a "
        "bullish arrow, soft ambient glow, premium fintech aesthetic, "
        "glassmorphism friendly, "
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
            "linear-gradient(rgba(7,19,35,0.60), rgba(7,19,35,0.60)), "
            f"url('data:image/png;base64,{bg_data_uri}') center/cover no-repeat, "
            "radial-gradient(1200px 520px at 50% -10%, #12314f, #091a2e 60%, #06111f)"
        )
    else:
        bg_css = "radial-gradient(1200px 520px at 50% -10%, #12314f, #091a2e 60%, #06111f)"

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

    def card(title, value, sub, up):
        color = "#2fbf71" if up else "#ef6c6c"
        emoji = "🟢" if up else "🔴"
        return f"""
        <div class="card">
          <div class="card-title">{title}</div>
          <div class="card-value">{value}</div>
          <div class="card-sub" style="color:{color}">{emoji} {sub}</div>
        </div>"""

    cards = []
    cards.append(card("Market Capitalization", fmt_usd(d.get("total_cap", 0)),
                      f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0))
    cards.append(card("Bitcoin (BTC) Price", f"${d.get('btc_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(btc_7d)}", btc_7d >= 0))
    cards.append(card("Ethereum (ETH) Price", f"${d.get('eth_price', 0):,.0f}",
                      f"vs previous week {fmt_pct(eth_7d)}", eth_7d >= 0))
    cards.append(card("Bitcoin Dominance", f"{btc_dom:.1f}%",
                      "share of total market", btc_dom >= 50))
    cards.append(card("Fear & Greed Index", f"{fng}",
                      f"{fng_class}", fng >= 50))
    if btc_etf_this is not None:
        cards.append(card("Bitcoin ETF Weekly Inflow", fmt_usd(btc_etf_this),
                          f"vs previous week {fmt_usd(btc_etf_chg)}", (btc_etf_chg or 0) >= 0))
    if eth_etf_this is not None:
        cards.append(card("Ethereum ETF Weekly Inflow", fmt_usd(eth_etf_this),
                          f"vs previous week {fmt_usd(eth_etf_chg)}", (eth_etf_chg or 0) >= 0))

    cards_html = "\n".join(cards)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    width:1180px; height:1180px;
    background:{bg_css};
    font-family:-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color:#eef4ff; padding:48px 44px;
    display:flex; flex-direction:column;
  }}
  .header {{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:34px;
  }}
  .title {{
    font-size:44px; font-weight:800; letter-spacing:0.5px;
    background:linear-gradient(90deg,#ffffff,#9fd0ff);
    -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
  }}
  .subtitle {{ font-size:20px; color:#9fb6d4; margin-top:6px; }}
  .badge {{
    background:rgba(255,255,255,0.10); border:1px solid rgba(255,255,255,0.18);
    border-radius:14px; padding:10px 18px; font-size:18px; color:#cfe3ff;
    backdrop-filter:blur(8px);
  }}
  .grid {{
    display:grid; grid-template-columns:repeat(3,1fr); gap:22px; flex:1;
  }}
  .card {{
    background:rgba(255,255,255,0.07);
    border:1px solid rgba(255,255,255,0.16);
    border-radius:22px; padding:26px 24px;
    backdrop-filter:blur(14px);
    box-shadow:0 8px 32px rgba(0,0,0,0.35);
    display:flex; flex-direction:column; justify-content:space-between;
  }}
  .card-title {{ font-size:19px; color:#a9c2e4; font-weight:600; }}
  .card-value {{ font-size:40px; font-weight:800; margin-top:10px; }}
  .card-sub {{ font-size:18px; font-weight:600; margin-top:8px; }}
  .footer {{
    margin-top:26px; text-align:center; font-size:17px; color:#8fa8c8;
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
  <div class="footer">Data: CoinGecko · SoSoValue · alternative.me</div>
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
