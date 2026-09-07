#!/usr/bin/env python3
"""ASV ekonomikas dati — dashboard infografika.
Rāda reālus makro rādītājus (FRED) ar mini-grafikiem: IKP, bezdarbs, inflācija,
Fed likme + nedēļai atbilstošos rādītājus. Zīmola (tumšs/zelta) stilā.
"""
import os
import io
import csv
import time
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Wedge
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# Dizains
# ---------------------------------------------------------------------------
BG_TOP = "#081a2e"
BG_BOT = "#0f2a45"
CARD = "#14293f"
CARD_EDGE = "#1f3c5a"
GOLD = "#f0c860"
WHITE = "#f5f1e6"
MUTED = "#93a9c0"
GREEN = "#2fbf71"
RED = "#ef6c6c"
AMBER = "#f0b34a"
BLUE = "#5aa9e6"

# ---------------------------------------------------------------------------
# FRED rādītāju reģistrs
# ---------------------------------------------------------------------------
# Katrs: key -> (fred_id, nosaukums LV, vienība/lielā skaitļa formāts, transformācija)
# transformācija: "value" | "yoy" | "mom" | "rate"
REGISTRY = {
    "gdp":     dict(id="GDPC1",    title="IKP IZAUGSME",      unit="% g/g",     calc="yoy_q",  icon="▲", accent=GREEN),
    "bezdarbs":dict(id="UNRATE",   title="BEZDARBA LĪMENIS",  unit="%",          calc="value",  icon="●", accent=BLUE),
    "cpi":     dict(id="CPIAUCSL", title="INFLĀCIJA (CPI)",    unit="% g/g",      calc="yoy",    icon="%",   accent=RED),
    "corecpi": dict(id="CPILFESL", title="PAMATA INFLĀCIJA",   unit="% g/g",      calc="yoy",    icon="%",   accent=RED),
    "ppi":     dict(id="PPIFIS",   title="RAŽOTĀJU CENAS",     unit="% g/g",      calc="yoy",    icon="►", accent=AMBER),
    "coreppi": dict(id="PPIFES",   title="PAMATA PPI",         unit="% g/g",      calc="yoy",    icon="►", accent=AMBER),
    "retail":  dict(id="RSAFS",    title="MAZUMTIRDZNIECĪBA",  unit="% m/m",      calc="mom",    icon="◆", accent=GREEN),
    "ind":     dict(id="INDPRO",   title="RŪPNIECĪBA",         unit="% m/m",      calc="mom",    icon="■", accent=GREEN),
    "sent":    dict(id="UMCSENT",  title="PATĒRĒTĀJU NOSKAŅOJUMS", unit="ind.",   calc="value",  icon="◐", accent=AMBER),
    "housing": dict(id="HOUST",    title="JAUNBŪVES",          unit="tūkst.",     calc="value_th", icon="▼", accent=BLUE),
    "gauge":   dict(id="DFEDTARU", title="FED BĀZES LIKME",    unit="%",          calc="gauge",  icon="◆", accent=None),
}

import requests

# ---------------------------------------------------------------------------
# FRED datu iegūšana
# ---------------------------------------------------------------------------
def _fetch_fred(fred_id, start="2022-01-01", retries=3):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}&cosd={start}"
    last = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"User-Agent": "curl/8.0"}, timeout=20)
            resp.raise_for_status()
            raw = resp.text
            rows = list(csv.reader(io.StringIO(raw)))[1:]
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
    """Atgriež (dates, values) pēc transformācijas."""
    raw = _fetch_fred(fred_id, start)
    dates = [r[0] for r in raw]
    nums = [_to_float(r[1]) for r in raw]
    nums = [n if n is not None else float('nan') for n in nums]

    if calc == "value":
        vals = nums
    elif calc == "value_th":
        vals = [n / 1000.0 for n in nums]
    elif calc == "yoy":
        vals = []
        for i, n in enumerate(nums):
            if i >= 12:
                base = nums[i - 12]
                vals.append((n / base - 1) * 100 if base else float('nan'))
            else:
                vals.append(float('nan'))
    elif calc == "yoy_q":  # ceturkšņa dati: 4 atpakaļ
        vals = []
        for i, n in enumerate(nums):
            if i >= 4:
                base = nums[i - 4]
                vals.append((n / base - 1) * 100 if base else float('nan'))
            else:
                vals.append(float('nan'))
    elif calc == "mom":
        vals = []
        for i, n in enumerate(nums):
            if i >= 1:
                base = nums[i - 1]
                vals.append((n / base - 1) * 100 if base else float('nan'))
            else:
                vals.append(float('nan'))
    else:
        vals = nums

    return dates, vals


