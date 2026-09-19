#!/usr/bin/env python3
"""ASV ekonomikas dati — bagāts finanšu dashboard.
Rāda reālus makro rādītājus (FRED) ar LIELIEM izceltiem skaitļiem, vektoru
ikonām un mini-diagrammām katrā kartītē. Zīmola (tumšs/zelta) stilā.
Paredzēts importam no asv_calendar.py: generate_dashboard(keys, out_path).
"""
import os
import io
import csv
import time
import math
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Wedge, Circle, Polygon
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# Dizains
# ---------------------------------------------------------------------------
BG_TOP = "#0a1e35"
BG_BOT = "#071323"
CARD = "#12283f"
CARD_TOP = "#1b3f63"
CARD_EDGE = "#2b4c6e"
GOLD = "#f0c860"
WHITE = "#f5f1e6"
MUTED = "#8fa8bf"
GREEN = "#2fbf71"
RED = "#ef6c6c"
AMBER = "#f0b34a"
BLUE = "#5aa9e6"

# ---------------------------------------------------------------------------
# FRED rādītāju reģistrs
# ---------------------------------------------------------------------------
REGISTRY = {
    # calc: 'gauge' -> pusloka mērītājs; 'yoy'/'mom'/'yoy_q' -> stabiņi; 'value' -> līnija
    "gdp":      dict(id="GDPC1",    title="IKP izaugsme",     unit="g/g %", calc="yoy_q",  icon="gdp",   accent=GREEN),
    "bezdarbs": dict(id="UNRATE",   title="Bezdarba līmenis", unit="%",      calc="value", icon="people",accent=BLUE),
    "cpi":      dict(id="CPIAUCSL", title="Inflācija (CPI)",   unit="g/g %",  calc="yoy",   icon="pct",   accent=RED),
    "corecpi":  dict(id="CPILFESL", title="Pamata inflācija",  unit="g/g %",  calc="yoy",   icon="pct",   accent=RED),
    "ppi":      dict(id="PPIFIS",   title="Ražotāju cenas",    unit="g/g %",  calc="yoy",   icon="factory",accent=AMBER),
    "coreppi":  dict(id="PPIFES",   title="Pamata PPI",        unit="g/g %",  calc="yoy",   icon="factory",accent=AMBER),
    "retail":   dict(id="RSAFS",    title="Mazumtirdzniecība", unit="m/m %",  calc="mom",   icon="bag",   accent=GREEN),
    "ind":      dict(id="INDPRO",   title="Rūpniecība",        unit="m/m %",  calc="mom",   icon="factory",accent=GREEN),
    "sent":     dict(id="UMCSENT",  title="Noskaņojums",       unit="ind.",   calc="value", icon="face",  accent=AMBER),
    "housing":  dict(id="HOUST",    title="Jaunbūves",         unit="tūkst.", calc="value_th", icon="house",accent=BLUE),
    "gauge":    dict(id="DFEDTARU", title="Fed bāzes likme",   unit="%",      calc="gauge", icon="gauge",  accent=GOLD),
}

import requests


def _fetch_fred(fred_id, start="2022-01-01", retries=3):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}&cosd={start}"
    last = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"User-Agent": "curl/8.0"}, timeout=20)
            resp.raise_for_status()
            rows = list(csv.reader(io.StringIO(resp.text)))[1:]
            rows = [r for r in rows if len(r) >= 2 and r[1] not in ("", ".")]
            if rows:
                return rows
            last = RuntimeError(f"{fred_id}: tukši dati")
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last if last else RuntimeError(f"{fred_id}: neizdevās iegūt datus")


