#!/usr/bin/env python3
"""ASV ekonomikas dati — plakans tumšs stils (1080x1080), tāds pats kā kripto nedēļas bilde.

Dati no FRED (tā pati loģika kā ASV kalendāram). Izkārtojums: 3 kartītes
(Unemployment | Inflation CPI | GDP), plats CPI 16 mēnešu grafiks, apakšā
Fed Funds Rate + tabula (Retail Sales, Industrial Production, Consumer Sentiment).
Bez neona, bez AI fona (KIE kredīti netiek tērēti), bez footera un zīmola.

Lietošana (jāiet ar /usr/bin/python3 — ir playwright):
    python3 asv_dashboard_html.py <out.png> [key1 key2 ...]   # keys tiek ignorēti
"""
import os
import sys
import csv
import io
import time
import datetime as dt

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_ui as ui  # noqa: E402

# ---------------- FRED dati ----------------

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2022-01-01"

REGISTRY = {
    "gdp":      dict(id="GDPC1",    calc="yoy_q"),
    "bezdarbs": dict(id="UNRATE",   calc="value"),
    "cpi":      dict(id="CPIAUCSL", calc="yoy"),
    "gauge":    dict(id="DFEDTARU", calc="value"),
    "retail":   dict(id="RSAFS",    calc="mom"),
    "ind":      dict(id="INDPRO",   calc="mom"),
    "sent":     dict(id="UMCSENT",  calc="value"),
}


