#!/usr/bin/env python3
"""ASV nedēļas ekonomikas infografika.
Ģenerē PNG no atlasītajiem notikumiem — zīmola (tumšs/zelta) stilā.
Paredzēts importam no asv_calendar.py: generate_infographic(selected_events, next_monday, out_path)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.colors import LinearSegmentedColormap
from datetime import timedelta

# ---------------------------------------------------------------------------
# Dizaina krāsas — Kripto Nr.1 zīmols
# ---------------------------------------------------------------------------
C = {
    "bg_top": "#071526",
    "bg_bot": "#12263f",
    "card": "#16283e",
    "card_edge": "#24405e",
    "gold": "#f0c860",
    "gold_dark": "#c9a13b",
    "white": "#f7f3e8",
    "muted": "#8fa8bf",
    "green": "#2fbf71",
    "blue": "#5aa9e6",
    "red": "#ef6c6c",
    "amber": "#f0b34a",
}

# Dienu nosaukumi (pēc kartēšanas secības) — nodrošina, ka vienmēr 5 rindas
DATE_MAP = [
    ("Pirmdiena", "Mon"),
    ("Otrdiena", "Tue"),
    ("Trešdiena", "Wed"),
    ("Ceturtiena", "Thu"),
    ("Piektdiena", "Fri"),
]

HOLIDAYS = {"Sep 7": "🏖️ Labor Day"}

# Īsi latviski nosaukumi vizuālajam (ja atrodams atslēgvārds) — citādi rāda EN
LV_SHORT = {
    "fomc meeting minutes": "FOMC protokols",
    "fomc": "FOMC sanāksme",
    "core cpi": "Pamata inflācija (Core CPI)",
    "cpi": "Inflācija (CPI)",
    "core ppi": "Pamata PPI",
    "ppi": "Ražotāju cenas (PPI)",
    "non-farm employment": "Nodarbinātība (NFP)",
    "adp": "ADP nodarbinātība",
    "unemployment claims": "Bezdarba pieteikumi",
    "jobless claims": "Bezdarba pieteikumi",
    "unemployment rate": "Bezdarba līmenis",
    "payrolls": "Algu saraksti (NFP)",
    "philly fed": "Philly Fed indekss",
    "empire state": "Empire State indekss",
    "building permits": "Būvatļaujas",
    "housing starts": "Jaunbūves (Housing Starts)",
    "pending home sales": "Mājokļu pārdošanas līgumi",
    "existing home sales": "Mājokļu pārdošana",
    "retail sales": "Mazumtirdzniecība",
    "durable goods": "Ilgtermiņa preču pasūtījumi",
    "gdp": "Iekšzemes kopprodukts (GDP)",
    "pmi": "PMI aktivitātes indekss",
    "ism": "ISM biznesa indekss",
    "consumer confidence": "Patērētāju konfidence",
    "consumer credit": "Patēriņa kredīti",
    "nfib": "NFIB mazo uzņēmumu indekss",
    "powell speaks": "Pauela uzruna",
    "speaks": "Fed pārstāvja uzruna",
    "treasury auction": "Obligāciju izsole",
    "crude oil": "Naftas krājumi",
    "trade balance": "Tirdzniecības bilance",
    "industrial production": "Rūpniecības izlaide",
    "factory orders": "Rūpniecības pasūtījumi",
    "inventories": "Krājumi",
}

# Cik ietekmīgs (punkti) — tuvinājums pēc atslēgvārda
HIGH = ["cpi", "fomc", "fed", "payrolls", "employment", "gdp", "unemployment", "nfp"]
MED = ["ppmf", "retail", "durable", "housing", "pmi", "adp", "ism", "consumer", "permits", "starts"]

def lv_name(en):
    """Pārvērš EN notikuma nosaukumu īsā latviskā (ja zināms), saglabājot m/m · y/y."""
    low = en.lower()
    out = None
    for k, v in sorted(LV_SHORT.items(), key=lambda x: -len(x[0])):
        if k in low:
            out = v
            break
    if out is None:
        out = en
    # nošķir mēneša / gada izmaiņas
    if " m/m" in en or " m/m)" in en or en.lower().endswith(" m/m"):
        out += " (mēnesī)"
    elif " y/y" in en or " y/y)" in en or en.lower().endswith(" y/y"):
        out += " (gadā)"
    return out

def impact_level(en):
    low = en.lower()
    if any(h in low for h in HIGH):
        return 3
    if any(m in low for m in MED):
        return 2
    return 1

def _day_events(selected_events, date_key_map, abbr):
    """selected_events[abbr] pēc scrape kartēšanas — kā build_message."""
    return date_key_map.get(abbr, [])

def generate_infographic(selected_events, next_monday, out_path,
                         scraped_dates=None):
    """Ģenerē infografiku PNG formātā no selected_events (scrape) un next_monday.
    scraped_dates: {abbr: full_date_key} — ja nav dots, atvasina automātiski."""
    if scraped_dates is None:
        scraped_dates = {}
        for dk in selected_events.keys():
            parts = dk.split()
            if len(parts) >= 2:
                scraped_dates[parts[0]] = dk
    # Sagatavot rindas (vienmēr 5 dienas)
    rows = []
    for i, (day_lv, en_abbr) in enumerate(DATE_MAP):
        date_obj = next_monday + timedelta(days=i)
        month_day = date_obj.strftime("%b %-d")
        holiday = HOLIDAYS.get(month_day)
        if holiday:
            events = [holiday]
        elif scraped_dates:
            dk = scraped_dates.get(en_abbr)
            events = selected_events.get(dk, ["Nav svarīgu ekonomisko datu"]) if dk else ["Nav svarīgu ekonomisko datu"]
        else:
            events = ["Nav svarīgu ekonomisko datu"]
        rows.append((day_lv, date_obj.strftime("%d.%m."), events))

    days = len(rows)
    # Augstums atkarīgs no satura daudzuma + papildu augšējā atstarpe virsrakstam
    fig_h = 2.6 + days * 2.15
    fig, ax = plt.subplots(figsize=(8.5, fig_h), dpi=170)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    # Fona vertikālais gradients
    grad = LinearSegmentedColormap.from_list("bg", [C["bg_top"], C["bg_bot"]])
    ax.imshow([[0, 1]], extent=(0, 10, 0, fig_h), aspect="auto", cmap=grad, zorder=0)

    # ---- Virsraksts ----
    ty = fig_h - 0.5
    ax.text(0.5, ty, "NĀKAMĀS NEDĒĻAS", fontsize=19, fontweight="bold",
            color=C["muted"], ha="left", va="center")
    ax.text(0.5, ty - 0.75, "ASV EKONOMIKA", fontsize=30, fontweight="bold",
            color=C["gold"], ha="left", va="center")
    # Zelta līnija zem virsraksta
    ax.add_patch(Rectangle((0.52, ty - 1.02), 2.6, 0.035, color=C["gold"], zorder=3))
    # Datumu diapazons pa labi
    ax.text(9.5, ty - 0.15, f"{rows[0][1][:5]}–{rows[-1][1][:5]}",
            fontsize=15, color=C["white"], ha="right", va="center", fontweight="bold")
    ax.text(9.5, ty - 0.7, "Galvenie notikumi", fontsize=10, color=C["muted"],
            ha="right", va="center")

    # ---- Dienu kartītes ----
    top = fig_h - 2.5
    for i, (row_day, date_str, events) in enumerate(rows):
        cy = top - i * 2.15
        # Kartītes fons
        ax.add_patch(FancyBboxPatch((0.3, cy - 1.12), 9.4, 1.85,
                     boxstyle="round,pad=0.02,rounding_size=0.14",
                     linewidth=0, facecolor=C["card"], edgecolor="none"))
        ax.add_patch(FancyBboxPatch((0.3, cy - 1.12), 9.4, 1.85,
                     boxstyle="round,pad=0.02,rounding_size=0.14",
                     linewidth=1.0, facecolor="none", edgecolor=C["card_edge"]))
        # Kreisā akcenta josla atkarībā no ietekmes
        imp = max((impact_level(e) for e in events), default=1)
        accent = {1: C["green"], 2: C["amber"], 3: C["red"]}[imp]
        ax.add_patch(FancyBboxPatch((0.42, cy - 1.0), 0.10, 1.6,
                     boxstyle="round,pad=0.02,rounding_size=0.05",
                     facecolor=accent, edgecolor="none"))

        # Dienas nosaukums + ietekmes punkti
        ax.text(0.78, cy + 0.45, row_day, fontsize=15, fontweight="bold",
                color=C["white"], ha="left", va="center")
        # punkti (ietekmes indikators)
        dot_col = {1: C["green"], 2: C["amber"], 3: C["red"]}[imp]
        n_dots = {1: 1, 2: 3, 3: 5}[imp]
        for di in range(5):
            dx = 0.78 + di * 0.30
            col = dot_col if di < n_dots else "#37506b"
            ax.add_patch(Rectangle((dx, cy + 0.27), 0.18, 0.055, color=col))
        ax.text(9.55, cy + 0.45, date_str, fontsize=14, fontweight="bold",
                color=C["gold"], ha="right", va="center")

        # Notikumu saraksts
        ev_y = cy - 0.15
        for ev in events:
            label = lv_name(ev)
            ax.text(0.78, ev_y, f"◆  {label}", fontsize=12.5, color=C["white"],
                    ha="left", va="center")
            ev_y -= 0.62

    # ---- Futers ----
    ax.text(0.5, 0.3, "KRIPTO NR.1  •  kriptonr1.xyz", fontsize=11, fontweight="bold",
            color=C["gold"], ha="left", va="center")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(out_path, dpi=170, facecolor=C["bg_bot"], bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    # Pašpārbaude ar fiktīviem datiem
    sample = {
        "Mon Sep 7": ["Bank Holiday"],
        "Tue Sep 8": ["NFIB Small Business Index", "Consumer Credit m/m"],
        "Wed Sep 9": ["ADP Weekly Employment Change", "10-y Bond Auction"],
        "Thu Sep 10": ["Unemployment Claims", "Core PPI m/m"],
        "Fri Sep 11": ["Core CPI m/m", "Core CPI y/y"],
    }
    from datetime import datetime
    nm = datetime(2026, 9, 7).date()
    sd = {"Mon": "Mon Sep 7", "Tue": "Tue Sep 8", "Wed": "Wed Sep 9",
          "Thu": "Thu Sep 10", "Fri": "Fri Sep 11"}
    generate_infographic(sample, nm, "/tmp/asv_infographic_test.png", scraped_dates=sd)
    print("saved /tmp/asv_infographic_test.png")