def _to_float(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _values(fred_id, calc, start="2022-01-01"):
    raw = _fetch_fred(fred_id, start)
    dates = [r[0] for r in raw]
    nums = [_to_float(r[1]) for r in raw]
    nums = [n if n is not None else float('nan') for n in nums]
    if calc == "value":
        vals = nums
    elif calc == "value_th":
        vals = [n / 1000.0 for n in nums]
    elif calc == "yoy":
        vals = [(nums[i] / nums[i - 12] - 1) * 100 if i >= 12 and nums[i - 12] else float('nan') for i in range(len(nums))]
    elif calc == "yoy_q":
        vals = [(nums[i] / nums[i - 4] - 1) * 100 if i >= 4 and nums[i - 4] else float('nan') for i in range(len(nums))]
    elif calc == "mom":
        vals = [(nums[i] / nums[i - 1] - 1) * 100 if i >= 1 and nums[i - 1] else float('nan') for i in range(len(nums))]
    else:
        vals = nums
    return dates, vals


def _clean_tail(dates, vals, n=20):
    pairs = [(d, v) for d, v in zip(dates, vals) if v == v]
    return pairs[-n:]


# ---------------------------------------------------------------------------
# Indikatoru atlase pēc nedēļas notikumiem
# ---------------------------------------------------------------------------
NOTICE_MAP = [
    ("core cpi", "corecpi"), ("cpi", "cpi"),
    ("core ppi", "coreppi"), ("ppi", "ppi"),
    ("fomc", "gauge"), ("fed", "gauge"), ("powell", "gauge"), ("speaks", "gauge"), ("rate", "gauge"),
    ("gdp", "gdp"),
    ("retail", "retail"),
    ("industrial production", "ind"), ("capacity", "ind"),
    ("consumer confidence", "sent"), ("consumer sentiment", "sent"), ("michigan", "sent"),
    ("housing starts", "housing"), ("building permits", "housing"),
    ("unemployment rate", "bezdarbs"), ("jobless", "bezdarbs"), ("claims", "bezdarbs"),
    ("payrolls", "bezdarbs"), ("nonfarm", "bezdarbs"), ("non-farm", "bezdarbs"),
    ("nfp", "bezdarbs"),
]


def _map_event_to_indicator(event_name):
    low = " " + event_name.lower() + " "
    for pat, key in NOTICE_MAP:
        if pat in low:
            return key
    return None


def select_indicators(events_by_day):
    keys = []
    for day_events in events_by_day.values():
        for ev in day_events:
            if ev == "Nav svarīgu ekonomisko datu" or ev.startswith("🏖️") or ev.startswith("Bank"):
                continue
            k = _map_event_to_indicator(ev)
            if k and k not in keys:
                keys.append(k)
    return keys


# ---------------------------------------------------------------------------
# Ikonu zīmēšana — vienkārši vektoru ikonas, font-safe
# ---------------------------------------------------------------------------
def _draw_icon(ax, icon_id, color):
    """uzzīmē vektoru ikonu zem kartītes virsraksta / badge apgabalā."""
    # badge fons (apaļš)
    ax.add_patch(Circle((0.115, 0.86), 0.075, color=color, alpha=0.22,
                 transform=ax.transAxes, zorder=2))
    # ikonu zīmē lokālās koordinātēs (centrs badge)
    cx, cy, s = 0.115, 0.86, 0.038
    kw = dict(transform=ax.transAxes, zorder=3, color=color)
    if icon_id == "gdp":   # ▲ uz augšu
        ax.add_patch(Polygon([(cx, cy + s), (cx - s, cy - s * 0.7), (cx + s, cy - s * 0.7)], closed=True, **kw))
    elif icon_id == "people":  # divi apļi + ķermenis
        ax.add_patch(Circle((cx - s * 0.35, cy + s * 0.55), s * 0.28, **kw))
        ax.add_patch(Circle((cx + s * 0.4, cy + s * 0.55), s * 0.28, **kw))
        ax.plot([cx - s * 0.7, cx - s * 0.05], [cy - s * 0.25, cy - s * 0.25], color=color, lw=3, solid_capstyle="round", transform=ax.transAxes)
        ax.plot([cx + s * 0.05, cx + s * 0.7], [cy - s * 0.25, cy - s * 0.25], color=color, lw=3, solid_capstyle="round", transform=ax.transAxes)
    elif icon_id == "pct":   # procenta zīme (tikai '%' — gandrīz nav fonta panākumu)
        ax.text(cx, cy, "%", fontsize=15, fontweight="bold", ha="center", va="center", transform=ax.transAxes, color=color, zorder=4)
    elif icon_id == "bag":   # iepirkumu maza soma
        ax.add_patch(Polygon([(cx - s * 0.8, cy - s), (cx + s * 0.8, cy - s), (cx + s * 0.5, cy), (cx - s * 0.5, cy)], closed=True, **kw))
        ax.plot([cx - s * 0.35, cx - s * 0.35, cx + s * 0.35, cx + s * 0.35], [cy, cy - s * 0.15, cy - s * 0.15, cy], color=color, lw=2, transform=ax.transAxes)
    elif icon_id == "factory":  # kvadrāts ar skursteni
        ax.add_patch(Rectangle((cx - s, cy - s * 0.8), s * 2, s * 1.3, facecolor=color, edgecolor="none", transform=ax.transAxes))
        ax.plot([cx - s * 0.4, cx - s * 0.4], [cy + s * 0.5, cy + s * 0.9], color=color, lw=2.5, transform=ax.transAxes)
        ax.plot([cx, cx], [cy + s * 0.5, cy + s * 0.75], color=color, lw=2.5, transform=ax.transAxes)
    elif icon_id == "house":  # māja
        ax.add_patch(Polygon([(cx, cy + s), (cx - s, cy - s * 0.3), (cx + s, cy - s * 0.3)], closed=True, **kw))
        ax.add_patch(Rectangle((cx - s * 0.5, cy - s), s, s * 0.5, facecolor=color, edgecolor="none", transform=ax.transAxes))
    elif icon_id == "face":  # noskaņojuma seja (aplis + smaids)
        ax.add_patch(Circle((cx, cy), s, facecolor=color, edgecolor="none", transform=ax.transAxes))
        ax.plot([cx - s * 0.3, cx - s * 0.15], [cy + s * 0.15, cy + s * 0.15], color=BG_TOP, lw=1.5, transform=ax.transAxes)
        ax.plot([cx + s * 0.15, cx + s * 0.3], [cy + s * 0.15, cy + s * 0.15], color=BG_TOP, lw=1.5, transform=ax.transAxes)
        ax.plot([cx - s * 0.35, cx, cx + s * 0.35], [cy - s * 0.1, cy - s * 0.5, cy - s * 0.1], color=BG_TOP, lw=1.5, transform=ax.transAxes)
    elif icon_id == "gauge":  # mērītāja daļa (pusloks)
        ax.add_patch(Wedge((cx, cy), s, 0, 180, width=s * 0.5, facecolor=color, edgecolor="none", transform=ax.transAxes))
    else:
        ax.add_patch(Circle((cx, cy), s, **kw))


# ---------------------------------------------------------------------------
# Mini diagrammu zīmēšana
# ---------------------------------------------------------------------------
def _draw_sparkline(ax, pairs, color):
    ys = [p[1] for p in pairs]
    if not ys:
        return
    xs = list(range(len(pairs)))
    ax.plot(xs, ys, color=color, linewidth=2.2, solid_capstyle="round")
    lo, hi = min(ys), max(ys)
    ax.fill_between(xs, ys, lo - (hi - lo) * 0.3, color=color, alpha=0.12)
    ax.axis("off")
    span = (hi - lo) or 1.0
    ax.set_ylim(lo - span * 0.4, hi + span * 0.4)


def _draw_bars(ax, pairs, color):
    ys = [p[1] for p in pairs]
    if not ys:
        return
    xs = range(len(pairs))
    colors = [color if y >= 0 else RED for y in ys]
    ax.bar(xs, ys, color=colors, width=0.6)
    ax.axhline(0, color=MUTED, linewidth=0.6, alpha=0.5)
    # pēdējā stabiņa izcelšana
    ax.axvspan(len(pairs) - 1.3, len(pairs) - 0.7, color="#ffffff", alpha=0.08)
    ax.axis("off")


def _draw_gauge(ax, rate_pairs, low=1.5, high=5.5):
    last = rate_pairs[-1][1] if rate_pairs else 3.5
    frac = max(0.0, min(1.0, (last - low) / (high - low)))
    ax.set_xlim(-1.25, 1.25); ax.set_ylim(-0.25, 1.2); ax.axis("off")
    ax.add_patch(Wedge((0, 0), 1.0, 0, 180, width=0.20, facecolor="#27405a", edgecolor="none"))
    for a0, a1, col in [(20, 70, GREEN), (70, 110, AMBER), (110, 160, RED)]:
        ax.add_patch(Wedge((0, 0), 1.0, a0, a1, width=0.20, facecolor=col, edgecolor="none"))
    ang = 180 * frac
    rad = math.radians(ang)
    ax.plot([0, 0.75 * math.sin(rad)], [0, 0.75 * math.cos(rad)], color=WHITE, linewidth=3, solid_capstyle="round")
    ax.add_patch(Circle((0, 0), 0.07, color=GOLD))


# ---------------------------------------------------------------------------
# Galvenais ģenerators — bagāta finanšu dashboard
# ---------------------------------------------------------------------------
GAUGE_KEY = "gauge"


def generate_dashboard(indicator_keys, out_path):
    n = len(indicator_keys)
    if n == 0:
        return None
    gauges = [k for k in indicator_keys if k == GAUGE_KEY]
    regulars = [k for k in indicator_keys if k != GAUGE_KEY]

    rows_layout = []
    for i in range(0, len(regulars), 3):
        rows_layout.append(("regular", regulars[i:i+3]))
    for g in gauges:
        rows_layout.append(("full", [g]))

    card_3_w = 3.35
    card_full_w = card_3_w * 3 + 0.26 * 2
    card_h = 1.95
    header_h = 0.95
    footer_h = 0.40
    gap = 0.26

    fig_w = card_3_w * 3 + gap * 2
    fig_h = header_h + footer_h + sum((card_h + gap) for _ in rows_layout)
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=170)

    # fona gradients
    grad = LinearSegmentedColormap.from_list("bg", [BG_TOP, BG_BOT])
    bgax = fig.add_axes((0, 0, 1, 1)); bgax.set_xticks([]); bgax.set_yticks([])
    bgax.imshow([[0, 1]], aspect="auto", extent=(0, 1, 0, 1), cmap=grad, zorder=0)
    bgax.set_zorder(0)
    fig.add_artist(Rectangle((0, fig_h), fig_w, -1.1, color="#2b5eaa", alpha=0.08))

    W, H = fig_w, fig_h

    # Virsraksta josla
    fig.add_artist(Rectangle((0, H - 0.08), W, 0.08, color=GOLD))
    fig.text(0.03, H - 0.26, "ASV EKONOMISKIE DATI", fontsize=22, fontweight="bold",
             color=WHITE, ha="left", va="center")
    fig.text(0.03, H - 0.58, "Aktuālie rādītāji šai nedēļai", fontsize=9.5,
             color=MUTED, ha="left", va="top")
    _badge(fig, W - 0.75, H - 0.28, f"{n}", GOLD)
    fig.text(W - 0.5, H - 0.28, "rādītāji", fontsize=9, color=MUTED, ha="left", va="center")

    # Kartīšu rindas
    y_cursor = H - header_h
    for kind, keys in rows_layout:
        x_cursor = gap
        for key in keys:
            w = card_full_w if kind == "full" else card_3_w
            x = x_cursor
            y = y_cursor - card_h
            ax = fig.add_axes((x / W, y / H, w / W, card_h / H))
            _draw_card(ax, REGISTRY[key], key)
            x_cursor += w + gap
        y_cursor -= card_h + gap

    # Futers
    fig.text(0.03, footer_h * 0.30, "KRIPTO NR.1  •  kriptonr1.xyz", fontsize=9,
             fontweight="bold", color=GOLD, ha="left", va="center")

    plt.savefig(out_path, dpi=170, facecolor=BG_BOT)
    plt.close(fig)
    return out_path


