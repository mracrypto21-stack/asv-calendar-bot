import os
import re
import json
import urllib.request
import ssl
from datetime import datetime, timedelta
import requests

# GitHub Actions / local run
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def fetch_forexfactory_calendar():
    url = "https://r.jina.ai/https://www.forexfactory.com/calendar"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl._create_unverified_context()
    r = urllib.request.urlopen(req, context=ctx, timeout=30)
    return r.read().decode("utf-8", errors="replace")

def parse_us_events(text):
    lines = text.split('\n')
    us_events = {}
    current_date = None

    for line in lines:
        date_match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(Aug\s+\d+)', line)
        if date_match:
            current_date = date_match.group(2)
            continue

        if not line.startswith('|') or not current_date:
            continue

        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 5:
            continue

        currency = parts[2].strip()
        event_raw = parts[4].strip()

        if currency == 'USD' and event_raw:
            event_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', event_raw)
            event_clean = re.sub(r'!\[\]\([^\)]+\)', '', event_clean).strip()

            if event_clean and event_clean not in ['', 'Actual', 'Forecast', 'Previous']:
                if current_date not in us_events:
                    us_events[current_date] = []
                us_events[current_date].append(event_clean)

    return us_events

IMPORTANT_KEYWORDS = [
    'FOMC', 'CPI', 'PMI', 'NFP', 'Employment', 'GDP', 'Fed',
    'Empire State', 'Housing', 'Permits', 'Philly Fed', 'Jobless',
    'Claims', 'Unemployment', 'Retail Sales', 'Durable Goods',
    'Consumer Confidence', 'Pending Home Sales', 'Building'
]

def select_top_events(us_events, max_per_day=2):
    selected = {}
    for date, events in sorted(us_events.items()):
        scored = []
        for ev in events:
            score = sum(1 for kw in IMPORTANT_KEYWORDS if kw.lower() in ev.lower())
            scored.append((score, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [ev for _, ev in scored[:max_per_day]]
        selected[date] = top if top else ["Nav svarīgu ekonomisko datu"]
    return selected

DATE_MAP = [
    ("Pirmdiena", "Mon"),
    ("Otrdiena", "Tue"),
    ("Trešdiena", "Wed"),
    ("Ceturtiena", "Thu"),
    ("Piektdiena", "Fri"),
]

def build_message(selected_events, next_monday):
    dates = {
        "Mon": (next_monday + timedelta(days=0)).strftime("%d.%m."),
        "Tue": (next_monday + timedelta(days=1)).strftime("%d.%m."),
        "Wed": (next_monday + timedelta(days=2)).strftime("%d.%m."),
        "Thu": (next_monday + timedelta(days=3)).strftime("%d.%m."),
        "Fri": (next_monday + timedelta(days=4)).strftime("%d.%m."),
    }

    lines = ["📊 Nākamās nedēļas ASV ekonomikas dati", ""]

    for lv_name, en_abbr in DATE_MAP:
        date_str = dates.get(en_abbr, "")
        events = selected_events.get(en_abbr + " " + date_str.split('.')[0].lstrip('0'), [])
        if not events:
            events = selected_events.get(en_abbr, ["Nav svarīgu ekonomisko datu"])

        lines.append(f"📅 {lv_name}, {date_str}")
        for ev in events:
            lines.append(f"✅ {ev}")
        lines.append("")

    lines.append("---")
    lines.append("Šīs nedēļas svarīgie makroekonomikas dati var ievērojami ietekmēt tirgus kustības.")
    return "\n".join(lines)

def self_check(text):
    errors = []
    if text.count('📅') != 5:
        errors.append(f"Nav 5 dienu ierakstu: {text.count('📅')}")
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith(('📅', '✅', '📊', '---')):
            if line.endswith(('Sāk', 'un ', 'par ', 'uz ', 'no ', 'un')):
                errors.append(f"Iespējama nepilnīga teikuma: {line}")
    words = text.lower().split()
    for i in range(len(words) - 1):
        if words[i] == words[i + 1] and words[i] not in ['un', 'ar', 'no', 'par', 'uz', 'ja', 'kas']:
            errors.append(f"Vārdu atkārtojums: {words[i]}")
    for artifact in ['influences', ' the ', ' and ', ' of ', ' to ', ' is ', ' for ']:
        if artifact in text.lower():
            errors.append(f"Tenglish fragments: {artifact}")
    return errors

def send_telegram(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'disable_web_page_preview': True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if result.get('ok'):
        print(f'Sent message_id={result["result"]["message_id"]}')
    else:
        print(f'Kļūda sūtot ziņu: {result}')
        exit(1)

def send_alert(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"ALERT: {text}")
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': f"⚠️ ASV kalendāra brīdinājums: {text}",
        'disable_web_page_preview': True,
    }
    requests.post(url, json=payload, timeout=15)

def main():
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)

    print(f"Next week starts: {next_monday.strftime('%Y-%m-%d')}")

    try:
        body = fetch_forexfactory_calendar()
        us_events = parse_us_events(body)
        total_us = sum(len(v) for v in us_events.values())
        print(f"Parsed USD events: {total_us}")

        if total_us < 3:
            send_alert(f"Pārāk maz ASV notikumu atrasti: {total_us}. Iespējams, avots ir mainījies.")
            exit(1)

        selected = select_top_events(us_events)
        message = build_message(selected, next_monday)

        errors = self_check(message)
        if errors:
            send_alert(f"Self-check kļūdas: {errors}")
            exit(1)

        send_telegram(message)
        print("✅ Ziņa nosūtīta veiksmīgi")

    except Exception as e:
        send_alert(f"Kļūda: {e}")
        exit(1)

if __name__ == '__main__':
    main()