def _clean_tail(dates, vals, n=18):
    """Pēdējie n nen-NaN punkti."""
    pairs = [(d, v) for d, v in zip(dates, vals) if v == v]  # not NaN
    return pairs[-n:]


# ---------------------------------------------------------------------------
# Rādītāju atlase pēc nedēļas notikumiem
# ---------------------------------------------------------------------------
# Sakritība (apakšvirkne, FRED key) — specifiskākās PIRMAS, lai notikums
# netiktu pieskaitīts gan vispārīgajam, gan pamata variantam.
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
    """Notikuma nosaukums (EN) -> viens FRED key vai None."""
    low = " " + event_name.lower() + " "
    for pat, key in NOTICE_MAP:
        if pat in low:
            return key
    return None


def select_indicators(events_by_day):
    """events_by_day: selected_events struktūra (dict diena -> [notikumu nosaukumi]).
    Atgriež unikālus FRED key sarakstu, kas atbilst nedēļas notikumiem, kārtībā."""
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
    ax.axhline(0, color=MUTED, linewidth=0.6)
    ax.axis("off")


def _draw_gauge(ax, rate_pairs, low=0, high=6):
    """Fed likmes mērītājs (pusloks). rate_pairs: [(date, val), ...]."""
    last = rate_pairs[-1][1] if rate_pairs else 3.5
    frac = max(0.0, min(1.0, (last - low) / (high - low)))
    ax.set_xlim(-1.2, 1.2); ax.set_ylim(-0.2, 1.15); ax.axis("off")
    # Aizmugure (gaiši pelēka puse)
    ax.add_patch(Wedge((0, 0), 1.0, 0, 180, width=0.22, facecolor="#27405a", edgecolor="none"))
    # Zaļa zona (pieņemam, ka 2.5-5.0 normāla -> zaļa 3-5)
    for a0, a1, col in [(45, 135, GREEN), (20, 45, AMBER), (135, 160, AMBER)]:
        ax.add_patch(Wedge((0, 0), 1.0, a0, a1, width=0.22, facecolor=col, edgecolor="none"))
    # Rādītāja adata
    ang = 180 * frac
    import math
    rad = math.radians(ang)
    ax.plot([0, 0.75 * math.sin(rad)], [0, 0.75 * math.cos(rad)],
            color=WHITE, linewidth=3, solid_capstyle="round")
    ax.add_patch(plt.Circle((0, 0), 0.07, color=GOLD))


