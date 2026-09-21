#!/usr/bin/env python3
"""ASV nedēļas notikumu X poste (EN) ar to pašu bildi, ko sūta Telegram.

Plūsma:
1. Atlasa nedēļas notikumus (tā pati loģika kā asv_calendar.py).
2. Ģenerē EN apkopojumu formātā (bez '-', ar ciparu datumiem DD.MM., + linku).
3. Izmanto to pašu bildi, ko ģenerēja Telegram sūtījums (asv_dashboard_<YYYYMMDD>.png).
4. Publicē caur composio_x_post.py (VPS).

Lietošana (VPS):
    /root/.hermes/venv/bin/python3 asv_x_poster.py [--dry-run]

Saistība ar cron: izsauc no asv_run.sh PĒC Telegram sūtījuma (ar `|| true`,
lai X kļūme nebloķē Telegram).
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asv_calendar as m

# Kartēšana: family_key -> EN nosaukums X postam.
EN_NAME = {
    "fomc": "FOMC Rate Decision",
    "inflacija_core": "Core CPI Inflation data",
    "inflacija": "CPI Inflation data",
    "ppi_core": "Core PPI Inflation data",
    "ppi": "PPI Inflation data",
    "pce": "PCE Inflation data",
    "darba_tirgus_nfp": "Non-Farm Payrolls data",
    "bezdarbs": "Unemployment Rate data",
    "jobless": "Initial Jobless Claims data",
    "ikp": "GDP data",
    "retail": "Retail Sales data",
    "rūpn_empire": "Empire State Manufacturing Index",
    "rūpn_philly": "Philly Fed Manufacturing Index",
    "housing_starts": "Housing Starts data",
    "permits": "Building Permits data",
    "pending_home": "Pending Home Sales data",
    "conf": "Consumer Confidence data",
    "sentiment": "Michigan Consumer Sentiment data",
    "pmi": "S&P Global Flash PMI data",
    "capacity": "Capacity Utilization data",
    "indprod": "Industrial Production data",
    "dur": "Durable Goods Orders data",
    "factory": "Factory Orders data",
}

# Saraksts, kuriem mēneša prefikss ir dabīgs (dati par iepriekšējo mēnesi).
PREV_MONTH = {
    "inflacija_core", "inflacija", "ppi_core", "ppi", "pce", "dur", "retail",
}

# Saraksts, kuriem mēneša prefikss ir pašreizējais mēnesis (piem., MI Consumer Sentiment).
CUR_MONTH = {"sentiment"}

MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}


def fmt_date(date_obj):
    """DD.MM. bez nullēm kā lietotājs vēlas (21.09., 22.09. ...)."""
    return f"{date_obj.day}.{date_obj.month:02d}."


def month_name(date_obj, prev=False):
    mo = (date_obj.month - 1) if prev else date_obj.month
    if mo == 0:
        mo = 12
    return MONTHS[mo]


def en_name_for(display_name):
    """Mēģina atrast EN nosaukumu no display_name (latviešu) vai fallback."""
    fam = m._match_family(display_name)
    if fam:
        key_, disp, hl = fam
        if key_ in EN_NAME:
            return EN_NAME[key_]
    name = display_name.lower()
    for key_, en in EN_NAME.items():
        pat = key_.replace("_", " ")
        if pat in name or key_ in name:
            return en
    return display_name


def build_en(selected, next_monday):
    """Veido EN apkopojumu. selected: {date_key: [display_name, ...]}."""
    lines = ["Key Economic Events next Week:", ""]
    for i, (lv_name, en_abbr) in enumerate(m.DATE_MAP):
        date_obj = next_monday + timedelta(days=i)
        date_key = None
        for dk in selected:
            parts = dk.split()
            if len(parts) >= 2 and parts[0] == en_abbr:
                date_key = dk
                break
        if not date_key:
            continue
        events = selected[date_key]
        events = [e for e in events if e != "Nav svarīgu ekonomisko datu"
                  and not e.startswith("🏖️")]
        if not events:
            continue
        en_items = []
        for ev in events:
            key_ = en_name_for(ev)
            fam = m._match_family(ev)
            if fam and fam[0] in PREV_MONTH:
                key_ = f"{month_name(date_obj, prev=True)} {key_}"
            elif fam and fam[0] in CUR_MONTH:
                key_ = f"{month_name(date_obj, prev=False)} {key_}"
            en_items.append(key_)
        line = f"{fmt_date(date_obj)} {', '.join(en_items)}"
        lines.append(line)
    lines.append("")
    lines.append("Check it out mracrypto.co 🚀")
    return "\n".join(lines)


def get_image(selected, next_monday):
    """Atgriež to pašu bildi, ko ģenerē asv_calendar.py. None, ja nav."""
    for root, _, files in os.walk("/root/scripts"):
        for f in files:
            if f.startswith(f"asv_dashboard_{next_monday.strftime('%Y%m%d')}.png"):
                return os.path.join(root, f)
    return None


def send_telegram_notice(text):
    import re
    import requests
    try:
        tok = open("/root/.hermes/.env").read()
        t = re.search(r"TELEGRAM_BOT_TOKEN\s*=\s*(\S+)", tok).group(1).strip("'\" ")
        requests.post(
            f"https://api.telegram.org/bot{t}/sendMessage",
            json={"chat_id": "1494676964", "text": text,
                  "disable_web_page_preview": True}, timeout=20)
    except Exception as e:
        print("notice send failed:", e)


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)

    body = m.fetch_forexfactory_calendar()
    us_events = m.parse_us_events(body)
    selected = m.select_top_events(us_events)

    text = build_en(selected, next_monday)
    wlen = len(text)
    print("=== X post (EN) ===")
    print(text)
    print("=== length:", wlen, "(limit 280) ===")

    if wlen > 280:
        print("X post pārāk garš — NEPOSTu")
        send_telegram_notice(f"ASV X post skipped: too long ({wlen}>280)")
        return 1

    img = get_image(selected, next_monday)
    if not img or not os.path.exists(img):
        print("Bilde nav atrasta — sūtu tikai tekstu")
    else:
        print("Bilde:", img, "(eksistē)")

    if dry_run:
        print("DRY-RUN: nepostu")
        return 0

    print("=== Publicēju X postu ===")
    if img and os.path.exists(img):
        cmd = ["/root/.hermes/venv/bin/python3",
               "/root/scripts/composio_x_post.py", text, img]
    else:
        cmd = ["/root/.hermes/venv/bin/python3",
               "/root/scripts/composio_x_post.py", text]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(r.stdout)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:200]
        send_telegram_notice(f"ASV X post failed: {err}")
        print("X post neizdevās:", err)
        return 1
    print("X post publicēts")
    return 0


if __name__ == "__main__":
    sys.exit(main())