def _badge(fig, x, y, text, color):
    fig.add_artist(Circle((x, y), 0.16, color=color, alpha=0.25))
    fig.text(x, y, text, fontsize=13, fontweight="bold", color=color, ha="center", va="center")


def _draw_card(ax, meta, key):
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor("none")

    accent = meta["accent"] or GOLD
    title = meta["title"]

    # kartītes fons (apaļi stūri, viegla gradienta sajūta + apmale)
    gcard = LinearSegmentedColormap.from_list("card", [CARD_TOP, CARD])
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.0,rounding_size=0.05",
                 facecolor=gcard(0.4), edgecolor="none", transform=ax.transAxes, zorder=0))
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.0,rounding_size=0.05",
                 facecolor="none", edgecolor=CARD_EDGE, linewidth=1.0, transform=ax.transAxes, zorder=1))

    # dati
    try:
        dates, vals = _values(meta["id"], meta["calc"])
        pairs = _clean_tail(dates, vals, 20)
        last = pairs[-1][1] if pairs else float('nan')
    except Exception:
        pairs, last = [], float('nan')

    # ---- Augšējā rinda: ikona + nosaukums + liels skaitlis ----
    _draw_icon(ax, meta["icon"], accent)
    ax.text(0.26, 0.90, title, fontsize=13, fontweight="bold", color=WHITE,
            va="center", ha="left", transform=ax.transAxes, zorder=3)
    # vienība + datums pa labi no nosaukuma
    per = (pairs[-1][0][:7] if pairs else "")
    ax.text(0.99, 0.90, per, fontsize=8, color=MUTED,
            va="center", ha="right", transform=ax.transAxes, zorder=3)

    # liels skaitlis (kompakts, virs diagrammas)
    if meta["calc"] == "gauge":
        big = f"{last:.2f}%" if last == last else "—"
    elif meta["calc"] in ("yoy", "yoy_q", "mom"):
        sign = "+" if last > 0 else "−"
        big = f"{sign}{abs(last):.1f}%" if last == last else "—"
    else:
        big = f"{last:.1f}" if last == last else "—"
    big_col = WHITE
    if meta["calc"] in ("yoy", "yoy_q", "mom") and last == last:
        big_col = GREEN if last >= 0 else RED
    ax.text(0.26, 0.60, big, fontsize=26, fontweight="bold", color=big_col,
            ha="left", va="center", transform=ax.transAxes, zorder=4)
    ax.text(0.70, 0.60, meta["unit"], fontsize=8.5, color=MUTED,
            ha="left", va="center", transform=ax.transAxes, zorder=3)

    # ---- Diagramma — dominēja apakšējā daļa (2/3 kartītes) ----
    if meta["calc"] == "gauge" and pairs:
        chart = ax.inset_axes((0.06, 0.06, 0.88, 0.38), transform=ax.transAxes)
        _draw_gauge(chart, pairs)
        chart.axis("off")
        for s in chart.spines.values():
            s.set_visible(False)
    else:
        chart = ax.inset_axes((0.04, 0.05, 0.92, 0.40), transform=ax.transAxes)
        if meta["calc"] in ("yoy", "yoy_q", "mom"):
            _draw_bars(chart, pairs, accent)
        else:
            _draw_sparkline(chart, pairs, accent)
        chart.axis("off")
        for s in chart.spines.values():
            s.set_visible(False)
            s.set_color("none")


if __name__ == "__main__":
    import sys
    keys = sys.argv[1:] if len(sys.argv) > 1 else ["gdp", "bezdarbs", "cpi", "corecpi", "gauge", "retail", "ind", "sent"]
    p = generate_dashboard(keys, "/tmp/asv_dashboard_demo.png")
    print("saved", p)