# ---------------------------------------------------------------------------
# Galvenais ģenerators
# ---------------------------------------------------------------------------
def generate_dashboard(indicator_keys, out_path):
    """indicator_keys: list FRED key nosaukumu. Ģenerē dashboard attēlu."""
    n = len(indicator_keys)
    if n == 0:
        return None
    cols = 2
    rows = (n + cols - 1) // cols
    fig_w = 8.6
    fig_h = 1.1 + rows * 2.1
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=160)

    # Fona gradients visam fig
    grad = LinearSegmentedColormap.from_list("bg", [BG_TOP, BG_BOT])
    bgax = fig.add_axes([0, 0, 1, 1]); bgax.set_xticks([]); bgax.set_yticks([])
    bgax.imshow([[0, 1]], aspect="auto", extent=(0, 1, 0, 1), cmap=grad, zorder=0)
    bgax.set_zorder(0)

    # Virsraksts
    fig.text(0.05, 0.965, "ASV EKONOMISKIE DATI", fontsize=22, fontweight="bold",
             color=GOLD, ha="left", va="top")
    fig.text(0.05, 0.925, "Aktuālie rādītāji nedēļai", fontsize=10.5, color=MUTED,
             ha="left", va="top")

    # Kartes
    # Rokas grid — katrs bloks pa aksi
    for idx, key in enumerate(indicator_keys):
        meta = REGISTRY[key]
        col = idx % cols
        row_i = idx // cols
        left = 0.05 + col * 0.465
        bottom = 0.86 - (row_i + 1) * (0.84 / rows)  # approx
        # (tiek precizēts zemāk)

    # Vienkāršāka pieeja: izmantot GridSpec manuāli
    gs = fig.add_gridspec(rows, cols, left=0.05, right=0.955, top=0.90, bottom=0.06,
                          wspace=0.10, hspace=0.35)
    for idx, key in enumerate(indicator_keys):
        meta = REGISTRY[key]
        ax = fig.add_subplot(gs[idx // cols, idx % cols])
        _draw_card(ax, meta, key)

    plt.savefig(out_path, dpi=160, facecolor=BG_BOT)
    plt.close(fig)
    return out_path


def _draw_card(ax, meta, key):
    """uzzīmē vienu kartiņu uz ax."""
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor(CARD)

    # Kartītes fons ar apmali
    ax.add_patch(FancyBboxPatch((0.0, 0.0), 1, 1,
                 boxstyle="round,pad=0.0,rounding_size=0.02",
                 facecolor=CARD, edgecolor=CARD_EDGE, linewidth=1.2,
                 transform=ax.transAxes, zorder=0))
    accent = meta["accent"]

    # Ikonas + nosaukums
    icon = meta["icon"]
    title = meta["title"]
    ax.text(0.06, 0.90, title, fontsize=11.5, fontweight="bold", color=WHITE,
            va="top", ha="left", transform=ax.transAxes, zorder=3)
    ax.text(0.93, 0.90, icon, fontsize=14, va="top", ha="right", color=accent if accent else GOLD,
            transform=ax.transAxes, zorder=3)

    # Datu iegūšana
    try:
        dates, vals = _values(meta["id"], meta["calc"])
        pairs = _clean_tail(dates, vals, 16)
        last = pairs[-1][1] if pairs else float('nan')
    except Exception:
        pairs = []
        last = float('nan')

    # Lielais skaitlis
    if meta["calc"] == "gauge":
        big = f"{last:.2f}%" if last == last else "—"
    elif meta["calc"] in ("yoy", "yoy_q", "mom"):
        sign = "+" if last > 0 else ""
        big = f"{sign}{last:.1f}%" if last == last else "—"
    else:
        big = f"{last:.1f}" if last == last else "—"
    big_col = WHITE
    if meta["calc"] in ("yoy", "yoy_q", "mom") and last == last:
        big_col = GREEN if last >= 0 else RED
    ax.text(0.06, 0.62, big, fontsize=22, fontweight="bold", color=big_col,
            va="center", transform=ax.transAxes, zorder=3)

    # Periods (datums no pēdējā punkta)
    per = pairs[-1][0][:7] if pairs else ""
    ax.text(0.44, 0.62, meta['unit'], fontsize=8.5, color=MUTED,
            va="center", ha="left", transform=ax.transAxes, zorder=3)
    ax.text(0.44, 0.52, per, fontsize=8.5, color=MUTED,
            va="center", ha="left", transform=ax.transAxes, zorder=3)

    # Mini diagramma apakšā
    if meta["calc"] == "gauge" and pairs:
        gax = ax.inset_axes([0.06, 0.04, 0.5, 0.42], transform=ax.transAxes)
        _draw_gauge(gax, pairs)
        gax.set_facecolor(CARD)
    else:
        chart = ax.inset_axes([0.05, 0.03, 0.9, 0.42], transform=ax.transAxes)
        if meta["calc"] in ("yoy", "yoy_q", "mom"):
            _draw_bars(chart, pairs, accent if accent else GREEN)
        else:
            _draw_sparkline(chart, pairs, accent if accent else BLUE)
        chart.set_facecolor(CARD)
        # lai neredzētu baltu fonu
        for s in chart.spines.values():
            s.set_visible(False)


if __name__ == "__main__":
    import sys
    keys = sys.argv[1:] if len(sys.argv) > 1 else ["gdp", "bezdarbs", "cpi", "corecpi", "gauge"]
    p = generate_dashboard(keys, "/tmp/asv_dashboard_demo.png")
    print("saved", p)
