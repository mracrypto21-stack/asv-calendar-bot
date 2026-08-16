import os
import urllib.request
import ssl
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

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

def main():
    now = datetime.now()
    next_monday = now + __import__('datetime').timedelta(days=(7 - now.weekday()) % 7 or 7)
    dates = [(next_monday + __import__('datetime').timedelta(days=i)).strftime("%d.%m.") for i in range(5)]
    days_lv = ["Pirmdiena", "Otrdiena", "Trešdiena", "Ceturtiena", "Piektdiena"]
    date_lines = "\n".join([f"{days_lv[i]}, {dates[i]}" for i in range(5)])
    
    message = f"✅ ASV kalendāra sistēma darbojas.\n\nNākamā nedēļa:\n{date_lines}\n\nNākamā pārbaude: katru svētdienu 18:30 UTC."
    send_telegram(message)
    print("✅ Health check nosūtīts")

if __name__ == '__main__':
    main()
