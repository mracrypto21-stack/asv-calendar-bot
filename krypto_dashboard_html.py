#!/usr/bin/env python3
"""Kripto nedēļas infografika — plakans tumšs stils (1080x1080), bez neona un bez AI fona.

Izkārtojums: 3 kartītes (BTC cena | Fear & Greed | BTC dominance), plats BTC 7d
grafiks, apakšā ETF plūsmas + 7d tabula. Viss ir HTML/SVG → PNG (Playwright),
tāpēc skaitļi vienmēr pikseļprecīzi. KIE kredīti netiek tērēti.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 krypto_dashboard_html.py <out.png> '<json_data>'
"""
import os
import sys
import json
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_ui as ui  # noqa: E402


def _fng_color(v):
    if v < 25:
        return ui.RED
    if v < 45:
        return "#e08a4a"
    if v < 55:
        return ui.GOLD
    return ui.GREEN


def build_html(d):
    now = dt.datetime.now()
    btc_price = d.get("btc_price", 0)
    btc_7d = d.get("btc_7d", 0)
    eth_price = d.get("eth_price", 0)
    eth_7d = d.get("eth_7d", 0)
    total = d.get("total_cap", 0)
    total_7d = d.get("total_cap_7d", 0)
    btc_dom = d.get("btc_dom", 0)
    eth_dom = d.get("eth_dom", 0)
    dom_prev = d.get("btc_dom_prev")
    fng = int(d.get("fng", 0))
    fng_prev = int(d.get("fng_prev", fng))
    fng_class = d.get("fng_class", "")
    others = max(0.0, 100.0 - btc_dom - eth_dom)

    # ---- 1. rinda: 3 kartītes ----
    c_btc = f"""
    <div class="card" style="width:320px;height:230px;">
      <div class="ctitle">BTC Price</div>
      <div class="grow">
        <div class="big">${btc_price:,.0f}</div>
        <div class="delta" style="color:{ui.col(btc_7d >= 0)};">{ui.tri(btc_7d >= 0, 20)}{ui.pct(btc_7d)}</div>
        <div class="muted">7-day change</div>
      </div>
    </div>"""

    fc = _fng_color(fng)
    c_fng = f"""
    <div class="card" style="width:320px;height:230px;">
      <div class="ctitle">Fear &amp; Greed Index</div>
      <div class="grow" style="gap:6px;">
        <div style="display:flex; align-items:baseline; gap:12px;">
          <div class="big" style="color:{fc};">{fng}</div>
          <div style="font-size:26px; font-weight:800;">{fng_class}</div>
        </div>
        {ui.scale_bar(fng, 0, 100, [0, 25, 50, 75, 100])}
        <div class="muted">Prev week: {fng_prev}</div>
      </div>
    </div>"""

    if dom_prev is not None:
        dchg = btc_dom - dom_prev
        dom_delta = (f'<div class="delta" style="color:{ui.col(dchg >= 0)};">{ui.tri(dchg >= 0, 20)}'
                     f'{dchg:+.1f} pp</div>')
        dom_sub = "vs previous week"
    else:
        dom_delta, dom_sub = "", "share of total market"
    c_dom = f"""
    <div class="card" style="width:320px;height:230px;">
      <div class="ctitle">BTC Dominance</div>
      <div class="grow" style="gap:8px;">
        <div class="big">{btc_dom:.1f}%</div>
        {dom_delta}
        <div class="muted">{dom_sub}</div>
        <div style="display:flex; height:12px; border-radius:6px; overflow:hidden; gap:2px; margin-top:2px;">
          <div style="width:{btc_dom:.1f}%; background:{ui.GOLD};"></div>
          <div style="width:{eth_dom:.1f}%; background:#8fa3c4;"></div>
          <div style="width:{others:.1f}%; background:#3a4356;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:700; color:{ui.MUTED};">
          <span>BTC {btc_dom:.0f}%</span><span>ETH {eth_dom:.0f}%</span><span>Other {others:.0f}%</span>
        </div>
      </div>
    </div>"""

    # ---- 2. rinda: plats BTC 7d grafiks ----
    series = d.get("btc_series", [])
    n = len(series)
    per_h = (7 * 24) / max(n - 1, 1) if n > 1 else 1.0   # stundas uz vienu punktu
    step_samples = max(1, int(round(24 / per_h)))         # ~1 etiķete dienā
    ticks = ui.date_ticks(n, step_samples, now, count=7, per_sample_hours=per_h) if n else []
    chart = ui.line_chart(series, 956, 262, lambda v: f"${v:,.0f}", ticks, f"${btc_price:,.0f}") if n >= 2 else ""
    c_chart = f"""
    <div class="card" style="width:1000px;height:330px;">
      <div class="ctitle">BTC Price (7-Day)</div>
      <div style="margin-top:6px;">{chart}</div>
    </div>"""

    # ---- 3. rinda: ETF + tabula ----
    etf = d.get("etf") or {}

    def etf_block(sym):
        e = etf.get(sym) or {}
        this = e.get("this_week")
        if this is None:
            return ""
        prev = e.get("prev_week", 0)
        daily = e.get("daily") or []
        bars = ui.mini_bars(daily, 150, 70, ["M", "T", "W", "T", "F"][:len(daily)]) if len(daily) >= 2 else ""
        up = this >= 0
        return f"""
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <div>
            <div style="font-size:18px; font-weight:800; color:{ui.GOLD}; letter-spacing:0.5px;">{sym} ETF</div>
            <div style="font-size:40px; font-weight:800; line-height:1.15; color:{ui.col(up)};">{ui.smoney(this)}</div>
            <div class="muted">Prev week {ui.smoney(prev)}</div>
          </div>
          {bars}
        </div>"""

    c_etf = f"""
    <div class="card" style="width:470px;height:310px;">
      <div class="ctitle">ETF Weekly Flows</div>
      <div style="flex:1; display:flex; flex-direction:column; justify-content:space-around; margin-top:6px;">
        {etf_block("BTC")}
        <div style="height:1px; background:#222a39;"></div>
        {etf_block("ETH")}
      </div>
    </div>"""

    def trow(tk, name, price, chg):
        up = chg >= 0
        return f"""
        <tr style="height:66px;">
          <td><div class="tk">{tk}</div><div class="nm">{name}</div></td>
          <td class="r"><span class="num">{price}</span></td>
          <td class="r"><span class="num" style="color:{ui.col(up)}; display:inline-flex; align-items:center; gap:8px;">{ui.tri(up, 15)}{ui.pct(chg, 2)}</span></td>
        </tr>"""

    c_tab = f"""
    <div class="card" style="width:510px;height:310px;">
      <div class="ctitle" style="margin-bottom:12px;">7D Performance</div>
      <table>
        <tr><th>Asset</th><th class="r">Price</th><th class="r">7D Change</th></tr>
        {trow("TOTAL", "Market cap", ui.money(total), total_7d)}
        {trow("BTC", "Bitcoin", f"${btc_price:,.0f}", btc_7d)}
        {trow("ETH", "Ethereum", f"${eth_price:,.0f}", eth_7d)}
      </table>
    </div>"""

    start = now - dt.timedelta(days=7)
    sub = f"{start:%-d %b} – {now:%-d %b %Y}"
    body = (ui.header("Crypto Weekly Market Update", sub)
            + f'<div class="row">{c_btc}{c_fng}{c_dom}</div>'
            + c_chart
            + f'<div class="row">{c_etf}{c_tab}</div>')
    return ui.page(body)


def generate_dashboard(d, out_path):
    html = build_html(d)
    ui.render(html, out_path)
    print("saved", out_path, os.path.getsize(out_path))
    return out_path


def main():
    out = sys.argv[1]
    data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    generate_dashboard(data, out)


if __name__ == "__main__":
    main()
