#!/usr/bin/env python3
"""ETF X (Twitter) posta nosūtīšana caur composio MCP — pēc Telegram ziņas.

Lietošana:
    /root/.hermes/venv/bin/python3 /root/scripts/x_poster.py [--dry-run] [--force]

Plūsma (etf_run.sh beigās, pēc etf_sender.py):
1. Nolasa tos pašus datus kā etf_sender.py (sosovalue_etf_data.json) — viens avots.
2. Pārbauda NEPUBLICĒŠANAS nosacījumus (sk. darba apraksta 4. sadaļu).
3. Veido EN tekstu precīzā formā (≤280).
4. Dubultā posta aizsardzība (.x_last_posted).
5. Publicē caur composio_x_post.py (bildi no /root/scripts/assets/etf_x.png).
6. Ja izlaists/neizdevās → īsa servisa ziņa uz Telegram.

--force: apstiprināts testa posts — apej skip-nosacījumus (NYSE slēgts, novecojuši dati,
         garš teksts), bet joprojām publicē caur composio un atzīmē datumu.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pandas_market_calendars as mcal

JSON_PATH = "/root/scripts/sosovalue_etf_data.json"
IMAGE_PATH = "/root/scripts/assets/etf_x.png"
LAST_POSTED_PATH = "/root/scripts/.x_last_posted"
ENV_PATH = "/root/.hermes/.env"
CHAT_ID = "1494676964"
COINS = ["BTC", "ETH", "XRP", "SOL"]  # secība vienmēr šāda

# VPS laika josla ir Europe/Berlin (UTC+2 vasarā). ASV tirgus diena = NYSE.
TZ = timezone(timedelta(hours=2))  # CEST

_DRY_RUN = False  # --dry-run režīms: nesūtīt Telegram paziņojumus


def load_token():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                    tok = line.strip().split("=", 1)[1].strip().strip('"\'')
                    break
    if not tok:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nav atrasts")
    return tok


def send_telegram_notice(text):
    """Īsa servisa ziņa uz Telegram (tikai kad X izlaists/neizdevās). --dry-run nesūta."""
    if _DRY_RUN:
        return
    try:
        tok = load_token()
        import requests
        url = "https://api.telegram.org/bot{}/sendMessage".format(tok)
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=15)
    except Exception as e:
        print("Neizdevās nosūtīt servisa ziņu: {}".format(e))


def nyse_last_trading_day_before(today):
    """Pēdējā NYSE tirdzniecības diena pirms today (datetime.date)."""
    cal = mcal.get_calendar("NYSE")
    start = today - timedelta(days=10)
    days = cal.valid_days(start, today - timedelta(days=1))
    if len(days) == 0:
        return None
    return days[-1].date()


def fmt_money(val):
    """$159.45M, $-39.24M, $0M — 2 cipari aiz komata, bez + zīmes; nulle bez cipariem."""
    m = val / 1_000_000.0
    if m == 0:
        return "$0M"
    return "${:,.2f}M".format(m)


def fmt_date(etf_date):
    """'2026-09-17' → 'September 17' (mēneša nosaukums + diena, bez nulles, bez th)."""
    d = datetime.strptime(etf_date, "%Y-%m-%d")
    return d.strftime("%B %-d")


def build_post(data, etf_date):
    """Veido EN posta tekstu precīzā formā. Atgriež (text, len)."""
    lines = []
    lines.append("ETF FLOWS: On {}.".format(fmt_date(etf_date)))
    lines.append("")
    for coin in COINS:
        records = data.get(coin, [])
        if not records:
            return None, "{}: nav datu".format(coin)
        net = records[0].get("total_net_inflow")
        if net is None:
            return None, "{}: total_net_inflow tukšs".format(coin)
        flow = "net inflow" if net >= 0 else "net outflow"
        lines.append("#{} ETFs saw {} in {}.".format(coin, fmt_money(net), flow))
    lines.append("")
    lines.append("Check it out mracrypto.co 🚀")
    text = "\n".join(lines)
    return text, len(text)


def main():
    global _DRY_RUN
    dry_run = "--dry-run" in sys.argv
    _DRY_RUN = dry_run
    force = "--force" in sys.argv  # apstiprināts testa posts: apej skip-nosacījumus

    # 1. Dati — viens avots ar etf_sender.py
    if not os.path.exists(JSON_PATH):
        send_telegram_notice("X post skipped: ETF data file missing")
        print("X post skipped: nav datu faila")
        return 1
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 2. Datuma pārbaude: visiem 4 simboliem jābūt no viena datuma
    dates = {}
    for coin in COINS:
        records = data.get(coin, [])
        dates[coin] = records[0].get("date") if records else None
    unique = set(d for d in dates.values() if d)
    if len(unique) != 1:
        reason = "; ".join("{}={}".format(c, dates[c]) for c in COINS)
        send_telegram_notice("X post skipped: date mismatch between symbols")
        print("X post skipped: datumi nesakrīt ({})".format(reason))
        return 1
    etf_date = next(iter(unique))
    if etf_date is None:
        send_telegram_notice("X post skipped: no data date")
        print("X post skipped: nav datuma")
        return 1

    # 3. Teksts (veidojam agri, lai dry-run vienmēr parāda tekstu un garumu)
    text, length = build_post(data, etf_date)
    if text is None:
        send_telegram_notice("X post skipped: {}".format(length))
        print("X post skipped: {}".format(length))
        return 1

    if dry_run:
        print("=== DRY RUN — netiek publicēts ===")
        print(text)
        print("\nGarums: {}/280".format(length))
        print("Datums: {} ({}).".format(etf_date, fmt_date(etf_date)))

    # 4. NEPUBLICĒŠANAS nosacījumi (ar --force apstiprinātam testam tiek apieti)
    # a) ASV tirgus slēgts datuma dienā (nedēļas nogale / NYSE brīvdiena)
    try:
        d = datetime.strptime(etf_date, "%Y-%m-%d").date()
    except ValueError:
        send_telegram_notice("X post skipped: bad data date format")
        print("X post skipped: nepareizs datuma formāts {}".format(etf_date))
        return 1
    cal = mcal.get_calendar("NYSE")
    valid_dates = {ts.date() for ts in cal.valid_days(d, d)}
    if d not in valid_dates and not force:
        send_telegram_notice("X post skipped: US market closed")
        print("X post skipped: ASV tirgus slēgts {}".format(etf_date))
        return 1

    # b) Nav jaunu datu: datuma dienai jābūt pēdējai NYSE dienai pirms šodienas
    today = datetime.now(TZ).date()
    last_td = nyse_last_trading_day_before(today)
    if (last_td is None or d != last_td) and not force:
        send_telegram_notice("X post skipped: no new data (stale)")
        print("X post skipped: dati novecojuši ({}, pēdējā diena {})".format(etf_date, last_td))
        return 1

    # c) Kāda vērtība tukša/None
    for coin in COINS:
        records = data.get(coin, [])
        if not records or records[0].get("total_net_inflow") is None:
            send_telegram_notice("X post skipped: missing data for {}".format(coin))
            print("X post skipped: {} datu trūkst".format(coin))
            return 1

    # d) Teksts ≤ 280
    if length > 280 and not force:
        send_telegram_notice("X post skipped: text too long ({})".format(length))
        print("X post skipped: teksts pārāk garš ({}/280)".format(length))
        return 1

    # 5. Dubultā posta aizsardzība
    if os.path.exists(LAST_POSTED_PATH):
        with open(LAST_POSTED_PATH, encoding="utf-8") as f:
            last = f.read().strip()
        if last == etf_date:
            print("X post skipped: {} jau publicēts (dubultā aizsardzība)".format(etf_date))
            return 0

    # 6. Bilde
    if not os.path.exists(IMAGE_PATH):
        send_telegram_notice("X post skipped: image missing")
        print("X post skipped: nav bildes {}".format(IMAGE_PATH))
        return 1

    if dry_run:
        print("Bilde: {} (eksistē)".format(IMAGE_PATH))
        print("Rezultāts: GATAVS publicēšanai")
        return 0

    # 7. Publicēšana caur composio
    print("=== Publicēju X postu ===")
    cmd = [
        "/root/.hermes/venv/bin/python3",
        "/root/scripts/composio_x_post.py",
        text,
        IMAGE_PATH,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(r.stdout)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:200]
        send_telegram_notice("X post failed: composio error {}".format(err))
        print("X post neizdevās: {}".format(err))
        return 1

    # 8. Atzīmē publicēto datumu
    with open(LAST_POSTED_PATH, "w", encoding="utf-8") as f:
        f.write(etf_date)
    print("X post publicēts ({})".format(etf_date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