def _fetch(sid):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(FRED_BASE.format(sid=sid), headers={"User-Agent": "curl/8.0"}, timeout=20)
            r.raise_for_status()
            rows = list(csv.reader(io.StringIO(r.text)))[1:]
            return [(row[0], row[1]) for row in rows if len(row) >= 2 and row[1] not in ("", ".")]
        except Exception as e:  # FRED mēdz ierobežot ātrumu
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def _d(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return float("nan")


def _series(sid, calc):
    raw = _fetch(sid)
    dates = [x[0] for x in raw]
    nums = [_d(x[1]) for x in raw]
    if calc == "yoy":
        vals = [(nums[i] / nums[i - 12] - 1) * 100 if i >= 12 and nums[i - 12] else float("nan") for i in range(len(nums))]
    elif calc == "yoy_q":
        vals = [(nums[i] / nums[i - 4] - 1) * 100 if i >= 4 and nums[i - 4] else float("nan") for i in range(len(nums))]
    elif calc == "mom":
        vals = [(nums[i] / nums[i - 1] - 1) * 100 if i >= 1 and nums[i - 1] else float("nan") for i in range(len(nums))]
    else:
        vals = nums
    return [(a, b) for a, b in zip(dates, vals) if b == b]


def load_all():
    out = {}
    for key, card in REGISTRY.items():
        try:
            out[key] = _series(card["id"], card["calc"])
        except Exception as e:
            print(f"  ⚠️ FRED {card['id']} neizdevās: {e}")
            out[key] = []
        time.sleep(1.5)
    return out


def _last_prev(pairs):
    """(pēdējā, iepriekšējā) vērtība; DFEDTARU dienas sērijai iepriekšējā = pēdējā atšķirīgā."""
    if not pairs:
        return None, None
    last = pairs[-1][1]
    prev = pairs[-2][1] if len(pairs) >= 2 else None
    return last, prev


# ---------------- HTML ----------------

def build_html(data):
    today = dt.date.today()
    monday = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
    friday = monday + dt.timedelta(days=4)

    def stat_card(title, key, sub, signed=True, nd=1, unit="%"):
        last, prev = _last_prev(data.get(key, []))
        if last is None:
            val, delta = "—", ""
        else:
            val = f"{last:+.{nd}f}{unit}" if signed else f"{last:.{nd}f}{unit}"
            if prev is not None:
                ch = last - prev
                delta = (f'<div class="delta" style="color:{ui.col(ch >= 0)};">{ui.tri(ch >= 0, 20)}'
                         f'{ch:+.{nd}f} pp</div>')
            else:
                delta = ""
        return f"""
    <div class="card" style="width:320px;height:230px;">
      <div class="ctitle">{title}</div>
      <div class="grow">
        <div class="big">{val}</div>
        {delta}
        <div class="muted">{sub}</div>
      </div>
    </div>"""

    c1 = stat_card("Unemployment Rate", "bezdarbs", "vs previous month", signed=False)
    c2 = stat_card("Inflation (CPI)", "cpi", "year over year · vs prev. month")
    c3 = stat_card("GDP Growth", "gdp", "year over year · vs prev. quarter")

    # plats CPI grafiks
    cpi = data.get("cpi", [])[-16:]
    if len(cpi) >= 2:
        vals = [v for _, v in cpi]
        labels = []
        for i, (ds, _) in enumerate(cpi):
            if (len(cpi) - 1 - i) % 3 == 0:
                labels.append((i, dt.date.fromisoformat(ds).strftime("%b '%y")))
        chart = ui.line_chart(vals, 956, 262, lambda v: f"{v:.1f}%", labels, f"{vals[-1]:+.1f}%")
    else:
        chart = ""
    c_chart = f"""
    <div class="card" style="width:1000px;height:330px;">
      <div class="ctitle">Inflation CPI (Year over Year)</div>
      <div style="margin-top:6px;">{chart}</div>
    </div>"""

    # Fed funds
    fed, _ = _last_prev(data.get("gauge", []))
    if fed is None:
        fed_html = '<div class="big">—</div>'
    else:
        fed_html = f"""
        <div class="big">{fed:.2f}%</div>
        <div class="muted">Target rate (upper bound)</div>
        <div style="margin-top:8px;">{ui.scale_bar(fed, 0, 6, ["0%", "2%", "4%", "6%"], left_color="#4aa880", mid_color="#c9a24a", right_color="#b8545c")}</div>"""
    c_fed = f"""
    <div class="card" style="width:470px;height:310px;">
      <div class="ctitle">Fed Funds Rate</div>
      <div class="grow" style="gap:6px;">{fed_html}</div>
    </div>"""

    def trow(name, sub, key, nd, unit, signed):
        last, prev = _last_prev(data.get(key, []))
        if last is None:
            latest, chg_html = "—", '<span class="num" style="color:#8a94a6;">—</span>'
        else:
            latest = f"{last:+.{nd}f}{unit}" if signed else f"{last:.{nd}f}{unit}"
            if prev is None:
                chg_html = '<span class="num" style="color:#8a94a6;">—</span>'
            else:
                ch = last - prev
                cu = "pp" if unit == "%" else "pts"
                chg_html = (f'<span class="num" style="color:{ui.col(ch >= 0)}; display:inline-flex; align-items:center; gap:8px;">'
                            f'{ui.tri(ch >= 0, 15)}{ch:+.{nd}f} {cu}</span>')
        return f"""
        <tr style="height:66px;">
          <td><div class="tk" style="font-size:21px;">{name}</div><div class="nm">{sub}</div></td>
          <td class="r"><span class="num">{latest}</span></td>
          <td class="r">{chg_html}</td>
        </tr>"""

    c_tab = f"""
    <div class="card" style="width:510px;height:310px;">
      <div class="ctitle" style="margin-bottom:12px;">Key Indicators</div>
      <table>
        <tr><th>Indicator</th><th class="r">Latest</th><th class="r">vs Previous</th></tr>
        {trow("Retail Sales", "month over month", "retail", 1, "%", True)}
        {trow("Industrial Production", "month over month", "ind", 1, "%", True)}
        {trow("Consumer Sentiment", "index", "sent", 1, "", False)}
      </table>
    </div>"""

    sub = f"Week of {monday:%-d %b} – {friday:%-d %b %Y}"
    body = (ui.header("US Economic Data", sub)
            + f'<div class="row">{c1}{c2}{c3}</div>'
            + c_chart
            + f'<div class="row">{c_fed}{c_tab}</div>')
    return ui.page(body)


def generate_dashboard(d_keys, out_path):
    data = load_all()
    html = build_html(data)
    ui.render(html, out_path)
    print("saved", out_path, os.path.getsize(out_path))
    return out_path


def main():
    out = sys.argv[1]
    # keys ignorējam — vienmēr pilns fiksēts komplekts (bilde nekad nav tukša)
    generate_dashboard(sys.argv[2:], out)


if __name__ == "__main__":
    main()
