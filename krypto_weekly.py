#!/usr/bin/env python3
"""Nedēļas kripto tirgus pārskats — pirmdienās 09:00 LV.

1. Savāc datus (CoinGecko + alternative.me + SoSoValue ETF):
   - kopējā tirgus kapitalizācija (TOTAL cap)
   - BTC cena + nedēļas izmaiņa
   - ETH cena + nedēļas izmaiņa
   - BTC dominance
   - Fear & Greed indekss
   - BTC ETF nedēļas inflow (summa pēdējām 7 dienām) + izmaiņa pret iepriekšējo nedēļu
   - ETH ETF nedēļas inflow + izmaiņa
2. Ģenerē infografiku (krypto_dashboard_html.py: kie.ai fons + HTML→PNG).
3. Nosūta uz Telegram: bilde + teksts + footer saite kriptonr1.xyz.
4. Sagatavo X (Twitter) postu (≤280, EN, mracrypto.co) un nosūta caur xurl.

Lietošana:
    python3 krypto_weekly.py            # tikai savāc + izdrukā (test)
    SEND_TELEGRAM=1 python3 krypto_weekly.py   # pilns: bilde + teksts + X
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime

import requests

# ---------- konfigurācija ----------
TELEGRAM_CHAT_ID = "1494676964"
FOOTER_LINK = '🔗 Kripto nr. 1 ekosistēma: <a href="https://kriptonr1.xyz/">kriptonr1.xyz</a>'
X_LINK = "Check it out mracrypto.co 🚀"

COINGECKO_GLOBAL = "https://api.coingecko.com/api/v3/global"
FNG_URL = "https://api.alternative.me/fng/"
SOSO_BASE = "https://openapi.sosovalue.com/openapi/v1"
SOSO_ENDPOINT = "/etfs/summary-history"
SOSO_SYMBOLS = ["BTC", "ETH"]
SOSO_COUNTRY = "US"
SOSO_LIMIT = 30  # 30 dienas → pietiek 2 nedēļām


def load_token():
    """Nolasa TELEGRAM_BOT_TOKEN no /root/.hermes/.env (kā asv_calendar.py)."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if tok:
        return tok.strip()
    for env_path in ("/root/.hermes/.env", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                        return line.strip().split("=", 1)[1].strip().strip("'").strip('"')
    raise RuntimeError("TELEGRAM_BOT_TOKEN nav atrasts")


def load_sosovalue_key():
    key = os.environ.get("SOSOVALUE_API_KEY")
    if key:
        return key.strip()
    for env_path in ("/root/scripts/.env", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("SOSOVALUE_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("'").strip('"')
    return None


def _get(url, headers=None, timeout=20, retries=3):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers or {"User-Agent": "curl/8.0"}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} neizdevās: {last}")


def fetch_market():
    """TOTAL cap, BTC/ETH cena + 7d, BTC dominance, Fear & Greed."""
    g = _get(COINGECKO_GLOBAL)["data"]
    total_cap = g["total_market_cap"]["usd"]
    btc_dom = g["market_cap_percentage"].get("btc")

    pr = _get(
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&ids=bitcoin,ethereum"
        "&price_change_percentage=7d"
    )
    btc = next(x for x in pr if x["id"] == "bitcoin")
    eth = next(x for x in pr if x["id"] == "ethereum")

    fng = _get(FNG_URL)["data"][0]
    fng_val = int(fng["value"])
    fng_class = fng.get("value_classification", "")

    return {
        "total_cap": total_cap,
        "btc_price": btc["current_price"],
        "btc_7d": btc.get("price_change_percentage_7d_in_currency", 0) or 0,
        "eth_price": eth["current_price"],
        "eth_7d": eth.get("price_change_percentage_7d_in_currency", 0) or 0,
        "btc_dom": btc_dom,
        "fng": fng_val,
        "fng_class": fng_class,
    }


def fetch_etf_weekly():
    """BTC/ETH ETF nedēļas inflow (pēdējās 7 dienas) + iepriekšējā nedēļa."""
    key = load_sosovalue_key()
    if not key:
        return None
    headers = {"x-soso-api-key": key, "Content-Type": "application/json"}
    out = {}
    for sym in SOSO_SYMBOLS:
        try:
            r = requests.get(
                f"{SOSO_BASE}{SOSO_ENDPOINT}",
                headers=headers,
                params={"symbol": sym, "country_code": SOSO_COUNTRY, "limit": SOSO_LIMIT},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data = data.get("data", [])
            data = sorted(data, key=lambda x: x.get("date", ""))
            last14 = data[-14:]
            this_week = sum(x.get("total_net_inflow", 0) for x in last14[-7:])
            prev_week = sum(x.get("total_net_inflow", 0) for x in last14[:7])
            out[sym] = {"this_week": this_week, "prev_week": prev_week}
        except Exception as e:
            print(f"  ⚠️ SoSoValue {sym} kļūda: {e}")
            out[sym] = None
        time.sleep(4)
    return out


def fmt_usd(v):
    """2.77T / 1.23B / 456.7M / 12.3K formāts."""
    v = float(v)
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:.2f}T"
    if a >= 1e9:
        return f"{v/1e9:.2f}B"
    if a >= 1e6:
        return f"{v/1e6:.1f}M"
    if a >= 1e3:
        return f"{v/1e3:.1f}K"
    return f"{v:.0f}"


def fmt_pct(v):
    return f"{v:+.1f}%"


def arrow(v):
    return "🟢" if v >= 0 else "🔴"


def build_telegram_text(m, etf):
    lines = []
    lines.append("📊 <b>Nedēļas kripto tirgus pārskats</b>")
    lines.append("")
    lines.append(f"💰 Kopējā tirgus kapitalizācija: ${fmt_usd(m['total_cap'])}")
    lines.append(f"₿ Bitcoin (BTC): ${m['btc_price']:,.0f} {arrow(m['btc_7d'])} {fmt_pct(m['btc_7d'])} (7d)")
    lines.append(f"Ξ Ethereum (ETH): ${m['eth_price']:,.0f} {arrow(m['eth_7d'])} {fmt_pct(m['eth_7d'])} (7d)")
    lines.append(f"📈 BTC dominance: {m['btc_dom']:.1f}%")
    lines.append(f"😨 Fear & Greed: {m['fng']} ({m['fng_class']})")
    lines.append("")
    if etf:
        for sym in ("BTC", "ETH"):
            e = etf.get(sym)
            if e and e["this_week"] is not None:
                chg = e["this_week"] - e["prev_week"]
                lines.append(
                    f"{'₿' if sym=='BTC' else 'Ξ'} {sym} ETF nedēļas inflow: {fmt_usd(e['this_week'])} "
                    f"{arrow(chg)} {fmt_usd(chg)} vs iepr. nedēļa"
                )
    lines.append("")
    lines.append(FOOTER_LINK)
    return "\n".join(lines)


def build_x_post(m, etf):
    """X post ≤280 rakstzīmes, EN, mracrypto.co."""
    lines = []
    lines.append("📊 Weekly Crypto Update:")
    lines.append(f"• TOTAL cap: ${fmt_usd(m['total_cap'])} {arrow(m['btc_7d'])} ({fmt_pct(m['btc_7d'])})")
    lines.append(f"• BTC: ${m['btc_price']:,.0f} {arrow(m['btc_7d'])} ({fmt_pct(m['btc_7d'])})")
    lines.append(f"• ETH: ${m['eth_price']:,.0f} {arrow(m['eth_7d'])} ({fmt_pct(m['eth_7d'])})")
    lines.append(f"• BTC Dom: {m['btc_dom']:.1f}% {arrow(m['btc_dom'] - 50)}")
    lines.append(f"• Fear & Greed: {m['fng']} {arrow(m['fng'] - 50)}")
    if etf and etf.get("BTC") and etf["BTC"]["this_week"] is not None:
        lines.append(f"• BTC ETF (7d): {fmt_usd(etf['BTC']['this_week'])} {arrow(etf['BTC']['this_week'])}")
    lines.append("")
    lines.append(X_LINK)
    return "\n".join(lines)


def send_telegram_photo(token, image_path, caption=None):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {"chat_id": TELEGRAM_CHAT_ID}
    if caption:
        data["caption"] = caption
    with open(image_path, "rb") as f:
        r = requests.post(url, data=data, files={"photo": f}, timeout=40)
    r.raise_for_status()
    j = r.json()
    if j.get("ok"):
        print(f"Sent photo message_id={j['result']['message_id']}")
    else:
        print(f"Kļūda sūtot bildi: {j}")
        sys.exit(1)


def send_telegram_text(token, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("ok"):
        print(f"Sent text message_id={j['result']['message_id']}")
    else:
        print(f"Kļūda sūtot tekstu: {j}")
        sys.exit(1)


def send_x_post(text):
    """Nosūta X postu caur xurl. Ja xurl nav autentificēts, izlaiž ar brīdinājumu."""
    if not text:
        return
    try:
        r = subprocess.run(["xurl", "post", text], capture_output=True, text=True, timeout=60)
        print("xurl exit:", r.returncode)
        print("xurl stdout:", r.stdout[:500])
        if r.stderr:
            print("xurl stderr:", r.stderr[:500])
        if r.returncode != 0:
            print("⚠️ X post neizdevās (xurl), bet Telegram ziņa jau nosūtīta.")
    except FileNotFoundError:
        print("⚠️ xurl nav uzstādīts — X post izlaists.")
    except Exception as e:
        print(f"⚠️ X post kļūda: {e}")


def main():
    send = os.environ.get("SEND_TELEGRAM", "0") == "1"
    print("=== Kripto nedēļas pārskats ===")
    print("Savācu tirgus datus...")
    m = fetch_market()
    print(f"  TOTAL cap: ${fmt_usd(m['total_cap'])}")
    print(f"  BTC: ${m['btc_price']:,.0f} ({fmt_pct(m['btc_7d'])})")
    print(f"  ETH: ${m['eth_price']:,.0f} ({fmt_pct(m['eth_7d'])})")
    print(f"  BTC dom: {m['btc_dom']:.1f}%")
    print(f"  F&G: {m['fng']} ({m['fng_class']})")

    print("Savācu ETF datus...")
    etf = fetch_etf_weekly()
    if etf:
        for sym in ("BTC", "ETH"):
            e = etf.get(sym)
            if e and e["this_week"] is not None:
                print(f"  {sym} ETF 7d: {fmt_usd(e['this_week'])} (prev {fmt_usd(e['prev_week'])})")

    text = build_telegram_text(m, etf)
    x_post = build_x_post(m, etf)

    if not send:
        print("\n=== TELEGRAM TEKSTS (test) ===")
        print(text)
        print("\n=== X POST (test, len=%d) ===" % len(x_post))
        print(x_post)
        print(f"\nX post garums: {len(x_post)}/280")
        return

    token = load_token()

    # 1. Infografika
    img_path = f"/root/scripts/krypto_dashboard_{datetime.now():%Y%m%d}.png"
    try:
        # krypto_dashboard_html.py izmanto /usr/bin/python3 (playwright)
        data_json = json.dumps({**m, "etf": etf})
        cmd = ["/usr/bin/python3", "/root/scripts/krypto_dashboard_html.py", img_path, data_json]
        subprocess.run(cmd, check=True, timeout=400)
        if os.path.exists(img_path):
            send_telegram_photo(token, img_path)
        else:
            print("⚠️ Infografika netika izveidota — sūtu tikai tekstu.")
    except Exception as e:
        print(f"⚠️ Infografikas kļūda: {e} — sūtu tikai tekstu.")

    # 2. Teksts
    send_telegram_text(token, text)

    # 3. X post
    send_x_post(x_post)


if __name__ == "__main__":
    main()
