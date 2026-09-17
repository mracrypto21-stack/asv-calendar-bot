#!/usr/bin/env python3
"""kie.ai premium fona ģenerēšana ASV ekonomikas dashboardam.

Ģenerē tikai FONU (bez teksta/cipariem) caur kie.ai Seedream 5.0 Lite —
dziļš gandrīz melns gradients, neona svečturi, hologrāfisks vērsis (pa kreisi)
un lācis (pa labi). Katru nedēļu fons nedaudz atšķiras (seed no ISO nedēļas
numura → reproducējams, bet mainīgs).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs (asv_dashboard_html.py),
jo AI modeļi slikti renderē ciparus. Šis modulis tikai sagatavo fonu.

Lietošana:
    python3 kie_bg.py <out.png> [seed]
"""
import os
import time
import json
import random
import urllib.request
from datetime import datetime

import requests

KIE_API = "https://api.kie.ai"
KIE_MODEL = "seedream/5-lite-text-to-image"   # lēts (5.5 kredīti), labs
ASPECT = "4:3"
QUALITY = "basic"


def load_api_key():
    key = os.environ.get("KIE_AI_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for env_path in (os.path.join(here, ".env"), "/root/.hermes/.env"):
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("KIE_AI_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("'").strip('"')
    raise RuntimeError("KIE_AI_API_KEY nav atrasts (env vai .env)")


def build_prompt(seed):
    """Uz seed balstīts, katru nedēļu nedaudz atšķirīgs fona prompt.

    Katru nedēļu izvēlas citu SCENE tēmu (vērsis/lācis, kāpjošs tirgus grafiks,
    svečturi, abstrakti finanšu elementi, pilsētas siluets u.c.), lai fons
    laika gaitā atsvaidzinātos un nebūtu monotonisks.
    """
    rng = random.Random(seed)

    lighting = [
        "soft ambient glow", "dramatic rim lighting", "subtle volumetric light",
        "gentle neon glow", "moody cinematic lighting",
    ]
    style = [
        "premium fintech aesthetic", "minimal futuristic", "sleek modern",
        "cyberpunk elegance", "high-end trading terminal",
    ]
    accent = ["cyan", "gold", "teal", "violet", "silver"]
    light = rng.choice(lighting)
    st = rng.choice(style)
    acc = rng.choice(accent)

    # --- dažādas fona tēmas (scenes) ---
    bull_colors = ["neon blue", "cyan", "electric blue", "ice blue"]
    bear_colors = ["neon red", "magenta", "hot pink", "crimson"]
    bull_styles = [
        "stylized holographic wireframe bull charging upward",
        "minimal neon outline of a bull, glowing",
        "sleek holographic bull silhouette with neon wireframe",
        "futuristic wireframe bull in a dynamic charging pose",
    ]
    bear_styles = [
        "stylized holographic wireframe bear walking downward",
        "minimal neon outline of a bear, glowing",
        "sleek holographic bear silhouette with neon wireframe",
        "futuristic wireframe bear in a prowling pose",
    ]
    candlestick = [
        "faint semi-transparent neon candlestick charts in red and green scattered in the background depth",
        "subtle glowing candlestick patterns in red and green rising through the background",
        "dim neon candlestick columns in red and green fading into the dark background",
        "softly glowing candlestick charts in red and green layered in the background",
    ]
    rising_chart = [
        "a large glowing neon line chart trending sharply upward with a rising arrow, bullish market momentum",
        "a holographic rising stock market graph with an upward arrow and green glow",
        "a sweeping neon uptrend line chart climbing across the background with a bullish arrow",
    ]
    falling_chart = [
        "a large glowing neon line chart trending downward with a falling arrow, bearish market momentum",
        "a holographic declining stock market graph with a downward arrow and red glow",
        "a sweeping neon downtrend line chart dropping across the background with a bearish arrow",
    ]
    abstract_fin = [
        "abstract floating holographic coins and candlestick charts in neon tones",
        "floating neon dollar symbols and rising bar charts in the background depth",
        "abstract geometric financial shapes, coins and chart lines in neon glow",
    ]
    skyline = [
        "a futuristic financial district skyline silhouette with glowing windows and neon accents",
        "a dark city skyline with neon-lit skyscrapers and subtle chart lines in the sky",
        "a sleek financial city skyline at night with neon towers and a rising graph",
    ]

    scenes = [
        # (svars, prompt_fragments)
        (3, lambda: (
            f"{rng.choice(bull_styles)} in {rng.choice(bull_colors)} on the left side, "
            f"{rng.choice(bear_styles)} in {rng.choice(bear_colors)} on the right side, "
            f"{rng.choice(candlestick)}"
        )),
        (2, lambda: f"{rng.choice(rising_chart)}, {rng.choice(candlestick)}"),
        (1, lambda: f"{rng.choice(falling_chart)}, {rng.choice(candlestick)}"),
        (2, lambda: f"{rng.choice(abstract_fin)}, {rng.choice(candlestick)}"),
        (1, lambda: f"{rng.choice(skyline)}, {rng.choice(candlestick)}"),
    ]
    weights = [w for w, _ in scenes]
    scene = rng.choices(scenes, weights=weights, k=1)[0][1]()

    prompt = (
        "Premium financial trading dashboard background, deep near-black premium "
        "gradient (dark charcoal center fading to deep indigo edges), "
        f"{scene}, {light}, {st}, subtle {acc} glow, "
        "no text, no numbers, no letters, no words, no labels, "
        "empty background for data overlay"
    )
    return prompt


def check_credits(api_key=None):
    """Atgriež atlikušo kredītu skaitu (float). Ja neizdodas, raise."""
    if api_key is None:
        api_key = load_api_key()
    resp = requests.get(
        f"{KIE_API}/api/v1/chat/credit",
        headers={"Authorization": f"Bearer {api_key}"}, timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"kie.ai credit kļūda: {data}")
    return float(data.get("data", 0))


def create_task(prompt, api_key):
    payload = {
        "model": KIE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": ASPECT,
            "quality": QUALITY,
            "output_format": "png",
            "nsfw_checker": False,
        },
    }
    resp = requests.post(
        f"{KIE_API}/api/v1/jobs/createTask",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"kie.ai createTask kļūda: {data}")
    return data["data"]["taskId"]


def poll_task(task_id, api_key, timeout=180):
    url = f"{KIE_API}/api/v1/jobs/recordInfo?taskId={task_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        state = data.get("state")
        if state == "success":
            urls = data.get("resultJson", "")
            try:
                urls = json.loads(urls).get("resultUrls", [])
            except Exception:
                urls = []
            if urls:
                return urls[0]
            raise RuntimeError("kie.ai: success, bet nav rezultāta URL")
        if state in ("failed", "error"):
            raise RuntimeError(f"kie.ai uzdevums neizdevās: {data.get('failMsg')}")
        time.sleep(5)
    raise RuntimeError("kie.ai: uzdevuma apstrādes taimauts")


def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(out_path, "wb") as f:
            f.write(r.read())
    return out_path


def generate_background(out_path, seed=None):
    """Ģenerē premium fonu caur kie.ai un saglabā to out_path."""
    if seed is None:
        iso = datetime.now().isocalendar()
        seed = iso[0] * 100 + iso[1]  # piem. 2026*100 + 38
    api_key = load_api_key()
    prompt = build_prompt(seed)
    print(f"🎨 kie.ai fons (seed={seed})")
    task_id = create_task(prompt, api_key)
    url = poll_task(task_id, api_key)
    download(url, out_path)
    print(f"✅ Fons saglabāts: {out_path}")
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/kie_bg.png"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    generate_background(out, seed)
